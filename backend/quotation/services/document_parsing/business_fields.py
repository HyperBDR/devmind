from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

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
EXPIRE_DATE_LABELS = (
    "Quote Valid Till",
    "Valid Till",
    "Valid Until",
    "Expiry Date",
    "Expiration Date",
    "Expire Date",
)
QUOTE_NO_LABELS = (
    "Quote No.",
    "Quotation No.",
    "Quote Number",
    "Quotation Number",
)
REMARKS_LABELS = (
    "Additional Notes & Disclaimers",
    "Remarks",
    "Remark",
)
_CURRENCY_CANONICAL = {
    "USD": "USD",
    "US$": "USD",
    "CNY": "CNY",
    "RMB": "CNY",
    "¥": "CNY",
    "￥": "CNY",
    "EUR": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
    "HKD": "HKD",
    "HK$": "HKD",
    "MYR": "MYR",
    "RM": "MYR",
}
_FULL_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.I,
)
_TRUNCATED_ONEPRO_RE = re.compile(
    r"([A-Z0-9._%+-]+)@oneproclo(?:ud)?\.?(?=$|[^A-Z0-9.-])",
    re.I,
)
_PERSON_NAME_RE = re.compile(
    r"^[A-Za-z][A-Za-z.'-]*"
    r"(?:\s+[A-Za-z][A-Za-z.'-]*){1,3}$"
)


def find_issuer_email(text: str) -> tuple[str, int, int] | None:
    """Return a source email span, repairing truncated OnePro addresses."""
    raw = str(text or "")
    match = _FULL_EMAIL_RE.search(raw)
    if match:
        return match.group(0), match.start(), match.end()
    match = _TRUNCATED_ONEPRO_RE.search(raw)
    if match is None:
        return None
    email = f"{match.group(1)}@oneprocloud.com"
    return email, match.start(), match.end()


def looks_like_person_name(value: str) -> bool:
    """Return whether text looks like a personal name, not a project label."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or "@" in text or any(char.isdigit() for char in text):
        return False
    lowered = text.casefold()
    blocked = (
        "hyper",
        "license",
        "project",
        "disaster",
        "recovery",
        "quotation",
        "subscription",
    )
    if any(token in lowered for token in blocked):
        return False
    return bool(_PERSON_NAME_RE.fullmatch(text))


def strip_repeated_field_label(value: str, *labels: str) -> str:
    """Remove duplicated leading labels such as ``Title : Title :``."""
    text = str(value or "").strip()
    if not labels:
        return text
    pattern = "|".join(re.escape(label) for label in labels)
    while True:
        updated = re.sub(
            rf"^(?:{pattern})\s*:\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        if updated == text:
            return text
        text = updated


def repair_issuer_email(value: str) -> str:
    """Normalize a standalone issuer email cell when it was truncated."""
    found = find_issuer_email(value)
    if found is None:
        return str(value or "").strip()
    return found[0]


def split_salesperson_after_email(
    email: str,
    values: list[str],
) -> tuple[str, list[str]]:
    """Split a leading salesperson name using the email local part."""
    tokens = [str(value or "").strip() for value in values if value]
    local_part = str(email or "").split("@", 1)[0]
    email_tokens = [
        token
        for token in re.split(r"[._+-]+", local_part)
        if token
    ]

    def normalized(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    if 2 <= len(email_tokens) <= 4 and len(tokens) > len(email_tokens):
        source_tokens = tokens[: len(email_tokens)]
        if all(
            normalized(source) == normalized(expected)
            for source, expected in zip(source_tokens, email_tokens)
        ):
            return " ".join(source_tokens), tokens[len(email_tokens) :]

    if len(tokens) >= 3:
        candidate = " ".join(tokens[:2])
        if looks_like_person_name(candidate):
            return candidate, tokens[2:]
    return "", tokens


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


def parse_quote_date(value: Any) -> date | None:
    """Parse a quotation date from common document formats."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = re.sub(r"\s+", " ", str(value or "")).strip(" ,")
    if not raw:
        return None
    natural = re.sub(
        r"(?<=\d)(st|nd|rd|th)\b",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip(" ,")
    try:
        return date.fromisoformat(natural)
    except ValueError:
        pass
    dashed = re.sub(r"[./]", "-", natural)
    parts = dashed.split("-")
    numeric_formats: tuple[str, ...] = ()
    if len(parts) == 3:
        if len(parts[0]) == 4:
            numeric_formats = ("%Y-%m-%d",)
        elif len(parts[2]) == 4:
            numeric_formats = ("%d-%m-%Y",)
        else:
            numeric_formats = ("%d-%m-%y",)
    for date_format in numeric_formats:
        try:
            return datetime.strptime(dashed, date_format).date()
        except ValueError:
            continue
    for date_format in (
        "%d %B, %Y",
        "%d %b, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d/%b/%Y",
        "%d/%b/%y",
    ):
        try:
            return datetime.strptime(natural, date_format).date()
        except ValueError:
            continue
    digits = re.sub(r"\D", "", natural)
    if len(digits) != 8:
        return None
    for date_format in ("%Y%m%d", "%d%m%Y"):
        try:
            return datetime.strptime(digits, date_format).date()
        except ValueError:
            continue
    return None


def normalize_currency_code(value: str, default: str = "USD") -> str:
    """Return a canonical ISO-like currency code from document text."""
    raw = re.sub(r"\s+", "", str(value or "")).upper()
    if not raw:
        return default
    raw = raw.split("/", 1)[0]
    return _CURRENCY_CANONICAL.get(raw, raw[:10] or default)
