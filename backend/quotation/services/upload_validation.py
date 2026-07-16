from pathlib import Path

from django.conf import settings


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
    finally:
        upload.seek(original_position)

    if extension == ".pdf" and not signature.startswith(b"%PDF-"):
        raise ValueError("File content does not match PDF")
    if extension == ".xlsx" and not signature.startswith(b"PK\x03\x04"):
        raise ValueError("File content does not match XLSX")
