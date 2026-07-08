"""Maintenance helpers for LLM Ops catalog normalization and cleanup."""

from __future__ import annotations

from django.db.models import Q

from .constants import (
    SUPPLIER_SOURCE_OWNER_ALIASES,
    canonical_meta_model_identity,
    meta_model_owner_payload,
    resolve_meta_model_owner_fields,
)
from .models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    UsageReconciliationRecord,
)
from .services import stable_fingerprint

REAL_RESOURCE_CHANNEL_CODE = "real-resource-platform"
YUNCE_SUPPLIER_CHANNEL_CODE = "yunce-supplier-platform"
DEMO_BASELINE_SUPPLIER_CHANNEL_CODE = "demo-baseline-supplier"
MOCK_SUPPLIER_CHANNEL_CODES = (
    YUNCE_SUPPLIER_CHANNEL_CODE,
    DEMO_BASELINE_SUPPLIER_CHANNEL_CODE,
    "demo-premium-supplier",
    "demo-backup-supplier",
)
LEGACY_TEST_SOURCE_SLUGS = (
    "real-resource-platform-supplier",
    "test-02-supplier",
    "cc-supplier",
)
UNCONFIRMED_PRICE_SOURCE_SLUGS = (
    "anthropic-sheet",
    "google-sheet",
    "openai-sheet",
    "aliyun-wanx-sheet",
)
TREND_DEMO_SOURCE_SLUGS = (
    f"{REAL_RESOURCE_CHANNEL_CODE}-trend-demo",
    f"{DEMO_BASELINE_SUPPLIER_CHANNEL_CODE}-trend-demo",
    "demo-premium-supplier-trend-demo",
    "demo-backup-supplier-trend-demo",
)
TREND_DEMO_HISTORY_POINTS = {
    DEMO_BASELINE_SUPPLIER_CHANNEL_CODE: (
        ("2026-01-01", "0.150000", "0.600000"),
        ("2026-02-01", "0.145000", "0.570000"),
        ("2026-03-01", "0.138000", "0.540000"),
        ("2026-04-01", "0.132000", "0.520000"),
        ("2026-05-01", "0.128000", "0.500000"),
    ),
    "demo-premium-supplier": (
        ("2026-01-01", "0.165000", "0.640000"),
        ("2026-02-01", "0.152000", "0.590000"),
        ("2026-03-01", "0.130000", "0.505000"),
        ("2026-04-01", "0.118000", "0.470000"),
        ("2026-05-01", "0.112000", "0.450000"),
    ),
    "demo-backup-supplier": (
        ("2026-01-01", "0.120000", "0.700000"),
        ("2026-02-01", "0.118000", "0.665000"),
        ("2026-03-01", "0.140000", "0.610000"),
        ("2026-04-01", "0.155000", "0.580000"),
        ("2026-05-01", "0.160000", "0.560000"),
    ),
}


def clean_legacy_llm_ops_demo_data() -> dict[str, int]:
    """Remove deterministic legacy mock/demo rows."""
    stats = {
        "model_price_items": 0,
        "channel_price_items": 0,
        "channel_model_prices": 0,
        "channel_model_histories": 0,
        "resale_listings": 0,
        "resale_listing_histories": 0,
        "sources": 0,
        "channels": 0,
    }
    source_ids = list(
        PriceCollectionSource.objects.filter(
            Q(slug__startswith="yunce-")
            | Q(slug__in=TREND_DEMO_SOURCE_SLUGS)
            | Q(slug__in=LEGACY_TEST_SOURCE_SLUGS)
            | Q(slug__in=UNCONFIRMED_PRICE_SOURCE_SLUGS)
            | Q(slug__startswith="test-")
            | Q(name__startswith="测试")
        ).values_list("id", flat=True)
    )
    test_channel_price_filter = (
        Q(channel__code=REAL_RESOURCE_CHANNEL_CODE)
        | Q(channel__code__in=MOCK_SUPPLIER_CHANNEL_CODES)
        | Q(channel__code__startswith="test-")
        | Q(channel__name__startswith="测试")
    )
    test_channel_ids = list(
        ProcurementChannel.objects.filter(
            Q(code=REAL_RESOURCE_CHANNEL_CODE)
            | Q(code__in=MOCK_SUPPLIER_CHANNEL_CODES)
            | Q(code__startswith="test-")
        ).values_list("id", flat=True)
    )
    PriceCollectionSource.objects.filter(
        channel__code=REAL_RESOURCE_CHANNEL_CODE,
    ).update(channel=None)
    stats["model_price_items"] += _delete_count(
        ModelPriceItem.objects.filter(
            Q(source_id__in=source_ids) | Q(spec__mock_source="yunce_supplier")
        )
    )
    stats["channel_price_items"] += _delete_count(
        ChannelPriceItem.objects.filter(
            Q(source_id__in=source_ids)
            | Q(channel__code__startswith="test-")
            | Q(channel__name__startswith="测试")
        )
    )
    stats["channel_model_prices"] += _delete_count(
        ChannelModelPrice.objects.filter(test_channel_price_filter)
    )
    stats["channel_model_histories"] += _delete_count(
        ChannelModelPriceHistory.objects.filter(
            price_fingerprint__in=trend_demo_history_fingerprints(),
        )
    )
    stats["resale_listing_histories"] += _delete_count(
        ResaleListingPriceHistory.objects.filter(
            channel_id__in=test_channel_ids,
        )
    )
    stats["resale_listings"] += _delete_count(
        ResaleListing.objects.filter(channel_id__in=test_channel_ids)
    )
    stats["sources"] += _delete_count(
        PriceCollectionSource.objects.filter(id__in=source_ids)
    )
    stats["channels"] += _delete_count(
        ProcurementChannel.objects.filter(
            Q(code=REAL_RESOURCE_CHANNEL_CODE)
            | Q(code__in=MOCK_SUPPLIER_CHANNEL_CODES)
            | Q(code__startswith="test-")
        )
    )
    return stats


def resolve_orphan_meta_models() -> dict[str, int]:
    """Backfill canonical owner on every meta model that has none."""
    stats = {
        "resolved": 0,
        "unresolved": 0,
    }
    for meta in MetaModel.objects.filter(owner_code=""):
        owner = meta_model_owner_payload(meta.code)
        if not owner["owner_code"]:
            stats["unresolved"] += 1
            continue
        for field_name, value in owner.items():
            setattr(meta, field_name, value)
        meta.save(update_fields=[*owner.keys(), "updated_at"])
        stats["resolved"] += 1
    return stats


def normalize_meta_model_catalog() -> dict[str, int]:
    """Merge release/date meta-model rows into family-level rows."""
    stats = {
        "normalized": 0,
        "merged": 0,
        "linked_records": 0,
    }
    for meta in list(MetaModel.objects.all()):
        if not is_models_dev_meta_model(meta):
            continue
        identity = canonical_meta_model_identity(meta.code, meta.name)
        canonical_code = identity["code"]
        canonical_name = identity["name"]
        if meta.code == canonical_code:
            changed_fields = []
            aliases = merged_meta_aliases(meta, identity)
            if aliases != list(meta.aliases or []):
                meta.aliases = aliases
                changed_fields.append("aliases")
            owner = resolve_meta_model_owner_fields(meta)
            for field_name, value in owner.items():
                if getattr(meta, field_name) != value:
                    setattr(meta, field_name, value)
                    changed_fields.append(field_name)
            if changed_fields:
                meta.save(update_fields=[*changed_fields, "updated_at"])
                stats["normalized"] += 1
            continue
        canonical = MetaModel.objects.filter(code=canonical_code).first()
        if canonical is not None and not is_models_dev_meta_model(canonical):
            continue
        if canonical is None:
            meta.code = canonical_code
            meta.name = canonical_name
            meta.aliases = merged_meta_aliases(meta, identity)
            owner = meta_model_owner_payload(canonical_code)
            for field_name, value in owner.items():
                setattr(meta, field_name, value)
            meta.save(
                update_fields=[
                    "code",
                    "name",
                    "aliases",
                    *owner.keys(),
                    "updated_at",
                ],
            )
            stats["normalized"] += 1
            continue
        merge_meta_model_rows(canonical, meta, identity)
        stats["merged"] += 1
    stats["linked_records"] = normalize_model_linked_meta_models()
    return stats


def is_models_dev_meta_model(meta_model: MetaModel) -> bool:
    """Return whether a meta model is managed by models.dev sync."""
    return bool((meta_model.metadata or {}).get("models_dev"))


def normalize_model_linked_meta_models() -> int:
    """Align every model-linked row with its model's canonical meta model."""
    total = 0
    model_linked_types = (
        ModelPriceItem,
        ChannelModelPrice,
        ChannelPriceItem,
        ChannelModelPriceHistory,
        CollectedModelPriceSnapshot,
        CollectedModelPriceHistory,
        ResaleListing,
        ResaleListingExclusion,
        ResaleListingPriceHistory,
        UsageReconciliationRecord,
    )
    for model in LLMModel.objects.select_related("meta_model").all():
        for model_type in model_linked_types:
            total += (
                model_type.objects.filter(
                    model=model,
                )
                .exclude(
                    meta_model=model.meta_model,
                )
                .update(
                    meta_model=model.meta_model,
                )
            )
    return total


def merged_meta_aliases(meta: MetaModel, identity: dict) -> list[str]:
    """Return de-duplicated aliases for a normalized meta model."""
    aliases = list(meta.aliases or [])
    for token in (meta.code, meta.name, *identity["aliases"]):
        if token and token not in {identity["code"], identity["name"]}:
            if token not in aliases:
                aliases.append(token)
    return aliases


def merge_meta_model_rows(
    canonical: MetaModel,
    duplicate: MetaModel,
    identity: dict,
) -> None:
    """Move duplicate meta-model references onto the canonical row."""
    aliases = merged_meta_aliases(canonical, identity)
    for token in (duplicate.code, duplicate.name, *(duplicate.aliases or [])):
        if token and token not in {canonical.code, canonical.name}:
            if token not in aliases:
                aliases.append(token)
    changed_fields = []
    if aliases != list(canonical.aliases or []):
        canonical.aliases = aliases
        changed_fields.append("aliases")
    if duplicate.context_window > canonical.context_window:
        canonical.context_window = duplicate.context_window
        changed_fields.append("context_window")
    if duplicate.max_output_tokens > canonical.max_output_tokens:
        canonical.max_output_tokens = duplicate.max_output_tokens
        changed_fields.append("max_output_tokens")
    capabilities = merged_meta_capabilities(canonical, duplicate)
    if capabilities != dict(canonical.capabilities or {}):
        canonical.capabilities = capabilities
        changed_fields.append("capabilities")
    metadata = merged_meta_metadata(canonical, duplicate)
    if metadata != dict(canonical.metadata or {}):
        canonical.metadata = metadata
        changed_fields.append("metadata")
    if not canonical.owner_code and duplicate.owner_code:
        canonical.owner_code = duplicate.owner_code
        canonical.owner_name = duplicate.owner_name
        canonical.owner_website = duplicate.owner_website
        changed_fields += ["owner_code", "owner_name", "owner_website"]
    if changed_fields:
        changed_fields.append("updated_at")
        canonical.save(update_fields=changed_fields)
    for relation in MetaModel._meta.related_objects:
        field = relation.field
        relation.related_model.objects.filter(
            **{field.name: duplicate}
        ).update(**{field.name: canonical})
    duplicate.delete()


def merged_meta_capabilities(
    canonical: MetaModel,
    duplicate: MetaModel,
) -> dict:
    """Return canonical capabilities enriched from a duplicate row."""
    capabilities = dict(canonical.capabilities or {})
    duplicate_capabilities = dict(duplicate.capabilities or {})
    for key, value in duplicate_capabilities.items():
        if key == "features":
            existing_features = capabilities.get("features") or []
            duplicate_features = value or []
            capabilities["features"] = list(
                dict.fromkeys([*existing_features, *duplicate_features])
            )
            continue
        if key not in capabilities:
            capabilities[key] = value
    return capabilities


def merged_meta_metadata(
    canonical: MetaModel,
    duplicate: MetaModel,
) -> dict:
    """Return canonical metadata enriched without replacing models.dev."""
    metadata = dict(canonical.metadata or {})
    duplicate_metadata = dict(duplicate.metadata or {})
    duplicate_models_dev = duplicate_metadata.get("models_dev")
    canonical_models_dev = metadata.get("models_dev")
    if duplicate_models_dev and duplicate_models_dev != canonical_models_dev:
        merged_rows = list(metadata.get("merged_models_dev") or [])
        if duplicate_models_dev not in merged_rows:
            merged_rows.append(duplicate_models_dev)
            metadata["merged_models_dev"] = merged_rows
    for key, value in duplicate_metadata.items():
        if key == "models_dev":
            continue
        if key not in metadata:
            metadata[key] = value
    return metadata


def cleanup_orphan_meta_models() -> dict[str, int]:
    """Remove meta models that no canonical price row references."""
    return cleanup_orphan_meta_models_for_reset(dry_run=False)


def cleanup_orphan_meta_models_for_reset(
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Remove or preview meta models that no canonical model references."""
    stats = {
        "meta_models_owner_updated": 0,
        "meta_models_deleted": 0,
    }
    orphan_ids = []
    for meta in MetaModel.objects.all():
        owner = resolve_meta_model_owner_fields(meta)
        owner_changed = any(
            getattr(meta, field_name) != value
            for field_name, value in owner.items()
        )
        if owner_changed:
            if not dry_run:
                for field_name, value in owner.items():
                    setattr(meta, field_name, value)
                meta.save(update_fields=[*owner.keys(), "updated_at"])
            stats["meta_models_owner_updated"] += 1
        if not meta.provider_prices.exists():
            orphan_ids.append(meta.id)
    if orphan_ids:
        if dry_run:
            stats["meta_models_deleted"] = len(orphan_ids)
        else:
            stats["meta_models_deleted"] = MetaModel.objects.filter(
                id__in=orphan_ids,
            ).delete()[0]
    return stats


MODEL_BUSINESS_LINK_MODELS = (
    ("channel_model_prices", ChannelModelPrice),
    ("channel_price_items", ChannelPriceItem),
    ("channel_model_histories", ChannelModelPriceHistory),
    ("resale_listings", ResaleListing),
    ("resale_listing_exclusions", ResaleListingExclusion),
    ("resale_listing_histories", ResaleListingPriceHistory),
    ("usage_reconciliation_records", UsageReconciliationRecord),
)


def model_business_link_counts(model_ids: list[int]) -> dict[str, int]:
    """Return downstream business references for model ids."""
    if not model_ids:
        return {}
    counts = {}
    for key, model_type in MODEL_BUSINESS_LINK_MODELS:
        count = model_type.objects.filter(model_id__in=model_ids).count()
        if count:
            counts[key] = count
    return counts


def model_ids_with_business_links(model_ids: list[int]) -> set[int]:
    """Return model ids referenced by downstream business rows."""
    linked_ids: set[int] = set()
    if not model_ids:
        return linked_ids
    for _, model_type in MODEL_BUSINESS_LINK_MODELS:
        linked_ids.update(
            model_type.objects.filter(model_id__in=model_ids)
            .values_list("model_id", flat=True)
            .distinct()
        )
    return linked_ids


def model_delete_dependency_counts(model: LLMModel) -> dict[str, int]:
    """Return dependencies that make direct model deletion unsafe."""
    counts = model_business_link_counts([model.id])
    price_items = ModelPriceItem.objects.filter(model=model).count()
    if price_items:
        counts["model_price_items"] = price_items
    return counts


def meta_model_dependency_counts(meta_model: MetaModel) -> dict[str, int]:
    """Return dependencies that make direct meta-model deletion unsafe."""
    counts = {}
    for relation in MetaModel._meta.related_objects:
        if relation.related_model is MetaModel:
            continue
        count = relation.related_model.objects.filter(
            **{relation.field.name: meta_model},
        ).count()
        if count:
            counts[relation.get_accessor_name()] = count
    return counts


def meta_model_has_business_links(meta_model: MetaModel) -> bool:
    """Return whether a meta model is still referenced by another table."""
    return bool(meta_model_dependency_counts(meta_model))


def reset_meta_models_canonical() -> dict[str, int]:
    """Wipe meta models without repopulating replacement data."""
    stats = {
        "manual_sources_kept": 0,
        "supplier_sources_kept": 0,
        "meta_models_deleted": 0,
    }
    stats["manual_sources_kept"] = PriceCollectionSource.objects.filter(
        source_category=(PriceCollectionSource.SOURCE_CATEGORY_MANUAL),
    ).count()
    stats["supplier_sources_kept"] = PriceCollectionSource.objects.filter(
        source_category=(PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER),
    ).count()
    PriceCollectionSource.objects.filter(
        channel__code=REAL_RESOURCE_CHANNEL_CODE,
    ).delete()
    stats["meta_models_deleted"] = MetaModel.objects.all().delete()[0]
    for supplier_code in SUPPLIER_SOURCE_OWNER_ALIASES.keys():
        LLMProvider.objects.filter(code=supplier_code).delete()
    return stats


def is_llm_ops_database_empty() -> bool:
    """Return True when no llm_ops canonical rows exist yet."""
    if LLMProvider.objects.exists():
        return False
    if LLMModel.objects.exists():
        return False
    return True


def trend_demo_history_fingerprints() -> tuple[str, ...]:
    """Return fingerprints generated by the old trend demo seed."""
    fingerprints = []
    for points in TREND_DEMO_HISTORY_POINTS.values():
        for date_text, input_price, output_price in points:
            fingerprints.append(
                stable_fingerprint(
                    {
                        "is_listed": True,
                        "input_price_per_million": str(input_price),
                        "output_price_per_million": str(output_price),
                        "currency": "USD",
                        "effective_from": date_text,
                    }
                )
            )
    return tuple(fingerprints)


def _delete_count(queryset) -> int:
    """Delete a queryset and return the number of rows deleted."""
    count = queryset.count()
    if count:
        queryset.delete()
    return count
