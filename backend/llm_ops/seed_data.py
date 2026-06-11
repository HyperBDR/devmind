from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.utils.text import slugify

from .collection_services import ensure_official_source
from .models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
)
from .services import (
    ensure_meta_model,
    price_role_for_source,
    stable_fingerprint,
)


SERVICE_ACCESS_URL = "https://llm.guohe-sh.com"
REAL_RESOURCE_CHANNEL_CODE = "real-resource-platform"
YUNCE_SUPPLIER_CHANNEL_CODE = "yunce-supplier-platform"


@dataclass(frozen=True)
class ProviderSheetEntry:
    """One provider section from the initial operations price sheet."""

    group_name: str
    provider_name: str
    provider_code: str
    upstream_url: str
    currency: str
    discount: Decimal
    models: tuple[str, ...]


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
            "qwen3.5-122b-a10b",
            "qwen3.5-27b",
            "qwen3.5-35b-a3b",
            "qwen3.5-39fb-a17b",
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
        provider_name="硅基流动",
        provider_code="siliconflow",
        upstream_url="https://api.siliconflow.cn/",
        currency="CNY",
        discount=Decimal("0.65"),
        models=(
            "deepseek-r1",
            "deepseek-v3",
            "deepseek-v3.1",
            "deepseek-v3.2",
            "deepseek-v3.2-exp",
        ),
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
        provider_code="siliconflow",
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
            name=title_model_code(model_code, uppercase_tokens={"wan", "wanx"}),
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
    """Persist richer metadata on the canonical model entity."""
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
    updates = {
        "name": info.name,
        "family": info.family,
        "vendor": provider,
        "modality": info.modality,
        "aliases": sorted(set(info.aliases + (meta_model.code,))),
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


def seed_initial_price_sheet() -> dict[str, int]:
    """Import the initial operations price sheet into LLM Ops tables."""
    stats = {
        "providers": 0,
        "sources": 0,
        "models": 0,
        "channel_model_prices": 0,
        "yunce_supplier_sources": 0,
        "yunce_supplier_prices": 0,
        "yunce_supplier_price_items": 0,
        "trend_channels": 0,
        "trend_histories": 0,
        "trend_listings": 0,
    }
    channel, _ = ProcurementChannel.objects.update_or_create(
        code=REAL_RESOURCE_CHANNEL_CODE,
        defaults={
            "name": "真实资源平台",
            "api_endpoint": SERVICE_ACCESS_URL,
            "currency": "USD",
            "settlement_ratio": Decimal("1"),
            "is_active": True,
            "notes": (
                "基础价格为真实资源平台列表价，"
                "折扣有效期为合同存续期间。"
            ),
        },
    )

    for entry in PRICE_SHEET_ENTRIES:
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

        ensure_seed_official_source(provider)

        source_manager = PriceCollectionSource.objects
        source, source_created = source_manager.update_or_create(
            slug=f"{entry.provider_code}-sheet",
            defaults={
                "provider": provider,
                "channel": channel,
                "name": f"{entry.provider_name} 表格价格目录",
                "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
                ),
                "endpoint_url": SERVICE_ACCESS_URL,
                "currency": entry.currency,
                "is_enabled": True,
                "updates_model_prices": True,
                "notes": (
                    "供应方接入地址："
                    f"{SERVICE_ACCESS_URL}; "
                    f"原厂地址：{entry.upstream_url}"
                ),
            },
        )
        if source_created:
            stats["sources"] += 1

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
            model, model_created = LLMModel.objects.update_or_create(
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
                    "source_url": SERVICE_ACCESS_URL,
                    "price_role": price_role_for_source(source),
                    "is_active": True,
                },
            )
            if model_created:
                stats["models"] += 1

            _, price_created = ChannelModelPrice.objects.update_or_create(
                channel=channel,
                model=model,
                defaults={
                    "meta_model": model.meta_model,
                    "price_source": source,
                    "is_listed": True,
                    "currency": entry.currency,
                    "settlement_ratio": entry.discount,
                    "notes": (
                        "基础价格：真实资源平台列表价；"
                        f"币种：{entry.currency}；"
                        "折扣有效期：合同存续期间。"
                    ),
                },
            )
            if price_created:
                stats["channel_model_prices"] += 1

    supplier_stats = seed_yunce_supplier_price_demo()
    stats.update(supplier_stats)
    trend_stats = seed_agione_price_trend_demo()
    stats.update(trend_stats)
    return stats


def ensure_seed_official_source(provider: LLMProvider) -> None:
    """Create official source config when the provider is supported."""
    try:
        ensure_official_source(provider=provider)
    except KeyError:
        return


def seed_yunce_supplier_price_demo() -> dict[str, int]:
    """Seed Yunce supplier prices with one source per model."""
    stats = {
        "yunce_supplier_sources": 0,
        "yunce_supplier_prices": 0,
    }
    channel, _ = ProcurementChannel.objects.update_or_create(
        code=YUNCE_SUPPLIER_CHANNEL_CODE,
        defaults={
            "name": "云测供应商",
            "api_endpoint": SERVICE_ACCESS_URL,
            "currency": "CNY",
            "settlement_ratio": Decimal("1"),
            "is_active": True,
            "notes": (
                "Mock 云测供应商价格。每个模型绑定独立上游供货源，"
                "用于验证渠道采购价、Agione 挂售决策和价格源展示。"
            ),
        },
    )

    for entry in YUNCE_SUPPLIER_PRICE_ENTRIES:
        provider = LLMProvider.objects.filter(code=entry.provider_code).first()
        if not provider:
            continue
        model = LLMModel.objects.filter(
            provider=provider,
            code=entry.model_code,
        ).first()
        if not model:
            continue

        source, source_created = PriceCollectionSource.objects.update_or_create(
            slug=yunce_supplier_source_slug(entry),
            defaults={
                "name": (
                    f"云测 / {entry.upstream_name} / {entry.model_code}"
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
                    f"上游供货源：{entry.upstream_name}；"
                    "该来源只作为渠道采购价，不覆盖模型原厂价。"
                ),
            },
        )
        if source_created:
            stats["yunce_supplier_sources"] += 1

        _, price_created = ChannelModelPrice.objects.update_or_create(
            channel=channel,
            model=model,
            defaults={
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
                "notes": f"云测上游供货源：{entry.upstream_name}",
            },
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
    for dimension, billing_unit, unit_price in yunce_supplier_item_specs(entry):
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


def seed_agione_price_trend_demo() -> dict[str, int]:
    """Seed demo histories for Agione supplier price trend comparison."""
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
            code=REAL_RESOURCE_CHANNEL_CODE,
            name="真实资源平台",
            currency="USD",
            ratio=Decimal("0.55"),
            stats=stats,
        ),
        ensure_demo_channel(
            code="demo-premium-supplier",
            name="优选供货源",
            currency="USD",
            ratio=Decimal("0.62"),
            stats=stats,
        ),
        ensure_demo_channel(
            code="demo-backup-supplier",
            name="备选供货源",
            currency="USD",
            ratio=Decimal("0.72"),
            stats=stats,
        ),
    ]
    history_points = {
        REAL_RESOURCE_CHANNEL_CODE: (
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
    channel_by_code = {channel.code: channel for channel in channels}
    for channel_code, points in history_points.items():
        channel = channel_by_code[channel_code]
        ensure_demo_channel_price(channel, model, points[-1])
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
) -> ProcurementChannel:
    """Ensure one demo supplier channel exists."""
    channel, created = ProcurementChannel.objects.update_or_create(
        code=code,
        defaults={
            "name": name,
            "api_endpoint": SERVICE_ACCESS_URL,
            "currency": currency,
            "settlement_ratio": ratio,
            "is_active": True,
            "notes": "用于 Agione 挂售价格走势演示。",
        },
    )
    if created:
        stats["trend_channels"] += 1
    PriceCollectionSource.objects.update_or_create(
        slug=f"{code}-trend-demo",
        defaults={
            "name": f"{name} 趋势演示价格",
            "provider": LLMProvider.objects.filter(code="openai").first(),
            "channel": channel,
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            "endpoint_url": SERVICE_ACCESS_URL,
            "currency": currency,
            "is_enabled": True,
            "updates_model_prices": False,
        },
    )
    return channel


def ensure_demo_channel_price(
    channel: ProcurementChannel,
    model: LLMModel,
    point: tuple[str, Decimal, Decimal],
) -> None:
    """Set current demo channel prices for one model."""
    _, input_price, output_price = point
    ChannelModelPrice.objects.update_or_create(
        channel=channel,
        model=model,
        defaults={
            "meta_model": model.meta_model,
            "price_source": model.source,
            "is_listed": True,
            "currency": "USD",
            "settlement_ratio": None,
            "custom_input_price_per_million": input_price,
            "custom_output_price_per_million": output_price,
            "notes": "Agione 趋势演示供货价。",
        },
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
