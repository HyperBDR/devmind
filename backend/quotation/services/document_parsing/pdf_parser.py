from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from core.pdf_text import extract_pdf_text, pymupdf

from quotation.services.document_parsing.business_fields import (
    EXPIRE_DATE_LABELS,
    PRODUCT_LINE_LABELS,
    QUOTE_DATE_LABELS,
    QUOTE_NO_LABELS,
    REMARKS_LABELS,
    SECTION_ALIASES,
    explicit_product_line,
    find_issuer_email,
    known_product_line,
    normalize_currency_code,
    normalize_contact_email,
    normalize_contact_name,
    normalize_section_name,
    split_salesperson_after_email,
    strip_repeated_field_label,
)
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
PARSER_VERSION = "2.48.0"
_CURRENCY_TOKEN = r"(?:MYR|US\$|HK\$|RM|USD|HKD|CNY|RMB|EUR|GBP|[$¥￥€£])"


class QuotationPdfParseError(ValueError):
    """Raised when a text PDF cannot be interpreted safely."""


def _extract_text_pypdf(path: Path) -> str:
    try:
        return extract_pdf_text(path, prefer_pymupdf=False)
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
        return extract_pdf_text(path, prefer_pymupdf=True)
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
                r"\s+(?:Quote\s+No\.?|Quotation\s+No\.?|"
                r"Quote\s+Valid\s+Till|Valid\s+Till|Valid\s+Until|"
                r"Ship\s+to|Bill\s+to|Date)\s*:",
                match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return value.strip()
    return ""


def _line_value_aliases(lines: list[str], labels: tuple[str, ...]) -> str:
    for label in labels:
        value = _line_value(lines, label)
        if value:
            return value
    return ""


def _product_line(
    lines: list[str],
    items: list[ParsedQuotationItem],
) -> tuple[str, str]:
    explicit = _line_value_aliases(lines, PRODUCT_LINE_LABELS)
    if explicit:
        return explicit_product_line(explicit)
    for item in items:
        name, prefix = known_product_line(
            item.name or item.description or ""
        )
        if name:
            return name, prefix
    for line in lines:
        name, prefix = known_product_line(line)
        if name:
            return name, prefix
    return "", ""


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
            ("name", "Contact"),
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
        "sales person": "issuer_contact_name",
        "salesperson": "issuer_contact_name",
        "sales representative": "issuer_contact_name",
        "prepared by": "issuer_contact_name",
        "account manager": "issuer_contact_name",
        "email": "issuer_contact_email",
        "job title": "issuer_contact_title",
        "position": "issuer_contact_title",
        "title": "issuer_contact_title",
        "project": "project_name",
        "payment terms": "payment_terms",
        "currency": "currency",
    }
    issuer_headers = {
        "account manager",
        "contact person",
        "prepared by",
        "sales person",
        "sales representative",
        "salesperson",
    }
    for index, line in enumerate(lines[:-1]):
        cells = [cell.lower() for cell in _split_row(line)]
        lower_line = line.lower()
        has_issuer_header = any(
            header in lower_line for header in issuer_headers
        )
        if "project" not in lower_line or not (
            has_issuer_header or "email" in lower_line
        ):
            continue
        values = _split_row(lines[index + 1])
        result = {}
        for column, header in enumerate(cells):
            key = headers.get(header)
            if key and column < len(values):
                result[key] = values[column]
        if len(result) >= 3:
            email = result.get("issuer_contact_email", "")
            repaired = find_issuer_email(email)
            if repaired:
                result["issuer_contact_email"] = repaired[0]
            return result
        value_line = lines[index + 1]
        email_span = find_issuer_email(value_line)
        if email_span is None:
            continue
        email, email_start, email_end = email_span
        issuer_name = value_line[:email_start].strip()
        trailing = value_line[email_end:].strip().split()
        if not issuer_name:
            issuer_name, trailing = split_salesperson_after_email(
                email,
                trailing,
            )
        if len(trailing) < 1:
            continue
        currency = ""
        if "currency" in lower_line:
            currency = trailing.pop()
        payment_terms = ""
        if trailing:
            payment_match = re.fullmatch(
                r"(?:NET\s*\d+|CIA|MIXED)",
                trailing[-1],
                flags=re.IGNORECASE,
            )
            if payment_match:
                raw_payment = trailing.pop()
                net_match = re.fullmatch(
                    r"NET\s*(\d+)",
                    raw_payment,
                    flags=re.IGNORECASE,
                )
                payment_terms = (
                    f"NET {net_match.group(1)}"
                    if net_match
                    else raw_payment.upper()
                )
        if not payment_terms and len(trailing) >= 2:
            if (
                trailing[-2].upper() == "NET"
                and trailing[-1].isdigit()
            ):
                payment_terms = " ".join(trailing[-2:])
                trailing = trailing[:-2]
        if not trailing or not issuer_name:
            continue
        result.update(
            {
                "issuer_contact_name": issuer_name,
                "issuer_contact_email": email,
                "project_name": " ".join(trailing),
            }
        )
        if payment_terms:
            result["payment_terms"] = payment_terms
        if currency:
            result["currency"] = currency
        return result
    return {}


def _valid_issuer_name(
    value: str,
    excluded_names: set[str],
) -> bool:
    normalized = value.strip().casefold()
    return bool(
        normalized
        and "@" not in normalized
        and normalized not in excluded_names
        and not re.match(
            r"^(?:Email|E-mail|Title|Position)\s*:",
            value,
            flags=re.IGNORECASE,
        )
    )


def _valid_issuer_email(
    value: str,
    excluded_emails: set[str],
) -> bool:
    normalized = value.strip().casefold()
    return bool(
        normalized
        and normalized not in excluded_emails
        and re.fullmatch(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            value.strip(),
            flags=re.IGNORECASE,
        )
    )


def _valid_issuer_candidate(
    fields: dict[str, str],
    excluded_names: set[str],
    excluded_emails: set[str],
) -> bool:
    return _valid_issuer_name(
        fields.get("issuer_contact_name", ""),
        excluded_names,
    ) and _valid_issuer_email(
        fields.get("issuer_contact_email", ""),
        excluded_emails,
    )


def _signature_name(line: str) -> str:
    match = re.search(
        r"(?:^|\s)Name\s*:\s*(.+)$",
        line,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    name = re.sub(
        r"^(?:Name\s*:\s*)+",
        "",
        match.group(1).strip(),
        flags=re.IGNORECASE,
    )
    return re.split(
        r"\s+(?:Title|Email|E-mail)\s*:",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()


def _signature_title(lines: list[str]) -> str:
    for line in lines:
        match = re.search(
            r"(?:^|\s)(?:Job Title|Position|Title)\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        title = strip_repeated_field_label(
            match.group(1).strip(),
            "Job Title",
            "Position",
            "Title",
        )
        if re.match(
            r"^(?:Email|E-mail|Name)\s*:",
            title,
            flags=re.IGNORECASE,
        ):
            continue
        title = re.split(
            r"\s+(?:Email|E-mail|Name)\s*:",
            title,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        title = strip_repeated_field_label(
            title,
            "Job Title",
            "Position",
            "Title",
        )
        if title and "@" not in title:
            return title
    return ""


def _issuer_signature_fields(
    lines: list[str],
    *,
    excluded_names: set[str],
    excluded_emails: set[str],
) -> dict[str, str]:
    """Recover a paired issuer contact from the document tail."""
    tail_size = max(12, len(lines) // 3)
    tail_start = max(0, len(lines) - tail_size)
    for index in range(len(lines) - 1, tail_start - 1, -1):
        email = ""
        labeled = re.search(
            r"(?:^|[\s:])(?:Email|E-mail)\s*:\s*(.*)$",
            lines[index],
            flags=re.IGNORECASE,
        )
        if labeled is not None:
            found = find_issuer_email(labeled.group(1))
            if found:
                email = found[0]
        if (
            not email
            and index > 0
            and re.search(
                r"(?:Email|E-mail)\s*:\s*$",
                lines[index - 1],
                flags=re.IGNORECASE,
            )
        ):
            found = find_issuer_email(lines[index])
            if found:
                email = found[0]
        if not email.casefold().endswith("@oneprocloud.com"):
            continue
        window_start = max(tail_start, index - 4)
        window_end = min(len(lines), index + 2)
        window = lines[window_start:window_end]
        for line in reversed(window):
            candidate = {
                "issuer_contact_name": _signature_name(line),
                "issuer_contact_email": email,
            }
            if not _valid_issuer_candidate(
                candidate,
                excluded_names,
                excluded_emails,
            ):
                continue
            title = _signature_title(window)
            if title:
                candidate["issuer_contact_title"] = title
            return candidate
    return {}


def _select_issuer_fields(
    project: dict[str, str],
    signature: dict[str, str],
    excluded_names: set[str],
    excluded_emails: set[str],
) -> dict[str, str]:
    if _valid_issuer_candidate(
        project,
        excluded_names,
        excluded_emails,
    ):
        result = dict(project)
        if (
            not result.get("issuer_contact_title")
            and signature.get("issuer_contact_email", "").casefold()
            == result.get("issuer_contact_email", "").casefold()
        ):
            result["issuer_contact_title"] = signature.get(
                "issuer_contact_title",
                "",
            )
        return result
    if _valid_issuer_candidate(
        signature,
        excluded_names,
        excluded_emails,
    ):
        return signature
    return {}


def _parse_currency_item_line(
    line: str,
    pending_description: str,
) -> ParsedQuotationItem | None:
    currency_matches = list(
        re.finditer(
            rf"{_CURRENCY_TOKEN}\s*([\d,]+(?:\.\d+)?)",
            line,
            flags=re.IGNORECASE,
        )
    )
    trailing_tilde = line.find("~", currency_matches[0].start()) \
        if currency_matches else -1
    if trailing_tilde >= 0:
        line = line[:trailing_tilde].rstrip()
        currency_matches = list(
            re.finditer(
                rf"{_CURRENCY_TOKEN}\s*([\d,]+(?:\.\d+)?)",
                line,
                flags=re.IGNORECASE,
            )
        )
    if len(currency_matches) >= 5:
        extended_match = currency_matches[-1]
        if "~" in line[currency_matches[-1].start() - 2:]:
            extended_match = currency_matches[-2]
        prefix = line[: currency_matches[0].start()].strip().split()
        numeric_indexes = [
            index
            for index, token in enumerate(prefix)
            if re.fullmatch(r"[\d,.]+", token)
        ]
        if not numeric_indexes:
            return None
        qty_index = numeric_indexes[-1]
        item_index = (
            numeric_indexes[0]
            if len(numeric_indexes) > 1
            else None
        )
        description = _clean_item_description(
            " ".join(
                token
                for index, token in enumerate(prefix)
                if index not in {item_index, qty_index}
            )
        )
        if pending_description:
            description = "\n".join(
                value
                for value in (
                    _clean_item_description(pending_description),
                    description,
                )
                if value
            )
        if not description:
            return None
        line_no = (
            int(_decimal(prefix[item_index]))
            if item_index is not None
            else 0
        )
        return ParsedQuotationItem(
            line_no=line_no,
            type="",
            description=description,
            qty=_decimal(prefix[qty_index]),
            list_price=_decimal(currency_matches[0].group(1)),
            discount_percent=Decimal("0"),
            net_unit_price=_decimal(currency_matches[1].group(1)),
            extended_price=_decimal(extended_match.group(1)),
        )
    parts = re.split(rf"\s*{_CURRENCY_TOKEN}\s*", line)
    if len(parts) not in {3, 4, 5}:
        return None
    prefix = parts[0].strip().split()
    if not prefix:
        return None
    price_fields = parts[1].strip().split()
    if not price_fields:
        return None
    extended_part = parts[-1].strip()
    extended_match = re.match(
        r"(?:\([\d,]+(?:\.\d+)?\)|-?[\d,]+(?:\.\d+)?)",
        extended_part,
    )
    if extended_match is None:
        return None
    numeric_indexes = [
        index
        for index, token in enumerate(prefix)
        if re.fullmatch(r"[\d,.]+", token)
    ]
    if not numeric_indexes:
        return None
    if len(numeric_indexes) == 1 and numeric_indexes[0] == 0:
        item_index = 0
        qty_index = None
        qty = Decimal("1")
    else:
        qty_index = numeric_indexes[-1]
        qty = _decimal(prefix[qty_index])
        item_index = (
            numeric_indexes[0]
            if numeric_indexes[0] < qty_index
            else None
        )
    description_tokens = [
        token
        for index, token in enumerate(prefix)
        if index not in {qty_index, item_index}
    ]
    raw_description = _clean_item_description(
        " ".join(description_tokens).strip()
    )
    is_bullet = raw_description.lstrip().startswith(("•", "·", "-", "*"))
    description = raw_description.lstrip("•·-* ").strip()
    if is_bullet and description:
        description = f"• {description}"
    if pending_description:
        description = "\n".join(
            value
            for value in (
                _clean_item_description(pending_description.strip()),
                description,
            )
            if value
        )
    trailing_text = extended_part[extended_match.end() :].strip()
    if trailing_text:
        description = f"{description}\n{trailing_text}"
    if not description:
        return None
    if len(parts) == 3:
        list_price = _decimal(price_fields[0])
        discount_percent = Decimal("0")
        net_unit_price = list_price
    else:
        list_price = _decimal(price_fields[0])
        if len(price_fields) == 1 and len(parts) == 4:
            discount_percent = Decimal("0")
        elif len(price_fields) >= 2:
            discount_percent = _decimal(price_fields[-1])
        else:
            return None
        net_unit_price = _decimal(parts[2])
    return ParsedQuotationItem(
        line_no=(
            int(_decimal(prefix[item_index]))
            if item_index is not None
            else 0
        ),
        type="",
        description=description,
        qty=qty,
        list_price=list_price,
        discount_percent=discount_percent,
        net_unit_price=net_unit_price,
        extended_price=_decimal(extended_match.group(0)),
    )


def _clean_item_description(value: str) -> str:
    """Remove table-unit fragments accidentally emitted by PDF extraction."""
    value = re.sub(r"^\s*\(%\)\s*", "", value)
    value = re.sub(
        r"\((?:ea|qty|myr|hk\$?|hkd|rm|usd|cny|rmb|eur|gbp|[$¥￥€£])\)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s{2,}", " ", value).strip()


def _parse_item_line(line: str) -> ParsedQuotationItem | None:
    cells = _split_row(line)
    if len(cells) >= 7 and re.fullmatch(r"\d+(?:\.\d+)?", cells[0].strip()):
        return ParsedQuotationItem(
            line_no=int(_decimal(cells[0])),
            type="",
            description=_clean_item_description(cells[1]),
            qty=_decimal(cells[2]),
            list_price=_decimal(cells[3]),
            discount_percent=_decimal(cells[4]),
            net_unit_price=_decimal(cells[5]),
            extended_price=_decimal(cells[6]),
        )
    match = re.match(
        r"^(\d+)\s+(.+?)\s+([0-9.,]+)\s+"
        rf"({_CURRENCY_TOKEN}?[0-9.,]+)\s+"
        r"([0-9.]+%?)\s+"
        rf"({_CURRENCY_TOKEN}?[0-9.,]+)\s+"
        rf"({_CURRENCY_TOKEN}?[0-9.,]+)$",
        line,
    )
    if not match:
        return None
    return ParsedQuotationItem(
        line_no=int(match.group(1)),
        type="",
        description=_clean_item_description(match.group(2).strip()),
        qty=_decimal(match.group(3)),
        list_price=_decimal(match.group(4)),
        discount_percent=_decimal(match.group(5)),
        net_unit_price=_decimal(match.group(6)),
        extended_price=_decimal(match.group(7)),
    )


def _unsectioned_item_lines(
    lines: list[str],
) -> list[ParsedQuotationItem]:
    """Parse row-oriented tables that do not have section headings."""
    items = []
    pending_description = ""
    in_table = False
    current_type = ""
    for line in lines:
        lower = line.casefold()
        normalized = normalize_section_name(line)
        if normalized in SECTION_ALIASES["Software"]:
            current_type = "Software"
        elif normalized in SECTION_ALIASES["Others"]:
            current_type = "Other"
        if (
            "item" in lower and "description" in lower
        ) or "product details" in lower:
            in_table = True
            pending_description = ""
            continue
        if not in_table:
            continue
        if "subtotal" in lower:
            in_table = False
            continue
        marker_count = len(
            re.findall(_CURRENCY_TOKEN, line, flags=re.IGNORECASE)
        )
        if marker_count >= 2 and re.match(
            r"^\d+(?:\.\d+)?\s",
            line,
        ):
            item = _parse_currency_item_line(
                line,
                pending_description,
            )
            if item is not None:
                item.line_no = len(items) + 1
                item.type = current_type or (
                    "Software" if not items else "Other"
                )
                items.append(item)
                pending_description = ""
                continue
        if items and line.startswith("~"):
            items[-1].description = (
                f"{items[-1].description}\n{line}"
            )
        elif (
            not re.match(r"^\d+\s", line)
            and not any(
                label in lower
                for label in (
                    "qty",
                    "list price",
                    "discount",
                    "extended price",
                )
            )
        ):
            pending_description = _clean_item_description(line)
    return items


def _line_items(
    lines: list[str], section: str, item_type: str
) -> list[ParsedQuotationItem]:
    section_aliases = SECTION_ALIASES.get(
        section,
        frozenset({normalize_section_name(section)}),
    )
    section_index = None
    for index, line in enumerate(lines):
        if normalize_section_name(line) in section_aliases:
            section_index = index
            break
    if section_index is None:
        return []
    items: list[ParsedQuotationItem] = []
    pending_description: list[str] = []
    current_item: ParsedQuotationItem | None = None
    after_item = False
    section_markers = {
        alias
        for aliases in SECTION_ALIASES.values()
        for alias in aliases
    }
    section_lines = lines[section_index + 1 :]
    for index, line in enumerate(section_lines):
        lower = normalize_section_name(line)
        if lower in section_markers and lower not in section_aliases:
            break
        if any(
            marker in lower
            for marker in (
                "total amount",
                "grand total",
                "vat amount",
                "tax amount",
                "vat charged",
                "digital service tax",
                "tax charged",
                "additional notes",
                "to indicate customer acceptance",
                "onepro cloud confidential",
            )
        ):
            break
        if "subtotal" in lower:
            continue
        if (
            current_item is not None
            and after_item
            and not re.search(_CURRENCY_TOKEN, line, flags=re.IGNORECASE)
            and (
                re.match(r"^\d+(?:\.\d+)?\s+", line)
                or (
                    index + 1 < len(section_lines)
                    and re.match(
                        r"^\d+(?:\.\d+)?\s+",
                        section_lines[index + 1],
                    )
                    and re.search(
                        _CURRENCY_TOKEN,
                        section_lines[index + 1],
                        flags=re.IGNORECASE,
                    )
                )
            )
        ):
            pending_description = [re.sub(r"^\d+\s+", "", line)]
            after_item = False
            continue
        item = _parse_item_line(line)
        if item is None:
            item = _parse_currency_item_line(
                line,
                "\n".join(pending_description),
            )
        if item is None:
            if re.fullmatch(
                r"\d+\s+(?:HK\$|RM|USD|[$¥￥€£])?\s*0+(?:\.0+)?",
                line.strip(),
                flags=re.IGNORECASE,
            ):
                continue
            header_fragment = re.fullmatch(
                r"[a-z]\s*\(%\)",
                line.strip(),
                flags=re.IGNORECASE,
            )
            if line.strip() in {"(%)", "%"}:
                continue
            if not any(
                label in lower
                for label in (
                    "item",
                    "description",
                    "qty",
                    "list price",
                    "discount",
                    "discoun",
                    "extended price",
                )
            ) and not header_fragment and not re.fullmatch(
                r"[()A-Z ]+", line
            ):
                if (
                    current_item is not None
                    and after_item
                    and not re.fullmatch(r"[\d.,\s]+", line.strip())
                ):
                    separator = "\n\n" if line.lstrip().startswith(
                        ("*", "~")
                    ) else "\n"
                    current_item.description = (
                        f"{current_item.description}"
                        f"{separator}{line.strip()}"
                    )
                else:
                    pending_description.append(
                        re.sub(r"^\d+\s+", "", line)
                    )
                    after_item = False
            continue
        if (
            item.qty == 0
            and item.list_price == 0
            and item.net_unit_price == 0
            and item.extended_price == 0
        ):
            current_item = None
            pending_description = []
            after_item = False
            continue
        item.type = item_type
        items.append(item)
        current_item = item
        pending_description = []
        after_item = True
    return items


def _amount_by_label(lines: list[str], label: str) -> Decimal:
    target = label.lower()
    for line in lines:
        if target in line.lower():
            value = line.split(":", 1)[-1] if ":" in line else line
            matches = re.findall(
                r"(?:HK\$|[$¥￥€£]|RM)?\s*([\d,]+(?:\.\d+)?)",
                value,
                flags=re.IGNORECASE,
            )
            if matches:
                return _decimal(matches[-1])
    return Decimal("0")


def _merge_optional_service_rows(
    items: list[ParsedQuotationItem], lines: list[str]
) -> None:
    """Keep optional service rows with the license table when one table is used.

    The source PDF can expose a visual table break as an ``Others`` marker
    even when the original document has one continuous item table.
    """
    software_subtotal = _amount_by_label(
        lines,
        "software subscription subtotal",
    )
    others_subtotal = _amount_by_label(lines, "others subtotal")
    if software_subtotal or others_subtotal:
        return
    software_items = [item for item in items if item.type == "Software"]
    other_items = [item for item in items if item.type == "Other"]
    if not software_items or not other_items:
        return
    if not any(
        token in software_items[0].description.casefold()
        for token in ("hyperbdr", "hypermotion")
    ):
        return
    if not all(
        "product service" in item.description.casefold()
        and "optional" in item.description.casefold()
        for item in other_items
    ):
        return
    for item in other_items:
        item.type = "Software"


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
            r"(.+?)\s+\(([0-9.]+)%\)\s*:?\s*"
            rf"{_CURRENCY_TOKEN}",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip(), Decimal(match.group(2))
        match = re.search(
            r"(.+?)\s+([0-9.]+)%\s*(?:VAT|Tax)?\s*$",
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
    targets = {label.lower().rstrip(":") for label in REMARKS_LABELS}
    marker_indexes = [
        index
        for index, line in enumerate(lines)
        if line.lower().rstrip(":") in targets
    ]
    if marker_indexes:
        start = marker_indexes[0] + 1
        values = []
        stop_markers = (
            "to indicate customer acceptance",
            "onepro cloud confidential",
            "prepared by",
            "signature",
        )
        for value in lines[start:]:
            normalized = value.casefold().strip()
            repeated_signature_field = re.match(
                r"^(?:name|title|position|email|e-mail)\s*:\s*"
                r"(?:name|title|position|email|e-mail)\s*:",
                normalized,
            )
            if (
                normalized == "t"
                or repeated_signature_field
                or any(normalized.startswith(marker) for marker in stop_markers)
            ):
                break
            values.append(value)
        return "\n".join(values).strip()
    return _line_value_aliases(lines, REMARKS_LABELS)


def parse_quotation_pdf_text(text: str) -> ParsedDocumentData:
    lines = _lines(text)
    if not lines:
        raise QuotationPdfParseError("PDF contains no extractable text")

    ship_to = _section_fields(lines, "Ship to")
    bill_to = _section_fields(lines, "Bill to")
    project = _project_fields(lines)
    quote_date_value = _line_value_aliases(lines, QUOTE_DATE_LABELS)
    if not quote_date_value:
        quote_date_value = next(
            (
                line for line in lines[:8]
                if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", line)
            ),
            "",
        )
    quote_no_value = _line_value_aliases(lines, QUOTE_NO_LABELS)
    if not quote_no_value:
        match = re.search(r"\bShip\s+to\s+([A-Za-z0-9_-]+)", " ".join(lines[:8]), re.I)
        quote_no_value = match.group(1) if match else ""
    expire_value = _line_value_aliases(lines, EXPIRE_DATE_LABELS)
    if not expire_value:
        for line in lines[:8]:
            match = re.search(
                r"Company\s*:\s*.+?\s+"
                r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})$",
                line,
                re.I,
            )
            if match:
                expire_value = match.group(1)
                break
    for address in (ship_to, bill_to):
        address["company"] = re.sub(
            r"\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$", "",
            address.get("company", ""),
        ).strip()
    excluded_names = {
        value.strip().casefold()
        for value in (ship_to.get("name", ""), bill_to.get("name", ""))
        if value.strip()
    }
    excluded_emails = {
        value.strip().casefold()
        for value in (ship_to.get("email", ""), bill_to.get("email", ""))
        if value.strip()
    }
    signature = _issuer_signature_fields(
        lines,
        excluded_names=excluded_names,
        excluded_emails=excluded_emails,
    )
    issuer = _select_issuer_fields(
        project,
        signature,
        excluded_names,
        excluded_emails,
    )
    items = []
    for alias in SECTION_ALIASES["Software"]:
        items.extend(_line_items(lines, alias, "Software"))
    for alias in SECTION_ALIASES["Others"]:
        items.extend(_line_items(lines, alias, "Other"))
    unsectioned_items = _unsectioned_item_lines(lines)
    if len(unsectioned_items) > len(items):
        items = unsectioned_items
    _merge_optional_service_rows(items, lines)
    for line_no, item in enumerate(items, start=1):
        item.line_no = line_no
    product_line_name, product_line = _product_line(lines, items)

    tax_label, vat_rate = _tax_details(lines)
    total_amount = _amount_by_label(lines, "total amount")
    subtotal_before_vat = _amount_by_label(lines, "subtotal before")
    item_total = sum(
        (item.extended_price for item in items),
        Decimal("0"),
    )
    if not subtotal_before_vat:
        subtotal_lines = [
            line for line in lines if "subtotal" in line.casefold()
        ]
        generic_subtotal = (
            _amount_by_label(lines, "subtotal")
            if len(subtotal_lines) == 1
            else Decimal("0")
        )
        subtotal_before_vat = generic_subtotal or item_total or total_amount
    grand_total = (
        _amount_by_label(lines, "grand total")
        or _amount_by_label(lines, "final amount")
    )
    if not subtotal_before_vat:
        subtotal_before_vat = total_amount
    if not grand_total:
        grand_total = total_amount or subtotal_before_vat
    vat_amount = (
        _amount_by_label(lines, "amount (")
        or _amount_by_label(lines, "vat charged")
        or _amount_by_label(lines, "tax charged")
    )
    if not vat_amount and vat_rate:
        vat_amount = _amount_by_label(lines, tax_label)
    deduction_amount = _amount_by_label(lines, "special offer")
    tax_calculation_mode = "add"
    has_charge = any(
        re.search(r"\b(?:tax|vat|markup)\b", line, re.IGNORECASE)
        and re.search(r"\d+(?:\.\d+)?%", line)
        for line in lines
    )
    if not has_charge and abs(item_total - grand_total) <= Decimal("0.02"):
        subtotal_before_vat = item_total
    total_difference = grand_total + deduction_amount - subtotal_before_vat
    if (
        has_charge
        and not vat_amount
        and abs(total_difference) > Decimal("0.02")
    ):
        vat_amount = abs(total_difference)
        tax_calculation_mode = (
            "add" if total_difference > 0 else "subtract"
        )
    has_extra_charge = any(
        "withold" in line.casefold()
        or "withhold" in line.casefold()
        or "markup" in line.casefold()
        for line in lines
    )
    if has_extra_charge and abs(total_difference) > Decimal("0.02"):
        vat_amount = abs(total_difference)
    if (
        vat_amount
        and abs(
            subtotal_before_vat - vat_amount
            - deduction_amount - grand_total
        ) <= Decimal("0.02")
    ):
        tax_calculation_mode = "subtract"
    source_totals = {
        "software_subtotal": str(
            _amount_by_label(lines, "software subscription subtotal")
            or _amount_by_label(lines, "subscription items subtotal")
            or _amount_by_label(lines, "subscriptions items subtotal")
            or _amount_by_label(lines, "monthly subscriptions subtotal")
            or _amount_by_label(lines, "yearly subscriptions subtotal")
            or sum(
                (item.extended_price for item in items
                 if item.type == "Software"),
                Decimal("0"),
            )
        ),
        "others_subtotal": str(
            _amount_by_label(lines, "others subtotal")
            or _amount_by_label(lines, "one-time items subtotal")
            or _amount_by_label(lines, "one time items subtotal")
            or _amount_by_label(lines, "optional items subtotal")
            or _amount_by_label(lines, "professional service subtotal")
            or sum(
                (item.extended_price for item in items
                 if item.type == "Other"),
                Decimal("0"),
            )
        ),
        "subtotal_before_vat": str(subtotal_before_vat),
        "vat_amount": str(vat_amount),
        "grand_total": str(grand_total),
    }
    payment_terms = project.get("payment_terms", "")
    quotation = ParsedQuotation(
        quote_no=quote_no_value,
        product_line=product_line,
        product_line_name=product_line_name,
        project_name=project.get("project_name", ""),
        currency=normalize_currency_code(project.get("currency", "")),
        payment_term_option=_payment_term_option(payment_terms),
        payment_terms=payment_terms,
        quote_date=_date(quote_date_value),
        expire_date=_date(expire_value),
        tax_label=tax_label,
        vat_rate=vat_rate,
        tax_calculation_mode=tax_calculation_mode,
        deduction_amount=deduction_amount,
        remarks_disclaimer=_remarks(lines),
        issuer_company_name=_issuer_company(lines),
        issuer_contact_name=normalize_contact_name(
            issuer.get("issuer_contact_name", "")
        ),
        issuer_contact_email=normalize_contact_email(
            issuer.get("issuer_contact_email", "")
        ),
        issuer_contact_title=strip_repeated_field_label(
            issuer.get("issuer_contact_title", ""),
            "Job Title",
            "Position",
            "Title",
        ),
        client_company=ship_to.get("company", ""),
        contact_person=normalize_contact_name(ship_to.get("name", "")),
        email=normalize_contact_email(ship_to.get("email", "")),
        billing_company=bill_to.get("company", ""),
        billing_contact=normalize_contact_name(bill_to.get("name", "")),
        billing_email=normalize_contact_email(bill_to.get("email", "")),
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
        str((sum(field_confidence.values()) + field_confidence["items"] * 3)
            / (len(field_confidence) + 3))
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
