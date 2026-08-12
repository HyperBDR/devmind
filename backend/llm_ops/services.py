from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import re

from cloud_billing.dashboard import _build_exchange_rate_info
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .meta_model_lookup import (
    find_meta_model_by_alias_or_name,
    invalidate_meta_model_lookup_cache as _invalidate_lookup_cache,
    normalize_meta_model_lookup_name as _normalize_lookup_name,
)
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
    ResaleListingPriceItem,
    ResaleListingPriceRevision,
    ResalePlatform,
    ResaleWorkflowConfig,
)
from .price_table_validation import (
    validate_price_table_groups,
    with_usage_range_spec,
)
from .tier_pricing import (
    PriceSchedule,
    PriceTier,
    RevenuePolicy,
    TieredPriceNotSupportedError,
    UnitPrices,
    UsageContext,
    analyze_tier_profit,
    calculate_price_schedule_usage_cost,
    resolve_price_tier,
    resolve_usage_unit_prices,
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

MANUAL_COLLECTION_METHODS = {
    PriceCollectionSource.COLLECTION_METHOD_MANUAL_ENTRY,
    PriceCollectionSource.COLLECTION_METHOD_MANUAL_IMPORT,
}


def invalidate_meta_model_lookup_cache() -> None:
    """Clear cached meta model lookup indexes for compatibility callers."""
    _invalidate_lookup_cache()


def normalize_meta_model_lookup_name(value: str | None) -> str:
    """Normalize a model display name for loose matching."""
    return _normalize_lookup_name(value)


@dataclass(frozen=True)
class CurrencyConversionContext:
    """Exchange-rate context for panel-level display conversion."""

    display_currency: str
    usd_to_cny_rate: Decimal
    rate_source_label: str
    rate_source_url: str
    rate_collected_at: str


class TieredPriceScheduleRequired(ValueError):
    """Raised when a legacy flat-price API receives tiered prices."""

    code = "price_schedule.tiered_requires_usage_context"

    def __init__(self):
        super().__init__(self.code)


class ResalePriceRevisionError(ValueError):
    """Stable policy or state error for resale price revision APIs."""

    def __init__(self, code: str, detail: str, *, conflict: bool = False):
        self.code = code
        self.detail = detail
        self.conflict = conflict
        super().__init__(code)


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

    return find_meta_model_by_alias_or_name(
        tokens=tokens,
        name=canonical_name,
    )


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


def price_role_for_source(
    source: PriceCollectionSource | None,
    *,
    meta_model: MetaModel | None = None,
) -> str:
    """Map a price source to the business role of one model row."""
    if source is None:
        return LLMModel.PRICE_ROLE_UNKNOWN
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
    """Return the display/business role from source owner metadata."""
    owner_type = source_owner_type_for_source(source)
    if owner_type == PriceCollectionSource.SOURCE_OWNER_SUPPLIER:
        return PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
    if owner_type == PriceCollectionSource.SOURCE_OWNER_INTERNAL:
        return PriceCollectionSource.SOURCE_CATEGORY_MANUAL
    if (
        owner_type
        == PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
    ):
        return LLMModel.PRICE_ROLE_CLOUD_HOSTED
    if (
        owner_type
        != PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL
    ):
        return PriceCollectionSource.SOURCE_CATEGORY_UNKNOWN

    source_owner_code = str(getattr(source.provider, "code", "") or "")
    model_owner_code = canonical_owner_code_for_meta_model(meta_model)
    if not source_owner_code or not model_owner_code:
        return PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    if source_owner_code == model_owner_code:
        return PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    return LLMModel.PRICE_ROLE_CLOUD_HOSTED


def source_owner_type_for_source(source: PriceCollectionSource) -> str:
    """Return source owner metadata, with legacy category fallback."""
    owner_type = getattr(source, "source_owner_type", "")
    if owner_type and owner_type != PriceCollectionSource.SOURCE_OWNER_UNKNOWN:
        return owner_type

    if (
        source.source_category
        == PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
    ):
        return PriceCollectionSource.SOURCE_OWNER_SUPPLIER
    if source.source_category == PriceCollectionSource.SOURCE_CATEGORY_MANUAL:
        return PriceCollectionSource.SOURCE_OWNER_INTERNAL
    if (
        source.source_category
        != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return PriceCollectionSource.SOURCE_OWNER_UNKNOWN

    provider_code = str(getattr(source.provider, "code", "") or "").lower()
    if provider_code in PriceCollectionSource.CLOUD_PROVIDER_OFFICIAL_CODES:
        return PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
    return PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL


def is_manual_price_source(source: PriceCollectionSource) -> bool:
    """Return whether a source is maintained through manual workflows."""
    method = getattr(source, "collection_method", "")
    if method in MANUAL_COLLECTION_METHODS:
        return True
    return (
        source_owner_type_for_source(source)
        == PriceCollectionSource.SOURCE_OWNER_INTERNAL
    )


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
        role = (
            price_role_for_source(
                model.source,
                meta_model=model.meta_model,
            )
            if model.source_id and model.source is not None
            else ""
        )
        is_current_source = (
            bool(current_source_id)
            and model.source_id == current_source_id
        )
        if role == LLMModel.PRICE_ROLE_OFFICIAL:
            category_rank = 0
        elif role == "":
            category_rank = 1
        elif role == LLMModel.PRICE_ROLE_MANUAL:
            category_rank = 2 if is_current_source else 3
        elif role in (
            LLMModel.PRICE_ROLE_SUPPLIER,
            LLMModel.PRICE_ROLE_CLOUD_HOSTED,
        ):
            category_rank = 4 if is_current_source else 5
        elif role == LLMModel.PRICE_ROLE_UNKNOWN:
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

    exchange_info = _build_exchange_rate_info(allow_remote=False)
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
    if is_manual_price_source(source):
        effective_updates_model_prices = False
    run = source.collection_runs.create(status="running")
    created_count = 0
    updated_count = 0
    price_item_count = 0
    skipped_count = 0
    affected_model_ids = set()
    affected_meta_model_ids = set()
    affected_price_item_ids = set()
    deactivated_price_item_ids = set()

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

        affected_model_ids.add(model.id)
        if model.meta_model_id:
            affected_meta_model_ids.add(model.meta_model_id)

        price_result = sync_manual_model_price_items(
            source=source,
            provider=row_provider,
            model=model,
            row=row,
            row_index=index,
            default_currency=default_currency,
        )
        price_items = price_result["current_items"]
        price_item_count += len(price_items)
        affected_price_item_ids.update(item.id for item in price_items)
        deactivated_price_item_ids.update(
            price_result["deactivated_item_ids"],
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
    changed_price_item_ids = (
        affected_price_item_ids | deactivated_price_item_ids
    )
    changed_price_items = list(
        ModelPriceItem.objects.filter(id__in=changed_price_item_ids)
    )
    channel_sync = sync_dependent_channel_price_items_for_price_items(
        changed_price_items,
    )
    current_price_item_ids = set(
        ModelPriceItem.objects.filter(
            id__in=changed_price_item_ids,
            is_current=True,
        ).values_list("id", flat=True)
    )
    return {
        "run_id": run.id,
        "source_id": source.id,
        "collected_count": run.collected_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "price_item_count": price_item_count,
        "affected_collection_run_ids": [run.id],
        "affected_meta_model_ids": sorted(affected_meta_model_ids),
        "affected_model_ids": sorted(affected_model_ids),
        "affected_price_item_ids": sorted(
            affected_price_item_ids & current_price_item_ids,
        ),
        "deactivated_price_item_ids": sorted(
            deactivated_price_item_ids - current_price_item_ids,
        ),
        "channel_price_sync": channel_sync,
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
        if (
            model.source_id == source.id
            and can_detach_model_from_source(model)
        ):
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
) -> dict:
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
        return {"current_items": [], "deactivated_item_ids": []}

    current_queryset = ModelPriceItem.objects.filter(
        model=model,
        source=source,
        is_current=True,
    )

    current_items = []
    with transaction.atomic():
        old_current_ids = set(current_queryset.values_list("id", flat=True))
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
            needs_reactivate = (
                not price_item.is_current
                or price_item.effective_to is not None
            )
            if needs_reactivate:
                price_item.is_current = True
                price_item.effective_to = None
                price_item.save(update_fields=["is_current", "effective_to"])
            current_items.append(price_item)

        current_item_ids = {item.id for item in current_items}
        stale_item_ids = old_current_ids - current_item_ids
        if stale_item_ids:
            ModelPriceItem.objects.filter(id__in=stale_item_ids).update(
                is_current=False,
                effective_to=now,
            )

    return {
        "current_items": current_items,
        "deactivated_item_ids": sorted(old_current_ids - current_item_ids),
    }


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


def resolve_channel_price_schedule(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None = None,
    source_items: list[ModelPriceItem] | None = None,
    video_resolution: str = "",
) -> PriceSchedule:
    """Resolve every channel price interval without flattening tiers."""
    if override is None:
        override = ChannelModelPrice.objects.filter(
            channel=channel,
            model=model,
        ).first()

    if source_items is None and override is not None:
        source_items = current_model_price_items_for_channel_price(override)
    source_items = list(source_items or [])
    if source_items:
        return _schedule_from_source_items(
            channel,
            model,
            override=override,
            source_items=source_items,
            video_resolution=video_resolution,
        )
    if override is not None and override.price_source_id:
        return _schedule_from_source_items(
            channel,
            model,
            override=override,
            source_items=[],
            video_resolution=video_resolution,
        )

    unit_prices = resolve_channel_model_price(
        channel,
        model,
        override=override,
        source_items=[],
        video_resolution=video_resolution,
    )
    currency = resolve_channel_model_currency(
        channel,
        model,
        override=override,
    )
    return _flat_schedule_from_unit_prices(unit_prices, currency=currency)


def _merge_flat_fallback_tiers(tiers: list[PriceTier]) -> list[PriceTier]:
    """Merge flat fallback tiers into tiered tables as an unbounded tail.

    Some models store both explicit usage-range tiers (e.g. 0-128000) and a
    flat fallback price for usage beyond that window. The price table
    contract forbids mixing flat and tiered rows, so we convert flat
    fallbacks into an unbounded tier ``[max_end, None)``.
    """
    by_dim: dict[str, list[PriceTier]] = {}
    for tier in tiers:
        by_dim.setdefault(tier.dimension, []).append(tier)

    merged: list[PriceTier] = []
    for dim_tiers in by_dim.values():
        tiered = [t for t in dim_tiers if t.tier_type != "flat"]
        flat = [t for t in dim_tiers if t.tier_type == "flat"]
        if not tiered or not flat:
            merged.extend(dim_tiers)
            continue

        max_end = max(
            (t.tier_end for t in tiered if t.tier_end is not None),
            default=None,
        )
        for t in tiered:
            merged.append(t)
        for t in flat:
            if max_end is not None:
                merged.append(
                    PriceTier(
                        dimension=t.dimension,
                        billing_unit=t.billing_unit,
                        currency=t.currency,
                        unit_price=t.unit_price,
                        tier_type=ModelPriceItem.TIER_USAGE_RANGE,
                        tier_start=max_end,
                        tier_end=None,
                        spec=with_usage_range_spec(t.spec),
                    )
                )
            else:
                merged.append(t)
    return merged


def _schedule_from_source_items(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None,
    source_items: list[ModelPriceItem],
    video_resolution: str,
) -> PriceSchedule:
    """Convert normalized source items into channel settlement prices."""
    currency = resolve_channel_model_currency(
        channel,
        model,
        override=override,
    )
    ratio = decimal_or_zero(channel.settlement_ratio) or ONE
    if override is not None and override.settlement_ratio is not None:
        ratio = decimal_or_zero(override.settlement_ratio)

    tiers = []
    for item in source_items:
        spec = item.spec or {}
        if item.tier_type == ModelPriceItem.TIER_USAGE_RANGE:
            spec = with_usage_range_spec(spec)
        item_currency = currency
        unit_price = convert_currency_between(
            item.unit_price,
            item.currency,
            currency,
        )
        if unit_price is None:
            unit_price = decimal_or_zero(item.unit_price)
            item_currency = normalize_currency(item.currency) or currency
        unit_price *= ratio
        custom_price = None
        if override is not None:
            custom_price = custom_price_for_dimension(
                override,
                item.dimension,
            )
        if custom_price is not None and item.tier_type == item.TIER_FLAT:
            unit_price = custom_price
        resolution_price = _video_resolution_price(
            model,
            override=override,
            dimension=item.dimension,
            video_resolution=video_resolution,
            ratio=ratio,
        )
        if resolution_price is not None and item.tier_type == item.TIER_FLAT:
            unit_price = resolution_price
        tiers.append(
            PriceTier(
                dimension=item.dimension,
                billing_unit=item.billing_unit,
                currency=item_currency,
                unit_price=unit_price,
                tier_type=item.tier_type,
                tier_start=item.tier_start,
                tier_end=item.tier_end,
                spec=dict(spec),
            )
        )
    existing_dimensions = {tier.dimension for tier in tiers}
    custom_dimensions = (
        (
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
        ),
        (
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
        ),
    )
    for dimension, billing_unit in custom_dimensions:
        if override is None or dimension in existing_dimensions:
            continue
        custom_price = custom_price_for_dimension(override, dimension)
        resolution_price = _video_resolution_price(
            model,
            override=override,
            dimension=dimension,
            video_resolution=video_resolution,
            ratio=ratio,
        )
        if custom_price is None and resolution_price is None:
            continue
        tiers.append(
            PriceTier(
                dimension=dimension,
                billing_unit=billing_unit,
                currency=currency,
                unit_price=(
                    resolution_price
                    if resolution_price is not None
                    else custom_price
                ),
                tier_type=ModelPriceItem.TIER_FLAT,
                tier_start=None,
                tier_end=None,
                spec={},
            )
        )
    merged_tiers = _merge_flat_fallback_tiers(tiers)
    schedule = PriceSchedule(tiers=tuple(merged_tiers))
    validate_price_table_groups(schedule.tiers)
    return schedule


def _video_resolution_price(
    model: LLMModel,
    *,
    override: ChannelModelPrice | None,
    dimension: str,
    video_resolution: str,
    ratio: Decimal,
) -> Decimal | None:
    """Resolve the legacy video-resolution override precedence."""
    dimension_key = {
        ModelPriceItem.DIMENSION_VIDEO_INPUT: "input",
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT: "output",
    }.get(dimension)
    if not video_resolution or dimension_key is None:
        return None

    unit_price = None
    resolution_prices = model.video_resolution_prices or {}
    model_price = resolution_prices.get(video_resolution) or {}
    if model_price.get(dimension_key) is not None:
        unit_price = decimal_or_zero(model_price[dimension_key]) * ratio

    if override is None:
        return unit_price
    custom_price = custom_price_for_dimension(override, dimension)
    if custom_price is not None:
        unit_price = custom_price
    custom_resolution_prices = override.custom_video_resolution_prices or {}
    custom_resolution_price = (
        custom_resolution_prices.get(video_resolution) or {}
    )
    if custom_resolution_price.get(dimension_key) is not None:
        unit_price = decimal_or_zero(
            custom_resolution_price[dimension_key]
        )
    return unit_price


def _flat_schedule_from_unit_prices(
    unit_prices: UnitPrices,
    *,
    currency: str,
) -> PriceSchedule:
    """Expose legacy scalar prices through the normalized schedule API."""
    values = (
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
            ModelPriceItem.DIMENSION_CACHE_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            unit_prices.cache_input_per_million,
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
    )
    return PriceSchedule(
        tiers=tuple(
            PriceTier(
                dimension=dimension,
                billing_unit=billing_unit,
                currency=currency,
                unit_price=unit_price,
                tier_type=ModelPriceItem.TIER_FLAT,
                tier_start=None,
                tier_end=None,
                spec={},
            )
            for dimension, billing_unit, unit_price in values
        )
    )


def resolve_channel_model_price(
    channel: ProcurementChannel,
    model: LLMModel,
    *,
    override: ChannelModelPrice | None = None,
    source_items: list[ModelPriceItem] | None = None,
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
        source_items=source_items,
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
    elif override and override.price_source_id:
        input_price = ZERO
        output_price = ZERO
        cache_input_price = ZERO
        image_output_price = ZERO
        audio_input_price = ZERO
        audio_output_price = ZERO
        video_input_price = ZERO
        video_output_price = ZERO

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
    source_items: list[ModelPriceItem] | None = None,
) -> UnitPrices | None:
    """Resolve unit prices from the selected procurement source."""
    if not override:
        return None

    target_currency = resolve_channel_model_currency(
        channel,
        model,
        override=override,
    )
    values = {}
    grouped_items = {}
    if source_items is None:
        source_items = current_model_price_items_for_channel_price(override)
    for item in source_items:
        grouped_items.setdefault(item.dimension, []).append(item)

    for dimension, items in grouped_items.items():
        item = selected_price_item_for_channel_model(items)
        if item is None:
            continue
        unit_price = convert_currency_between(
            item.unit_price,
            item.currency,
            target_currency,
        )
        values[dimension] = unit_price or decimal_or_zero(item.unit_price)

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


def selected_price_item_for_channel_model(
    items: list[ModelPriceItem],
) -> ModelPriceItem | None:
    """Select one flat item for the legacy scalar price interface."""
    if not items:
        return None

    tiered_items = [
        item
        for item in items
        if item.tier_type
        in (ModelPriceItem.TIER_USAGE_RANGE, ModelPriceItem.TIER_VOLUME)
    ]
    if tiered_items:
        raise TieredPriceNotSupportedError(
            "Tiered prices require resolve_channel_price_schedule()."
        )

    flat_items = [
        item for item in items if item.tier_type == ModelPriceItem.TIER_FLAT
    ]
    if flat_items:
        return sorted(flat_items, key=lambda item: item.id)[0]
    return None


def calculate_usage_cost(
    unit_prices: UnitPrices,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_input_tokens: int = 0,
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
    cache_input_cost = Decimal(cache_input_tokens or 0) / Decimal(1000000)
    cache_input_cost *= unit_prices.cache_input_per_million

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
        + cache_input_cost
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
    cache_input_tokens: int = 0,
    audio_input_seconds: Decimal | int | str = 0,
    audio_output_seconds: Decimal | int | str = 0,
    video_input_seconds: Decimal | int | str = 0,
    video_output_seconds: Decimal | int | str = 0,
    video_resolution: str = "",
) -> Decimal:
    """Resolve channel prices and calculate expected usage cost."""
    schedule = resolve_channel_price_schedule(
        channel,
        model,
        video_resolution=video_resolution,
    )
    return calculate_price_schedule_usage_cost(
        schedule,
        UsageContext(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_input_tokens=cache_input_tokens,
            audio_input_seconds=audio_input_seconds,
            audio_output_seconds=audio_output_seconds,
            video_input_seconds=video_input_seconds,
            video_output_seconds=video_output_seconds,
        ),
    )


def record_channel_model_price_history(
    price: ChannelModelPrice,
    *,
    video_resolution: str = "",
) -> ChannelModelPriceHistory | None:
    """Record a flat channel price version when price fields change.

    Tiered history remains in normalized channel price items because the
    legacy snapshot cannot represent interval boundaries.
    """
    schedule = resolve_channel_price_schedule(
        price.channel,
        price.model,
        override=price,
        video_resolution=video_resolution,
    )
    if any(
        tier.tier_type != ModelPriceItem.TIER_FLAT
        for tier in schedule.tiers
    ):
        return None
    unit_prices = resolve_usage_unit_prices(schedule, UsageContext())
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


@transaction.atomic
def sync_channel_price_items(
    price: ChannelModelPrice,
) -> list[ChannelPriceItem]:
    """Sync normalized channel price items from one channel/model config."""
    source = price.price_source
    payloads = channel_price_item_payloads(price, source=source)
    validate_price_table_groups(payloads)
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


def sync_dependent_channel_price_items_for_price_items(
    price_items,
) -> dict[str, int]:
    """Resync channel prices that derive from changed upstream prices."""
    references = [
        price_item_dependency_reference(item) for item in price_items if item
    ]
    model_ids = {
        reference["model_id"]
        for reference in references
        if reference["model_id"]
    }
    meta_model_ids = {
        reference["meta_model_id"]
        for reference in references
        if reference["meta_model_id"]
    }
    source_ids = {
        reference["source_id"]
        for reference in references
        if reference["source_id"]
    }
    if not model_ids and not meta_model_ids:
        return {"channel_model_prices": 0, "channel_price_items": 0}

    model_query = Q()
    if model_ids:
        model_query |= Q(model_id__in=model_ids)
    if meta_model_ids:
        model_query |= Q(meta_model_id__in=meta_model_ids)

    source_query = Q(price_source__isnull=True)
    if source_ids:
        source_query |= Q(price_source_id__in=source_ids)

    prices = list(
        ChannelModelPrice.objects.filter(model_query)
        .filter(source_query)
        .select_related(
            "channel",
            "model",
            "model__meta_model",
            "price_source",
        )
        .order_by("id")
    )
    item_count = 0
    for price in prices:
        record_channel_model_price_history(price)
        item_count += len(sync_channel_price_items(price))
    return {
        "channel_model_prices": len(prices),
        "channel_price_items": item_count,
    }


def price_item_dependency_reference(item) -> dict[str, int | None]:
    """Return stable channel dependency fields for a price item."""
    if isinstance(item, dict):
        return {
            "model_id": item.get("model_id"),
            "meta_model_id": item.get("meta_model_id"),
            "source_id": item.get("source_id"),
        }
    return {
        "model_id": getattr(item, "model_id", None),
        "meta_model_id": getattr(item, "meta_model_id", None),
        "source_id": getattr(item, "source_id", None),
    }


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
    if price.price_source_id:
        return []
    return legacy_channel_price_item_payloads(
        price,
        currency=currency,
        source=source,
    )


def current_model_price_items_for_channel_price(
    price: ChannelModelPrice,
) -> list[ModelPriceItem]:
    """Return current price items for the selected procurement source."""
    if price.price_source_id:
        rows = current_price_items_for_model(
            price.model,
            source_id=price.price_source_id,
        )
        if rows:
            return selected_price_item_group(rows, model=price.model)
        return fallback_price_items_for_meta_model(
            price.model,
            source_id=price.price_source_id,
        )

    rows = current_price_items_for_model(
        price.model,
    )
    if rows:
        return selected_price_item_group(rows, model=price.model)
    return fallback_price_items_for_meta_model(price.model)


def current_price_items_for_model(
    model: LLMModel,
    *,
    source_id: int | None = None,
) -> list[ModelPriceItem]:
    """Return current price items directly linked to a legacy model."""
    queryset = ModelPriceItem.objects.filter(
        model=model,
        is_current=True,
    )
    if source_id:
        queryset = queryset.filter(source_id=source_id)
    return list(queryset.order_by("dimension", "tier_start", "id"))


def fallback_price_items_for_meta_model(
    model: LLMModel,
    *,
    source_id: int | None = None,
) -> list[ModelPriceItem]:
    """Return the best current flat price item group for a meta model."""
    if not model.meta_model_id:
        return []

    queryset = ModelPriceItem.objects.filter(
        meta_model_id=model.meta_model_id,
        is_current=True,
        unit_price__gt=ZERO,
    )
    if source_id:
        queryset = queryset.filter(source_id=source_id)
    rows = list(
        queryset.select_related("offering", "sku", "source").order_by(
            "dimension",
            "tier_start",
            "id",
        )
    )
    if not rows:
        return []

    return selected_price_item_group(rows, model=model)


def selected_price_item_group(
    rows: list[ModelPriceItem],
    *,
    model: LLMModel | None = None,
) -> list[ModelPriceItem]:
    """Return the best coherent price item group from candidate rows."""
    groups: dict[str, list[ModelPriceItem]] = {}
    for item in rows:
        key = price_item_group_key(item)
        groups.setdefault(key, []).append(item)

    return sorted(
        groups.values(),
        key=lambda group: price_item_group_score(group, model=model),
        reverse=True,
    )[0]


def price_item_group_key(item: ModelPriceItem) -> str:
    """Return the identity used to compare coherent price item groups."""
    spec_key = json.dumps(item.spec or {}, sort_keys=True)
    if item.offering_id:
        return f"offering:{item.offering_id}:{spec_key}"
    if item.sku_id:
        return f"sku:{item.source_id or ''}:{item.sku_id}:{spec_key}"
    if item.model_id:
        return f"model:{item.source_id or ''}:{item.model_id}:{spec_key}"
    return f"source:{item.source_id or ''}:{spec_key}"


def price_item_group_score(
    rows: list[ModelPriceItem],
    *,
    model: LLMModel | None = None,
) -> tuple:
    """Score fallback price groups like the frontend channel preview."""
    if not rows:
        return (0, 0, 0, 0)
    first = rows[0]
    role = ""
    if first.source_id:
        meta_model = first.meta_model or getattr(
            first.model,
            "meta_model",
            None,
        )
        role = price_role_for_source(first.source, meta_model=meta_model)
    category_score = {
        LLMModel.PRICE_ROLE_OFFICIAL: 300,
        LLMModel.PRICE_ROLE_CLOUD_HOSTED: 250,
        LLMModel.PRICE_ROLE_SUPPLIER: 200,
    }.get(role, 0)
    alignment_score = price_item_group_alignment_score(rows, model)
    latest = max((item.effective_from for item in rows), default=None)
    latest_score = latest.timestamp() if latest else 0
    return (category_score, len(rows), alignment_score, latest_score)


def price_item_group_alignment_score(
    rows: list[ModelPriceItem],
    model: LLMModel | None,
) -> int:
    """Prefer the group that matches the model's promoted base prices."""
    if model is None:
        return 0

    field_map = {
        ModelPriceItem.DIMENSION_TEXT_INPUT: "input_price_per_million",
        ModelPriceItem.DIMENSION_TEXT_OUTPUT: "output_price_per_million",
        ModelPriceItem.DIMENSION_CACHE_INPUT: "cache_input_price_per_million",
        ModelPriceItem.DIMENSION_IMAGE_OUTPUT: "image_output_price_per_image",
        ModelPriceItem.DIMENSION_AUDIO_INPUT: "audio_input_price_per_second",
        ModelPriceItem.DIMENSION_AUDIO_OUTPUT: "audio_output_price_per_second",
        ModelPriceItem.DIMENSION_VIDEO_INPUT: "video_input_price_per_second",
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT: "video_output_price_per_second",
    }
    score = 0
    for item in rows:
        field_name = field_map.get(item.dimension)
        if not field_name:
            continue
        model_value = getattr(model, field_name, None)
        if model_value is None:
            continue
        converted = convert_currency_between(
            item.unit_price,
            item.currency,
            model.currency,
        )
        if converted is None:
            continue
        if decimal_or_zero(model_value) == decimal_or_zero(converted):
            score += 1
    return score


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
    spec = base_item.spec or {}
    if base_item.tier_type == ModelPriceItem.TIER_USAGE_RANGE:
        spec = with_usage_range_spec(spec)
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
        "spec": spec,
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
    direct_item = ModelPriceItem.objects.filter(
        model=model,
        dimension=dimension,
        billing_unit=billing_unit,
        spec=spec or {},
        is_current=True,
    ).order_by("tier_start", "id").first()
    if direct_item is not None:
        return direct_item
    if not model.meta_model_id:
        return None
    return ModelPriceItem.objects.filter(
        meta_model_id=model.meta_model_id,
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


def _resale_revision_fingerprint(currency: str, items: list[dict]) -> str:
    """Return a stable fingerprint for one normalized resale price table."""
    normalized_items = []
    for item in items:
        normalized_items.append(
            {
                "dimension": item["dimension"],
                "billing_unit": item.get(
                    "billing_unit",
                    ResaleListingPriceItem.UNIT_PER_1M_TOKENS,
                ),
                "tier_type": item.get(
                    "tier_type",
                    ResaleListingPriceItem.TIER_FLAT,
                ),
                "tier_start": decimal_to_string(item.get("tier_start")),
                "tier_end": decimal_to_string(item.get("tier_end")),
                "unit_price": decimal_to_string(item["unit_price"]),
                "spec": item.get("spec") or {},
            }
        )
    normalized_items.sort(
        key=lambda item: (
            item["dimension"],
            item["tier_start"] or "",
            item["tier_end"] or "",
        )
    )
    return stable_fingerprint(
        {
            "currency": normalize_currency(currency),
            "items": normalized_items,
        }
    )


@transaction.atomic
def create_resale_listing_price_revision(
    *,
    listing: ResaleListing,
    currency: str,
    status: str,
    items: list[dict],
    created_by=None,
    effective_from=None,
) -> ResaleListingPriceRevision:
    """Atomically create a complete normalized resale price revision."""
    valid_statuses = {
        choice[0] for choice in ResaleListingPriceRevision.STATUS_CHOICES
    }
    if status not in valid_statuses:
        raise ValueError(
            f"Unsupported resale price revision status: {status}."
        )
    if not items:
        raise ValueError("A resale price revision requires at least one item.")

    normalized_currency = normalize_currency(currency)
    if not normalized_currency:
        raise ValueError("Resale price revision currency is required.")
    allowed_dimensions = {
        ResaleListingPriceItem.DIMENSION_TEXT_INPUT,
        ResaleListingPriceItem.DIMENSION_TEXT_OUTPUT,
        ResaleListingPriceItem.DIMENSION_CACHE_INPUT,
    }
    unsupported_dimensions = {
        item["dimension"]
        for item in items
        if item["dimension"] not in allowed_dimensions
    }
    if unsupported_dimensions:
        dimensions = ", ".join(sorted(unsupported_dimensions))
        raise ValueError(f"Unsupported dimension: {dimensions}.")

    locked_listing = ResaleListing.objects.select_for_update().get(
        pk=listing.pk
    )
    max_version = (
        ResaleListingPriceRevision.objects.filter(
            listing=locked_listing
        ).aggregate(value=Max("version"))["value"]
        or 0
    )
    revision = ResaleListingPriceRevision.objects.create(
        listing=locked_listing,
        version=max_version + 1,
        status=ResaleListingPriceRevision.STATUS_DRAFT,
        currency=normalized_currency,
        price_fingerprint=_resale_revision_fingerprint(
            normalized_currency,
            items,
        ),
        effective_from=effective_from,
        created_by=created_by,
    )
    price_items = [
        ResaleListingPriceItem(
            revision=revision,
            dimension=item["dimension"],
            billing_unit=item.get(
                "billing_unit",
                ResaleListingPriceItem.UNIT_PER_1M_TOKENS,
            ),
            tier_type=item.get(
                "tier_type",
                ResaleListingPriceItem.TIER_FLAT,
            ),
            tier_start=item.get("tier_start"),
            tier_end=item.get("tier_end"),
            unit_price=item["unit_price"],
            spec=item.get("spec") or {},
        )
        for item in items
    ]
    ResaleListingPriceItem.objects.bulk_create(price_items)
    if status != ResaleListingPriceRevision.STATUS_DRAFT:
        ResaleListingPriceRevision.objects.filter(pk=revision.pk).update(
            status=status,
        )
        revision.status = status
    return revision


def derive_resale_pricing_format(schedule: PriceSchedule) -> str:
    """Classify a resale schedule as flat / usage_range / mixed."""
    tier_types = {tier.tier_type for tier in schedule.tiers}
    if not tier_types:
        return ResaleListing.PRICING_FORMAT_FLAT
    if tier_types == {ModelPriceItem.TIER_FLAT}:
        return ResaleListing.PRICING_FORMAT_FLAT
    if ModelPriceItem.TIER_FLAT in tier_types:
        return ResaleListing.PRICING_FORMAT_MIXED
    return ResaleListing.PRICING_FORMAT_USAGE_RANGE


def resolve_resale_listing_unit_prices(
    listing: ResaleListing,
    usage: UsageContext,
) -> UnitPrices:
    """Resolve retail unit prices from the effective resale schedule."""
    schedule = resale_listing_price_schedule(listing)
    return resolve_usage_unit_prices(schedule, usage)


def _flat_resale_listing_price_items(listing: ResaleListing) -> list[dict]:
    """Build normalized flat items from compatibility listing columns."""
    items = [
        {
            "dimension": ResaleListingPriceItem.DIMENSION_TEXT_INPUT,
            "unit_price": listing.retail_input_price_per_million,
        },
        {
            "dimension": ResaleListingPriceItem.DIMENSION_TEXT_OUTPUT,
            "unit_price": listing.retail_output_price_per_million,
        },
    ]
    if listing.retail_cache_input_price_per_million is not None:
        items.append(
            {
                "dimension": ResaleListingPriceItem.DIMENSION_CACHE_INPUT,
                "unit_price": (listing.retail_cache_input_price_per_million),
            }
        )
    return items


@transaction.atomic
def sync_resale_listing_flat_revision(
    listing: ResaleListing,
    *,
    status: str,
    created_by=None,
) -> ResaleListingPriceRevision:
    """Dual-write compatibility flat fields into a complete revision."""
    locked_listing = ResaleListing.objects.select_for_update().get(
        pk=listing.pk
    )
    items = _flat_resale_listing_price_items(locked_listing)
    currency = resolve_resale_listing_currency(locked_listing)
    fingerprint = _resale_revision_fingerprint(currency, items)
    pending = locked_listing.pending_price_revision
    if pending and pending.price_fingerprint == fingerprint:
        if (
            pending.status == ResaleListingPriceRevision.STATUS_DRAFT
            and status == ResaleListingPriceRevision.STATUS_SUBMITTED
        ):
            pending.status = status
            pending.save(update_fields=["status"])
            listing.pending_price_revision_id = pending.id
            return pending
        if pending.status == status:
            listing.pending_price_revision_id = pending.id
            return pending

    revision = create_resale_listing_price_revision(
        listing=locked_listing,
        currency=currency,
        status=status,
        items=items,
        created_by=created_by,
    )
    if pending is not None:
        ResaleListingPriceRevision.objects.filter(pk=pending.pk).update(
            status=ResaleListingPriceRevision.STATUS_SUPERSEDED,
        )
    ResaleListing.objects.filter(pk=locked_listing.pk).update(
        pending_price_revision=revision,
    )
    listing.pending_price_revision_id = revision.id
    return revision


@transaction.atomic
def approve_resale_listing_price_revision(
    listing: ResaleListing,
) -> ResaleListingPriceRevision:
    """Approve the exact pending revision and supersede the old current one."""
    locked_listing = ResaleListing.objects.select_for_update().get(
        pk=listing.pk
    )
    pending = locked_listing.pending_price_revision
    if pending is None or pending.status != pending.STATUS_SUBMITTED:
        raise ValueError("A submitted pending price revision is required.")

    current = locked_listing.current_price_revision
    if current is not None and current.pk != pending.pk:
        ResaleListingPriceRevision.objects.filter(pk=current.pk).update(
            status=ResaleListingPriceRevision.STATUS_SUPERSEDED,
        )
    now = timezone.now()
    ResaleListingPriceRevision.objects.filter(pk=pending.pk).update(
        status=ResaleListingPriceRevision.STATUS_APPROVED,
        effective_from=now,
    )
    ResaleListing.objects.filter(pk=locked_listing.pk).update(
        current_price_revision=pending,
        pending_price_revision=None,
    )
    pending.status = pending.STATUS_APPROVED
    pending.effective_from = now
    listing.current_price_revision_id = pending.id
    listing.pending_price_revision_id = None
    return pending


def _normalize_resale_price_schedule(items) -> PriceSchedule:
    """Normalize resale rows into the canonical tier schedule."""
    allowed_dimensions = {
        choice[0] for choice in ResaleListingPriceItem.DIMENSION_CHOICES
    }
    tiers = []
    for item in items:
        dimension = item["dimension"]
        if dimension not in allowed_dimensions:
            raise ResalePriceRevisionError(
                "resale_price.unsupported_dimension",
                f"Unsupported resale price dimension: {dimension}.",
            )
        tier_type = item.get(
            "tier_type",
            ResaleListingPriceItem.TIER_FLAT,
        )
        spec = dict(item.get("spec") or {})
        if tier_type == ResaleListingPriceItem.TIER_USAGE_RANGE:
            spec = with_usage_range_spec(spec)
        tiers.append(
            PriceTier(
                dimension=dimension,
                billing_unit=item.get(
                    "billing_unit",
                    ResaleListingPriceItem.UNIT_PER_1M_TOKENS,
                ),
                currency=normalize_currency(item.get("currency")),
                unit_price=decimal_or_zero(item.get("unit_price")),
                tier_type=tier_type,
                tier_start=(
                    decimal_or_zero(item["tier_start"])
                    if item.get("tier_start") is not None
                    else None
                ),
                tier_end=(
                    decimal_or_zero(item["tier_end"])
                    if item.get("tier_end") is not None
                    else None
                ),
                spec=spec,
            )
        )
    merged_tiers = _merge_flat_fallback_tiers(tiers)
    schedule = PriceSchedule(tiers=tuple(merged_tiers))
    validate_price_table_groups(schedule.tiers)
    return schedule


def _replace_resale_revision_items(
    revision: ResaleListingPriceRevision,
    schedule: PriceSchedule,
) -> None:
    """Replace all rows belonging to one mutable draft revision."""
    revision.items.all().delete()
    ResaleListingPriceItem.objects.bulk_create(
        [
            ResaleListingPriceItem(
                revision=revision,
                dimension=tier.dimension,
                billing_unit=tier.billing_unit,
                unit_price=tier.unit_price,
                tier_type=tier.tier_type,
                tier_start=tier.tier_start,
                tier_end=tier.tier_end,
                spec=tier.spec,
            )
            for tier in schedule.tiers
        ]
    )


def resale_listing_price_schedule(
    listing: ResaleListing,
    *,
    revision: ResaleListingPriceRevision | None = None,
) -> PriceSchedule:
    """Return a revision or compatibility listing as a canonical schedule."""
    selected_revision = revision
    if selected_revision is None:
        selected_revision = (
            listing.pending_price_revision
            or listing.current_price_revision
        )
    if selected_revision is not None:
        tiers = tuple(
            PriceTier(
                dimension=item.dimension,
                billing_unit=item.billing_unit,
                currency=selected_revision.currency,
                unit_price=item.unit_price,
                tier_type=item.tier_type,
                tier_start=item.tier_start,
                tier_end=item.tier_end,
                spec=dict(item.spec or {}),
            )
            for item in selected_revision.items.all()
        )
        schedule = PriceSchedule(tiers=tiers)
        validate_price_table_groups(schedule.tiers)
        return schedule

    currency = resolve_resale_listing_currency(listing)
    rows = [
        {**item, "currency": currency}
        for item in _flat_resale_listing_price_items(listing)
    ]
    return _normalize_resale_price_schedule(rows)


@transaction.atomic
def save_resale_listing_price_draft(
    listing: ResaleListing,
    *,
    items,
    currency: str,
    created_by=None,
    expected_revision_id=None,
) -> ResaleListingPriceRevision:
    """Atomically save a complete resale schedule as the active draft."""
    locked = (
        ResaleListing.objects.select_for_update()
        .select_related("platform", "model")
        .get(pk=listing.pk)
    )
    if locked.workflow_status == ResaleListing.WORKFLOW_ONLINE:
        locked.workflow_status = ResaleListing.WORKFLOW_UPDATE_DRAFT
    elif locked.workflow_status not in {
        ResaleListing.WORKFLOW_DRAFT,
        ResaleListing.WORKFLOW_UPDATE_DRAFT,
    }:
        raise ResalePriceRevisionError(
            "resale_price.invalid_listing_state",
            "The listing is not in an editable price state.",
        )
    normalized = _normalize_resale_price_schedule(items)
    normalized_currency = normalize_currency(currency)
    if not normalized_currency:
        raise ResalePriceRevisionError(
            "resale_price.currency_required",
            "A resale price currency is required.",
        )
    if any(
        normalize_currency(tier.currency) != normalized_currency
        for tier in normalized.tiers
    ):
        raise ResalePriceRevisionError(
            "resale_price.currency_mismatch",
            "Every price item must use the revision currency.",
        )

    pending = locked.pending_price_revision
    active_draft = (
        pending
        if pending
        and pending.status == ResaleListingPriceRevision.STATUS_DRAFT
        else None
    )
    if expected_revision_id is not None and (
        active_draft is None
        or str(active_draft.id) != str(expected_revision_id)
    ):
        raise ResalePriceRevisionError(
            "resale_price.revision_conflict",
            "The price draft changed after it was loaded.",
            conflict=True,
        )

    fingerprint = stable_fingerprint(
        {
            "currency": normalized_currency,
            "items": _standard_price_schedule(normalized),
        }
    )
    if active_draft is not None:
        revision = active_draft
        _replace_resale_revision_items(revision, normalized)
        revision.currency = normalized_currency
        revision.price_fingerprint = fingerprint
        revision.decision_snapshot = {}
        revision.decision_fingerprint = ""
        revision.save(
            update_fields=[
                "currency",
                "price_fingerprint",
                "decision_snapshot",
                "decision_fingerprint",
            ]
        )
    else:
        next_version = (
            locked.price_revisions.aggregate(maximum=Max("version"))[
                "maximum"
            ]
            or 0
        ) + 1
        revision = ResaleListingPriceRevision.objects.create(
            listing=locked,
            version=next_version,
            currency=normalized_currency,
            price_fingerprint=fingerprint,
            created_by=created_by,
        )
        _replace_resale_revision_items(revision, normalized)

    _project_resale_schedule_to_legacy_fields(
        locked,
        normalized,
        normalized_currency,
    )
    locked.pricing_format = derive_resale_pricing_format(normalized)
    locked.pending_price_revision = revision
    locked.save()
    listing.pending_price_revision_id = revision.id
    listing.workflow_status = locked.workflow_status
    return revision


def _project_resale_schedule_to_legacy_fields(
    listing: ResaleListing,
    schedule: PriceSchedule,
    currency: str,
) -> None:
    """Keep flat legacy fields as a usage-zero compatibility projection."""
    prices = {}
    for dimension in {tier.dimension for tier in schedule.tiers}:
        tier = resolve_price_tier(
            schedule,
            dimension=dimension,
            usage=ZERO,
        )
        prices[dimension] = tier.unit_price
    required = {
        ModelPriceItem.DIMENSION_TEXT_INPUT,
        ModelPriceItem.DIMENSION_TEXT_OUTPUT,
    }
    if listing.model.modality == LLMModel.MODALITY_TEXT and not (
        required <= set(prices)
    ):
        raise ResalePriceRevisionError(
            "resale_price.required_dimension_missing",
            "Text listings require input and output prices.",
        )
    field_map = {
        ModelPriceItem.DIMENSION_TEXT_INPUT: (
            "retail_input_price_per_million"
        ),
        ModelPriceItem.DIMENSION_TEXT_OUTPUT: (
            "retail_output_price_per_million"
        ),
        ModelPriceItem.DIMENSION_CACHE_INPUT: (
            "retail_cache_input_price_per_million"
        ),
        ModelPriceItem.DIMENSION_IMAGE_OUTPUT: (
            "retail_image_output_price_per_image"
        ),
        ModelPriceItem.DIMENSION_AUDIO_INPUT: (
            "retail_audio_input_price_per_second"
        ),
        ModelPriceItem.DIMENSION_AUDIO_OUTPUT: (
            "retail_audio_output_price_per_second"
        ),
        ModelPriceItem.DIMENSION_VIDEO_INPUT: (
            "retail_video_input_price_per_second"
        ),
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT: (
            "retail_video_output_price_per_second"
        ),
    }
    listing.currency = currency
    for dimension, field_name in field_map.items():
        setattr(listing, field_name, prices.get(dimension))


def preview_resale_listing_price(
    listing: ResaleListing,
    *,
    revision: ResaleListingPriceRevision | None = None,
    items=None,
    currency: str | None = None,
) -> dict:
    """Build the canonical cost, fee, margin and approval preview."""
    _validate_resale_listing_context(listing)
    if revision is not None:
        retail_schedule = resale_listing_price_schedule(
            listing,
            revision=revision,
        )
        retail_currency = revision.currency
    elif items is not None:
        retail_schedule = _normalize_resale_price_schedule(items)
        retail_currency = normalize_currency(currency)
    else:
        retail_schedule = resale_listing_price_schedule(listing)
        retail_currency = resolve_resale_listing_currency(listing)
    if not retail_currency:
        raise ResalePriceRevisionError(
            "resale_price.currency_required",
            "A resale price currency is required.",
        )
    if not retail_schedule.tiers:
        raise ResalePriceRevisionError(
            "resale_price.items_required",
            "At least one resale price item is required.",
        )
    if any(
        normalize_currency(tier.currency) != retail_currency
        for tier in retail_schedule.tiers
    ):
        raise ResalePriceRevisionError(
            "resale_price.currency_mismatch",
            "Every price item must use the preview currency.",
        )

    override = (
        ChannelModelPrice.objects.select_related(
            "channel",
            "model",
            "price_source",
        )
        .filter(
            channel=listing.channel,
            model=listing.model,
            is_listed=True,
        )
        .first()
    )
    if override is None:
        raise ResalePriceRevisionError(
            "resale_price.channel_price_unavailable",
            "The selected channel has no active model price.",
        )
    if override.price_source and not override.price_source.is_enabled:
        raise ResalePriceRevisionError(
            "resale_price.price_source_inactive",
            "The selected price source is inactive.",
        )

    source_items = current_model_price_items_for_channel_price(override)
    raw_cost_schedule = resolve_channel_price_schedule(
        listing.channel,
        listing.model,
        override=override,
        source_items=source_items,
    )
    cost_schedule = _matching_cost_schedule(
        raw_cost_schedule,
        retail_schedule,
    )
    profitability = calculate_tiered_profitability(
        cost_schedule,
        retail_schedule,
        platform=listing.platform,
    )
    lineage = _cost_schedule_lineage(source_items, override)
    cost_stale = any(item["is_stale"] for item in lineage)
    approval = _resale_auto_approval(listing, profitability)
    currency_context = build_currency_conversion_context(retail_currency)
    return {
        "retail_schedule": _standard_price_schedule(retail_schedule),
        "cost_schedule": _standard_price_schedule(cost_schedule),
        "profitability": profitability,
        "fee_config": {
            "fee_rate": listing.platform.fee_rate,
            "service_fee_rate": listing.platform.service_fee_rate,
            "tax_rate": listing.platform.tax_rate,
            "settlement_rate": listing.platform.settlement_rate,
            "yield_warning": listing.platform.yield_warning,
            "auto_approve_max_margin_rate": (
                listing.platform.auto_approve_max_margin_rate
            ),
        },
        "exchange_rate": {
            "display_currency": currency_context.display_currency,
            "usd_to_cny_rate": currency_context.usd_to_cny_rate,
            "source_label": currency_context.rate_source_label,
            "source_url": currency_context.rate_source_url,
            "collected_at": currency_context.rate_collected_at,
        },
        "cost_lineage": lineage,
        "cost_stale": cost_stale,
        "approval": approval,
    }


def _validate_resale_listing_context(listing: ResaleListing) -> None:
    """Validate stable listing dependencies before pricing decisions."""
    if not listing.platform.is_active:
        raise ResalePriceRevisionError(
            "resale_price.platform_inactive",
            "The resale platform is inactive.",
        )
    if not listing.model.is_active:
        raise ResalePriceRevisionError(
            "resale_price.model_inactive",
            "The model is inactive.",
        )
    if listing.channel is None:
        raise ResalePriceRevisionError(
            "resale_price.channel_required",
            "A fixed procurement channel is required for tier preview.",
        )
    if not listing.channel.is_active:
        raise ResalePriceRevisionError(
            "resale_price.channel_inactive",
            "The procurement channel is inactive.",
        )


def _matching_cost_schedule(
    cost_schedule: PriceSchedule,
    retail_schedule: PriceSchedule,
) -> PriceSchedule:
    """Select canonical cost dimensions required by the retail schedule."""
    retail_dimensions = {
        tier.dimension for tier in retail_schedule.tiers
    }
    for dimension in retail_dimensions:
        if not cost_schedule.for_dimension(dimension):
            raise ResalePriceRevisionError(
                "resale_price.cost_dimension_missing",
                "A resale dimension has no matching procurement cost.",
            )
    selected = tuple(
        tier
        for tier in cost_schedule.tiers
        if tier.dimension in retail_dimensions
    )
    schedule = PriceSchedule(tiers=selected)
    validate_price_table_groups(schedule.tiers)
    return schedule


def _standard_price_schedule(schedule: PriceSchedule) -> list[dict]:
    """Serialize a canonical schedule without changing its semantics."""
    return [
        {
            "dimension": tier.dimension,
            "billing_unit": tier.billing_unit,
            "currency": tier.currency,
            "unit_price": tier.unit_price,
            "tier_type": tier.tier_type,
            "tier_start": tier.tier_start,
            "tier_end": tier.tier_end,
            "spec": tier.spec,
        }
        for tier in schedule.tiers
    ]


def calculate_tiered_profitability(
    cost_schedule: PriceSchedule,
    retail_schedule: PriceSchedule,
    *,
    platform: ResalePlatform,
) -> dict:
    """Adapt canonical tier-profit analysis to the approval API payload."""
    intervals = []
    for dimension in sorted(
        {tier.dimension for tier in retail_schedule.tiers}
    ):
        cost_tiers = cost_schedule.for_dimension(dimension)
        retail_tiers = retail_schedule.for_dimension(dimension)
        cost_rate = convert_currency_between(
            ONE,
            cost_tiers[0].currency,
            retail_tiers[0].currency,
        )
        if cost_rate is None:
            raise ResalePriceRevisionError(
                "resale_price.currency_conversion_required",
                "The procurement cost currency cannot be converted.",
            )
        policy = RevenuePolicy(
            target_currency=retail_tiers[0].currency,
            cost_exchange_rate=cost_rate,
            platform_fee_rate=decimal_or_zero(platform.fee_rate),
            service_fee_rate=decimal_or_zero(platform.service_fee_rate),
            tax_rate=decimal_or_zero(platform.tax_rate),
            settlement_rate=decimal_or_zero(platform.settlement_rate) or ONE,
            risk_net_yield_rate=decimal_or_zero(platform.yield_warning),
        )
        analysis = analyze_tier_profit(
            cost_schedule,
            retail_schedule,
            dimension=dimension,
            policy=policy,
        )
        for interval in analysis.intervals:
            retail_tier = resolve_price_tier(
                retail_schedule,
                dimension=dimension,
                usage=interval.tier_start,
            )
            markup_rate = ZERO
            if interval.converted_cost_unit_price:
                markup_rate = (
                    interval.converted_retail_unit_price
                    - interval.converted_cost_unit_price
                ) / interval.converted_cost_unit_price
            elif interval.converted_retail_unit_price > ZERO:
                markup_rate = ONE
            intervals.append(
                {
                    "dimension": interval.dimension,
                    "billing_unit": interval.billing_unit,
                    "currency": interval.currency,
                    "spec": retail_tier.spec,
                    "tier_start": interval.tier_start,
                    "tier_end": interval.tier_end,
                    "cost_unit_price": (
                        interval.converted_cost_unit_price
                    ),
                    "retail_unit_price": (
                        interval.converted_retail_unit_price
                    ),
                    "settled_cost": interval.cost,
                    "platform_fee": (
                        interval.gross_revenue
                        * policy.platform_fee_rate
                    ).quantize(Decimal("0.000001")),
                    "service_fee": (
                        interval.gross_revenue
                        * policy.service_fee_rate
                    ).quantize(Decimal("0.000001")),
                    "tax_fee": (
                        interval.gross_revenue * policy.tax_rate
                    ).quantize(Decimal("0.000001")),
                    "net_revenue": interval.net_revenue,
                    "gross_margin": interval.gross_profit,
                    "gross_margin_rate": interval.gross_margin_rate,
                    "net_yield_rate": interval.net_yield_rate,
                    "markup_rate": markup_rate.quantize(
                        Decimal("0.000001")
                    ),
                    "is_risk": interval.is_risk,
                }
            )

    risk_intervals = [item for item in intervals if item["is_risk"]]
    minimum_margin_interval = min(
        intervals,
        key=lambda item: item["gross_margin"],
        default=None,
    )
    return {
        "intervals": intervals,
        "minimum_gross_margin": (
            minimum_margin_interval["gross_margin"]
            if minimum_margin_interval
            else None
        ),
        "minimum_gross_margin_interval": minimum_margin_interval,
        "minimum_gross_margin_rate": min(
            (item["gross_margin_rate"] for item in intervals),
            default=None,
        ),
        "minimum_net_yield_rate": min(
            (item["net_yield_rate"] for item in intervals),
            default=None,
        ),
        "maximum_markup_rate": max(
            (item["markup_rate"] for item in intervals),
            default=None,
        ),
        "risk_intervals": risk_intervals,
    }


def _cost_schedule_lineage(source_items, override) -> list[dict]:
    """Capture immutable source versions and freshness for cost evidence."""
    stale_before = timezone.now() - timedelta(days=30)
    lineage = []
    seen = set()
    for base_item in source_items:
        key = base_item.id
        if key in seen:
            continue
        seen.add(key)
        observed_at = None
        if base_item is not None:
            observed_at = base_item.effective_from or base_item.updated_at
        lineage.append(
            {
                "channel_id": override.channel_id,
                "channel_price_id": override.id,
                "price_source_id": override.price_source_id,
                "base_price_item_id": key,
                "observed_at": (
                    observed_at.isoformat() if observed_at else None
                ),
                "is_stale": bool(
                    observed_at and observed_at < stale_before
                ),
            }
        )
    return lineage


def _resale_auto_approval(listing, profitability) -> dict:
    """Evaluate all tier markups against the server-side workflow policy."""
    from .workflow_config import merge_resale_workflow_config

    saved = ResaleWorkflowConfig.objects.filter(
        platform=listing.platform
    ).first()
    config = merge_resale_workflow_config(
        listing.platform,
        saved.config if saved else None,
    )
    enabled = bool(config["policies"].get("auto_approve_enabled"))
    maximum_markup = profitability.get("maximum_markup_rate")
    limit_percent = decimal_or_zero(
        listing.platform.auto_approve_max_margin_rate
    )
    eligible = bool(
        enabled
        and maximum_markup is not None
        and maximum_markup * Decimal("100") <= limit_percent
        and not profitability.get("risk_intervals")
    )
    return {
        "enabled": enabled,
        "eligible": eligible,
        "result": (
            "auto_approved" if eligible else "manual_review_required"
        ),
        "maximum_markup_rate": maximum_markup,
        "limit_percent": limit_percent,
        "requires_manual_review": not eligible,
    }


@transaction.atomic
def submit_resale_listing_price_revision(
    listing: ResaleListing,
    revision: ResaleListingPriceRevision,
    *,
    submitted_by=None,
) -> tuple[ResaleListingPriceRevision, dict]:
    """Submit a concrete draft with immutable decision evidence."""
    locked = (
        ResaleListing.objects.select_for_update()
        .select_related("platform", "model")
        .get(pk=listing.pk)
    )
    revision = ResaleListingPriceRevision.objects.select_for_update().get(
        pk=revision.pk,
        listing=locked,
    )
    if locked.pending_price_revision_id != revision.id:
        raise ResalePriceRevisionError(
            "resale_price.revision_not_pending",
            "The revision is no longer the active draft.",
            conflict=True,
        )
    if revision.status != ResaleListingPriceRevision.STATUS_DRAFT:
        raise ResalePriceRevisionError(
            "resale_price.invalid_revision_state",
            "Only a draft price revision can be submitted.",
        )

    preview = preview_resale_listing_price(locked, revision=revision)
    if preview["cost_stale"]:
        raise ResalePriceRevisionError(
            "resale_price.cost_stale",
            "The procurement cost snapshot is stale.",
        )
    if preview["profitability"]["risk_intervals"]:
        raise ResalePriceRevisionError(
            "resale_price.minimum_margin_below_warning",
            "At least one tier is below the platform yield warning.",
        )

    submitted_at = timezone.now()
    snapshot = json_safe_payload(preview)
    snapshot["submitted_at"] = submitted_at.isoformat()
    snapshot["submitted_by_id"] = (
        submitted_by.id if submitted_by is not None else None
    )
    revision.decision_snapshot = snapshot
    revision.decision_fingerprint = stable_fingerprint(snapshot)
    revision.submitted_by = submitted_by
    revision.submitted_at = submitted_at
    auto_approved = bool(preview["approval"]["eligible"])
    revision.status = (
        ResaleListingPriceRevision.STATUS_APPROVED
        if auto_approved
        else ResaleListingPriceRevision.STATUS_SUBMITTED
    )
    if auto_approved:
        revision.approved_by = submitted_by
        revision.approved_at = submitted_at
    revision.save()

    if locked.workflow_status == ResaleListing.WORKFLOW_DRAFT:
        locked.workflow_status = ResaleListing.WORKFLOW_PENDING_PUBLISH
    elif locked.workflow_status == ResaleListing.WORKFLOW_UPDATE_DRAFT:
        locked.workflow_status = ResaleListing.WORKFLOW_PENDING_UPDATE
    else:
        raise ResalePriceRevisionError(
            "resale_price.invalid_listing_state",
            "The listing is not in an editable draft state.",
        )
    locked.save(update_fields=["workflow_status", "updated_at"])
    listing.workflow_status = locked.workflow_status
    return revision, preview


@transaction.atomic
def approve_and_publish_resale_price_revision(
    listing: ResaleListing,
    *,
    approved_by=None,
) -> ResaleListingPriceRevision | None:
    """Bind manual approval and publication to the pending revision."""
    locked = ResaleListing.objects.select_for_update().get(pk=listing.pk)
    revision = locked.pending_price_revision
    if revision is None:
        return None
    if not revision.decision_snapshot:
        raise ResalePriceRevisionError(
            "resale_price.approval_evidence_missing",
            "The pending revision has no immutable decision snapshot.",
        )
    if revision.status == ResaleListingPriceRevision.STATUS_SUBMITTED:
        revision.status = ResaleListingPriceRevision.STATUS_APPROVED
        revision.approved_by = approved_by
        revision.approved_at = timezone.now()
        revision.save()
    elif revision.status != ResaleListingPriceRevision.STATUS_APPROVED:
        raise ResalePriceRevisionError(
            "resale_price.invalid_revision_state",
            "The pending revision is not ready for approval.",
        )

    current = locked.current_price_revision
    if current and current.id != revision.id:
        current.status = ResaleListingPriceRevision.STATUS_SUPERSEDED
        current.save(update_fields=["status"])
    revision.effective_from = timezone.now()
    revision.save(update_fields=["effective_from"])
    locked.current_price_revision = revision
    locked.pending_price_revision = None
    locked.published_price_revision = revision
    locked.save(
        update_fields=[
            "current_price_revision",
            "pending_price_revision",
            "published_price_revision",
            "updated_at",
        ]
    )
    listing.current_price_revision_id = revision.id
    listing.pending_price_revision_id = None
    listing.published_price_revision_id = revision.id
    return revision


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


# ---------------------------------------------------------------------------
# Model Resale Decision helper
# ---------------------------------------------------------------------------
#
# Compute the canonical decision row used by the LLM Ops Monitor
# overview page. Inputs are plain dicts (matching SummaryAPIView
# procurement_rows and ResaleListing payloads). Outputs follow the
# shape described in docs/llm-ops/overview-refactor.codex.md.
#
# No global fallback constants: if any platform fee/yield field is
# missing, ``platform_fee_unresolved`` is returned and the yield
# values stay ``None``.


DECISION_STATUS_NO_SUPPLY = "no_supply"
DECISION_STATUS_CURRENCY_UNRESOLVED = "currency_unresolved"
DECISION_STATUS_PLATFORM_FEE_UNRESOLVED = "platform_fee_unresolved"
DECISION_STATUS_LOW_YIELD = "low_yield"
DECISION_STATUS_NOT_LOWEST_CHANNEL = "not_lowest_channel"
DECISION_STATUS_UNLISTED = "unlisted"
DECISION_STATUS_SINGLE_CHANNEL = "single_channel"
DECISION_STATUS_READY = "ready"
DECISION_STATUS_MARKET_REFERENCE = "market_reference"

OPERATION_SCOPE_OPERATIONAL = "operational"
OPERATION_SCOPE_MARKET_REFERENCE = "market_reference"


_DECISION_PRIORITY = {
    DECISION_STATUS_NO_SUPPLY: 1,
    DECISION_STATUS_CURRENCY_UNRESOLVED: 2,
    DECISION_STATUS_PLATFORM_FEE_UNRESOLVED: 3,
    DECISION_STATUS_LOW_YIELD: 4,
    DECISION_STATUS_NOT_LOWEST_CHANNEL: 5,
    DECISION_STATUS_UNLISTED: 6,
    DECISION_STATUS_SINGLE_CHANNEL: 7,
    DECISION_STATUS_READY: 8,
    DECISION_STATUS_MARKET_REFERENCE: 9,
}


_DECISION_ACTION = {
    DECISION_STATUS_NO_SUPPLY: "configure_channel",
    DECISION_STATUS_CURRENCY_UNRESOLVED: "configure_exchange_rate",
    DECISION_STATUS_PLATFORM_FEE_UNRESOLVED: "configure_platform_fee",
    DECISION_STATUS_LOW_YIELD: "review_pricing_or_channel",
    DECISION_STATUS_NOT_LOWEST_CHANNEL: "switch_lowest_channel",
    DECISION_STATUS_UNLISTED: "publish_listing",
    DECISION_STATUS_SINGLE_CHANNEL: "add_channel_coverage",
    DECISION_STATUS_READY: "keep",
    DECISION_STATUS_MARKET_REFERENCE: "view_market_price",
}


DECISION_ANOMALY_EVENT_TYPES = {
    "collection_failed",
    "source_disabled",
    "reconciliation_anomaly",
}


def _decimal(value, default=None):
    """Return Decimal for numeric input, preserving None as None."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _fee_config_resolved(platform) -> bool:
    """Return True when every required fee field is non-null."""
    required = (
        "fee_rate",
        "service_fee_rate",
        "tax_rate",
        "settlement_rate",
        "yield_warning",
    )
    for attr in required:
        if getattr(platform, attr, None) is None:
            return False
    return True


def _compute_yield(retail, cost, platform):
    """Return (input_yield, output_yield) or (None, None)."""
    if not _fee_config_resolved(platform):
        return None, None
    net_factor = (
        Decimal("1")
        - Decimal(str(platform.fee_rate))
        - Decimal(str(platform.service_fee_rate))
        - Decimal(str(platform.tax_rate))
    )
    settlement = Decimal(str(platform.settlement_rate))
    if retail is None or cost is None:
        return None, None
    if retail == ZERO:
        if cost > ZERO:
            return Decimal("-1"), Decimal("-1")
        return ZERO, ZERO
    net = retail * net_factor - cost * settlement
    yield_rate = net / retail if retail else None
    return yield_rate, yield_rate


def compute_model_decision(
    *,
    procurement_row,
    current_listing,
    platform,
    operation_scope=OPERATION_SCOPE_OPERATIONAL,
    data_event_type="updated",
    last_data_event_at=None,
):
    """Build the canonical decision payload for one model row.

    Parameters
    ----------
    procurement_row : dict
        SummaryAPIView procurement row. Must include ``best_channel``,
        ``options`` (list) and ``requires_currency_conversion``.
    current_listing : dict or None
        Currently active listing payload for the selected platform.
    platform : ResalePlatform or None
        Selected resale platform used for fee/yield lookup.
    operation_scope : str
        ``operational`` for channel/resale decisions or
        ``market_reference`` for price-only catalog rows.
    data_event_type : str
        ``updated`` | ``collection_failed`` | ``source_disabled`` |
        ``reconciliation_anomaly`` | ``stale``.
    last_data_event_at : datetime or None
        Timestamp of the most recent data event for the row.
    """
    best_channel = (procurement_row or {}).get("best_channel") or None
    options = list((procurement_row or {}).get("options") or [])
    requires_currency_conversion = bool(
        (best_channel or {}).get("requires_currency_conversion")
        or (procurement_row or {}).get(
            "requires_currency_conversion",
        )
    )
    is_listed = bool(
        (current_listing or {}).get("is_listed", bool(current_listing))
    )
    listing_requires_currency_conversion = bool(
        (current_listing or {}).get("requires_currency_conversion")
    )

    if operation_scope == OPERATION_SCOPE_MARKET_REFERENCE:
        status = DECISION_STATUS_MARKET_REFERENCE
        return {
            "decision_status": status,
            "decision_action": _DECISION_ACTION[status],
            "decision_priority": _DECISION_PRIORITY[status],
            "input_yield": None,
            "output_yield": None,
            "data_event_type": data_event_type,
            "last_data_event_at": (
                last_data_event_at.isoformat()
                if last_data_event_at is not None
                else None
            ),
            "is_data_anomaly": data_event_type
            in DECISION_ANOMALY_EVENT_TYPES,
        }

    if best_channel is None:
        status = DECISION_STATUS_NO_SUPPLY
    elif requires_currency_conversion or listing_requires_currency_conversion:
        status = DECISION_STATUS_CURRENCY_UNRESOLVED
    elif platform is None or not _fee_config_resolved(platform):
        status = DECISION_STATUS_PLATFORM_FEE_UNRESOLVED
    elif is_listed:
        if "cost_input_price_per_million" in (current_listing or {}):
            cost_input = _decimal(
                (current_listing or {}).get(
                    "cost_input_price_per_million"
                ),
            )
        else:
            cost_input = _decimal(best_channel.get("input_price_per_million"))
        if "cost_output_price_per_million" in (current_listing or {}):
            cost_output = _decimal(
                (current_listing or {}).get(
                    "cost_output_price_per_million"
                ),
            )
        else:
            cost_output = _decimal(
                best_channel.get("output_price_per_million")
            )
        retail_input = _decimal(
            (current_listing or {}).get(
                "retail_input_price_per_million"
            )
        )
        retail_output = _decimal(
            (current_listing or {}).get(
                "retail_output_price_per_million"
            )
        )
        input_yield, _ = _compute_yield(retail_input, cost_input, platform)
        _, output_yield = _compute_yield(
            retail_output, cost_output, platform
        )
        yield_warning = Decimal(str(platform.yield_warning))
        below_warning = (
            (input_yield is not None and input_yield < yield_warning)
            or (
                output_yield is not None
                and output_yield < yield_warning
            )
        )
        listing_channel_id = (current_listing or {}).get("channel_id")
        on_lowest = (
            listing_channel_id is None
            or listing_channel_id == best_channel.get("channel_id")
        )
        if below_warning:
            status = DECISION_STATUS_LOW_YIELD
        elif not on_lowest:
            status = DECISION_STATUS_NOT_LOWEST_CHANNEL
        elif len(options) <= 1:
            status = DECISION_STATUS_SINGLE_CHANNEL
        else:
            status = DECISION_STATUS_READY
        return {
            "decision_status": status,
            "decision_action": _DECISION_ACTION[status],
            "decision_priority": _DECISION_PRIORITY[status],
            "input_yield": input_yield,
            "output_yield": output_yield,
            "data_event_type": data_event_type,
            "last_data_event_at": (
                last_data_event_at.isoformat()
                if last_data_event_at is not None
                else None
            ),
            "is_data_anomaly": data_event_type
            in DECISION_ANOMALY_EVENT_TYPES,
        }
    else:
        status = DECISION_STATUS_UNLISTED

    return {
        "decision_status": status,
        "decision_action": _DECISION_ACTION[status],
        "decision_priority": _DECISION_PRIORITY[status],
        "input_yield": None,
        "output_yield": None,
        "data_event_type": data_event_type,
        "last_data_event_at": (
            last_data_event_at.isoformat()
            if last_data_event_at is not None
            else None
        ),
        "is_data_anomaly": data_event_type
        in DECISION_ANOMALY_EVENT_TYPES,
    }
