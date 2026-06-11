from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from django.db import transaction
from django.utils import timezone

from .collectors import CollectedModelPricing, CollectedPricingCatalog
from .collectors.official import (
    OFFICIAL_PROVIDER_CONFIGS,
    collect_official_pricing_catalog,
)
from .collectors.yunce import DEFAULT_YUNCE_BASE_URL, YuncePricingClient
from .models import (
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
)
from .services import ensure_meta_model, price_role_for_source


def collect_yunce_pricing_catalog(
    *,
    username: str,
    password: str,
    base_url: str = DEFAULT_YUNCE_BASE_URL,
) -> CollectedPricingCatalog:
    """Fetch and normalize Yunce model pricing without persisting it."""
    client = YuncePricingClient(base_url=base_url)
    return client.collect_catalog(username=username, password=password)


def sync_yunce_model_prices(
    *,
    username: str,
    password: str,
    source: PriceCollectionSource | None = None,
    base_url: str = DEFAULT_YUNCE_BASE_URL,
) -> dict[str, int]:
    """Fetch Yunce pricing and persist model prices plus snapshots."""
    source = source or ensure_yunce_source(base_url=base_url)
    if not source.is_enabled:
        raise ValueError("Price collection source is disabled.")
    base_url = resolve_collection_base_url(source=source, base_url=base_url)
    run = PriceCollectionRun.objects.create(source=source)
    stats = {
        "models": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "changed": 0,
        "unchanged": 0,
    }

    try:
        catalog = collect_yunce_pricing_catalog(
            username=username,
            password=password,
            base_url=base_url,
        )
        skipped_provider_names = []
        with transaction.atomic():
            for item in catalog.models:
                if not matches_source_provider(item, source):
                    stats["skipped"] += 1
                    if item.model_source:
                        skipped_provider_names.append(item.model_source)
                    continue

                model, created = upsert_collected_model(
                    item,
                    source=source,
                    source_url=catalog.source_url,
                )
                _, changed = upsert_collected_snapshot(
                    item,
                    source=source,
                    run=run,
                    model=model,
                    provider=model.provider,
                )
                sync_model_price_items(
                    item,
                    source=source,
                    model=model,
                    provider=model.provider,
                    source_url=catalog.source_url,
                )
                stats["models"] += 1
                stats["created" if created else "updated"] += 1
                stats["changed" if changed else "unchanged"] += 1

            source.last_collected_at = timezone.now()
            source.save(update_fields=["last_collected_at", "updated_at"])
            run.status = PriceCollectionRun.STATUS_SUCCEEDED
            run.finished_at = timezone.now()
            run.collected_count = stats["models"]
            run.created_count = stats["created"]
            run.updated_count = stats["updated"]
            run.skipped_count = stats["skipped"]
            run.metadata = {
                "source_url": catalog.source_url,
                "total_models": catalog.total_models,
                "changed_count": stats["changed"],
                "unchanged_count": stats["unchanged"],
                "skipped_provider_names": sorted(
                    set(skipped_provider_names),
                ),
            }
            run.save()
        return stats
    except Exception as exc:
        run.status = PriceCollectionRun.STATUS_FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.collected_count = stats["models"]
        run.created_count = stats["created"]
        run.updated_count = stats["updated"]
        run.skipped_count = stats["skipped"]
        run.save()
        raise


def resolve_collection_base_url(
    *,
    source: PriceCollectionSource,
    base_url: str,
) -> str:
    """Resolve the API base URL from request override or source config."""
    if base_url != DEFAULT_YUNCE_BASE_URL:
        return base_url
    if source.endpoint_url:
        return api_base_from_endpoint(source.endpoint_url)
    return base_url


def api_base_from_endpoint(endpoint: str) -> str:
    """Normalize a configured Yunce endpoint into its API base URL."""
    value = str(endpoint or "").strip().rstrip("/")
    if not value:
        return DEFAULT_YUNCE_BASE_URL
    if value.endswith("/admin/api"):
        return value
    return f"{value}/admin/api"


def matches_source_provider(
    item: CollectedModelPricing,
    source: PriceCollectionSource,
) -> bool:
    """Return whether a collected item belongs to the source provider."""
    if source.provider is None:
        return True
    aliases = provider_aliases(source.provider)
    candidates = {
        item.model_source,
        item.provider,
    }
    raw_provider = item.raw_detail.get("model_info", {}).get("provider")
    candidates.add(raw_provider)
    for candidate in candidates:
        if normalize_provider_label(candidate) in aliases:
            return True
    return False


def provider_aliases(provider: LLMProvider) -> set[str]:
    """Return normalized aliases accepted for a canonical provider."""
    aliases = {
        provider.name,
        provider.code,
    }
    code_aliases = {
        "openai": {"OpenAI", "Azure OpenAI"},
        "anthropic": {"Anthropic", "AWS Cloud", "Claude"},
        "google": {"Google", "Google云", "Google Cloud"},
        "aliyun": {"阿里云", "阿里云百炼", "DashScope"},
        "aliyun-wanx": {"阿里云万象", "通义万相", "WAN"},
        "volcengine": {"火山", "Volcengine", "豆包"},
    }
    aliases.update(code_aliases.get(provider.code, set()))
    return {normalize_provider_label(alias) for alias in aliases}


def normalize_provider_label(value: str | None) -> str:
    """Normalize provider labels for loose source matching."""
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[\s_\-]+", "", normalized)
    return normalized


def sync_yunce_text_model_prices(
    *,
    username: str,
    password: str,
    source: PriceCollectionSource | None = None,
    base_url: str = DEFAULT_YUNCE_BASE_URL,
) -> dict[str, int]:
    """Compatibility wrapper for the full Yunce model sync."""
    return sync_yunce_model_prices(
        username=username,
        password=password,
        source=source,
        base_url=base_url,
    )


def sync_official_provider_model_prices(
    *,
    provider: LLMProvider,
    source: PriceCollectionSource | None = None,
    verify_source: bool = True,
) -> dict[str, int | list[str]]:
    """Collect and persist official provider prices for existing models."""
    if provider.code not in OFFICIAL_PROVIDER_CONFIGS:
        raise ValueError(f"Unsupported official provider: {provider.code}")

    config = OFFICIAL_PROVIDER_CONFIGS[provider.code]
    source = source or ensure_official_source(provider=provider)
    if source.provider_id != provider.id:
        raise ValueError("Price source does not belong to the provider.")
    if not source.is_enabled:
        raise ValueError("Price collection source is disabled.")

    configured_codes = set(
        provider.models.filter(is_active=True).values_list("code", flat=True)
    )
    run = PriceCollectionRun.objects.create(source=source)
    stats: dict[str, int | list[str]] = {
        "models": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped_model_codes": [],
    }

    try:
        source_url = official_source_url(provider, source, config)
        if source_url != source.endpoint_url:
            source.endpoint_url = source_url
            source.save(update_fields=["endpoint_url", "updated_at"])

        catalog = collect_official_pricing_catalog(
            provider_code=provider.code,
            model_codes=configured_codes,
            source_url=source_url,
            verify_source=verify_source,
        )
        collected_currency = first_catalog_currency(catalog)
        collected_codes = {item.model_id for item in catalog.models}
        skipped_codes = sorted(configured_codes - collected_codes)
        with transaction.atomic():
            for item in catalog.models:
                model, created = upsert_collected_model(
                    item,
                    source=source,
                    source_url=catalog.source_url,
                )
                _, changed = upsert_collected_snapshot(
                    item,
                    source=source,
                    run=run,
                    model=model,
                    provider=model.provider,
                )
                sync_model_price_items(
                    item,
                    source=source,
                    model=model,
                    provider=model.provider,
                    source_url=catalog.source_url,
                )
                stats["models"] = int(stats["models"]) + 1
                key = "created" if created else "updated"
                stats[key] = int(stats[key]) + 1
                change_key = "changed" if changed else "unchanged"
                stats[change_key] = int(stats[change_key]) + 1

            source.last_collected_at = timezone.now()
            source_update_fields = ["last_collected_at", "updated_at"]
            if collected_currency and source.currency != collected_currency:
                source.currency = collected_currency
                source_update_fields.append("currency")
            source.save(update_fields=source_update_fields)
            run.status = PriceCollectionRun.STATUS_SUCCEEDED
            run.finished_at = timezone.now()
            run.collected_count = int(stats["models"])
            run.created_count = int(stats["created"])
            run.updated_count = int(stats["updated"])
            run.skipped_count = len(skipped_codes)
            run.metadata = {
                "source_url": catalog.source_url,
                "currency": collected_currency or source.currency,
                "configured_currency": config.currency,
                "total_configured_models": len(configured_codes),
                "changed_count": stats["changed"],
                "unchanged_count": stats["unchanged"],
                "skipped_model_codes": skipped_codes,
            }
            run.save()
            stats["skipped"] = len(skipped_codes)
            stats["skipped_model_codes"] = skipped_codes
        return stats
    except Exception as exc:
        run.status = PriceCollectionRun.STATUS_FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.collected_count = int(stats["models"])
        run.created_count = int(stats["created"])
        run.updated_count = int(stats["updated"])
        run.skipped_count = int(stats["skipped"])
        run.save()
        raise


def first_catalog_currency(catalog) -> str:
    """Return the first non-empty currency observed in a collected catalog."""
    for item in catalog.models:
        if item.currency:
            return item.currency
    return ""


def sync_configured_official_model_prices(
    *,
    provider_codes: list[str] | None = None,
    verify_source: bool = True,
) -> dict[str, dict[str, int | list[str]]]:
    """Collect official prices for configured supported providers."""
    queryset = LLMProvider.objects.filter(
        code__in=provider_codes or OFFICIAL_PROVIDER_CONFIGS.keys(),
        is_active=True,
    ).order_by("code")
    results = {}
    for provider in queryset:
        results[provider.code] = sync_official_provider_model_prices(
            provider=provider,
            verify_source=verify_source,
        )
    return results


def official_source_url(
    provider: LLMProvider,
    source: PriceCollectionSource,
    config,
) -> str:
    """Return the effective official source URL for collection."""
    endpoint_url = source.endpoint_url or config.source_url
    broken_urls = {
        "aliyun-wanx": {
            "https://help.aliyun.com/zh/model-studio/model-price",
        },
    }
    if endpoint_url in broken_urls.get(provider.code, set()):
        return config.source_url
    return endpoint_url


def upsert_collected_model(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    source_url: str,
) -> tuple[LLMModel, bool]:
    """Upsert one collected model into the canonical model table."""
    provider = source.provider
    if provider is None:
        provider, _ = LLMProvider.objects.get_or_create(
            code=slugify_provider(item.model_source),
            defaults={
                "name": item.model_source or "Unknown",
                "is_active": True,
            },
        )
    lookup = {
        "provider": provider,
        "source": source,
        "code": item.model_id or item.name,
    }
    meta_model = ensure_meta_model(
        code=item.model_id or item.name,
        name=item.name or item.model_id,
        provider=provider,
        modality=modality_from_source_type(item.source_model_type),
    )
    defaults = model_defaults_from_collected_item(
        item,
        source=source,
        source_url=source_url,
    )
    defaults["meta_model"] = meta_model
    defaults["price_role"] = price_role_for_source(source)
    if source.updates_model_prices:
        return LLMModel.objects.update_or_create(**lookup, defaults=defaults)

    create_defaults = model_identity_defaults_from_collected_item(
        item,
        source=source,
        source_url=source_url,
    )
    create_defaults["meta_model"] = meta_model
    create_defaults["price_role"] = price_role_for_source(source)
    model, created = LLMModel.objects.get_or_create(
        **lookup,
        defaults=create_defaults,
    )
    if created:
        return model, True

    identity_fields = {
        "meta_model": meta_model,
        "name": create_defaults["name"],
        "modality": create_defaults["modality"],
        "currency": create_defaults["currency"],
        "source": source,
        "source_url": source_url,
        "price_role": price_role_for_source(source),
        "is_active": True,
    }
    changed_fields = []
    for field, value in identity_fields.items():
        if getattr(model, field) != value:
            setattr(model, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        model.save(update_fields=changed_fields)
    return model, False


def upsert_collected_snapshot(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    run: PriceCollectionRun,
    model: LLMModel,
    provider: LLMProvider,
) -> tuple[CollectedModelPriceSnapshot, bool]:
    """Persist the latest normalized source payload for one model."""
    rows = normalized_rows_payload(item)
    payload = collected_payload(
        item,
        run=run,
        model=model,
        provider=provider,
        rows=rows,
    )
    fingerprint = price_fingerprint(payload)
    existing = CollectedModelPriceSnapshot.objects.filter(
        source=source,
        source_platform_id=str(item.platform_id),
    ).first()
    changed = (
        existing is None
        or existing.price_fingerprint != fingerprint
    )
    if changed:
        create_collected_price_history(
            payload,
            source=source,
            source_platform_id=str(item.platform_id),
            previous=existing,
            price_hash=fingerprint,
        )

    payload["price_fingerprint"] = fingerprint
    snapshot, _ = CollectedModelPriceSnapshot.objects.update_or_create(
        source=source,
        source_platform_id=str(item.platform_id),
        defaults=payload,
    )
    return snapshot, changed


def normalized_rows_payload(item: CollectedModelPricing) -> list[dict]:
    """Build a JSON-safe normalized price row payload."""
    return [
        {
            "kind": row.kind,
            "values": row.values,
            "raw": row.raw,
        }
        for row in item.price_rows
    ]


def collected_payload(
    item: CollectedModelPricing,
    *,
    run: PriceCollectionRun,
    model: LLMModel,
    provider: LLMProvider,
    rows: list[dict],
) -> dict:
    """Build common collected price payload fields."""
    return {
        "run": run,
        "provider": provider,
        "model": model,
        "meta_model": model.meta_model,
        "source_model_id": item.model_id or item.name,
        "source_model_name": item.name or item.model_id,
        "source_model_type": item.source_model_type,
        "source_provider_name": item.model_source,
        "currency": item.currency or "",
        "billing_unit": item.billing_unit or "",
        "billing_mode": item.billing_mode or "",
        "normalized_price_rows": rows,
        "raw_price_info": item.raw_price_info,
        "raw_detail": item.raw_detail,
    }


def price_fingerprint(payload: dict) -> str:
    """Return a stable fingerprint for price-affecting collected fields."""
    price_payload = {
        "currency": payload.get("currency") or "",
        "billing_unit": payload.get("billing_unit") or "",
        "billing_mode": payload.get("billing_mode") or "",
        "normalized_price_rows": payload.get("normalized_price_rows") or [],
    }
    encoded = json.dumps(
        price_payload,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def create_collected_price_history(
    payload: dict,
    *,
    source: PriceCollectionSource,
    source_platform_id: str,
    previous: CollectedModelPriceSnapshot | None,
    price_hash: str,
) -> CollectedModelPriceHistory:
    """Insert a history row and close the previous current version."""
    now = timezone.now()
    CollectedModelPriceHistory.objects.filter(
        source=source,
        source_platform_id=source_platform_id,
        is_current=True,
    ).update(
        is_current=False,
        effective_to=now,
    )
    return CollectedModelPriceHistory.objects.create(
        source=source,
        run=payload["run"],
        provider=payload["provider"],
        model=payload["model"],
        meta_model=payload["meta_model"],
        source_platform_id=source_platform_id,
        source_model_id=payload["source_model_id"],
        source_model_name=payload["source_model_name"],
        source_model_type=payload["source_model_type"],
        source_provider_name=payload["source_provider_name"],
        currency=payload["currency"],
        billing_unit=payload["billing_unit"],
        billing_mode=payload["billing_mode"],
        normalized_price_rows=payload["normalized_price_rows"],
        raw_price_info=payload["raw_price_info"],
        raw_detail=payload["raw_detail"],
        price_fingerprint=price_hash,
        changed_fields=changed_fields(previous, payload),
        effective_from=now,
        is_current=True,
    )


def sync_model_price_items(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    model: LLMModel,
    provider: LLMProvider,
    source_url: str,
) -> list[ModelPriceItem]:
    """Persist normalized official price items for display and comparison."""
    payloads = model_price_item_payloads(
        item,
        source=source,
        model=model,
        provider=provider,
        source_url=source_url,
    )
    if not payloads:
        return []

    now = timezone.now()
    ModelPriceItem.objects.filter(
        model=model,
        source=source,
        is_current=True,
    ).update(is_current=False, effective_to=now)
    items = []
    for payload in payloads:
        fingerprint = model_price_item_fingerprint(payload)
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
        items.append(price_item)
    return items


def model_price_item_payloads(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    model: LLMModel,
    provider: LLMProvider,
    source_url: str,
) -> list[dict]:
    """Convert normalized source rows into durable price item payloads."""
    payloads = []
    for index, row in enumerate(item.price_rows):
        payloads.extend(
            price_item_payloads_from_row(
                item,
                row,
                source=source,
                model=model,
                provider=provider,
                source_url=source_url,
                row_index=index,
            )
        )
    return payloads


def price_item_payloads_from_row(
    item: CollectedModelPricing,
    row,
    *,
    source: PriceCollectionSource,
    model: LLMModel,
    provider: LLMProvider,
    source_url: str,
    row_index: int,
) -> list[dict]:
    """Convert one normalized row into one or more price item payloads."""
    values = row.values or {}
    common = {
        "provider": provider,
        "model": model,
        "meta_model": model.meta_model,
        "source": source,
        "currency": item.currency or source.currency or "USD",
        "source_url": source_url,
        "raw_payload": {
            "kind": row.kind,
            "values": values,
            "raw": row.raw,
            "row_index": row_index,
        },
    }

    if row.kind in {"text_token", "text_unit"}:
        return token_price_item_payloads(item, values, common)
    if row.kind == "image_token":
        return image_token_price_item_payloads(item, values, common)
    if row.kind in {"image_size", "image_unit"}:
        price = first_decimal_from_row(values, "unit_price", "price")
        spec = {}
        if values.get("image_size"):
            spec["size"] = values.get("image_size")
        return [
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_IMAGE,
                unit_price=price,
                spec=spec,
            )
        ] if price is not None else []
    if row.kind == "video_resolution_input":
        return video_resolution_input_payloads(values, common)
    if row.kind == "video_resolution_output":
        return video_resolution_output_payloads(values, common)
    if row.kind == "video_inference":
        return video_inference_payloads(values, common)
    if row.kind == "video_unit":
        price = first_decimal_from_row(values, "unit_price", "price")
        return [
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=price,
            )
        ] if price is not None else []
    return []


def token_price_item_payloads(
    item: CollectedModelPricing,
    values: dict,
    common: dict,
) -> list[dict]:
    """Build token input/output price item payloads."""
    payloads = []
    input_price = first_decimal_from_row(values, "input_price")
    output_price = first_decimal_from_row(
        values,
        "output_price",
        "output_non_thinking_price",
        "output_thinking_price",
    )
    cache_price = first_decimal_from_row(values, "cache_input_price")
    input_range = parse_price_range(values.get("input_token_range"))
    output_range = parse_price_range(values.get("output_token_range"))
    if input_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(input_price, item.unit),
                tier_start=input_range[0],
                tier_end=input_range[1],
            )
        )
    if output_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(output_price, item.unit),
                tier_start=output_range[0],
                tier_end=output_range[1],
            )
        )
    if cache_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(cache_price, item.unit),
                tier_start=input_range[0],
                tier_end=input_range[1],
            )
        )
    return payloads


def image_token_price_item_payloads(
    item: CollectedModelPricing,
    values: dict,
    common: dict,
) -> list[dict]:
    """Build image token input/output price item payloads."""
    payloads = []
    input_price = first_decimal_from_row(values, "input_price")
    image_input_price = first_decimal_from_row(values, "image_input_price")
    output_price = first_decimal_from_row(values, "output_price")
    image_output_price = first_decimal_from_row(values, "image_output_price")
    if input_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(input_price, item.unit),
            )
        )
    if image_input_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_IMAGE_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(image_input_price, item.unit),
            )
        )
    if output_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(output_price, item.unit),
            )
        )
    if image_output_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(image_output_price, item.unit),
            )
        )
    return payloads


def video_resolution_input_payloads(values: dict, common: dict) -> list[dict]:
    """Build video input price items for resolution-specific rows."""
    payloads = []
    spec = {}
    if values.get("resolution"):
        spec["resolution"] = values.get("resolution")
    contains_price = first_decimal_from_row(values, "contains_video_price")
    no_video_price = first_decimal_from_row(values, "no_video_price")
    if contains_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=contains_price,
                spec={**spec, "mode": "contains_video"},
            )
        )
    if no_video_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=no_video_price,
                spec={**spec, "mode": "no_video"},
            )
        )
    return payloads


def video_resolution_output_payloads(values: dict, common: dict) -> list[dict]:
    """Build video output price items for resolution-specific rows."""
    payloads = []
    spec = {}
    if values.get("resolution"):
        spec["resolution"] = values.get("resolution")
    price = first_decimal_from_row(values, "price")
    no_audio_price = first_decimal_from_row(values, "no_audio_price")
    if price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=price,
                spec={**spec, "audio": "included"},
            )
        )
    if no_audio_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=no_audio_price,
                spec={**spec, "audio": "excluded"},
            )
        )
    return payloads


def video_inference_payloads(values: dict, common: dict) -> list[dict]:
    """Build video inference price item payloads."""
    payloads = []
    spec = {}
    if values.get("inference_type"):
        spec["inference_type"] = values.get("inference_type")
    audible_price = first_decimal_from_row(values, "audible_price")
    silent_price = first_decimal_from_row(values, "silent_price")
    if audible_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=audible_price,
                spec={**spec, "audio": "included"},
            )
        )
    if silent_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                unit_price=silent_price,
                spec={**spec, "audio": "excluded"},
            )
        )
    return payloads


def price_item_payload(
    common: dict,
    *,
    dimension: str,
    billing_unit: str,
    unit_price: Decimal | None,
    spec: dict | None = None,
    tier_start: Decimal | None = None,
    tier_end: Decimal | None = None,
) -> dict:
    """Build one model price item payload."""
    tier_type = ModelPriceItem.TIER_FLAT
    if tier_start is not None or tier_end is not None:
        tier_type = ModelPriceItem.TIER_USAGE_RANGE
    return {
        **common,
        "dimension": dimension,
        "billing_unit": billing_unit,
        "unit_price": unit_price or Decimal("0"),
        "tier_type": tier_type,
        "tier_start": tier_start,
        "tier_end": tier_end,
        "spec": spec or {},
        "is_current": True,
    }


def parse_price_range(value) -> tuple[Decimal | None, Decimal | None]:
    """Parse a normalized token range string into start/end values."""
    text = str(value or "").strip()
    if not text or text in {"-", "不限"}:
        return None, None
    match = re.match(r"^([0-9.]+)\s*-\s*([0-9.]+)$", text)
    if not match:
        return None, None
    return to_decimal(match.group(1)), to_decimal(match.group(2))


def model_price_item_fingerprint(payload: dict) -> str:
    """Return a stable fingerprint for one normalized price item."""
    price_payload = {
        "source": payload.get("source").id if payload.get("source") else None,
        "dimension": payload["dimension"],
        "billing_unit": payload["billing_unit"],
        "currency": payload["currency"],
        "unit_price": str(payload["unit_price"]),
        "tier_type": payload["tier_type"],
        "tier_start": str(payload["tier_start"] or ""),
        "tier_end": str(payload["tier_end"] or ""),
        "spec": payload.get("spec") or {},
    }
    encoded = json.dumps(
        price_payload,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def changed_fields(
    previous: CollectedModelPriceSnapshot | None,
    payload: dict,
) -> list[str]:
    """Return collected fields changed from the previous snapshot."""
    if previous is None:
        return ["initial"]
    fields = [
        "currency",
        "billing_unit",
        "billing_mode",
        "normalized_price_rows",
    ]
    changed = []
    for field in fields:
        if getattr(previous, field) != payload[field]:
            changed.append(field)
    return changed


def model_defaults_from_collected_item(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    source_url: str,
) -> dict:
    """Build canonical model defaults from normalized collected pricing."""
    prices = prices_from_collected_item(item)
    return {
        "name": item.name or item.model_id,
        "modality": modality_from_source_type(item.source_model_type),
        "input_price_per_million": prices["input_price_per_million"],
        "output_price_per_million": prices["output_price_per_million"],
        "cache_input_price_per_million": prices[
            "cache_input_price_per_million"
        ],
        "image_output_price_per_image": prices[
            "image_output_price_per_image"
        ],
        "video_input_price_per_second": prices[
            "video_input_price_per_second"
        ],
        "video_output_price_per_second": prices[
            "video_output_price_per_second"
        ],
        "video_resolution_prices": prices["video_resolution_prices"],
        "currency": item.currency or "USD",
        "source": source,
        "source_url": source_url,
        "is_active": True,
        "last_price_updated_at": timezone.now(),
    }


def model_identity_defaults_from_collected_item(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    source_url: str,
) -> dict:
    """Build model defaults that do not promote collected prices."""
    return {
        "name": item.name or item.model_id,
        "modality": modality_from_source_type(item.source_model_type),
        "currency": item.currency or "USD",
        "source": source,
        "source_url": source_url,
        "is_active": True,
    }


def prices_from_collected_item(item: CollectedModelPricing) -> dict:
    """Extract calculator-friendly prices from normalized Yunce rows."""
    values = {
        "input_price_per_million": Decimal("0"),
        "output_price_per_million": Decimal("0"),
        "cache_input_price_per_million": None,
        "image_output_price_per_image": None,
        "video_input_price_per_second": None,
        "video_output_price_per_second": None,
        "video_resolution_prices": {},
    }

    text_pair = first_text_price_pair(item)
    if text_pair is not None:
        values["input_price_per_million"] = price_per_million(
            text_pair[0],
            item.unit,
        )
        values["output_price_per_million"] = price_per_million(
            text_pair[1],
            item.unit,
        )

    cache_price = first_decimal_value(item, "cache_input_price")
    if cache_price is not None:
        values["cache_input_price_per_million"] = price_per_million(
            cache_price,
            item.unit,
        )

    if item.source_model_type == "Image":
        image_pair = first_image_token_price_pair(item)
        if image_pair is not None:
            values["input_price_per_million"] = price_per_million(
                image_pair[0],
                item.unit,
            )
            values["output_price_per_million"] = price_per_million(
                image_pair[1],
                item.unit,
            )
        image_unit_price = first_image_unit_price(item)
        if image_unit_price is not None:
            values["image_output_price_per_image"] = image_unit_price

    if item.source_model_type == "Video":
        values.update(video_prices_from_rows(item))

    return values


def price_per_million(
    price: Decimal,
    unit: int | str | None,
) -> Decimal:
    """Convert a token price into a per-million-token price."""
    unit_value = to_decimal(unit) or Decimal("1000000")
    if unit_value <= 0:
        unit_value = Decimal("1000000")
    return price * Decimal("1000000") / unit_value


def ensure_yunce_source(*, base_url: str = DEFAULT_YUNCE_BASE_URL):
    """Ensure the default Yunce collection source exists."""
    source_url = base_url.replace("/admin/api", "/")
    source, _ = PriceCollectionSource.objects.get_or_create(
        slug="yunce",
        defaults={
            "name": "Yunce",
            "source_type": PriceCollectionSource.SOURCE_TYPE_YUNCE,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
            ),
            "endpoint_url": source_url,
            "currency": "USD",
            "is_enabled": True,
        },
    )
    return source


def ensure_official_source(*, provider: LLMProvider):
    """Ensure an official pricing source exists for a provider."""
    config = OFFICIAL_PROVIDER_CONFIGS[provider.code]
    source, created = PriceCollectionSource.objects.get_or_create(
        slug=f"{provider.code}-official",
        defaults={
            "provider": provider,
            "name": f"{provider.name} 官方价格",
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            "endpoint_url": config.source_url,
            "currency": config.currency,
            "is_enabled": True,
            "updates_model_prices": True,
            "notes": (
                "官方公开价格采集源；价格按官方币种入库，"
                "不做跨币种换算。"
            ),
        },
    )
    if created:
        return source

    changed_fields = []
    desired_fields = {
        "provider": provider,
        "name": f"{provider.name} 官方价格",
        "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
        "source_category": (
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ),
        "currency": config.currency,
        "updates_model_prices": True,
        "notes": (
            "官方公开价格采集源；价格按官方币种入库，"
            "不做跨币种换算。"
        ),
    }
    if not source.endpoint_url:
        desired_fields["endpoint_url"] = config.source_url
    for field, value in desired_fields.items():
        if getattr(source, field) != value:
            setattr(source, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        source.save(update_fields=changed_fields)
    return source


def first_text_price_pair(
    item: CollectedModelPricing,
) -> tuple[Decimal, Decimal] | None:
    """Return the first usable text input/output price pair."""
    for row in item.price_rows:
        input_price = to_decimal(row.values.get("input_price"))
        output_price = to_decimal(row.values.get("output_price"))
        if output_price is None:
            output_price = to_decimal(
                row.values.get("output_non_thinking_price")
            )
        if output_price is None:
            output_price = to_decimal(row.values.get("output_thinking_price"))
        if input_price is not None and output_price is not None:
            return input_price, output_price
    return None


def first_image_token_price_pair(
    item: CollectedModelPricing,
) -> tuple[Decimal, Decimal] | None:
    """Return the first usable image token input/output price pair."""
    for row in item.price_rows:
        input_price = to_decimal(row.values.get("input_price"))
        if input_price is None:
            input_price = to_decimal(row.values.get("image_input_price"))
        output_price = to_decimal(row.values.get("output_price"))
        if output_price is None:
            output_price = to_decimal(row.values.get("image_output_price"))
        if input_price is not None and output_price is not None:
            return input_price, output_price
    return None


def first_image_unit_price(item: CollectedModelPricing) -> Decimal | None:
    """Return the first per-image output price."""
    for row in item.price_rows:
        unit_price = to_decimal(row.values.get("unit_price"))
        if unit_price is None:
            unit_price = to_decimal(row.values.get("price"))
        if unit_price is not None:
            return unit_price
    return None


def video_prices_from_rows(item: CollectedModelPricing) -> dict:
    """Return video per-second and resolution prices from rows."""
    prices = {
        "video_input_price_per_second": None,
        "video_output_price_per_second": None,
        "video_resolution_prices": {},
    }
    resolution_prices = {}

    for row in item.price_rows:
        resolution = row.values.get("resolution")
        if resolution:
            resolution_prices[str(resolution)] = {
                "input": decimal_to_json_value(
                    first_decimal_from_row(
                        row.values,
                        "contains_video_price",
                        "no_video_price",
                    )
                ),
                "output": decimal_to_json_value(
                    first_decimal_from_row(
                        row.values,
                        "price",
                        "no_audio_price",
                    )
                ),
                "raw": row.values,
            }

        input_price = first_decimal_from_row(
            row.values,
            "contains_video_price",
            "audible_price",
        )
        output_price = first_decimal_from_row(
            row.values,
            "price",
            "audible_price",
            "silent_price",
        )
        if (
            prices["video_input_price_per_second"] is None
            and input_price is not None
        ):
            prices["video_input_price_per_second"] = input_price
        if (
            prices["video_output_price_per_second"] is None
            and output_price is not None
        ):
            prices["video_output_price_per_second"] = output_price

    prices["video_resolution_prices"] = resolution_prices
    return prices


def first_decimal_value(
    item: CollectedModelPricing,
    key: str,
) -> Decimal | None:
    """Return the first decimal value for a normalized row key."""
    for row in item.price_rows:
        value = to_decimal(row.values.get(key))
        if value is not None:
            return value
    return None


def first_decimal_from_row(
    values: dict,
    *keys: str,
) -> Decimal | None:
    """Return the first decimal value from a row dictionary."""
    for key in keys:
        value = to_decimal(values.get(key))
        if value is not None:
            return value
    return None


def decimal_to_json_value(value: Decimal | None):
    """Convert Decimal values to JSON-safe strings."""
    if value is None:
        return None
    return str(value)


def modality_from_source_type(source_model_type: str) -> str:
    """Map Yunce source model type to canonical model modality."""
    if source_model_type == "Text":
        return LLMModel.MODALITY_TEXT
    if source_model_type == "Video":
        return LLMModel.MODALITY_VIDEO
    return LLMModel.MODALITY_MULTIMODAL


def to_decimal(value) -> Decimal | None:
    """Parse a decimal from API values."""
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def slugify_provider(value: str) -> str:
    """Build a stable provider code from a provider label."""
    raw_value = str(value or "unknown").strip()
    normalized = raw_value.lower()
    normalized = normalized.replace(" ", "-").replace("_", "-")
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if normalized:
        return normalized
    digest = hashlib.sha1(raw_value.encode()).hexdigest()[:10]
    return f"provider-{digest}"
