import re
from urllib.parse import urljoin

import requests

from ai_pricehub.vendor_pricing_common import build_vendor_metadata, resolve_vendor_url


PRICING_URL = "https://bigmodel.cn/pricing"
DEFAULT_CURRENCY = "CNY"


def sync_vendor_catalog(vendor: dict | None = None) -> dict:
    pricing_url = _resolve_pricing_url(vendor)
    html = _fetch_text(pricing_url)
    app_js_url = _extract_app_js_url(pricing_url, html)
    bundle = _fetch_text(app_js_url)
    models = _extract_models_from_bundle(bundle)
    priced_models = [
        item
        for item in models
        if item["family"] == "text"
        and (item["input_price_per_million"] is not None or item["output_price_per_million"] is not None)
    ]
    return {
        "vendor": build_vendor_metadata(
            vendor=vendor,
            slug="zhipu",
            name="Zhipu AI",
            pricing_url=pricing_url,
            default_method="bundle",
            bundle_url=app_js_url,
        ),
        "models": priced_models,
        "notes": f"Extracted {len(priced_models)} priced models from app bundle.",
    }


def _resolve_pricing_url(vendor: dict | None) -> str:
    return resolve_vendor_url(vendor, default_url=PRICING_URL)


def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_app_js_url(page_url: str, html: str) -> str:
    match = re.search(r'<script[^>]+src="([^"]*?/js/app\.[^"]+?\.js)"', html, flags=re.IGNORECASE)
    if not match:
        raise ValueError("Could not find app.*.js bundle from pricing page HTML.")
    return urljoin(page_url, match.group(1))


def _extract_models_from_bundle(bundle: str) -> list[dict]:
    models: dict[str, dict] = {}
    for item in _extract_modern_flagship_rows(bundle):
        _upsert_model(models, item)
    for item in _extract_legacy_public_rows(bundle):
        _upsert_model(models, item)
    return sorted(models.values(), key=lambda item: item["model_name"].lower())


def _extract_modern_flagship_rows(bundle: str) -> list[dict]:
    results = []
    current_name = ""
    pattern = re.compile(
        r'\{name:"([^"]*)".*?upDownText:\[(.*?)\],inPrice:\["([^"]+)"\],outPrice:\["([^"]+)"\].*?decode:"([^"]*)"',
        flags=re.DOTALL,
    )
    for match in pattern.finditer(bundle):
        name = match.group(1).strip() or current_name
        if not name:
            continue
        current_name = name
        input_price = _parse_price_value(match.group(3), assume_per_million=True)
        output_price = _parse_price_value(match.group(4), assume_per_million=True)
        if input_price is None and output_price is None:
            continue
        results.append(
            {
                "model_name": name,
                "aliases": [name],
                "family": _derive_family_from_name(name),
                "input_price_per_million": input_price,
                "output_price_per_million": output_price,
                "currency": DEFAULT_CURRENCY,
                "notes": f"Extracted from pricing page app bundle row with range {match.group(2).strip()}.",
            }
        )
    return results


def _extract_legacy_public_rows(bundle: str) -> list[dict]:
    results = []
    pattern = re.compile(
        r'\{(?:rowspan:\d+,)?label:"([^"]+)".*?costPrice:"([^"]+)".*?unit:"([^"]+tokens?)"(?:,privatePrice:"([^"]*)")?',
        flags=re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(bundle):
        name = match.group(1).strip()
        unit = match.group(3).strip()
        if not _is_public_token_unit(unit):
            continue
        shared_price = _parse_price_value(match.group(2), unit=unit)
        if shared_price is None:
            continue
        results.append(
            {
                "model_name": name,
                "aliases": [name],
                "family": _derive_family_from_name(name),
                "input_price_per_million": shared_price,
                "output_price_per_million": shared_price,
                "currency": DEFAULT_CURRENCY,
                "notes": f"Shared token price extracted from pricing page app bundle with unit {unit}.",
            }
        )
    return results


def _upsert_model(models: dict[str, dict], item: dict) -> None:
    key = item["model_name"].strip().lower()
    existing = models.get(key)
    if existing is None or _pricing_score(item) > _pricing_score(existing):
        models[key] = item


def _pricing_score(item: dict) -> tuple[int, float]:
    priced_fields = int(item["input_price_per_million"] is not None) + int(item["output_price_per_million"] is not None)
    total = float(item["input_price_per_million"] or 0) + float(item["output_price_per_million"] or 0)
    return priced_fields, total


def _parse_price_value(value: str, unit: str | None = None, assume_per_million: bool = False) -> float | None:
    text = value.strip()
    if not text or text in {"-", "/", "Not Supported"}:
        return None
    if text.lower() == "free":
        return 0.0
    numeric = re.search(r"([0-9]+(?:\.[0-9]+)?)", text.replace(",", ""))
    if not numeric:
        return None
    amount = float(numeric.group(1))
    if assume_per_million:
        return amount
    normalized_unit = (unit or "").strip().lower()
    if "1m" in normalized_unit or "1 m" in normalized_unit:
        return amount
    if "1k" in normalized_unit or "1 k" in normalized_unit:
        return amount * 1000
    return amount


def _is_public_token_unit(unit: str) -> bool:
    normalized = unit.strip().lower()
    if "token" not in normalized:
        return False
    if any(token in normalized for token in ["gpu", "day", "year", "time"]):
        return False
    return "1k" in normalized or "1m" in normalized


def _derive_family_from_name(name: str) -> str | None:
    lowered = name.lower()
    if lowered.startswith("glm"):
        return "text"
    if lowered.startswith("embedding"):
        return "embedding"
    if lowered.startswith("cogview"):
        return "image-generation"
    if lowered.startswith("cogvideo"):
        return "video-generation"
    if lowered.startswith("rerank"):
        return "rerank"
    return None
