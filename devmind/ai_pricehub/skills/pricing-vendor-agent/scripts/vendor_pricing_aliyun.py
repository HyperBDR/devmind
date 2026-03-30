import json
import re

import requests


PRICING_URL = "https://help.aliyun.com/zh/model-studio/model-pricing"
DEFAULT_CURRENCY = "CNY"
TEXT_MODEL_PREFIXES = ("qwen", "deepseek", "qwq", "qvq", "glm", "kimi", "moonshot-kimi")


def sync_vendor_catalog() -> dict:
    html = _fetch_text(PRICING_URL)
    models = _extract_models(html)
    return {
        "vendor": {
            "slug": "aliyun",
            "name": "Aliyun",
            "pricing_url": "https://bailian.console.aliyun.com/cn-beijing/?tab=doc#/doc/?type=model&url=2987148",
            "resolved_pricing_url": PRICING_URL,
        },
        "models": models,
        "notes": f"Extracted {len(models)} Aliyun priced models from the official pricing page.",
        "source_type": "vendor_python_skill",
    }


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_models(html: str) -> list[dict]:
    rows = re.findall(r"<tr\b.*?</tr>", html, flags=re.DOTALL | re.IGNORECASE)
    models: dict[tuple[str, str], dict] = {}
    current_model = ""
    current_market_scope = "unknown"

    for row in rows:
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
        if market_scope != "unknown":
            current_market_scope = market_scope
        elif _is_market_scope_heading(texts):
            continue
        market_scope = current_market_scope

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

    cleaned = []
    for item in sorted(models.values(), key=lambda model: (model["model_name"].lower(), model.get("market_scope", ""))):
        cleaned.append({key: value for key, value in item.items() if not key.startswith("_")})
    return cleaned


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
    domestic_tokens = ["国内", "中国站", "中国地区", "cn-beijing", "杭州", "北京", "上海", "深圳"]
    international_tokens = ["国际", "海外", "新加坡", "硅谷", "弗吉尼亚", "singapore", "international", "overseas"]
    if any(token in merged for token in domestic_tokens):
        return "domestic"
    if any(token in merged for token in international_tokens):
        return "international"
    return "unknown"


def _is_market_scope_heading(texts: list[str]) -> bool:
    merged = " ".join(texts)
    if "元" in merged or "token" in merged.lower():
        return False
    return any(token in merged for token in ["国内", "国际", "中国站", "海外", "新加坡"])


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
        "unknown": "default",
    }.get(market_scope, "default")
    if range_text:
        return prices[0], prices[1], f"Aliyun {region_label} pricing row for range {range_text}."
    input_price = prices[0] if prices else None
    output_candidates = prices[1:] if len(prices) > 1 else []
    output_price = max(output_candidates) if output_candidates else None
    return input_price, output_price, f"Aliyun {region_label} pricing row for mode {mode_text or 'unknown mode'}."


def _upsert_model(models: dict[tuple[str, str], dict], item: dict) -> None:
    key = (item["model_name"].strip().lower(), item.get("market_scope") or "unknown")
    existing = models.get(key)
    if existing is None or _prefer_candidate(existing, item):
        models[key] = item


def _prefer_candidate(existing: dict, candidate: dict) -> bool:
    existing_has_range = bool(existing.get("_has_range"))
    candidate_has_range = bool(candidate.get("_has_range"))
    existing_total = float(existing.get("input_price_per_million") or 0) + float(existing.get("output_price_per_million") or 0)
    candidate_total = float(candidate.get("input_price_per_million") or 0) + float(candidate.get("output_price_per_million") or 0)
    if existing_has_range or candidate_has_range:
        if candidate_has_range != existing_has_range:
            return candidate_has_range
        if candidate_total != existing_total:
            return candidate_total > existing_total
    elif candidate_total != existing_total:
        return candidate_total < existing_total
    return len(candidate.get("notes", "")) > len(existing.get("notes", ""))


if __name__ == "__main__":
    print(json.dumps(sync_vendor_catalog(), ensure_ascii=False, indent=2))
