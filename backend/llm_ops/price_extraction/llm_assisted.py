from __future__ import annotations

from .schemas import ExtractedModelPrice


class LLMPriceExtractionNotConfigured(RuntimeError):
    """Raised when LLM-assisted extraction is requested but unavailable."""


def extract_prices_with_llm(
    *,
    source_text: str,
    source_url: str,
    provider_code: str,
    model_codes: set[str] | None = None,
) -> tuple[ExtractedModelPrice, ...]:
    """Extract candidate prices with an LLM-backed parser.

    The function is intentionally side-effect free. It must return
    candidates that still pass validators before any persistence layer
    can write them to current prices.
    """
    raise LLMPriceExtractionNotConfigured(
        "LLM-assisted price extraction is not configured.",
    )
