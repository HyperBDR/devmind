from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from core.pdf_ocr import extract_pdf_text_with_ocr
from core.pdf_text import extract_pdf_text
from invoice.parsing.schemas import (
    ParsedInvoice,
    ParsedInvoiceDocumentData,
    ParsedInvoiceItem,
)
from quotation.services.document_parsing.business_fields import (
    normalize_currency_code,
)

PARSER_NAME = "devmind_invoice_pdf"
PARSER_VERSION = "0.7.0"

_CURRENCY_TOKEN_RE = re.compile(
    r"(?<![A-Z])(?:USD|MYR|HKD|SGD|CNY|RMB|EUR|GBP|THB|BAHT)"
    r"(?![A-Z])|US\$|HK\$|S\$|RM(?=\s*[\d.,])|[$€£¥￥]",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?:(?P<prefix>USD|MYR|HKD|SGD|CNY|RMB|EUR|GBP|THB|BAHT|"
    r"US\$|HK\$|S\$|RM|[$€£¥￥])\s*)?"
    r"(?P<amount>-?[\d,]+(?:\.\d{1,4})?)"
    r"(?:\s*(?P<suffix>USD|MYR|HKD|SGD|CNY|RMB|EUR|GBP|THB|BAHT))?",
    re.IGNORECASE,
)
_CONTACT_NAME_PREFIX_RE = re.compile(
    r"^(?:name|contact\s+person|contact|经办人|联系人)\s*[:：#]?\s*",
    re.IGNORECASE,
)
_CONTACT_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)


class InvoicePdfParseError(ValueError):
    """Raised when an invoice PDF cannot be read safely."""


def _extract_text(path: Path) -> str:
    text = ""
    try:
        text = extract_pdf_text(path, layout=True)
    except Exception as exc:
        raise InvoicePdfParseError(
            f"Unable to read invoice PDF: {type(exc).__name__}: {exc}"
        ) from exc
    if len(text.strip()) < 300:
        try:
            ocr_text = extract_pdf_text_with_ocr(path, dpi=300)
        except Exception as exc:
            if not text.strip():
                raise InvoicePdfParseError(
                    "Unable to OCR invoice PDF: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
        else:
            text = "\n".join(
                value for value in (text.strip(), ocr_text.strip()) if value
            )
    if not text.strip():
        raise InvoicePdfParseError("Invoice PDF contains no extractable text")
    return text


def _label_value(text: str, labels: tuple[str, ...]) -> str:
    joined = "|".join(
        re.escape(label)
        for label in sorted(labels, key=len, reverse=True)
    )
    match = re.search(
        rf"(?:^|\n)[ \t|;·•_-]*(?:{joined})[ \t]*\.?(?:[ \t]*[:：#])?"
        rf"[ \t]*([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_label_value(match.group(1)) if match else ""


def _label_or_next_value(text: str, labels: tuple[str, ...]) -> str:
    """Read a labelled value whether PDF text keeps it on the next line."""
    value = _label_value(text, labels) or _inline_label_value(text, labels)
    if value:
        return value
    joined = "|".join(
        re.escape(label)
        for label in sorted(labels, key=len, reverse=True)
    )
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        if not re.fullmatch(
            rf"[\s|;·•_-]*(?:{joined})\s*[:：#]?\s*",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        for candidate in lines[index + 1 : index + 4]:
            cleaned = _clean_label_value(candidate)
            if cleaned:
                return cleaned
    return ""


def _inline_label_value(text: str, labels: tuple[str, ...]) -> str:
    joined = "|".join(
        re.escape(label)
        for label in sorted(labels, key=len, reverse=True)
    )
    match = re.search(
        rf"(?:^|\n|[ \t]{{2,}})(?:{joined})[ \t]*\.?"
        rf"(?:[ \t]*[:：#])?[ \t]*([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_label_value(match.group(1)) if match else ""


def _anywhere_label_value(text: str, labels: tuple[str, ...]) -> str:
    """Read a field when OCR joins its label to another visual column."""
    joined = "|".join(
        re.escape(label)
        for label in sorted(labels, key=len, reverse=True)
    )
    match = re.search(
        rf"(?:{joined})\s*[:：#]\s*([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_label_value(match.group(1)) if match else ""


def _clean_label_value(value: str) -> str:
    """Keep the first visual column after a document field label."""
    first_column = re.split(r"[ \t]{2,}", value.strip(), maxsplit=1)[0]
    return re.sub(r"\s+", " ", first_column).strip(
        " \t:：#;；,，|·•_-"
    )


def _clean_contact_name(value: str) -> str:
    """Normalize OCR noise without inventing a contact identity."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    cleaned = re.sub(
        r"^(?:if|ul|ll|i)\s+(?=[A-Z])",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    email_match = _CONTACT_EMAIL_RE.search(cleaned)
    if email_match:
        cleaned = cleaned[: email_match.start()]
    cleaned = _CONTACT_NAME_PREFIX_RE.sub("", cleaned).strip()
    return cleaned.strip(" \t:：#;；,，|·•")


def _clean_contact_email(value: str) -> str:
    """Extract only a valid email token from an OCR value."""
    match = _CONTACT_EMAIL_RE.search(str(value or ""))
    if not match:
        return ""
    email = match.group(0).strip(" \t.,;；，").casefold()
    local, separator, domain = email.partition("@")
    if not separator:
        return email
    domain = domain.replace("cioud", "cloud")
    domain = domain.replace("ctoud", "cloud")
    domain = domain.replace("oneprac", "onepro")
    domain = domain.replace("onenrocloud", "oneprocloud")
    domain = domain.replace("onenincloud", "oneprocloud")
    return f"{local}@{domain}"


def _parse_date(value: str) -> date | None:
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"\s+([,])", r"\1", value)
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d.%m.%y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{4})[年./-](\d{1,2})[月./-](\d{1,2})", value)
    if match:
        return date(*(int(part) for part in match.groups()))
    return None


def _parse_amount(value: str) -> Decimal:
    cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
    if not cleaned or not re.search(r"\d", cleaned):
        return Decimal("0")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise InvoicePdfParseError(f"Invalid invoice amount: {value}") from exc


def _normalize_currency(value: str) -> str:
    """Reuse Quote currency aliases and cover common invoice symbols."""
    raw = re.sub(r"\s+", "", str(value or "")).upper()
    local_aliases = {
        "$": "USD",
        "BAHT": "THB",
        "S$": "SGD",
        "SGD": "SGD",
    }
    return local_aliases.get(
        raw,
        normalize_currency_code(raw, default=""),
    )


def _currency_from_text(value: str) -> str:
    matches = list(_CURRENCY_TOKEN_RE.finditer(value or ""))
    if not matches:
        return ""
    codes = [
        match.group(0)
        for match in matches
        if match.group(0).upper() not in {"$", "€", "£", "¥", "￥"}
    ]
    return _normalize_currency(codes[0] if codes else matches[0].group(0))


def _money_values(value: str) -> list[tuple[Decimal, str]]:
    values = []
    for match in _MONEY_RE.finditer(value or ""):
        raw_amount = match.group("amount")
        if not raw_amount or raw_amount.endswith("."):
            continue
        token = match.group("prefix") or match.group("suffix") or ""
        values.append(
            (
                _parse_amount(raw_amount),
                _normalize_currency(token) if token else "",
            )
        )
    return values


def _line_has_label(line: str, label: str) -> re.Match | None:
    return re.search(
        rf"(?<![A-Za-z]){re.escape(label)}(?![A-Za-z])",
        line,
        flags=re.IGNORECASE,
    )


def _amount_by_labels(
    text: str,
    labels: tuple[str, ...],
    currency: str = "",
) -> Decimal:
    """Read a labelled amount, including totals printed on a later line."""
    lines = text.splitlines()
    for label in labels:
        candidates = []
        for index, line in enumerate(lines):
            match = _line_has_label(line, label)
            if match is None:
                continue
            inline = _money_values(line[match.end() :])
            candidates.extend(inline)
            if inline:
                continue
            for following in lines[index + 1 : index + 4]:
                next_values = _money_values(following)
                with_currency = [item for item in next_values if item[1]]
                if with_currency:
                    candidates.extend(with_currency)
                    break
        if currency:
            matching = [
                amount
                for amount, item_currency in candidates
                if item_currency == currency
            ]
            if matching:
                return matching[-1]
        if candidates:
            return candidates[-1][0]
    return Decimal("0")


def _invoice_currency(text: str) -> str:
    explicit = _label_value(text, ("Currency",)) or _inline_label_value(
        text,
        ("Currency",),
    )
    currency = _currency_from_text(explicit)
    if currency:
        return currency
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bcurrency\b", line, re.IGNORECASE):
            continue
        if not re.search(r"\bpayment\s+term", line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 4]:
            if not candidate.strip():
                continue
            currency = _currency_from_text(candidate)
            if currency:
                return currency
            break
    for label in (
        "Grand Total",
        "Total Amount",
        "Amount due",
        "Amount paid",
        "Amount of tax withheld",
        "refunded",
        "Total",
        "应付金额",
        "合计",
    ):
        for line in text.splitlines():
            if _line_has_label(line, label):
                currency = _currency_from_text(line)
                if currency:
                    return currency
    return _currency_from_text(text)


def _parse_delivery_note_items(
    lines: list[str],
    header_index: int,
) -> list[ParsedInvoiceItem]:
    """Read delivery-note lines without inventing monetary values."""
    pattern = re.compile(
        r"^\s*(\d+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+"
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*$",
        re.IGNORECASE,
    )
    items = []
    for line in lines[header_index + 1 :]:
        if re.search(
            r"^\s*(?:remarks|additional\s+notes|acknowledgment|"
            r"signature)\b",
            line,
            re.IGNORECASE,
        ):
            break
        match = pattern.match(line)
        if not match:
            continue
        line_no, description, quantity, _delivery_date = match.groups()
        items.append(
            ParsedInvoiceItem(
                line_no=int(line_no),
                product_name=description.strip().splitlines()[0][:255],
                description=description.strip(),
                quantity=Decimal(quantity),
            )
        )
    return items


def _parse_items(text: str) -> list[ParsedInvoiceItem]:
    items = []
    currency = (
        r"(?:USD|MYR|HKD|SGD|CNY|RMB|EUR|GBP|THB|BAHT|"
        r"US\$|HK\$|S\$|RM|[$€£¥￥])"
    )
    pattern = re.compile(
        r"^\s*(\d+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+"
        r"(?:[A-Z]{1,5}\s+)?"
        rf"(?:{currency}\s*)?"
        r"([\d,]+(?:\.\d{1,4})?)\s+"
        rf"(?:{currency}\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)\s*$",
        re.IGNORECASE,
    )
    receipt_pattern = re.compile(
        r"^\s*(.+?)\s+(\d+(?:\.\d+)?)\s+"
        rf"(?:{currency}\s*)?"
        r"([\d,]+(?:\.\d{1,4})?)\s+"
        rf"(?:{currency}\s*)?"
        r"([\d,]+(?:\.\d{1,2})?)\s*$",
        re.IGNORECASE,
    )
    lines = text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"\bdescription\b|描述", line, re.IGNORECASE)
            and re.search(
                r"\bqty\b|\bquantity\b|数量",
                line,
                re.IGNORECASE,
            )
            and re.search(
                r"\bamount\b|\bextended\s+price\b|\bdate\s+of\s+delivery\b|金额",
                line,
                re.IGNORECASE,
            )
        ),
        None,
    )
    if header_index is None:
        return []
    if re.search(
        r"\bdate\s+of\s+delivery\b",
        lines[header_index],
        re.IGNORECASE,
    ):
        return _parse_delivery_note_items(lines, header_index)
    pending_description: list[str] = []
    for line in lines[header_index + 1 :]:
        if re.search(
            r"^\s*(?:subtotal|grand\s+total|total\s+amount|total|"
            r"amount\s+(?:due|paid)|additional\s+notes|remarks|"
            r"disclaimer)\b",
            line,
            re.IGNORECASE,
        ):
            break
        match = pattern.match(line)
        if match:
            line_no, name, quantity, unit_price, total = match.groups()
        else:
            receipt_match = receipt_pattern.match(line)
            if not receipt_match:
                candidate = re.sub(r"\s+", " ", line).strip()
                has_letters = re.search(r"[^\W\d_]", candidate)
                if candidate and (
                    has_letters or not _money_values(candidate)
                ):
                    pending_description.append(candidate)
                continue
            name, quantity, unit_price, total = receipt_match.groups()
            line_no = str(len(items) + 1)
        name = name.strip()
        if name and pending_description and items:
            continuation = "\n".join(pending_description)
            items[-1].description = (
                f"{items[-1].description}\n{continuation}"
            )
        if not name:
            name = "\n".join(pending_description)
        items.append(
            ParsedInvoiceItem(
                line_no=int(line_no),
                product_name=(name.splitlines() or [""])[0][:255],
                description=name,
                quantity=Decimal(quantity),
                unit_price=_parse_amount(unit_price),
                net_amount=_parse_amount(total),
                total_amount=_parse_amount(total),
            )
        )
        pending_description = []
    if pending_description and items:
        continuation = "\n".join(pending_description)
        items[-1].description = f"{items[-1].description}\n{continuation}"
    return items


def _receipt_customer(text: str) -> str:
    """Read the right-hand customer column from payment receipts."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bbill\s+to\b|收票人", line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 5]:
            parts = re.split(r"\s{2,}", candidate.strip())
            if len(parts) > 1 and parts[-1].strip():
                value = parts[-1].strip()
                if value.lower() not in {"company", "address"}:
                    return value
    return ""


def _multiline_label_value(
    text: str,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...],
) -> str:
    """Read a wrapped field such as a customer postal address."""
    joined = "|".join(
        re.escape(label)
        for label in sorted(labels, key=len, reverse=True)
    )
    stop_joined = "|".join(
        re.escape(label)
        for label in sorted(stop_labels, key=len, reverse=True)
    )
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(
            rf"^\s*(?:{joined})\s*\.?(?:\s*[:：#])?\s*(.*)$",
            line,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        values = []
        initial = _clean_label_value(match.group(1))
        if initial:
            values.append(initial)
        for candidate in lines[index + 1 : index + 5]:
            stripped = candidate.strip()
            if not stripped:
                if values:
                    break
                continue
            if re.match(
                rf"^(?:{stop_joined})\s*[:：#]?",
                stripped,
                flags=re.IGNORECASE,
            ):
                break
            value = _clean_label_value(stripped)
            if value:
                values.append(value)
        return ", ".join(values)
    return ""


def _additional_notes_value(text: str) -> str:
    """Read all note lines, including blank lines between bullets."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.match(
            r"^\s*Additional Notes(?:\s*&\s*Disclaimers)?\s*[:：]?\s*$",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        values = []
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if re.match(r"^\s*Remarks\s*[:：]?\s*$", stripped, re.IGNORECASE):
                break
            if stripped:
                value = _clean_label_value(stripped)
                if value:
                    values.append(value)
        return "\n".join(values)
    return ""


def _receipt_customer_details(text: str) -> dict[str, str]:
    """Read customer contact fields from a two-column Stripe layout."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bbill\s+to\b|收票人", line, re.IGNORECASE):
            continue
        values = []
        for candidate in lines[index + 1 : index + 10]:
            if not candidate.strip():
                if values:
                    break
                continue
            parts = re.split(r"\s{2,}", candidate.strip())
            if len(parts) > 1 and parts[-1].strip():
                values.append(parts[-1].strip())
            elif candidate[:2].isspace() and candidate.strip():
                values.append(candidate.strip())
        if not values:
            return {}
        email = next(
            (value for value in values if "@" in value),
            "",
        )
        address = [
            value
            for value in values[1:]
            if "@" not in value
            and not re.search(r"(?:^|\s)\+?[\d ()-]{7,}$", value)
        ]
        return {
            "customer_name": _clean_contact_name(values[0]),
            "contact_person": _clean_contact_name(values[0]),
            "contact_email": email,
            "customer_address": ", ".join(address),
        }
    return {}


def _bill_to_section(text: str) -> str:
    """Bound customer labels so bank and signature fields cannot leak in."""
    lines = text.splitlines()
    start_indexes = []
    for index, line in enumerate(lines):
        if re.search(
            r"(?:^|\n)\s*bill\s+to\s*[:：]|^\s*bill\s+to\s*$",
            line,
            re.IGNORECASE,
        ):
            start_indexes.append(index)
        elif re.search(
            r"^\s*(?:company|customer|buyer)\s*[:：]",
            line,
            re.IGNORECASE,
        ):
            start_indexes.append(index)
    for index in start_indexes:
        line = lines[index]
        if not re.search(
            r"\bbill\s+to\b|^\s*(?:company|customer|buyer)\s*[:：]",
            line,
            re.IGNORECASE,
        ):
            continue
        section = [line]
        for candidate in lines[index + 1 : index + 14]:
            if re.search(
                r"\b(?:contact|[cg]antact)\s+person\b.*\bemail\b"
                r".*\bP[O0](?:#|F)?\b"
                r"|\bitem#?\b.*\bdescription\b"
                r"|^\s*total\s+amount\s*:",
                candidate,
                re.IGNORECASE,
            ):
                break
            section.append(candidate)
        return "\n".join(section)
    return ""


def _seller_fields(text: str) -> dict[str, str]:
    """Read seller contact fields from the header before the Bill to block."""
    customer_start = re.search(
        r"(?:^|\n)\s*(?:bill\s+to\b|company\s*[:：])",
        text,
        re.IGNORECASE,
    )
    header = text[: customer_start.start()] if customer_start else text
    lines = [line.strip() for line in header.splitlines() if line.strip()]
    website = next(
        (
            line
            for line in lines
            if re.fullmatch(r"https?://\S+|www\.\S+", line, re.I)
        ),
        "",
    )
    email = next(
        (line for line in lines if re.fullmatch(r"[^\s@]+@[^\s@]+", line)),
        "",
    )
    address_lines = []
    for line in lines:
        line = re.split(
            r"\s{2,}(?=(?:Date|Invoice Number)\s*:)",
            line,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        if re.search(r"UNIT\b|\bROAD\b|\bHONG KONG\b|\bKOWLOON\b", line, re.I):
            address_lines.append(line)
    seller_address = ", ".join(dict.fromkeys(address_lines))
    seller_address = re.sub(r",\s*,+", ",", seller_address)
    return {
        "seller_tax_id": _label_value(
            header,
            ("Seller Tax ID", "Seller VAT Number", "销方税号"),
        ),
        "seller_address": seller_address,
        "seller_website": website,
        "seller_email": email,
    }


def _customer_address_from_bill_to(text: str) -> str:
    """Keep wrapped address lines around the Address label."""
    section = _bill_to_section(text)
    if not section:
        return ""
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\bAddress\b\s*[:：]", line, re.I):
            continue
        values = []
        value = re.split(
            r"\bAddress\b\s*[:：]",
            line,
            maxsplit=1,
            flags=re.I,
        )[-1].strip()
        if value:
            values.append(value)
        previous = lines[index - 1].strip() if index else ""
        if value and previous and ":" not in previous and not re.search(
            r"\b(?:Company|Name|Email)\b",
            previous,
            re.I,
        ):
            values.insert(0, previous)
        for candidate in lines[index + 1:index + 4]:
            stripped = candidate.strip()
            if not stripped or re.search(
                r"\b(?:Company|Name|Email|Contact Person)\b\s*[:：]"
                r"|\b(?:Contact\s*#?|Phone|Telephone|Mobile)\s*[:：]",
                stripped,
                re.I,
            ):
                break
            values.append(stripped)
        return ", ".join(dict.fromkeys(values))
    return ""


def _summary_contact_fields(text: str) -> dict[str, str]:
    """Read the seller contact row below the Bill to block."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not (
            re.search(r"\b(?:contact|[cg]antact)\s+person\b", line, re.I)
            and re.search(r"\bemail\b", line, re.I)
            and re.search(r"\bP[O0](?:#|F)?\b", line, re.I)
        ):
            continue
        candidates = lines[index + 1 : index + 6]
        for candidate_index, candidate in enumerate(candidates):
            email_match = _CONTACT_EMAIL_RE.search(candidate)
            name = (
                _clean_contact_name(candidate[: email_match.start()])
                if email_match
                else _summary_contact_name_without_email(candidate)
            )
            if not name:
                for previous in reversed(candidates[:candidate_index]):
                    if (
                        previous.strip()
                        and not _CONTACT_EMAIL_RE.search(previous)
                        and not re.search(
                            r"\b(?:USD|MYR|HKD|SGD|CNY|EUR|GBP|THB)\b|"
                            r"^\s*[\d,.]+\s*$",
                            previous,
                            re.IGNORECASE,
                        )
                    ):
                        name = _clean_contact_name(previous)
                        if name:
                            break
            email = (
                _clean_contact_email(email_match.group(0))
                if email_match else ""
            )
            if not name:
                continue
            return {
                "contact_person": name,
                "contact_email": email,
            }
    return {}


def _summary_contact_name_without_email(candidate: str) -> str:
    """Read the first cell when OCR corrupts the contact email token."""
    value = re.sub(r"^[\s|;·•_-]+", "", candidate).strip()
    match = re.match(
        r"(?P<name>[A-Za-z][A-Za-z .'-]{0,39}?)(?=\s+"
        r"(?:[A-Za-z0-9._%+-]+@|[_|;:-]*[A-Z0-9]{4,}[-_]))",
        value,
        re.IGNORECASE,
    )
    if match:
        return _clean_contact_name(match.group("name"))
    first = re.split(r"\s{2,}|\s*[|_]{1,}\s*", value, maxsplit=1)[0]
    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,39}", first):
        return _clean_contact_name(first)
    return ""


def _summary_contact_fallback_email(text: str) -> str:
    """Use the last valid email after a contact table header."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not (
            re.search(r"\b(?:contact|[cg]antact)\s+person\b", line, re.I)
            and re.search(r"\bemail\b", line, re.I)
            and re.search(r"\bP[O0](?:#|F)?\b", line, re.I)
        ):
            continue
        matches = _CONTACT_EMAIL_RE.findall("\n".join(lines[index:]))
        if matches:
            return _clean_contact_email(matches[-1])
    return ""


def _reconciled_contact_email(text: str, contact_email: str) -> str:
    """Prefer a matching remittance address over a noisy OCR row value."""
    remittance_email = _clean_contact_email(_remittance_instruction(text))
    if not contact_email or not remittance_email:
        return contact_email
    contact_local = contact_email.partition("@")[0].casefold()
    remittance_local = remittance_email.partition("@")[0].casefold()
    return (
        remittance_email
        if contact_local == remittance_local
        else contact_email
    )


def _signatory_fields(text: str) -> dict[str, str]:
    """Read a signer only when a footer Title proves a signature block."""
    title_matches = list(
        re.finditer(
            r"(?:^|\n)\s*Title\s*[:：]?\s*([^\n]+)",
            text,
            re.IGNORECASE,
        )
    )
    if not title_matches:
        return {"name": "", "title": ""}
    title_match = title_matches[-1]
    name_matches = list(
        re.finditer(
            r"(?:^|\n)\s*Name\s*[:：]?\s*([^\n]+)",
            text[: title_match.start()],
            re.IGNORECASE,
        )
    )
    return {
        "name": (
            _clean_label_value(name_matches[-1].group(1))
            if name_matches else ""
        ),
        "title": _clean_label_value(title_match.group(1)),
    }


def _bank_fields(text: str) -> dict[str, str]:
    """Read bank data from the footer block, not customer details."""
    matches = list(
        re.finditer(
            r"(?:^|\n)\s*(?:Remarks|Bank Details|Bank Information)"
            r"\s*[:：]?",
            text,
            re.IGNORECASE,
        )
    )
    bank_text = text[matches[-1].start() :] if matches else text
    return {
        "account_name": _label_value(
            bank_text,
            ("Account Name", "Bank Account Beneficiary"),
        ),
        "bank_name": _label_value(bank_text, ("Bank Name",)),
        "bank_address": _label_value(bank_text, ("Bank Address",)),
        "account_number": _label_value(bank_text, ("Account Number",)),
        "bank_code": _label_value(bank_text, ("Bank Code",)),
        "branch_code": _label_value(bank_text, ("Branch Code",)),
        "swift_code": _label_value(bank_text, ("SWIFT CODE", "SWIFT")),
    }


def _remittance_instruction(text: str) -> str:
    """Read the complete remittance sentence from the source document."""
    match = re.search(
        r"(?:^|\n)\s*(P(?:lease|leose|Iease) use the Invoice number "
        r"as a reference and "
        r"email remittance advice to\s+[^\n]+)",
        text,
        re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _document_classification(text: str) -> tuple[str, dict | None]:
    """Classify the PDF without stopping extraction of its fields."""
    classifications = (
        (
            r"\bdelivery\s+note\b",
            "delivery_note",
            "delivery_note_detected",
            "The PDF is a delivery note.",
        ),
        (
            r"\bwithholding\s+tax\b",
            "withholding_tax",
            "withholding_tax_detected",
            "The PDF is a withholding tax record.",
        ),
        (
            r"(?:^|\n)\s*proforma\s+invoice\s*(?:\n|$)",
            "proforma_invoice",
            "proforma_invoice_detected",
            "The PDF is a proforma invoice.",
        ),
        (
            r"(?:^|\n)\s*refund\s*(?:\n|$)",
            "refund",
            "refund_detected",
            "The PDF is a refund record.",
        ),
    )
    for pattern, kind, code, detail in classifications:
        if re.search(pattern, text, re.IGNORECASE):
            return kind, {
                "field": "document",
                "code": code,
                "detail": detail,
            }
    return "invoice", None


def _withholding_invoice_reference(text: str) -> str:
    """Read the referenced Invoice number from a WHT summary table."""
    match = re.search(
        r"(?:^|\n)\s*INVOICE\s+(?:P\.?O\.?|PO)\s+WHT[^\n]*"
        r"\n\s*([A-Z0-9][A-Z0-9._/-]+)",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_label_value(match.group(1)) if match else ""


def _date_after_label(text: str, label: str) -> date | None:
    """Read a date printed just below a long field label."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(re.escape(label), line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 4]:
            parsed = _parse_date(candidate.strip())
            if parsed is not None:
                return parsed
    return None


def _purchase_order_number(text: str) -> str:
    """Read labelled and compact tabular purchase-order numbers."""
    labelled = _label_value(
        text,
        ("Purchase Order No", "PO Number", "PO No", "PO#"),
    ) or _inline_label_value(
        text,
        ("Purchase Order No", "PO Number", "PO No"),
    )
    if labelled:
        return labelled
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not (
            re.search(r"\bemail\b", line, re.IGNORECASE)
            and re.search(r"\bPO#?\b", line, re.IGNORECASE)
        ):
            continue
        for candidate in lines[index + 1 : index + 4]:
            tokens = candidate.replace("|", " ").split()
            email_index = next(
                (
                    position
                    for position, token in enumerate(tokens)
                    if "@" in token
                ),
                None,
            )
            if email_index is None:
                continue
            for token in tokens[email_index + 1 :]:
                cleaned = _clean_label_value(token)
                if cleaned.lower() in {"com", "net", "org"}:
                    continue
                if re.search(r"\d", cleaned):
                    return cleaned
    wht_match = re.search(
        r"(?:^|\n)\s*INVOICE\s+(?:P\.?O\.?|PO)\s+WHT[^\n]*"
        r"\n\s*[A-Z0-9][A-Z0-9._/-]+\s+(\S+)",
        text,
        re.IGNORECASE,
    )
    if wht_match:
        return _clean_label_value(wht_match.group(1))
    match = re.search(r"#(PO/[A-Z0-9/_-]+)", text, re.IGNORECASE)
    return match.group(1) if match else ""


def _payment_terms(text: str) -> str:
    """Read payment terms from labels or the commercial summary row."""
    def normalize(value: str) -> str:
        cleaned = _clean_label_value(value)
        cleaned = re.sub(
            r"\bNET\s+(\d+)\b",
            r"NET\1",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned

    labelled = _label_value(
        text,
        ("Payment Terms", "Payment Term"),
    ) or _inline_label_value(
        text,
        ("Payment Terms", "Payment Term"),
    )
    if labelled and not re.search(r"\bcurrency\b", labelled, re.IGNORECASE):
        if re.fullmatch(r"[|_\-]+", labelled):
            return ""
        return normalize(labelled)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not (
            re.search(r"\bcurrency\b", line, re.IGNORECASE)
            and re.search(r"\bpayment\s+terms?\b", line, re.IGNORECASE)
        ):
            continue
        for candidate in lines[index + 1 : index + 4]:
            match = re.search(
                r"(?:USD|MYR|HKD|SGD|CNY|EUR|GBP|THB)\s+"
                r"(\S+(?:\s+\d+)?)",
                candidate,
                re.IGNORECASE,
            )
            if match:
                value = normalize(match.group(1))
                return "" if re.fullmatch(r"[|_\-]+", value) else value
    return ""


def parse_invoice_pdf(path: Path) -> ParsedInvoiceDocumentData:
    """Extract a reviewable normalized invoice from a text PDF."""
    text = _extract_text(path)
    document_kind, classification_warning = _document_classification(text)
    invoice_no = _label_value(
        text,
        (
            "Proforma Invoice Number",
            "Delivery Note Number",
            "DN Number",
            "Invoice No",
            "Invoice Number",
            "账单编号",
            "发票号码",
            "发票编号",
        ),
    ) or _inline_label_value(
        text,
        (
            "Proforma Invoice Number",
            "Delivery Note Number",
            "DN Number",
            "Invoice No",
            "Invoice Number",
            "账单编号",
            "发票号码",
            "发票编号",
        ),
    ) or _anywhere_label_value(
        text,
        (
            "Proforma Invoice Number",
            "Delivery Note Number",
            "DN Number",
            "Invoice No",
            "Invoice Number",
        ),
    )
    if document_kind == "withholding_tax":
        invoice_no = _withholding_invoice_reference(text) or invoice_no
    invoice_date_value = _label_value(
        text,
        (
            "Invoice Date",
            "Date of issue",
            "Date issued",
            "Date paid",
            "Date (DD/MM/YY)",
            "发出日期",
            "开票日期",
        ),
    ) or _inline_label_value(
        text,
        (
            "Invoice Date",
            "Date (DD/MM/YY)",
            "Date",
            "发出日期",
            "开票日期",
        ),
    )
    invoice_date = _parse_date(invoice_date_value)
    if invoice_date is None:
        invoice_date = _parse_date(
            _anywhere_label_value(text, ("Date",))
        )
    if document_kind == "withholding_tax" and invoice_date is None:
        invoice_date = _date_after_label(
            text,
            "Amount of tax withheld and date of tax payment",
        )
        if invoice_date is None:
            date_matches = re.findall(
                r"\b(?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+"
                r"\d{1,2},?\s+\d{4}\b",
                text,
                re.IGNORECASE,
            )
            if date_matches:
                invoice_date = _parse_date(date_matches[-1])
    due_date_value = _label_value(
        text,
        (
            "Due Date (DD/MM/YY)",
            "Due Date",
            "Date due",
            "到期日期",
            "到期日",
        ),
    ) or _inline_label_value(
        text,
        (
            "Due Date (DD/MM/YY)",
            "Due Date",
            "Date due",
            "到期日期",
            "到期日",
        ),
    )
    due_date = _parse_date(due_date_value)
    currency = _invoice_currency(text)
    seller_name = _label_value(
        text,
        ("Seller", "From", "销售方", "销方名称"),
    )
    if not seller_name:
        seller_name = next(
            (
                re.sub(r"\s+", " ", line).strip()
                for line in text.splitlines()
                if line.strip()
                and "commercial invoice" not in line.lower()
                and "receipt" not in line.lower()
            ),
            "",
        )
    bill_to_text = _bill_to_section(text)
    customer_source = bill_to_text or text
    customer_name = _label_value(
        customer_source,
        ("Customer", "Buyer", "Company", "购买方", "购方名称"),
    ) or _inline_label_value(
        customer_source,
        ("Bill To",),
    )
    customer_name = customer_name or _receipt_customer(text)
    receipt_details = (
        {} if bill_to_text else _receipt_customer_details(text)
    )
    customer_name = customer_name or receipt_details.get(
        "customer_name",
        "",
    )
    customer_name = _clean_contact_name(customer_name)
    customer_tax_id = ""
    customer_contact_person = ""
    customer_contact_email = ""
    customer_contact_phone = ""
    customer_address = ""
    if bill_to_text:
        customer_tax_id = _label_value(
            customer_source,
            ("Customer Tax ID", "VAT Number", "Tax ID", "购方税号"),
        )
        customer_contact_person = _clean_contact_name(_label_or_next_value(
            customer_source,
            ("Name", "Contact Person", "联系人"),
        ))
        customer_contact_email = _clean_contact_email(_label_or_next_value(
            customer_source,
            ("Email", "Contact Email", "客户邮箱"),
        ))
        customer_contact_phone = _clean_label_value(
            _label_or_next_value(
                customer_source,
                (
                    "Contact#",
                    "Contact No",
                    "Contact Number",
                    "Phone",
                    "Telephone",
                    "Mobile",
                    "电话",
                ),
            )
        )
        customer_address = (
            _customer_address_from_bill_to(text)
            or _multiline_label_value(
                customer_source,
                ("Address", "Customer Address", "客户地址"),
                ("Contact", "Contact#", "Email", "PO#", "Currency"),
            )
        )
    else:
        customer_contact_person = _clean_contact_name(
            receipt_details.get("contact_person", "")
        )
        customer_contact_email = _clean_contact_email(
            receipt_details.get("contact_email", "")
        )
        customer_address = receipt_details.get("customer_address", "")
        if document_kind == "delivery_note":
            customer_contact_person = _clean_contact_name(
                _label_or_next_value(
                    text,
                    ("Name", "Contact Person", "联系人"),
                )
            )
            customer_contact_email = _clean_contact_email(
                _label_or_next_value(
                    text,
                    ("Email", "Contact Email", "客户邮箱"),
                )
            )
            customer_address = _multiline_label_value(
                text,
                ("Address", "Customer Address", "客户地址"),
                ("Email", "Contact", "PO#"),
            )
    summary_contact = _summary_contact_fields(text)
    contact_person = _clean_contact_name(
        summary_contact.get("contact_person", "")
    )
    contact_email = _clean_contact_email(
        summary_contact.get("contact_email", "")
    )
    if contact_person and not contact_email:
        contact_email = _clean_contact_email(_remittance_instruction(text))
    if contact_person and not contact_email:
        contact_email = _summary_contact_fallback_email(text)
    contact_email = _reconciled_contact_email(text, contact_email)
    seller_fields = _seller_fields(text)
    bank_fields = _bank_fields(text)
    signatory_fields = _signatory_fields(text)
    notes = _multiline_label_value(
        text,
        ("Notes",),
        ("Additional Notes", "Additional Notes & Disclaimers", "Remarks"),
    )
    additional_notes = _additional_notes_value(text)
    remarks = _multiline_label_value(
        text,
        ("Remarks",),
        ("Account Name",),
    )
    region = _label_value(text, ("Region", "地区", "区域"))
    sales_owner = _label_value(
        text,
        ("Salesperson", "Sales Person", "销售人员", "业务员"),
    )
    tax_rate_value = _label_value(text, ("Tax Rate", "税率"))
    if not tax_rate_value:
        vat_match = re.search(
            r"(?:^|\n)\s*VAT\s*[:：]\s*"
            r"([0-9]{1,3}(?:\.[0-9]{1,4})?%?)",
            text,
            re.IGNORECASE,
        )
        tax_rate_value = vat_match.group(1) if vat_match else ""
    tax_rate = _parse_amount(tax_rate_value.rstrip("%"))
    subtotal = _amount_by_labels(
        text,
        ("Subtotal", "Amount Before Tax", "未税金额"),
        currency,
    )
    tax_amount = _amount_by_labels(
        text,
        ("Tax Amount", "VAT Amount", "税额"),
        currency,
    )
    total = _amount_by_labels(
        text,
        (
            "Grand Total",
            "Total Amount",
            "Amount due",
            "Total",
            "Amount paid",
            "Amount of tax withheld",
            "价税合计",
            "应付金额",
            "合计",
            "总额",
        ),
        currency,
    )
    if document_kind == "refund":
        refund_match = re.search(
            r"([^\n]*?[\d,]+(?:\.\d+)?)\s+refunded\s+on\b",
            text,
            re.IGNORECASE,
        )
        if refund_match:
            values = _money_values(refund_match.group(1))
            if values:
                total = -abs(values[-1][0])
    invoice = ParsedInvoice(
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=currency,
        seller_name=seller_name,
        seller_tax_id=seller_fields["seller_tax_id"],
        customer_name=customer_name,
        customer_tax_id=customer_tax_id,
        customer_address=customer_address,
        customer_contact_person=customer_contact_person,
        customer_contact_email=customer_contact_email,
        customer_contact_phone=customer_contact_phone,
        contact_person=contact_person,
        contact_email=contact_email,
        seller_address=seller_fields["seller_address"],
        seller_website=seller_fields["seller_website"],
        seller_email=seller_fields["seller_email"],
        notes=notes,
        additional_notes=additional_notes,
        remarks=remarks,
        bank_account_name=bank_fields["account_name"],
        bank_name=bank_fields["bank_name"],
        bank_address=bank_fields["bank_address"],
        bank_account_number=bank_fields["account_number"],
        bank_code=bank_fields["bank_code"],
        bank_branch_code=bank_fields["branch_code"],
        bank_swift_code=bank_fields["swift_code"],
        remittance_instruction=_remittance_instruction(text),
        signatory_name=signatory_fields["name"],
        signatory_title=signatory_fields["title"],
        purchase_order_no=_purchase_order_number(text),
        payment_terms=_payment_terms(text),
        region=region,
        sales_owner=sales_owner,
        tax_rate=tax_rate,
        subtotal_amount=subtotal,
        tax_amount=tax_amount,
        total_amount=total,
        items=_parse_items(text),
    )
    confidence_fields = {
        field: 1.0
        for field, value in {
            "invoice_no": invoice_no,
            "invoice_date": invoice_date,
            "customer_name": customer_name,
            "total_amount": total,
        }.items()
        if value not in ("", None, Decimal("0"))
    }
    warnings = [classification_warning] if classification_warning else []
    if not invoice.items:
        warnings.append(
            {
                "field": "items",
                "code": "items_not_detected",
                "detail": "No tabular invoice lines were detected.",
            }
        )
    return ParsedInvoiceDocumentData(
        invoice=invoice,
        document_kind=document_kind,
        field_confidence=confidence_fields,
        validation_warnings=warnings,
        confidence=Decimal("0.8") if confidence_fields else Decimal("0"),
    )
