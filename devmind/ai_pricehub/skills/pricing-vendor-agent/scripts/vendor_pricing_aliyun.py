import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import requests


def _bootstrap_django() -> None:
    project_root = Path(__file__).resolve().parents[5]
    package_root = project_root / "devmind"
    for candidate in (project_root, package_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

    try:
        import django
        from django.conf import settings
    except ImportError:
        return

    if not settings.configured:
        django.setup()


_bootstrap_django()

from ai_pricehub.extraction import ExtractedPricingCatalog
from ai_pricehub.tracked_llm import build_tracking_state, invoke_tracked_structured_llm
from ai_pricehub.vendor_pricing_common import build_vendor_metadata


PRICING_URL = "https://help.aliyun.com/zh/model-studio/model-pricing"
DEFAULT_VENDOR_URL = "https://bailian.console.aliyun.com/cn-beijing/?tab=doc#/doc/?type=model&url=2987148"
ALIYUN_API_URL = (
    "https://bailian-cs.console.aliyun.com/data/api.json"
    "?action=BroadScopeAspnGateway&product=sfm_bailian"
    "&api=zeldaHttp.dashscopeModel./zelda/api/v1/modelCenter/listFoundationModels&_v=undefined"
)
ALIYUN_REFERER_TEMPLATE = (
    "https://bailian.console.aliyun.com/{region}"
    "?spm=a219a.7839801.0.0&tab=model#/model-market/detail/{model}"
)
DEFAULT_CURRENCY = "CNY"
TEXT_MODEL_PREFIXES = (
    "qwen",
    "deepseek",
    "qwq",
    "qvq",
    "glm",
    "kimi",
    "moonshot-kimi",
)
LLM_TEXT_CHAR_LIMIT = 48000
LLM_TABLE_CHAR_LIMIT = 36000
LLM_CONTEXT_CHAR_LIMIT = 12000


def sync_vendor_catalog(vendor: dict[str, Any] | None = None) -> dict[str, Any]:
    api_models: list[dict[str, Any]] = []
    api_error = None
    api_payload_count = 0
    model_queries = _resolve_target_models(vendor)
    session_config = _resolve_api_session_config(vendor)
    if model_queries:
        try:
            api_payloads = _query_models_via_api(
                vendor=vendor,
                model_queries=model_queries,
            )
            api_payload_count = len(api_payloads)
            api_models = _extract_models_from_api_payloads(
                payloads=api_payloads,
                vendor=vendor,
            )
        except Exception as exc:
            api_error = str(exc)
    else:
        api_error = "No Aliyun target models were derived from AGIOne source vendors."

    models = api_models
    notes_parts = [
        f"Extracted {len(models)} Aliyun priced models from the Aliyun model center API."
    ]
    notes_parts.append("Primary extraction path: Aliyun model center API only.")
    if api_error:
        notes_parts.append(f"api_error={api_error}")

    return {
        "vendor": build_vendor_metadata(
            vendor=vendor,
            slug="aliyun",
            name="Aliyun",
            pricing_url=DEFAULT_VENDOR_URL,
            default_method="api",
            resolved_pricing_url=session_config["api_url"],
        ),
        "models": models,
        "notes": " ".join(notes_parts),
        "source_type": "vendor_python_skill",
        "raw_payload": {
            "resolved_api_url": session_config["api_url"],
            "resolved_region": session_config["region"],
            "api_only": True,
            "api_attempted": bool(model_queries),
            "api_used": bool(api_payload_count),
            "api_query_model_count": len(model_queries),
            "api_query_models": model_queries,
            "api_payload_count": api_payload_count,
            "api_error": api_error,
            "page_fallback_used": False,
        },
    }


def _resolve_aliyun_pricing_url(vendor: dict[str, Any] | None) -> str:
    acquisition = dict((vendor or {}).get("acquisition") or {})
    page_url = str(acquisition.get("page_url") or "").strip()
    if page_url:
        return page_url
    return PRICING_URL


def _extract_models_with_llm(
    *,
    html: str,
    vendor: dict[str, Any] | None,
    pricing_url: str,
) -> list[dict[str, Any]]:
    result, _usage, _llm_settings = invoke_tracked_structured_llm(
        schema=ExtractedPricingCatalog,
        messages=_build_llm_prompt(pricing_url=pricing_url, html=html),
        preferred_config_uuid=(vendor or {}).get("parser_llm_config_uuid") or None,
        node_name="ai_pricehub_vendor_skill_aliyun",
        state=build_tracking_state(
            vendor=vendor,
            node_name="ai_pricehub_vendor_skill_aliyun",
            source_path="ai_pricehub.skill.aliyun",
            metadata={"pricing_url": pricing_url},
        ),
        max_tokens=5000,
        temperature=0,
    )
    payload = result.model_dump()
    return _finalize_models(payload.get("models", []))


def _resolve_target_models(vendor: dict[str, Any] | None) -> list[str]:
    queries: list[str] = []
    for value in (vendor or {}).get("_primary_model_queries") or []:
        model_name = str(value or "").strip().lower()
        if model_name and model_name not in queries:
            queries.append(model_name)
    return queries


def _query_models_via_api(
    *,
    vendor: dict[str, Any] | None,
    model_queries: list[str],
) -> list[dict[str, Any]]:
    session_config = _resolve_api_session_config(vendor)
    if not session_config["cookie"]:
        raise ValueError("Aliyun API cookie is required for model-center price queries.")

    responses: list[dict[str, Any]] = []
    for model_query in model_queries:
        response = requests.post(
            session_config["api_url"],
            headers=_build_api_headers(
                cookie=session_config["cookie"],
                region=session_config["region"],
                model_query=model_query,
            ),
            data=_build_api_form_data(
                region=session_config["region"],
                model_query=model_query,
            ),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        responses.append({"model_query": model_query, "payload": payload})
    return responses


def _resolve_api_session_config(vendor: dict[str, Any] | None) -> dict[str, str]:
    acquisition = dict((vendor or {}).get("acquisition") or {})
    return {
        "api_url": str(acquisition.get("api_url") or ALIYUN_API_URL).strip() or ALIYUN_API_URL,
        "region": str(acquisition.get("region") or os.getenv("AIPRICEHUB_ALIYUN_REGION") or "cn-beijing").strip() or "cn-beijing",
        "cookie": str(acquisition.get("cookie") or os.getenv("AIPRICEHUB_ALIYUN_COOKIE") or "").strip(),
    }


def _build_api_headers(*, cookie: str, region: str, model_query: str) -> dict[str, str]:
    referer = ALIYUN_REFERER_TEMPLATE.format(region=region, model=model_query)
    return {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://bailian.console.aliyun.com",
        "referer": referer,
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "cookie": cookie,
    }


def _build_api_form_data(*, region: str, model_query: str) -> dict[str, str]:
    return {
        "params": json.dumps(
            {
                "Api": "zeldaHttp.dashscopeModel./zelda/api/v1/modelCenter/listFoundationModels",
                "V": "1.0",
                "Data": {
                    "input": {
                        "pageNo": 1,
                        "pageSize": 50,
                        "group": True,
                        "model": model_query,
                        "querySampleCode": True,
                        "queryGroupByModel": True,
                        "queryWorkspaceLimit": True,
                        "queryPrice": True,
                        "queryQuota": False,
                        "queryQpmInfo": True,
                        "queryApplyStatus": True,
                        "queryPermissions": True,
                        "queryActivationStatus": True,
                    },
                    "cornerstoneParam": {
                        "feTraceId": str(uuid.uuid4()),
                        "feURL": ALIYUN_REFERER_TEMPLATE.format(region=region, model=model_query),
                        "protocol": "V2",
                        "console": "ONE_CONSOLE",
                        "productCode": "p_efm",
                        "switchUserType": 3,
                        "domain": "bailian.console.aliyun.com",
                        "consoleSite": "BAILIAN_ALIYUN",
                        "xsp_lang": "zh-CN",
                    },
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "region": region,
    }


def _extract_models_from_api_payloads(
    *,
    payloads: list[dict[str, Any]],
    vendor: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not payloads:
        return []

    evidence_blocks: list[str] = []
    for item in payloads:
        evidence_blocks.append(
            "Query Model: "
            f"{item['model_query']}\n"
            "API Response JSON:\n"
            f"{json.dumps(item['payload'], ensure_ascii=False)}"
        )
    prompt = (
        "You are extracting official Aliyun Model Studio pricing from the model center API.\n"
        "Requirements:\n"
        "- Use only the API JSON evidence.\n"
        "- Return only China mainland / 中国内地 / domestic prices.\n"
        "- Ignore global, international, overseas, and workspace-specific discounted prices.\n"
        "- Normalize prices to CNY per 1M tokens.\n"
        "- If multiple token ranges exist for one model, keep the highest standard range price.\n"
        "- Preserve the queried model name as the canonical model_name when it matches the API result.\n"
        "- Omit models when the response does not expose a reliable domestic standard price.\n\n"
        f"{chr(10).join(evidence_blocks)}"
    )
    result, _usage, _llm_settings = invoke_tracked_structured_llm(
        schema=ExtractedPricingCatalog,
        messages=[
            {
                "role": "system",
                "content": "Extract structured AI model token pricing from official vendor API responses and return valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        preferred_config_uuid=(vendor or {}).get("parser_llm_config_uuid") or None,
        node_name="ai_pricehub_vendor_skill_aliyun_api",
        state=build_tracking_state(
            vendor=vendor,
            node_name="ai_pricehub_vendor_skill_aliyun_api",
            source_path="ai_pricehub.skill.aliyun.api",
            metadata={"query_count": len(payloads)},
        ),
        max_tokens=5000,
        temperature=0,
    )
    payload = result.model_dump()
    return _finalize_models(payload.get("models", []))


def _build_llm_prompt(*, pricing_url: str, html: str) -> list[dict[str, str]]:
    table_text = _extract_table_text(html)
    page_text = _html_to_text(html)
    prompt = (
        "You are extracting official Aliyun Model Studio pricing into structured JSON.\n"
        f"Source URL: {pricing_url}\n"
        "Requirements:\n"
        "- Return only standard domestic (China mainland) model pricing.\n"
        "- market_scope should be domestic when the source explicitly marks China mainland or domestic pricing.\n"
        "- If the source shows regional groups like 中国内地 / 国内, treat them as domestic.\n"
        "- Ignore international, overseas, and global pricing rows.\n"
        "- Normalize prices to CNY per 1M tokens.\n"
        "- Ignore cache, batch, promo, discount, and free-tier pricing unless it is the only standard price shown.\n"
        "- When the same model has token-range pricing, keep the highest standard range price.\n"
        "- Keep model_name canonical and concise.\n"
        "- aliases may include vendor naming variants.\n"
        "- family should be text when the model is a text/chat model.\n"
        "- notes should briefly explain region or range normalization when relevant.\n\n"
        "Use the structured table rows as the primary evidence. "
        "Use the page context only as a fallback for headings or notes.\n\n"
        "Structured table rows:\n"
        f"{table_text or 'No table rows extracted.'}\n\n"
        "Supplemental page context:\n"
        f"{page_text}"
    )
    return [
        {
            "role": "system",
            "content": "Extract AI model token pricing from vendor pages and return valid structured JSON.",
        },
        {"role": "user", "content": prompt},
    ]


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(tr|p|div|h[1-6]|li)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned[:LLM_CONTEXT_CHAR_LIMIT]


def _extract_table_text(html: str) -> str:
    rows = re.findall(r"<tr\b.*?</tr>", html, flags=re.DOTALL | re.IGNORECASE)
    rendered_rows: list[str] = []
    for row in rows:
        texts = _extract_texts(row)
        if not texts:
            continue
        normalized_cells = [cell.replace("\n", " / ") for cell in texts if cell]
        if not normalized_cells:
            continue
        rendered_rows.append(" | ".join(normalized_cells))
    return "\n".join(rendered_rows)[:LLM_TABLE_CHAR_LIMIT]


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_models_deterministic(html: str) -> list[dict[str, Any]]:
    row_matches = list(
        re.finditer(r"<tr\b.*?</tr>", html, flags=re.DOTALL | re.IGNORECASE)
    )
    models: dict[tuple[str, str], dict[str, Any]] = {}
    current_model = ""
    current_market_scope = "unknown"

    for row_match in row_matches:
        row = row_match.group(0)
        texts = _extract_texts(row)
        if not texts:
            continue

        if "模型名称" in texts and "输入单价（每百万Token）" in "".join(texts):
            current_model = ""
            current_market_scope = "unknown"
            continue

        if _is_section_heading(texts):
            current_model = ""
            continue

        market_scope = _find_market_scope(texts)
        if market_scope == "unknown":
            market_scope = _infer_market_scope_from_context(
                html[max(0, row_match.start() - 2500):row_match.start()]
            )
        if market_scope != "unknown":
            current_market_scope = market_scope
        elif _is_market_scope_heading(texts):
            continue
        market_scope = current_market_scope
        if market_scope not in {"domestic", "unknown"}:
            continue

        model_name = _detect_model_name(texts)
        if model_name:
            current_model = model_name

        prices = _extract_prices(texts)
        if len(prices) < 2:
            continue
        if not current_model or _derive_family_from_name(current_model) != "text":
            continue

        range_text = _find_range_text(texts)
        mode_text = _find_mode_text(texts)
        input_price, output_price, notes = _resolve_pricing(
            prices=prices,
            range_text=range_text,
            mode_text=mode_text,
            market_scope=market_scope,
        )
        item = {
            "model_name": current_model,
            "aliases": [current_model],
            "family": "text",
            "currency": DEFAULT_CURRENCY,
            "input_price_per_million": input_price,
            "output_price_per_million": output_price,
            "market_scope": market_scope,
            "notes": notes,
            "_has_range": bool(range_text),
        }
        _upsert_model(models, item)

    return _clean_models(models.values())


def _finalize_models(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    models: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        model_name = str(item.get("model_name") or "").strip()
        if not model_name:
            continue
        family = item.get("family") or _derive_family_from_name(model_name)
        if family != "text":
            continue
        market_scope = _normalize_market_scope(item.get("market_scope"))
        if market_scope not in {"domestic", "unknown"}:
            continue
        normalized = {
            "model_name": model_name,
            "aliases": _normalize_aliases(item.get("aliases"), model_name),
            "family": "text",
            "currency": str(item.get("currency") or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY,
            "input_price_per_million": _normalize_price(item.get("input_price_per_million")),
            "output_price_per_million": _normalize_price(item.get("output_price_per_million")),
            "market_scope": market_scope,
            "notes": (str(item.get("notes") or "").strip() or None),
            "_has_range": _notes_imply_range(item.get("notes")),
        }
        _upsert_model(models, normalized)
    return _retain_domestic_prices(_clean_models(models.values()))


def _clean_models(items: Any) -> list[dict[str, Any]]:
    cleaned = []
    for item in sorted(
        items,
        key=lambda model: (
            model["model_name"].lower(),
            model.get("market_scope") or "",
        ),
    ):
        cleaned.append(
            {key: value for key, value in item.items() if not key.startswith("_")}
        )
    return cleaned


def _retain_domestic_prices(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item["model_name"].lower(), []).append(item)

    retained: list[dict[str, Any]] = []
    for model_items in grouped.values():
        domestic_items = [
            item for item in model_items if item.get("market_scope") == "domestic"
        ]
        if domestic_items:
            retained.extend(domestic_items)
            continue
        unknown_items = [
            item for item in model_items if item.get("market_scope") == "unknown"
        ]
        retained.extend(unknown_items)
    return sorted(
        retained,
        key=lambda model: (
            model["model_name"].lower(),
            model.get("market_scope") or "",
        ),
    )


def _merge_models(
    *,
    primary_items: list[dict[str, Any]],
    supplemental_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not primary_items:
        return supplemental_items
    if not supplemental_items:
        return primary_items

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in primary_items:
        merged[(item["model_name"].strip().lower(), item.get("market_scope") or "unknown")] = dict(item)

    for item in supplemental_items:
        key = (
            item["model_name"].strip().lower(),
            item.get("market_scope") or "unknown",
        )
        existing = merged.get(key)
        if existing is None:
            if item.get("market_scope") not in {"domestic", "unknown"}:
                continue
            merged[key] = dict(item)
            continue
        merged[key] = _prefer_primary(existing=existing, supplemental=item)

    return _retain_domestic_prices(_clean_models(merged.values()))


def _prefer_primary(
    *,
    existing: dict[str, Any],
    supplemental: dict[str, Any],
) -> dict[str, Any]:
    existing_total = float(existing.get("input_price_per_million") or 0) + float(existing.get("output_price_per_million") or 0)
    supplemental_total = float(supplemental.get("input_price_per_million") or 0) + float(supplemental.get("output_price_per_million") or 0)
    if existing.get("market_scope") == "domestic":
        return dict(existing)
    if supplemental.get("market_scope") == "domestic" and existing.get("market_scope") != "domestic":
        return dict(supplemental)
    if existing_total <= 0 and supplemental_total > 0:
        return dict(supplemental)
    return dict(existing)


def _normalize_aliases(raw_aliases: Any, model_name: str) -> list[str]:
    aliases: list[str] = []
    if isinstance(raw_aliases, list):
        for alias in raw_aliases:
            text = str(alias or "").strip()
            if text and text not in aliases:
                aliases.append(text)
    if model_name not in aliases:
        aliases.insert(0, model_name)
    return aliases


def _normalize_market_scope(value: Any) -> str:
    scope = str(value or "").strip().lower()
    if scope in {"domestic", "international", "global"}:
        return scope
    aliases = {
        "china": "domestic",
        "china mainland": "domestic",
        "mainland china": "domestic",
        "cn": "domestic",
        "国内": "domestic",
        "中国内地": "domestic",
        "international": "international",
        "global international": "international",
        "海外": "international",
        "国际": "international",
        "global": "global",
        "全球": "global",
    }
    return aliases.get(scope, "unknown")


def _normalize_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _notes_imply_range(notes: Any) -> bool:
    text = str(notes or "")
    return "range" in text.lower() or "区间" in text


def _extract_texts(row_html: str) -> list[str]:
    cells = re.findall(
        r"<(td|th)\b[^>]*>(.*?)</\1>",
        row_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    texts = []
    for _, raw in cells:
        text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("help-letter-space", " ").replace("&nbsp;", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        if cleaned:
            texts.append(cleaned)
    return texts


def _find_range_text(texts: list[str]) -> str | None:
    return next(
        (text for text in texts if "Token≤" in text or ("Token" in text and "<" in text)),
        None,
    )


def _find_mode_text(texts: list[str]) -> str | None:
    return next((text for text in texts if "思考模式" in text or "非思考" in text), None)


def _find_market_scope(texts: list[str]) -> str:
    merged = " ".join(texts).lower()
    domestic_tokens = ["国内", "中国站", "中国地区", "中国内地", "华北", "华东", "华南", "cn-beijing", "杭州", "北京", "上海", "深圳"]
    international_tokens = ["国际", "海外", "新加坡", "硅谷", "弗吉尼亚", "singapore", "international", "overseas"]
    global_tokens = ["全球", "global"]
    if any(token in merged for token in domestic_tokens):
        return "domestic"
    if any(token in merged for token in international_tokens):
        return "international"
    if any(token in merged for token in global_tokens):
        return "global"
    return "unknown"


def _infer_market_scope_from_context(context_html: str) -> str:
    context_text = re.sub(r"<br\s*/?>", "\n", context_html, flags=re.IGNORECASE)
    context_text = re.sub(r"<[^>]+>", " ", context_text)
    context_text = re.sub(r"\s+", " ", context_text).strip().lower()
    if not context_text:
        return "unknown"

    scope_markers = {
        "domestic": [
            "中国内地",
            "国内",
            "中国站",
            "华北",
            "华东",
            "华南",
            "cn-beijing",
            "杭州",
            "北京",
            "上海",
            "深圳",
        ],
        "international": [
            "国际",
            "海外",
            "新加坡",
            "硅谷",
            "弗吉尼亚",
            "singapore",
            "international",
            "overseas",
        ],
        "global": ["全球", "global"],
    }

    best_scope = "unknown"
    best_index = -1
    for scope, markers in scope_markers.items():
        for marker in markers:
            index = context_text.rfind(marker.lower())
            if index > best_index:
                best_scope = scope
                best_index = index
    return best_scope


def _is_market_scope_heading(texts: list[str]) -> bool:
    merged = " ".join(texts)
    if "元" in merged or "token" in merged.lower():
        return False
    return any(token in merged for token in ["国内", "国际", "中国站", "海外", "新加坡", "全球"])


def _is_section_heading(texts: list[str]) -> bool:
    merged = " ".join(texts).strip()
    lowered = merged.lower()
    if "元" in merged or "token" in lowered:
        return False
    if _find_market_scope(texts) != "unknown":
        return False
    if any(token in merged for token in ["模型名称", "输入单价", "输出单价", "免费额度", "模式"]):
        return False
    if any(token in merged for token in ["计费规则", "影响计费", "说明", "更多模型"]):
        return True
    return bool(re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9 ._-]{2,40}", merged)) and not lowered.startswith(TEXT_MODEL_PREFIXES)


def _extract_prices(texts: list[str]) -> list[float]:
    prices = []
    for text in texts:
        if "元" not in text:
            continue
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元", text)
        if match:
            prices.append(float(match.group(1)))
    return prices


def _detect_model_name(texts: list[str]) -> str | None:
    for text in texts:
        lowered = text.lower()
        if "token" in lowered or "元" in lowered:
            continue
        if any(token in text for token in ["模式", "半价", "享有折扣", "免费额度"]):
            continue
        if lowered.startswith(TEXT_MODEL_PREFIXES):
            return text
    return None


def _derive_family_from_name(name: str) -> str | None:
    return "text" if name.lower().startswith(TEXT_MODEL_PREFIXES) else None


def _resolve_pricing(
    *,
    prices: list[float],
    range_text: str | None,
    mode_text: str | None,
    market_scope: str,
) -> tuple[float | None, float | None, str]:
    region_label = {
        "domestic": "China mainland",
        "international": "international",
        "global": "global",
        "unknown": "default",
    }.get(market_scope, "default")
    if range_text:
        return prices[0], prices[1], f"Aliyun {region_label} pricing row for range {range_text}."
    input_price = prices[0] if prices else None
    output_candidates = prices[1:] if len(prices) > 1 else []
    output_price = max(output_candidates) if output_candidates else None
    return input_price, output_price, f"Aliyun {region_label} pricing row for mode {mode_text or 'unknown mode'}."


def _upsert_model(models: dict[tuple[str, str], dict[str, Any]], item: dict[str, Any]) -> None:
    key = (
        item["model_name"].strip().lower(),
        item.get("market_scope") or "unknown",
    )
    existing = models.get(key)
    if existing is None or _prefer_candidate(existing, item):
        models[key] = item


def _prefer_candidate(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    existing_has_range = bool(existing.get("_has_range"))
    candidate_has_range = bool(candidate.get("_has_range"))
    existing_scope = existing.get("market_scope") or "unknown"
    candidate_scope = candidate.get("market_scope") or "unknown"
    existing_total = float(existing.get("input_price_per_million") or 0) + float(existing.get("output_price_per_million") or 0)
    candidate_total = float(candidate.get("input_price_per_million") or 0) + float(candidate.get("output_price_per_million") or 0)
    if existing_has_range or candidate_has_range:
        if candidate_has_range != existing_has_range:
            return candidate_has_range
        if candidate_total != existing_total:
            return candidate_total > existing_total
    elif candidate_total != existing_total:
        if existing_scope == candidate_scope:
            return candidate_total > existing_total
        if existing_scope == "unknown" and candidate_scope == "unknown":
            return candidate_total > existing_total
        return candidate_total > existing_total
    return len(str(candidate.get("notes") or "")) > len(str(existing.get("notes") or ""))


if __name__ == "__main__":
    print(json.dumps(sync_vendor_catalog(), ensure_ascii=False, indent=2))
