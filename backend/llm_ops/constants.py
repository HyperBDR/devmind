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
)


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
