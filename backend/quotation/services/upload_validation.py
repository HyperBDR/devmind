from pathlib import Path, PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from django.conf import settings


def _validate_xlsx_path(file_name: str) -> None:
    """Reject archive member paths that can escape the XLSX root."""
    normalized = file_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    first_part = path.parts[0] if path.parts else ""
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or ":" in first_part
    ):
        raise ValueError("XLSX archive contains an unsafe path")


def validate_xlsx_archive(upload) -> None:
    """Reject XLSX ZIP containers that exceed safe resource limits."""
    try:
        with ZipFile(upload) as archive:
            entries = archive.infolist()
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValueError("XLSX archive is invalid") from exc

    if len(entries) > settings.QUOTATION_XLSX_MAX_ENTRIES:
        raise ValueError(
            "XLSX archive has more than "
            f"{settings.QUOTATION_XLSX_MAX_ENTRIES} entries"
        )

    expanded_bytes = 0
    normalized_names = set()
    shared_strings_name = None
    worksheet_count = 0
    for entry in entries:
        _validate_xlsx_path(entry.filename)
        if entry.flag_bits & 0x1:
            raise ValueError("Encrypted XLSX entries are not supported")
        if entry.file_size > settings.QUOTATION_XLSX_MAX_ENTRY_BYTES:
            raise ValueError(
                "XLSX entry exceeds the "
                f"{settings.QUOTATION_XLSX_MAX_ENTRY_BYTES} byte "
                "expanded size limit"
            )
        expanded_bytes += entry.file_size
        if expanded_bytes > settings.QUOTATION_XLSX_MAX_EXPANDED_BYTES:
            raise ValueError(
                "XLSX expanded content exceeds the "
                f"{settings.QUOTATION_XLSX_MAX_EXPANDED_BYTES} byte limit"
            )
        if entry.file_size:
            ratio = entry.file_size / max(entry.compress_size, 1)
            if ratio > settings.QUOTATION_XLSX_MAX_COMPRESSION_RATIO:
                raise ValueError(
                    "XLSX entry exceeds the "
                    f"{settings.QUOTATION_XLSX_MAX_COMPRESSION_RATIO}:1 "
                    "compression ratio limit"
                )

        normalized_name = entry.filename.replace("\\", "/").lower()
        normalized_names.add(normalized_name)
        if normalized_name.startswith(
            "xl/worksheets/"
        ) and normalized_name.endswith(".xml"):
            worksheet_count += 1
            if worksheet_count > settings.QUOTATION_XLSX_MAX_WORKSHEETS:
                raise ValueError(
                    "XLSX workbook has more than "
                    f"{settings.QUOTATION_XLSX_MAX_WORKSHEETS} worksheets"
                )
        if (
            normalized_name == "xl/sharedstrings.xml"
            and entry.file_size
            > settings.QUOTATION_XLSX_MAX_SHARED_STRINGS_BYTES
        ):
            byte_limit = settings.QUOTATION_XLSX_MAX_SHARED_STRINGS_BYTES
            raise ValueError(
                "XLSX shared strings exceed the " f"{byte_limit} byte limit"
            )
        if normalized_name == "xl/sharedstrings.xml":
            shared_strings_name = entry.filename

    if shared_strings_name is not None:
        try:
            with ZipFile(upload) as archive:
                with archive.open(shared_strings_name) as shared_strings:
                    count = 0
                    for _, element in ElementTree.iterparse(
                        shared_strings,
                        events=("end",),
                    ):
                        if element.tag.rsplit("}", 1)[-1] == "si":
                            count += 1
                            if (
                                count
                                > settings.QUOTATION_XLSX_MAX_SHARED_STRINGS
                            ):
                                item_limit = (
                                    settings.QUOTATION_XLSX_MAX_SHARED_STRINGS
                                )
                                raise ValueError(
                                    "XLSX shared strings exceed the "
                                    f"{item_limit} "
                                    "item limit"
                                )
                        element.clear()
        except ElementTree.ParseError as exc:
            raise ValueError("XLSX shared strings XML is invalid") from exc
        except (BadZipFile, OSError, RuntimeError) as exc:
            raise ValueError("XLSX archive is invalid") from exc

    required_entries = {"[content_types].xml", "xl/workbook.xml"}
    if not required_entries.issubset(normalized_names):
        raise ValueError("XLSX archive is missing required workbook entries")


def validate_quotation_upload(upload) -> None:
    file_name = str(getattr(upload, "name", "") or "")
    extension = Path(file_name).suffix.lower()
    if extension not in settings.QUOTATION_ALLOWED_EXTENSIONS:
        raise ValueError("Only XLSX and PDF files are supported")

    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0:
        raise ValueError("File is empty")
    if size > settings.QUOTATION_MAX_UPLOAD_BYTES:
        raise ValueError(
            "File must be "
            f"{settings.QUOTATION_MAX_UPLOAD_BYTES} bytes or smaller"
        )

    original_position = upload.tell()
    try:
        upload.seek(0)
        signature = upload.read(5)
        if extension == ".xlsx" and signature.startswith(b"PK\x03\x04"):
            upload.seek(0)
            validate_xlsx_archive(upload)
    finally:
        upload.seek(original_position)

    if extension == ".pdf" and not signature.startswith(b"%PDF-"):
        raise ValueError("File content does not match PDF")
    if extension == ".xlsx" and not signature.startswith(b"PK\x03\x04"):
        raise ValueError("File content does not match XLSX")
