from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PAGE_DATA_URL = (
    "https://bce.bdstatic.com/p3m/bce-doc/online/qianfan/doc/qianfan/s/"
    "page-data/wmh4sv6ya/page-data.json"
)
PRICING_URL = "https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya"
DEFAULT_CURRENCY = "CNY"


class BaiduPriceCatalogCollector:
    """Collect Baidu Qianfan official prices into standard catalog JSON."""

    provider_code = "baidu"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Baidu Qianfan official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        pricing_url, page_data_url = resolve_urls(vendor)
        html = str(vendor.get("raw_html") or "")
        if not html and vendor.get("verify_source") is False:
            return sync_official_vendor_catalog("baidu", vendor)
        if not html:
            payload = fetch_json(page_data_url)
            html = extract_html_from_payload(payload)

        models = extract_models(html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        provider_name = str(
            vendor.get("provider_name") or "百度千帆"
        ).strip()
        currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
        return build_text_token_standard_catalog(
            provider_code="baidu",
            provider_name=provider_name,
            currency=currency or DEFAULT_CURRENCY,
            source_url=pricing_url,
            models=models,
            notes=(
                "Extracted Baidu Qianfan text model prices from the "
                "official pricing table."
            ),
            raw_payload={
                "provider_code": "baidu",
                "collector": "llm_ops.price_collectors.baidu",
                "source_url": pricing_url,
                "page_data_url": page_data_url,
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_html_supplied": bool(vendor.get("raw_html")),
                "parsed_models": len(models),
            },
        )


def resolve_urls(vendor: dict[str, Any]) -> tuple[str, str]:
    """Return the configured Baidu pricing page and page-data URLs."""
    acquisition = dict(vendor.get("acquisition") or {})
    pricing_url = str(
        acquisition.get("page_url")
        or vendor.get("source_url")
        or vendor.get("pricing_url")
        or PRICING_URL
    ).strip()
    page_data_url = str(
        acquisition.get("page_data_url")
        or vendor.get("page_data_url")
        or PAGE_DATA_URL
    ).strip()
    return pricing_url, page_data_url


def fetch_json(url: str) -> dict[str, Any]:
    """Fetch Baidu Gatsby page-data JSON."""
    response = requests.get(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def extract_html_from_payload(payload: dict[str, Any]) -> str:
    """Return rendered document HTML from Baidu page-data JSON."""
    try:
        return str(payload["result"]["data"]["markdownRemark"]["html"] or "")
    except (KeyError, TypeError):
        return ""


def extract_models(html: str) -> list[dict[str, Any]]:
    """Extract Baidu Qianfan text model price rows from HTML tables."""
    tables = re.findall(
        r"<table.*?>.*?</table>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    models: dict[str, dict[str, Any]] = {}
    for table in tables:
        for row in expand_rows(table):
            if len(row) < 9:
                continue
            _, version_text, service, subitem, online_price, *_rest, unit = row
            if "推理服务" not in service or "token" not in unit.lower():
                continue
            price = parse_price(online_price)
            if price is None:
                continue
            for version_name in split_versions(version_text):
                if not is_text_model(version_name):
                    continue
                merge_price(
                    models=models,
                    version_name=version_name,
                    service=service,
                    subitem=subitem,
                    unit=unit,
                    price=price,
                )

    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_name"].lower(),
        )
        if (
            item.get("input_price_per_million") is not None
            or item.get("output_price_per_million") is not None
        )
    ]


def expand_rows(table_html: str) -> list[list[str]]:
    """Expand Baidu table rows while preserving row spans."""
    rows_html = re.findall(
        r"<tr.*?>.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    expanded_rows = []
    active_spans: list[dict[str, Any] | None] = [None] * 9
    for row_html in rows_html:
        cells = parse_cells(row_html)
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
            active_spans[column] = (
                {"value": value, "remaining": rowspan - 1}
                if rowspan > 1
                else None
            )
        if row and row[0] == "模型名称":
            continue
        expanded_rows.append(row)
    return expanded_rows


def parse_cells(row_html: str) -> list[tuple[str, int]]:
    """Parse one HTML row into cell text plus row span."""
    results = []
    pattern = re.compile(
        r"<(td|th)([^>]*)>(.*?)</\1>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    for _, attrs, inner_html in pattern.findall(row_html):
        rowspan_match = re.search(
            r'rowspan=["\']?(\d+)["\']?',
            attrs,
            flags=re.IGNORECASE,
        )
        rowspan = int(rowspan_match.group(1)) if rowspan_match else 1
        results.append((clean_cell_text(inner_html), rowspan))
    return results


def clean_cell_text(inner_html: str) -> str:
    """Convert one HTML cell body into normalized text."""
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def split_versions(version_text: str) -> list[str]:
    """Split a Baidu version cell into model names."""
    versions = []
    for part in version_text.split("\n"):
        cleaned = part.strip()
        if not cleaned:
            continue
        if (
            "如开启思考模式" in cleaned
            or "计费详情请查看" in cleaned
        ):
            continue
        versions.append(cleaned)
    return versions


def is_text_model(model_name: str) -> bool:
    """Return whether a Baidu model row is text-token pricing."""
    lowered = model_name.lower()
    blocked = (
        "-vl",
        "vision",
        "embedding",
        "rerank",
        "image",
        "video",
        "tts",
        "asr",
        "audio",
    )
    return not any(token in lowered for token in blocked)


def normalize_version_name(version_name: str) -> str:
    """Normalize Baidu version names while preserving official casing."""
    cleaned = re.sub(r"\s+", " ", version_name).strip()
    aliases = {
        "moonshot-kimi-k2-instruct": "Kimi-K2-Instruct",
        "kimi-k2-instruct": "Kimi-K2-Instruct",
    }
    return aliases.get(cleaned.lower(), cleaned)


def parse_price(text: str) -> Decimal | None:
    """Parse a non-negative Baidu price number."""
    cleaned = text.strip()
    if not cleaned or cleaned in {"-", "触发"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    if not match:
        return None
    try:
        value = Decimal(match.group(1))
    except (InvalidOperation, ValueError):
        return None
    return value if value >= 0 else None


def normalize_to_per_million(price: Decimal, unit: str) -> str:
    """Normalize Baidu price units to CNY per 1M tokens."""
    normalized_unit = unit.lower()
    value = price
    if "千token" in normalized_unit or "千tokens" in normalized_unit:
        value *= Decimal("1000")
    return format_decimal(value)


def format_decimal(value: Decimal) -> str:
    """Format a decimal as a compact price string."""
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def merge_price(
    *,
    models: dict[str, dict[str, Any]],
    version_name: str,
    service: str,
    subitem: str,
    unit: str,
    price: Decimal,
) -> None:
    """Merge one Baidu price row into a model aggregate."""
    normalized_name = normalize_version_name(version_name)
    key = normalized_name.lower()
    model = models.setdefault(
        key,
        {
            "model_id": normalized_name,
            "model_name": normalized_name,
            "aliases": [normalized_name, version_name.strip()],
            "input_price_per_million": None,
            "output_price_per_million": None,
            "cache_hit_price_per_million": None,
            "currency": DEFAULT_CURRENCY,
            "notes": "Extracted from Baidu Qianfan official pricing table.",
            "_meta": {"input_score": -1, "output_score": -1},
        },
    )
    normalized_price = normalize_to_per_million(price, unit)
    subitem_clean = subitem.replace(" ", "")
    service_clean = service.replace(" ", "")
    pricing_context = f"{service_clean} {subitem_clean}".strip()
    subitem_kind = subitem_kind_from_text(subitem_clean, pricing_context)
    score = subitem_score(pricing_context)
    if subitem_clean.startswith("命中缓存"):
        model["cache_hit_price_per_million"] = normalized_price
        return
    if subitem_kind == "input" and should_replace_price(
        current_price=model["input_price_per_million"],
        current_score=model["_meta"]["input_score"],
        candidate_price=normalized_price,
        candidate_score=score,
    ):
        model["input_price_per_million"] = normalized_price
        model["_meta"]["input_score"] = score
    if subitem_kind == "output" and should_replace_price(
        current_price=model["output_price_per_million"],
        current_score=model["_meta"]["output_score"],
        candidate_price=normalized_price,
        candidate_score=score,
    ):
        model["output_price_per_million"] = normalized_price
        model["_meta"]["output_score"] = score
    notes = ["Extracted from Baidu Qianfan official pricing table."]
    if model["cache_hit_price_per_million"] is not None:
        notes.append(
            "cache_hit_input="
            f"{model['cache_hit_price_per_million']} CNY/1M tokens"
        )
    model["notes"] = "; ".join(notes)


def subitem_kind_from_text(subitem: str, pricing_context: str = "") -> str:
    """Return the normalized price role for one Baidu billing item."""
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


def subitem_score(subitem: str) -> int:
    """Return replacement priority for a Baidu billing item."""
    if subitem in {"输入", "输出"}:
        return 100
    range_score = range_upper_bound_score(subitem)
    if range_score is not None:
        return range_score
    return 10


def range_upper_bound_score(subitem: str) -> int | None:
    """Return the largest context range bound mentioned in a row."""
    normalized = subitem.lower()
    values = [int(value) for value in re.findall(r"(\d+)k", normalized)]
    if not values:
        return None
    return max(values)


def should_replace_price(
    *,
    current_price: str | None,
    current_score: int,
    candidate_price: str,
    candidate_score: int,
) -> bool:
    """Return whether a candidate row should replace current model price."""
    if current_price is None:
        return True
    if candidate_price != current_price:
        return Decimal(candidate_price) > Decimal(current_price)
    return candidate_score > current_score
