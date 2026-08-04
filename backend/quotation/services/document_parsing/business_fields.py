from __future__ import annotations

import re

PRODUCT_LINE_PATTERNS = (
    ("HyperBDR", "BDR", re.compile(r"\bhyper[\s-]*bdr\b", re.I)),
    (
        "HyperMotion",
        "Motion",
        re.compile(r"\bhyper[\s-]*motion\b", re.I),
    ),
    ("AGIOne", "AGIOne", re.compile(r"\bagi[\s-]*one\b", re.I)),
    (
        "General Service",
        "Service",
        re.compile(r"\bgeneral[\s-]*service\b", re.I),
    ),
)

PRODUCT_LINE_LABELS = (
    "Product Line",
    "Product Line Name",
    "Solution Line",
)
QUOTE_DATE_LABELS = (
    "Quote Date",
    "Quotation Date",
    "Date",
)


def known_product_line(value: str) -> tuple[str, str]:
    """Return the official name and quote prefix found in source text."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for name, prefix, pattern in PRODUCT_LINE_PATTERNS:
        if pattern.search(text):
            return name, prefix
    return "", ""


def explicit_product_line(value: str) -> tuple[str, str]:
    """Preserve an explicit source name and derive only a known prefix."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return "", ""
    name, prefix = known_product_line(text)
    if name:
        return name, prefix
    return text[:120], ""
