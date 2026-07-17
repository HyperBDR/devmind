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


def storage_root() -> Path:
    return Path(settings.QUOTATION_STORAGE).resolve()


def resolve_document_path(storage_key: str) -> Path:
    root = storage_root()
    path = (root / str(storage_key)).resolve()
    if path != root and root not in path.parents:
        raise ValueError("document path is outside quotation storage")
    return path


def write_document(content: bytes, storage_key: str) -> Path:
    path = resolve_document_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def delete_document(storage_key: str) -> bool:
    path = resolve_document_path(storage_key)
    if not path.is_file():
        return False
    path.unlink()
    try:
        path.parent.rmdir()
    except OSError:
        pass
    return True


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
