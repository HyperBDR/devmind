"""Render the approved English Commercial Invoice as an A4 PDF."""

from __future__ import annotations

import base64
import binascii
import re
import textwrap
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError

ITEMS_PER_PAGE = 7
BACKEND_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = BACKEND_ROOT / "quotation" / "assets" / "onepro-logo.png"
FONT_DIR = BACKEND_ROOT / "invoice" / "assets" / "fonts"
# Built-in PDF fonts only cover Latin-1, so typographic quotes, dashes and
# the euro sign would print as "?". Embed Liberation Sans instead.
FONT_FILES = {
    "regular": ("libsans", "LiberationSans-Regular.ttf"),
    "bold": ("libsansb", "LiberationSans-Bold.ttf"),
    "italic": ("libsansi", "LiberationSans-Italic.ttf"),
    "bold_italic": ("libsansbi", "LiberationSans-BoldItalic.ttf"),
}
PAGE_BOTTOM = 800
ITEMS_TOP = 357
ITEMS_HEADER_HEIGHT = 18
BANK_ROW_HEIGHTS = (14, 14, 24, 14, 14, 14, 14)
BILL_TO_BOTTOM = 252
BILL_TO_TEXT_WIDTH = 231
SIGNATURE_PATTERN = re.compile(
    r"^data:image/(?P<format>png|jpeg);base64,(?P<data>[A-Za-z0-9+/=]+)$"
)
CURRENCY_PREFIXES = {
    "USD": "$",
    "CNY": "¥",
    "EUR": "€",
    "GBP": "£",
    "HKD": "HK$",
    "MYR": "RM",
}
BLACK = (0.09, 0.09, 0.09)
BORDER = (0.47, 0.47, 0.47)
GRAY = (0.54, 0.54, 0.54)
WHITE = (1, 1, 1)


class InvoicePdfRenderError(ValueError):
    """Raised when an invoice cannot be rendered safely."""


def validate_signature_data_url(value: str) -> str:
    """Validate a bounded PNG or JPEG signature data URL."""
    if not value:
        return ""
    match = SIGNATURE_PATTERN.fullmatch(value)
    if match is None:
        raise InvoicePdfRenderError("Signature must be a PNG or JPEG image.")
    try:
        content = base64.b64decode(match.group("data"), validate=True)
        with Image.open(BytesIO(content)) as image:
            expected = "JPEG" if match.group("format") == "jpeg" else "PNG"
            if image.format != expected:
                raise InvoicePdfRenderError(
                    "Signature image format does not match its data URL."
                )
            if image.width > 4096 or image.height > 4096:
                raise InvoicePdfRenderError("Signature image is too large.")
            image.verify()
    except InvoicePdfRenderError:
        raise
    except (
        binascii.Error,
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise InvoicePdfRenderError(
            "Signature must contain a valid PNG or JPEG image."
        ) from exc
    return value


def _signature_bytes(value: str) -> bytes | None:
    value = validate_signature_data_url(value)
    if not value:
        return None
    return base64.b64decode(value.split(",", 1)[1], validate=True)


def _plain(value, fallback: str = "—") -> str:
    return str(value or "").strip() or fallback


def _date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def _quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _amount(value: Decimal, currency: str) -> str:
    prefix = CURRENCY_PREFIXES.get(currency, currency)
    return f"{prefix} {value:,.2f}"


def _font(*, bold: bool = False, italic: bool = False) -> tuple[str, str]:
    """Return the embedded font name and file for a text style."""
    style = (
        "bold_italic"
        if bold and italic
        else "bold" if bold else "italic" if italic else "regular"
    )
    fontname, filename = FONT_FILES[style]
    return fontname, str(FONT_DIR / filename)


@lru_cache(maxsize=None)
def _measuring_font(bold: bool = False) -> pymupdf.Font:
    return pymupdf.Font(fontfile=_font(bold=bold)[1])


def _text_width(text: str, size: float, *, bold: bool = False) -> float:
    return _measuring_font(bold).text_length(text, fontsize=size)


def _line_count(value, width: float, size: float) -> int:
    """Estimate wrapped lines for text drawn in a box of the given width."""
    count = 0
    for paragraph in _plain(value, "").splitlines() or [""]:
        lines = 1
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and _text_width(candidate, size) > width:
                lines += 1
                current = word
            else:
                current = candidate
        count += lines
    return count


def _text(
    page,
    rect,
    value,
    *,
    size: float = 8,
    minimum_size: float = 6,
    bold: bool = False,
    italic: bool = False,
    align: int = pymupdf.TEXT_ALIGN_LEFT,
    color=BLACK,
) -> None:
    fontname, fontfile = _font(bold=bold, italic=italic)
    text = _plain(value, "")
    current_size = size
    while current_size >= minimum_size:
        remaining = page.insert_textbox(
            rect,
            text,
            fontname=fontname,
            fontfile=fontfile,
            fontsize=current_size,
            lineheight=1.15,
            color=color,
            align=align,
        )
        if remaining >= 0:
            return
        current_size -= 0.5
    raise InvoicePdfRenderError(
        "Invoice content is too long for the approved A4 template."
    )


def _filled_cell(page, rect, value, *, size: float = 8) -> None:
    page.draw_rect(rect, color=BORDER, fill=GRAY, width=0.6)
    _text(
        page,
        pymupdf.Rect(rect.x0 + 2, rect.y0 + 3, rect.x1 - 2, rect.y1 - 2),
        value,
        size=size,
        minimum_size=6,
        align=pymupdf.TEXT_ALIGN_CENTER,
        color=WHITE,
    )


def _bordered_cell(
    page,
    rect,
    value,
    *,
    size: float = 7.5,
    align: int = pymupdf.TEXT_ALIGN_LEFT,
) -> None:
    page.draw_rect(rect, color=BORDER, width=0.6)
    _text(
        page,
        pymupdf.Rect(rect.x0 + 4, rect.y0 + 3, rect.x1 - 4, rect.y1 - 2),
        value,
        size=size,
        minimum_size=6,
        align=align,
    )


def _underlined_text(page, x: float, y: float, width: float, value) -> None:
    text = _plain(value, "")
    _text(
        page,
        pymupdf.Rect(x, y, x + width, y + 13),
        text,
        size=7.5,
    )
    if text:
        text_width = _text_width(text, 7.5)
        page.draw_line(
            (x, y + 10),
            (x + min(text_width, width), y + 10),
            color=BLACK,
            width=0.4,
        )


def _is_proforma(invoice) -> bool:
    return getattr(invoice, "document_kind", "") == "proforma_invoice"


def _document_title(invoice) -> str:
    return (
        "Proforma Invoice" if _is_proforma(invoice) else "Commercial Invoice"
    )


def _number_label(invoice) -> str:
    return (
        "Proforma Invoice Number"
        if _is_proforma(invoice)
        else "Invoice Number"
    )


def _draw_header(page, invoice) -> None:
    page.insert_image(
        pymupdf.Rect(38, 50, 155, 70),
        filename=str(LOGO_PATH),
        keep_proportion=True,
    )
    _text(
        page,
        pymupdf.Rect(175, 40, 455, 64),
        _plain(invoice.seller_name, "OnePro Cloud Limited"),
        size=14,
        minimum_size=10,
        align=pymupdf.TEXT_ALIGN_CENTER,
    )
    _text(
        page,
        pymupdf.Rect(210, 67, 425, 87),
        _document_title(invoice),
        size=12.5,
        minimum_size=10,
        align=pymupdf.TEXT_ALIGN_CENTER,
    )
    page.draw_line((222, 86), (413, 86), color=BLACK, width=0.7)

    _text(
        page,
        pymupdf.Rect(38, 109, 335, 126),
        _plain(invoice.seller_name),
        bold=True,
    )
    _text(
        page,
        pymupdf.Rect(38, 123, 335, 159),
        _plain(invoice.seller_address, ""),
        size=7.5,
    )
    _underlined_text(page, 38, 157, 297, invoice.seller_website)
    _underlined_text(page, 38, 169, 297, invoice.seller_email)

    labels = [("Date:", _date(invoice.invoice_date))]
    labels.append(
        (f"{_number_label(invoice)}:", _plain(invoice.invoice_no))
    )
    for index, (label, value) in enumerate(labels):
        top = 111 + index * 24
        _text(
            page,
            pymupdf.Rect(338, top, 430, top + 14),
            label,
            bold=True,
            align=pymupdf.TEXT_ALIGN_RIGHT,
        )
        _text(
            page,
            pymupdf.Rect(436, top, 557, top + 14),
            value,
            align=pymupdf.TEXT_ALIGN_CENTER,
        )
        page.draw_line((436, top + 14), (557, top + 14), color=BORDER)


def _bill_to_rows(invoice) -> list[tuple[str, str, float]]:
    """Return the Bill to rows shown by the invoice preview."""
    optional = [
        (
            "Name:",
            invoice.customer_contact_person or invoice.contact_person,
        ),
        ("VAT NO:", invoice.customer_tax_id),
        ("Address:", invoice.customer_address),
        (
            "Email:",
            invoice.customer_contact_email or invoice.contact_email,
        ),
        ("Contact:", invoice.customer_contact_phone),
    ]
    rows = [("Company:", _plain(invoice.customer_name))]
    rows.extend(
        (label, _plain(value, ""))
        for label, value in optional
        if _plain(value, "")
    )
    result = []
    for label, value in rows:
        lines = min(_line_count(value, BILL_TO_TEXT_WIDTH, 7.5), 3)
        height = 14 if lines == 1 else 6 + lines * 9
        result.append((label, value, height))
    return result


def _bill_to_shift(invoice) -> float:
    """Return how far the Bill to box pushes the content below it."""
    bottom = 208 + sum(row[2] for row in _bill_to_rows(invoice)) + 2
    return max(0.0, bottom - BILL_TO_BOTTOM)


def _draw_bill_to(page, invoice) -> None:
    rows = _bill_to_rows(invoice)
    bottom = BILL_TO_BOTTOM + _bill_to_shift(invoice)
    box = pymupdf.Rect(38, 190, 340, bottom)
    page.draw_rect(box, color=BORDER, width=0.6)
    header = pymupdf.Rect(box.x0, box.y0, box.x1, box.y0 + 15)
    page.draw_rect(header, color=BORDER, fill=GRAY, width=0.6)
    _text(
        page,
        pymupdf.Rect(40, 193, 338, 204),
        "Bill to:",
        color=WHITE,
        align=pymupdf.TEXT_ALIGN_CENTER,
    )
    top = 208
    for label, value, height in rows:
        _text(page, pymupdf.Rect(43, top, 100, top + height), label)
        _text(
            page,
            pymupdf.Rect(104, top, 335, top + height),
            value,
            size=7.5,
        )
        top += height


def _draw_contact(page, invoice, shift: float) -> None:
    left = 38
    top = 273 + shift
    header_height = 17
    row_height = 20
    widths = [104, 125, 78, 52, 160]
    headers = ["Contact Person", "Email", "PO#", "Currency", "Payment Term"]
    values = [
        invoice.contact_person,
        invoice.contact_email,
        invoice.purchase_order_no,
        invoice.currency,
        invoice.payment_terms,
    ]
    cursor = left
    for width, header, value in zip(widths, headers, values):
        _filled_cell(
            page,
            pymupdf.Rect(cursor, top, cursor + width, top + header_height),
            header,
            size=7.5,
        )
        _bordered_cell(
            page,
            pymupdf.Rect(
                cursor,
                top + header_height,
                cursor + width,
                top + header_height + row_height,
            ),
            _plain(value),
            size=7,
            align=pymupdf.TEXT_ALIGN_CENTER,
        )
        cursor += width
    page.draw_line(
        (38, 335 + shift),
        (557, 335 + shift),
        color=(0.33, 0.33, 0.33),
        width=1.5,
    )


def _item_row_height(item) -> float:
    description = _plain(item.description or item.product_name)
    line_count = sum(
        max(1, len(textwrap.wrap(line, width=72)))
        for line in description.splitlines() or [""]
    )
    return max(21, 7 + line_count * 9)


def _draw_items(page, invoice, items, start: int, shift: float) -> float:
    left = 38
    top = ITEMS_TOP + shift
    header_height = ITEMS_HEADER_HEIGHT
    widths = [36, 301, 36, 67, 79]
    headers = ["Item", "Description", "Qty", "Price", "Extended Price"]
    cursor = left
    for width, header in zip(widths, headers):
        _filled_cell(
            page,
            pymupdf.Rect(cursor, top, cursor + width, top + header_height),
            header,
            size=7.5,
        )
        cursor += width
    top += header_height
    if not items:
        items = [None]
    for offset, item in enumerate(items):
        row_height = _item_row_height(item) if item else 21
        cursor = left
        values = (
            [start + offset + 1, "—", "—", "—", "—"]
            if item is None
            else [
                start + offset + 1,
                item.description or item.product_name,
                _quantity(item.quantity),
                _amount(item.unit_price, invoice.currency),
                _amount(item.net_amount, invoice.currency),
            ]
        )
        aligns = [
            pymupdf.TEXT_ALIGN_CENTER,
            pymupdf.TEXT_ALIGN_LEFT,
            pymupdf.TEXT_ALIGN_CENTER,
            pymupdf.TEXT_ALIGN_RIGHT,
            pymupdf.TEXT_ALIGN_RIGHT,
        ]
        for width, value, align in zip(widths, values, aligns):
            _bordered_cell(
                page,
                pymupdf.Rect(cursor, top, cursor + width, top + row_height),
                value,
                size=7.5,
                align=align,
            )
            cursor += width
        top += row_height
    return top


def _draw_notes(page, invoice, top: float) -> float:
    box = pymupdf.Rect(38, top, 557, top + 48)
    page.draw_rect(box, color=BORDER, width=0.6)
    _text(
        page,
        pymupdf.Rect(43, top + 4, 552, top + 17),
        "Additional Notes & Disclaimers:",
        bold=True,
        italic=True,
    )
    _text(
        page,
        pymupdf.Rect(43, top + 19, 552, top + 44),
        _plain(invoice.additional_notes),
        size=7.5,
    )
    return box.y1


def _remarks_height(invoice) -> float:
    if not _plain(invoice.remarks, ""):
        return 0
    return 4 + _line_count(invoice.remarks, 304, 7.2) * 8.5


def _footer_height(invoice) -> float:
    """Return the space the totals, notes and footer need below items."""
    bank = 15 + _remarks_height(invoice) + sum(BANK_ROW_HEIGHTS) + 21
    return 8 + 27 + 48 + 17 + max(bank, 123)


def _draw_bank_details(page, invoice, top: float) -> float:
    _text(page, pymupdf.Rect(38, top, 350, top + 14), "Remarks:", bold=True)
    box_top = top + 15
    remarks_height = _remarks_height(invoice)
    if remarks_height:
        _text(
            page,
            pymupdf.Rect(38, box_top, 352, box_top + remarks_height),
            _plain(invoice.remarks, ""),
            size=7.2,
        )
        box_top += remarks_height
    heights = BANK_ROW_HEIGHTS
    rows = [
        ("Account Name:", invoice.bank_account_name),
        ("Bank Name:", invoice.bank_name),
        ("Bank Address:", invoice.bank_address),
        ("Account Number:", invoice.bank_account_number),
        ("Bank Code:", invoice.bank_code),
        ("Branch Code:", invoice.bank_branch_code),
        ("SWIFT CODE:", invoice.bank_swift_code),
    ]
    box_bottom = box_top + sum(heights)
    page.draw_rect(
        pymupdf.Rect(38, box_top, 352, box_bottom),
        color=BORDER,
        width=0.6,
    )
    cursor = box_top + 3
    for (label, value), height in zip(rows, heights):
        _text(
            page,
            pymupdf.Rect(43, cursor, 125, cursor + height - 2),
            label,
            size=7.2,
        )
        _text(
            page,
            pymupdf.Rect(130, cursor, 347, cursor + height - 2),
            _plain(value),
            size=7.2,
        )
        cursor += height
    _text(
        page,
        pymupdf.Rect(38, box_bottom + 3, 352, box_bottom + 21),
        _plain(invoice.remittance_instruction),
        size=6.8,
        italic=True,
    )
    return box_bottom + 21


def _draw_signature(page, invoice, top: float) -> float:
    left = 382
    right = 557
    _text(
        page,
        pymupdf.Rect(left, top + 16, right, top + 32),
        _plain(invoice.seller_name, "OnePro Cloud Limited"),
        bold=True,
        align=pymupdf.TEXT_ALIGN_CENTER,
    )
    signature = _signature_bytes(invoice.issuer_signature)
    if signature:
        page.insert_image(
            pymupdf.Rect(left + 18, top + 34, right - 18, top + 73),
            stream=signature,
            keep_proportion=True,
        )
    page.draw_line((left, top + 76), (right, top + 76), color=BORDER)
    rows = [
        ("Name:", invoice.signatory_name),
        ("Title:", invoice.signatory_title),
        ("Date:", _date(invoice.invoice_date)),
    ]
    cursor = top + 81
    for label, value in rows:
        _text(page, pymupdf.Rect(left, cursor, left + 42, cursor + 13), label)
        _text(
            page,
            pymupdf.Rect(left + 46, cursor, right, cursor + 13),
            _plain(value),
            size=7.5,
        )
        cursor += 14
    return cursor


def _draw_final_page(page, invoice, item_bottom: float) -> None:
    total_top = item_bottom + 8
    _text(
        page,
        pymupdf.Rect(250, total_top, 445, total_top + 15),
        "Total Amount:",
        bold=True,
        align=pymupdf.TEXT_ALIGN_RIGHT,
    )
    _text(
        page,
        pymupdf.Rect(450, total_top, 557, total_top + 15),
        _amount(invoice.total_amount, invoice.currency),
        bold=True,
        align=pymupdf.TEXT_ALIGN_RIGHT,
    )
    page.draw_line(
        (450, total_top + 16),
        (557, total_top + 16),
        color=BLACK,
    )
    notes_bottom = _draw_notes(page, invoice, total_top + 27)
    footer_top = notes_bottom + 17
    bank_bottom = _draw_bank_details(page, invoice, footer_top)
    signature_bottom = _draw_signature(page, invoice, footer_top)
    if max(bank_bottom, signature_bottom) > PAGE_BOTTOM:
        raise InvoicePdfRenderError(
            "Invoice content is too long for the approved A4 template."
        )


def _paginate(items, items_top: float, footer_height: float) -> list:
    """
    Split items into pages that fit the A4 template.

    Each page holds at most ITEMS_PER_PAGE rows, continuation pages keep
    room for the "continued" note, and trailing rows move to a new page
    when the last page cannot also hold the totals and footer.
    """
    if not items:
        return [[]]
    continued_limit = PAGE_BOTTOM - 30
    pages = [[]]
    bottom = items_top
    for item in items:
        height = _item_row_height(item)
        if pages[-1] and (
            len(pages[-1]) == ITEMS_PER_PAGE
            or bottom + height > continued_limit
        ):
            pages.append([])
            bottom = items_top
        pages[-1].append(item)
        bottom += height

    def overflows(page_items) -> bool:
        rows = sum(_item_row_height(item) for item in page_items)
        return items_top + rows + footer_height > PAGE_BOTTOM

    while len(pages[-1]) > 1 and overflows(pages[-1]):
        moved = []
        while len(pages[-1]) > 1 and overflows(pages[-1]):
            moved.insert(0, pages[-1].pop())
        pages.append(moved)
    return pages


def render_invoice_pdf(invoice) -> bytes:
    """Return an English, A4 Commercial Invoice PDF."""
    if not LOGO_PATH.is_file():
        raise InvoicePdfRenderError("Invoice logo is unavailable.")
    if not all((FONT_DIR / name).is_file() for _, name in FONT_FILES.values()):
        raise InvoicePdfRenderError("Invoice fonts are unavailable.")
    items = list(invoice.items.all())
    shift = _bill_to_shift(invoice)
    pages = _paginate(
        items,
        ITEMS_TOP + shift + ITEMS_HEADER_HEIGHT,
        _footer_height(invoice),
    )
    document = pymupdf.open()
    try:
        start = 0
        for page_index, page_items in enumerate(pages):
            page = document.new_page(width=595, height=842)
            _draw_header(page, invoice)
            _draw_bill_to(page, invoice)
            _draw_contact(page, invoice, shift)
            item_bottom = _draw_items(
                page,
                invoice,
                page_items,
                start,
                shift,
            )
            start += len(page_items)
            if page_index == len(pages) - 1:
                _draw_final_page(page, invoice, item_bottom)
            else:
                _text(
                    page,
                    pymupdf.Rect(170, item_bottom + 15, 425, item_bottom + 30),
                    "Invoice items continued on next page",
                    italic=True,
                    align=pymupdf.TEXT_ALIGN_CENTER,
                    color=(0.33, 0.33, 0.33),
                )
            if len(pages) > 1:
                _text(
                    page,
                    pymupdf.Rect(470, 810, 557, 826),
                    f"Page {page_index + 1} / {len(pages)}",
                    size=7,
                    align=pymupdf.TEXT_ALIGN_RIGHT,
                    color=(0.33, 0.33, 0.33),
                )
        title = _document_title(invoice)
        document.set_metadata(
            {
                "title": f"{title} {invoice.invoice_no}",
                "author": invoice.seller_name or "OnePro Cloud Limited",
                "subject": title,
            }
        )
        document.subset_fonts()
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
