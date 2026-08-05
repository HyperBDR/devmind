from __future__ import annotations

import base64
import binascii
import fcntl
import os
import signal
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from copy import copy
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as SpreadsheetImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import (
    absolute_coordinate,
    coordinate_to_tuple,
    get_column_letter,
    quote_sheetname,
)
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.writer.excel import ExcelWriter
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from quotation.models import QuotationTemplate, QuotationTemplateStatus
from quotation.services.storage import (
    delete_document,
    resolve_document_path,
    template_storage_key,
    write_document_atomic,
)

LEGACY_DEFAULT_TEMPLATE_NAME = "DevMind standard quotation"
DEFAULT_TEMPLATE_NAME = "DevMind managed standard quotation"
DEFAULT_TEMPLATE_VERSION = 2
CURRENT_RENDERER_VERSION = "openpyxl-libreoffice-v5-original-import"
DEFAULT_WORKSHEET = "Quotation"
REQUIRED_TEMPLATE_NAMES = {
    "billing_company",
    "billing_contact",
    "billing_email",
    "client_company",
    "contact_person",
    "currency",
    "email",
    "expire_date",
    "grand_total",
    "issuer_company_name",
    "issuer_contact_email",
    "issuer_contact_name",
    "issuer_signature",
    "line_items_start",
    "payment_terms",
    "project_name",
    "quote_date",
    "quote_no",
    "remarks_disclaimer",
    "subtotal_before_vat",
    "vat_amount",
}
OPTIONAL_TEMPLATE_NAMES = {"tax_label", "vat_rate"}


class TemplateValidationError(ValueError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


class PdfConversionError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class PdfConversionBusyError(PdfConversionError):
    pass


class PdfConversionTimeoutError(PdfConversionError, TimeoutError):
    pass


@contextmanager
def _libreoffice_conversion_slot() -> Iterator[None]:
    """Acquire one cross-process LibreOffice conversion slot."""
    lock_dir = Path(settings.QUOTATION_RENDER_LOCK_DIR)
    lock_dir.mkdir(parents=True, exist_ok=True)
    for slot in range(settings.QUOTATION_RENDER_CONCURRENCY):
        lock_path = lock_dir / f"slot-{slot}.lock"
        lock_file = lock_path.open("a+b")
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            lock_file.close()
            continue
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
        return
    raise PdfConversionBusyError(
        "LibreOffice conversion capacity is busy",
        code="libreoffice_busy",
    )


def _save_workbook_deterministic(workbook: Workbook) -> bytes:
    """Serialize an XLSX without wall-clock metadata or ZIP timestamps."""
    stable_modified = (
        workbook.properties.modified
        or workbook.properties.created
        or datetime(2000, 1, 1)
    )
    workbook.properties.modified = stable_modified.replace(microsecond=0)
    raw_output = BytesIO()
    archive = ZipFile(
        raw_output,
        "w",
        ZIP_DEFLATED,
        allowZip64=True,
    )
    ExcelWriter(workbook, archive).save()

    canonical_output = BytesIO()
    with ZipFile(BytesIO(raw_output.getvalue())) as source:
        with ZipFile(
            canonical_output,
            "w",
            ZIP_DEFLATED,
            allowZip64=True,
        ) as target:
            for source_info in source.infolist():
                target_info = ZipInfo(
                    source_info.filename,
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                target_info.compress_type = source_info.compress_type
                target_info.create_system = source_info.create_system
                target_info.external_attr = source_info.external_attr
                target_info.internal_attr = source_info.internal_attr
                target_info.comment = source_info.comment
                target.writestr(
                    target_info,
                    source.read(source_info.filename),
                )
    return canonical_output.getvalue()


def _add_defined_name(
    workbook: Workbook,
    name: str,
    cell_reference: str,
) -> None:
    workbook.defined_names.add(
        DefinedName(
            name,
            attr_text=f"'{DEFAULT_WORKSHEET}'!${cell_reference}",
        )
    )


def _build_managed_template_bytes(*, version: int) -> bytes:
    """Build one managed template version for creation or identification."""
    if version not in {1, DEFAULT_TEMPLATE_VERSION}:
        raise ValueError("unsupported managed template version")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = DEFAULT_WORKSHEET
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 9
    sheet.column_dimensions["B"].width = 30
    sheet.column_dimensions["C"].width = 10
    sheet.column_dimensions["D"].width = 15
    sheet.column_dimensions["E"].width = 12
    sheet.column_dimensions["F"].width = 16
    sheet.column_dimensions["G"].width = 17

    thin = Side(style="thin", color="94A3B8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="E2E8F0")

    sheet.merge_cells("A1:G1")
    sheet["A1"] = "OnePro Cloud Limited"
    sheet["A1"].font = Font(size=18, bold=True)
    sheet["A1"].alignment = Alignment(horizontal="center")
    sheet.merge_cells("A2:G2")
    sheet["A2"] = "Quotation"
    sheet["A2"].font = Font(size=16, bold=True, underline="single")
    sheet["A2"].alignment = Alignment(horizontal="center")

    labels = {
        "A4": "Quote No.",
        "F4": "Date",
        "F5": "Valid Till",
        "A6": "Ship to",
        "C6": "Contact",
        "E6": "Email",
        "A7": "Bill to",
        "C7": "Contact",
        "E7": "Email",
        "A8": "Project",
        "C8": "Payment Terms",
        "F8": "Currency",
    }
    for coordinate, label in labels.items():
        sheet[coordinate] = label
        sheet[coordinate].font = Font(bold=True)

    headers = [
        "Line",
        "Description",
        "Qty",
        "List Price",
        "Discount",
        "Net Unit Price",
        "Extended Price",
    ]
    for column, label in enumerate(headers, 1):
        cell = sheet.cell(row=10, column=column, value=label)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
        item_cell = sheet.cell(row=11, column=column)
        item_cell.border = border
        item_cell.alignment = Alignment(
            horizontal="left" if column == 2 else "right",
            vertical="top",
            wrap_text=True,
        )

    sheet["F12"] = "Subtotal"
    if version == 1:
        sheet["F13"] = "Tax"
    else:
        sheet["E13"] = "Tax"
        sheet["F13"] = "Rate"
    sheet["F14"] = "Grand Total"
    for row in range(12, 15):
        if version >= DEFAULT_TEMPLATE_VERSION:
            sheet.cell(row=row, column=5).font = Font(bold=True)
            sheet.cell(row=row, column=5).border = border
        sheet.cell(row=row, column=6).font = Font(bold=True)
        sheet.cell(row=row, column=7).font = Font(bold=True)
        sheet.cell(row=row, column=6).border = border
        sheet.cell(row=row, column=7).border = border

    sheet["A16"] = "Remarks"
    sheet["A16"].font = Font(bold=True)
    sheet.merge_cells("B16:G16")
    sheet["B16"].alignment = Alignment(wrap_text=True, vertical="top")
    sheet["A18"] = "Prepared by"
    sheet["A18"].font = Font(bold=True)
    sheet["D18"] = "Email"
    sheet["D18"].font = Font(bold=True)
    sheet["D20"] = "Signature"
    sheet["D20"].font = Font(bold=True)
    sheet.merge_cells("E20:G22")

    names = {
        "issuer_company_name": "A1",
        "quote_no": "B4",
        "quote_date": "G4",
        "expire_date": "G5",
        "client_company": "B6",
        "contact_person": "D6",
        "email": "G6",
        "billing_company": "B7",
        "billing_contact": "D7",
        "billing_email": "G7",
        "project_name": "B8",
        "payment_terms": "D8",
        "currency": "G8",
        "line_items_start": "A11",
        "subtotal_before_vat": "G12",
        "vat_amount": "G13",
        "grand_total": "G14",
        "remarks_disclaimer": "B16",
        "issuer_contact_name": "B18",
        "issuer_contact_email": "E18",
        "issuer_signature": "E20",
    }
    if version >= DEFAULT_TEMPLATE_VERSION:
        names.update(
            {
                "tax_label": "E13",
                "vat_rate": "F13",
            }
        )
    for name, coordinate in names.items():
        _add_defined_name(workbook, name, coordinate)

    sheet.freeze_panes = "A10"
    sheet.print_area = "A1:G22"
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True

    stable_timestamp = datetime(2000, 1, 1)
    workbook.properties.created = stable_timestamp
    workbook.properties.modified = stable_timestamp
    return _save_workbook_deterministic(workbook)


def build_default_template_bytes() -> bytes:
    """Build the managed fallback template used on fresh deployments."""
    return _build_managed_template_bytes(version=DEFAULT_TEMPLATE_VERSION)


def _template_fingerprint(content: bytes) -> str:
    """Hash workbook semantics while ignoring generated timestamps."""
    workbook = load_workbook(BytesIO(content), read_only=False)
    try:
        stable_timestamp = datetime(2000, 1, 1)
        workbook.properties.created = stable_timestamp
        workbook.properties.modified = stable_timestamp
        normalized = _save_workbook_deterministic(workbook)
    finally:
        workbook.close()
    return sha256(normalized).hexdigest()


def _is_legacy_managed_template(template: QuotationTemplate) -> bool:
    """Identify the shipped v1 template by immutable workbook content."""
    if template.version != 1 or template.name not in {
        LEGACY_DEFAULT_TEMPLATE_NAME,
        DEFAULT_TEMPLATE_NAME,
    }:
        return False
    try:
        content = template_path(template).read_bytes()
        expected = _build_managed_template_bytes(version=1)
        return _template_fingerprint(content) == _template_fingerprint(expected)
    except (OSError, TemplateValidationError):
        return False


def validate_template_bytes(content: bytes) -> None:
    max_bytes = settings.QUOTATION_MAX_TEMPLATE_BYTES
    if not content.startswith(b"PK\x03\x04"):
        raise TemplateValidationError(
            "Quotation template is not an XLSX file",
            code="template_invalid_signature",
        )
    if len(content) > max_bytes:
        raise TemplateValidationError(
            "Quotation template exceeds the size limit",
            code="template_too_large",
        )
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            member_names = {member.filename for member in members}
    except BadZipFile as exc:
        raise TemplateValidationError(
            "Quotation template is not a valid ZIP container",
            code="template_invalid_zip",
        ) from exc
    expanded_bytes = sum(member.file_size for member in members)
    if expanded_bytes > settings.QUOTATION_MAX_TEMPLATE_EXPANDED_BYTES:
        raise TemplateValidationError(
            "Quotation template expands beyond the size limit",
            code="template_expanded_too_large",
        )
    if "xl/vbaProject.bin" in member_names:
        raise TemplateValidationError(
            "Macro-enabled quotation templates are not allowed",
            code="template_macros_forbidden",
        )
    if any(name.startswith("xl/externalLinks/") for name in member_names):
        raise TemplateValidationError(
            "External workbook links are not allowed",
            code="template_external_links_forbidden",
        )
    if "xl/connections.xml" in member_names:
        raise TemplateValidationError(
            "External workbook connections are not allowed",
            code="template_external_connections_forbidden",
        )
    try:
        workbook = load_workbook(BytesIO(content), read_only=False)
    except Exception as exc:
        raise TemplateValidationError(
            "Quotation template cannot be opened",
            code="template_unreadable",
        ) from exc
    has_worksheet = DEFAULT_WORKSHEET in workbook.sheetnames
    available_names = set(workbook.defined_names)
    workbook.close()
    if not has_worksheet:
        raise TemplateValidationError(
            "Quotation template is missing the Quotation worksheet",
            code="template_worksheet_missing",
        )
    missing = sorted(REQUIRED_TEMPLATE_NAMES - available_names)
    if missing:
        message = "Quotation template is missing named ranges: "
        message += ", ".join(missing)
        raise TemplateValidationError(
            message,
            code="template_named_ranges_missing",
        )


def ensure_default_template(*, created_by=None) -> QuotationTemplate:
    active = (
        QuotationTemplate.objects.filter(status=QuotationTemplateStatus.ACTIVE)
        .order_by("-version", "id")
        .first()
    )
    if active is not None and not _is_legacy_managed_template(active):
        return active

    content = build_default_template_bytes()
    validate_template_bytes(content)
    template = QuotationTemplate(
        name=DEFAULT_TEMPLATE_NAME,
        version=DEFAULT_TEMPLATE_VERSION,
        content_hash=sha256(content).hexdigest(),
        status=QuotationTemplateStatus.ACTIVE,
        created_by=created_by,
    )
    template.storage_key = template_storage_key(template.id)
    write_document_atomic(content, template.storage_key)
    try:
        with transaction.atomic():
            current = (
                QuotationTemplate.objects.select_for_update()
                .filter(status=QuotationTemplateStatus.ACTIVE)
                .order_by("-version", "id")
                .first()
            )
            if current is not None and not _is_legacy_managed_template(current):
                selected = current
            else:
                existing = (
                    QuotationTemplate.objects.select_for_update()
                    .filter(
                        name=DEFAULT_TEMPLATE_NAME,
                        version=DEFAULT_TEMPLATE_VERSION,
                    )
                    .first()
                )
                if (
                    existing is not None
                    and existing.content_hash != template.content_hash
                ):
                    raise TemplateValidationError(
                        "Managed default template version conflicts with "
                        "different content",
                        code="default_template_version_conflict",
                    )
                if current is not None:
                    current.status = QuotationTemplateStatus.ARCHIVED
                    current.save(
                        update_fields=["status", "updated_at"],
                    )
                if existing is not None:
                    existing.status = QuotationTemplateStatus.ACTIVE
                    existing.save(
                        update_fields=["status", "updated_at"],
                    )
                    selected = existing
                else:
                    template.save(force_insert=True)
                    selected = template
    except IntegrityError:
        delete_document(template.storage_key)
        active = (
            QuotationTemplate.objects.filter(
                status=QuotationTemplateStatus.ACTIVE,
            )
            .order_by("-version", "id")
            .first()
        )
        if active is not None:
            return active
        raise
    except Exception:
        delete_document(template.storage_key)
        raise
    if selected.pk != template.pk:
        delete_document(template.storage_key)
    return selected


def register_template_version(
    *,
    name: str,
    version: int,
    content: bytes,
    status: str,
    created_by=None,
) -> QuotationTemplate:
    """Validate and atomically register an immutable XLSX template."""
    validate_template_bytes(content)
    template = QuotationTemplate(
        name=name,
        version=version,
        content_hash=sha256(content).hexdigest(),
        status=status,
        created_by=created_by,
    )
    template.storage_key = template_storage_key(template.id)
    write_document_atomic(content, template.storage_key)
    try:
        with transaction.atomic():
            if status == QuotationTemplateStatus.ACTIVE:
                QuotationTemplate.objects.filter(
                    status=QuotationTemplateStatus.ACTIVE,
                ).update(status=QuotationTemplateStatus.ARCHIVED)
            template.save(force_insert=True)
    except Exception:
        delete_document(template.storage_key)
        raise
    return template


def template_path(template: QuotationTemplate) -> Path:
    path = resolve_document_path(template.storage_key)
    if not path.is_file():
        raise TemplateValidationError(
            "Quotation template file is missing",
            code="template_file_missing",
        )
    content = path.read_bytes()
    validate_template_bytes(content)
    if sha256(content).hexdigest() != template.content_hash:
        raise TemplateValidationError(
            "Quotation template hash does not match its version",
            code="template_hash_mismatch",
        )
    return path


def _defined_cell(workbook, name: str):
    definition = workbook.defined_names.get(name)
    destinations = list(definition.destinations) if definition else []
    if len(destinations) != 1:
        raise TemplateValidationError(
            f"Named range {name} must point to one cell",
            code="template_named_range_invalid",
        )
    sheet_name, coordinate = destinations[0]
    return workbook[sheet_name], coordinate.replace("$", "")


def _copy_row_style(sheet, source_row: int, target_row: int) -> None:
    for column in range(1, sheet.max_column + 1):
        source = sheet.cell(row=source_row, column=column)
        target = sheet.cell(row=target_row, column=column)
        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format
        target.alignment = copy(source.alignment)
        target.protection = copy(source.protection)
    source_height = sheet.row_dimensions[source_row].height
    sheet.row_dimensions[target_row].height = source_height


def _insert_rows_preserving_layout(
    workbook,
    sheet,
    row: int,
    amount: int,
) -> None:
    """Insert template rows and move layout metadata openpyxl leaves stale."""
    shifted_dimensions = []
    for dimension_row, dimension in list(sheet.row_dimensions.items()):
        if dimension_row < row:
            continue
        shifted = copy(dimension)
        shifted.index = dimension_row + amount
        shifted_dimensions.append((dimension_row, shifted))

    shifted_merges = []
    for merged_range in list(sheet.merged_cells.ranges):
        if merged_range.max_row < row:
            continue
        current = CellRange(str(merged_range))
        sheet.unmerge_cells(str(merged_range))
        if current.min_row >= row:
            current.shift(row_shift=amount)
        else:
            current.max_row += amount
        shifted_merges.append(str(current))

    sheet.insert_rows(row, amount=amount)
    for dimension_row, _dimension in shifted_dimensions:
        del sheet.row_dimensions[dimension_row]
    for _dimension_row, dimension in shifted_dimensions:
        sheet.row_dimensions[dimension.index] = dimension
    for merged_range in shifted_merges:
        sheet.merge_cells(merged_range)

    for drawing in [*sheet._images, *sheet._charts]:
        anchor = drawing.anchor
        if isinstance(anchor, str):
            anchor_row, anchor_column = coordinate_to_tuple(anchor)
            if anchor_row >= row:
                drawing.anchor = (
                    f"{get_column_letter(anchor_column)}" f"{anchor_row + amount}"
                )
            continue
        for marker_name in ("_from", "to"):
            marker = getattr(anchor, marker_name, None)
            if marker is not None and marker.row >= row - 1:
                marker.row += amount

    template_names = REQUIRED_TEMPLATE_NAMES | OPTIONAL_TEMPLATE_NAMES
    for name in template_names:
        definition = workbook.defined_names.get(name)
        destinations = list(definition.destinations) if definition else []
        if len(destinations) != 1:
            continue
        sheet_name, coordinate = destinations[0]
        if sheet_name != sheet.title:
            continue
        target = CellRange(coordinate.replace("$", ""))
        if target.min_row < row:
            continue
        target.shift(row_shift=amount)
        sheet_reference = quote_sheetname(sheet.title)
        cell_reference = absolute_coordinate(str(target))
        definition.attr_text = f"{sheet_reference}!{cell_reference}"


def _signature_image(data_url: str) -> SpreadsheetImage | None:
    if not data_url:
        return None
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError as exc:
        raise TemplateValidationError(
            "Quotation signature is not a data URL",
            code="signature_invalid",
        ) from exc
    allowed_headers = {
        "data:image/jpeg;base64",
        "data:image/jpg;base64",
        "data:image/png;base64",
    }
    if header.lower() not in allowed_headers:
        raise TemplateValidationError(
            "Quotation signature must be a PNG or JPEG data URL",
            code="signature_type_invalid",
        )
    max_encoded_bytes = ((settings.QUOTATION_MAX_SIGNATURE_BYTES + 2) // 3) * 4
    if len(encoded) > max_encoded_bytes:
        raise TemplateValidationError(
            "Quotation signature exceeds the size limit",
            code="signature_too_large",
        )
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TemplateValidationError(
            "Quotation signature contains invalid base64 data",
            code="signature_invalid",
        ) from exc
    if len(image_bytes) > settings.QUOTATION_MAX_SIGNATURE_BYTES:
        raise TemplateValidationError(
            "Quotation signature exceeds the size limit",
            code="signature_too_large",
        )
    try:
        with PillowImage.open(BytesIO(image_bytes)) as image:
            image.verify()
        with PillowImage.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            image_format = image.format
    except (OSError, UnidentifiedImageError) as exc:
        raise TemplateValidationError(
            "Quotation signature image is invalid",
            code="signature_invalid",
        ) from exc
    if image_format not in {"JPEG", "PNG"} or width > 4000 or height > 4000:
        raise TemplateValidationError(
            "Quotation signature image dimensions are invalid",
            code="signature_dimensions_invalid",
        )
    image = SpreadsheetImage(BytesIO(image_bytes))
    scale = min(180 / image.width, 60 / image.height, 1)
    image.width = round(image.width * scale)
    image.height = round(image.height * scale)
    return image


def render_quotation_xlsx(
    template: QuotationTemplate,
    snapshot: dict,
) -> bytes:
    """Render one immutable quotation snapshot into a validated XLSX."""
    path = template_path(template)
    workbook = load_workbook(path)
    scalar_values = {
        "issuer_company_name": snapshot.get("issuer_company_name", ""),
        "quote_no": snapshot.get("quote_no", ""),
        "quote_date": snapshot.get("quote_date", ""),
        "expire_date": snapshot.get("expire_date", ""),
        "client_company": snapshot.get("client_company", ""),
        "contact_person": snapshot.get("contact_person", ""),
        "email": snapshot.get("email", ""),
        "billing_company": snapshot.get("billing_company", ""),
        "billing_contact": snapshot.get("billing_contact", ""),
        "billing_email": snapshot.get("billing_email", ""),
        "project_name": snapshot.get("project_name", ""),
        "payment_terms": snapshot.get("payment_terms", ""),
        "currency": snapshot.get("currency", ""),
        "tax_label": snapshot.get("tax_label", ""),
        "vat_rate": f"{snapshot.get('vat_rate') or '0'}%",
        "remarks_disclaimer": snapshot.get("remarks_disclaimer", ""),
        "issuer_contact_name": snapshot.get("issuer_contact_name", ""),
        "issuer_contact_email": snapshot.get("issuer_contact_email", ""),
    }
    for name, value in scalar_values.items():
        definition = workbook.defined_names.get(name)
        if name in OPTIONAL_TEMPLATE_NAMES and definition is None:
            continue
        sheet, coordinate = _defined_cell(workbook, name)
        sheet[coordinate] = value

    item_sheet, item_coordinate = _defined_cell(
        workbook,
        "line_items_start",
    )
    item_start_row = item_sheet[item_coordinate].row
    items = list(snapshot.get("items") or [])
    render_items = items or [{}]
    extra_rows = max(len(render_items) - 1, 0)
    if extra_rows:
        _insert_rows_preserving_layout(
            workbook,
            item_sheet,
            item_start_row + 1,
            extra_rows,
        )
        for offset in range(1, extra_rows + 1):
            _copy_row_style(
                item_sheet,
                item_start_row,
                item_start_row + offset,
            )

    signature = _signature_image(snapshot.get("issuer_signature", ""))
    if signature is not None:
        signature_sheet, signature_coordinate = _defined_cell(
            workbook,
            "issuer_signature",
        )
        signature_cell = signature_sheet[signature_coordinate]
        signature.anchor = signature_sheet.cell(
            row=signature_cell.row,
            column=signature_cell.column,
        ).coordinate
        signature_sheet.add_image(signature)

    columns = (
        "line_no",
        "description",
        "qty",
        "list_price",
        "discount_percent",
        "net_unit_price",
        "extended_price",
    )
    for offset, item in enumerate(render_items):
        row = item_start_row + offset
        values = dict(item)
        values["description"] = item.get("description") or item.get("name") or ""
        for column, key in enumerate(columns, 1):
            item_sheet.cell(row=row, column=column, value=values.get(key, ""))

    for name in ("subtotal_before_vat", "vat_amount", "grand_total"):
        sheet, coordinate = _defined_cell(workbook, name)
        original = sheet[coordinate]
        original.value = snapshot.get(name, "0")
    item_sheet.print_area = f"A1:G{item_sheet.max_row}"

    try:
        content = _save_workbook_deterministic(workbook)
    finally:
        workbook.close()
    validate_template_bytes(content)
    return content


def _terminate_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def convert_xlsx_to_pdf(excel_bytes: bytes, *, job_id: str) -> bytes:
    """Convert XLSX bytes while respecting shared process capacity."""
    with _libreoffice_conversion_slot():
        return _convert_xlsx_to_pdf_unlocked(excel_bytes, job_id=job_id)


def _convert_xlsx_to_pdf_unlocked(excel_bytes: bytes, *, job_id: str) -> bytes:
    """Convert XLSX bytes with an isolated headless LibreOffice profile."""
    with TemporaryDirectory(prefix=f"quotation-render-{job_id}-") as root:
        root_path = Path(root)
        profile_path = root_path / "profile"
        output_path = root_path / "output"
        profile_path.mkdir()
        output_path.mkdir()
        input_path = root_path / "quotation.xlsx"
        input_path.write_bytes(excel_bytes)
        command = [
            settings.QUOTATION_SOFFICE_BINARY,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_path.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_path),
            str(input_path),
        ]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise PdfConversionError(
                "LibreOffice executable is unavailable",
                code="libreoffice_unavailable",
            ) from exc
        try:
            _stdout, stderr = process.communicate(
                timeout=settings.QUOTATION_RENDER_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as exc:
            _terminate_process_group(process)
            raise PdfConversionTimeoutError(
                "LibreOffice conversion timed out",
                code="libreoffice_timeout",
            ) from exc
        if process.returncode != 0:
            error_type = "conversion_failed" if stderr else "process_failed"
            raise PdfConversionError(
                "LibreOffice conversion failed",
                code=f"libreoffice_{error_type}",
            )
        pdf_path = output_path / "quotation.pdf"
        if not pdf_path.is_file():
            raise PdfConversionError(
                "LibreOffice produced no PDF file",
                code="libreoffice_no_output",
            )
        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes.startswith(b"%PDF-"):
            raise PdfConversionError(
                "LibreOffice produced an invalid PDF file",
                code="libreoffice_invalid_pdf",
                retryable=False,
            )
        if len(pdf_bytes) > settings.QUOTATION_MAX_PDF_BYTES:
            raise PdfConversionError(
                "Generated PDF exceeds the size limit",
                code="libreoffice_pdf_too_large",
                retryable=False,
            )
        return pdf_bytes
