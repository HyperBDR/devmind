from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from .collection_services import (
    ensure_official_source,
    sync_configured_official_model_prices,
)
from .collectors.official import (
    MODELS_DEV_API_URL,
    MODELS_DEV_PROVIDER_KEYS,
    OFFICIAL_PROVIDER_CONFIGS,
)
from .constants import (
    SUPPLIER_SOURCE_VENDOR_ALIASES,
    canonical_meta_model_identity,
    canonical_vendor_for_model_code,
    ensure_canonical_vendor_row,
    is_canonical_vendor_code,
    resolve_meta_model_vendor,
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
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    UsageReconciliationRecord,
)
from .services import (
    ensure_meta_model,
    price_role_for_source,
    stable_fingerprint,
)


SERVICE_ACCESS_URL = "https://llm.guohe-sh.com"
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
CONFIRMED_SUPPLIER_SHEET_SOURCE_CODES = (
    "aliyun",
    "volcengine",
    "siliconflow",
)
TREND_DEMO_SOURCE_SLUGS = (
    f"{REAL_RESOURCE_CHANNEL_CODE}-trend-demo",
    f"{DEMO_BASELINE_SUPPLIER_CHANNEL_CODE}-trend-demo",
    "demo-premium-supplier-trend-demo",
    "demo-backup-supplier-trend-demo",
)
TREND_DEMO_HISTORY_POINTS = {
    DEMO_BASELINE_SUPPLIER_CHANNEL_CODE: (
        ("2026-01-01", Decimal("0.150000"), Decimal("0.600000")),
        ("2026-02-01", Decimal("0.145000"), Decimal("0.570000")),
        ("2026-03-01", Decimal("0.138000"), Decimal("0.540000")),
        ("2026-04-01", Decimal("0.132000"), Decimal("0.520000")),
        ("2026-05-01", Decimal("0.128000"), Decimal("0.500000")),
    ),
    "demo-premium-supplier": (
        ("2026-01-01", Decimal("0.165000"), Decimal("0.640000")),
        ("2026-02-01", Decimal("0.152000"), Decimal("0.590000")),
        ("2026-03-01", Decimal("0.130000"), Decimal("0.505000")),
        ("2026-04-01", Decimal("0.118000"), Decimal("0.470000")),
        ("2026-05-01", Decimal("0.112000"), Decimal("0.450000")),
    ),
    "demo-backup-supplier": (
        ("2026-01-01", Decimal("0.120000"), Decimal("0.700000")),
        ("2026-02-01", Decimal("0.118000"), Decimal("0.665000")),
        ("2026-03-01", Decimal("0.140000"), Decimal("0.610000")),
        ("2026-04-01", Decimal("0.155000"), Decimal("0.580000")),
        ("2026-05-01", Decimal("0.160000"), Decimal("0.560000")),
    ),
}


@dataclass(frozen=True)
class ProviderSheetEntry:
    """One vendor section from the initial operations price sheet.

    ``provider_*`` identifies the canonical model vendor (OpenAI,
    Anthropic, Google, Alibaba, DeepSeek, etc.). ``source_*`` is only
    for the price source / supplier that supplied this sheet. A source
    such as SiliconFlow or OpenRouter must not become a model vendor.
    """

    group_name: str
    provider_name: str
    provider_code: str
    upstream_url: str
    currency: str
    discount: Decimal
    models: tuple[str, ...]
    source_name: str = ""
    source_code: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class YunceSupplierPriceEntry:
    """One mock Yunce supplier price for a concrete provider/model pair."""

    provider_code: str
    model_code: str
    upstream_name: str
    currency: str
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    image_output_price: Decimal | None = None
    audio_input_price: Decimal | None = None
    audio_output_price: Decimal | None = None
    video_input_price: Decimal | None = None
    video_output_price: Decimal | None = None


@dataclass(frozen=True)
class MetaModelSeedInfo:
    """Human-readable canonical metadata for one model family."""

    name: str
    family: str
    modality: str
    context_window: int = 0
    max_output_tokens: int = 0
    aliases: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()


PRICE_SHEET_ENTRIES = (
    ProviderSheetEntry(
        group_name="GPT",
        provider_name="OpenAI",
        provider_code="openai",
        upstream_url="https://{resource-name}.openai.azure.com/",
        currency="USD",
        discount=Decimal("0.55"),
        models=(
            "gpt-5.4-pro",
            "gpt-5.4",
            "gpt-5.3-codex",
            "gpt-5.3-chat",
            "gpt-5.2-chat",
            "gpt-5.2-codex",
            "gpt-5.2",
            "gpt-5.1-codex-max",
            "gpt-5.1-codex-mini",
            "gpt-5.1-codex",
            "gpt-5.1-chat",
            "gpt-5.1",
            "gpt-5-pro",
            "gpt-5-codex",
            "gpt-5-chat",
            "gpt-5-nano",
            "gpt-5-mini",
            "gpt-5",
            "gpt-5.5",
            "o3-pro",
            "text-embedding-3-large",
            "text-embedding-3-small",
            "text-embedding-ada-002",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4.1-nano",
            "o3",
            "o4-mini",
            "o3-mini",
            "o1",
            "gpt-4o-mini",
            "gpt-4o",
            "o3-deep-research",
            "gpt-image-1.5",
            "gpt-image-1-mini",
            "gpt-image-2",
        ),
    ),
    ProviderSheetEntry(
        group_name="Claude",
        provider_name="Anthropic",
        provider_code="anthropic",
        upstream_url="https://api.anthropic.com/",
        currency="USD",
        discount=Decimal("0.55"),
        models=(
            "claude-sonnet-4-6-20260218",
            "claude-opus-4-6-20260205",
            "claude-opus-4-5-20251101",
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-opus-4-1-20250805",
        ),
    ),
    ProviderSheetEntry(
        group_name="Gemini",
        provider_name="Google",
        provider_code="google",
        upstream_url="https://{region}-aiplatform.googleapis.com/",
        currency="USD",
        discount=Decimal("0.68"),
        models=(
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-image-preview",
            "gemini-3-pro-image-preview",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ),
    ),
    ProviderSheetEntry(
        group_name="通义千问",
        provider_name="阿里云",
        provider_code="aliyun",
        upstream_url="https://dashscope.aliyuncs.com/",
        currency="CNY",
        discount=Decimal("0.40"),
        models=(
            "deepseek-r1",
            "deepseek-r1-0528",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "qwen3.5-122b-a10b",
            "qwen3.5-27b",
            "qwen3.5-35b-a3b",
            "qwen3.5-397b-a17b",
            "qwen3.5-plus",
            "qwen3.6-max-preview",
            "qwen3.7-max",
            "qwen3.7-max-preview",
            "qwen3-235b-a22b-instruct-2507",
            "qwen3-235b-a22b-thinking-2507",
            "qwen3-30b-a3b",
            "qwen3-30b-a3b-instruct-2507",
            "qwen3-30b-a3b-think",
            "qwen3-30b-a3b-thinking-2507",
            "qwen3-max",
            "qwen3-vl-235b-a22b-instruct",
            "qwen3-vl-235b-a22b-thinking",
            "qwen3-vl-30b-a3b-instruct",
            "qwen3-vl-30b-a3b-thinking",
            "qwen3-vl-32b-thinking",
            "qwen3-vl-plus",
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
            "qwq-32b",
            "text-embedding-v4",
        ),
    ),
    ProviderSheetEntry(
        group_name="WAN",
        provider_name="阿里云万象",
        provider_code="aliyun-wanx",
        upstream_url="https://dashscope.aliyuncs.com/",
        currency="CNY",
        discount=Decimal("0.50"),
        models=(
            "wan2.2-animate-move",
            "qwen-image",
            "qwen-image-edit",
            "qwen-image-edit-plus",
            "qwen-image-plus",
            "wan2.2-i2v-flash",
            "wan2.2-i2v-plus",
            "wan2.2-kf2v-flash",
            "wan2.2-t2v-plus",
            "wan2.5-i2v-preview",
            "wan2.5-t2v-preview",
            "wanx2.1-i2v-plus",
            "wanx2.1-i2v-turbo",
            "wanx2.1-kf2v-plus",
            "wanx2.1-t2v-plus",
            "wanx2.1-t2v-turbo",
        ),
    ),
    ProviderSheetEntry(
        group_name="豆包",
        provider_name="火山",
        provider_code="volcengine",
        upstream_url="https://ark.cn-beijing.volces.com/",
        currency="CNY",
        discount=Decimal("1.00"),
        models=(
            "deepseek-r1",
            "deepseek-r1-250528",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "doubao-seedance-1-0-pro-250528",
            "doubao-seedance-1.5-pro-251215",
            "doubao-2.0sccd",
            "doubao-1.8seed",
        ),
    ),
    ProviderSheetEntry(
        group_name="豆包",
        provider_name="火山",
        provider_code="volcengine",
        upstream_url="https://ark.cn-beijing.volces.com/",
        currency="CNY",
        discount=Decimal("0.70"),
        models=("doubao-seedream-4.0-250828",),
    ),
    ProviderSheetEntry(
        group_name="豆包",
        provider_name="火山",
        provider_code="volcengine",
        upstream_url="https://ark.cn-beijing.volces.com/",
        currency="CNY",
        discount=Decimal("0.75"),
        models=("doubao-seedream-4.5-251128",),
    ),
    ProviderSheetEntry(
        group_name="豆包",
        provider_name="火山",
        provider_code="volcengine",
        upstream_url="https://ark.cn-beijing.volces.com/",
        currency="CNY",
        discount=Decimal("0.95"),
        models=("doubao-seedance-2.0-pro",),
    ),
    ProviderSheetEntry(
        group_name="DeepSeek",
        provider_name="DeepSeek",
        provider_code="deepseek",
        upstream_url="https://api.deepseek.com/",
        currency="CNY",
        discount=Decimal("0.65"),
        models=(
            "deepseek-r1",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ),
        source_name="硅基流动",
        source_code="siliconflow",
        source_url="https://api.siliconflow.cn/",
    ),
)

MODEL_BASE_PRICES = {
    "deepseek-r1": (Decimal("4"), Decimal("16")),
    "deepseek-r1-0528": (Decimal("4"), Decimal("16")),
    "deepseek-r1-250528": (Decimal("4"), Decimal("16")),
    "deepseek-v3": (Decimal("2"), Decimal("8")),
    "deepseek-v3.1": (Decimal("2"), Decimal("8")),
    "deepseek-v3.2": (Decimal("2"), Decimal("8")),
    "deepseek-v3.2-exp": (Decimal("2"), Decimal("8")),
    "qwen-plus": (Decimal("0.8"), Decimal("2")),
}

META_MODEL_EXACT_INFO = {
    "gpt-4o-mini": MetaModelSeedInfo(
        name="GPT-4o mini",
        family="GPT-4o",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=128000,
        max_output_tokens=16384,
        aliases=("GPT-4o mini", "gpt-4o-mini"),
        capabilities=("chat", "vision", "tool_calling"),
    ),
    "gpt-4o": MetaModelSeedInfo(
        name="GPT-4o",
        family="GPT-4o",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=128000,
        max_output_tokens=16384,
        aliases=("GPT-4o", "gpt-4o"),
        capabilities=("chat", "vision", "tool_calling"),
    ),
    "o1": MetaModelSeedInfo(
        name="OpenAI o1",
        family="OpenAI o-series",
        modality=LLMModel.MODALITY_TEXT,
        context_window=200000,
        max_output_tokens=100000,
        aliases=("o1", "OpenAI o1"),
        capabilities=("reasoning", "chat"),
    ),
    "o3": MetaModelSeedInfo(
        name="OpenAI o3",
        family="OpenAI o-series",
        modality=LLMModel.MODALITY_TEXT,
        context_window=200000,
        max_output_tokens=100000,
        aliases=("o3", "OpenAI o3"),
        capabilities=("reasoning", "chat"),
    ),
    "o3-pro": MetaModelSeedInfo(
        name="OpenAI o3 Pro",
        family="OpenAI o-series",
        modality=LLMModel.MODALITY_TEXT,
        context_window=200000,
        max_output_tokens=100000,
        aliases=("o3-pro", "OpenAI o3 Pro"),
        capabilities=("reasoning", "chat"),
    ),
    "o4-mini": MetaModelSeedInfo(
        name="OpenAI o4 mini",
        family="OpenAI o-series",
        modality=LLMModel.MODALITY_TEXT,
        context_window=200000,
        max_output_tokens=100000,
        aliases=("o4-mini", "OpenAI o4 mini"),
        capabilities=("reasoning", "chat"),
    ),
    "text-embedding-3-large": MetaModelSeedInfo(
        name="Text Embedding 3 Large",
        family="OpenAI Embeddings",
        modality=LLMModel.MODALITY_TEXT,
        context_window=8191,
        aliases=("text-embedding-3-large",),
        capabilities=("embedding",),
    ),
    "text-embedding-3-small": MetaModelSeedInfo(
        name="Text Embedding 3 Small",
        family="OpenAI Embeddings",
        modality=LLMModel.MODALITY_TEXT,
        context_window=8191,
        aliases=("text-embedding-3-small",),
        capabilities=("embedding",),
    ),
    "text-embedding-ada-002": MetaModelSeedInfo(
        name="Text Embedding Ada 002",
        family="OpenAI Embeddings",
        modality=LLMModel.MODALITY_TEXT,
        context_window=8191,
        aliases=("text-embedding-ada-002",),
        capabilities=("embedding",),
    ),
    "claude-sonnet-4-5-20250929": MetaModelSeedInfo(
        name="Claude Sonnet 4.5",
        family="Claude Sonnet",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=200000,
        max_output_tokens=64000,
        aliases=("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
        capabilities=("chat", "vision", "tool_calling"),
    ),
    "claude-sonnet-4-20250514": MetaModelSeedInfo(
        name="Claude Sonnet 4",
        family="Claude Sonnet",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=200000,
        max_output_tokens=64000,
        aliases=("Claude Sonnet 4", "claude-sonnet-4-20250514"),
        capabilities=("chat", "vision", "tool_calling"),
    ),
    "claude-opus-4-1-20250805": MetaModelSeedInfo(
        name="Claude Opus 4.1",
        family="Claude Opus",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=200000,
        max_output_tokens=32000,
        aliases=("Claude Opus 4.1", "claude-opus-4-1-20250805"),
        capabilities=("chat", "vision", "tool_calling"),
    ),
    "gemini-2.5-pro": MetaModelSeedInfo(
        name="Gemini 2.5 Pro",
        family="Gemini 2.5",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=1048576,
        max_output_tokens=65536,
        aliases=("Gemini 2.5 Pro", "gemini-2.5-pro"),
        capabilities=("chat", "vision", "long_context"),
    ),
    "gemini-2.5-flash": MetaModelSeedInfo(
        name="Gemini 2.5 Flash",
        family="Gemini 2.5",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=1048576,
        max_output_tokens=65536,
        aliases=("Gemini 2.5 Flash", "gemini-2.5-flash"),
        capabilities=("chat", "vision", "long_context"),
    ),
    "gemini-3-pro-preview": MetaModelSeedInfo(
        name="Gemini 3 Pro Preview",
        family="Gemini 3",
        modality=LLMModel.MODALITY_MULTIMODAL,
        context_window=1048576,
        max_output_tokens=65536,
        aliases=("Gemini 3 Pro Preview", "gemini-3-pro-preview"),
        capabilities=("chat", "vision", "long_context"),
    ),
    "qwen-plus": MetaModelSeedInfo(
        name="Qwen Plus",
        family="Qwen",
        modality=LLMModel.MODALITY_TEXT,
        context_window=131072,
        max_output_tokens=8192,
        aliases=("Qwen Plus", "qwen-plus", "通义千问 Plus"),
        capabilities=("chat", "tool_calling"),
    ),
    "qwen-max": MetaModelSeedInfo(
        name="Qwen Max",
        family="Qwen",
        modality=LLMModel.MODALITY_TEXT,
        context_window=32768,
        max_output_tokens=8192,
        aliases=("Qwen Max", "qwen-max", "通义千问 Max"),
        capabilities=("chat", "tool_calling"),
    ),
    "qwen-turbo": MetaModelSeedInfo(
        name="Qwen Turbo",
        family="Qwen",
        modality=LLMModel.MODALITY_TEXT,
        context_window=1000000,
        max_output_tokens=8192,
        aliases=("Qwen Turbo", "qwen-turbo", "通义千问 Turbo"),
        capabilities=("chat", "long_context"),
    ),
    "deepseek-r1": MetaModelSeedInfo(
        name="DeepSeek R1",
        family="DeepSeek R1",
        modality=LLMModel.MODALITY_TEXT,
        context_window=64000,
        max_output_tokens=8192,
        aliases=("DeepSeek R1", "deepseek-r1"),
        capabilities=("reasoning", "chat"),
    ),
    "deepseek-v3": MetaModelSeedInfo(
        name="DeepSeek V3",
        family="DeepSeek V3",
        modality=LLMModel.MODALITY_TEXT,
        context_window=64000,
        max_output_tokens=8192,
        aliases=("DeepSeek V3", "deepseek-v3"),
        capabilities=("chat",),
    ),
    "deepseek-v3.1": MetaModelSeedInfo(
        name="DeepSeek V3.1",
        family="DeepSeek V3",
        modality=LLMModel.MODALITY_TEXT,
        context_window=128000,
        max_output_tokens=8192,
        aliases=("DeepSeek V3.1", "deepseek-v3.1"),
        capabilities=("chat",),
    ),
    "deepseek-v3.2": MetaModelSeedInfo(
        name="DeepSeek V3.2",
        family="DeepSeek V3",
        modality=LLMModel.MODALITY_TEXT,
        context_window=128000,
        max_output_tokens=8192,
        aliases=("DeepSeek V3.2", "deepseek-v3.2"),
        capabilities=("chat",),
    ),
    "qwen-image": MetaModelSeedInfo(
        name="Qwen Image",
        family="Qwen Image",
        modality=LLMModel.MODALITY_MULTIMODAL,
        aliases=("Qwen Image", "qwen-image"),
        capabilities=("image_generation",),
    ),
    "wan2.5-t2v-preview": MetaModelSeedInfo(
        name="WAN 2.5 T2V Preview",
        family="WAN 2.5",
        modality=LLMModel.MODALITY_VIDEO,
        aliases=("WAN 2.5 T2V Preview", "wan2.5-t2v-preview"),
        capabilities=("video_generation",),
    ),
    "doubao-seedream-4.5-251128": MetaModelSeedInfo(
        name="Doubao Seedream 4.5",
        family="Doubao Seedream",
        modality=LLMModel.MODALITY_MULTIMODAL,
        aliases=("Doubao Seedream 4.5", "doubao-seedream-4.5-251128"),
        capabilities=("image_generation",),
    ),
    "doubao-seedance-2.0-pro": MetaModelSeedInfo(
        name="Doubao Seedance 2.0 Pro",
        family="Doubao Seedance",
        modality=LLMModel.MODALITY_VIDEO,
        aliases=("Doubao Seedance 2.0 Pro", "doubao-seedance-2.0-pro"),
        capabilities=("video_generation",),
    ),
}

YUNCE_SUPPLIER_PRICE_ENTRIES = (
    YunceSupplierPriceEntry(
        provider_code="openai",
        model_code="gpt-4o-mini",
        upstream_name="Azure OpenAI East US 共享池",
        currency="USD",
        input_price=Decimal("0.112000"),
        output_price=Decimal("0.450000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="openai",
        model_code="gpt-4o",
        upstream_name="Azure OpenAI Japan East 标准池",
        currency="USD",
        input_price=Decimal("1.980000"),
        output_price=Decimal("7.920000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="anthropic",
        model_code="claude-sonnet-4-5-20250929",
        upstream_name="Anthropic Direct Priority",
        currency="USD",
        input_price=Decimal("2.640000"),
        output_price=Decimal("13.200000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="google",
        model_code="gemini-2.5-pro",
        upstream_name="Google Vertex AI us-central1",
        currency="USD",
        input_price=Decimal("1.080000"),
        output_price=Decimal("8.640000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="aliyun",
        model_code="qwen-plus",
        upstream_name="阿里云百炼华东专线",
        currency="CNY",
        input_price=Decimal("0.520000"),
        output_price=Decimal("1.280000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="aliyun",
        model_code="deepseek-v3",
        upstream_name="阿里云百炼 DeepSeek 专线",
        currency="CNY",
        input_price=Decimal("1.320000"),
        output_price=Decimal("5.280000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="volcengine",
        model_code="deepseek-v3",
        upstream_name="火山方舟 DeepSeek 共享池",
        currency="CNY",
        input_price=Decimal("1.180000"),
        output_price=Decimal("4.720000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="deepseek",
        model_code="deepseek-v3",
        upstream_name="硅基流动华北低延迟池",
        currency="CNY",
        input_price=Decimal("1.050000"),
        output_price=Decimal("4.200000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="aliyun-wanx",
        model_code="qwen-image",
        upstream_name="阿里云万相图片生成池",
        currency="CNY",
        image_output_price=Decimal("0.160000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="aliyun-wanx",
        model_code="wan2.2-i2v-plus",
        upstream_name="阿里云万相视频高清池",
        currency="CNY",
        video_input_price=Decimal("0.000000"),
        video_output_price=Decimal("0.520000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="volcengine",
        model_code="doubao-seedream-4.5-251128",
        upstream_name="火山即梦图片标准池",
        currency="CNY",
        image_output_price=Decimal("0.135000"),
    ),
    YunceSupplierPriceEntry(
        provider_code="volcengine",
        model_code="doubao-seedance-2.0-pro",
        upstream_name="火山即梦视频 Pro 池",
        currency="CNY",
        video_input_price=Decimal("0.000000"),
        video_output_price=Decimal("0.460000"),
    ),
)


def modality_for_model(model_code: str) -> str:
    """Infer a coarse model modality from its code."""
    lowered = model_code.lower()
    if "embedding" in lowered:
        return LLMModel.MODALITY_TEXT
    if any(token in lowered for token in ("seedance", "wan", "i2v", "t2v")):
        return LLMModel.MODALITY_VIDEO
    if any(token in lowered for token in ("image", "seedream")):
        return LLMModel.MODALITY_MULTIMODAL
    return LLMModel.MODALITY_TEXT


def meta_model_info_for_entry(
    entry: ProviderSheetEntry,
    model_code: str,
) -> MetaModelSeedInfo:
    """Return seeded canonical metadata for one price-sheet model."""
    if model_code in META_MODEL_EXACT_INFO:
        return META_MODEL_EXACT_INFO[model_code]

    modality = modality_for_model(model_code)
    if model_code.startswith("gpt-image-"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"gpt"}),
            family="GPT Image",
            modality=LLMModel.MODALITY_MULTIMODAL,
            aliases=(model_code,),
            capabilities=("image_generation",),
        )
    if model_code.startswith("gpt-"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"gpt"}),
            family=openai_gpt_family(model_code),
            modality=modality,
            context_window=128000,
            max_output_tokens=16384,
            aliases=(model_code,),
            capabilities=("chat", "tool_calling"),
        )
    if model_code.startswith("claude-"):
        return MetaModelSeedInfo(
            name=title_model_code(
                model_code_without_date(model_code),
                uppercase_tokens={"claude"},
            ),
            family=claude_family(model_code),
            modality=LLMModel.MODALITY_MULTIMODAL,
            context_window=200000,
            max_output_tokens=32000,
            aliases=(model_code,),
            capabilities=("chat", "vision", "tool_calling"),
        )
    if model_code.startswith("gemini-"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"gemini"}),
            family=gemini_family(model_code),
            modality=LLMModel.MODALITY_MULTIMODAL,
            context_window=1048576,
            max_output_tokens=65536,
            aliases=(model_code,),
            capabilities=("chat", "vision", "long_context"),
        )
    if model_code.startswith("qwen"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"qwen"}),
            family=qwen_family(model_code),
            modality=modality,
            context_window=131072,
            max_output_tokens=8192,
            aliases=(model_code,),
            capabilities=qwen_capabilities(model_code),
        )
    if model_code.startswith("deepseek-"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"deepseek"}),
            family=deepseek_family(model_code),
            modality=LLMModel.MODALITY_TEXT,
            context_window=128000 if "v3.2" in model_code else 64000,
            max_output_tokens=8192,
            aliases=(model_code,),
            capabilities=deepseek_capabilities(model_code),
        )
    if model_code.startswith(("wan", "wanx")):
        return MetaModelSeedInfo(
            name=title_model_code(
                model_code,
                uppercase_tokens={"wan", "wanx"},
            ),
            family=wan_family(model_code),
            modality=LLMModel.MODALITY_VIDEO,
            aliases=(model_code,),
            capabilities=("video_generation",),
        )
    if model_code.startswith("doubao-"):
        return MetaModelSeedInfo(
            name=title_model_code(model_code, uppercase_tokens={"doubao"}),
            family=doubao_family(model_code),
            modality=modality,
            aliases=(model_code,),
            capabilities=doubao_capabilities(model_code),
        )
    return MetaModelSeedInfo(
        name=title_model_code(model_code),
        family=entry.group_name,
        modality=modality,
        aliases=(model_code,),
        capabilities=("chat",),
    )


def apply_meta_model_seed_info(
    meta_model,
    info: MetaModelSeedInfo,
    provider: LLMProvider,
    entry: ProviderSheetEntry,
) -> None:
    """Persist richer metadata on the canonical model entity.

    ``MetaModel.vendor`` is always the company that built the
    model, never the supplier that priced the row. We resolve the
    canonical vendor from the model code and only fall back to the
    price-sheet provider when the code does not match a known
    rule. Manually-maintained vendor assignments are preserved.
    """
    capabilities = {
        "features": list(info.capabilities),
        "modalities": capability_modalities(info),
    }
    metadata = {
        **(meta_model.metadata or {}),
        "seed_source": "llm_ops_price_sheet",
        "price_sheet_group": entry.group_name,
        "provider_code": provider.code,
    }
    canonical_vendor = resolve_meta_model_vendor(
        meta_model,
        info,
        provider,
    )
    identity = canonical_meta_model_identity(meta_model.code, info.name)
    aliases = set(meta_model.aliases or [])
    aliases.update(info.aliases)
    aliases.update(identity["aliases"])
    updates = {
        "name": identity["name"],
        "family": info.family,
        "vendor": canonical_vendor,
        "modality": info.modality,
        "aliases": sorted(alias for alias in aliases if alias),
        "capabilities": capabilities,
        "metadata": metadata,
    }
    if info.context_window:
        updates["context_window"] = info.context_window
    if info.max_output_tokens:
        updates["max_output_tokens"] = info.max_output_tokens

    changed_fields = []
    for field, value in updates.items():
        if getattr(meta_model, field) != value:
            setattr(meta_model, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        meta_model.save(update_fields=changed_fields)


def capability_modalities(info: MetaModelSeedInfo) -> list[str]:
    """Return UI-friendly modality tags for a seeded meta model."""
    if info.modality == LLMModel.MODALITY_VIDEO:
        return ["text", "image", "video"]
    if "image_generation" in info.capabilities:
        return ["text", "image"]
    if info.modality == LLMModel.MODALITY_MULTIMODAL:
        return ["text", "image"]
    return ["text"]


def title_model_code(
    model_code: str,
    *,
    uppercase_tokens: set[str] | None = None,
) -> str:
    """Turn a model code into a readable display name."""
    uppercase_tokens = uppercase_tokens or set()
    parts = model_code.replace(".", " ").replace("-", " ").split()
    display_parts = []
    for part in parts:
        lowered = part.lower()
        if lowered in uppercase_tokens:
            display_parts.append(lowered.upper())
        elif lowered in {"vl", "t2v", "i2v", "kf2v", "r1", "v3"}:
            display_parts.append(lowered.upper())
        else:
            display_parts.append(part.capitalize())
    return " ".join(display_parts)


def model_code_without_date(model_code: str) -> str:
    """Remove a trailing date-like suffix from a model code."""
    parts = model_code.split("-")
    if parts and parts[-1].isdigit() and len(parts[-1]) == 8:
        return "-".join(parts[:-1])
    return model_code


def openai_gpt_family(model_code: str) -> str:
    """Return a GPT family label for one OpenAI model code."""
    if model_code.startswith("gpt-5.4"):
        return "GPT-5.4"
    if model_code.startswith("gpt-5.3"):
        return "GPT-5.3"
    if model_code.startswith("gpt-5.2"):
        return "GPT-5.2"
    if model_code.startswith("gpt-5.1"):
        return "GPT-5.1"
    if model_code.startswith("gpt-5"):
        return "GPT-5"
    if model_code.startswith("gpt-4.1"):
        return "GPT-4.1"
    return "GPT"


def claude_family(model_code: str) -> str:
    """Return a Claude family label for one model code."""
    if "opus" in model_code:
        return "Claude Opus"
    if "sonnet" in model_code:
        return "Claude Sonnet"
    if "haiku" in model_code:
        return "Claude Haiku"
    return "Claude"


def gemini_family(model_code: str) -> str:
    """Return a Gemini family label for one model code."""
    if model_code.startswith("gemini-3"):
        return "Gemini 3"
    if model_code.startswith("gemini-2.5"):
        return "Gemini 2.5"
    return "Gemini"


def qwen_family(model_code: str) -> str:
    """Return a Qwen family label for one model code."""
    if model_code.startswith("qwen3.5"):
        return "Qwen 3.5"
    if model_code.startswith("qwen3-vl"):
        return "Qwen 3 VL"
    if model_code.startswith("qwen3"):
        return "Qwen 3"
    if model_code.startswith("qwen-image"):
        return "Qwen Image"
    return "Qwen"


def qwen_capabilities(model_code: str) -> tuple[str, ...]:
    """Return Qwen feature tags."""
    if "vl" in model_code:
        return ("chat", "vision")
    if "image" in model_code:
        return ("image_generation",)
    if "thinking" in model_code or "think" in model_code:
        return ("reasoning", "chat")
    return ("chat", "tool_calling")


def deepseek_family(model_code: str) -> str:
    """Return a DeepSeek family label for one model code."""
    if "r1" in model_code:
        return "DeepSeek R1"
    return "DeepSeek V3"


def deepseek_capabilities(model_code: str) -> tuple[str, ...]:
    """Return DeepSeek feature tags."""
    if "r1" in model_code:
        return ("reasoning", "chat")
    return ("chat",)


def wan_family(model_code: str) -> str:
    """Return a WAN family label for one model code."""
    if model_code.startswith("wan2.5"):
        return "WAN 2.5"
    if model_code.startswith("wan2.2"):
        return "WAN 2.2"
    return "WAN 2.1"


def doubao_family(model_code: str) -> str:
    """Return a Doubao media family label for one model code."""
    if "seedream" in model_code:
        return "Doubao Seedream"
    if "seedance" in model_code:
        return "Doubao Seedance"
    return "Doubao"


def doubao_capabilities(model_code: str) -> tuple[str, ...]:
    """Return Doubao feature tags."""
    if "seedream" in model_code:
        return ("image_generation",)
    if "seedance" in model_code:
        return ("video_generation",)
    return ("chat",)


def _seed_initial_price_sheet_core(
    preserve_manual_overrides: bool = False,
) -> dict[str, int]:
    """Import the initial operations price sheet into LLM Ops tables."""
    stats = {
        "providers": 0,
        "sources": 0,
        "models": 0,
        "model_price_items": 0,
        "channel_model_prices": 0,
        "yunce_supplier_sources": 0,
        "yunce_supplier_prices": 0,
        "yunce_supplier_price_items": 0,
        "trend_channels": 0,
        "trend_histories": 0,
        "trend_listings": 0,
    }
    normalize_supplier_source_vendors()

    for entry in PRICE_SHEET_ENTRIES:
        source_code = entry.source_code or entry.provider_code
        source_name = entry.source_name or entry.provider_name
        source_url = entry.source_url or entry.upstream_url
        provider, provider_created = LLMProvider.objects.update_or_create(
            code=entry.provider_code,
            defaults={
                "name": entry.provider_name,
                "website": entry.upstream_url,
                "is_active": True,
                "notes": f"模型类别：{entry.group_name}",
            },
        )
        if provider_created:
            stats["providers"] += 1

        try:
            ensure_official_source(provider=provider)
        except KeyError:
            pass

        source = None
        if should_seed_supplier_sheet_source(entry):
            source_manager = PriceCollectionSource.objects
            (
                source,
                source_created,
            ) = source_manager.get_or_create(
                slug=f"{source_code}-sheet",
                defaults={
                    "provider": provider,
                    "channel": None,
                    "name": f"{source_name} 表格价格目录",
                    "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                    "source_category": (
                        PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
                    ),
                    "endpoint_url": SERVICE_ACCESS_URL,
                    "currency": entry.currency,
                    "is_enabled": True,
                    "updates_model_prices": True,
                    "notes": (
                        f"价格源地址：{source_url}; "
                        f"元模型厂商：{entry.provider_name}"
                    ),
                },
            )
            if source_created:
                stats["sources"] += 1
            elif not preserve_manual_overrides:
                _update_price_collection_source_defaults(
                    source,
                    provider=provider,
                    channel=None,
                    name=f"{source_name} 表格价格目录",
                    currency=entry.currency,
                    notes=(
                        f"价格源地址：{source_url}; "
                        f"元模型厂商：{entry.provider_name}"
                    ),
                )

        for model_code in entry.models:
            input_price, output_price = MODEL_BASE_PRICES.get(
                model_code,
                (Decimal("0"), Decimal("0")),
            )
            meta_info = meta_model_info_for_entry(entry, model_code)
            meta_model = ensure_meta_model(
                code=model_code,
                name=meta_info.name,
                provider=provider,
                modality=meta_info.modality,
                context_window=meta_info.context_window,
                max_output_tokens=meta_info.max_output_tokens,
            )
            apply_meta_model_seed_info(meta_model, meta_info, provider, entry)
            model, model_created = LLMModel.objects.get_or_create(
                provider=provider,
                source=source,
                code=model_code,
                defaults={
                    "meta_model": meta_model,
                    "name": meta_info.name,
                    "modality": meta_info.modality,
                    "input_price_per_million": input_price,
                    "output_price_per_million": output_price,
                    "context_window": meta_info.context_window,
                    "max_output_tokens": meta_info.max_output_tokens,
                    "currency": entry.currency,
                    "source": source,
                    "source_url": source.endpoint_url if source else "",
                    "price_role": seed_model_price_role(source, meta_model),
                    "is_active": True,
                },
            )
            if model_created:
                stats["models"] += 1
            elif not preserve_manual_overrides:
                _update_llm_model_defaults(
                    model,
                    name=meta_info.name,
                    modality=meta_info.modality,
                    input_price_per_million=input_price,
                    output_price_per_million=output_price,
                    context_window=meta_info.context_window,
                    max_output_tokens=meta_info.max_output_tokens,
                    currency=entry.currency,
                    price_role=seed_model_price_role(source, meta_model),
                )
            if source is not None:
                stats["model_price_items"] += seed_sheet_model_price_items(
                    entry,
                    provider,
                    model,
                    source,
                    preserve_manual_overrides=preserve_manual_overrides,
                )

    normalize_meta_model_catalog()
    return stats


def should_seed_supplier_sheet_source(entry: ProviderSheetEntry) -> bool:
    """Return whether the price sheet entry has a confirmed supplier."""
    source_code = entry.source_code or entry.provider_code
    return source_code in CONFIRMED_SUPPLIER_SHEET_SOURCE_CODES


def seed_model_price_role(
    source: PriceCollectionSource | None,
    meta_model: MetaModel,
) -> str:
    """Return the role for a seeded model without an unconfirmed source."""
    if source is None:
        return LLMModel.PRICE_ROLE_UNKNOWN
    return price_role_for_source(source, meta_model=meta_model)


def normalize_supplier_source_vendors() -> int:
    """Move supplier-only aliases out of the canonical vendor table.

    Older seeds treated platforms such as SiliconFlow as ``LLMProvider``
    rows. They are price sources, not model vendors. This function
    rewires their sources, provider-specific model rows and meta-model
    vendor pointers to the true vendor without touching any price or
    operator-maintained fields.
    """
    moved = 0
    for supplier_code, spec in SUPPLIER_SOURCE_VENDOR_ALIASES.items():
        supplier = LLMProvider.objects.filter(code=supplier_code).first()
        if not supplier:
            continue
        vendor, _ = LLMProvider.objects.get_or_create(
            code=spec["vendor_code"],
            defaults={
                "name": spec["vendor_name"],
                "website": spec["vendor_url"],
                "is_active": True,
                "notes": "元模型厂商。",
            },
        )

        source_ids = list(
            PriceCollectionSource.objects.filter(
                provider=supplier,
            ).values_list("id", flat=True)
        )
        if source_ids:
            moved += PriceCollectionSource.objects.filter(
                id__in=source_ids,
            ).update(provider=vendor)

        model_filter = LLMModel.objects.filter(provider=supplier)
        if spec.get("model_prefixes"):
            prefix_query = None
            for prefix in spec["model_prefixes"]:
                query = Q(code__startswith=prefix)
                prefix_query = query if prefix_query is None else (
                    prefix_query | query
                )
            if prefix_query is not None:
                model_filter = model_filter.filter(prefix_query)
        for model in model_filter:
            model.provider = vendor
            model.save(update_fields=["provider", "updated_at"])
            moved += 1

        meta_filter = MetaModel.objects.filter(vendor=supplier)
        if spec.get("model_prefixes"):
            prefix_query = None
            for prefix in spec["model_prefixes"]:
                query = Q(code__startswith=prefix)
                prefix_query = query if prefix_query is None else (
                    prefix_query | query
                )
            if prefix_query is not None:
                meta_filter = meta_filter.filter(prefix_query)
        for meta in meta_filter:
            spec_vendor = canonical_vendor_for_model_code(meta.code)
            target = vendor
            if spec_vendor:
                target = ensure_canonical_vendor_row(spec_vendor)
            if not target or target.id == meta.vendor_id:
                continue
            meta.vendor = target
            meta.save(update_fields=["vendor", "updated_at"])
            moved += 1

        # Supplier-only aliases must never remain canonical vendors.
        # Some historical rows were attached to SiliconFlow before
        # the canonical model was correctly identified; re-home all
        # of them and reapply the canonical vendor lookup so the
        # meta model ends up owned by the company that built it.
        for meta in MetaModel.objects.filter(
            vendor__code__in=SUPPLIER_SOURCE_VENDOR_ALIASES.keys()
        ).distinct():
            spec_vendor = canonical_vendor_for_model_code(meta.code)
            if not spec_vendor:
                continue
            target = ensure_canonical_vendor_row(spec_vendor)
            if not target or target.id == meta.vendor_id:
                continue
            meta.vendor = target
            meta.save(update_fields=["vendor", "updated_at"])
            moved += 1

        if not (
            supplier.models.exists()
            or supplier.collection_sources.exists()
            or supplier.canonical_models.exists()
        ):
            supplier.delete()
    return moved


def seed_sheet_model_price_items(
    entry: ProviderSheetEntry,
    provider: LLMProvider,
    model: LLMModel,
    source: PriceCollectionSource,
    *,
    preserve_manual_overrides: bool = False,
) -> int:
    """Seed normalized current price items for one sheet-backed model."""
    payloads = []
    for dimension, billing_unit, unit_price in sheet_model_item_specs(model):
        if unit_price is None:
            continue
        unit_value = Decimal(str(unit_price))
        if unit_value <= 0:
            continue
        payload = {
            "provider": provider,
            "model": model,
            "meta_model": model.meta_model,
            "source": source,
            "dimension": dimension,
            "billing_unit": billing_unit,
            "currency": entry.currency,
            "unit_price": unit_value,
            "tier_type": ModelPriceItem.TIER_FLAT,
            "tier_start": None,
            "tier_end": None,
            "spec": {
                "seed_source": "initial_price_sheet",
                "source_code": entry.source_code or entry.provider_code,
            },
            "source_url": source.endpoint_url,
            "raw_payload": {
                "provider_code": entry.provider_code,
                "model_code": model.code,
                "source_url": entry.source_url or entry.upstream_url,
            },
            "is_current": True,
            "effective_to": None,
        }
        payload["price_fingerprint"] = stable_fingerprint(
            {
                "source": source.id,
                "dimension": dimension,
                "billing_unit": billing_unit,
                "currency": entry.currency,
                "unit_price": str(unit_value),
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": "",
                "tier_end": "",
                "spec": payload["spec"],
            }
        )
        payloads.append(payload)

    if not payloads:
        return 0

    if preserve_manual_overrides:
        return create_missing_sheet_price_items(model, source, payloads)

    now = timezone.now()
    ModelPriceItem.objects.filter(
        model=model,
        source=source,
        spec__seed_source="initial_price_sheet",
        is_current=True,
    ).exclude(
        price_fingerprint__in=[
            payload["price_fingerprint"] for payload in payloads
        ],
    ).update(is_current=False, effective_to=now)

    created_count = 0
    for payload in payloads:
        price_item, created = ModelPriceItem.objects.update_or_create(
            model=model,
            source=source,
            dimension=payload["dimension"],
            billing_unit=payload["billing_unit"],
            tier_type=payload["tier_type"],
            tier_start=None,
            tier_end=None,
            defaults=payload,
        )
        if created:
            created_count += 1
        if not price_item.is_current or price_item.effective_to is not None:
            price_item.is_current = True
            price_item.effective_to = None
            price_item.save(update_fields=["is_current", "effective_to"])
    return created_count


def create_missing_sheet_price_items(
    model: LLMModel,
    source: PriceCollectionSource,
    payloads: list[dict],
) -> int:
    """Create missing sheet price dimensions without touching existing rows."""
    created_count = 0
    for payload in payloads:
        exists = ModelPriceItem.objects.filter(
            model=model,
            source=source,
            dimension=payload["dimension"],
            billing_unit=payload["billing_unit"],
            tier_type=payload["tier_type"],
            tier_start=None,
            tier_end=None,
            is_current=True,
        ).exists()
        if exists:
            continue
        ModelPriceItem.objects.create(**payload)
        created_count += 1
    return created_count


def sheet_model_item_specs(
    model: LLMModel,
) -> tuple[tuple[str, str, object], ...]:
    """Return normalized price dimensions backed by LLMModel fields."""
    return (
        (
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            model.input_price_per_million,
        ),
        (
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            model.output_price_per_million,
        ),
        (
            ModelPriceItem.DIMENSION_CACHE_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            model.cache_input_price_per_million,
        ),
        (
            ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
            ModelPriceItem.UNIT_PER_IMAGE,
            model.image_output_price_per_image,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            model.audio_input_price_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            model.audio_output_price_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            model.video_input_price_per_second,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            model.video_output_price_per_second,
        ),
    )


def seed_yunce_supplier_price_demo(
    preserve_manual_overrides: bool = False,
) -> dict[str, int]:
    """Seed Yunce supplier prices with one source per model.

    In safe mode (``preserve_manual_overrides=True``) existing rows
    are left untouched: the supplier channel, sources and channel
    model prices are created with :func:`get_or_create` and never
    re-applied. In legacy mode the function falls back to
    ``update_or_create`` for isolated fixture rebuilds.
    """
    stats = {
        "yunce_supplier_sources": 0,
        "yunce_supplier_prices": 0,
    }
    channel_kwargs = {
        "code": YUNCE_SUPPLIER_CHANNEL_CODE,
        "defaults": {
            "name": "\u4e91\u6d4b\u4f9b\u5e94\u5546",
            "api_endpoint": SERVICE_ACCESS_URL,
            "currency": "CNY",
            "settlement_ratio": Decimal("1"),
            "is_active": True,
            "notes": (
                "Mock \u4e91\u6d4b\u4f9b\u5e94\u5546\u4ef7\u683c\u3002"
                "\u6bcf\u4e2a\u6a21\u578b\u7ed1\u5b9a\u72ec\u7acb"
                "\u4e0a\u6e38\u4f9b\u8d27\u6e90\uff0c"
                "\u7528\u4e8e\u9a8c\u8bc1\u6e20\u9053\u91c7\u8d2d\u4ef7\u3001"
                "Agione \u6302\u552e\u51b3\u7b56\u548c\u4ef7\u683c\u6e90"
                "\u5c55\u793a\u3002"
            ),
        },
    }
    if preserve_manual_overrides:
        channel, _ = ProcurementChannel.objects.get_or_create(
            **channel_kwargs,
        )
    else:
        channel, _ = ProcurementChannel.objects.update_or_create(
            **channel_kwargs,
        )

    for entry in YUNCE_SUPPLIER_PRICE_ENTRIES:
        provider = LLMProvider.objects.filter(
            code=entry.provider_code
        ).first()
        if not provider:
            continue
        model = LLMModel.objects.filter(
            provider=provider,
            code=entry.model_code,
        ).first()
        if not model:
            continue

        source_defaults = {
            "name": (
                f"\u4e91\u6d4b / {entry.upstream_name} / "
                f"{entry.model_code}"
            ),
            "provider": provider,
            "channel": channel,
            "source_type": PriceCollectionSource.SOURCE_TYPE_YUNCE,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
            ),
            "endpoint_url": (
                f"{SERVICE_ACCESS_URL}/supplier/"
                f"{entry.provider_code}/{entry.model_code}"
            ),
            "currency": entry.currency,
            "is_enabled": True,
            "updates_model_prices": False,
            "notes": (
                f"\u4e0a\u6e38\u4f9b\u8d27\u6e90\uff1a"
                f"{entry.upstream_name}\uff1b"
                "\u8be5\u6765\u6e90\u53ea\u4f5c\u4e3a"
                "\u6e20\u9053\u91c7\u8d2d\u4ef7\uff0c"
                "\u4e0d\u8986\u76d6\u6a21\u578b\u539f\u5382\u4ef7\u3002"
            ),
        }
        if preserve_manual_overrides:
            (
                source,
                source_created,
            ) = PriceCollectionSource.objects.get_or_create(
                slug=yunce_supplier_source_slug(entry),
                defaults=source_defaults,
            )
        else:
            (
                source,
                source_created,
            ) = PriceCollectionSource.objects.update_or_create(
                slug=yunce_supplier_source_slug(entry),
                defaults=source_defaults,
            )
        if source_created:
            stats["yunce_supplier_sources"] += 1

        cmp_defaults = {
            "meta_model": model.meta_model,
            "price_source": source,
            "is_listed": True,
            "currency": entry.currency,
            "settlement_ratio": None,
            "custom_input_price_per_million": entry.input_price,
            "custom_output_price_per_million": entry.output_price,
            "custom_audio_input_price_per_second": (
                entry.audio_input_price
            ),
            "custom_audio_output_price_per_second": (
                entry.audio_output_price
            ),
            "custom_video_input_price_per_second": (
                entry.video_input_price
            ),
            "custom_video_output_price_per_second": (
                entry.video_output_price
            ),
            "notes": (
                f"\u4e91\u6d4b\u4e0a\u6e38\u4f9b\u8d27\u6e90\uff1a"
                f"{entry.upstream_name}"
            ),
        }
        if preserve_manual_overrides:
            _cmp, price_created = (
                ChannelModelPrice.objects.get_or_create(
                    channel=channel,
                    model=model,
                    defaults=cmp_defaults,
                )
            )
        else:
            _cmp, price_created = (
                ChannelModelPrice.objects.update_or_create(
                    channel=channel,
                    model=model,
                    defaults=cmp_defaults,
                )
            )
        if price_created:
            stats["yunce_supplier_prices"] += 1
        stats["yunce_supplier_price_items"] = (
            stats.get("yunce_supplier_price_items", 0)
            + seed_yunce_supplier_model_price_items(
                entry,
                provider,
                model,
                source,
            )
        )

    return stats





def seed_yunce_supplier_model_price_items(
    entry: YunceSupplierPriceEntry,
    provider: LLMProvider,
    model: LLMModel,
    source: PriceCollectionSource,
) -> int:
    """Seed normalized Yunce supplier price items for one model source."""
    payloads = []
    item_specs = yunce_supplier_item_specs(entry)
    for dimension, billing_unit, unit_price in item_specs:
        if unit_price is None:
            continue
        payload = {
            "provider": provider,
            "model": model,
            "meta_model": model.meta_model,
            "source": source,
            "dimension": dimension,
            "billing_unit": billing_unit,
            "currency": entry.currency,
            "unit_price": unit_price,
            "tier_type": ModelPriceItem.TIER_FLAT,
            "tier_start": None,
            "tier_end": None,
            "spec": {
                "mock_source": "yunce_supplier",
                "upstream_name": entry.upstream_name,
            },
            "source_url": source.endpoint_url,
            "raw_payload": {
                "provider_code": entry.provider_code,
                "model_code": entry.model_code,
                "upstream_name": entry.upstream_name,
            },
            "is_current": True,
            "effective_to": None,
        }
        fingerprint = stable_fingerprint(
            {
                "source": source.id,
                "dimension": dimension,
                "billing_unit": billing_unit,
                "currency": entry.currency,
                "unit_price": str(unit_price),
                "tier_type": ModelPriceItem.TIER_FLAT,
                "tier_start": "",
                "tier_end": "",
                "spec": payload["spec"],
            }
        )
        payload["price_fingerprint"] = fingerprint
        payloads.append(payload)

    if not payloads:
        return 0

    now = timezone.now()
    ModelPriceItem.objects.filter(
        model=model,
        source=source,
        is_current=True,
    ).update(is_current=False, effective_to=now)

    created_count = 0
    for payload in payloads:
        _, created = ModelPriceItem.objects.update_or_create(
            model=model,
            dimension=payload["dimension"],
            billing_unit=payload["billing_unit"],
            currency=payload["currency"],
            price_fingerprint=payload["price_fingerprint"],
            defaults=payload,
        )
        if created:
            created_count += 1
    return created_count


def yunce_supplier_item_specs(entry: YunceSupplierPriceEntry):
    """Return non-tiered price item specs for one Yunce mock entry."""
    return (
        (
            ModelPriceItem.DIMENSION_TEXT_INPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            entry.input_price,
        ),
        (
            ModelPriceItem.DIMENSION_TEXT_OUTPUT,
            ModelPriceItem.UNIT_PER_1M_TOKENS,
            entry.output_price,
        ),
        (
            ModelPriceItem.DIMENSION_IMAGE_OUTPUT,
            ModelPriceItem.UNIT_PER_IMAGE,
            entry.image_output_price,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            entry.audio_input_price,
        ),
        (
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            entry.audio_output_price,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_INPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            entry.video_input_price,
        ),
        (
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT,
            ModelPriceItem.UNIT_PER_SECOND,
            entry.video_output_price,
        ),
    )


def yunce_supplier_source_slug(entry: YunceSupplierPriceEntry) -> str:
    """Return a stable slug for one per-model Yunce supplier source."""
    raw_slug = slugify(f"yunce-{entry.provider_code}-{entry.model_code}")
    if len(raw_slug) <= 100:
        return raw_slug
    digest = stable_fingerprint(
        {
            "provider_code": entry.provider_code,
            "model_code": entry.model_code,
        }
    )[:10]
    return f"{raw_slug[:89]}-{digest}"


def seed_agione_price_trend_demo(
    preserve_manual_overrides: bool = False,
) -> dict[str, int]:
    """Seed demo histories for Agione supplier price trend comparison.

    In safe mode the demo channels, supplier sources and channel
    model prices are created with get_or_create and never
    re-applied. In legacy mode the helpers fall back to
    update_or_create so the explicit seed command still overwrites
    demo data on re-import.
    """
    stats = {
        "trend_channels": 0,
        "trend_histories": 0,
        "trend_listings": 0,
    }
    provider = LLMProvider.objects.filter(code="openai").first()
    if not provider:
        return stats
    model = LLMModel.objects.filter(
        provider=provider,
        code="gpt-4o-mini",
    ).first()
    if not model:
        return stats

    channels = [
        ensure_demo_channel(
            code=DEMO_BASELINE_SUPPLIER_CHANNEL_CODE,
            name="基准演示供货源",
            currency="USD",
            ratio=Decimal("0.55"),
            stats=stats,
            preserve_manual_overrides=preserve_manual_overrides,
        ),
        ensure_demo_channel(
            code="demo-premium-supplier",
            name="优选供货源",
            currency="USD",
            ratio=Decimal("0.62"),
            stats=stats,
            preserve_manual_overrides=preserve_manual_overrides,
        ),
        ensure_demo_channel(
            code="demo-backup-supplier",
            name="备选供货源",
            currency="USD",
            ratio=Decimal("0.72"),
            stats=stats,
            preserve_manual_overrides=preserve_manual_overrides,
        ),
    ]
    channel_by_code = {channel.code: channel for channel in channels}
    for channel_code, points in TREND_DEMO_HISTORY_POINTS.items():
        channel = channel_by_code[channel_code]
        ensure_demo_channel_price(
            channel,
            model,
            points[-1],
            preserve_manual_overrides=preserve_manual_overrides,
        )
        stats["trend_histories"] += seed_channel_history_points(
            channel,
            model,
            points,
        )

    return stats


def ensure_demo_channel(
    *,
    code: str,
    name: str,
    currency: str,
    ratio: Decimal,
    stats: dict[str, int],
    preserve_manual_overrides: bool = False,
) -> ProcurementChannel:
    """Ensure one demo supplier channel exists."""
    channel_kwargs = {
        "code": code,
        "defaults": {
            "name": name,
            "api_endpoint": SERVICE_ACCESS_URL,
            "currency": currency,
            "settlement_ratio": ratio,
            "is_active": True,
            "notes": (
                "用于 Agione 挂售价格走势演示。"
            ),
        },
    }
    if preserve_manual_overrides:
        channel, created = ProcurementChannel.objects.get_or_create(
            **channel_kwargs,
        )
    else:
        channel, created = ProcurementChannel.objects.update_or_create(
            **channel_kwargs,
        )
    if created:
        stats["trend_channels"] += 1
    source_kwargs = {
        "slug": f"{code}-trend-demo",
        "defaults": {
            "name": f"{name} 趋势演示价格",
            "provider": LLMProvider.objects.filter(
                code="openai",
            ).first(),
            "channel": channel,
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
            ),
            "endpoint_url": SERVICE_ACCESS_URL,
            "currency": currency,
            "is_enabled": True,
            "updates_model_prices": False,
        },
    }
    if preserve_manual_overrides:
        PriceCollectionSource.objects.get_or_create(**source_kwargs)
    else:
        PriceCollectionSource.objects.update_or_create(**source_kwargs)
    return channel


def ensure_demo_channel_price(
    channel: ProcurementChannel,
    model: LLMModel,
    point: tuple[str, Decimal, Decimal],
    *,
    preserve_manual_overrides: bool = False,
) -> None:
    """Set current demo channel prices for one model.

    In safe mode the call is a no-op when a ChannelModelPrice
    already exists for the (channel, model) pair. Otherwise the
    custom price slots are written with the demo seed values.
    """
    _, input_price, output_price = point
    defaults = {
        "meta_model": model.meta_model,
        "price_source": model.source,
        "is_listed": True,
        "currency": "USD",
        "settlement_ratio": None,
        "custom_input_price_per_million": input_price,
        "custom_output_price_per_million": output_price,
        "notes": "Agione 趋势演示供货价。",
    }
    if preserve_manual_overrides:
        ChannelModelPrice.objects.get_or_create(
            channel=channel,
            model=model,
            defaults=defaults,
        )
    else:
        ChannelModelPrice.objects.update_or_create(
            channel=channel,
            model=model,
            defaults=defaults,
        )


def seed_channel_history_points(
    channel: ProcurementChannel,
    model: LLMModel,
    points: tuple[tuple[str, Decimal, Decimal], ...],
) -> int:
    """Create channel price history points for chart comparison."""
    created_count = 0
    for index, (date_text, input_price, output_price) in enumerate(points):
        effective_from = timezone.datetime.fromisoformat(date_text)
        effective_from = timezone.make_aware(effective_from)
        effective_to = None
        if index < len(points) - 1:
            next_date = timezone.datetime.fromisoformat(points[index + 1][0])
            effective_to = timezone.make_aware(next_date)
            effective_to -= timedelta(seconds=1)
        payload = {
            "is_listed": True,
            "input_price_per_million": str(input_price),
            "output_price_per_million": str(output_price),
            "currency": "USD",
            "effective_from": date_text,
        }
        fingerprint = stable_fingerprint(payload)
        _, created = ChannelModelPriceHistory.objects.update_or_create(
            channel=channel,
            model=model,
            price_fingerprint=fingerprint,
            defaults={
                "meta_model": model.meta_model,
                "price_source": model.source,
                "is_listed": True,
                "settlement_ratio": None,
                "input_price_per_million": input_price,
                "output_price_per_million": output_price,
                "currency": "USD",
                "price_fingerprint": fingerprint,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "is_current": index == len(points) - 1,
            },
        )
        if created:
            created_count += 1
    return created_count


def clean_mock_llm_ops_seed_data() -> dict[str, int]:
    """Remove legacy mock/demo rows from earlier seed versions.

    The cleanup only targets deterministic rows created by this module:
    Yunce mock supplier sources, Agione trend-demo sources, demo supplier
    channels and the generated trend-history fingerprints. Manual sources
    and operator-maintained channels are not matched by these selectors.
    """
    stats = {
        "model_price_items": 0,
        "channel_price_items": 0,
        "channel_model_prices": 0,
        "channel_model_histories": 0,
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
    real_resource_channel_filter = Q(code=REAL_RESOURCE_CHANNEL_CODE)
    test_channel_filter = (
        real_resource_channel_filter
        |
        Q(code__in=MOCK_SUPPLIER_CHANNEL_CODES)
        | Q(code__startswith="test-")
        | Q(name__startswith="测试")
    )
    test_channel_price_filter = (
        Q(channel__code=REAL_RESOURCE_CHANNEL_CODE)
        | Q(channel__code__in=MOCK_SUPPLIER_CHANNEL_CODES)
        | Q(channel__code__startswith="test-")
        | Q(channel__name__startswith="测试")
    )
    PriceCollectionSource.objects.filter(
        channel__code=REAL_RESOURCE_CHANNEL_CODE,
    ).update(channel=None)
    stats["model_price_items"] += _delete_count(
        ModelPriceItem.objects.filter(
            Q(source_id__in=source_ids)
            | Q(spec__mock_source="yunce_supplier")
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
    """Backfill canonical vendor on every meta model that has none.

    A meta model without a vendor is a bug: the canonical concept
    requires every model to belong to a real vendor. We look up
    the company that built the model from the model code prefix
    and rewrite ``vendor`` so the API never reports unbound rows.
    Meta models whose code does not match any known prefix are
    surfaced as warnings but otherwise left alone.
    """
    stats = {
        "resolved": 0,
        "unresolved": 0,
    }
    for meta in MetaModel.objects.filter(vendor__isnull=True):
        spec = canonical_vendor_for_model_code(meta.code)
        if not spec:
            stats["unresolved"] += 1
            continue
        provider = ensure_canonical_vendor_row(spec)
        if not provider:
            stats["unresolved"] += 1
            continue
        meta.vendor = provider
        meta.save(update_fields=["vendor", "updated_at"])
        stats["resolved"] += 1
    return stats


def normalize_meta_model_catalog() -> dict[str, int]:
    """Merge release/date meta-model rows into family-level rows."""
    stats = {
        "normalized": 0,
        "merged": 0,
        "linked_records": 0,
    }
    for meta in list(MetaModel.objects.select_related("vendor").all()):
        identity = canonical_meta_model_identity(meta.code, meta.name)
        canonical_code = identity["code"]
        canonical_name = identity["name"]
        if meta.code == canonical_code:
            aliases = merged_meta_aliases(meta, identity)
            if aliases != list(meta.aliases or []):
                meta.aliases = aliases
                meta.save(update_fields=["aliases", "updated_at"])
                stats["normalized"] += 1
            continue
        canonical = MetaModel.objects.filter(code=canonical_code).first()
        if canonical is None:
            meta.code = canonical_code
            meta.name = canonical_name
            meta.aliases = merged_meta_aliases(meta, identity)
            spec = canonical_vendor_for_model_code(canonical_code)
            if spec:
                meta.vendor = ensure_canonical_vendor_row(spec)
            meta.save(
                update_fields=[
                    "code",
                    "name",
                    "aliases",
                    "vendor",
                    "updated_at",
                ],
            )
            stats["normalized"] += 1
            continue
        merge_meta_model_rows(canonical, meta, identity)
        stats["merged"] += 1
    stats["linked_records"] = normalize_model_linked_meta_models()
    return stats


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
            total += model_type.objects.filter(
                model=model,
            ).exclude(
                meta_model=model.meta_model,
            ).update(
                meta_model=model.meta_model,
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
    if not canonical.vendor_id and duplicate.vendor_id:
        canonical.vendor = duplicate.vendor
        changed_fields.append("vendor")
    if changed_fields:
        changed_fields.append("updated_at")
        canonical.save(update_fields=changed_fields)
    for relation in MetaModel._meta.related_objects:
        field = relation.field
        relation.related_model.objects.filter(
            **{field.name: duplicate}
        ).update(**{field.name: canonical})
    duplicate.delete()


def cleanup_orphan_meta_models() -> dict[str, int]:
    """Remove meta models that no canonical price row references.

    Meta models without ``LLMModel.provider_prices`` are unused
    and can be dropped without disturbing manual channel prices.
    The lookup reuses the canonical vendor rules so that legacy
    rows whose ``vendor`` points at a supplier alias are
    rehomed to the company that actually built the model.
    """
    stats = {
        "meta_models_rehomed": 0,
        "meta_models_deleted": 0,
    }
    orphan_codes = []
    for meta in MetaModel.objects.all():
        spec = canonical_vendor_for_model_code(meta.code)
        canonical = None
        if spec:
            canonical = ensure_canonical_vendor_row(spec)
        elif meta.vendor_id and is_canonical_vendor_code(
            meta.vendor.code
        ):
            canonical = meta.vendor
        if (
            canonical
            and meta.vendor_id
            and canonical.id != meta.vendor_id
        ):
            meta.vendor = canonical
            meta.save(update_fields=["vendor", "updated_at"])
            stats["meta_models_rehomed"] += 1
        if not meta.provider_prices.exists():
            orphan_codes.append(meta.id)
    if orphan_codes:
        stats["meta_models_deleted"] = MetaModel.objects.filter(
            id__in=orphan_codes,
        ).delete()[0]
    return stats


def reset_meta_models_canonical() -> dict[str, int]:
    """Wipe meta models without repopulating replacement data.

    The reset is destructive: it deletes every ``MetaModel`` and
    cascades through ``LLMModel`` to ``ChannelModelPrice``,
    ``ChannelPriceItem`` and ``ChannelModelPriceHistory``. Manual
    price sources and supplier sources are kept by default so
    operator-maintained catalogues survive. Supplier-only aliases are
    removed so future Agent sync or manual imports cannot reuse them as
    model vendors.
    """
    stats = {
        "manual_sources_kept": 0,
        "supplier_sources_kept": 0,
        "meta_models_deleted": 0,
    }
    stats["manual_sources_kept"] = (
        PriceCollectionSource.objects.filter(
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_MANUAL
            ),
        ).count()
    )
    stats["supplier_sources_kept"] = (
        PriceCollectionSource.objects.filter(
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
            ),
        ).count()
    )
    PriceCollectionSource.objects.filter(
        channel__code=REAL_RESOURCE_CHANNEL_CODE,
    ).delete()
    stats["meta_models_deleted"] = MetaModel.objects.all().delete()[0]
    for supplier_code in SUPPLIER_SOURCE_VENDOR_ALIASES.keys():
        LLMProvider.objects.filter(code=supplier_code).delete()
    return stats


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


# ---------------------------------------------------------------------------
# Public wrappers for safe vs legacy seed
# ---------------------------------------------------------------------------


def is_llm_ops_database_empty() -> bool:
    """Return True when no llm_ops canonical rows exist yet.

    This is retained for isolated maintenance helpers and tests. It
    returns ``True`` only when every canonical anchor (providers and
    models) is missing. Procurement channels are operator-maintained
    resources and must not decide whether the canonical model catalogue
    is empty.
    """
    if LLMProvider.objects.exists():
        return False
    if LLMModel.objects.exists():
        return False
    return True


def _update_channel_model_price_defaults(
    instance: "ChannelModelPrice",
    *,
    meta_model,
    price_source,
    currency: str,
    settlement_ratio: Decimal,
    notes: str,
) -> None:
    """Refresh seed-managed fields on a ChannelModelPrice row.

    Only updates seed-managed columns (``meta_model``, ``price_source``,
    ``currency``, ``settlement_ratio``, ``notes``) and never touches the
    operator-managed ``custom_*`` overrides. This keeps human edits to
    custom prices intact across idempotent re-runs of the seed.
    """
    changed = []
    desired = {
        "meta_model": meta_model,
        "price_source": price_source,
        "currency": currency,
        "settlement_ratio": settlement_ratio,
        "notes": notes,
    }
    for field, value in desired.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    if changed:
        changed.append("updated_at")
        instance.save(update_fields=changed)


def _update_llm_model_defaults(
    instance: "LLMModel",
    *,
    name: str,
    modality: str,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
    context_window: int,
    max_output_tokens: int,
    currency: str,
    price_role: str,
) -> None:
    """Refresh seed-managed fields on a LLMModel row.

    Updates only the seed-managed identity/pricing fields. ``is_active``,
    ``meta_model`` and ``source_url`` are deliberately left untouched so
    manual toggles (disable model, swap canonical meta model) survive an
    idempotent seed.
    """
    desired = {
        "name": name,
        "modality": modality,
        "input_price_per_million": input_price_per_million,
        "output_price_per_million": output_price_per_million,
        "context_window": context_window,
        "max_output_tokens": max_output_tokens,
        "currency": currency,
        "price_role": price_role,
    }
    changed = []
    for field, value in desired.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    if changed:
        changed.append("updated_at")
        instance.save(update_fields=changed)


def _update_price_collection_source_defaults(
    instance: "PriceCollectionSource",
    *,
    provider,
    channel,
    name: str,
    currency: str,
    notes: str,
) -> None:
    """Refresh seed-managed fields on a PriceCollectionSource row.

    Preserves operator toggles such as ``is_enabled`` and
    ``updates_model_prices`` so the seed never silently re-enables a source
    that was disabled by an operator.
    """
    desired = {
        "provider": provider,
        "channel": channel,
        "name": name,
        "currency": currency,
        "notes": notes,
    }
    changed = []
    for field, value in desired.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    if changed:
        changed.append("updated_at")
        instance.save(update_fields=changed)


def seed_initial_price_sheet() -> dict[str, int]:
    """Import the initial operations price sheet into LLM Ops tables.

    Backwards-compatible wrapper that historically called
    ``update_or_create`` and overwrote all defaults. This helper is
    kept for isolated tests and internal maintenance utilities; product
    synchronization must use Agent sync or manual import instead.
    """
    return _seed_initial_price_sheet_core(preserve_manual_overrides=False)


def seed_initial_price_sheet_safely() -> dict[str, int]:
    """Idempotent seed that preserves manually-maintained overrides.

    This helper is retained for isolated tests and maintenance scripts.
    Product startup paths must use Agent sync, manual entry or bulk
    import instead. It differs from :func:`seed_initial_price_sheet` in
    two ways:

    1. Models, sources and channel prices are created with
       :func:`~django.db.models.Manager.get_or_create` rather than
       ``update_or_create``, so existing rows are not re-written.
    2. Re-runs of the seed on an already populated database are no-ops
       (creation counters stay at zero) and never touch operator-edited
       fields such as ``ChannelModelPrice.custom_*``,
       ``LLMModel.is_active`` or ``PriceCollectionSource.is_enabled``.
    """
    return _seed_initial_price_sheet_core(preserve_manual_overrides=True)


def seed_initial_price_sheet_if_empty() -> dict[str, int] | None:
    """Collect official model prices only on a fresh database.

    Returns import stats when collection actually happened, or ``None``
    when the database already contains llm_ops canonical rows. This is a
    maintenance helper, not a product startup hook.
    """
    if not is_llm_ops_database_empty():
        return None
    return seed_initial_catalog_from_official_sources()


def seed_initial_catalog_from_official_sources(
    *,
    verify_source: bool = True,
) -> dict[str, int]:
    """Collect official source data into an empty model catalogue."""
    before = {
        "providers": LLMProvider.objects.count(),
        "sources": PriceCollectionSource.objects.count(),
        "models": LLMModel.objects.count(),
        "model_price_items": ModelPriceItem.objects.count(),
    }
    before_source_ids = set(
        PriceCollectionSource.objects.values_list("id", flat=True)
    )
    provider_codes = []
    created_provider_codes = []
    for provider_code, config in OFFICIAL_PROVIDER_CONFIGS.items():
        source_url = official_bootstrap_source_url(provider_code)
        provider, created = LLMProvider.objects.update_or_create(
            code=provider_code,
            defaults={
                "name": config.provider_label,
                "website": source_url,
                "is_active": True,
                "notes": "官方价格采集自动初始化。",
            },
        )
        source = ensure_official_source(provider=provider)
        if source.endpoint_url != source_url:
            source.endpoint_url = source_url
            source.save(update_fields=["endpoint_url", "updated_at"])
        if created:
            created_provider_codes.append(provider.code)
        provider_codes.append(provider.code)

    results = sync_configured_official_model_prices(
        provider_codes=provider_codes,
        verify_source=verify_source,
    )
    after = {
        "providers": LLMProvider.objects.count(),
        "sources": PriceCollectionSource.objects.count(),
        "models": LLMModel.objects.count(),
        "model_price_items": ModelPriceItem.objects.count(),
    }
    if after["models"] == before["models"] and created_provider_codes:
        created_source_ids = list(
            PriceCollectionSource.objects.exclude(
                id__in=before_source_ids,
            ).values_list("id", flat=True)
        )
        PriceCollectionRun.objects.filter(
            source_id__in=created_source_ids,
        ).delete()
        PriceCollectionSource.objects.filter(
            id__in=created_source_ids,
        ).delete()
        LLMProvider.objects.filter(code__in=created_provider_codes).delete()
        after = {
            "providers": LLMProvider.objects.count(),
            "sources": PriceCollectionSource.objects.count(),
            "models": LLMModel.objects.count(),
            "model_price_items": ModelPriceItem.objects.count(),
        }
    return {
        "providers": after["providers"] - before["providers"],
        "sources": after["sources"] - before["sources"],
        "models": after["models"] - before["models"],
        "model_price_items": (
            after["model_price_items"] - before["model_price_items"]
        ),
        "channel_model_prices": 0,
        "yunce_supplier_sources": 0,
        "yunce_supplier_prices": 0,
        "yunce_supplier_price_items": 0,
        "trend_channels": 0,
        "trend_histories": 0,
        "trend_listings": 0,
        "official_collect_results": results,
    }


def official_bootstrap_source_url(provider_code: str) -> str:
    """Return the external source URL used for initial bootstrap."""
    if provider_code in MODELS_DEV_PROVIDER_KEYS:
        return MODELS_DEV_API_URL
    return OFFICIAL_PROVIDER_CONFIGS[provider_code].source_url
