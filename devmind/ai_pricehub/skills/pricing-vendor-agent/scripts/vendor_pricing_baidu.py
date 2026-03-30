import re
from html import unescape

import requests

from ai_pricehub.vendor_pricing_common import build_vendor_metadata, resolve_acquisition_config


PAGE_DATA_URL = "https://bce.bdstatic.com/p3m/bce-doc/online/qianfan/doc/qianfan/s/page-data/wmh4sv6ya/page-data.json"
PRICING_URL = "https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya"
DEFAULT_CURRENCY = "CNY"


def sync_vendor_catalog(vendor: dict | None = None) -> dict:
    pricing_url, page_data_url = _resolve_urls(vendor)
    payload = _fetch_json(page_data_url)
    html = payload["result"]["data"]["markdownRemark"]["html"]
    models = _extract_models(html)
    return {
        "vendor": build_vendor_metadata(
            vendor=vendor,
            slug="baidu",
            name="Baidu Qianfan",
            pricing_url=pricing_url,
            default_method="page_data_json",
            resolved_pricing_url=page_data_url,
        ),
        "models": models,
        "notes": f"Extracted {len(models)} priced text models from the official Baidu Qianfan pricing table.",
    }


def _resolve_urls(vendor: dict | None) -> tuple[str, str]:
    acquisition = resolve_acquisition_config(vendor, default_method="page_data_json")
    pricing_url = acquisition.get("page_url") or (vendor or {}).get("pricing_url") or PRICING_URL
    page_data_url = acquisition.get("page_data_url") or PAGE_DATA_URL
    return pricing_url, page_data_url


def _fetch_json(url: str) -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _extract_models(html: str) -> list[dict]:
    tables = re.findall(r"<table.*?>.*?</table>", html, flags=re.DOTALL | re.IGNORECASE)
    models: dict[str, dict] = {}
    for table in tables:
        for row in _expand_rows(table):
            _, version_text, service, subitem, online_price, *_rest, unit = row
            if "推理服务" not in service or "token" not in unit.lower():
                continue
            price = _parse_price(online_price)
            if price is None:
                continue
            for version_name in _split_versions(version_text):
                if _derive_family(version_name) != "text":
                    continue
                _merge_price(
                    models=models,
                    version_name=version_name,
                    service=service,
                    subitem=subitem,
                    unit=unit,
                    price=price,
                )
    cleaned = []
    for item in sorted(models.values(), key=lambda candidate: candidate["model_name"].lower()):
        if item["input_price_per_million"] is None and item["output_price_per_million"] is None:
            continue
        cleaned.append({key: value for key, value in item.items() if not key.startswith("_")})
    return cleaned


def _expand_rows(table_html: str) -> list[list[str]]:
    rows_html = re.findall(r"<tr.*?>.*?</tr>", table_html, flags=re.DOTALL | re.IGNORECASE)
    expanded_rows = []
    active_spans: list[dict | None] = [None] * 9
    for row_html in rows_html:
        cells = _parse_cells(row_html)
        if not cells:
            continue
        row = []
        cell_index = 0
        for column in range(9):
            span = active_spans[column]
            if span and span["remaining"] > 0:
                row.append(span["value"])
                span["remaining"] -= 1
                continue
            if cell_index >= len(cells):
                row.append("")
                active_spans[column] = None
                continue
            value, rowspan = cells[cell_index]
            cell_index += 1
            row.append(value)
            active_spans[column] = {"value": value, "remaining": rowspan - 1} if rowspan > 1 else None
        if row and row[0] == "模型名称":
            continue
        expanded_rows.append(row)
    return expanded_rows


def _parse_cells(row_html: str) -> list[tuple[str, int]]:
    results = []
    cell_pattern = re.compile(r"<(td|th)([^>]*)>(.*?)</\1>", flags=re.DOTALL | re.IGNORECASE)
    for _, attrs, inner_html in cell_pattern.findall(row_html):
        rowspan_match = re.search(r'rowspan="(\d+)"', attrs, flags=re.IGNORECASE)
        rowspan = int(rowspan_match.group(1)) if rowspan_match else 1
        results.append((_clean_cell_text(inner_html), rowspan))
    return results


def _clean_cell_text(inner_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _split_versions(version_text: str) -> list[str]:
    versions = []
    for part in version_text.split("\n"):
        cleaned = part.strip()
        if not cleaned or "如开启思考模式" in cleaned or "计费详情请查看" in cleaned:
            continue
        versions.append(cleaned)
    return versions


def _derive_family(version_name: str) -> str | None:
    lowered = version_name.lower()
    blocked = ["-vl", "vision", "embedding", "rerank", "image", "video", "tts", "asr", "audio"]
    return None if any(token in lowered for token in blocked) else "text"


def _normalize_version_name(version_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", version_name).strip()
    aliases = {
        "moonshot-kimi-k2-instruct": "Kimi-K2-Instruct",
        "kimi-k2-instruct": "Kimi-K2-Instruct",
    }
    return aliases.get(cleaned.lower(), cleaned)


def _parse_price(text: str) -> float | None:
    cleaned = text.strip()
    if not cleaned or cleaned in {"-", "触发"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    return float(match.group(1)) if match else None


def _normalize_to_per_million(price: float, unit: str) -> float:
    normalized_unit = unit.lower()
    if "千token" in normalized_unit or "千tokens" in normalized_unit:
        return price * 1000
    return price


def _merge_price(*, models: dict[str, dict], version_name: str, service: str, subitem: str, unit: str, price: float) -> None:
    normalized_name = _normalize_version_name(version_name)
    key = normalized_name.lower()
    model = models.setdefault(
        key,
        {
            "model_name": normalized_name,
            "aliases": [normalized_name, version_name.strip()],
            "family": "text",
            "input_price_per_million": None,
            "output_price_per_million": None,
            "currency": DEFAULT_CURRENCY,
            "notes": "Extracted from Baidu Qianfan official pricing table.",
            "_meta": {"input_score": -1, "output_score": -1, "cache_hit": None},
        },
    )
    normalized_price = _normalize_to_per_million(price, unit)
    subitem_clean = subitem.replace(" ", "")
    service_clean = service.replace(" ", "")
    pricing_context = f"{service_clean} {subitem_clean}".strip()
    subitem_kind = _subitem_kind(subitem_clean, pricing_context)
    score = _subitem_score(pricing_context)
    if subitem_clean.startswith("命中缓存"):
        model["_meta"]["cache_hit"] = normalized_price
        return
    if subitem_kind == "input" and _should_replace_price(
        current_price=model["input_price_per_million"],
        current_score=model["_meta"]["input_score"],
        candidate_price=normalized_price,
        candidate_score=score,
    ):
        model["input_price_per_million"] = normalized_price
        model["_meta"]["input_score"] = score
    if subitem_kind == "output" and _should_replace_price(
        current_price=model["output_price_per_million"],
        current_score=model["_meta"]["output_score"],
        candidate_price=normalized_price,
        candidate_score=score,
    ):
        model["output_price_per_million"] = normalized_price
        model["_meta"]["output_score"] = score
    notes = ["Extracted from Baidu Qianfan official pricing table."]
    if model["_meta"]["cache_hit"] is not None:
        notes.append(f"cache_hit_input={model['_meta']['cache_hit']}元/百万token")
    model["notes"] = "; ".join(notes)


def _subitem_kind(subitem: str, pricing_context: str = "") -> str:
    if "命中缓存" in subitem:
        return ""
    if "输入" in subitem and "输出" not in subitem:
        return "input"
    if "输出" in subitem and "输入" not in subitem:
        return "output"
    if "输入" in pricing_context and "输出" not in pricing_context:
        return "input"
    if "输出" in pricing_context and "输入" not in pricing_context:
        return "output"
    return ""


def _subitem_score(subitem: str) -> int:
    if subitem in {"输入", "输出"}:
        return 100
    range_score = _range_upper_bound_score(subitem)
    if range_score is not None:
        return range_score
    return 10


def _range_upper_bound_score(subitem: str) -> int | None:
    normalized = subitem.lower()
    values = [int(value) for value in re.findall(r"(\d+)k", normalized)]
    if not values:
        return None
    return max(values)


def _should_replace_price(*, current_price: float | None, current_score: int, candidate_price: float, candidate_score: int) -> bool:
    if current_price is None:
        return True
    if candidate_price != current_price:
        return candidate_price > current_price
    return candidate_score > current_score
