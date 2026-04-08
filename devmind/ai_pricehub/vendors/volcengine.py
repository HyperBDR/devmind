import json
import re

import requests


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


def sync_vendor_catalog() -> dict:
    html = _fetch_text(PRICING_URL)
    zones = _extract_zones(html)
    models: dict[str, dict] = {}
    for item in _extract_rows(zones=zones, schema=ONLINE_SCHEMA, section_name="online_inference"):
        _upsert_model(models, item)
    for item in _extract_rows(zones=zones, schema=BATCH_SCHEMA, section_name="batch_inference"):
        _upsert_model(models, item)
    priced_models = []
    for item in sorted(models.values(), key=lambda candidate: candidate["model_name"].lower()):
        if item["input_price_per_million"] is None and item["output_price_per_million"] is None:
            continue
        priced_models.append({key: value for key, value in item.items() if not key.startswith("_")})
    return {
        "vendor": {
            "slug": "volcengine",
            "name": "VolcEngine",
            "pricing_url": PRICING_URL,
        },
        "models": priced_models,
        "notes": f"Extracted {len(priced_models)} priced text models from the official VolcEngine pricing document.",
    }


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_zones(html: str) -> dict[str, str]:
    pattern = re.compile(
        r'\\"ops\\":\[(.*?)\],\\"zoneId\\":\\"([^\\"]+)\\",\\"zoneType\\":\\"Z\\"',
        flags=re.DOTALL,
    )
    zones = {}
    for ops, zone_id in pattern.findall(html):
        inserts = re.findall(r'\\"insert\\":\\"(.*?)\\"', ops, flags=re.DOTALL)
        parts = []
        for raw in inserts:
            text = _decode_insert(raw)
            if not text or text == "*":
                continue
            normalized = _normalize_whitespace(text)
            if normalized:
                parts.append(normalized)
        zones[zone_id] = " ".join(parts).strip()
    return zones


def _extract_rows(*, zones: dict[str, str], schema: dict[str, str], section_name: str) -> list[dict]:
    prefixes = sorted(
        {
            zone_id[:-SUFFIX_LEN]
            for zone_id in zones
            if zone_id.endswith(schema["model"]) and zones.get(zone_id, "").strip()
        }
    )
    rows = []
    for prefix in prefixes:
        model_text = zones.get(prefix + schema["model"], "").strip()
        if not model_text:
            continue
        model_name, extra_note = _split_model_name(model_text)
        if not model_name or not _is_text_model(model_name):
            continue
        condition = zones.get(prefix + schema["condition"], "").strip()
        input_price = _parse_price(zones.get(prefix + schema["input"], ""))
        output_price = _parse_price(zones.get(prefix + schema["output"], ""))
        cache_hit_price = _parse_price(zones.get(prefix + schema["cache_hit"], ""))
        notes_parts = [f"VolcEngine official {section_name} pricing row."]
        if condition and condition != "-":
            notes_parts.append(f"condition={condition}")
        if cache_hit_price is not None:
            notes_parts.append(f"cache_hit_input={cache_hit_price}元/百万token")
        if extra_note:
            notes_parts.append(extra_note)
        rows.append(
            {
                "model_name": model_name,
                "aliases": [model_name],
                "family": "text",
                "input_price_per_million": input_price,
                "output_price_per_million": output_price,
                "currency": DEFAULT_CURRENCY,
                "notes": "; ".join(notes_parts),
                "_section_priority": 2 if section_name == "online_inference" else 1,
            }
        )
    return rows


def _decode_insert(raw: str) -> str:
    try:
        value = json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        value = raw.replace("\\u002F", "/")
    return value.replace("\\n", "\n")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_model_name(text: str) -> tuple[str, str | None]:
    cleaned = _normalize_whitespace(text).replace("\\n", " ").strip()
    if not cleaned or cleaned == r"\n":
        return "", None
    match = re.match(r"^([A-Za-z0-9._:+-]+)(?:\s+(.*))?$", cleaned)
    if not match:
        return cleaned, None
    return match.group(1).strip(), match.group(2).strip() if match.group(2) else None


def _is_text_model(model_name: str) -> bool:
    lowered = model_name.lower()
    blocked = ["vision", "image", "video", "embedding", "rerank", "tts", "asr", "audio", "speech"]
    return not any(token in lowered for token in blocked)


def _parse_price(text: str) -> float | None:
    normalized = _normalize_whitespace(text)
    if not normalized or normalized in {"-", "不支持"}:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", normalized)
    return float(match.group(1)) if match else None


def _upsert_model(models: dict[str, dict], item: dict) -> None:
    key = item["model_name"].strip().lower()
    existing = models.get(key)
    if existing is None or _candidate_score(item) > _candidate_score(existing):
        models[key] = item


def _candidate_score(item: dict) -> tuple[int, int, float]:
    priced_fields = int(item["input_price_per_million"] is not None) + int(
        item["output_price_per_million"] is not None
    )
    section_priority = int(item.get("_section_priority", 0))
    total = float(item.get("input_price_per_million") or 0) + float(
        item.get("output_price_per_million") or 0
    )
    return priced_fields, section_priority, total
