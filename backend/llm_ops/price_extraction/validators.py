from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .schemas import (
    ExtractedModelPrice,
    PriceExtractionValidationResult,
    RejectedModelPrice,
)


SUPPORTED_CURRENCIES = {"CNY", "USD"}
LLM_PARSER_NAME = "llm"
DEFAULT_MIN_LLM_CONFIDENCE = Decimal("0.80")


def validate_extracted_model_prices(
    candidates: Iterable[ExtractedModelPrice],
    *,
    allowed_model_codes: set[str] | None = None,
    min_llm_confidence: Decimal = DEFAULT_MIN_LLM_CONFIDENCE,
) -> PriceExtractionValidationResult:
    """Validate extracted prices before they are eligible for persistence."""
    accepted = []
    rejected = []
    for candidate in candidates:
        reason = rejection_reason(
            candidate,
            allowed_model_codes=allowed_model_codes,
            min_llm_confidence=min_llm_confidence,
        )
        if reason:
            rejected.append(RejectedModelPrice(candidate, reason))
        else:
            accepted.append(candidate)
    return PriceExtractionValidationResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
    )


def rejection_reason(
    candidate: ExtractedModelPrice,
    *,
    allowed_model_codes: set[str] | None,
    min_llm_confidence: Decimal,
) -> str:
    """Return the first validation failure reason for a candidate."""
    model_code = str(candidate.model_code or "").strip()
    if not model_code:
        return "model_code is required."
    if (
        allowed_model_codes is not None
        and model_code not in allowed_model_codes
    ):
        return f"{model_code} is not in allowed model codes."

    currency = str(candidate.currency or "").upper()
    if currency not in SUPPORTED_CURRENCIES:
        return f"{currency or 'currency'} is not supported."

    if not candidate.prices:
        return "at least one price dimension is required."

    for price in candidate.prices:
        if not str(price.dimension or "").strip():
            return "price dimension is required."
        if not str(price.unit or "").strip():
            return "price unit is required."
        if price.amount < 0:
            return "price amount cannot be negative."

    if candidate.parser == LLM_PARSER_NAME:
        if candidate.confidence is None:
            return "LLM candidate requires confidence."
        if candidate.confidence < min_llm_confidence:
            return "LLM candidate confidence is below threshold."
        if not candidate.evidence.strip():
            return "LLM candidate requires evidence."

    return ""
