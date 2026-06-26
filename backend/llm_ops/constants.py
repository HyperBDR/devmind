import re


SUPPLIER_SOURCE_VENDOR_ALIASES = {
    "siliconflow": {
        "vendor_code": "deepseek",
        "vendor_name": "DeepSeek",
        "vendor_url": "https://api.deepseek.com/",
        "model_prefixes": ("deepseek-",),
    },
}

# Canonical vendor lookup rules. A meta model belongs to the company
# that actually built it, never to a price source or reseller. The
# seed, the API layer and the cleanup helpers all funnel through
# ``canonical_vendor_for_model_code`` so the meta-model ``vendor``
# field can never end up pointing at a marketplace.
META_MODEL_VENDOR_RULES = (
    # (model code prefix, vendor code, vendor name, vendor website)
    ("gpt-", "openai", "OpenAI", "https://api.openai.com/"),
    ("o1", "openai", "OpenAI", "https://api.openai.com/"),
    ("o3", "openai", "OpenAI", "https://api.openai.com/"),
    ("o4", "openai", "OpenAI", "https://api.openai.com/"),
    ("text-embedding-", "openai", "OpenAI", "https://api.openai.com/"),
    ("gpt-image-", "openai", "OpenAI", "https://api.openai.com/"),
    ("claude-", "anthropic", "Anthropic", "https://api.anthropic.com/"),
    ("gemini-", "google", "Google", "https://ai.google.dev/"),
    ("qwen", "aliyun", "阿里云", "https://dashscope.aliyuncs.com/"),
    ("wan", "aliyun-wanx", "阿里云万象", "https://dashscope.aliyuncs.com/"),
    ("wanx", "aliyun-wanx", "阿里云万象", "https://dashscope.aliyuncs.com/"),
    ("doubao-", "volcengine", "火山", "https://ark.cn-beijing.volces.com/"),
    ("deepseek-", "deepseek", "DeepSeek", "https://api.deepseek.com/"),
    ("kimi-", "kimi", "Kimi（月之暗面）", "https://api.moonshot.cn/"),
    ("moonshot-", "kimi", "Kimi（月之暗面）", "https://api.moonshot.cn/"),
    ("minimax-", "minimax", "MiniMax", "https://api.minimax.io/"),
    ("grok-", "xai", "xAI", "https://x.ai/api"),
    ("llama-", "meta", "Meta", "https://ai.meta.com/"),
    ("mistral-", "mistral", "Mistral AI", "https://mistral.ai/"),
    ("mixtral-", "mistral", "Mistral AI", "https://mistral.ai/"),
    ("codestral-", "mistral", "Mistral AI", "https://mistral.ai/"),
    ("magistral-", "mistral", "Mistral AI", "https://mistral.ai/"),
    ("pixtral-", "mistral", "Mistral AI", "https://mistral.ai/"),
    ("ernie-", "baidu", "百度", "https://cloud.baidu.com/"),
    ("glm-", "zhipu", "智谱", "https://open.bigmodel.cn/"),
    ("chatglm", "zhipu", "智谱", "https://open.bigmodel.cn/"),
    ("hunyuan-", "tencent", "腾讯混元", "https://hunyuan.tencent.com/"),
    ("hy", "tencent", "腾讯混元", "https://hunyuan.tencent.com/"),
    ("baichuan-", "baichuan", "百川智能", "https://www.baichuan-ai.com/"),
    ("yi-", "01ai", "零一万物", "https://www.lingyiwanwu.com/"),
    ("step-", "stepfun", "阶跃星辰", "https://www.stepfun.com/"),
    ("command-", "cohere", "Cohere", "https://cohere.com/"),
)


ROLE_RELEASE_SUFFIXES = {
    "abliterated",
    "cs",
    "dynamic",
    "fast",
    "fp8",
    "instruct",
    "maas",
    "thinking",
    "think",
    "turbo",
    "versatile",
}


def canonical_meta_model_identity(code, name=None):
    """Return the family-level identity for a reported model code.

    Provider catalogues often expose release SKUs such as
    ``deepseek-r1-0528`` or ``qwen3-30b-a3b-instruct-2507``.
    Those are price-source model spellings, not separate meta models.
    The canonical meta model keeps the meaningful major/minor family
    and stores the reported release spelling in aliases.
    """
    raw_code = str(code or name or "").strip()
    canonical_code = normalize_meta_model_code(raw_code)
    raw_name = str(name or raw_code).strip() or canonical_code
    canonical_name = normalize_meta_model_name(raw_name, canonical_code)
    aliases = []
    for token in (raw_code, raw_name):
        if token and token not in {canonical_code, canonical_name}:
            aliases.append(token)
    return {
        "code": canonical_code,
        "name": canonical_name,
        "aliases": aliases,
    }


def normalize_meta_model_code(value):
    """Collapse release/date suffixes from a model identifier."""
    normalized = str(value or "").strip().lower().replace("_", "-")
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0]
    normalized = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", normalized)
    normalized = re.sub(r"-\d{8}$", "", normalized)
    normalized = re.sub(r"-\d{6}$", "", normalized)
    normalized = re.sub(r"-\d{4}$", "", normalized)
    parts = normalized.split("-")
    while parts and parts[-1] in ROLE_RELEASE_SUFFIXES:
        parts.pop()
    return "-".join(parts) or normalized


def normalize_meta_model_name(value, canonical_code):
    """Return a display name matching the family-level meta model."""
    name = str(value or "").strip()
    if not name:
        return canonical_code
    name = re.sub(r"\s+\d{4}-\d{2}-\d{2}$", "", name)
    name = re.sub(r"\s+\d{8}$", "", name)
    name = re.sub(r"\s+\d{6}$", "", name)
    name = re.sub(r"\s+\d{4}$", "", name)
    parts = name.split()
    while parts and parts[-1].lower() in ROLE_RELEASE_SUFFIXES:
        parts.pop()
    return " ".join(parts) or canonical_code


def canonical_vendor_for_model_code(model_code):
    """Return the canonical vendor spec for a model code.

    A meta model always belongs to the company that built the model.
    Price sources such as SiliconFlow or OpenRouter never appear as a
    vendor here. Returns ``None`` when the code is unknown so callers
    can fall back to historical data.
    """
    if not model_code:
        return None
    normalized = str(model_code).strip().lower()
    for prefix, code, name, url in META_MODEL_VENDOR_RULES:
        if normalized.startswith(prefix):
            return {
                "code": code,
                "name": name,
                "url": url,
            }
    return None


def is_canonical_vendor_code(vendor_code):
    """Return True when ``vendor_code`` is a model vendor (not a supplier)."""
    if not vendor_code:
        return False
    return vendor_code not in SUPPLIER_SOURCE_VENDOR_ALIASES


def ensure_canonical_vendor_row(spec):
    """Return the LLMProvider that owns a canonical model vendor.

    The lookup is refusal-by-default: supplier aliases are not
    treated as canonical vendors, even when the legacy seed
    pointed at them.
    """
    if not spec:
        return None
    if not is_canonical_vendor_code(spec["code"]):
        return None
    from .models import LLMProvider
    provider, _ = LLMProvider.objects.get_or_create(
        code=spec["code"],
        defaults={
            "name": spec["name"],
            "website": spec["url"],
            "is_active": True,
            "notes": "\u5143\u6a21\u578b\u5382\u5546\u3002",
        },
    )
    if provider.name != spec["name"]:
        provider.name = spec["name"]
        provider.save(update_fields=["name", "updated_at"])
    return provider


def resolve_meta_model_vendor(meta_model, info, provider):
    """Decide which LLMProvider should be the canonical vendor.

    Always prefer the company that built the model. We only
    overwrite an existing vendor when it is missing or when it
    points at a known supplier alias (e.g. legacy SiliconFlow).
    """
    spec = canonical_vendor_for_model_code(meta_model.code)
    canonical = None
    if spec:
        canonical = ensure_canonical_vendor_row(spec)
    elif provider and is_canonical_vendor_code(provider.code):
        canonical = provider
    if not meta_model.vendor_id:
        return canonical
    existing_code = (
        meta_model.vendor.code if meta_model.vendor_id else ""
    )
    if not is_canonical_vendor_code(existing_code):
        # Legacy row pointing at a supplier alias: rehome it.
        return canonical
    if canonical and canonical.id != meta_model.vendor_id:
        return canonical
    return meta_model.vendor
