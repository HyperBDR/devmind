from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .collectors import CollectedModelPricing, CollectedPricingCatalog
from .collectors.official import (
    ALIYUN_LEGACY_PRICING_SOURCE_URLS,
    BAIDU_PRICING_SOURCE_URL,
    MINIMAX_LEGACY_PRICING_SOURCE_URLS,
    MINIMAX_PRICING_SOURCE_URL,
    MODELS_DEV_MODELS_URL,
    OFFICIAL_PROVIDER_CONFIGS,
    VOLCENGINE_PRICING_SOURCE_URL,
    ZHIPU_PRICING_SOURCE_URL,
    collect_official_pricing_catalog,
    fetch_source_payload,
    normalize_model_code,
)
from .collectors.yunce import DEFAULT_YUNCE_BASE_URL, YuncePricingClient
from .constants import canonical_meta_model_identity
from .models import (
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMOpsGlobalConfig,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    ModelSku,
    PriceCollectionRun,
    PriceCollectionSource,
    SourceSkuOffering,
)
from .price_collectors import (
    collect_vendor_price_catalog,
    registered_vendor_price_collector_codes,
    vendor_price_collector_exists,
)
from .services import (
    find_aggregated_model,
    match_meta_model_by_alias_or_name,
    normalize_currency,
    price_role_for_source,
    source_owner_type_for_source,
    sync_dependent_channel_price_items_for_price_items,
    update_aggregated_model_identity,
)
from .skill_runner import (
    run_vendor_pricing_skill,
    standard_catalog_run_metadata,
    standard_catalog_to_collected_catalog,
    vendor_pricing_skill_exists,
)

logger = logging.getLogger(__name__)

SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES = tuple(
    code
    for code in registered_vendor_price_collector_codes()
    if code in OFFICIAL_PROVIDER_CONFIGS
)
MANUAL_OFFICIAL_SOURCE_PROVIDER_CODES: tuple[str, ...] = ()
SUPPORTED_OFFICIAL_SOURCE_PROVIDER_CODES = tuple(
    sorted(
        {
            *SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES,
            *MANUAL_OFFICIAL_SOURCE_PROVIDER_CODES,
        }
    )
)
DEFAULT_OFFICIAL_PRICE_SYNC_PROVIDER_CODES: tuple[str, ...] = ()
AZURE_OPENAI_PRICING_SOURCE_URL = (
    "https://azure.microsoft.com/en-us/pricing/details/"
    "azure-openai/#pricing"
)
FULL_CATALOG_PROVIDER_CODES = (
    "aliyun",
    "baidu",
    "volcengine",
)
DEFAULT_MODELS_DEV_SYNC_TIMEOUT = 60
MODELS_DEV_RESPONSE_CACHE_KEY = "llm_ops:models_dev:last_success_payload"
CLOUD_PROVIDER_OFFICIAL_CODES = {
    "aliyun",
    "aliyun-wanx",
    "azure-openai",
    "baidu",
    "volcengine",
}

OFFICIAL_SOURCE_PROVIDER_DEFAULTS = {
    "aliyun": {
        "name": "阿里云",
        "website": "https://dashscope.aliyuncs.com/",
        "notes": "模型价格源厂商。",
    },
    "aliyun-wanx": {
        "name": "阿里云万象",
        "website": "https://dashscope.aliyuncs.com/",
        "notes": "模型价格源厂商。",
    },
    "baidu": {
        "name": "百度千帆",
        "website": "https://cloud.baidu.com/",
        "notes": "模型价格源厂商。",
        "source_name": "百度千帆官方价格",
        "source_url": BAIDU_PRICING_SOURCE_URL,
        "currency": "CNY",
    },
    "volcengine": {
        "name": "火山方舟",
        "website": "https://ark.cn-beijing.volces.com/",
        "notes": "模型价格源厂商。",
        "source_name": "火山方舟官方价格",
        "source_url": VOLCENGINE_PRICING_SOURCE_URL,
        "currency": "CNY",
    },
    "anthropic": {
        "name": "Anthropic",
        "website": "https://anthropic.com/",
        "notes": "模型价格源厂商。",
        "source_name": "Anthropic 官方价格",
        "source_url": (
            "https://docs.anthropic.com/en/docs/about-claude/pricing"
        ),
        "currency": "USD",
    },
    "azure-openai": {
        "name": "Azure OpenAI",
        "website": (
            "https://azure.microsoft.com/en-us/products/"
            "ai-services/openai-service"
        ),
        "notes": "云厂商托管 OpenAI 模型的官方价格源。",
        "source_name": "Azure OpenAI 官方价格",
        "source_url": AZURE_OPENAI_PRICING_SOURCE_URL,
        "currency": "USD",
    },
    "google": {
        "name": "Google",
        "website": "https://ai.google.dev/",
        "notes": "模型价格源厂商。",
        "source_name": "Google Gemini 官方价格",
        "source_url": (
            "https://cloud.google.com/gemini-enterprise-agent-platform/"
            "generative-ai/pricing?hl=en"
        ),
        "currency": "USD",
    },
    "minimax": {
        "name": "MiniMax",
        "website": "https://api.minimax.io/",
        "notes": "模型价格源厂商。",
        "source_name": "MiniMax 官方价格",
        "source_url": MINIMAX_PRICING_SOURCE_URL,
        "currency": "CNY",
    },
    "zhipu": {
        "name": "智谱",
        "website": "https://open.bigmodel.cn/",
        "notes": "模型价格源厂商。",
        "source_name": "智谱 BigModel 官方价格",
        "source_url": ZHIPU_PRICING_SOURCE_URL,
        "currency": "CNY",
    },
}

AUTO_SYNC_SOURCE_DEFAULTS = {
    "siliconflow": {
        "name": "硅基流动",
        "source_name": "硅基流动价格页",
        "source_slug": "siliconflow-pricing",
        "source_url": "https://siliconflow.cn/pricing",
        "currency": "CNY",
        "source_category": PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        "source_owner_type": PriceCollectionSource.SOURCE_OWNER_SUPPLIER,
        "collection_method": (
            PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
        ),
    },
}

MODELS_DEV_META_SOURCE_PROVIDERS = {
    "alibaba",
    "alibaba-cn",
    "anthropic",
    "cohere",
    "deepseek",
    "google",
    "llama",
    "minimax",
    "minimax-cn",
    "mistral",
    "moonshotai",
    "moonshotai-cn",
    "novita-ai",
    "openai",
    "perplexity",
    "stepfun",
    "stepfun-ai",
    "tencent-tokenhub",
    "xai",
    "xiaomi",
    "zai",
    "zhipuai",
}
MODELS_DEV_CLEANUP_MIN_RETAIN_COUNT = 10
MODELS_DEV_CLEANUP_MAX_DROP_PERCENT = 30

MODELS_DEV_LAB_OWNER_DEFAULTS = {
    "alibaba": ("alibaba", "阿里巴巴", "https://www.alibaba.com/"),
    "anthropic": ("anthropic", "Anthropic", "https://anthropic.com/"),
    "cohere": ("cohere", "Cohere", "https://cohere.com/"),
    "deepreinforce": (
        "deepreinforce",
        "Deepreinforce",
        "https://deepreinforce.ai/",
    ),
    "deepseek": ("deepseek", "DeepSeek", "https://api.deepseek.com/"),
    "google": ("google", "Google", "https://ai.google.dev/"),
    "meta": ("meta", "Meta", "https://ai.meta.com/"),
    "microsoft": ("microsoft", "Microsoft", "https://microsoft.ai/"),
    "minimax": ("minimax", "MiniMax", "https://api.minimax.io/"),
    "mistral": ("mistral", "Mistral AI", "https://mistral.ai/"),
    "moonshotai": (
        "kimi",
        "Kimi（月之暗面）",
        "https://api.moonshot.cn/",
    ),
    "nvidia": ("nvidia", "NVIDIA", "https://www.nvidia.com/"),
    "openai": ("openai", "OpenAI", "https://api.openai.com/"),
    "perplexity": (
        "perplexity",
        "Perplexity",
        "https://www.perplexity.ai/",
    ),
    "sakana": ("sakana", "Sakana AI", "https://sakana.ai/"),
    "sarvam": ("sarvam", "Sarvam AI", "https://www.sarvam.ai/"),
    "stepfun": ("stepfun", "阶跃星辰", "https://www.stepfun.com/"),
    "tencent": ("tencent", "腾讯混元", "https://hunyuan.tencent.com/"),
    "xai": ("xai", "xAI", "https://x.ai/api"),
    "xiaomi": ("xiaomi", "Xiaomi", "https://www.mi.com/"),
    "zhipuai": ("zhipu", "智谱", "https://open.bigmodel.cn/"),
}

MODELS_DEV_LOGO_ASSET_PREFIX = "/src/assets/provider-icons/models-dev"


def source_owner_type_for_provider(provider: LLMProvider) -> str:
    """Return the publisher type for provider official price sources."""
    if str(provider.code or "").lower() in CLOUD_PROVIDER_OFFICIAL_CODES:
        return PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
    return PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL


def source_owner_type_for_provider_code(provider_code: str) -> str:
    """Return the publisher type for one official provider code."""
    if str(provider_code or "").lower() in CLOUD_PROVIDER_OFFICIAL_CODES:
        return PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
    return PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL


CACHE_INPUT_PRICE_KEYS = (
    "cache_input_price",
    "cache_read",
    "cache_read_price",
    "cache_hit",
    "cache_hit_price",
    "cache_hit_input",
    "cache_hit_input_price",
    "cache_hit_tokens",
    "cache_hits",
    "cache_hits_price",
    "cache_hits_input",
    "cache_hits_input_price",
    "cached_input",
    "cached_input_price",
    "cached_input_tokens",
    "cached_token",
    "cached_tokens",
    "cached_tokens_price",
    "cache_read_input",
    "cache_read_input_price",
    "cache_read_tokens",
    "input_cache_read",
    "input_cache_hit",
    "input_cache_hits",
    "input_cached",
    "input_cached_price",
    "hit_cache",
)


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
) -> dict[str, int | list[str]]:
    """Fetch Yunce pricing and persist model prices plus snapshots."""
    source = source or ensure_yunce_source(base_url=base_url)
    if not source.is_enabled:
        raise ValueError("Price collection source is disabled.")
    base_url = resolve_collection_base_url(source=source, base_url=base_url)
    run = PriceCollectionRun.objects.create(source=source)
    active_offering_ids: set[int] = set()
    stats = {
        "models": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped_model_codes": [],
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

                upsert_result = upsert_collected_offering(
                    item,
                    source=source,
                    source_url=catalog.source_url,
                )
                if upsert_result is None:
                    stats["skipped"] += 1
                    stats["skipped_model_codes"].append(
                        collected_model_code(item),
                    )
                    continue
                offering, created = upsert_result
                _, changed = upsert_collected_snapshot(
                    item,
                    source=source,
                    run=run,
                    offering=offering,
                )
                sync_model_price_items(
                    item,
                    source=source,
                    offering=offering,
                    source_url=catalog.source_url,
                )
                active_offering_ids.add(offering.id)
                stats["models"] += 1
                stats["created" if created else "updated"] += 1
                stats["changed" if changed else "unchanged"] += 1

            stale_stats = close_stale_current_collected_prices(
                source=source,
                active_offering_ids=active_offering_ids,
            )
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
                "skipped_model_codes": sorted(
                    set(stats["skipped_model_codes"]),
                ),
                "closed_stale_price_items": stale_stats["price_items"],
                "closed_stale_history": stale_stats["history"],
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


def sync_vendor_price_source_catalog(
    *,
    provider_code: str,
    source: PriceCollectionSource,
    verify_source: bool = True,
) -> dict[str, int | list[str]]:
    """Collect an auto price source through a registered adapter."""
    if not source.is_enabled:
        raise ValueError("Price collection source is disabled.")
    source_url = source.endpoint_url or ""
    if (
        provider_code in OFFICIAL_PROVIDER_CONFIGS
        and is_legacy_official_pricing_url(provider_code, source_url)
    ):
        source_url = OFFICIAL_PROVIDER_CONFIGS[provider_code].source_url
        source.endpoint_url = source_url
        source.save(update_fields=["endpoint_url", "updated_at"])
    provider_name = (
        source.provider.name
        if source.provider_id and source.provider
        else source.name
    )
    run = PriceCollectionRun.objects.create(source=source)
    active_offering_ids: set[int] = set()
    stats = {
        "models": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped_model_codes": [],
    }
    try:
        vendor_payload = {
            "provider_name": provider_name,
            "currency": source.currency or "CNY",
            "source_url": source_url,
            "model_codes": [],
            "verify_source": verify_source,
        }
        if not vendor_price_collector_exists(provider_code):
            raise ValueError(
                "Vendor price catalog collector not found for provider "
                f"'{provider_code}'."
            )
        standard_catalog = collect_vendor_price_catalog(
            provider_code,
            vendor_payload,
        )
        if not standard_catalog.get("models"):
            raise ValueError(
                "Vendor price catalog collector returned no models for "
                f"provider '{provider_code}'."
            )
        catalog = standard_catalog_to_collected_catalog(standard_catalog)
        with transaction.atomic():
            for item in catalog.models:
                model_code = collected_model_code(item)
                meta_model = existing_meta_model_for_collected_item(item)
                if meta_model is None:
                    stats["skipped"] += 1
                    stats["skipped_model_codes"].append(model_code)
                    continue
                upsert_result = upsert_collected_offering(
                    item,
                    source=source,
                    source_url=catalog.source_url,
                    meta_model=meta_model,
                )
                if upsert_result is None:
                    stats["skipped"] += 1
                    stats["skipped_model_codes"].append(model_code)
                    continue
                offering, created = upsert_result
                _, changed = upsert_collected_snapshot(
                    item,
                    source=source,
                    run=run,
                    offering=offering,
                )
                sync_model_price_items(
                    item,
                    source=source,
                    offering=offering,
                    source_url=catalog.source_url,
                )
                active_offering_ids.add(offering.id)
                stats["models"] += 1
                stats["created" if created else "updated"] += 1
                stats["changed" if changed else "unchanged"] += 1

            stale_stats = close_stale_current_collected_prices(
                source=source,
                active_offering_ids=active_offering_ids,
            )
            source.last_collected_at = timezone.now()
            source.save(update_fields=["last_collected_at", "updated_at"])
            run.status = PriceCollectionRun.STATUS_SUCCEEDED
            run.finished_at = timezone.now()
            run.collected_count = stats["models"]
            run.created_count = stats["created"]
            run.updated_count = stats["updated"]
            run.skipped_count = stats["skipped"]
            run.metadata = {
                **standard_catalog_run_metadata(standard_catalog),
                "source_url": catalog.source_url,
                "total_models": catalog.total_models,
                "currency": source.currency or "CNY",
                "changed_count": stats["changed"],
                "unchanged_count": stats["unchanged"],
                "skipped_model_codes": sorted(
                    set(stats["skipped_model_codes"]),
                ),
                "closed_stale_price_items": stale_stats["price_items"],
                "closed_stale_history": stale_stats["history"],
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
        "baidu": {"百度", "百度千帆", "千帆", "Baidu Qianfan"},
        "volcengine": {"火山", "火山方舟", "Volcengine", "豆包"},
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
) -> dict[str, int | list[str]]:
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

    target_model_codes = official_provider_target_model_codes(
        provider=provider,
        config=config,
    )
    run = PriceCollectionRun.objects.create(source=source)
    active_offering_ids: set[int] = set()
    changed_price_item_ids: set[int] = set()
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

        catalog, standard_catalog = collect_official_provider_price_catalog(
            provider=provider,
            source=source,
            config=config,
            target_model_codes=target_model_codes,
            source_url=source_url,
            verify_source=verify_source,
        )
        collected_currency = first_catalog_currency(catalog)
        collected_codes = {item.model_id for item in catalog.models}
        skipped_codes = sorted(target_model_codes - collected_codes)
        with transaction.atomic():
            for item in catalog.models:
                model_code = collected_model_code(item)
                meta_model = existing_meta_model_for_collected_item(item)
                if meta_model is None:
                    skipped_codes.append(model_code)
                    continue
                upsert_result = upsert_collected_offering(
                    item,
                    source=source,
                    source_url=catalog.source_url,
                    meta_model=meta_model,
                )
                if upsert_result is None:
                    skipped_codes.append(model_code)
                    continue
                offering, created = upsert_result
                _, changed = upsert_collected_snapshot(
                    item,
                    source=source,
                    run=run,
                    offering=offering,
                )
                price_items = sync_model_price_items(
                    item,
                    source=source,
                    offering=offering,
                    source_url=catalog.source_url,
                )
                changed_price_item_ids.update(
                    price_item.id for price_item in price_items
                )
                active_offering_ids.add(offering.id)
                stats["models"] = int(stats["models"]) + 1
                key = "created" if created else "updated"
                stats[key] = int(stats[key]) + 1
                change_key = "changed" if changed else "unchanged"
                stats[change_key] = int(stats[change_key]) + 1

            skipped_codes = sorted(set(skipped_codes))
            stale_stats = close_stale_current_collected_prices(
                source=source,
                active_offering_ids=active_offering_ids,
            )
            changed_price_item_ids.update(stale_stats["price_item_ids"])
            channel_sync = sync_dependent_channel_price_items_for_price_items(
                ModelPriceItem.objects.filter(id__in=changed_price_item_ids),
            )
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
            run_metadata = {
                "source_url": catalog.source_url,
                "currency": collected_currency or source.currency,
                "configured_currency": config.currency,
                "total_configured_models": len(target_model_codes),
                "changed_count": stats["changed"],
                "unchanged_count": stats["unchanged"],
                "skipped_model_codes": skipped_codes,
                "closed_stale_price_items": stale_stats["price_items"],
                "closed_stale_history": stale_stats["history"],
                "channel_model_prices_synced": (
                    channel_sync["channel_model_prices"]
                ),
                "channel_price_items_synced": (
                    channel_sync["channel_price_items"]
                ),
            }
            run_metadata.update(catalog_source_fetch_metadata(catalog))
            if standard_catalog is not None:
                run_metadata.update(
                    standard_catalog_run_metadata(standard_catalog)
                )
            run.metadata = run_metadata
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


def collect_official_provider_price_catalog(
    *,
    provider: LLMProvider,
    source: PriceCollectionSource,
    config,
    target_model_codes: set[str],
    source_url: str,
    verify_source: bool,
) -> tuple[CollectedPricingCatalog, dict | None]:
    """Collect an official provider catalog through the JSON contract."""
    if vendor_price_collector_exists(provider.code):
        collector_model_codes = (
            None
            if (
                verify_source
                and provider.code in FULL_CATALOG_PROVIDER_CODES
            )
            else target_model_codes
        )
        standard_catalog = collect_official_provider_standard_catalog(
            provider=provider,
            source=source,
            verify_source=verify_source,
            model_codes=collector_model_codes,
            source_url=source_url,
        )
        return (
            standard_catalog_to_collected_catalog(standard_catalog),
            standard_catalog,
        )

    if vendor_pricing_skill_exists(provider.code):
        skill_model_codes = (
            None
            if (
                verify_source
                and provider.code in FULL_CATALOG_PROVIDER_CODES
            )
            else target_model_codes
        )
        standard_catalog = collect_official_provider_standard_catalog(
            provider=provider,
            source=source,
            verify_source=verify_source,
            model_codes=skill_model_codes,
            source_url=source_url,
        )
        return (
            standard_catalog_to_collected_catalog(standard_catalog),
            standard_catalog,
        )

    catalog = collect_official_pricing_catalog(
        provider_code=provider.code,
        model_codes=target_model_codes,
        source_url=source_url,
        verify_source=verify_source,
    )
    return catalog, None


def collect_official_provider_standard_catalog(
    *,
    provider: LLMProvider,
    source: PriceCollectionSource,
    verify_source: bool = True,
    model_codes: set[str] | None = None,
    source_url: str = "",
) -> dict:
    """Collect official prices as standard JSON without persistence."""
    if provider.code not in OFFICIAL_PROVIDER_CONFIGS:
        raise ValueError(f"Unsupported official provider: {provider.code}")
    if not (
        vendor_price_collector_exists(provider.code)
        or vendor_pricing_skill_exists(provider.code)
    ):
        raise ValueError(
            "No vendor price catalog collector is available for "
            f"{provider.code}."
        )
    if source.provider_id != provider.id:
        raise ValueError("Price source does not belong to the provider.")

    config = OFFICIAL_PROVIDER_CONFIGS[provider.code]
    target_model_codes = set(model_codes or [])
    resolved_source_url = source_url or official_source_url(
        provider,
        source,
        config,
    )
    vendor_payload = {
        "provider_code": provider.code,
        "provider_name": provider.name,
        "currency": source.currency or config.currency,
        "source_url": resolved_source_url,
        "model_codes": sorted(target_model_codes),
        "verify_source": verify_source,
    }
    if vendor_price_collector_exists(provider.code):
        return collect_vendor_price_catalog(provider.code, vendor_payload)

    return run_vendor_pricing_skill(
        provider.code,
        vendor_payload,
    )


def first_catalog_currency(catalog) -> str:
    """Return the first non-empty currency observed in a collected catalog."""
    for item in catalog.models:
        if item.currency:
            return item.currency
    return ""


def catalog_source_fetch_metadata(catalog) -> dict:
    """Return official source fetch metadata from the first catalog item."""
    for item in catalog.models:
        raw_detail = item.raw_detail or {}
        metadata = raw_detail.get("official_source_fetch")
        if isinstance(metadata, dict):
            return dict(metadata)
    return {}


def official_provider_target_model_codes(*, provider, config) -> set[str]:
    """Return model codes that an official sync should attempt to cover."""
    existing_codes = set(
        provider.models.filter(is_active=True).values_list("code", flat=True)
    )
    official_codes = set()
    for spec in config.models:
        official_codes.add(spec.model_id)
        official_codes.update(spec.aliases)
    return {
        str(code).strip()
        for code in existing_codes | official_codes
        if str(code).strip()
    }


def sync_configured_official_model_prices(
    *,
    provider_codes: list[str] | None = None,
    verify_source: bool = True,
) -> dict[str, dict[str, int | str | list[str]]]:
    """Collect official prices for configured supported providers."""
    selected_provider_codes = provider_codes or list(
        DEFAULT_OFFICIAL_PRICE_SYNC_PROVIDER_CODES
    )
    supported_codes = set(SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES)
    if provider_codes:
        supported_codes.update(
            code
            for code, config in OFFICIAL_PROVIDER_CONFIGS.items()
            if config.models
        )
    selected_provider_codes = [
        code
        for code in selected_provider_codes
        if code in supported_codes
    ]
    queryset = LLMProvider.objects.filter(
        code__in=selected_provider_codes,
        is_active=True,
    ).order_by("code")
    results = {}
    for provider in queryset:
        try:
            results[provider.code] = sync_official_provider_model_prices(
                provider=provider,
                verify_source=verify_source,
            )
        except Exception as exc:
            results[provider.code] = {
                "models": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "changed": 0,
                "unchanged": 0,
                "skipped_model_codes": [],
                "error": str(exc),
            }
    return results


def supported_official_provider_options() -> list[dict]:
    """Return official provider source presets available to operators."""
    return official_provider_options_for_codes(
        SUPPORTED_OFFICIAL_SOURCE_PROVIDER_CODES,
    )


def official_provider_options_for_codes(provider_codes) -> list[dict]:
    """Return official source presets for selected provider codes."""
    provider_codes = list(provider_codes)
    providers = {
        provider.code: provider
        for provider in LLMProvider.objects.filter(code__in=provider_codes)
    }
    source_slugs = [
        official_provider_source_slug(provider_code)
        for provider_code in provider_codes
    ]
    sources = {
        source.slug: source
        for source in PriceCollectionSource.objects.select_related(
            "provider"
        ).filter(slug__in=source_slugs)
    }

    options = []
    for provider_code in provider_codes:
        defaults = official_provider_defaults(provider_code)
        provider = providers.get(provider_code)
        source_slug = official_provider_source_slug(provider_code)
        source = sources.get(source_slug)
        provider_name = provider.name if provider else defaults["name"]
        collection_method = official_provider_collection_method(
            provider_code,
        )
        options.append(
            {
                "provider_code": provider_code,
                "provider_name": provider_name,
                "provider_exists": provider is not None,
                "source_id": source.id if source else None,
                "source_slug": source_slug,
                "source_name": (
                    source.name
                    if source
                    else official_provider_default_source_name(provider_code)
                ),
                "source_exists": source is not None,
                "source_url": (
                    source.endpoint_url
                    if source and source.endpoint_url
                    else official_provider_source_url(provider_code)
                ),
                "currency": (
                    source.currency
                    if source
                    else official_provider_currency(provider_code)
                ),
                "option_code": provider_code,
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
                ),
                "source_owner_type": source_owner_type_for_provider_code(
                    provider_code
                ),
                "collection_method": collection_method,
                "updates_model_prices": True,
            }
        )
    return options


def supported_auto_sync_source_options() -> list[dict]:
    """Return source presets operators can add from the source modal."""
    options = official_provider_options_for_codes(
        SUPPORTED_OFFICIAL_SOURCE_PROVIDER_CODES,
    )
    supplier_codes = [
        code
        for code in registered_vendor_price_collector_codes()
        if code not in OFFICIAL_PROVIDER_CONFIGS
    ]
    supplier_slugs = [
        AUTO_SYNC_SOURCE_DEFAULTS[code]["source_slug"]
        for code in supplier_codes
        if code in AUTO_SYNC_SOURCE_DEFAULTS
    ]
    sources = {
        source.slug: source
        for source in PriceCollectionSource.objects.filter(
            slug__in=supplier_slugs
        )
    }
    for source_code in supplier_codes:
        defaults = AUTO_SYNC_SOURCE_DEFAULTS.get(source_code)
        if not defaults:
            continue
        source_slug = defaults["source_slug"]
        source = sources.get(source_slug)
        options.append(
            {
                "option_code": source_code,
                "provider_code": source_code,
                "provider_name": defaults["name"],
                "provider_exists": False,
                "source_id": source.id if source else None,
                "source_slug": source_slug,
                "source_name": (
                    source.name if source else defaults["source_name"]
                ),
                "source_exists": source is not None,
                "source_url": (
                    source.endpoint_url
                    if source and source.endpoint_url
                    else defaults["source_url"]
                ),
                "currency": (
                    source.currency if source else defaults["currency"]
                ),
                "source_category": defaults["source_category"],
                "source_owner_type": defaults["source_owner_type"],
                "collection_method": defaults["collection_method"],
                "updates_model_prices": True,
            }
        )
    return sorted(options, key=lambda item: item["source_name"])


def ensure_supported_official_provider_source(
    provider_code: str,
) -> tuple[LLMProvider, PriceCollectionSource, bool, bool]:
    """Ensure an operator-selected official provider source exists."""
    provider_code = str(provider_code or "").strip()
    if provider_code not in SUPPORTED_OFFICIAL_SOURCE_PROVIDER_CODES:
        raise ValueError("Unsupported official provider source.")

    defaults = official_provider_defaults(provider_code)
    provider, provider_created = LLMProvider.objects.get_or_create(
        code=provider_code,
        defaults={
            "name": defaults["name"],
            "website": defaults["website"],
            "notes": defaults["notes"],
            "is_active": True,
        },
    )
    changed_fields = []
    for field in ("website", "notes"):
        if not getattr(provider, field):
            setattr(provider, field, defaults[field])
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        provider.save(update_fields=changed_fields)

    source_created = not PriceCollectionSource.objects.filter(
        slug=official_provider_source_slug(provider_code)
    ).exists()
    if provider_code in SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES:
        source = ensure_official_source(provider=provider)
    else:
        source = ensure_manual_official_source(provider=provider)
    return provider, source, provider_created, source_created


def official_provider_source_slug(provider_code: str) -> str:
    """Return the stable provider-level official source slug."""
    return f"{provider_code}-official"


def official_provider_defaults(provider_code: str) -> dict[str, str]:
    """Return display defaults for a supported official source."""
    if provider_code in OFFICIAL_SOURCE_PROVIDER_DEFAULTS:
        return OFFICIAL_SOURCE_PROVIDER_DEFAULTS[provider_code]
    config = OFFICIAL_PROVIDER_CONFIGS[provider_code]
    return {
        "name": config.provider_label,
        "website": config.source_url,
        "notes": "模型价格源厂商。",
    }


def official_provider_source_url(provider_code: str) -> str:
    """Return the pricing URL for one official source preset."""
    defaults = OFFICIAL_SOURCE_PROVIDER_DEFAULTS.get(provider_code, {})
    if defaults.get("source_url"):
        return defaults["source_url"]
    return OFFICIAL_PROVIDER_CONFIGS[provider_code].source_url


def official_provider_currency(provider_code: str) -> str:
    """Return the default currency for one official source preset."""
    defaults = OFFICIAL_SOURCE_PROVIDER_DEFAULTS.get(provider_code, {})
    if defaults.get("currency"):
        return defaults["currency"]
    return OFFICIAL_PROVIDER_CONFIGS[provider_code].currency


def official_provider_source_name(
    provider: LLMProvider,
    provider_code: str,
) -> str:
    """Return the canonical source name for one official source."""
    defaults = official_provider_defaults(provider_code)
    return defaults.get("source_name") or f"{provider.name} 官方价格"


def official_provider_default_source_name(provider_code: str) -> str:
    """Return the default source display name for one provider code."""
    defaults = official_provider_defaults(provider_code)
    return defaults.get("source_name") or f"{defaults['name']} 官方价格"


def official_provider_collection_method(provider_code: str) -> str:
    """Return whether the official source has backend collection code."""
    if provider_code in SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES:
        return PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
    return PriceCollectionSource.COLLECTION_METHOD_UNKNOWN


def reset_official_price_catalog(
    *,
    provider_codes: list[str] | tuple[str, ...] | None = None,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    """Clear official price data while preserving provider-level sources."""
    codes = tuple(
        provider_codes or SUPPORTED_OFFICIAL_PRICE_SYNC_PROVIDER_CODES
    )
    provider_source_slugs = {
        official_provider_source_slug(provider_code) for provider_code in codes
    }
    matched_sources = [
        source
        for source in PriceCollectionSource.objects.select_related(
            "provider"
        ).filter(
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        if official_source_matches_provider_codes(
            source,
            provider_codes=codes,
            provider_source_slugs=provider_source_slugs,
        )
    ]
    source_ids = [source.id for source in matched_sources]
    provider_source_ids = [
        source.id
        for source in matched_sources
        if source.slug in provider_source_slugs
    ]
    provider_sources_by_provider_id = {
        source.provider_id: source
        for source in matched_sources
        if source.id in provider_source_ids and source.provider_id
    }
    legacy_source_ids = [
        source.id
        for source in matched_sources
        if source.slug not in provider_source_slugs
    ]
    legacy_sources = [
        source for source in matched_sources if source.id in legacy_source_ids
    ]
    legacy_source_slugs = sorted(
        source.slug
        for source in matched_sources
        if source.id in legacy_source_ids
    )
    legacy_models_deduplicated = count_legacy_model_source_collisions(
        legacy_sources=legacy_sources,
        provider_source_ids=provider_source_ids,
        provider_sources_by_provider_id=provider_sources_by_provider_id,
    )

    stats: dict[str, int | list[str]] = {
        "sources_matched": len(source_ids),
        "provider_sources_kept": len(provider_source_ids),
        "legacy_sources_deleted": len(legacy_source_ids),
        "legacy_models_deduplicated": legacy_models_deduplicated,
        "models_reset": LLMModel.objects.filter(
            source_id__in=source_ids,
        ).count(),
        "price_items_deleted": ModelPriceItem.objects.filter(
            source_id__in=source_ids,
        ).count(),
        "snapshots_deleted": CollectedModelPriceSnapshot.objects.filter(
            source_id__in=source_ids,
        ).count(),
        "history_deleted": CollectedModelPriceHistory.objects.filter(
            source_id__in=source_ids,
        ).count(),
        "runs_deleted": PriceCollectionRun.objects.filter(
            source_id__in=source_ids,
        ).count(),
        "legacy_source_slugs": legacy_source_slugs,
    }
    if dry_run:
        return stats

    now = timezone.now()
    with transaction.atomic():
        CollectedModelPriceSnapshot.objects.filter(
            source_id__in=source_ids,
        ).delete()
        CollectedModelPriceHistory.objects.filter(
            source_id__in=source_ids,
        ).delete()
        ModelPriceItem.objects.filter(source_id__in=source_ids).delete()
        PriceCollectionRun.objects.filter(source_id__in=source_ids).delete()
        LLMModel.objects.filter(source_id__in=source_ids).update(
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
            updated_at=now,
        )
        for legacy_source in legacy_sources:
            queryset = LLMModel.objects.filter(source=legacy_source)
            provider_source = provider_sources_by_provider_id.get(
                legacy_source.provider_id
            )
            if provider_source is None:
                queryset.update(
                    source=None,
                    source_url="",
                    price_role=LLMModel.PRICE_ROLE_UNKNOWN,
                    updated_at=now,
                )
                continue
            migrate_legacy_models_to_provider_source(
                queryset=queryset,
                provider_source=provider_source,
                now=now,
            )
        prune_global_config_price_sources(legacy_source_ids)
        PriceCollectionSource.objects.filter(id__in=legacy_source_ids).delete()

    return stats


def count_legacy_model_source_collisions(
    *,
    legacy_sources: list[PriceCollectionSource],
    provider_source_ids: list[int],
    provider_sources_by_provider_id: dict[int, PriceCollectionSource],
) -> int:
    """Count legacy model rows that would collide on provider source move."""
    if not legacy_sources:
        return 0

    target_keys = set(
        LLMModel.objects.filter(source_id__in=provider_source_ids).values_list(
            "provider_id", "source_id", "code"
        )
    )
    collisions = 0
    for legacy_source in legacy_sources:
        provider_source = provider_sources_by_provider_id.get(
            legacy_source.provider_id
        )
        if provider_source is None:
            continue
        legacy_models = LLMModel.objects.filter(
            source=legacy_source,
        ).values_list("provider_id", "code")
        for provider_id, code in legacy_models:
            key = (provider_id, provider_source.id, code)
            if key in target_keys:
                collisions += 1
                continue
            target_keys.add(key)
    return collisions


def migrate_legacy_models_to_provider_source(
    *,
    queryset,
    provider_source: PriceCollectionSource,
    now,
) -> None:
    """Move legacy official models without violating provider/source/code."""
    source_url = provider_source.endpoint_url or ""
    for model in queryset.order_by("id").only("id", "provider_id", "code"):
        duplicate_exists = (
            LLMModel.objects.filter(
                provider_id=model.provider_id,
                source_id=provider_source.id,
                code=model.code,
            )
            .exclude(id=model.id)
            .exists()
        )
        if duplicate_exists:
            LLMModel.objects.filter(id=model.id).update(
                source=None,
                source_url="",
                price_role=LLMModel.PRICE_ROLE_UNKNOWN,
                updated_at=now,
            )
            continue
        LLMModel.objects.filter(id=model.id).update(
            source_id=provider_source.id,
            source_url=source_url,
            updated_at=now,
        )


def official_source_matches_provider_codes(
    source: PriceCollectionSource,
    *,
    provider_codes: tuple[str, ...],
    provider_source_slugs: set[str],
) -> bool:
    """Return whether an official source belongs to the reset scope."""
    if source.slug in provider_source_slugs:
        return True
    if not source.provider or source.provider.code not in provider_codes:
        return False

    provider_code = source.provider.code
    if not source.slug.startswith(f"{provider_code}-"):
        return False
    if not source.slug.endswith("-official"):
        return False

    model_codes = set(
        LLMModel.objects.filter(source=source).values_list("code", flat=True)
    )
    model_codes.update(
        ModelPriceItem.objects.filter(source=source)
        .exclude(model__isnull=True)
        .values_list("model__code", flat=True)
    )
    model_codes.update(
        CollectedModelPriceSnapshot.objects.filter(source=source).values_list(
            "source_platform_id",
            flat=True,
        )
    )
    for model_code in model_codes:
        if source.slug == official_model_source_slug(
            provider_code, model_code
        ):
            return True
    return False


def prune_global_config_price_sources(source_ids: list[int]) -> int:
    """Remove deleted source ids from persisted sync selections."""
    if not source_ids:
        return 0
    deleted = {str(source_id) for source_id in source_ids}
    changed = 0
    for config in LLMOpsGlobalConfig.objects.all():
        raw_ids = list(config.price_collection_source_ids or [])
        kept_ids = [
            source_id for source_id in raw_ids if str(source_id) not in deleted
        ]
        if kept_ids == raw_ids:
            continue
        config.price_collection_source_ids = kept_ids
        config.save(
            update_fields=["price_collection_source_ids", "updated_at"]
        )
        changed += 1
    return changed


def ensure_official_model_source(
    *,
    provider: LLMProvider,
    model_code: str,
    display_name: str,
    source_url: str,
    currency: str,
) -> PriceCollectionSource:
    """Ensure an independent official source exists for one model."""
    normalized_code = collected_model_code_from_value(model_code)
    slug = official_model_source_slug(provider.code, normalized_code)
    owner_type = source_owner_type_for_provider(provider)
    source, created = PriceCollectionSource.objects.get_or_create(
        slug=slug,
        defaults={
            "provider": provider,
            "name": (
                f"{provider.name} / "
                f"{display_name or normalized_code} 官方价格"
            ),
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            "source_owner_type": owner_type,
            "collection_method": (
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
            ),
            "endpoint_url": source_url,
            "currency": currency or "USD",
            "is_enabled": True,
            "updates_model_prices": True,
            "notes": (
                "官方公开价格采集源；"
                "该来源只对应一个模型。"
            ),
        },
    )
    if created:
        return source

    desired_fields = {
        "provider": provider,
        "name": (
            f"{provider.name} / {display_name or normalized_code} 官方价格"
        ),
        "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
        "source_category": (
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ),
        "source_owner_type": owner_type,
        "collection_method": (
            PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
        ),
        "currency": currency or source.currency or "USD",
        "updates_model_prices": True,
        "notes": (
            "官方公开价格采集源；"
            "该来源只对应一个模型。"
        ),
    }
    if not source.endpoint_url:
        desired_fields["endpoint_url"] = source_url
    changed_fields = []
    for field, value in desired_fields.items():
        if getattr(source, field) != value:
            setattr(source, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        source.save(update_fields=changed_fields)
    return source


def official_model_source_slug(provider_code: str, model_code: str) -> str:
    """Return a stable slug for a model-specific official source."""
    value = f"{provider_code}-{model_code}-official".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if len(slug) <= 100:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:10]
    prefix = slug[: 100 - len(digest) - 1].rstrip("-")
    return f"{prefix}-{digest}"


def collected_model_code_from_value(value: str) -> str:
    """Normalize a collected model code for source identity."""
    return str(value or "").strip() or "unknown"


def sync_meta_models_from_models_dev(
    *,
    source_url: str | None = None,
    timeout: int | None = None,
    fallback_urls: list[str] | tuple[str, ...] | str | None = None,
) -> dict[str, object]:
    """Fetch models.dev and upsert canonical meta-model identities."""
    from .constants import (
        canonical_meta_model_identity,
    )

    resolved_source_url = source_url or MODELS_DEV_MODELS_URL
    resolved_timeout = models_dev_sync_timeout(timeout)
    source_json, effective_source_url, used_cache, cached_at = (
        fetch_models_dev_source_json(
            source_url=resolved_source_url,
            timeout=resolved_timeout,
            fallback_urls=fallback_urls,
        )
    )

    stats = {
        "models": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "deleted": 0,
        "used_cache": int(used_cache),
    }
    if cached_at:
        stats["cached_at"] = cached_at
    seen_codes = set()
    with transaction.atomic():
        for model_payload in iter_models_dev_meta_model_payloads(
            source_json,
        ):
            if not isinstance(model_payload, dict):
                stats["skipped"] += 1
                continue
            reported_code = models_dev_meta_code(model_payload)
            identity = canonical_meta_model_identity(
                reported_code,
                model_payload.get("name"),
            )
            code = identity["code"]
            if not code or code in seen_codes:
                stats["skipped"] += 1
                continue
            owner = models_dev_owner_payload(model_payload, code)
            if not owner["owner_code"]:
                stats["skipped"] += 1
                continue
            seen_codes.add(code)
            _, created, changed = upsert_models_dev_meta_model(
                model_payload,
                code=code,
                identity=identity,
                owner=owner,
                source_url=effective_source_url,
            )
            stats["models"] += 1
            stats["created" if created else "updated"] += int(changed)
        stats["deleted"] = cleanup_stale_models_dev_meta_models(seen_codes)
    return stats


def models_dev_sync_timeout(timeout: int | None) -> int:
    """Return the configured timeout for models.dev metadata sync."""
    if timeout is not None:
        return max(1, int(timeout))
    configured = getattr(settings, "LLM_OPS_MODELS_DEV_TIMEOUT", None)
    if configured in (None, ""):
        configured = os.getenv("LLM_OPS_MODELS_DEV_TIMEOUT", "")
    try:
        return max(1, int(configured))
    except (TypeError, ValueError):
        return DEFAULT_MODELS_DEV_SYNC_TIMEOUT


def fetch_models_dev_source_json(
    *,
    source_url: str,
    timeout: int,
    fallback_urls: list[str] | tuple[str, ...] | str | None = None,
) -> tuple[dict, str, bool, str]:
    """Fetch models.dev JSON, falling back to mirrors then cache."""
    errors = []
    for candidate_url in models_dev_candidate_urls(
        source_url,
        fallback_urls,
    ):
        try:
            payload = fetch_source_payload(candidate_url, timeout)
            source_json = payload.get("json")
            if not isinstance(source_json, dict):
                raise ValueError("models.dev source did not return JSON.")
            cache_models_dev_source_json(source_json, candidate_url)
            return source_json, candidate_url, False, ""
        except Exception as exc:
            errors.append(f"{candidate_url}: {exc}")
            logger.warning(
                "llm_ops.models_dev_sync_source_failed",
                extra={"source_url": candidate_url},
                exc_info=True,
            )

    cached = cached_models_dev_source_json()
    if cached is not None:
        logger.warning(
            "llm_ops.models_dev_sync_using_cached_payload",
            extra={"source_url": cached["source_url"]},
        )
        return (
            cached["json"],
            cached["source_url"],
            True,
            cached["cached_at"],
        )
    raise ValueError(
        "models.dev source did not return JSON and no cache is available: "
        + "; ".join(errors),
    )


def models_dev_candidate_urls(
    source_url: str,
    fallback_urls: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    """Return primary and fallback models.dev URLs without duplicates."""
    values = [source_url]
    values.extend(configured_models_dev_fallback_urls(fallback_urls))
    candidates = []
    seen = set()
    for value in values:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def configured_models_dev_fallback_urls(
    fallback_urls: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    """Return explicit or environment-configured models.dev fallback URLs."""
    if fallback_urls is None:
        fallback_urls = getattr(
            settings,
            "LLM_OPS_MODELS_DEV_FALLBACK_URLS",
            None,
        )
        if fallback_urls in (None, ""):
            fallback_urls = os.getenv("LLM_OPS_MODELS_DEV_FALLBACK_URLS", "")
    if isinstance(fallback_urls, str):
        return [
            item.strip()
            for item in fallback_urls.split(",")
            if item.strip()
        ]
    return [
        str(item).strip()
        for item in fallback_urls
        if str(item or "").strip()
    ]


def cache_models_dev_source_json(source_json: dict, source_url: str) -> None:
    """Store the last successful models.dev response for outage fallback."""
    try:
        cache.set(
            MODELS_DEV_RESPONSE_CACHE_KEY,
            {
                "json": source_json,
                "source_url": source_url,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=None,
        )
    except Exception:
        logger.warning(
            "llm_ops.models_dev_sync_cache_write_failed",
            exc_info=True,
        )


def cached_models_dev_source_json() -> dict | None:
    """Return the cached models.dev payload when it has the expected shape."""
    try:
        cached = cache.get(MODELS_DEV_RESPONSE_CACHE_KEY)
    except Exception:
        logger.warning(
            "llm_ops.models_dev_sync_cache_read_failed",
            exc_info=True,
        )
        return None
    if not isinstance(cached, dict):
        return None
    source_json = cached.get("json")
    source_url = str(cached.get("source_url") or "").strip()
    cached_at = str(cached.get("cached_at") or "").strip()
    if not isinstance(source_json, dict) or not source_url:
        return None
    return {
        "json": source_json,
        "source_url": source_url,
        "cached_at": cached_at,
    }


def iter_models_dev_meta_model_payloads(source_json: dict):
    """Yield model rows from the public models.dev metadata endpoint."""
    if is_models_dev_models_json(source_json):
        for model_id in sorted(source_json):
            model_payload = source_json[model_id]
            if isinstance(model_payload, dict):
                yield model_payload
        return

    for provider_payload in iter_models_dev_meta_sources(source_json):
        if not isinstance(provider_payload, dict):
            continue
        models = provider_payload.get("models", {})
        if not isinstance(models, dict):
            continue
        for model_payload in models.values():
            yield model_payload


def is_models_dev_models_json(source_json: dict) -> bool:
    """Return whether a payload has the flat models.json shape."""
    if not isinstance(source_json, dict) or not source_json:
        return False
    for key, value in source_json.items():
        if not isinstance(value, dict):
            return False
        if value.get("models") is not None:
            return False
        if value.get("id") != key or "/" not in str(value.get("id") or ""):
            return False
    return True


def iter_models_dev_meta_sources(source_json: dict):
    """Yield model-provider payloads accepted for meta-model sync.

    models.dev contains both original model vendors and marketplaces.
    The meta-model library should track original model families, not
    every reseller SKU. We therefore only consume known primary vendor
    catalogues plus a small fallback source for vendors that are not
    published directly by models.dev yet.
    """
    entries = [
        (provider_id, payload)
        for provider_id, payload in source_json.items()
        if provider_id in MODELS_DEV_META_SOURCE_PROVIDERS
    ]
    entries.sort(key=lambda item: models_dev_provider_priority(item[0]))
    for _, payload in entries:
        yield payload


def models_dev_provider_priority(provider_id: str) -> tuple[int, str]:
    """Prefer original vendor feeds before fallback aggregators."""
    fallback_sources = {"novita-ai"}
    return (1 if provider_id in fallback_sources else 0, provider_id)


def cleanup_stale_models_dev_meta_models(active_codes: set[str]) -> int:
    """Delete old online-only meta models outside the accepted source set."""
    active_count = len(active_codes)
    tracked_count = count_models_dev_meta_models()
    if should_skip_models_dev_stale_cleanup(active_count, tracked_count):
        logger.warning(
            "llm_ops: skipped models.dev stale cleanup because "
            "active model count %d is unsafe for %d tracked models.dev "
            "meta model(s)",
            active_count,
            tracked_count,
        )
        return 0

    deleted = 0
    for meta in MetaModel.objects.all():
        if not (meta.metadata or {}).get("models_dev"):
            continue
        if meta.code in active_codes:
            continue
        if meta_model_has_business_links(meta):
            continue
        meta.delete()
        deleted += 1
    return deleted


def count_models_dev_meta_models() -> int:
    """Return the number of meta models currently sourced from models.dev."""
    return sum(
        1
        for metadata in MetaModel.objects.values_list("metadata", flat=True)
        if (metadata or {}).get("models_dev")
    )


def should_skip_models_dev_stale_cleanup(
    active_count: int,
    tracked_count: int,
) -> bool:
    """Return whether source shrinkage makes stale cleanup unsafe."""
    if tracked_count <= 0:
        return False
    if active_count <= 0:
        return True
    if tracked_count < MODELS_DEV_CLEANUP_MIN_RETAIN_COUNT:
        return False
    if active_count < MODELS_DEV_CLEANUP_MIN_RETAIN_COUNT:
        return True

    retained_percent = 100 - MODELS_DEV_CLEANUP_MAX_DROP_PERCENT
    return active_count * 100 < tracked_count * retained_percent


def meta_model_has_business_links(meta_model: MetaModel) -> bool:
    """Return whether a meta model is referenced by business records."""
    for relation in MetaModel._meta.related_objects:
        if relation.related_model is MetaModel:
            continue
        if relation.related_model.objects.filter(
            **{relation.field.name: meta_model}
        ).exists():
            return True
    return False


def models_dev_meta_code(model_payload: dict) -> str:
    """Normalize a models.dev model id into one canonical meta-model code."""
    raw_code = str(model_payload.get("id") or "").strip()
    if raw_code.startswith("hf:"):
        raw_code = raw_code[3:]
    if "/" in raw_code:
        raw_code = raw_code.rsplit("/", 1)[-1]
    return normalize_model_code(raw_code)


def models_dev_owner_payload(model_payload: dict, code: str) -> dict:
    """Return local owner fields using model code then models.dev lab."""
    from .constants import meta_model_owner_payload

    owner = meta_model_owner_payload(code)
    if owner["owner_code"]:
        return owner

    lab_key = models_dev_lab_key(model_payload)
    lab_owner = MODELS_DEV_LAB_OWNER_DEFAULTS.get(lab_key)
    if lab_owner is None:
        return owner
    owner_code, owner_name, owner_website = lab_owner
    return {
        "owner_code": owner_code,
        "owner_name": owner_name,
        "owner_website": owner_website,
    }


def models_dev_lab_key(model_payload: dict) -> str:
    """Return the lab slug from a models.dev model id."""
    model_id = str(model_payload.get("id") or "").strip()
    if model_id.startswith("hf:"):
        model_id = model_id[3:]
    if "/" not in model_id:
        return ""
    return model_id.split("/", 1)[0].strip().lower()


def upsert_models_dev_meta_model(
    model_payload: dict,
    *,
    code: str,
    identity: dict,
    owner: dict,
    source_url: str,
) -> tuple[MetaModel, bool, bool]:
    """Upsert one models.dev row without overwriting operator fields."""
    name = identity["name"]
    defaults = {
        "name": name,
        **owner,
        "family": str(model_payload.get("family") or "").strip(),
        "modality": models_dev_modality(model_payload),
        "aliases": models_dev_meta_aliases(model_payload, code, identity),
        "capabilities": models_dev_capabilities(model_payload),
        "context_window": models_dev_limit(model_payload, "context"),
        "max_output_tokens": models_dev_limit(model_payload, "output"),
        "status": MetaModel.STATUS_ACTIVE,
        "metadata": models_dev_metadata(model_payload, source_url),
    }
    meta_model, created = MetaModel.objects.get_or_create(
        code=code,
        defaults=defaults,
    )
    if created:
        return meta_model, True, True

    changed_fields = []
    if meta_model.name in {"", meta_model.code} and name:
        meta_model.name = name
        changed_fields.append("name")
    for field_name, value in owner.items():
        if getattr(meta_model, field_name) != value:
            setattr(meta_model, field_name, value)
            changed_fields.append(field_name)
    if not meta_model.family and defaults["family"]:
        meta_model.family = defaults["family"]
        changed_fields.append("family")
    if (
        meta_model.modality == MetaModel.MODALITY_TEXT
        and defaults["modality"] != MetaModel.MODALITY_TEXT
    ):
        meta_model.modality = defaults["modality"]
        changed_fields.append("modality")
    changed_fields += update_meta_model_numbers(meta_model, defaults)
    changed_fields += merge_meta_model_json(meta_model, defaults)
    if meta_model.status == MetaModel.STATUS_UNKNOWN:
        meta_model.status = MetaModel.STATUS_ACTIVE
        changed_fields.append("status")
    if changed_fields:
        changed_fields.append("updated_at")
        meta_model.save(update_fields=changed_fields)
    return meta_model, False, bool(changed_fields)


def update_meta_model_numbers(
    meta_model: MetaModel,
    defaults: dict,
) -> list[str]:
    """Raise token limits when the online source has a larger value."""
    changed_fields = []
    context_window = defaults["context_window"]
    if context_window and context_window > meta_model.context_window:
        meta_model.context_window = context_window
        changed_fields.append("context_window")
    max_output = defaults["max_output_tokens"]
    if max_output and max_output > meta_model.max_output_tokens:
        meta_model.max_output_tokens = max_output
        changed_fields.append("max_output_tokens")
    return changed_fields


def merge_meta_model_json(meta_model: MetaModel, defaults: dict) -> list[str]:
    """Merge aliases, capabilities and source metadata."""
    changed_fields = []
    aliases = list(
        dict.fromkeys(
            list(meta_model.aliases or []) + list(defaults["aliases"])
        )
    )
    if aliases != (meta_model.aliases or []):
        meta_model.aliases = aliases
        changed_fields.append("aliases")

    capabilities = dict(meta_model.capabilities or {})
    existing_features = capabilities.get("features") or []
    new_features = defaults["capabilities"].get("features") or []
    features = list(dict.fromkeys(existing_features + new_features))
    if features != existing_features:
        capabilities["features"] = features
        meta_model.capabilities = capabilities
        changed_fields.append("capabilities")

    metadata = dict(meta_model.metadata or {})
    if metadata.get("models_dev") != defaults["metadata"]["models_dev"]:
        metadata["models_dev"] = defaults["metadata"]["models_dev"]
        meta_model.metadata = metadata
        changed_fields.append("metadata")
    return changed_fields


def models_dev_meta_aliases(
    model_payload: dict,
    code: str,
    identity: dict,
) -> list[str]:
    """Return stable aliases from models.dev identity fields."""
    values = [
        model_payload.get("id"),
        model_payload.get("name"),
        model_payload.get("family"),
        code,
        *identity["aliases"],
    ]
    aliases = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        aliases.append(text)
    return aliases


def models_dev_modality(model_payload: dict) -> str:
    """Map models.dev modalities to the local meta-model modality."""
    modalities = model_payload.get("modalities") or {}
    inputs = set(modalities.get("input") or [])
    outputs = set(modalities.get("output") or [])
    if "video" in outputs:
        return MetaModel.MODALITY_VIDEO
    if "audio" in outputs:
        return MetaModel.MODALITY_AUDIO
    if (inputs | outputs) - {"text"}:
        return MetaModel.MODALITY_MULTIMODAL
    return MetaModel.MODALITY_TEXT


def models_dev_limit(model_payload: dict, key: str) -> int:
    """Return an integer token limit from models.dev."""
    try:
        return int((model_payload.get("limit") or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0


def models_dev_capabilities(model_payload: dict) -> dict:
    """Return local feature labels from models.dev boolean flags."""
    feature_map = {
        "attachment": "attachment",
        "reasoning": "reasoning",
        "structured_output": "structured_output",
        "tool_call": "tool_calling",
        "temperature": "temperature",
        "open_weights": "open_weights",
    }
    features = [
        label
        for field, label in feature_map.items()
        if model_payload.get(field) is True
    ]
    return {"features": features}


def models_dev_metadata(model_payload: dict, source_url: str) -> dict:
    """Return source metadata stored under the models_dev key."""
    lab = models_dev_lab_key(model_payload)
    return {
        "models_dev": {
            "id": model_payload.get("id") or "",
            "lab": lab,
            "source_url": source_url,
            "description": model_payload.get("description") or "",
            "release_date": model_payload.get("release_date") or "",
            "last_updated": model_payload.get("last_updated") or "",
            "knowledge": model_payload.get("knowledge") or "",
            "modalities": model_payload.get("modalities") or {},
            "links": model_payload.get("links") or [],
            "weights": model_payload.get("weights") or [],
            "benchmarks": model_payload.get("benchmarks") or [],
            "open_weights": bool(model_payload.get("open_weights")),
            "logo_url": models_dev_lab_logo_url(lab),
            "logo_path": models_dev_lab_logo_path(lab),
        },
    }


def models_dev_lab_logo_url(lab: str) -> str:
    """Return the public models.dev lab logo URL for one lab."""
    if not lab:
        return ""
    return f"https://models.dev/logos/labs/{lab}.svg"


def models_dev_lab_logo_path(lab: str) -> str:
    """Return the committed frontend asset path for one lab logo."""
    if not lab:
        return ""
    return f"{MODELS_DEV_LOGO_ASSET_PREFIX}/labs/{lab}.svg"


def official_source_url(
    provider: LLMProvider,
    source: PriceCollectionSource,
    config,
) -> str:
    """Return the effective official source URL for collection."""
    endpoint_url = source.endpoint_url or config.source_url
    if is_legacy_official_pricing_url(provider.code, endpoint_url):
        return config.source_url
    return endpoint_url


def is_legacy_official_pricing_url(provider_code: str, url: str) -> bool:
    """Return whether a persisted URL should follow current config."""
    return (
        is_legacy_aliyun_pricing_url(provider_code, url)
        or is_legacy_minimax_pricing_url(provider_code, url)
    )


def is_legacy_aliyun_pricing_url(provider_code: str, url: str) -> bool:
    """Return whether a persisted Aliyun URL should follow current config."""
    if provider_code not in {"aliyun", "aliyun-wanx"}:
        return False
    return url in ALIYUN_LEGACY_PRICING_SOURCE_URLS


def is_legacy_minimax_pricing_url(provider_code: str, url: str) -> bool:
    """Return whether a persisted MiniMax URL should follow current config."""
    if provider_code != "minimax":
        return False
    return url in MINIMAX_LEGACY_PRICING_SOURCE_URLS


def upsert_collected_offering(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    source_url: str,
    meta_model: MetaModel | None = None,
) -> tuple[SourceSkuOffering, bool] | None:
    """Upsert the final SKU/offering identity for one collected price."""
    meta_model = meta_model or existing_meta_model_for_collected_item(item)
    if meta_model is None:
        return None
    provider = resolve_collected_provider(item, source=source)
    sku = upsert_collected_sku(
        item,
        provider=provider,
        meta_model=meta_model,
        source=source,
        source_url=source_url,
    )
    offering, created = upsert_collected_source_offering(
        item,
        source=source,
        sku=sku,
        provider=provider,
        source_url=source_url,
    )
    upsert_legacy_model_for_offering(
        item,
        source=source,
        offering=offering,
        source_url=source_url,
    )
    return offering, created


def upsert_collected_sku(
    item: CollectedModelPricing,
    *,
    provider: LLMProvider,
    meta_model: MetaModel,
    source: PriceCollectionSource,
    source_url: str,
) -> ModelSku:
    """Upsert a provider SKU without confirming runtime routing."""
    sku_code = collected_model_code(item)
    upstream_name = collected_model_raw_code(item) or sku_code
    display_name = item.name or upstream_name
    sku, created = ModelSku.objects.get_or_create(
        provider=provider,
        canonical_sku_code=sku_code,
        region=sku_region(item),
        mode=sku_mode(item),
        api_type=sku_api_type(item),
        defaults={
            "meta_model": meta_model,
            "upstream_model_name": upstream_name,
            "display_name": display_name,
            "variant_type": sku_variant_type(source),
            "capabilities": {},
            "evidence": sku_evidence(source=source, source_url=source_url),
            "routing_status": ModelSku.ROUTING_CANDIDATE,
            "is_routable": False,
            "is_active": True,
        },
    )
    changed_fields = []
    routing_locked = sku.routing_status == ModelSku.ROUTING_LOCKED
    if not routing_locked and sku.meta_model_id != meta_model.id:
        sku.meta_model = meta_model
        changed_fields.append("meta_model")
    if not routing_locked and not sku.display_name and display_name:
        sku.display_name = display_name
        changed_fields.append("display_name")
    if created is False and not routing_locked:
        if not sku.upstream_model_name and upstream_name:
            sku.upstream_model_name = upstream_name
            changed_fields.append("upstream_model_name")
    variant_type = sku_variant_type(source)
    if (
        not routing_locked
        and sku.variant_type == ModelSku.VARIANT_UNKNOWN
        and variant_type != ModelSku.VARIANT_UNKNOWN
    ):
        sku.variant_type = variant_type
        changed_fields.append("variant_type")
    evidence = dict(sku.evidence or {})
    evidence.update(sku_evidence(source=source, source_url=source_url))
    if evidence != (sku.evidence or {}):
        sku.evidence = evidence
        changed_fields.append("evidence")
    if changed_fields:
        changed_fields.append("updated_at")
        sku.save(update_fields=changed_fields)
    return sku


def upsert_collected_source_offering(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    sku: ModelSku,
    provider: LLMProvider,
    source_url: str,
) -> tuple[SourceSkuOffering, bool]:
    """Upsert the source-facing offering for one collected SKU."""
    exposed_model_name = source_exposed_model_name(item, sku)
    offering, created = SourceSkuOffering.objects.get_or_create(
        source=source,
        sku=sku,
        exposed_model_name=exposed_model_name,
        defaults={
            "provider": provider,
            "pricing_method": SourceSkuOffering.METHOD_COLLECTED,
            "evidence": offering_evidence(
                source=source,
                sku=sku,
                source_url=source_url,
            ),
            "is_active": True,
        },
    )
    changed_fields = []
    if offering.provider_id != provider.id:
        offering.provider = provider
        changed_fields.append("provider")
    if not offering.is_active:
        offering.is_active = True
        changed_fields.append("is_active")
    evidence = dict(offering.evidence or {})
    evidence.update(
        offering_evidence(
            source=source,
            sku=sku,
            source_url=source_url,
        )
    )
    if evidence != (offering.evidence or {}):
        offering.evidence = evidence
        changed_fields.append("evidence")
    if not created and changed_fields:
        changed_fields.append("updated_at")
        offering.save(update_fields=changed_fields)
    return offering, created


def sku_region(item: CollectedModelPricing) -> str:
    """Return explicit SKU region identity from collector metadata."""
    raw_detail = item.raw_detail or {}
    model_info = raw_detail.get("model_info") or {}
    if not isinstance(model_info, dict):
        model_info = {}
    value = (
        raw_detail.get("sku_region")
        or raw_detail.get("deployment_region")
        or model_info.get("sku_region")
        or model_info.get("deployment_region")
    )
    return str(value or "").strip()


def sku_mode(item: CollectedModelPricing) -> str:
    """Return SKU mode identity from collector metadata."""
    return str(item.mode or "").strip()


def sku_api_type(item: CollectedModelPricing) -> str:
    """Return SKU API type identity from collector metadata."""
    raw_detail = item.raw_detail or {}
    value = raw_detail.get("api_type") or raw_detail.get("endpoint_type")
    return str(value or "").strip()


def upsert_collected_model(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    source_url: str,
    meta_model: MetaModel | None = None,
) -> tuple[LLMModel, bool] | None:
    """Upsert one collected model into the canonical model table."""
    model_code = collected_model_code(item)
    meta_model = meta_model or existing_meta_model_for_collected_item(item)
    if meta_model is None:
        return None
    provider = resolve_collected_provider(item, source=source)
    lookup = {
        "provider": provider,
        "source": source,
        "code": model_code,
    }
    defaults = model_defaults_from_collected_item(
        item,
        source=source,
        source_url=source_url,
    )
    defaults["source"] = source
    defaults["meta_model"] = meta_model
    defaults["price_role"] = price_role_for_source(
        source,
        meta_model=meta_model,
    )
    if source.updates_model_prices:
        existing = LLMModel.objects.filter(**lookup).first()
        if existing is None:
            existing = legacy_official_model_for_provider_source(
                provider=provider,
                source=source,
                code=model_code,
            )
        if existing is None:
            model = LLMModel.objects.create(**{**lookup, **defaults})
            ensure_model_sku_for_model(
                model,
                item=item,
                source=source,
                source_url=source_url,
            )
            return model, True
        changed_fields = update_model_from_defaults(existing, defaults)
        if changed_fields:
            changed_fields.append("updated_at")
            existing.save(update_fields=changed_fields)
        ensure_model_sku_for_model(
            existing,
            item=item,
            source=source,
            source_url=source_url,
        )
        return existing, False

    model = find_aggregated_model(
        provider=provider,
        code=model_code,
        meta_model=meta_model,
        source=source,
    )
    if model is None:
        create_defaults = model_identity_defaults_from_collected_item(item)
        create_defaults["meta_model"] = meta_model
        create_defaults["price_role"] = price_role_for_source(
            source,
            meta_model=meta_model,
        )
        model = LLMModel.objects.create(
            provider=provider,
            code=model_code,
            **create_defaults,
        )
        ensure_model_sku_for_model(
            model,
            item=item,
            source=source,
            source_url=source_url,
        )
        return model, True

    changed_fields = update_aggregated_model_identity(
        model,
        meta_model=meta_model,
        name=item.name or item.model_id,
        modality=modality_from_source_type(item.source_model_type),
        currency=item.currency or source.currency or "USD",
        current_source=source,
    )
    if changed_fields:
        changed_fields.append("updated_at")
        model.save(update_fields=changed_fields)
    ensure_model_sku_for_model(
        model,
        item=item,
        source=source,
        source_url=source_url,
    )
    return model, False


def ensure_model_sku_for_model(
    model: LLMModel,
    *,
    item: CollectedModelPricing,
    source: PriceCollectionSource,
    source_url: str,
) -> ModelSku:
    """Ensure a provider SKU exists without making it routable by default."""
    sku_code = collected_model_code(item)
    upstream_name = collected_model_raw_code(item) or sku_code
    display_name = item.name or upstream_name
    sku, created = ModelSku.objects.get_or_create(
        provider=model.provider,
        canonical_sku_code=sku_code,
        region="",
        mode="",
        api_type="",
        defaults={
            "meta_model": model.meta_model,
            "upstream_model_name": upstream_name,
            "display_name": display_name,
            "variant_type": sku_variant_type(source),
            "capabilities": {},
            "evidence": sku_evidence(source=source, source_url=source_url),
            "routing_status": ModelSku.ROUTING_CANDIDATE,
            "is_routable": False,
            "is_active": True,
        },
    )
    changed_fields = []
    routing_locked = sku.routing_status == ModelSku.ROUTING_LOCKED
    if not routing_locked and sku.meta_model_id != model.meta_model_id:
        sku.meta_model = model.meta_model
        changed_fields.append("meta_model")
    if not routing_locked and not sku.display_name and display_name:
        sku.display_name = display_name
        changed_fields.append("display_name")
    if created is False and not routing_locked:
        if not sku.upstream_model_name and upstream_name:
            sku.upstream_model_name = upstream_name
            changed_fields.append("upstream_model_name")
    variant_type = sku_variant_type(source)
    if (
        not routing_locked
        and sku.variant_type == ModelSku.VARIANT_UNKNOWN
        and variant_type != ModelSku.VARIANT_UNKNOWN
    ):
        sku.variant_type = variant_type
        changed_fields.append("variant_type")
    evidence = dict(sku.evidence or {})
    evidence.update(sku_evidence(source=source, source_url=source_url))
    if evidence != (sku.evidence or {}):
        sku.evidence = evidence
        changed_fields.append("evidence")
    if changed_fields:
        changed_fields.append("updated_at")
        sku.save(update_fields=changed_fields)

    if model.sku_id != sku.id:
        model.sku = sku
        model.save(update_fields=["sku", "updated_at"])
    return sku


def sku_variant_type(source: PriceCollectionSource) -> str:
    """Return SKU variant type from source owner metadata."""
    owner_type = source_owner_type_for_source(source)
    if owner_type == (
        PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
    ):
        return ModelSku.VARIANT_CLOUD_HOSTED
    if owner_type == (
        PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL
    ):
        return ModelSku.VARIANT_OFFICIAL
    if owner_type == PriceCollectionSource.SOURCE_OWNER_SUPPLIER:
        return ModelSku.VARIANT_RESELLER
    return ModelSku.VARIANT_UNKNOWN


def sku_evidence(*, source: PriceCollectionSource, source_url: str) -> dict:
    """Return auditable evidence used to create or update a SKU."""
    return {
        "source_id": source.id,
        "source_slug": source.slug,
        "source_url": source_url,
    }


def ensure_source_sku_offering(
    *,
    source: PriceCollectionSource,
    model: LLMModel,
    item: CollectedModelPricing,
    source_url: str,
) -> SourceSkuOffering | None:
    """Ensure the price source has an offering for the model SKU."""
    if model.sku_id is None:
        return None
    exposed_model_name = source_exposed_model_name(item, model.sku)
    offering, created = SourceSkuOffering.objects.get_or_create(
        source=source,
        sku=model.sku,
        exposed_model_name=exposed_model_name,
        defaults={
            "provider": model.provider,
            "pricing_method": SourceSkuOffering.METHOD_COLLECTED,
            "evidence": offering_evidence(
                source=source,
                sku=model.sku,
                source_url=source_url,
            ),
            "is_active": True,
        },
    )
    changed_fields = []
    if offering.provider_id != model.provider_id:
        offering.provider = model.provider
        changed_fields.append("provider")
    if not offering.is_active:
        offering.is_active = True
        changed_fields.append("is_active")
    evidence = dict(offering.evidence or {})
    evidence.update(
        offering_evidence(
            source=source,
            sku=model.sku,
            source_url=source_url,
        )
    )
    if evidence != (offering.evidence or {}):
        offering.evidence = evidence
        changed_fields.append("evidence")
    if created is False and changed_fields:
        changed_fields.append("updated_at")
        offering.save(update_fields=changed_fields)
    return offering


def source_exposed_model_name(
    item: CollectedModelPricing,
    sku: ModelSku | None,
) -> str:
    """Return the model name exposed by this source for routing."""
    raw_detail = item.raw_detail or {}
    model_info = raw_detail.get("model_info") or {}
    if not isinstance(model_info, dict):
        model_info = {}
    for candidate in (
        raw_detail.get("exposed_model_name"),
        raw_detail.get("source_model_id"),
        raw_detail.get("published_model_id"),
        raw_detail.get("model_id"),
        model_info.get("exposed_model_name"),
        model_info.get("source_model_id"),
        model_info.get("model_id"),
        item.model_id,
        sku.canonical_sku_code if sku else "",
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def upsert_legacy_model_for_offering(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    offering: SourceSkuOffering,
    source_url: str,
) -> LLMModel | None:
    """Keep the legacy model table in sync for existing API consumers."""
    model_code = collected_model_code(item)
    provider = offering.provider
    meta_model = offering.sku.meta_model
    defaults = model_defaults_from_collected_item(
        item,
        source=source,
        source_url=source_url,
    )
    defaults["source"] = source
    defaults["sku"] = offering.sku
    defaults["meta_model"] = meta_model
    defaults["price_role"] = price_role_for_source(
        source,
        meta_model=meta_model,
    )

    if source.updates_model_prices:
        lookup = {
            "provider": provider,
            "source": source,
            "code": model_code,
        }
        model = LLMModel.objects.filter(**lookup).first()
        if model is None:
            model = legacy_official_model_for_provider_source(
                provider=provider,
                source=source,
                code=model_code,
            )
        if model is None:
            return LLMModel.objects.create(**{**lookup, **defaults})
        previous_source_id = model.source_id
        changed_fields = update_model_from_defaults(model, defaults)
        if changed_fields:
            changed_fields.append("updated_at")
            model.save(update_fields=changed_fields)
        close_legacy_current_price_items(
            model=model,
            previous_source_id=previous_source_id,
            source=source,
        )
        return model

    model = find_aggregated_model(
        provider=provider,
        code=model_code,
        meta_model=meta_model,
        source=source,
    )
    if model is None:
        create_defaults = model_identity_defaults_from_collected_item(item)
        create_defaults["meta_model"] = meta_model
        create_defaults["sku"] = offering.sku
        create_defaults["price_role"] = price_role_for_source(
            source,
            meta_model=meta_model,
        )
        return LLMModel.objects.create(
            provider=provider,
            code=model_code,
            **create_defaults,
        )

    changed_fields = update_aggregated_model_identity(
        model,
        meta_model=meta_model,
        name=item.name or item.model_id,
        modality=modality_from_source_type(item.source_model_type),
        currency=item.currency or source.currency or "USD",
        current_source=source,
    )
    if model.sku_id != offering.sku_id:
        model.sku = offering.sku
        changed_fields.append("sku")
    if changed_fields:
        changed_fields.append("updated_at")
        model.save(update_fields=changed_fields)
    return model


def close_legacy_current_price_items(
    *,
    model: LLMModel,
    previous_source_id: int | None,
    source: PriceCollectionSource,
) -> None:
    """Close current legacy price items after moving a model source."""
    if previous_source_id in {None, source.id}:
        return
    ModelPriceItem.objects.filter(
        model=model,
        source_id=previous_source_id,
        is_current=True,
    ).update(
        is_current=False,
        effective_to=timezone.now(),
    )


def legacy_model_for_offering(
    offering: SourceSkuOffering,
) -> LLMModel | None:
    """Return the legacy model row linked to an offering, when present."""
    return (
        LLMModel.objects.filter(
            provider=offering.provider,
            source=offering.source,
            sku=offering.sku,
        )
        .order_by("id")
        .first()
    )


def offering_evidence(
    *,
    source: PriceCollectionSource,
    sku: ModelSku | None,
    source_url: str,
) -> dict:
    """Return evidence proving a source offers one SKU."""
    return {
        "source_id": source.id,
        "source_slug": source.slug,
        "source_url": source_url,
        "sku_id": sku.id if sku else None,
        "sku_code": sku.canonical_sku_code if sku else "",
    }


def legacy_official_model_for_provider_source(
    *,
    provider: LLMProvider,
    source: PriceCollectionSource,
    code: str,
) -> LLMModel | None:
    """Return an existing model row that should move to provider source."""
    official_owner_types = (
        PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL,
        PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL,
    )
    official_model = (
        LLMModel.objects.filter(
            provider=provider,
            code=code,
            source__source_owner_type__in=official_owner_types,
        )
        .exclude(source=source)
        .order_by("id")
        .first()
    )
    if official_model is not None:
        return official_model

    legacy_official_model = (
        LLMModel.objects.filter(
            provider=provider,
            code=code,
            source__source_owner_type=(
                PriceCollectionSource.SOURCE_OWNER_UNKNOWN
            ),
            source__source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        .exclude(source=source)
        .order_by("id")
        .first()
    )
    if legacy_official_model is not None:
        return legacy_official_model

    return (
        LLMModel.objects.filter(
            provider=provider,
            code=code,
            source__isnull=True,
        )
        .order_by("id")
        .first()
    )


def update_model_from_defaults(model: LLMModel, defaults: dict) -> list[str]:
    """Apply update_or_create defaults to an existing model instance."""
    changed_fields = []
    for field, value in defaults.items():
        if getattr(model, field) == value:
            continue
        setattr(model, field, value)
        changed_fields.append(field)
    return changed_fields


def existing_meta_model_for_collected_item(
    item: CollectedModelPricing,
) -> MetaModel | None:
    """Resolve a collected price row to an existing canonical meta model."""
    model_code = collected_model_code(item)
    raw_code = collected_model_raw_code(item)
    reported_name = item.name or item.model_id
    source_code = str(raw_code or model_code or reported_name).strip()
    identity = canonical_meta_model_identity(source_code, reported_name)
    meta_model = MetaModel.objects.filter(code=identity["code"]).first()
    if meta_model is not None:
        return meta_model
    return match_meta_model_by_alias_or_name(
        raw_code=raw_code,
        reported_code=model_code,
        reported_name=reported_name,
        canonical_code=identity["code"],
        canonical_name=identity["name"],
        seed_aliases=identity["aliases"],
    )


def collected_model_code(item: CollectedModelPricing) -> str:
    """Return the most stable model code reported by a collector."""
    for candidate in (
        item.model_id,
        collected_model_raw_code(item),
        item.name,
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def collected_model_raw_code(item: CollectedModelPricing) -> str:
    """Extract the raw upstream model code from collector payloads."""
    raw_detail = item.raw_detail or {}
    model_info = raw_detail.get("model_info") or {}
    if not isinstance(model_info, dict):
        model_info = {}

    for candidate in (
        raw_detail.get("model_id"),
        raw_detail.get("model_code"),
        raw_detail.get("code"),
        raw_detail.get("id"),
        model_info.get("model_id"),
        model_info.get("model_code"),
        model_info.get("code"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def resolve_collected_provider(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
) -> LLMProvider:
    """Resolve the provider row a collected model should attach to."""
    if source.provider_id and source_owner_type_for_source(source) in (
        PriceCollectionSource.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL,
        PriceCollectionSource.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL,
    ):
        return source.provider

    candidate_labels = [
        item.provider,
        item.raw_detail.get("model_info", {}).get("provider"),
        item.model_source,
    ]
    matched = match_existing_provider(candidate_labels)
    if matched is not None:
        return matched

    provider_name = next(
        (
            str(label).strip()
            for label in candidate_labels
            if str(label or "").strip()
        ),
        "Unknown",
    )
    provider, _ = LLMProvider.objects.get_or_create(
        code=slugify_provider(provider_name),
        defaults={
            "name": provider_name,
            "is_active": True,
        },
    )
    return provider


def match_existing_provider(labels: list[str | None]) -> LLMProvider | None:
    """Return an existing provider whose aliases match one label."""
    normalized_labels = {
        normalize_provider_label(label)
        for label in labels
        if normalize_provider_label(label)
    }
    if not normalized_labels:
        return None

    for provider in LLMProvider.objects.all().order_by("id"):
        aliases = provider_aliases(provider)
        if aliases & normalized_labels:
            return provider
    return None


def upsert_collected_snapshot(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    run: PriceCollectionRun,
    offering: SourceSkuOffering,
) -> tuple[CollectedModelPriceSnapshot, bool]:
    """Persist the latest normalized source payload for one offering."""
    rows = normalized_rows_payload(item)
    payload = collected_payload(
        item,
        run=run,
        offering=offering,
        rows=rows,
    )
    fingerprint = price_fingerprint(payload)
    existing = CollectedModelPriceSnapshot.objects.filter(
        source=source,
        offering=offering,
        source_platform_id=str(item.platform_id),
    ).first()
    changed = existing is None or existing.price_fingerprint != fingerprint
    has_matching_history = collected_price_history_exists(
        source=source,
        offering=offering,
        source_platform_id=str(item.platform_id),
        price_hash=fingerprint,
    )
    if existing is None and has_matching_history:
        changed = False
    if existing is None or changed:
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
        offering=offering,
        source_platform_id=str(item.platform_id),
        defaults=payload,
    )
    return snapshot, changed


def collected_price_history_exists(
    *,
    source: PriceCollectionSource,
    offering: SourceSkuOffering,
    source_platform_id: str,
    price_hash: str,
) -> bool:
    """Return whether one collected history fingerprint already exists."""
    return CollectedModelPriceHistory.objects.filter(
        source=source,
        offering=offering,
        source_platform_id=source_platform_id,
        price_fingerprint=price_hash,
    ).exists()


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
    offering: SourceSkuOffering,
    rows: list[dict],
) -> dict:
    """Build common collected price payload fields."""
    return {
        "run": run,
        "provider": offering.provider,
        "model": legacy_model_for_offering(offering),
        "sku": offering.sku,
        "offering": offering,
        "meta_model": offering.sku.meta_model,
        "source_model_id": collected_model_code(item),
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
    lookup = {
        "source": source,
        "offering": payload["offering"],
        "source_platform_id": source_platform_id,
        "price_fingerprint": price_hash,
    }
    existing_history = CollectedModelPriceHistory.objects.filter(
        **lookup,
    ).first()
    if existing_history is not None:
        return activate_collected_price_history(
            existing_history,
            source=source,
            offering=payload["offering"],
            source_platform_id=source_platform_id,
            now=now,
        )

    CollectedModelPriceHistory.objects.filter(
        source=source,
        offering=payload["offering"],
        source_platform_id=source_platform_id,
        is_current=True,
    ).update(
        is_current=False,
        effective_to=now,
    )
    try:
        with transaction.atomic():
            return CollectedModelPriceHistory.objects.create(
                source=source,
                run=payload["run"],
                provider=payload["provider"],
                model=payload["model"],
                sku=payload["sku"],
                offering=payload["offering"],
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
    except IntegrityError:
        existing_history = CollectedModelPriceHistory.objects.get(**lookup)
        return activate_collected_price_history(
            existing_history,
            source=source,
            offering=payload["offering"],
            source_platform_id=source_platform_id,
            now=now,
        )


def activate_collected_price_history(
    history: CollectedModelPriceHistory,
    *,
    source: PriceCollectionSource,
    offering: SourceSkuOffering,
    source_platform_id: str,
    now,
) -> CollectedModelPriceHistory:
    """Make one existing collected history row current."""
    CollectedModelPriceHistory.objects.filter(
        source=source,
        offering=offering,
        source_platform_id=source_platform_id,
        is_current=True,
    ).exclude(id=history.id).update(
        is_current=False,
        effective_to=now,
    )
    if not history.is_current or history.effective_to is not None:
        history.is_current = True
        history.effective_to = None
        history.save(update_fields=["is_current", "effective_to"])
    return history


def close_stale_current_collected_prices(
    *,
    source: PriceCollectionSource,
    active_offering_ids: set[int],
) -> dict[str, int]:
    """Close current collected rows for offerings absent from a fresh sync."""
    now = timezone.now()
    price_items = ModelPriceItem.objects.filter(
        source=source,
        is_current=True,
    )
    history = CollectedModelPriceHistory.objects.filter(
        source=source,
        is_current=True,
    )
    if active_offering_ids:
        price_items = price_items.exclude(offering_id__in=active_offering_ids)
        history = history.exclude(offering_id__in=active_offering_ids)
    closed_price_item_ids = list(price_items.values_list("id", flat=True))
    closed_price_items = price_items.update(
        is_current=False,
        effective_to=now,
    )
    closed_history = history.update(
        is_current=False,
        effective_to=now,
    )
    return {
        "price_items": closed_price_items,
        "price_item_ids": closed_price_item_ids,
        "history": closed_history,
    }


def sync_model_price_items(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    offering: SourceSkuOffering,
    source_url: str,
) -> list[ModelPriceItem]:
    """Persist normalized official price items for display and comparison."""
    payloads = model_price_item_payloads(
        item,
        source=source,
        offering=offering,
        source_url=source_url,
    )
    if not payloads:
        return []

    now = timezone.now()
    current_filter = {
        "offering": offering,
        "source": source,
        "is_current": True,
    }
    items = []
    with transaction.atomic():
        old_current_ids = set(
            ModelPriceItem.objects.filter(**current_filter).values_list(
                "id",
                flat=True,
            )
        )
        for payload in payloads:
            fingerprint = model_price_item_fingerprint(payload)
            payload["price_fingerprint"] = fingerprint
            price_item, _ = ModelPriceItem.objects.update_or_create(
                offering=offering,
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
            items.append(price_item)

        current_item_ids = {price_item.id for price_item in items}
        stale_item_ids = old_current_ids - current_item_ids
        if stale_item_ids:
            ModelPriceItem.objects.filter(id__in=stale_item_ids).update(
                is_current=False,
                effective_to=now,
            )
    return items


def model_price_item_payloads(
    item: CollectedModelPricing,
    *,
    source: PriceCollectionSource,
    offering: SourceSkuOffering,
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
                offering=offering,
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
    offering: SourceSkuOffering,
    source_url: str,
    row_index: int,
) -> list[dict]:
    """Convert one normalized row into one or more price item payloads."""
    values = row.values or {}
    sku = offering.sku
    common = {
        "provider": offering.provider,
        "sku": sku,
        "offering": offering,
        "model": legacy_model_for_offering(offering),
        "meta_model": sku.meta_model,
        "source": source,
        "price_role": price_role_for_source(
            source,
            meta_model=sku.meta_model,
        ),
        "currency": row_price_currency(item, row, source),
        "source_url": source_url,
        "raw_payload": {
            "kind": row.kind,
            "values": values,
            "raw": row.raw,
            "row_index": row_index,
        },
    }

    if row.kind in {"text_token", "text_unit"}:
        return token_price_item_payloads(
            item,
            values,
            common,
            spec=row_price_spec(row),
        )
    if row.kind == "image_token":
        return image_token_price_item_payloads(item, values, common)
    if row.kind in {"image_size", "image_unit"}:
        price = first_decimal_from_row(values, "unit_price", "price")
        spec = {}
        if values.get("image_size"):
            spec["size"] = values.get("image_size")
        return (
            [
                price_item_payload(
                    common,
                    dimension=ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
                    billing_unit=ModelPriceItem.UNIT_PER_IMAGE,
                    unit_price=price,
                    spec=spec,
                )
            ]
            if price is not None
            else []
        )
    if row.kind == "video_resolution_input":
        return video_resolution_input_payloads(values, common)
    if row.kind == "video_resolution_output":
        return video_resolution_output_payloads(values, common)
    if row.kind == "video_inference":
        return video_inference_payloads(values, common)
    if row.kind == "video_unit":
        price = first_decimal_from_row(values, "unit_price", "price")
        return (
            [
                price_item_payload(
                    common,
                    dimension=ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
                    billing_unit=ModelPriceItem.UNIT_PER_SECOND,
                    unit_price=price,
                )
            ]
            if price is not None
            else []
        )
    return []


def token_price_item_payloads(
    item: CollectedModelPricing,
    values: dict,
    common: dict,
    *,
    spec: dict | None = None,
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
    cache_price = first_decimal_from_row(values, *CACHE_INPUT_PRICE_KEYS)
    input_range = parse_price_range(values.get("input_token_range"))
    output_range = parse_price_range(values.get("output_token_range"))
    if input_price is not None:
        payloads.append(
            price_item_payload(
                common,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                unit_price=price_per_million(input_price, item.unit),
                spec=spec,
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
                spec=spec,
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
                spec=spec,
                tier_start=input_range[0],
                tier_end=input_range[1],
            )
        )
    return payloads


def row_price_currency(
    item: CollectedModelPricing,
    row,
    source: PriceCollectionSource,
) -> str:
    """Return row-specific currency, falling back to item/source currency."""
    values = row.values or {}
    raw = row.raw or {}
    return str(
        values.get("currency")
        or raw.get("currency")
        or item.currency
        or source.currency
        or "USD"
    ).upper()


def row_price_spec(row) -> dict:
    """Return display/audit metadata that distinguishes price variants."""
    values = row.values or {}
    raw = row.raw or {}
    spec = {}
    for key in (
        "currency",
        "deployment_scope",
        "region",
        "market",
        "billing_scope",
    ):
        value = values.get(key) or raw.get(key)
        if value:
            spec[key] = value
    return spec


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
        "sku": payload.get("sku").id if payload.get("sku") else None,
        "offering": (
            payload.get("offering").id if payload.get("offering") else None
        ),
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
        "image_output_price_per_image": prices["image_output_price_per_image"],
        "video_input_price_per_second": prices["video_input_price_per_second"],
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
) -> dict:
    """Build model defaults that do not promote collected prices."""
    return {
        "name": item.name or item.model_id,
        "modality": modality_from_source_type(item.source_model_type),
        "currency": normalize_currency(item.currency or "USD"),
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

    cache_price = first_decimal_value(item, *CACHE_INPUT_PRICE_KEYS)
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
            "source_owner_type": PriceCollectionSource.SOURCE_OWNER_SUPPLIER,
            "collection_method": (
                PriceCollectionSource.COLLECTION_METHOD_API_SYNC
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
    owner_type = source_owner_type_for_provider(provider)
    source, created = PriceCollectionSource.objects.get_or_create(
        slug=f"{provider.code}-official",
        defaults={
            "provider": provider,
            "name": f"{provider.name} 官方价格",
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            "source_owner_type": owner_type,
            "collection_method": (
                PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
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
        "source_owner_type": owner_type,
        "collection_method": (
            PriceCollectionSource.COLLECTION_METHOD_AUTO_COLLECT
        ),
        "currency": config.currency,
        "updates_model_prices": True,
        "notes": (
            "官方公开价格采集源；价格按官方币种入库，"
            "不做跨币种换算。"
        ),
    }
    if not source.endpoint_url or is_legacy_official_pricing_url(
        provider.code,
        source.endpoint_url,
    ):
        desired_fields["endpoint_url"] = config.source_url
    for field, value in desired_fields.items():
        if getattr(source, field) != value:
            setattr(source, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        source.save(update_fields=changed_fields)
    return source


def ensure_manual_official_source(*, provider: LLMProvider):
    """Ensure an official source exists without backend collection code."""
    provider_code = provider.code
    owner_type = source_owner_type_for_provider(provider)
    source_slug = official_provider_source_slug(provider_code)
    source_name = official_provider_source_name(provider, provider_code)
    source, created = PriceCollectionSource.objects.get_or_create(
        slug=source_slug,
        defaults={
            "provider": provider,
            "name": source_name,
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            "source_owner_type": owner_type,
            "collection_method": (
                PriceCollectionSource.COLLECTION_METHOD_UNKNOWN
            ),
            "endpoint_url": official_provider_source_url(provider_code),
            "currency": official_provider_currency(provider_code),
            "is_enabled": True,
            "updates_model_prices": True,
            "notes": (
                "官方公开价格页；当前仅作为"
                "价格源记录维护。"
            ),
        },
    )
    if created:
        return source

    desired_fields = {
        "provider": provider,
        "name": source_name,
        "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
        "source_category": (
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ),
        "source_owner_type": owner_type,
        "collection_method": PriceCollectionSource.COLLECTION_METHOD_UNKNOWN,
        "currency": official_provider_currency(provider_code),
        "updates_model_prices": True,
    }
    if not source.endpoint_url:
        desired_fields["endpoint_url"] = official_provider_source_url(
            provider_code,
        )

    changed_fields = []
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
    *keys: str,
) -> Decimal | None:
    """Return the first decimal value for a normalized row key."""
    for row in item.price_rows:
        value = first_decimal_from_row(row.values, *keys)
        if value is not None:
            return value
    return None


def first_decimal_from_row(
    values: dict,
    *keys: str,
) -> Decimal | None:
    """Return the first decimal value from a row dictionary."""
    normalized_values = {
        normalize_price_key(key): value for key, value in values.items()
    }
    for key in keys:
        value = to_decimal(values.get(key))
        if value is None:
            value = to_decimal(normalized_values.get(normalize_price_key(key)))
        if value is not None:
            return value
    return None


def normalize_price_key(value) -> str:
    """Normalize provider-specific price labels to comparable keys."""
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


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
