from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

try:
    import pymupdf
except ImportError:
    pymupdf = None

from quotation.services.document_parsing.excel_parser import (
    _date,
    _decimal,
    _payment_term_option,
    _validate,
)
from quotation.services.document_parsing.schemas import (
    ParsedDocumentData,
    ParsedQuotation,
    ParsedQuotationItem,
)

PARSER_NAME = "devmind_standard_pdf"
PARSER_VERSION = "2.4.0"


class QuotationPdfParseError(ValueError):
    """Raised when a text PDF cannot be interpreted safely."""


def _extract_text_pypdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except TimeoutError:
        raise
    except Exception as exc:
        raise QuotationPdfParseError(
            f"Unable to read PDF text: {type(exc).__name__}: {exc}"
        ) from exc


def _extract_text_pymupdf(path: Path) -> str:
    if pymupdf is None:
        raise QuotationPdfParseError("PyMuPDF is not installed")
    try:
        with pymupdf.open(path) as document:
            return "\n".join(
                page.get_text("text", sort=True) for page in document
            )
    except TimeoutError:
        raise
    except Exception as exc:
        raise QuotationPdfParseError(
            f"Unable to read PDF text with PyMuPDF: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _extract_text(path: Path) -> str:
    """Use the fast native parser and retain pypdf as a safe fallback."""
    if pymupdf is not None:
        try:
            text = _extract_text_pymupdf(path)
            if text.strip():
                return text
        except QuotationPdfParseError:
            pass
    return _extract_text_pypdf(path)


def _lines(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line and line.strip()
    ]


def _line_value(lines: list[str], label: str) -> str:
    pattern = re.compile(
        rf"(?:^|\s){re.escape(label.rstrip(':'))}\s*:\s*(.+)$",
        flags=re.IGNORECASE,
    )
    for line in lines:
        match = pattern.search(line)
        if match:
            value = re.split(
                r"\s+(?:Quote\s+No\.?|Quote\s+Valid\s+Till|"
                r"Ship\s+to|Bill\s+to|Date)\s*:",
                match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return value.strip()
    return ""


def _section_fields(lines: list[str], start_label: str) -> dict[str, str]:
    start = None
    for index, line in enumerate(lines):
        normalized = line.lower().rstrip(":")
        target = start_label.lower().rstrip(":")
        if normalized == target or normalized.startswith(f"{target} "):
            start = index + 1
            break
    if start is None:
        return {}
    result: dict[str, str] = {}
    stop_labels = {"ship to", "bill to", "contact person", "software"}
    for line in lines[start : start + 10]:
        if line.lower().rstrip(":") in stop_labels:
            break
        for key, label in (
            ("company", "Company"),
            ("name", "Name"),
            ("email", "Email"),
        ):
            value = _line_value([line], label)
            if value and key not in result:
                result[key] = value
    return result


def _split_row(line: str) -> list[str]:
    if "|" in line:
        return [part.strip() for part in line.split("|")]
    return [part.strip() for part in re.split(r"\s{2,}", line) if part.strip()]


def _project_fields(lines: list[str]) -> dict[str, str]:
    headers = {
        "contact person": "issuer_contact_name",
        "email": "issuer_contact_email",
        "project": "project_name",
        "payment terms": "payment_terms",
        "currency": "currency",
    }
    for index, line in enumerate(lines[:-1]):
        cells = [cell.lower() for cell in _split_row(line)]
        lower_line = line.lower()
        if "project" not in lower_line or "currency" not in lower_line:
            continue
        values = _split_row(lines[index + 1])
        result = {}
        for column, header in enumerate(cells):
            key = headers.get(header)
            if key and column < len(values):
                result[key] = values[column]
        if len(result) >= 3:
            return result
        value_line = lines[index + 1]
        email_match = re.search(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            value_line,
            flags=re.IGNORECASE,
        )
        if email_match is None:
            return result
        issuer_name = value_line[: email_match.start()].strip()
        trailing = value_line[email_match.end() :].strip().split()
        if len(trailing) < 3:
            return result
        currency = trailing[-1]
        payment_start = len(trailing) - 2
        payment_terms = trailing[payment_start]
        if (
            payment_start >= 1
            and trailing[payment_start - 1].upper() == "NET"
        ):
            payment_start -= 1
            payment_terms = " ".join(trailing[payment_start:-1])
        result.update(
            {
                "issuer_contact_name": issuer_name,
                "issuer_contact_email": email_match.group(0),
                "project_name": " ".join(trailing[:payment_start]),
                "payment_terms": payment_terms,
                "currency": currency,
            }
        )
        return result
    return {}


def _parse_currency_item_line(
    line: str,
    pending_description: str,
) -> ParsedQuotationItem | None:
    parts = re.split(r"\s*[$¥€]\s*", line)
    if len(parts) != 4:
        return None
    prefix = parts[0].strip().split()
    if not prefix or not prefix[0].isdigit():
        return None
    price_discount = parts[1].strip().split()
    if len(price_discount) < 2:
        return None
    extended_match = re.match(r"[\d,. ()-]+", parts[3].strip())
    if extended_match is None:
        return None
    prefix_tail = prefix[1:]
    qty = Decimal("1")
    if prefix_tail and re.fullmatch(r"[\d,.]+", prefix_tail[-1]):
        qty = _decimal(prefix_tail.pop())
    description = " ".join(prefix_tail).strip() or pending_description
    if not description:
        return None
    return ParsedQuotationItem(
        line_no=int(prefix[0]),
        type="",
        description=description,
        qty=qty,
        list_price=_decimal(price_discount[0]),
        discount_percent=_decimal(price_discount[-1]),
        net_unit_price=_decimal(parts[2]),
        extended_price=_decimal(extended_match.group(0)),
    )


def _parse_item_line(line: str) -> ParsedQuotationItem | None:
    cells = _split_row(line)
    if len(cells) >= 7 and cells[0].strip().isdigit():
        return ParsedQuotationItem(
            line_no=int(cells[0]),
            type="",
            description=cells[1],
            qty=_decimal(cells[2]),
            list_price=_decimal(cells[3]),
            discount_percent=_decimal(cells[4]),
            net_unit_price=_decimal(cells[5]),
            extended_price=_decimal(cells[6]),
        )
    match = re.match(
        r"^(\d+)\s+(.+?)\s+([0-9.,]+)\s+([$¥€]?[0-9.,]+)\s+"
        r"([0-9.]+%?)\s+([$¥€]?[0-9.,]+)\s+([$¥€]?[0-9.,]+)$",
        line,
    )
    if not match:
        return None
    return ParsedQuotationItem(
        line_no=int(match.group(1)),
        type="",
        description=match.group(2).strip(),
        qty=_decimal(match.group(3)),
        list_price=_decimal(match.group(4)),
        discount_percent=_decimal(match.group(5)),
        net_unit_price=_decimal(match.group(6)),
        extended_price=_decimal(match.group(7)),
    )


def _line_items(
    lines: list[str], section: str, item_type: str
) -> list[ParsedQuotationItem]:
    section_index = None
    for index, line in enumerate(lines):
        if line.lower() == section.lower():
            section_index = index
            break
    if section_index is None:
        return []
    items: list[ParsedQuotationItem] = []
    pending_description = ""
    for line in lines[section_index + 1 :]:
        lower = line.lower()
        if "subtotal" in lower:
            break
        item = _parse_item_line(line)
        if item is None:
            item = _parse_currency_item_line(line, pending_description)
        if item is None:
            if not any(
                label in lower
                for label in (
                    "item",
                    "description",
                    "qty",
                    "list price",
                    "discount",
                    "extended price",
                )
            ) and not re.fullmatch(r"[()A-Z ]+", line):
                pending_description = line
            continue
        item.type = item_type
        items.append(item)
        pending_description = ""
    return items


def _amount_by_label(lines: list[str], label: str) -> Decimal:
    target = label.lower()
    for line in lines:
        if target in line.lower():
            value = line.split(":", 1)[-1] if ":" in line else line
            matches = re.findall(
                r"(?:[$¥€]|RM)?\s*([\d,]+(?:\.\d+)?)",
                value,
                flags=re.IGNORECASE,
            )
            if matches:
                return _decimal(matches[-1])
    return Decimal("0")


def _tax_details(lines: list[str]) -> tuple[str, Decimal]:
    for line in lines:
        match = re.search(
            r"(.+?)\s+Amount\s*\(([0-9.]+)%\)",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip(), Decimal(match.group(2))
        match = re.search(
            r"(.+?)\s+\(([0-9.]+)%\)\s+(?:[$¥€]|RM)",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip(), Decimal(match.group(2))
    return "VAT", Decimal("0")


def _issuer_company(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line.lower() == "quotation":
            for previous in reversed(lines[:index]):
                if previous:
                    return previous
    return "OnePro Cloud Limited"


def _remarks(lines: list[str]) -> str:
    for index, line in enumerate(lines[:-1]):
        if line.lower().rstrip(":") == "additional notes & disclaimers":
            return lines[index + 1]
    return ""


def parse_quotation_pdf_text(text: str) -> ParsedDocumentData:
    lines = _lines(text)
    if not lines:
        raise QuotationPdfParseError("PDF contains no extractable text")

    ship_to = _section_fields(lines, "Ship to")
    bill_to = _section_fields(lines, "Bill to")
    project = _project_fields(lines)
    items = _line_items(lines, "Software", "Software")
    items.extend(_line_items(lines, "Others", "Other"))
    for line_no, item in enumerate(items, start=1):
        item.line_no = line_no

    tax_label, vat_rate = _tax_details(lines)
    total_amount = _amount_by_label(lines, "total amount")
    subtotal_before_vat = _amount_by_label(lines, "subtotal before")
    if not subtotal_before_vat:
        subtotal_before_vat = total_amount or _amount_by_label(
            lines,
            "subtotal",
        )
    grand_total = _amount_by_label(lines, "grand total")
    if not subtotal_before_vat:
        subtotal_before_vat = total_amount
    if not grand_total:
        grand_total = total_amount
    vat_amount = _amount_by_label(lines, "amount (")
    if not vat_amount and vat_rate:
        vat_amount = _amount_by_label(lines, tax_label)
    source_totals = {
        "software_subtotal": str(
            _amount_by_label(lines, "software subscription subtotal")
        ),
        "others_subtotal": str(_amount_by_label(lines, "others subtotal")),
        "subtotal_before_vat": str(subtotal_before_vat),
        "vat_amount": str(vat_amount),
        "grand_total": str(grand_total),
    }
    payment_terms = project.get("payment_terms", "")
    quotation = ParsedQuotation(
        quote_no=_line_value(lines, "Quote No."),
        project_name=project.get("project_name", ""),
        currency=(
            project.get("currency", "USD").upper().split("/", 1)[0]
            or "USD"
        ),
        payment_term_option=_payment_term_option(payment_terms),
        payment_terms=payment_terms,
        quote_date=_date(_line_value(lines, "Date")),
        expire_date=_date(_line_value(lines, "Quote Valid Till")),
        tax_label=tax_label,
        vat_rate=vat_rate,
        remarks_disclaimer=_remarks(lines),
        issuer_company_name=_issuer_company(lines),
        issuer_contact_name=project.get("issuer_contact_name", ""),
        issuer_contact_email=project.get("issuer_contact_email", ""),
        issuer_contact_title=_line_value(lines, "Title"),
        client_company=ship_to.get("company", ""),
        contact_person=ship_to.get("name", ""),
        email=ship_to.get("email", ""),
        billing_company=bill_to.get("company", ""),
        billing_contact=bill_to.get("name", ""),
        billing_email=bill_to.get("email", ""),
        items=items,
    )
    errors, warnings = _validate(quotation, source_totals)
    confidence_fields = (
        "quote_no",
        "project_name",
        "client_company",
        "contact_person",
        "email",
        "quote_date",
        "expire_date",
        "issuer_contact_name",
        "issuer_contact_email",
        "payment_terms",
    )
    field_confidence = {
        field: 1.0 if getattr(quotation, field) else 0.0
        for field in confidence_fields
    }
    field_confidence["items"] = 1.0 if items else 0.0
    confidence = Decimal(
        str(sum(field_confidence.values()) / len(field_confidence))
    ).quantize(Decimal("0.0001"))
    return ParsedDocumentData(
        quotation=quotation,
        source_totals=source_totals,
        field_confidence=field_confidence,
        validation_errors=errors,
        validation_warnings=warnings,
        confidence=confidence,
    )


def parse_standard_quotation_pdf(path: Path) -> ParsedDocumentData:
    """Parse with PyMuPDF first and fall back when validation is incomplete."""
    candidates = []
    if pymupdf is not None:
        try:
            fast = parse_quotation_pdf_text(_extract_text_pymupdf(path))
            candidates.append(fast)
            if not fast.validation_errors and not fast.validation_warnings:
                return fast
        except QuotationPdfParseError:
            pass
    fallback = parse_quotation_pdf_text(_extract_text_pypdf(path))
    candidates.append(fallback)
    return max(
        candidates,
        key=lambda parsed: (
            parsed.confidence,
            -len(parsed.validation_errors),
            -len(parsed.validation_warnings),
        ),
    )
