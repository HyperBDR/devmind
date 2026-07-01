from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import re

from cloud_billing.dashboard import _build_exchange_rate_info
from django.db import transaction
from django.utils import timezone

from .models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingPriceHistory,
)


ZERO = Decimal("0")
ONE = Decimal("1")
SUPPORTED_DISPLAY_CURRENCIES = {"USD", "CNY"}
MANUAL_MODEL_PRICE_FIELDS = {
    "input_price_per_million": (
        ModelPriceItem.DIMENSION_TEXT_INPUT,
        ModelPriceItem.UNIT_PER_1M_TOKENS,
    ),
    "output_price_per_million": (
        ModelPriceItem.DIMENSION_TEXT_OUTPUT,
        ModelPriceItem.UNIT_PER_1M_TOKENS,
    ),
    "cache_input_price_per_million": (
        ModelPriceItem.DIMENSION_CACHE_INPUT,
        ModelPriceItem.UNIT_PER_1M_TOKENS,
    ),
    "image_output_price_per_image": (
        ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
        ModelPriceItem.UNIT_PER_IMAGE,
    ),
    "audio_input_price_per_second": (
        ModelPriceItem.DIMENSION_AUDIO_INPUT,
        ModelPriceItem.UNIT_PER_SECOND,
    ),
    "audio_output_price_per_second": (
        ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
        ModelPriceItem.UNIT_PER_SECOND,
    ),
    "video_input_price_per_second": (
        ModelPriceItem.DIMENSION_VIDEO_INPUT,
        ModelPriceItem.UNIT_PER_SECOND,
    ),
    "video_output_price_per_second": (
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
        ModelPriceItem.UNIT_PER_SECOND,
    ),
}


@dataclass(frozen=True)
class UnitPrices:
    """Resolved procurement unit prices for a channel/model pair."""

    input_per_million: Decimal
    output_per_million: Decimal
    cache_input_per_million: Decimal
    image_output_per_image: Decimal
    audio_input_per_second: Decimal
    audio_output_per_second: Decimal
    video_input_per_second: Decimal
    video_output_per_second: Decimal


@dataclass(frozen=True)
class CurrencyConversionContext:
    """Exchange-rate context for panel-level display conversion."""

    display_currency: str
    usd_to_cny_rate: Decimal
    rate_source_label: str
    rate_source_url: str
    rate_collected_at: str


def normalize_currency(value: str | None) -> str:
    """Normalize currency codes used by pricing records."""
    return str(value or "").strip().upper()


def ensure_meta_model(
    *,
    code: str,
    name: str,
    provider=None,
    raw_code: str = "",
    modality: str = LLMModel.MODALITY_TEXT,
    context_window: int = 0,
    max_output_tokens: int = 0,
) -> MetaModel:
    """Create or update canonical model identity for a source model.

    The ``provider`` argument is treated as a price-sheet hint. The
    canonical owner is resolved from the model code, and a supplier
    alias is never written as the meta model owner.
    ``raw_code`` keeps the original collector spelling so alias-only
    lookups can still reuse an existing canonical row.
    """
    from .constants import (
        canonical_meta_model_identity,
        meta_model_owner_payload,
        resolve_meta_model_owner_fields,
    )

    reported_code = str(code or "").strip()
    reported_name = str(name or reported_code or raw_code).strip()
    source_code = str(raw_code or reported_code or reported_name).strip()
    identity = canonical_meta_model_identity(source_code, reported_name)
    canonical_code = identity["code"]
    canonical_name = identity["name"]
    seed_aliases = identity["aliases"]
    owner = meta_model_owner_payload(canonical_code, provider)
    defaults = {
        "name": canonical_name,
        **owner,
        "modality": modality or MetaModel.MODALITY_TEXT,
        "context_window": context_window or 0,
        "max_output_tokens": max_output_tokens or 0,
        "status": MetaModel.STATUS_ACTIVE,
        "aliases": seed_aliases,
    }
    meta_model = MetaModel.objects.filter(code=canonical_code).first()
    created = False
    if meta_model is None:
        meta_model = match_meta_model_by_alias_or_name(
            raw_code=raw_code,
            reported_code=reported_code,
            reported_name=reported_name,
            canonical_code=canonical_code,
            canonical_name=canonical_name,
            seed_aliases=seed_aliases,
        )
    if meta_model is None:
        meta_model, created = MetaModel.objects.get_or_create(
            code=canonical_code,
            defaults=defaults,
        )
    if created:
        return meta_model

    changed_fields = []
    if canonical_name and meta_model.name in {"", meta_model.code}:
        meta_model.name = canonical_name
        changed_fields.append("name")
    owner = resolve_meta_model_owner_fields(meta_model, provider)
    for field_name, value in owner.items():
        if getattr(meta_model, field_name) != value:
            setattr(meta_model, field_name, value)
            changed_fields.append(field_name)
    if modality and meta_model.modality == MetaModel.MODALITY_TEXT:
        if modality != MetaModel.MODALITY_TEXT:
            meta_model.modality = modality
            changed_fields.append("modality")
    if context_window and context_window > meta_model.context_window:
        meta_model.context_window = context_window
        changed_fields.append("context_window")
    if max_output_tokens and max_output_tokens > meta_model.max_output_tokens:
        meta_model.max_output_tokens = max_output_tokens
        changed_fields.append("max_output_tokens")
    if meta_model.status == MetaModel.STATUS_UNKNOWN:
        meta_model.status = MetaModel.STATUS_ACTIVE
        changed_fields.append("status")
    merged_aliases = list(meta_model.aliases or [])
    for alias in meta_model_alias_tokens(
        raw_code=raw_code,
        reported_code=reported_code,
        reported_name=reported_name,
        canonical_code=canonical_code,
        canonical_name=canonical_name,
        seed_aliases=seed_aliases,
    ):
        if alias and alias not in merged_aliases:
            merged_aliases.append(alias)
    if merged_aliases != list(meta_model.aliases or []):
        meta_model.aliases = merged_aliases
        changed_fields.append("aliases")
    if changed_fields:
        changed_fields.append("updated_at")
        meta_model.save(update_fields=changed_fields)
    return meta_model


def match_meta_model_by_alias_or_name(
    *,
    raw_code: str,
    reported_code: str,
    reported_name: str,
    canonical_code: str,
    canonical_name: str,
    seed_aliases: list[str],
) -> MetaModel | None:
    """Reuse an existing meta model through aliases or display name."""
    tokens = meta_model_alias_tokens(
        raw_code=raw_code,
        reported_code=reported_code,
        reported_name=reported_name,
        canonical_code=canonical_code,
        canonical_name=canonical_name,
        seed_aliases=seed_aliases,
    )
    if not tokens:
        return None

    all_meta = list(MetaModel.objects.all())
    alias_index = {
        alias: meta
        for meta in all_meta
        for alias in (meta.aliases or [])
        if alias
    }
    for token in tokens:
        hit = alias_index.get(token)
        if hit is not None:
            return hit

    normalized_name = normalize_meta_model_lookup_name(canonical_name)
    if not normalized_name:
        return None
    for meta in all_meta:
        if normalize_meta_model_lookup_name(meta.name) == normalized_name:
            return meta
    return None


def meta_model_alias_tokens(
    *,
    raw_code: str,
    reported_code: str,
    reported_name: str,
    canonical_code: str,
    canonical_name: str,
    seed_aliases: list[str],
) -> list[str]:
    """Return distinct alias tokens relevant for one collector record."""
    tokens = []
    for token in (
        raw_code,
        reported_code,
        reported_name,
        canonical_code,
        canonical_name,
        *seed_aliases,
    ):
        value = str(token or "").strip()
        if value and value not in tokens:
            tokens.append(value)
    return tokens


def normalize_meta_model_lookup_name(value: str | None) -> str:
    """Normalize a model display name for loose matching."""
    return re.sub(r"[\s_\-]+", "", str(value or "").strip().lower())


def price_role_for_source(
    source: PriceCollectionSource | None,
    *,
    meta_model: MetaModel | None = None,
) -> str:
    """Map a price source to the business role of one model row."""
    if source is None:
        return LLMModel.PRICE_ROLE_UNKNOWN
    category = source.source_category
    if (
        category
        == PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        and meta_model is not None
    ):
        category = business_source_category_for_source_model(
            source=source,
            meta_model=meta_model,
        )
    if (
        category
        == PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return LLMModel.PRICE_ROLE_OFFICIAL
    if category == LLMModel.PRICE_ROLE_CLOUD_HOSTED:
        return LLMModel.PRICE_ROLE_CLOUD_HOSTED
    if category == PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER:
        return LLMModel.PRICE_ROLE_SUPPLIER
    if category == PriceCollectionSource.SOURCE_CATEGORY_MANUAL:
        return LLMModel.PRICE_ROLE_MANUAL
    return LLMModel.PRICE_ROLE_UNKNOWN


def canonical_owner_code_for_meta_model(meta_model: MetaModel | None) -> str:
    """Resolve the real owner code for one canonical meta model."""
    if meta_model is None:
        return ""

    from .constants import meta_model_owner_payload

    owner = meta_model_owner_payload(meta_model.code)
    return owner["owner_code"] or meta_model.owner_code


def business_source_category_for_source_model(
    *,
    source: PriceCollectionSource,
    meta_model: MetaModel | None,
) -> str:
    """Return official only when the source provider matches the owner."""
    raw_category = source.source_category
    if (
        raw_category
        != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return raw_category

    source_owner_code = str(getattr(source.provider, "code", "") or "")
    model_owner_code = canonical_owner_code_for_meta_model(meta_model)
    if not source_owner_code or not model_owner_code:
        return raw_category
    if source_owner_code == model_owner_code:
        return raw_category
    return LLMModel.PRICE_ROLE_CLOUD_HOSTED


def find_aggregated_model(
    *,
    provider,
    code: str,
    meta_model: MetaModel,
    source: PriceCollectionSource | None = None,
) -> LLMModel | None:
    """Return the best shared model row for non-promoted source prices."""
    current_source_id = source.id if source else None
    exact_matches = list(
        LLMModel.objects.filter(
            provider=provider,
            code=code,
        ).select_related("source")
    )
    match = preferred_aggregated_model(
        exact_matches,
        current_source_id=current_source_id,
    )
    if match is not None:
        return match

    meta_matches = list(
        LLMModel.objects.filter(
            provider=provider,
            meta_model=meta_model,
        ).select_related("source")
    )
    return preferred_aggregated_model(
        meta_matches,
        current_source_id=current_source_id,
    )


def preferred_aggregated_model(
    candidates: list[LLMModel],
    *,
    current_source_id: int | None,
) -> LLMModel | None:
    """Pick the least source-bound model row from candidate matches."""
    if not candidates:
        return None

    def sort_key(model: LLMModel) -> tuple[int, int, int, int]:
        category = (
            model.source.source_category
            if model.source_id and model.source is not None
            else ""
        )
        is_current_source = (
            bool(current_source_id)
            and model.source_id == current_source_id
        )
        if category == PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER:
            category_rank = 0
        elif category == "":
            category_rank = 1
        elif category == PriceCollectionSource.SOURCE_CATEGORY_MANUAL:
            category_rank = 2 if is_current_source else 3
        elif category == PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER:
            category_rank = 4 if is_current_source else 5
        elif model.price_role == LLMModel.PRICE_ROLE_CLOUD_HOSTED:
            category_rank = 4 if is_current_source else 5
        elif category == PriceCollectionSource.SOURCE_CATEGORY_UNKNOWN:
            category_rank = 6
        else:
            category_rank = 7
        supplier_role_rank = (
            1
            if model.price_role
            in (
                LLMModel.PRICE_ROLE_SUPPLIER,
                LLMModel.PRICE_ROLE_CLOUD_HOSTED,
            )
            else 0
        )
        return (
            category_rank,
            supplier_role_rank,
            0 if is_current_source else 1,
            model.id,
        )

    return min(candidates, key=sort_key)


def update_aggregated_model_identity(
    model: LLMModel,
    *,
    meta_model: MetaModel,
    name: str,
    modality: str,
    currency: str,
    current_source: PriceCollectionSource | None = None,
) -> list[str]:
    """Refresh shared model identity without binding it to one source."""
    changed_fields = []
    desired_name = str(name or "").strip() or model.name
    desired_currency = normalize_currency(currency) or model.currency

    if model.meta_model_id != meta_model.id:
        model.meta_model = meta_model
        changed_fields.append("meta_model")
    if desired_name and model.name in {"", model.code}:
        model.name = desired_name
        changed_fields.append("name")
    if (
        modality
        and model.modality == LLMModel.MODALITY_TEXT
        and modality != LLMModel.MODALITY_TEXT
    ):
        model.modality = modality
        changed_fields.append("modality")
    if desired_currency and not normalize_currency(model.currency):
        model.currency = desired_currency
        changed_fields.append("currency")
    if not model.is_active:
        model.is_active = True
        changed_fields.append("is_active")

    if (
        current_source is not None
        and model.source_id == current_source.id
        and can_detach_model_from_source(model)
    ):
        model.source = None
        model.source_url = ""
        changed_fields.extend(["source", "source_url"])

    return changed_fields


def can_detach_model_from_source(model: LLMModel) -> bool:
    """Return whether a legacy source-bound model can become shared."""
    if not model.source_id:
        return False
    return not LLMModel.objects.filter(
        provider=model.provider,
        code=model.code,
        source__isnull=True,
    ).exclude(id=model.id).exists()


def build_currency_conversion_context(
    display_currency: str | None = None,
) -> CurrencyConversionContext:
    """Build a display-currency context using operations console rates."""
    target_currency = normalize_currency(display_currency) or "CNY"
    if target_currency not in SUPPORTED_DISPLAY_CURRENCIES:
        target_currency = "CNY"

    exchange_info = _build_exchange_rate_info()
    rate = decimal_or_zero(exchange_info.get("exchange_rate")) or ONE
    return CurrencyConversionContext(
        display_currency=target_currency,
        usd_to_cny_rate=rate,
        rate_source_label=str(exchange_info.get("rate_source_label") or ""),
        rate_source_url=str(exchange_info.get("rate_source_url") or ""),
        rate_collected_at=str(exchange_info.get("rate_collected_at") or ""),
    )


def convert_currency_amount(
    value,
    source_currency: str | None,
    context: CurrencyConversionContext,
) -> Decimal | None:
    """Convert a money amount into the panel display currency."""
    source = normalize_currency(source_currency)
    target = context.display_currency
    if not source:
        return None
    amount = decimal_or_zero(value)
    if source == target:
        return amount
    if source == "USD" and target == "CNY":
        return amount * context.usd_to_cny_rate
    if source == "CNY" and target == "USD":
        return amount / context.usd_to_cny_rate
    return None


def convert_currency_between(
    value,
    source_currency: str | None,
    target_currency: str | None,
) -> Decimal | None:
    """Convert a money amount between supported pricing currencies."""
    source = normalize_currency(source_currency)
    target = normalize_currency(target_currency)
    if not source or not target:
        return None
    if source == target:
        return decimal_or_zero(value)
    context = build_currency_conversion_context(target)
    return convert_currency_amount(value, source, context)


def can_convert_currency(
    source_currency: str | None,
    context: CurrencyConversionContext,
) -> bool:
    """Return whether source can be shown in the display currency."""
    source = normalize_currency(source_currency)
    if not source:
        return False
    if source == context.display_currency:
        return True
    return source in SUPPORTED_DISPLAY_CURRENCIES


@transaction.atomic
def import_manual_model_prices(
    *,
    source: PriceCollectionSource,
    provider=None,
    rows: list[dict],
    default_currency: str,
    updates_model_prices: bool,
) -> dict:
    """Import manually maintained model prices into durable price tables."""
    now = timezone.now()
    effective_updates_model_prices = updates_model_prices
    if (
        source.source_category
        == PriceCollectionSource.SOURCE_CATEGORY_MANUAL
    ):
        effective_updates_model_prices = False
    run = source.collection_runs.create(status="running")
    created_count = 0
    updated_count = 0
    price_item_count = 0
    skipped_count = 0

    for index, row in enumerate(rows, start=1):
        model_code = str(row.get("model_code") or "").strip()
        if not model_code:
            skipped_count += 1
            continue

        row_provider = resolve_manual_import_provider(
            row,
            default_provider=provider,
            model_code=model_code,
        )
        meta_model = ensure_meta_model(
            code=model_code,
            name=row.get("model_name") or model_code,
            provider=row_provider,
            modality=row.get("modality") or LLMModel.MODALITY_TEXT,
        )
        if effective_updates_model_prices:
            model, created = LLMModel.objects.get_or_create(
                provider=row_provider,
                source=source,
                code=model_code,
                defaults={
                    "meta_model": meta_model,
                    "name": row.get("model_name") or model_code,
                    "modality": (
                        row.get("modality") or LLMModel.MODALITY_TEXT
                    ),
                    "currency": normalize_currency(
                        row.get("currency") or default_currency,
                    ),
                    "source_url": (
                        row.get("source_url") or source.endpoint_url
                    ),
                    "price_role": price_role_for_source(
                        source,
                        meta_model=meta_model,
                    ),
                    "last_price_updated_at": now,
                },
            )
        else:
            model = find_aggregated_model(
                provider=row_provider,
                code=model_code,
                meta_model=meta_model,
                source=source,
            )
            created = model is None
            if model is None:
                model = LLMModel.objects.create(
                    provider=row_provider,
                    meta_model=meta_model,
                    name=row.get("model_name") or model_code,
                    code=model_code,
                    modality=(
                        row.get("modality") or LLMModel.MODALITY_TEXT
                    ),
                    currency=normalize_currency(
                        row.get("currency") or default_currency,
                    ),
                    price_role=price_role_for_source(
                        source,
                        meta_model=meta_model,
                    ),
                    is_active=True,
                )
        if created:
            created_count += 1
        else:
            updated_count += 1

        changed_fields = update_model_from_manual_row(
            model,
            row,
            source=source,
            default_currency=default_currency,
            updates_model_prices=effective_updates_model_prices,
            now=now,
        )
        if changed_fields:
            model.save(update_fields=changed_fields)

        price_item_count += sync_manual_model_price_items(
            source=source,
            provider=row_provider,
            model=model,
            row=row,
            row_index=index,
            default_currency=default_currency,
        )

    source.last_collected_at = now
    source.currency = normalize_currency(default_currency) or source.currency
    source.updates_model_prices = effective_updates_model_prices
    source.save(
        update_fields=[
            "last_collected_at",
            "currency",
            "updates_model_prices",
            "updated_at",
        ]
    )
    run.status = "succeeded"
    run.finished_at = now
    run.collected_count = len(rows)
    run.created_count = created_count
    run.updated_count = updated_count
    run.skipped_count = skipped_count
    run.metadata = {
        "import_mode": "manual_table",
        "price_item_count": price_item_count,
        "updates_model_prices": effective_updates_model_prices,
    }
    run.save()
    return {
        "run_id": run.id,
        "source_id": source.id,
        "collected_count": run.collected_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "price_item_count": price_item_count,
    }


def resolve_manual_import_provider(
    row: dict,
    *,
    default_provider: LLMProvider | None,
    model_code: str,
) -> LLMProvider:
    """Resolve the provider row for one manually imported price row."""

    if default_provider is not None:
        return default_provider

    matched = match_manual_import_provider(row)
    if matched is not None:
        return matched

    model_matches = list(
        LLMModel.objects.filter(code=model_code)
        .select_related("provider")
        .order_by("id")
    )
    provider_ids = {
        model.provider_id for model in model_matches if model.provider_id
    }
    if len(provider_ids) == 1:
        return model_matches[0].provider

    raise ValueError(
        "Cannot resolve model provider for manual price row "
        f"{model_code}. Add provider_code or select an existing model."
    )


def match_manual_import_provider(row: dict) -> LLMProvider | None:
    """Match row-level provider fields to an existing model provider."""

    labels = {
        normalize_provider_match_label(row.get(field))
        for field in (
            "provider",
            "provider_code",
            "provider_name",
            "model_provider",
            "model_source",
        )
        if normalize_provider_match_label(row.get(field))
    }
    if not labels:
        return None

    for provider in LLMProvider.objects.filter(is_active=True).order_by("id"):
        provider_labels = {
            normalize_provider_match_label(provider.code),
            normalize_provider_match_label(provider.name),
        }
        if labels & provider_labels:
            return provider
    return None


def normalize_provider_match_label(value: str | None) -> str:
    """Normalize provider labels for manual import matching."""

    return re.sub(r"[\s_\-]+", "", str(value or "").strip().lower())


def update_model_from_manual_row(
    model: LLMModel,
    row: dict,
    *,
    source: PriceCollectionSource,
    default_currency: str,
    updates_model_prices: bool,
    now,
) -> list[str]:
    """Update the model master row from a manual price table row."""
    changed_fields = []
    basic_updates = {
        "meta_model": ensure_meta_model(
            code=model.code,
            name=row.get("model_name") or model.name,
            provider=model.provider,
            modality=row.get("modality") or model.modality,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
        ),
        "name": row.get("model_name") or model.name,
        "modality": row.get("modality") or model.modality,
        "currency": normalize_currency(
            row.get("currency") or default_currency,
        ),
    }
    for field, value in basic_updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed_fields.append(field)

    if not updates_model_prices:
        if model.source_id == source.id and can_detach_model_from_source(model):
            model.source = None
            model.source_url = ""
            changed_fields.extend(["source", "source_url"])
        return changed_fields

    promoted_updates = {
        "source": source,
        "source_url": row.get("source_url") or source.endpoint_url,
        "price_role": price_role_for_source(
            source,
            meta_model=model.meta_model,
        ),
        "last_price_updated_at": now,
    }
    for field, value in promoted_updates.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed_fields.append(field)

    for field in MANUAL_MODEL_PRICE_FIELDS:
        if field not in row or row.get(field) is None:
            continue
        value = row.get(field)
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed_fields.append(field)
    return changed_fields


def sync_manual_model_price_items(
    *,
    source: PriceCollectionSource,
    provider,
    model: LLMModel,
    row: dict,
    row_index: int,
    default_currency: str,
) -> int:
    """Replace current manual price items for one model/source pair."""
    currency = normalize_currency(row.get("currency") or default_currency)
    now = timezone.now()
    payloads = []
    for field, (dimension, billing_unit) in MANUAL_MODEL_PRICE_FIELDS.items():
        if field not in row or row.get(field) is None:
            continue
        payloads.append(
            {
                "provider": provider,
                "model": model,
                "meta_model": model.meta_model,
                "source": source,
                "price_role": price_role_for_source(
                    source,
                    meta_model=model.meta_model,
                ),
                "dimension": dimension,
                "billing_unit": billing_unit,
                "currency": currency,
                "unit_price": row[field],
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": None,
                "tier_end": None,
                "spec": {
                    "import_mode": "manual_table",
                    "row_index": row_index,
                    "source_field": field,
                },
                "source_url": row.get("source_url") or source.endpoint_url,
                "raw_payload": json_safe_payload(row),
                "is_current": True,
            }
        )
    if not payloads:
        return 0

    ModelPriceItem.objects.filter(
        model=model,
        source=source,
        is_current=True,
    ).update(is_current=False, effective_to=now)

    for payload in payloads:
        fingerprint = stable_fingerprint(
            {
                "source": source.id,
                "dimension": payload["dimension"],
                "billing_unit": payload["billing_unit"],
                "currency": payload["currency"],
                "unit_price": str(payload["unit_price"]),
                "tier_type": payload["tier_type"],
                "tier_start": "",
                "tier_end": "",
                "spec": payload["spec"],
            }
        )
        payload["price_fingerprint"] = fingerprint
        price_item, _ = ModelPriceItem.objects.update_or_create(
            model=model,
            dimension=payload["dimension"],
            billing_unit=payload["billing_unit"],
            currency=payload["currency"],
            price_fingerprint=fingerprint,
            defaults=payload,
        )
        if not price_item.is_current or price_item.effective_to is not None:
            price_item.is_current = True
            price_item.effective_to = None
            price_item.save(update_fields=["is_current", "effective_to"])
    return len(payloads)


def resolve_channel_model_currency(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None = None,
) -> str:
    """Resolve the procurement currency for one channel/model price."""
    if override and normalize_currency(override.currency):
        return normalize_currency(override.currency)
    if normalize_currency(channel.currency):
        return normalize_currency(channel.currency)
    return normalize_currency(model.currency) or "USD"


def resolve_resale_listing_currency(listing: ResaleListing) -> str:
    """Resolve the retail currency for one resale listing."""
    if normalize_currency(listing.currency):
        return normalize_currency(listing.currency)
    if normalize_currency(listing.platform.currency):
        return normalize_currency(listing.platform.currency)
    return normalize_currency(listing.model.currency) or "USD"


def decimal_or_zero(value) -> Decimal:
    """Return a Decimal value, falling back to zero."""
    if value is None:
        return ZERO
    return Decimal(str(value))


def resolve_channel_model_price(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None = None,
    video_resolution: str = "",
) -> UnitPrices:
    """Resolve final procurement unit prices after channel overrides."""
    if override is None:
        override = ChannelModelPrice.objects.filter(
            channel=channel,
            model=model,
        ).first()

    ratio = decimal_or_zero(channel.settlement_ratio) or ONE
    if override and override.settlement_ratio is not None:
        ratio = decimal_or_zero(override.settlement_ratio)

    input_price = decimal_or_zero(model.input_price_per_million) * ratio
    output_price = decimal_or_zero(model.output_price_per_million) * ratio
    cache_input_price = (
        decimal_or_zero(model.cache_input_price_per_million) * ratio
    )
    image_output_price = (
        decimal_or_zero(model.image_output_price_per_image) * ratio
    )
    audio_input_price = (
        decimal_or_zero(model.audio_input_price_per_second) * ratio
    )
    audio_output_price = (
        decimal_or_zero(model.audio_output_price_per_second) * ratio
    )
    video_input_price = (
        decimal_or_zero(model.video_input_price_per_second) * ratio
    )
    video_output_price = (
        decimal_or_zero(model.video_output_price_per_second) * ratio
    )

    source_unit_prices = source_unit_prices_for_channel_model(
        channel,
        model,
        override=override,
    )
    if source_unit_prices:
        input_price = source_unit_prices.input_per_million * ratio
        output_price = source_unit_prices.output_per_million * ratio
        cache_input_price = (
            source_unit_prices.cache_input_per_million * ratio
        )
        image_output_price = source_unit_prices.image_output_per_image * ratio
        audio_input_price = source_unit_prices.audio_input_per_second * ratio
        audio_output_price = source_unit_prices.audio_output_per_second * ratio
        video_input_price = source_unit_prices.video_input_per_second * ratio
        video_output_price = source_unit_prices.video_output_per_second * ratio

    resolution_prices = model.video_resolution_prices or {}
    if video_resolution and video_resolution in resolution_prices:
        resolution_price = resolution_prices.get(video_resolution) or {}
        if resolution_price.get("input") is not None:
            video_input_price = decimal_or_zero(resolution_price.get("input"))
            video_input_price *= ratio
        if resolution_price.get("output") is not None:
            video_output_price = decimal_or_zero(
                resolution_price.get("output")
            )
            video_output_price *= ratio

    if override:
        if override.custom_input_price_per_million is not None:
            input_price = decimal_or_zero(
                override.custom_input_price_per_million
            )
        if override.custom_output_price_per_million is not None:
            output_price = decimal_or_zero(
                override.custom_output_price_per_million
            )
        if override.custom_audio_input_price_per_second is not None:
            audio_input_price = decimal_or_zero(
                override.custom_audio_input_price_per_second
            )
        if override.custom_audio_output_price_per_second is not None:
            audio_output_price = decimal_or_zero(
                override.custom_audio_output_price_per_second
            )
        if override.custom_video_input_price_per_second is not None:
            video_input_price = decimal_or_zero(
                override.custom_video_input_price_per_second
            )
        if override.custom_video_output_price_per_second is not None:
            video_output_price = decimal_or_zero(
                override.custom_video_output_price_per_second
            )

        custom_resolution_prices = (
            override.custom_video_resolution_prices or {}
        )
        if video_resolution and video_resolution in custom_resolution_prices:
            custom_price = custom_resolution_prices.get(video_resolution) or {}
            if custom_price.get("input") is not None:
                video_input_price = decimal_or_zero(custom_price.get("input"))
            if custom_price.get("output") is not None:
                video_output_price = decimal_or_zero(
                    custom_price.get("output")
                )

    return UnitPrices(
        input_per_million=input_price,
        output_per_million=output_price,
        cache_input_per_million=cache_input_price,
        image_output_per_image=image_output_price,
        audio_input_per_second=audio_input_price,
        audio_output_per_second=audio_output_price,
        video_input_per_second=video_input_price,
        video_output_per_second=video_output_price,
    )


def source_unit_prices_for_channel_model(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None,
) -> UnitPrices | None:
    """Resolve flat unit prices from the selected procurement source."""
    if not override:
        return None

    target_currency = resolve_channel_model_currency(
        channel,
        model,
        override=override,
    )
    values = {}
    for item in current_model_price_items_for_channel_price(override):
        if item.tier_type != ModelPriceItem.TIER_FLAT:
            continue
        unit_price = convert_currency_between(
            item.unit_price,
            item.currency,
            target_currency,
        )
        values[item.dimension] = unit_price or decimal_or_zero(
            item.unit_price
        )

    if not values:
        return None

    return UnitPrices(
        input_per_million=values.get(
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ZERO,
        ),
        output_per_million=values.get(
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ZERO,
        ),
        cache_input_per_million=values.get(
            ModelPriceItem.DIMENSION_CACHE_INPUT,
            ZERO,
        ),
        image_output_per_image=values.get(
            ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
            ZERO,
        ),
        audio_input_per_second=values.get(
            ModelPriceItem.DIMENSION_AUDIO_INPUT,
            ZERO,
        ),
        audio_output_per_second=values.get(
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
            ZERO,
        ),
        video_input_per_second=values.get(
            ModelPriceItem.DIMENSION_VIDEO_INPUT,
            ZERO,
        ),
        video_output_per_second=values.get(
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            ZERO,
        ),
    )


def calculate_usage_cost(
    unit_prices: UnitPrices,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    audio_input_seconds: Decimal | int | str = 0,
    audio_output_seconds: Decimal | int | str = 0,
    video_input_seconds: Decimal | int | str = 0,
    video_output_seconds: Decimal | int | str = 0,
) -> Decimal:
    """Calculate total cost for token and media usage."""
    input_cost = Decimal(input_tokens or 0) / Decimal(1000000)
    input_cost *= unit_prices.input_per_million
    output_cost = Decimal(output_tokens or 0) / Decimal(1000000)
    output_cost *= unit_prices.output_per_million

    audio_input_cost = decimal_or_zero(audio_input_seconds)
    audio_input_cost *= unit_prices.audio_input_per_second
    audio_output_cost = decimal_or_zero(audio_output_seconds)
    audio_output_cost *= unit_prices.audio_output_per_second
    video_input_cost = decimal_or_zero(video_input_seconds)
    video_input_cost *= unit_prices.video_input_per_second
    video_output_cost = decimal_or_zero(video_output_seconds)
    video_output_cost *= unit_prices.video_output_per_second

    return (
        input_cost
        + output_cost
        + audio_input_cost
        + audio_output_cost
        + video_input_cost
        + video_output_cost
    ).quantize(Decimal("0.000001"))


def calculate_channel_model_cost(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    audio_input_seconds: Decimal | int | str = 0,
    audio_output_seconds: Decimal | int | str = 0,
    video_input_seconds: Decimal | int | str = 0,
    video_output_seconds: Decimal | int | str = 0,
    video_resolution: str = "",
) -> Decimal:
    """Resolve channel prices and calculate expected usage cost."""
    unit_prices = resolve_channel_model_price(
        channel,
        model,
        video_resolution=video_resolution,
    )
    return calculate_usage_cost(
        unit_prices,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        audio_input_seconds=audio_input_seconds,
        audio_output_seconds=audio_output_seconds,
        video_input_seconds=video_input_seconds,
        video_output_seconds=video_output_seconds,
    )


def record_channel_model_price_history(
    price: ChannelModelPrice,
    *,
    video_resolution: str = "",
) -> ChannelModelPriceHistory | None:
    """Record a channel/model price version when price fields change."""
    unit_prices = resolve_channel_model_price(
        price.channel,
        price.model,
        override=price,
        video_resolution=video_resolution,
    )
    currency = resolve_channel_model_currency(
        price.channel,
        price.model,
        override=price,
    )
    payload = {
        "price_source_id": price.price_source_id,
        "is_listed": price.is_listed,
        "settlement_ratio": decimal_to_string(price.settlement_ratio),
        "currency": currency,
        "input_price_per_million": decimal_to_string(
            unit_prices.input_per_million
        ),
        "output_price_per_million": decimal_to_string(
            unit_prices.output_per_million
        ),
        "image_output_price_per_image": decimal_to_string(
            unit_prices.image_output_per_image
        ),
        "audio_input_price_per_second": decimal_to_string(
            unit_prices.audio_input_per_second
        ),
        "audio_output_price_per_second": decimal_to_string(
            unit_prices.audio_output_per_second
        ),
        "video_input_price_per_second": decimal_to_string(
            unit_prices.video_input_per_second
        ),
        "video_output_price_per_second": decimal_to_string(
            unit_prices.video_output_per_second
        ),
        "video_resolution_prices": price.model.video_resolution_prices or {},
    }
    fingerprint = stable_fingerprint(payload)
    existing = ChannelModelPriceHistory.objects.filter(
        channel=price.channel,
        model=price.model,
        price_fingerprint=fingerprint,
    ).first()
    if existing:
        return None

    now = timezone.now()
    ChannelModelPriceHistory.objects.filter(
        channel=price.channel,
        model=price.model,
        is_current=True,
    ).update(
        is_current=False,
        effective_to=now,
    )
    return ChannelModelPriceHistory.objects.create(
        channel=price.channel,
        model=price.model,
        meta_model=price.meta_model,
        price_source=price.price_source,
        is_listed=price.is_listed,
        settlement_ratio=price.settlement_ratio,
        input_price_per_million=unit_prices.input_per_million,
        output_price_per_million=unit_prices.output_per_million,
        image_output_price_per_image=unit_prices.image_output_per_image,
        audio_input_price_per_second=unit_prices.audio_input_per_second,
        audio_output_price_per_second=unit_prices.audio_output_per_second,
        video_input_price_per_second=unit_prices.video_input_per_second,
        video_output_price_per_second=unit_prices.video_output_per_second,
        video_resolution_prices=price.model.video_resolution_prices or {},
        currency=currency,
        price_fingerprint=fingerprint,
        effective_from=now,
        is_current=True,
    )


def sync_channel_price_items(
    price: ChannelModelPrice,
) -> list[ChannelPriceItem]:
    """Sync normalized channel price items from one channel/model config."""
    source = price.price_source
    payloads = channel_price_item_payloads(price, source=source)
    now = timezone.now()
    ChannelPriceItem.objects.filter(
        channel=price.channel,
        model=price.model,
        is_current=True,
    ).update(is_current=False, effective_to=now)

    items = []
    for payload in payloads:
        fingerprint = stable_fingerprint(
            {
                "channel_id": price.channel_id,
                "model_id": price.model_id,
                "dimension": payload["dimension"],
                "billing_unit": payload["billing_unit"],
                "currency": payload["currency"],
                "source_id": payload["source"].id if payload["source"] else "",
                "unit_price": decimal_to_string(payload["unit_price"]),
                "tier_type": payload["tier_type"],
                "tier_start": decimal_to_string(payload["tier_start"]),
                "tier_end": decimal_to_string(payload["tier_end"]),
                "spec": payload["spec"],
                "source_type": payload["price_source_type"],
            }
        )
        payload["price_fingerprint"] = fingerprint
        item, _ = ChannelPriceItem.objects.update_or_create(
            channel=price.channel,
            model=price.model,
            dimension=payload["dimension"],
            billing_unit=payload["billing_unit"],
            currency=payload["currency"],
            price_fingerprint=fingerprint,
            defaults=payload,
        )
        if not item.is_current or item.effective_to is not None:
            item.is_current = True
            item.effective_to = None
            item.save(update_fields=["is_current", "effective_to"])
        items.append(item)
    return items


def channel_price_item_payloads(
    price: ChannelModelPrice,
    *,
    source: PriceCollectionSource | None,
) -> list[dict]:
    """Build normalized channel price item payloads for a model config."""
    channel = price.channel
    model = price.model
    currency = resolve_channel_model_currency(channel, model, override=price)
    ratio = decimal_or_zero(channel.settlement_ratio) or ONE
    if price.settlement_ratio is not None:
        ratio = decimal_or_zero(price.settlement_ratio)

    base_items = current_model_price_items_for_channel_price(price)
    if base_items:
        return [
            channel_price_payload_from_base_item(
                price,
                base_item,
                currency=currency,
                ratio=ratio,
                source=source,
            )
            for base_item in base_items
        ]
    return legacy_channel_price_item_payloads(
        price,
        currency=currency,
        source=source,
    )


def current_model_price_items_for_channel_price(
    price: ChannelModelPrice,
) -> list[ModelPriceItem]:
    """Return current price items for the selected procurement source."""
    queryset = ModelPriceItem.objects.filter(
        model=price.model,
        is_current=True,
    )
    if price.price_source_id:
        queryset = queryset.filter(source_id=price.price_source_id)
    rows = list(queryset.order_by("dimension", "tier_start", "id"))
    if rows:
        return rows
    return fallback_price_items_for_meta_model(price.model)


def fallback_price_items_for_meta_model(
    model: LLMModel,
) -> list[ModelPriceItem]:
    """Return the best current flat price item group for a meta model."""
    if not model.meta_model_id:
        return []

    rows = list(
        ModelPriceItem.objects.filter(
            meta_model_id=model.meta_model_id,
            is_current=True,
            unit_price__gt=ZERO,
        )
        .select_related("source")
        .order_by("dimension", "tier_start", "id")
    )
    if not rows:
        return []

    groups: dict[str, list[ModelPriceItem]] = {}
    for item in rows:
        key = str(item.source_id or item.model_id)
        groups.setdefault(key, []).append(item)

    return sorted(
        groups.values(),
        key=price_item_group_score,
        reverse=True,
    )[0]


def price_item_group_score(rows: list[ModelPriceItem]) -> tuple:
    """Score fallback price groups like the frontend channel preview."""
    if not rows:
        return (0, 0, 0)
    first = rows[0]
    category = ""
    if first.source_id:
        category = first.source.source_category
    category_score = {
        PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER: 300,
        PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER: 200,
    }.get(category, 0)
    latest = max((item.effective_from for item in rows), default=None)
    latest_score = latest.timestamp() if latest else 0
    return (category_score, len(rows), latest_score)


def channel_price_payload_from_base_item(
    price: ChannelModelPrice,
    base_item: ModelPriceItem,
    *,
    currency: str,
    ratio: Decimal,
    source,
) -> dict:
    """Build a channel item from a normalized official price item."""
    base_unit_price = convert_currency_between(
        base_item.unit_price,
        base_item.currency,
        currency,
    )
    if base_unit_price is None:
        base_unit_price = decimal_or_zero(base_item.unit_price)
        currency = normalize_currency(base_item.currency) or currency
    unit_price = base_unit_price * ratio
    source_type = ChannelPriceItem.SOURCE_DERIVED_DISCOUNT
    custom_price = custom_price_for_dimension(price, base_item.dimension)
    is_flat_price = base_item.tier_type == ModelPriceItem.TIER_FLAT
    if custom_price is not None and is_flat_price:
        unit_price = custom_price
        source_type = ChannelPriceItem.SOURCE_MANUAL

    comparison = channel_item_comparison(
        unit_price,
        currency,
        base_item,
    )
    return {
        "channel": price.channel,
        "model": price.model,
        "meta_model": price.meta_model,
        "base_price_item": base_item,
        "source": source,
        "dimension": base_item.dimension,
        "billing_unit": base_item.billing_unit,
        "currency": currency,
        "unit_price": unit_price,
        "tier_type": base_item.tier_type,
        "tier_start": base_item.tier_start,
        "tier_end": base_item.tier_end,
        "spec": base_item.spec or {},
        "price_source_type": source_type,
        "settlement_ratio": price.settlement_ratio,
        "comparison_status": comparison["status"],
        "delta_amount": comparison["delta_amount"],
        "delta_percent": comparison["delta_percent"],
        "raw_payload": {
            "source": "channel_model_price",
            "channel_model_price_id": price.id,
            "base_price_item_id": base_item.id,
        },
        "is_current": True,
    }


def legacy_channel_price_item_payloads(
    price: ChannelModelPrice,
    *,
    currency: str,
    source,
) -> list[dict]:
    """Build channel items from legacy flat model price fields."""
    unit_prices = resolve_channel_model_price(
        price.channel,
        price.model,
        override=price,
    )
    item_specs = [
        (
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            unit_prices.input_per_million,
        ),
        (
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            unit_prices.output_per_million,
        ),
        (
            ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
            ModelPriceItem.UNIT_PER_IMAGE,
            unit_prices.image_output_per_image,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            unit_prices.audio_input_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            unit_prices.audio_output_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            unit_prices.video_input_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            unit_prices.video_output_per_second,
        ),
    ]
    payloads = []
    for dimension, billing_unit, unit_price in item_specs:
        if unit_price == ZERO:
            continue
        source_currency = price.model.currency
        if custom_price_for_dimension(price, dimension) is not None:
            source_currency = currency
        unit_price = convert_currency_between(
            unit_price,
            source_currency,
            currency,
        ) or unit_price
        base_item = matching_base_price_item(
            price.model,
            dimension,
            billing_unit,
            {},
        )
        comparison = channel_item_comparison(unit_price, currency, base_item)
        payloads.append(
            {
                "channel": price.channel,
                "model": price.model,
                "meta_model": price.meta_model,
                "base_price_item": base_item,
                "source": source,
                "dimension": dimension,
                "billing_unit": billing_unit,
                "currency": currency,
                "unit_price": unit_price,
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": None,
                "tier_end": None,
                "spec": {},
                "price_source_type": legacy_source_type(price, dimension),
                "settlement_ratio": price.settlement_ratio,
                "comparison_status": comparison["status"],
                "delta_amount": comparison["delta_amount"],
                "delta_percent": comparison["delta_percent"],
                "raw_payload": {
                    "source": "channel_model_price",
                    "channel_model_price_id": price.id,
                },
                "is_current": True,
            }
        )
    return payloads


def custom_price_for_dimension(
    price: ChannelModelPrice,
    dimension: str,
) -> Decimal | None:
    """Return a manual channel override for one normalized dimension."""
    field_map = {
        ModelPriceItem.DIMENSION_TEXT_INPUT: (
            "custom_input_price_per_million"
        ),
        ModelPriceItem.DIMENSION_TEXT_OUTPUT: (
            "custom_output_price_per_million"
        ),
        ModelPriceItem.DIMENSION_AUDIO_INPUT: (
            "custom_audio_input_price_per_second"
        ),
        ModelPriceItem.DIMENSION_AUDIO_OUTPUT: (
            "custom_audio_output_price_per_second"
        ),
        ModelPriceItem.DIMENSION_VIDEO_INPUT: (
            "custom_video_input_price_per_second"
        ),
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT: (
            "custom_video_output_price_per_second"
        ),
    }
    field_name = field_map.get(dimension)
    if not field_name:
        return None
    value = getattr(price, field_name, None)
    if value is None:
        return None
    return decimal_or_zero(value)


def legacy_source_type(price: ChannelModelPrice, dimension: str) -> str:
    """Return source type for a legacy channel item."""
    if custom_price_for_dimension(price, dimension) is not None:
        return ChannelPriceItem.SOURCE_MANUAL
    return ChannelPriceItem.SOURCE_DERIVED_DISCOUNT


def matching_base_price_item(
    model: LLMModel,
    dimension: str,
    billing_unit: str,
    spec: dict,
) -> ModelPriceItem | None:
    """Find the current official item matching one channel price item."""
    return ModelPriceItem.objects.filter(
        model=model,
        dimension=dimension,
        billing_unit=billing_unit,
        spec=spec or {},
        is_current=True,
    ).order_by("tier_start", "id").first()


def channel_item_comparison(
    unit_price: Decimal,
    currency: str,
    base_item: ModelPriceItem | None,
) -> dict:
    """Compare a channel price item against the matching official item."""
    if not base_item or normalize_currency(base_item.currency) != currency:
        return {
            "status": ChannelPriceItem.COMPARISON_UNKNOWN,
            "delta_amount": None,
            "delta_percent": None,
        }

    official_price = decimal_or_zero(base_item.unit_price)
    delta = unit_price - official_price
    if official_price == ZERO:
        delta_percent = None
    else:
        delta_percent = (delta / official_price * Decimal("100")).quantize(
            Decimal("0.0001")
        )
    if delta < ZERO:
        status = ChannelPriceItem.COMPARISON_BELOW
    elif delta > ZERO:
        status = ChannelPriceItem.COMPARISON_ABOVE
    else:
        status = ChannelPriceItem.COMPARISON_SAME
    return {
        "status": status,
        "delta_amount": delta,
        "delta_percent": delta_percent,
    }


def record_resale_listing_price_history(
    listing: ResaleListing,
) -> ResaleListingPriceHistory | None:
    """Record a resale listing price version when price fields change."""
    currency = resolve_resale_listing_currency(listing)
    payload = {
        "channel_id": listing.channel_id,
        "display_name": listing.display_name,
        "retail_input_price_per_million": decimal_to_string(
            listing.retail_input_price_per_million
        ),
        "retail_output_price_per_million": decimal_to_string(
            listing.retail_output_price_per_million
        ),
        "retail_cache_input_price_per_million": decimal_to_string(
            listing.retail_cache_input_price_per_million
        ),
        "retail_image_output_price_per_image": decimal_to_string(
            listing.retail_image_output_price_per_image
        ),
        "retail_audio_input_price_per_second": decimal_to_string(
            listing.retail_audio_input_price_per_second
        ),
        "retail_audio_output_price_per_second": decimal_to_string(
            listing.retail_audio_output_price_per_second
        ),
        "retail_video_input_price_per_second": decimal_to_string(
            listing.retail_video_input_price_per_second
        ),
        "retail_video_output_price_per_second": decimal_to_string(
            listing.retail_video_output_price_per_second
        ),
        "currency": currency,
        "is_active": listing.is_active,
    }
    fingerprint = stable_fingerprint(payload)
    query = ResaleListingPriceHistory.objects.filter(
        platform=listing.platform,
        model=listing.model,
        price_fingerprint=fingerprint,
    )
    if listing.channel_id is None:
        query = query.filter(channel__isnull=True)
    else:
        query = query.filter(channel=listing.channel)
    if query.exists():
        return None

    now = timezone.now()
    current_query = ResaleListingPriceHistory.objects.filter(
        platform=listing.platform,
        model=listing.model,
        is_current=True,
    )
    if listing.channel_id is None:
        current_query = current_query.filter(channel__isnull=True)
    else:
        current_query = current_query.filter(channel=listing.channel)
    current_query.update(
        is_current=False,
        effective_to=now,
    )
    return ResaleListingPriceHistory.objects.create(
        platform=listing.platform,
        model=listing.model,
        meta_model=listing.meta_model,
        channel=listing.channel,
        display_name=listing.display_name,
        retail_input_price_per_million=(
            listing.retail_input_price_per_million
        ),
        retail_output_price_per_million=(
            listing.retail_output_price_per_million
        ),
        retail_cache_input_price_per_million=(
            listing.retail_cache_input_price_per_million
        ),
        retail_image_output_price_per_image=(
            listing.retail_image_output_price_per_image
        ),
        retail_audio_input_price_per_second=(
            listing.retail_audio_input_price_per_second
        ),
        retail_audio_output_price_per_second=(
            listing.retail_audio_output_price_per_second
        ),
        retail_video_input_price_per_second=(
            listing.retail_video_input_price_per_second
        ),
        retail_video_output_price_per_second=(
            listing.retail_video_output_price_per_second
        ),
        currency=currency,
        is_active=listing.is_active,
        price_fingerprint=fingerprint,
        effective_from=now,
        is_current=True,
    )


def stable_fingerprint(payload: dict) -> str:
    """Return a stable fingerprint for price history payloads."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def json_safe_payload(value):
    """Return a JSONField-safe copy of a nested payload."""
    if isinstance(value, Decimal):
        return decimal_to_string(value)
    if isinstance(value, dict):
        return {
            key: json_safe_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [json_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe_payload(item) for item in value]
    return value


def json_default(value):
    """Serialize non-standard values for stable JSON dumps."""
    if isinstance(value, Decimal):
        return decimal_to_string(value)
    raise TypeError(
        f"Object of type {value.__class__.__name__} "
        "is not JSON serializable"
    )


def decimal_to_string(value) -> str:
    """Serialize decimals for stable price fingerprints."""
    if value is None:
        return ""
    return str(Decimal(str(value)))
