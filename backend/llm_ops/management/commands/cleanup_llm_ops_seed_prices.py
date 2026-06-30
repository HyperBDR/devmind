"""Clean legacy LLM Ops seed and unintended official provider data."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from llm_ops.catalog_maintenance import (
    LEGACY_TEST_SOURCE_SLUGS,
    TREND_DEMO_SOURCE_SLUGS,
    UNCONFIRMED_PRICE_SOURCE_SLUGS,
    meta_model_has_business_links,
    model_ids_with_business_links,
)
from llm_ops.collection_services import prune_global_config_price_sources
from llm_ops.models import (
    ChannelModelPrice,
    ChannelPriceItem,
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ResaleListing,
)

DEFAULT_PROVIDER_CODES = ("aliyun-wanx", "baidu")


class Command(BaseCommand):
    """Remove provider data that should now be page-configured only."""

    help = (
        "Clean LLM Ops provider/model/source/price rows created by old "
        "seed/default official sync paths. Defaults to aliyun-wanx and "
        "baidu because those providers were previously pulled "
        "automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            action="append",
            dest="providers",
            help=(
                "Provider code to clean. Can be provided multiple times. "
                "Defaults to aliyun-wanx and baidu."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Only report what would be deleted.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            dest="confirm",
            help="Confirm the destructive cleanup.",
        )

    def handle(self, *args, **options):
        provider_codes = normalize_provider_codes(options.get("providers"))
        if not options.get("confirm") and not options.get("dry_run"):
            raise CommandError(
                "Refusing to clean without --yes. Pass --dry-run to "
                "preview the operation."
            )

        dry_run = options.get("dry_run")
        plan = build_cleanup_plan(provider_codes)
        stats = plan_stats(plan)
        stats["global_configs_pruned"] = 0
        stats["orphan_meta_models_deleted"] = 0

        if not dry_run:
            stats.update(execute_cleanup(plan))

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.WARNING(
                f"{prefix}llm_ops seed cleanup providers="
                f"{','.join(provider_codes)}: "
                f"providers={stats['providers']}, "
                f"sources={stats['sources']}, "
                f"models={stats['models']}, "
                f"models_deleted={stats['models_deleted']}, "
                f"models_detached={stats['models_detached']}, "
                f"model_price_items={stats['model_price_items']}, "
                f"snapshots={stats['snapshots']}, "
                f"history={stats['history']}, "
                f"runs={stats['runs']}, "
                f"channel_model_prices={stats['channel_model_prices']}, "
                f"channel_price_items={stats['channel_price_items']}, "
                f"resale_listings={stats['resale_listings']}, "
                f"orphan_meta_models_deleted="
                f"{stats['orphan_meta_models_deleted']}, "
                f"global_configs_pruned={stats['global_configs_pruned']}."
            )
        )


def normalize_provider_codes(values) -> tuple[str, ...]:
    """Return unique provider codes for the cleanup scope."""
    raw_values = values or DEFAULT_PROVIDER_CODES
    codes = []
    seen = set()
    for value in raw_values:
        code = str(value or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    if not codes:
        raise CommandError("Select at least one provider to clean.")
    return tuple(codes)


def build_cleanup_plan(
    provider_codes: tuple[str, ...],
) -> dict[str, list[int]]:
    """Collect row ids that belong to unwanted provider data."""
    provider_scope_ids = list(
        LLMProvider.objects.filter(code__in=provider_codes)
        .order_by("id")
        .values_list("id", flat=True)
    )
    source_ids = legacy_seed_source_ids(provider_codes, provider_scope_ids)
    model_ids = list(
        LLMModel.objects.filter(
            source_id__in=source_ids,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    meta_model_ids = list(
        MetaModel.objects.filter(
            Q(provider_prices__id__in=model_ids)
            | Q(price_items__source_id__in=source_ids)
        )
        .distinct()
        .order_by("id")
        .values_list("id", flat=True)
    )
    run_ids = list(
        PriceCollectionRun.objects.filter(
            source_id__in=source_ids,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    return {
        "provider_ids": [],
        "provider_scope_ids": provider_scope_ids,
        "source_ids": source_ids,
        "model_ids": model_ids,
        "meta_model_ids": meta_model_ids,
        "run_ids": run_ids,
    }


def legacy_seed_source_ids(
    provider_codes: tuple[str, ...],
    provider_ids: list[int],
) -> list[int]:
    """Return sources that match known legacy seed/default patterns."""
    legacy_slugs = set(LEGACY_TEST_SOURCE_SLUGS)
    legacy_slugs.update(TREND_DEMO_SOURCE_SLUGS)
    legacy_slugs.update(UNCONFIRMED_PRICE_SOURCE_SLUGS)
    legacy_slugs.update(f"{code}-sheet" for code in provider_codes)

    sources = PriceCollectionSource.objects.filter(
        Q(slug__in=legacy_slugs)
        | Q(slug__startswith="test-")
        | Q(name__startswith="测试")
        | Q(
            provider_id__in=provider_ids,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            slug__endswith="-official",
        )
    ).order_by("id")
    return [
        source.id
        for source in sources
        if source.slug in legacy_slugs
        or source.slug.startswith("test-")
        or source.name.startswith("测试")
        or is_legacy_model_official_source(source, provider_codes)
    ]


def is_legacy_model_official_source(
    source: PriceCollectionSource,
    provider_codes: tuple[str, ...],
) -> bool:
    """Return whether a source is an old per-model official source."""
    if (
        source.source_category
        != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return False
    slug = source.slug or ""
    for code in provider_codes:
        if slug == f"{code}-official":
            return False
        if slug.startswith(f"{code}-") and slug.endswith("-official"):
            return True
    return False


def plan_stats(plan: dict[str, list[int]]) -> dict[str, int]:
    """Return counts that will be affected by the cleanup plan."""
    source_ids = plan["source_ids"]
    model_ids = plan["model_ids"]
    provider_ids = plan["provider_ids"]
    linked_model_ids = model_ids_with_business_links(model_ids)
    return {
        "providers": len(provider_ids),
        "sources": len(source_ids),
        "models": len(model_ids),
        "models_deleted": len(model_ids) - len(linked_model_ids),
        "models_detached": len(linked_model_ids),
        "model_price_items": ModelPriceItem.objects.filter(
            Q(model_id__in=model_ids) | Q(source_id__in=source_ids)
        ).count(),
        "snapshots": CollectedModelPriceSnapshot.objects.filter(
            Q(source_id__in=source_ids) | Q(model_id__in=model_ids)
        ).count(),
        "history": CollectedModelPriceHistory.objects.filter(
            Q(source_id__in=source_ids) | Q(model_id__in=model_ids)
        ).count(),
        "runs": len(plan["run_ids"]),
        "channel_model_prices": ChannelModelPrice.objects.filter(
            model_id__in=model_ids,
        ).count(),
        "channel_price_items": ChannelPriceItem.objects.filter(
            model_id__in=model_ids,
        ).count(),
        "resale_listings": ResaleListing.objects.filter(
            model_id__in=model_ids,
        ).count(),
    }


def execute_cleanup(plan: dict[str, list[int]]) -> dict[str, int]:
    """Delete planned rows and prune now-unreferenced meta models."""
    stats = {}
    model_ids = plan["model_ids"]
    linked_model_ids = model_ids_with_business_links(model_ids)
    deletable_model_ids = [
        model_id for model_id in model_ids if model_id not in linked_model_ids
    ]
    with transaction.atomic():
        PriceCollectionRun.objects.filter(id__in=plan["run_ids"]).delete()
        CollectedModelPriceSnapshot.objects.filter(
            cleanup_relation_query(plan, deletable_model_ids),
        ).delete()
        CollectedModelPriceHistory.objects.filter(
            cleanup_relation_query(plan, deletable_model_ids),
        ).delete()
        ModelPriceItem.objects.filter(
            cleanup_relation_query(plan, deletable_model_ids),
        ).delete()
        LLMModel.objects.filter(id__in=deletable_model_ids).delete()
        detach_count = detach_cleanup_models(linked_model_ids)
        prune_count = prune_global_config_price_sources(plan["source_ids"])
        PriceCollectionSource.objects.filter(
            id__in=plan["source_ids"],
        ).delete()
        orphan_count = delete_orphan_meta_models(plan["meta_model_ids"])
        stats["models_deleted"] = len(deletable_model_ids)
        stats["models_detached"] = detach_count
        stats["global_configs_pruned"] = prune_count
        stats["orphan_meta_models_deleted"] = orphan_count
    return stats


def cleanup_relation_query(
    plan: dict[str, list[int]],
    deletable_model_ids: list[int] | None = None,
) -> Q:
    """Return relation filters shared by cleanup-owned rows."""
    if deletable_model_ids is None:
        model_ids = plan["model_ids"]
    else:
        model_ids = deletable_model_ids
    return Q(source_id__in=plan["source_ids"]) | Q(model_id__in=model_ids)


def detach_cleanup_models(model_ids: set[int]) -> int:
    """Detach legacy cleanup models that have downstream business rows."""
    if not model_ids:
        return 0
    return LLMModel.objects.filter(id__in=model_ids).update(
        source=None,
        source_url="",
        price_role=LLMModel.PRICE_ROLE_UNKNOWN,
        input_price_per_million=0,
        output_price_per_million=0,
        cache_input_price_per_million=None,
        image_output_price_per_image=None,
        audio_input_price_per_second=None,
        audio_output_price_per_second=None,
        video_input_price_per_second=None,
        video_output_price_per_second=None,
        video_resolution_prices={},
        last_price_updated_at=None,
    )


def delete_orphan_meta_models(meta_model_ids: list[int]) -> int:
    """Delete candidate meta models after provider cleanup if unused."""
    deleted = 0
    for meta_model in MetaModel.objects.filter(id__in=meta_model_ids):
        if meta_model_has_business_links(meta_model):
            continue
        meta_model.delete()
        deleted += 1
    return deleted
