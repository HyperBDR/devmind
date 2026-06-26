from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .schemas import ExtractedModelPrice, ExtractedPrice
from .validators import validate_extracted_model_prices


def official_specs_to_extracted_model_prices(
    *,
    config,
    specs: Iterable,
    parser: str = "deterministic",
) -> tuple[ExtractedModelPrice, ...]:
    """Convert official provider specs into generic price candidates."""
    candidates = []
    for spec in specs:
        candidates.append(
            ExtractedModelPrice(
                model_code=spec.model_id,
                currency=str(config.currency or "").upper(),
                prices=official_spec_prices(spec),
                parser=parser,
                confidence=Decimal("1"),
                evidence=spec.source_note or config.source_url,
                source_url=config.source_url,
                raw={
                    "provider_code": config.provider_code,
                    "source_model_type": spec.source_model_type,
                },
            )
        )
    return tuple(candidates)


def validate_official_price_specs(
    *,
    config,
    specs: Iterable,
    parser: str = "deterministic",
) -> None:
    """Validate official specs before they can flow to persistence."""
    result = validate_extracted_model_prices(
        official_specs_to_extracted_model_prices(
            config=config,
            specs=specs,
            parser=parser,
        )
    )
    if not result.rejected:
        return

    reasons = "; ".join(
        f"{item.candidate.model_code}: {item.reason}"
        for item in result.rejected
    )
    raise ValueError(f"Invalid extracted official prices: {reasons}")


def official_spec_prices(spec) -> tuple[ExtractedPrice, ...]:
    """Return generic price dimensions for one official spec."""
    if spec.source_model_type == "Image":
        return (
            ExtractedPrice(
                dimension="image_output",
                amount=spec.image_output_per_image or Decimal("0"),
                unit="per_image",
            ),
        )
    if spec.source_model_type == "Video":
        return tuple(
            ExtractedPrice(
                dimension=f"video_output:{resolution}",
                amount=price,
                unit="per_second",
            )
            for resolution, price in spec.video_output_prices
        )
    prices = [
        ExtractedPrice(
            dimension="input",
            amount=spec.input_per_million,
            unit="per_1m_tokens",
        ),
        ExtractedPrice(
            dimension="output",
            amount=spec.output_per_million,
            unit="per_1m_tokens",
        ),
    ]
    cache_input_price = getattr(spec, "cache_input_per_million", None)
    if cache_input_price is not None:
        prices.append(
            ExtractedPrice(
                dimension="cache_input",
                amount=cache_input_price,
                unit="per_1m_tokens",
            )
        )
    return tuple(prices)
