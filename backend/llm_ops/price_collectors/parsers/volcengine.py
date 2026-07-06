from __future__ import annotations

import json
import re
from typing import Any

import requests

from .common import (
    build_text_token_standard_catalog,
    filter_models_by_codes,
    sync_official_vendor_catalog,
)


PRICING_URL = "https://www.volcengine.com/docs/82379/1544106?lang=zh"
DEFAULT_CURRENCY = "CNY"
SUFFIX_LEN = 32

ONLINE_SCHEMA = {
    "model": "nj2n42rlpl8e7b6tvpmvqhysnzfp89bh",
    "input": "s303uu1c1g40de7oaoizn05md89iimb6",
    "output": "5wt3pecycob8so1pho26k692zw2cgbsm",
    "cache_hit": "cvklbb5m01p5jfrmdhooit6bknkyawsj",
    "condition": "gagtwd6h2ui45oj1di8jtwno5ytnfdt6",
}

BATCH_SCHEMA = {
    "model": "sd9qqqvyjh64sfk1ym6h608eym82d47r",
    "input": "g1jev13gq4vtdf1u98drambg5e4iydrp",
    "output": "r0s2ipdcp1is8youke6te708kops5in5",
    "cache_hit": "59955fwlp0lm8jma3qh1nqtzurbplpg8",
    "condition": "8tq8h7zdnkenawut121k9pl3482469oc",
}


class VolcEnginePriceCatalogCollector:
    """Collect VolcEngine official prices into the standard catalog JSON."""

    provider_code = "volcengine"

    def collect_catalog(
        self,
        vendor_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return VolcEngine official prices as standard catalog JSON."""
        vendor = dict(vendor_config or {})
        source_url = resolve_pricing_url(vendor)
        html = str(vendor.get("raw_html") or "")
        if not html and vendor.get("verify_source") is False:
            return sync_official_vendor_catalog("volcengine", vendor)
        if not html:
            html = fetch_text(source_url)

        models = extract_models(html)
        models = filter_models_by_codes(models, vendor.get("model_codes"))
        if not models:
            vendor["fallback_used"] = True
            vendor["fallback_reason"] = "official_page_parse_empty"
            return sync_official_vendor_catalog("volcengine", vendor)

        provider_name = str(
            vendor.get("provider_name") or "火山方舟"
        ).strip()
        currency = str(vendor.get("currency") or DEFAULT_CURRENCY).strip()
        return build_text_token_standard_catalog(
            provider_code="volcengine",
            provider_name=provider_name,
            currency=currency or DEFAULT_CURRENCY,
            source_url=source_url,
            models=models,
            notes=(
                "Extracted VolcEngine text model prices from the official "
                "pricing document."
            ),
            raw_payload={
                "provider_code": "volcengine",
                "collector": "llm_ops.price_collectors.volcengine",
                "source_url": source_url,
                "model_codes": list(vendor.get("model_codes") or []),
                "raw_html_supplied": bool(vendor.get("raw_html")),
            },
        )


def resolve_pricing_url(vendor: dict[str, Any]) -> str:
    """Return the configured VolcEngine pricing page URL."""
    acquisition = dict(vendor.get("acquisition") or {})
    return str(
        vendor.get("source_url")
        or acquisition.get("page_url")
        or vendor.get("pricing_url")
        or PRICING_URL
    ).strip()


def fetch_text(url: str) -> str:
    """Fetch one VolcEngine pricing document as text."""
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
    return response.text or ""


def extract_models(html: str) -> list[dict[str, Any]]:
    """Extract VolcEngine text model price rows from document zones."""
    zones = extract_zones(html)
    models: dict[str, dict[str, Any]] = {}
    for item in extract_rows(
        zones=zones,
        schema=ONLINE_SCHEMA,
        section_name="online_inference",
    ):
        upsert_model(models, item)
    for item in extract_rows(
        zones=zones,
        schema=BATCH_SCHEMA,
        section_name="batch_inference",
    ):
        upsert_model(models, item)

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


def extract_zones(html: str) -> dict[str, str]:
    """Extract VolcEngine document zone text keyed by zone ID."""
    pattern = re.compile(
        r'\\"ops\\":\[(.*?)\],\\"zoneId\\":\\"([^\\"]+)\\",'
        r'\\"zoneType\\":\\"Z\\"',
        flags=re.DOTALL,
    )
    zones = {}
    for ops, zone_id in pattern.findall(html):
        inserts = re.findall(r'\\"insert\\":\\"(.*?)\\"', ops)
        parts = []
        for raw in inserts:
            text = decode_insert(raw)
            if not text or text == "*":
                continue
            normalized = normalize_whitespace(text)
            if normalized:
                parts.append(normalized)
        zones[zone_id] = " ".join(parts).strip()
    return zones


def extract_rows(
    *,
    zones: dict[str, str],
    schema: dict[str, str],
    section_name: str,
) -> list[dict[str, Any]]:
    """Extract price row dictionaries for one VolcEngine table schema."""
    prefixes = sorted(
        {
            zone_id[:-SUFFIX_LEN]
            for zone_id in zones
            if zone_id.endswith(schema["model"])
            and zones.get(zone_id, "").strip()
        }
    )
    rows = []
    for prefix in prefixes:
        model_text = zones.get(prefix + schema["model"], "").strip()
        if not model_text:
            continue
        model_name, extra_note = split_model_name(model_text)
        if not model_name or not is_text_model(model_name):
            continue
        condition = zones.get(prefix + schema["condition"], "").strip()
        input_price = parse_price(zones.get(prefix + schema["input"], ""))
        output_price = parse_price(zones.get(prefix + schema["output"], ""))
        cache_hit_price = parse_price(
            zones.get(prefix + schema["cache_hit"], "")
        )
        rows.append(
            build_row(
                model_name=model_name,
                input_price=input_price,
                output_price=output_price,
                cache_hit_price=cache_hit_price,
                condition=condition,
                extra_note=extra_note,
                section_name=section_name,
            )
        )
    return rows


def build_row(
    *,
    model_name: str,
    input_price: str | None,
    output_price: str | None,
    cache_hit_price: str | None,
    condition: str,
    extra_note: str | None,
    section_name: str,
) -> dict[str, Any]:
    """Build one parsed VolcEngine model price row."""
    notes_parts = [f"VolcEngine official {section_name} pricing row."]
    if condition and condition != "-":
        notes_parts.append(f"condition={condition}")
    if cache_hit_price is not None:
        notes_parts.append(f"cache_hit_input={cache_hit_price} CNY/1M tokens")
    if extra_note:
        notes_parts.append(extra_note)
    return {
        "model_id": model_name,
        "model_name": model_name,
        "aliases": [model_name],
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
        "cache_hit_price_per_million": cache_hit_price,
        "currency": DEFAULT_CURRENCY,
        "notes": "; ".join(notes_parts),
        "_section_priority": 2 if section_name == "online_inference" else 1,
    }


def decode_insert(raw: str) -> str:
    """Decode one escaped Quill insert value from VolcEngine page data."""
    try:
        value = json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        value = raw.replace("\\u002F", "/")
    return value.replace("\\n", "\n")


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace in source text."""
    return re.sub(r"\s+", " ", text).strip()


def split_model_name(text: str) -> tuple[str, str | None]:
    """Split the model ID from an optional note."""
    cleaned = normalize_whitespace(text).replace("\\n", " ").strip()
    if not cleaned or cleaned == r"\n":
        return "", None
    match = re.match(r"^([A-Za-z0-9._:+-]+)(?:\s+(.*))?$", cleaned)
    if not match:
        return cleaned, None
    return (
        match.group(1).strip(),
        match.group(2).strip() if match.group(2) else None,
    )


def is_text_model(model_name: str) -> bool:
    """Return whether a VolcEngine model row is a text model."""
    lowered = model_name.lower()
    blocked = (
        "vision",
        "image",
        "video",
        "embedding",
        "rerank",
        "tts",
        "asr",
        "audio",
        "speech",
    )
    return not any(token in lowered for token in blocked)


def parse_price(text: str) -> str | None:
    """Parse one non-negative VolcEngine CNY price."""
    normalized = normalize_whitespace(text)
    if not normalized or normalized in {"-", "不支持"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", normalized)
    return match.group(1) if match else None


def upsert_model(
    models: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    """Keep the preferred row for one VolcEngine model."""
    key = item["model_name"].strip().lower()
    existing = models.get(key)
    if existing is None or candidate_score(item) > candidate_score(existing):
        models[key] = item


def candidate_score(item: dict[str, Any]) -> tuple[int, int, float]:
    """Rank candidate rows for the same model ID."""
    priced_fields = int(item["input_price_per_million"] is not None)
    priced_fields += int(item["output_price_per_million"] is not None)
    section_priority = int(item.get("_section_priority", 0))
    total = float(item.get("input_price_per_million") or 0)
    total += float(item.get("output_price_per_million") or 0)
    return priced_fields, section_priority, total
