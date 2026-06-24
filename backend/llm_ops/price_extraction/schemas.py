from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ExtractedPrice:
    """One normalized price dimension extracted from a source."""

    dimension: str
    amount: Decimal
    unit: str
    note: str = ""


@dataclass(frozen=True)
class ExtractedModelPrice:
    """Candidate prices for one upstream model before persistence."""

    model_code: str
    currency: str
    prices: tuple[ExtractedPrice, ...]
    parser: str
    confidence: Decimal | None = None
    evidence: str = ""
    source_url: str = ""
    raw: dict | None = None


@dataclass(frozen=True)
class RejectedModelPrice:
    """A candidate price rejected before it can write current prices."""

    candidate: ExtractedModelPrice
    reason: str


@dataclass(frozen=True)
class PriceExtractionValidationResult:
    """Validation outcome for extracted price candidates."""

    accepted: tuple[ExtractedModelPrice, ...]
    rejected: tuple[RejectedModelPrice, ...]
