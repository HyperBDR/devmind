"""
Quotation document storage under QUOTATION_STORAGE/documents/{record_uuid}/.

This mirrors data_collector attachment storage: disk paths contain UUIDs only;
the original file name and content type stay in the database.
"""

import logging
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.db import transaction

from core.document_storage import LocalDocumentStorage

logger = logging.getLogger(__name__)


def _uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(
            "document storage path segments must be UUIDs"
        ) from exc


def document_storage_key(
    document_id: str, quotation_id: str | None = None
) -> str:
    document_uuid = _uuid(document_id)
    record_uuid = _uuid(quotation_id) if quotation_id else document_uuid
    return f"documents/{record_uuid}/{document_uuid}"


def template_storage_key(template_id: str) -> str:
    return f"templates/{_uuid(template_id)}.xlsx"


def storage_root() -> Path:
    return Path(settings.QUOTATION_STORAGE).absolute()


def _storage() -> LocalDocumentStorage:
    return LocalDocumentStorage(
        storage_root(),
        chunk_size=settings.QUOTATION_UPLOAD_CHUNK_BYTES,
    )


def resolve_document_path(storage_key: str) -> Path:
    return _storage().resolve(storage_key)


def write_document(content: bytes, storage_key: str) -> Path:
    return _storage().write(content, storage_key)


def write_document_stream(stream, storage_key: str) -> tuple[Path, int]:
    return _storage().write_stream(stream, storage_key)


def write_document_atomic(content: bytes, storage_key: str) -> Path:
    return _storage().write_atomic(content, storage_key)


def delete_document(storage_key: str) -> bool:
    return _storage().delete(storage_key)


def delete_documents_after_commit(storage_keys) -> None:
    keys = tuple(dict.fromkeys(str(key) for key in storage_keys if key))

    def cleanup() -> None:
        for storage_key in keys:
            try:
                delete_document(storage_key)
            except (OSError, ValueError):
                logger.exception(
                    "Failed to delete quotation document storage_key=%s",
                    storage_key,
                )

    transaction.on_commit(cleanup)
