"""Currency normalization for Data Ops metrics."""

from __future__ import annotations


DEFAULT_CURRENCY = "CNY"


def normalize_currency(value: str | None) -> str:
    """Use CNY when a source record does not declare its currency."""
    return str(value or "").strip() or DEFAULT_CURRENCY


__all__ = ("DEFAULT_CURRENCY", "normalize_currency")
