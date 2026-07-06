from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
)


PRICING_URL = (
    "https://platform.minimaxi.com/docs/guides/pricing-paygo"
)
DEFAULT_CURRENCY = "CNY"


class MiniMaxPriceCatalogCollector:
    """Collect MiniMax official prices into standard catalog JSON."""

    provider_code = "minimax"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return MiniMax official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = str(vendor.get("source_url") or PRICING_URL).strip()
        page_html = str(vendor.get("raw_html") or "")
        if not page_html and vendor.get("verify_source") is False:
            return build_catalog(
                vendor=vendor,
                source_url=source_url,
                models=[],
            )
        if not page_html:
            page_html = fetch_text(source_url)

        models = extract_models(page_html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        return build_catalog(
            vendor=vendor,
            source_url=source_url,
            models=models,
        )


def build_catalog(
    *,
    vendor: dict[str, Any],
    source_url: str,
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the standard MiniMax price catalog payload."""
    provider_name = str(vendor.get("provider_name") or "MiniMax").strip()
    currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
    return build_text_token_standard_catalog(
        provider_code="minimax",
        provider_name=provider_name,
        currency=currency or DEFAULT_CURRENCY,
        source_url=source_url,
        models=models,
        notes=(
            "Extracted MiniMax text model prices from the official pricing "
            "page when explicit per-model token price rows are available."
        ),
        raw_payload={
            "provider_code": "minimax",
            "collector": "llm_ops.price_collectors.minimax",
            "source_url": source_url,
            "model_codes": list(vendor.get("model_codes") or []),
            "raw_html_supplied": bool(vendor.get("raw_html")),
            "parsed_models": len(models),
        },
    )


def fetch_text(url: str) -> str:
    """Fetch one MiniMax pricing document as UTF-8 text."""
    response = requests.get(
        url,
        headers={
            "Accept": "text/html,application/json,text/plain,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    if str(response.encoding).lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = "utf-8"
    return response.text or ""


def extract_models(content: str) -> list[dict[str, Any]]:
    """Extract MiniMax text-token price rows from JSON and HTML tables."""
    models: dict[str, dict[str, Any]] = {}
    for document in extract_json_documents(content):
        for item in extract_models_from_json(document):
            upsert_model(models, item)
    for item in extract_models_from_tables(content):
        upsert_model(models, item)
    return [
        item
        for item in sorted(
            models.values(),
            key=lambda candidate: candidate["model_id"].lower(),
        )
    ]


def extract_json_documents(content: str) -> list[Any]:
    """Return embedded JSON payloads that may contain API pricing data."""
    documents = []
    raw_text = unescape(str(content or ""))
    append_json_document(documents, raw_text)

    pattern = re.compile(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        flags=re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(raw_text):
        append_json_document(documents, match.group(1))

    for fragment in extract_balanced_values(raw_text, "apiPricing"):
        append_json_document(documents, fragment)
    return documents


def append_json_document(documents: list[Any], raw_value: str) -> None:
    """Append one JSON document if it can be decoded."""
    text = str(raw_value or "").strip()
    if not text:
        return
    try:
        documents.append(json.loads(text))
    except json.JSONDecodeError:
        return


def extract_balanced_values(text: str, key: str) -> list[str]:
    """Extract balanced JSON object or array values after one key."""
    fragments = []
    pattern = re.compile(rf'["\']?{re.escape(key)}["\']?\s*:')
    for match in pattern.finditer(text):
        start = next_json_value_start(text, match.end())
        if start < 0:
            continue
        fragment = balanced_fragment(text, start)
        if fragment:
            fragments.append(fragment)
    return fragments


def next_json_value_start(text: str, start: int) -> int:
    """Return the next JSON object or array start position."""
    positions = [
        position
        for position in (text.find("{", start), text.find("[", start))
        if position >= 0
    ]
    return min(positions) if positions else -1


def balanced_fragment(text: str, start: int) -> str:
    """Return a balanced object or array fragment from text."""
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def extract_models_from_json(document: Any) -> list[dict[str, Any]]:
    """Recursively extract explicit model price rows from JSON payloads."""
    models = []
    if isinstance(document, dict):
        row = model_from_mapping(document)
        if row:
            models.append(row)
        for value in document.values():
            models.extend(extract_models_from_json(value))
    elif isinstance(document, list):
        for item in document:
            models.extend(extract_models_from_json(item))
    return models


def model_from_mapping(item: dict[str, Any]) -> dict[str, Any]:
    """Build one model from a structured row with explicit token prices."""
    model_name = value_for_keys(item, MODEL_KEYS)
    input_price = value_for_keys(item, INPUT_PRICE_KEYS)
    output_price = value_for_keys(item, OUTPUT_PRICE_KEYS)
    if not model_name or input_price is None or output_price is None:
        return {}
    input_value = parse_price(input_price)
    output_value = parse_price(output_price)
    if input_value is None or output_value is None:
        return {}
    model_id = model_id_from_name(model_name)
    if not model_id:
        return {}
    return {
        "model_id": model_id,
        "model_name": model_id,
        "display_name": display_name_from_cell(model_name),
        "aliases": aliases_for_model(model_id, model_name),
        "input_price_per_million": input_value,
        "output_price_per_million": output_value,
        "currency": DEFAULT_CURRENCY,
        "notes": "Extracted from MiniMax official API pricing data.",
    }


MODEL_KEYS = {
    "model",
    "modelid",
    "modelname",
    "modelversion",
    "模型",
    "模型名称",
}
INPUT_PRICE_KEYS = {
    "input",
    "inputprice",
    "inputtokenprice",
    "promptprice",
    "prompttokenprice",
    "输入",
    "输入价格",
    "输入单价",
}
OUTPUT_PRICE_KEYS = {
    "output",
    "outputprice",
    "outputtokenprice",
    "completionprice",
    "completiontokenprice",
    "输出",
    "输出价格",
    "输出单价",
}


def value_for_keys(item: dict[str, Any], accepted_keys: set[str]) -> Any:
    """Return the first value matching a normalized key name."""
    for key, value in item.items():
        normalized_key = normalize_key(key)
        if normalized_key in accepted_keys:
            return value
    return None


def normalize_key(value: Any) -> str:
    """Normalize a source key for pricing field matching."""
    text = str(value or "").strip().lower()
    return re.sub(r"[\s_\-/.()]+", "", text)


def extract_models_from_tables(content: str) -> list[dict[str, Any]]:
    """Extract model rows from plain HTML pricing tables."""
    models = []
    for table_html in re.findall(
        r"<table\b.*?</table>",
        str(content or ""),
        flags=re.DOTALL | re.IGNORECASE,
    ):
        models.extend(models_from_table(table_html))
    return models


def models_from_table(table_html: str) -> list[dict[str, Any]]:
    """Build MiniMax model rows from one HTML table."""
    rows = parse_table_rows(table_html)
    if len(rows) < 2:
        return []
    headers = [normalize_header(value) for value in rows[0]]
    model_index = first_header_index(
        headers,
        {"model", "模型", "模型名称"},
    )
    input_index = first_header_index(
        headers,
        {"input", "输入", "输入价格"},
    )
    output_index = first_header_index(
        headers,
        {"output", "输出", "输出价格"},
    )
    if model_index < 0 or input_index < 0 or output_index < 0:
        return []

    models = []
    for row in rows[1:]:
        if max(model_index, input_index, output_index) >= len(row):
            continue
        item = model_from_mapping(
            {
                "model": row[model_index],
                "input": row[input_index],
                "output": row[output_index],
            }
        )
        if item:
            models.append(item)
    return models


def parse_table_rows(table_html: str) -> list[list[str]]:
    """Parse simple HTML table rows into normalized cell text."""
    rows = []
    for row_html in re.findall(
        r"<tr\b.*?</tr>",
        table_html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        cells = []
        for cell_html in re.findall(
            r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            cells.append(clean_cell_text(cell_html))
        if cells:
            rows.append(cells)
    return rows


def clean_cell_text(inner_html: str) -> str:
    """Convert one HTML cell body into normalized text."""
    text = re.sub(r"<br\s*/?>", "\n", inner_html, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|blockquote|div)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_header(value: str) -> str:
    """Normalize a table header for field matching."""
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if "model" in text:
        return "model"
    if "模型" in text:
        return "模型"
    if "input" in text or "prompt" in text:
        return "input"
    if "输入" in text:
        return "输入"
    if "output" in text or "completion" in text:
        return "output"
    if "输出" in text:
        return "输出"
    return text


def first_header_index(headers: list[str], candidates: set[str]) -> int:
    """Return the first matching header index, or -1."""
    for index, header in enumerate(headers):
        if header in candidates:
            return index
    return -1


def parse_price(value: Any) -> str | None:
    """Parse a non-negative CNY token price into CNY per 1M tokens."""
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"-", "n/a", "N/A"}:
        return None
    match = re.search(r"(?:¥|￥|CNY|RMB)?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    if is_per_thousand_tokens(text):
        amount *= Decimal("1000")
    return format_decimal(amount)


def is_per_thousand_tokens(text: str) -> bool:
    """Return whether a price is published per thousand tokens."""
    normalized = re.sub(r"\s+", "", text.lower())
    if "百万" in normalized or "1m" in normalized:
        return False
    return "千tokens" in normalized or "千token" in normalized


def format_decimal(value: Decimal) -> str:
    """Format a decimal as a compact price string."""
    formatted = format(value.normalize(), "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def model_id_from_name(value: Any) -> str:
    """Normalize a MiniMax model display name into a model ID."""
    text = display_name_from_cell(value)
    if not text:
        return ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"（[^）]*）", " ", text)
    text = re.sub(r"[^A-Za-z0-9.]+", "-", text)
    return text.strip("-").lower()


def display_name_from_cell(value: Any) -> str:
    """Return a readable model name from a table or JSON value."""
    text = re.sub(r"\s+", " ", str(value or "").replace("\n", " "))
    return text.strip()


def aliases_for_model(model_id: str, display_name: Any) -> list[str]:
    """Return matching aliases for one MiniMax model row."""
    aliases = [model_id]
    original = display_name_from_cell(display_name)
    if original and original not in aliases:
        aliases.append(original)
    return aliases


def upsert_model(
    models: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    """Merge one parsed MiniMax model into the extracted catalog."""
    model_id = item["model_id"]
    if model_id not in models:
        models[model_id] = item
