from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import html
import json
import re
from typing import Any

import requests

from .yunce import (
    CollectedModelPricing,
    CollectedPricingCatalog,
    NormalizedPriceRow,
)


MODELS_DEV_API_URL = "https://models.dev/api.json"
MODELS_DEV_PROVIDER_KEYS = {
    "aliyun": ("alibaba-cn", "alibaba"),
    "anthropic": ("anthropic",),
    "deepseek": ("deepseek",),
    "google": ("google",),
    "openai": ("openai",),
}


@dataclass(frozen=True)
class OfficialPriceSpec:
    """One provider-published model price."""

    model_id: str
    aliases: tuple[str, ...]
    input_per_million: Decimal
    output_per_million: Decimal
    display_name: str = ""
    source_model_type: str = "Text"
    image_output_per_image: Decimal | None = None
    video_output_prices: tuple[tuple[str, Decimal], ...] = ()
    source_note: str = ""

    def matches(self, model_code: str) -> bool:
        """Return whether this spec maps to a configured model code."""
        normalized_code = normalize_model_code(model_code)
        for alias in self.aliases:
            normalized_alias = normalize_model_code(alias)
            if normalized_code == normalized_alias:
                return True
            suffix = normalized_code.removeprefix(f"{normalized_alias}-")
            if suffix != normalized_code and re.fullmatch(r"\d{8}", suffix):
                return True
        return False


@dataclass(frozen=True)
class OfficialProviderConfig:
    """Official pricing source configuration for one provider."""

    provider_code: str
    provider_label: str
    source_url: str
    currency: str
    models: tuple[OfficialPriceSpec, ...]


OFFICIAL_PROVIDER_CONFIGS = {
    "openai": OfficialProviderConfig(
        provider_code="openai",
        provider_label="OpenAI",
        source_url="https://openai.com/api/pricing/",
        currency="USD",
        models=(
            OfficialPriceSpec(
                model_id="gpt-5.5",
                aliases=("gpt-5.5",),
                input_per_million=Decimal("5"),
                output_per_million=Decimal("30"),
                display_name="GPT-5.5",
            ),
            OfficialPriceSpec(
                model_id="gpt-5.4",
                aliases=("gpt-5.4",),
                input_per_million=Decimal("2.50"),
                output_per_million=Decimal("15"),
                display_name="GPT-5.4",
            ),
            OfficialPriceSpec(
                model_id="gpt-5.4-mini",
                aliases=("gpt-5.4-mini",),
                input_per_million=Decimal("0.75"),
                output_per_million=Decimal("4.50"),
                display_name="GPT-5.4 mini",
            ),
            OfficialPriceSpec(
                model_id="gpt-5",
                aliases=("gpt-5", "gpt-5-chat", "gpt-5-codex"),
                input_per_million=Decimal("1.25"),
                output_per_million=Decimal("10"),
                display_name="GPT-5",
            ),
            OfficialPriceSpec(
                model_id="gpt-5-mini",
                aliases=("gpt-5-mini",),
                input_per_million=Decimal("0.25"),
                output_per_million=Decimal("2"),
                display_name="GPT-5 mini",
            ),
            OfficialPriceSpec(
                model_id="gpt-5-nano",
                aliases=("gpt-5-nano",),
                input_per_million=Decimal("0.05"),
                output_per_million=Decimal("0.40"),
                display_name="GPT-5 nano",
            ),
            OfficialPriceSpec(
                model_id="gpt-4.1",
                aliases=("gpt-4.1",),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("8"),
                display_name="GPT-4.1",
            ),
            OfficialPriceSpec(
                model_id="gpt-4.1-mini",
                aliases=("gpt-4.1-mini",),
                input_per_million=Decimal("0.40"),
                output_per_million=Decimal("1.60"),
                display_name="GPT-4.1 mini",
            ),
            OfficialPriceSpec(
                model_id="gpt-4.1-nano",
                aliases=("gpt-4.1-nano",),
                input_per_million=Decimal("0.10"),
                output_per_million=Decimal("0.40"),
                display_name="GPT-4.1 nano",
            ),
            OfficialPriceSpec(
                model_id="gpt-4o",
                aliases=("gpt-4o",),
                input_per_million=Decimal("2.50"),
                output_per_million=Decimal("10"),
                display_name="GPT-4o",
            ),
            OfficialPriceSpec(
                model_id="gpt-4o-mini",
                aliases=("gpt-4o-mini",),
                input_per_million=Decimal("0.15"),
                output_per_million=Decimal("0.60"),
                display_name="GPT-4o mini",
            ),
            OfficialPriceSpec(
                model_id="o1",
                aliases=("o1",),
                input_per_million=Decimal("15"),
                output_per_million=Decimal("60"),
                display_name="o1",
            ),
            OfficialPriceSpec(
                model_id="o3",
                aliases=("o3",),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("8"),
                display_name="o3",
            ),
            OfficialPriceSpec(
                model_id="o3-mini",
                aliases=("o3-mini", "o4-mini"),
                input_per_million=Decimal("1.10"),
                output_per_million=Decimal("4.40"),
                display_name="o3 mini / o4-mini",
            ),
            OfficialPriceSpec(
                model_id="gpt-image-2",
                aliases=("gpt-image-2",),
                input_per_million=Decimal("5"),
                output_per_million=Decimal("30"),
                display_name="GPT-Image-2",
                source_note="Text input/output token price",
            ),
            OfficialPriceSpec(
                model_id="text-embedding-3-small",
                aliases=("text-embedding-3-small",),
                input_per_million=Decimal("0.02"),
                output_per_million=Decimal("0"),
                display_name="Text Embedding 3 Small",
            ),
            OfficialPriceSpec(
                model_id="text-embedding-3-large",
                aliases=("text-embedding-3-large",),
                input_per_million=Decimal("0.13"),
                output_per_million=Decimal("0"),
                display_name="Text Embedding 3 Large",
            ),
            OfficialPriceSpec(
                model_id="text-embedding-ada-002",
                aliases=("text-embedding-ada-002",),
                input_per_million=Decimal("0.10"),
                output_per_million=Decimal("0"),
                display_name="Text Embedding Ada 002",
            ),
        ),
    ),
    "anthropic": OfficialProviderConfig(
        provider_code="anthropic",
        provider_label="Anthropic",
        source_url="https://docs.anthropic.com/en/docs/about-claude/pricing",
        currency="USD",
        models=(
            OfficialPriceSpec(
                model_id="claude-opus-4-6",
                aliases=("claude-opus-4-6",),
                input_per_million=Decimal("5"),
                output_per_million=Decimal("25"),
                display_name="Claude Opus 4.6",
            ),
            OfficialPriceSpec(
                model_id="claude-sonnet-4-6",
                aliases=("claude-sonnet-4-6",),
                input_per_million=Decimal("3"),
                output_per_million=Decimal("15"),
                display_name="Claude Sonnet 4.6",
            ),
            OfficialPriceSpec(
                model_id="claude-opus-4-5",
                aliases=("claude-opus-4-5",),
                input_per_million=Decimal("5"),
                output_per_million=Decimal("25"),
                display_name="Claude Opus 4.5",
            ),
            OfficialPriceSpec(
                model_id="claude-haiku-4-5",
                aliases=("claude-haiku-4-5",),
                input_per_million=Decimal("1"),
                output_per_million=Decimal("5"),
                display_name="Claude Haiku 4.5",
            ),
            OfficialPriceSpec(
                model_id="claude-sonnet-4-5",
                aliases=("claude-sonnet-4-5",),
                input_per_million=Decimal("3"),
                output_per_million=Decimal("15"),
                display_name="Claude Sonnet 4.5",
            ),
            OfficialPriceSpec(
                model_id="claude-sonnet-4",
                aliases=("claude-sonnet-4",),
                input_per_million=Decimal("3"),
                output_per_million=Decimal("15"),
                display_name="Claude Sonnet 4",
            ),
            OfficialPriceSpec(
                model_id="claude-opus-4-1",
                aliases=("claude-opus-4-1",),
                input_per_million=Decimal("15"),
                output_per_million=Decimal("75"),
                display_name="Claude Opus 4.1",
            ),
            OfficialPriceSpec(
                model_id="claude-opus-4",
                aliases=("claude-opus-4",),
                input_per_million=Decimal("15"),
                output_per_million=Decimal("75"),
                display_name="Claude Opus 4",
            ),
        ),
    ),
    "google": OfficialProviderConfig(
        provider_code="google",
        provider_label="Google",
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
        currency="USD",
        models=(
            OfficialPriceSpec(
                model_id="gemini-3-pro-preview",
                aliases=("gemini-3-pro-preview",),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("12"),
                display_name="Gemini 3 Pro Preview",
                source_note="Standard tier, prompts <= 200k tokens",
            ),
            OfficialPriceSpec(
                model_id="gemini-3-pro-image-preview",
                aliases=("gemini-3-pro-image-preview",),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("12"),
                display_name="Gemini 3 Pro Image Preview",
                source_note="Text input/output price",
            ),
            OfficialPriceSpec(
                model_id="gemini-3-flash-preview",
                aliases=("gemini-3-flash-preview",),
                input_per_million=Decimal("0.50"),
                output_per_million=Decimal("3"),
                display_name="Gemini 3 Flash Preview",
                source_note="Standard tier text/image/video input price",
            ),
            OfficialPriceSpec(
                model_id="gemini-3.1-pro-preview",
                aliases=("gemini-3.1-pro-preview",),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("12"),
                display_name="Gemini 3.1 Pro Preview",
                source_note="Standard tier, prompts <= 200k tokens",
            ),
            OfficialPriceSpec(
                model_id="gemini-3.1-flash-lite",
                aliases=(
                    "gemini-3.1-flash-lite",
                    "gemini-3.1-flash-lite-preview",
                ),
                input_per_million=Decimal("0.25"),
                output_per_million=Decimal("1.50"),
                display_name="Gemini 3.1 Flash-Lite",
                source_note="Standard tier text/image/video input price",
            ),
            OfficialPriceSpec(
                model_id="gemini-3.1-flash-image",
                aliases=(
                    "gemini-3.1-flash-image",
                    "gemini-3.1-flash-image-preview",
                ),
                input_per_million=Decimal("0.50"),
                output_per_million=Decimal("3"),
                display_name="Gemini 3.1 Flash Image",
                source_note="Standard tier text output price",
            ),
            OfficialPriceSpec(
                model_id="gemini-3.5-flash",
                aliases=("gemini-3.5-flash",),
                input_per_million=Decimal("1.50"),
                output_per_million=Decimal("9"),
                display_name="Gemini 3.5 Flash",
            ),
            OfficialPriceSpec(
                model_id="gemini-2.5-pro",
                aliases=("gemini-2.5-pro",),
                input_per_million=Decimal("1.25"),
                output_per_million=Decimal("10"),
                display_name="Gemini 2.5 Pro",
                source_note="<= 200k token tier",
            ),
            OfficialPriceSpec(
                model_id="gemini-2.5-flash",
                aliases=("gemini-2.5-flash",),
                input_per_million=Decimal("0.30"),
                output_per_million=Decimal("2.50"),
                display_name="Gemini 2.5 Flash",
            ),
            OfficialPriceSpec(
                model_id="gemini-2.5-flash-lite",
                aliases=("gemini-2.5-flash-lite",),
                input_per_million=Decimal("0.10"),
                output_per_million=Decimal("0.40"),
                display_name="Gemini 2.5 Flash-Lite",
            ),
        ),
    ),
    "aliyun": OfficialProviderConfig(
        provider_code="aliyun",
        provider_label="阿里云百炼",
        source_url="https://help.aliyun.com/zh/model-studio/models",
        currency="CNY",
        models=(
            OfficialPriceSpec(
                model_id="deepseek-r1",
                aliases=("deepseek-r1", "deepseek-r1-0528"),
                input_per_million=Decimal("4"),
                output_per_million=Decimal("16"),
                display_name="DeepSeek R1",
            ),
            OfficialPriceSpec(
                model_id="deepseek-v3",
                aliases=(
                    "deepseek-v3",
                    "deepseek-v3.1",
                    "deepseek-v3.2",
                    "deepseek-v3.2-exp",
                ),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("8"),
                display_name="DeepSeek V3",
            ),
            OfficialPriceSpec(
                model_id="qwq-32b",
                aliases=("qwq-32b",),
                input_per_million=Decimal("0.90"),
                output_per_million=Decimal("3.60"),
                display_name="QwQ 32B",
            ),
            OfficialPriceSpec(
                model_id="qwen-max",
                aliases=("qwen-max",),
                input_per_million=Decimal("2.40"),
                output_per_million=Decimal("9.60"),
                display_name="Qwen Max",
            ),
            OfficialPriceSpec(
                model_id="qwen3-max",
                aliases=("qwen3-max",),
                input_per_million=Decimal("2.40"),
                output_per_million=Decimal("9.60"),
                display_name="Qwen3 Max",
            ),
            OfficialPriceSpec(
                model_id="qwen-plus",
                aliases=("qwen-plus", "qwen3-vl-plus"),
                input_per_million=Decimal("0.80"),
                output_per_million=Decimal("2"),
                display_name="Qwen Plus",
            ),
            OfficialPriceSpec(
                model_id="qwen-turbo",
                aliases=("qwen-turbo",),
                input_per_million=Decimal("0.30"),
                output_per_million=Decimal("0.60"),
                display_name="Qwen Turbo",
            ),
            OfficialPriceSpec(
                model_id="qwen3-235b-a22b",
                aliases=(
                    "qwen3-235b-a22b-instruct-2507",
                    "qwen3-235b-a22b-thinking-2507",
                ),
                input_per_million=Decimal("2"),
                output_per_million=Decimal("8"),
                display_name="Qwen3 235B A22B",
            ),
            OfficialPriceSpec(
                model_id="qwen3-30b-a3b",
                aliases=(
                    "qwen3-30b-a3b",
                    "qwen3-30b-a3b-instruct-2507",
                    "qwen3-30b-a3b-think",
                    "qwen3-30b-a3b-thinking-2507",
                ),
                input_per_million=Decimal("0.75"),
                output_per_million=Decimal("3"),
                display_name="Qwen3 30B A3B",
            ),
            OfficialPriceSpec(
                model_id="text-embedding-v4",
                aliases=("text-embedding-v4",),
                input_per_million=Decimal("0.10"),
                output_per_million=Decimal("0"),
                display_name="Text Embedding V4",
            ),
        ),
    ),
    "aliyun-wanx": OfficialProviderConfig(
        provider_code="aliyun-wanx",
        provider_label="阿里云通义万相",
        source_url="https://help.aliyun.com/zh/model-studio/models",
        currency="CNY",
        models=(
            OfficialPriceSpec(
                model_id="qwen-image",
                aliases=("qwen-image",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Qwen Image",
                source_model_type="Image",
                image_output_per_image=Decimal("0.08"),
            ),
            OfficialPriceSpec(
                model_id="qwen-image-plus",
                aliases=("qwen-image-plus",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Qwen Image Plus",
                source_model_type="Image",
                image_output_per_image=Decimal("0.20"),
            ),
            OfficialPriceSpec(
                model_id="qwen-image-edit",
                aliases=("qwen-image-edit",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Qwen Image Edit",
                source_model_type="Image",
                image_output_per_image=Decimal("0.05"),
            ),
            OfficialPriceSpec(
                model_id="qwen-image-edit-plus",
                aliases=("qwen-image-edit-plus",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Qwen Image Edit Plus",
                source_model_type="Image",
                image_output_per_image=Decimal("0.20"),
            ),
            OfficialPriceSpec(
                model_id="wan2.5-t2v-preview",
                aliases=("wan2.5-t2v-preview",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan 2.5 Text-to-Video Preview",
                source_model_type="Video",
                video_output_prices=(
                    ("480P", Decimal("0.12")),
                    ("720P", Decimal("0.24")),
                    ("1080P", Decimal("0.48")),
                ),
            ),
            OfficialPriceSpec(
                model_id="wan2.5-i2v-preview",
                aliases=("wan2.5-i2v-preview",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan 2.5 Image-to-Video Preview",
                source_model_type="Video",
                video_output_prices=(
                    ("480P", Decimal("0.12")),
                    ("720P", Decimal("0.24")),
                    ("1080P", Decimal("0.48")),
                ),
            ),
            OfficialPriceSpec(
                model_id="wan2.2-t2v-plus",
                aliases=("wan2.2-t2v-plus", "wanx2.1-t2v-plus"),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan Text-to-Video Plus",
                source_model_type="Video",
                video_output_prices=(
                    ("720P", Decimal("0.14")),
                    ("1080P", Decimal("0.28")),
                ),
            ),
            OfficialPriceSpec(
                model_id="wan2.2-i2v-plus",
                aliases=("wan2.2-i2v-plus", "wanx2.1-i2v-plus"),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan Image-to-Video Plus",
                source_model_type="Video",
                video_output_prices=(
                    ("720P", Decimal("0.14")),
                    ("1080P", Decimal("0.28")),
                ),
            ),
            OfficialPriceSpec(
                model_id="wanx2.1-t2v-turbo",
                aliases=("wanx2.1-t2v-turbo",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan Text-to-Video Turbo",
                source_model_type="Video",
                video_output_prices=(("720P", Decimal("0.04")),),
            ),
            OfficialPriceSpec(
                model_id="wanx2.1-i2v-turbo",
                aliases=("wanx2.1-i2v-turbo",),
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                display_name="Wan Image-to-Video Turbo",
                source_model_type="Video",
                video_output_prices=(("720P", Decimal("0.04")),),
            ),
        ),
    ),
    "volcengine": OfficialProviderConfig(
        provider_code="volcengine",
        provider_label="火山方舟",
        source_url="https://www.volcengine.com/docs/82379/1099320",
        currency="CNY",
        models=(
            OfficialPriceSpec(
                model_id="deepseek-r1-250528",
                aliases=("deepseek-r1-250528",),
                input_per_million=Decimal("4"),
                output_per_million=Decimal("16"),
                display_name="DeepSeek R1 250528",
            ),
        ),
    ),
}


def collect_official_pricing_catalog(
    *,
    provider_code: str,
    model_codes: set[str] | None = None,
    source_url: str | None = None,
    verify_source: bool = True,
    timeout: int = 20,
) -> CollectedPricingCatalog:
    """Collect official pricing rows for configured model codes."""
    config = OFFICIAL_PROVIDER_CONFIGS[provider_code]
    resolved_source_url = source_url or config.source_url
    source_payload = {}
    source_config = config
    if verify_source:
        source_payload = fetch_source_payload(resolved_source_url, timeout)
        source_payload["source_url"] = resolved_source_url
        source_config, source_payload = config_with_source_prices(
            config,
            source_payload,
        )

    models = []
    target_codes = sorted(model_codes or [])
    for target_code in target_codes:
        spec = first_matching_spec(source_config, target_code)
        if spec is None:
            continue
        models.append(build_collected_pricing(source_config, spec, target_code))

    if not target_codes:
        for spec in source_config.models:
            models.append(
                build_collected_pricing(source_config, spec, spec.model_id),
            )

    return CollectedPricingCatalog(
        source_url=resolved_source_url,
        total_models=len(models),
        models=[
            attach_source_payload(item, source_payload)
            for item in sorted(models, key=lambda item: item.model_id)
        ],
    )


def fetch_source_payload(source_url: str, timeout: int) -> dict[str, Any]:
    """Fetch an official pricing page for downstream price extraction."""
    response = requests.get(
        source_url,
        headers={
            "Accept": "text/html,application/json,text/plain,*/*",
            "User-Agent": "DevMind-LLMOpsPriceCollector/1.0",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.text or ""
    normalized_text = normalize_source_text(content)
    payload = {
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type", ""),
        "content_length": len(content),
        "text": normalized_text,
    }
    parsed_json = parse_json_content(content)
    if parsed_json is not None:
        payload["json"] = parsed_json
    return payload


def config_with_source_prices(
    config: OfficialProviderConfig,
    source_payload: dict[str, Any],
) -> tuple[OfficialProviderConfig, dict[str, Any]]:
    """Return provider config enriched with prices parsed from source text."""
    models_dev_result = config_with_models_dev_prices(config, source_payload)
    if models_dev_result is not None:
        return models_dev_result

    source_text = source_payload.get("text") or ""
    if not source_text.strip():
        raise ValueError(
            f"{config.provider_label} pricing source returned empty content.",
        )

    parsed_specs = []
    for spec in config.models:
        parsed_spec = parse_spec_from_source_text(config, spec, source_text)
        if parsed_spec is not None:
            parsed_specs.append(parsed_spec)

    enriched_payload = dict(source_payload)
    if not parsed_specs:
        enriched_payload["source_parse_warning"] = (
            "No configured model prices could be extracted from the fetched "
            "source page; built-in provider price specs were used after "
            "source availability was verified."
        )
        return (
            replace_config_source_url(config, enriched_payload),
            enriched_payload,
        )

    parsed_model_ids = {spec.model_id for spec in parsed_specs}
    missing_model_ids = [
        spec.model_id
        for spec in config.models
        if spec.model_id not in parsed_model_ids
    ]
    if missing_model_ids:
        enriched_payload["source_parse_missing_model_ids"] = missing_model_ids

    return OfficialProviderConfig(
        provider_code=config.provider_code,
        provider_label=config.provider_label,
        source_url=source_payload.get("source_url") or config.source_url,
        currency=config.currency,
        models=tuple(parsed_specs),
    ), enriched_payload


def config_with_models_dev_prices(
    config: OfficialProviderConfig,
    source_payload: dict[str, Any],
) -> tuple[OfficialProviderConfig, dict[str, Any]] | None:
    """Return provider config parsed from models.dev's public API JSON."""
    source_json = source_payload.get("json")
    if not isinstance(source_json, dict):
        return None

    provider_key = models_dev_provider_key(config.provider_code, source_json)
    if provider_key is None:
        return None

    provider_payload = source_json.get(provider_key) or {}
    model_payloads = provider_payload.get("models") or {}
    if not isinstance(model_payloads, dict):
        return None

    parsed_specs = []
    skipped_model_ids = []
    for model_payload in model_payloads.values():
        spec = models_dev_price_spec(model_payload)
        if spec is None:
            model_id = (
                model_payload.get("id")
                if isinstance(model_payload, dict)
                else None
            )
            if model_id:
                skipped_model_ids.append(model_id)
            continue
        parsed_specs.append(spec)

    if not parsed_specs:
        return None

    parsed_model_ids = {spec.model_id for spec in parsed_specs}
    missing_model_ids = [
        spec.model_id
        for spec in config.models
        if spec.model_id not in parsed_model_ids
    ]
    enriched_payload = dict(source_payload)
    enriched_payload["models_dev_provider_key"] = provider_key
    enriched_payload["models_dev_provider_name"] = (
        provider_payload.get("name") or config.provider_label
    )
    enriched_payload["models_dev_model_count"] = len(parsed_specs)
    if missing_model_ids:
        enriched_payload["models_dev_missing_model_ids"] = missing_model_ids
    if skipped_model_ids:
        enriched_payload["models_dev_skipped_model_ids"] = skipped_model_ids

    return OfficialProviderConfig(
        provider_code=config.provider_code,
        provider_label=provider_payload.get("name") or config.provider_label,
        source_url=source_payload.get("source_url") or config.source_url,
        currency="USD",
        models=tuple(parsed_specs),
    ), enriched_payload


def models_dev_provider_key(
    provider_code: str,
    source_json: dict[str, Any],
) -> str | None:
    """Return the models.dev provider key for a local provider code."""
    candidates = MODELS_DEV_PROVIDER_KEYS.get(provider_code, (provider_code,))
    for candidate in candidates:
        if candidate in source_json:
            return candidate
    return None


def models_dev_price_spec(
    model_payload: dict[str, Any],
) -> OfficialPriceSpec | None:
    """Convert one models.dev model entry into an official price spec."""
    if not isinstance(model_payload, dict):
        return None
    model_id = str(model_payload.get("id") or "").strip()
    cost = model_payload.get("cost") or {}
    if not model_id or not isinstance(cost, dict):
        return None

    input_price = parse_decimal(cost.get("input"))
    output_price = parse_decimal(cost.get("output"))
    if input_price is None and output_price is None:
        return None

    return OfficialPriceSpec(
        model_id=model_id,
        aliases=models_dev_aliases(model_payload),
        input_per_million=input_price or Decimal("0"),
        output_per_million=output_price or Decimal("0"),
        display_name=str(model_payload.get("name") or model_id),
        source_note="models.dev cost, USD per 1M tokens.",
    )


def models_dev_aliases(model_payload: dict[str, Any]) -> tuple[str, ...]:
    """Return normalized aliases useful for matching configured models."""
    values = [
        model_payload.get("id"),
        model_payload.get("name"),
        model_payload.get("family"),
    ]
    aliases = []
    seen = set()
    for value in values:
        normalized = normalize_model_code(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(str(value))
    return tuple(aliases)


def parse_decimal(value) -> Decimal | None:
    """Parse a non-negative decimal from JSON price values."""
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def parse_json_content(content: str) -> Any | None:
    """Parse fetched JSON content when the source endpoint is JSON."""
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return None


def replace_config_source_url(
    config: OfficialProviderConfig,
    source_payload: dict[str, Any],
) -> OfficialProviderConfig:
    """Return a config with source URL matching the fetched endpoint."""
    return OfficialProviderConfig(
        provider_code=config.provider_code,
        provider_label=config.provider_label,
        source_url=source_payload.get("source_url") or config.source_url,
        currency=config.currency,
        models=config.models,
    )


def parse_spec_from_source_text(
    config: OfficialProviderConfig,
    spec: OfficialPriceSpec,
    source_text: str,
) -> OfficialPriceSpec | None:
    """Parse one configured official model price from source text."""
    windows = source_windows_for_spec(spec, source_text)
    if not windows:
        return None

    for window in windows:
        if spec.source_model_type == "Image":
            image_price = extract_image_price(window, config.currency)
            if image_price is not None:
                return replace(
                    spec,
                    image_output_per_image=image_price,
                    input_per_million=Decimal("0"),
                    output_per_million=Decimal("0"),
                )
            continue

        if spec.source_model_type == "Video":
            video_prices = extract_video_prices(window, config.currency)
            if video_prices:
                return replace(
                    spec,
                    video_output_prices=tuple(video_prices),
                    input_per_million=Decimal("0"),
                    output_per_million=Decimal("0"),
                )
            continue

        token_prices = extract_token_prices(window, config.currency)
        if token_prices is not None:
            return replace(
                spec,
                input_per_million=token_prices[0],
                output_per_million=token_prices[1],
            )

    return None


def source_windows_for_spec(
    spec: OfficialPriceSpec,
    source_text: str,
    radius: int = 1200,
) -> list[str]:
    """Return nearby source text windows for a configured model spec."""
    windows = []
    search_terms = (
        spec.aliases
        + (spec.model_id,)
        + ((spec.display_name,) if spec.display_name else ())
    )
    for term in search_terms:
        if not term:
            continue
        pattern = model_term_pattern(term)
        for match in re.finditer(pattern, source_text, re.IGNORECASE):
            start = max(match.start() - radius, 0)
            end = min(match.end() + radius, len(source_text))
            windows.append(source_text[start:end])
    return windows


def model_term_pattern(term: str) -> str:
    """Return a regex pattern that matches a complete model identifier."""
    escaped = re.escape(term)
    return rf"(?<![A-Za-z0-9_.-]){escaped}(?![A-Za-z0-9_.-])"


def extract_token_prices(
    text: str,
    currency: str,
) -> tuple[Decimal, Decimal] | None:
    """Extract input and output token prices from a model text window."""
    input_price = extract_labeled_price(
        text,
        labels=("input", "prompt", "输入", "输入价格"),
        currency=currency,
    )
    output_price = extract_labeled_price(
        text,
        labels=("output", "completion", "输出", "输出价格"),
        currency=currency,
    )
    if input_price is not None and output_price is not None:
        return input_price, output_price

    prices = extract_money_values(text, currency)
    if len(prices) >= 2:
        return prices[0], prices[1]
    return None


def extract_image_price(text: str, currency: str) -> Decimal | None:
    """Extract an image generation unit price from a source window."""
    image_price = extract_labeled_price(
        text,
        labels=("image", "图片", "张", "幅"),
        currency=currency,
    )
    if image_price is not None:
        return image_price

    prices = extract_money_values(text, currency)
    if prices:
        return prices[0]
    return None


def extract_video_prices(
    text: str,
    currency: str,
) -> list[tuple[str, Decimal]]:
    """Extract per-second video prices grouped by resolution."""
    prices = []
    for resolution in ("480P", "720P", "1080P", "2K", "4K"):
        pattern = (
            rf"{resolution}.{{0,160}}?"
            rf"({money_regex(currency)})"
        )
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        price = parse_money(match.group(1), currency)
        if price is not None:
            prices.append((resolution.upper(), price))

    if prices:
        return prices

    values = extract_money_values(text, currency)
    if values:
        return [("default", values[0])]
    return []


def extract_labeled_price(
    text: str,
    *,
    labels: tuple[str, ...],
    currency: str,
) -> Decimal | None:
    """Find the first currency amount close to any pricing label."""
    money_pattern = money_regex(currency)
    for label in labels:
        label_pattern = re.escape(label)
        patterns = (
            rf"{label_pattern}.{{0,180}}?({money_pattern})",
            rf"({money_pattern}).{{0,180}}?{label_pattern}",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            for group in match.groups():
                price = parse_money(group, currency)
                if price is not None:
                    return price
    return None


def extract_money_values(text: str, currency: str) -> list[Decimal]:
    """Extract currency amounts from source text in display order."""
    values = []
    for match in re.finditer(money_regex(currency), text, re.IGNORECASE):
        price = parse_money(match.group(0), currency)
        if price is not None:
            values.append(price)
    return values


def money_regex(currency: str) -> str:
    """Return a permissive currency amount regex for source pages."""
    if currency.upper() == "CNY":
        return (
            r"(?:[¥￥]\s*\d+(?:\.\d+)?|"
            r"\d+(?:\.\d+)?\s*(?:元|人民币)|"
            r"(?:CNY|RMB)\s*\d+(?:\.\d+)?)"
        )
    return (
        r"(?:\$\s*\d+(?:\.\d+)?|"
        r"\d+(?:\.\d+)?\s*(?:USD|dollars?)|"
        r"USD\s*\d+(?:\.\d+)?)"
    )


def parse_money(raw_value: str, currency: str) -> Decimal | None:
    """Parse a currency amount from scraped source text."""
    value = str(raw_value or "")
    value = re.sub(
        r"(USD|CNY|RMB|dollars?|人民币|元|\$|¥|￥|,|\s)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if parsed < 0:
        return None
    return parsed


def normalize_source_text(content: str) -> str:
    """Normalize fetched HTML, JSON, or text into searchable plain text."""
    text = html.unescape(str(content or ""))
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\u([0-9a-fA-F]{4})", unicode_escape_match, text)
    text = re.sub(r"[\s\u00a0]+", " ", text)
    return text.strip()


def unicode_escape_match(match: re.Match) -> str:
    """Decode one unicode escape captured from embedded JSON text."""
    return chr(int(match.group(1), 16))


def first_matching_spec(
    config: OfficialProviderConfig,
    model_code: str,
) -> OfficialPriceSpec | None:
    """Return the first official price spec matching a model code."""
    specs = sorted(
        config.models,
        key=lambda spec: max(len(alias) for alias in spec.aliases),
        reverse=True,
    )
    for spec in specs:
        if spec.matches(model_code):
            return spec
    return None


def build_collected_pricing(
    config: OfficialProviderConfig,
    spec: OfficialPriceSpec,
    model_code: str,
) -> CollectedModelPricing:
    """Build a normalized collected pricing row from official data."""
    price_rows = build_price_rows(spec, model_code)
    raw_price_info = {
        "currency": config.currency,
        "unit": 1000000,
        "billing_mode": "pay_as_you_go",
    }
    raw_detail = {
        "official_source_url": config.source_url,
        "official_provider": config.provider_label,
        "published_model_id": spec.model_id,
        "matched_model_code": model_code,
        "currency": config.currency,
    }
    model_type_label = {
        "Image": "图片模型",
        "Video": "视频模型",
    }.get(spec.source_model_type, "文本模型")
    return CollectedModelPricing(
        model_source=config.provider_label,
        model_type=model_type_label,
        source_model_type=spec.source_model_type,
        name=spec.display_name or model_code,
        model_id=model_code,
        platform_id=model_code,
        mode="official",
        provider=config.provider_label,
        billing_type="按量计费",
        billing_unit=config.currency,
        currency=config.currency,
        unit=1000000,
        billing_mode="pay_as_you_go",
        price_rows=price_rows,
        raw_price_info=raw_price_info,
        raw_detail=raw_detail,
    )


def build_price_rows(
    spec: OfficialPriceSpec,
    model_code: str,
) -> list[NormalizedPriceRow]:
    """Build normalized price rows for an official model spec."""
    raw = {
        "model_id": spec.model_id,
        "matched_model_code": model_code,
        "source_note": spec.source_note,
    }
    if spec.source_model_type == "Image":
        return [
            NormalizedPriceRow(
                kind="image_unit",
                values={
                    "unit_price": str(spec.image_output_per_image or 0),
                },
                raw=raw,
            )
        ]
    if spec.source_model_type == "Video":
        return [
            NormalizedPriceRow(
                kind="video_resolution_output",
                values={
                    "resolution": resolution,
                    "price": str(price),
                },
                raw=raw,
            )
            for resolution, price in spec.video_output_prices
        ]
    return [
        NormalizedPriceRow(
            kind="text_token",
            values={
                "input_price": str(spec.input_per_million),
                "output_price": str(spec.output_per_million),
            },
            raw=raw,
        )
    ]


def attach_source_payload(
    item: CollectedModelPricing,
    source_payload: dict[str, Any],
) -> CollectedModelPricing:
    """Return item with source fetch metadata attached to raw_detail."""
    if not source_payload:
        return item
    raw_detail = {
        **item.raw_detail,
        "official_source_fetch": source_fetch_metadata(source_payload),
    }
    return CollectedModelPricing(
        model_source=item.model_source,
        model_type=item.model_type,
        source_model_type=item.source_model_type,
        name=item.name,
        model_id=item.model_id,
        platform_id=item.platform_id,
        mode=item.mode,
        provider=item.provider,
        billing_type=item.billing_type,
        billing_unit=item.billing_unit,
        currency=item.currency,
        unit=item.unit,
        billing_mode=item.billing_mode,
        price_rows=item.price_rows,
        raw_price_info=item.raw_price_info,
        raw_detail=raw_detail,
    )


def source_fetch_metadata(source_payload: dict[str, Any]) -> dict[str, Any]:
    """Return source fetch metadata safe for per-model raw detail storage."""
    return {
        key: value
        for key, value in source_payload.items()
        if key not in {"json", "text"}
    }


def normalize_model_code(value: str) -> str:
    """Normalize model identifiers for matching public aliases."""
    return str(value or "").strip().lower().replace("_", "-")
