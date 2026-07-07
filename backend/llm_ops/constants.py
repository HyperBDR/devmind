import re


SUPPLIER_SOURCE_OWNER_ALIASES = {
    "siliconflow": {
        "owner_code": "deepseek",
        "owner_name": "DeepSeek",
        "owner_website": "https://api.deepseek.com/",
        "model_prefixes": ("deepseek-",),
    },
    "openrouter": {},
    "yunce": {},
    "agione": {},
}

# Canonical owner lookup rules. A meta model belongs to the company
# that actually built it, never to a price source or reseller. The
# API layer and cleanup helpers all funnel through
# ``canonical_owner_for_model_code`` so marketplace suppliers never
# become meta-model owners.
META_MODEL_OWNER_RULES = (
    # (model code prefix, owner code, owner name, owner website)
    ("gpt-", "openai", "OpenAI", "https://api.openai.com/"),
    ("o1", "openai", "OpenAI", "https://api.openai.com/"),
    ("o3", "openai", "OpenAI", "https://api.openai.com/"),
    ("o4", "openai", "OpenAI", "https://api.openai.com/"),
    ("text-embedding-", "openai", "OpenAI", "https://api.openai.com/"),
    ("gpt-image-", "openai", "OpenAI", "https://api.openai.com/"),
    ("claude-", "anthropic", "Anthropic", "https://api.anthropic.com/"),
    ("gemini-", "google", "Google", "https://ai.google.dev/"),
    ("qwen", "alibaba", "阿里巴巴", "https://dashscope.aliyuncs.com/"),
    ("qwq", "alibaba", "阿里巴巴", "https://dashscope.aliyuncs.com/"),
    (
        "wan",
        "aliyun-wanx",
        "阿里云万象",
        "https://dashscope.aliyuncs.com/",
    ),
    (
        "wanx",
        "aliyun-wanx",
        "阿里云万象",
        "https://dashscope.aliyuncs.com/",
    ),
    ("doubao-", "volcengine", "火山", "https://ark.cn-beijing.volces.com/"),
    ("deepseek-", "deepseek", "DeepSeek", "https://api.deepseek.com/"),
    ("kimi-", "kimi", "Kimi（月之暗面）", "https://api.moonshot.cn/"),
    (
        "moonshot-",
        "kimi",
        "Kimi（月之暗面）",
        "https://api.moonshot.cn/",
    ),
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
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if ":" in name:
        name = name.split(":", 1)[0]
    name = re.sub(r"\s+\d{4}-\d{2}-\d{2}$", "", name)
    name = re.sub(r"\s+\d{8}$", "", name)
    name = re.sub(r"\s+\d{6}$", "", name)
    name = re.sub(r"\s+\d{4}$", "", name)
    parts = name.split()
    while parts and parts[-1].lower() in ROLE_RELEASE_SUFFIXES:
        parts.pop()
    return " ".join(parts) or canonical_code


def canonical_owner_for_model_code(model_code):
    """Return the canonical owner spec for a model code.

    A meta model always belongs to the company that built the model.
    Price sources such as SiliconFlow or OpenRouter never appear as a
    owner here. Returns ``None`` when the code is unknown so callers
    can fall back to historical data.
    """
    if not model_code:
        return None
    normalized = str(model_code).strip().lower()
    for prefix, code, name, url in META_MODEL_OWNER_RULES:
        if normalized.startswith(prefix):
            return {
                "code": code,
                "name": name,
                "website": url,
            }
    return None


def canonical_owner_name_for_code(owner_code):
    """Return the canonical display name for an owner code."""
    normalized = str(owner_code or "").strip().lower()
    if not normalized:
        return ""
    for _, code, name, _ in META_MODEL_OWNER_RULES:
        if code == normalized:
            return name
    return ""


def is_canonical_owner_code(owner_code):
    """Return True when ``owner_code`` is a model owner, not a supplier."""
    owner_code = str(owner_code or "").strip().lower()
    if not owner_code:
        return False
    return owner_code not in SUPPLIER_SOURCE_OWNER_ALIASES


def meta_model_owner_payload(model_code, provider=None):
    """Return owner fields for a meta model without creating FK rows."""
    spec = canonical_owner_for_model_code(model_code)
    if not spec:
        provider_code = str(getattr(provider, "code", "") or "").strip()
        if provider and is_canonical_owner_code(provider_code):
            spec = {
                "code": provider_code,
                "name": getattr(provider, "name", "") or provider_code,
                "website": getattr(provider, "website", "") or "",
            }
    if not spec or not is_canonical_owner_code(spec["code"]):
        return {
            "owner_code": "",
            "owner_name": "",
            "owner_website": "",
        }
    return {
        "owner_code": spec["code"],
        "owner_name": spec["name"],
        "owner_website": spec["website"],
    }


def resolve_meta_model_owner_fields(meta_model, provider=None):
    """Return the corrected owner fields for one meta model."""
    payload = meta_model_owner_payload(meta_model.code, provider)
    if payload["owner_code"]:
        return payload
    if is_canonical_owner_code(meta_model.owner_code):
        return {
            "owner_code": meta_model.owner_code,
            "owner_name": meta_model.owner_name,
            "owner_website": meta_model.owner_website,
        }
    return payload
