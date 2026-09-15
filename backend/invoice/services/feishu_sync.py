"""Read-only Feishu folder synchronization for Invoice PDFs."""

from __future__ import annotations

import uuid
from collections import deque
from hashlib import sha256

from django.conf import settings
from django.db import IntegrityError

from invoice.models import (
    InvoiceDocument,
    InvoiceDocumentPurpose,
    InvoiceDocumentType,
    InvoiceParseStatus,
    InvoiceSourceType,
)
from invoice.parsing.pdf_parser import PARSER_VERSION
from invoice.services.documents import invoice_storage
from invoice.services.imports import parse_and_create_invoice
from quotation.services.feishu_client import (
    FeishuAPIError,
    FeishuClient,
    extract_feishu_token_from_url,
)
from quotation.services.feishu_service import (
    folder_token_for_item,
    is_folder_drive_item,
)
from quotation.services.storage_control import configured_drive_context


def configured_folder_token() -> str:
    """Return the backend-managed Invoice folder token."""
    value = (
        settings.INVOICE_FEISHU_FOLDER_TOKEN
        or settings.INVOICE_FEISHU_FOLDER_URL
    )
    if not value:
        raise FeishuAPIError("Invoice Feishu folder is not configured")
    return extract_feishu_token_from_url(value)


def _store_source_document(
    *,
    content: bytes,
    file_name: str,
    content_type: str,
    file_token: str,
    folder_token: str,
    file_url: str,
    actor,
) -> tuple[InvoiceDocument, bool]:
    """Persist one downloaded PDF without mutating the remote file."""
    existing = InvoiceDocument.objects.filter(
        feishu_file_token=file_token
    ).first()
    if existing is not None:
        return existing, True

    document_id = str(uuid.uuid4())
    storage_key = f"documents/{document_id}/{uuid.uuid4()}.pdf"
    storage = invoice_storage()
    storage.write_atomic(content, storage_key)
    try:
        document = InvoiceDocument.objects.create(
            id=document_id,
            file_name=file_name[:255],
            storage_key=storage_key,
            content_type=content_type[:120],
            document_type=InvoiceDocumentType.PDF,
            purpose=InvoiceDocumentPurpose.SOURCE,
            size_bytes=len(content),
            content_hash=sha256(content).hexdigest(),
            feishu_file_token=file_token,
            feishu_folder_token=folder_token,
            feishu_url=file_url[:1000],
            created_by=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )
    except IntegrityError:
        storage.delete(storage_key)
        document = InvoiceDocument.objects.get(
            feishu_file_token=file_token
        )
        return document, True
    except Exception:
        storage.delete(storage_key)
        raise
    return document, False


def _is_pdf(item: dict) -> bool:
    name = str(item.get("name") or "").strip().lower()
    item_type = str(item.get("type") or "").strip().lower()
    return (
        name.endswith(".pdf")
        and "delete" not in name
        and item_type not in {
        "doc",
        "docx",
        "sheet",
        "spreadsheet",
        }
    )


def _read_context(client=None):
    """Resolve the Quote-managed Feishu connection with legacy fallback."""
    if client is not None:
        return client, client.get_tenant_access_token()
    managed_context = configured_drive_context(scope_key="invoice")
    if managed_context is not None:
        managed_client, access_token = managed_context[:2]
        return managed_client, access_token
    legacy_client = FeishuClient()
    return legacy_client, legacy_client.get_tenant_access_token()


def sync_invoice_feishu_folder(*, actor=None, client=None) -> dict:
    """Download and parse PDFs using only Feishu read operations."""
    resolved_client, access_token = _read_context(client)
    root_token = configured_folder_token()
    pending_folders = deque([(root_token, "")])
    visited_folders: set[str] = set()
    counts = {
        "discovered_count": 0,
        "created_count": 0,
        "reused_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }

    while pending_folders:
        folder_token, region_hint = pending_folders.popleft()
        if folder_token in visited_folders:
            continue
        visited_folders.add(folder_token)
        page_token = None
        visited_pages: set[str] = set()
        while True:
            page = resolved_client.list_folder_files(
                access_token,
                folder_token,
                page_size=200,
                page_token=page_token,
            )
            for item in page.get("files") or []:
                if is_folder_drive_item(item):
                    child_token = folder_token_for_item(item).strip()
                    if child_token and child_token not in visited_folders:
                        child_name = str(item.get("name") or "").strip()
                        child_region = region_hint
                        if " - " in child_name:
                            child_region = child_name.rsplit(" - ", 1)[1]
                        pending_folders.append(
                            (child_token, child_region.strip())
                        )
                    continue
                if not _is_pdf(item):
                    counts["skipped_count"] += 1
                    continue
                counts["discovered_count"] += 1
                file_token = str(item.get("token") or "").strip()
                if not file_token:
                    counts["failed_count"] += 1
                    continue
                existing = InvoiceDocument.objects.filter(
                    feishu_file_token=file_token
                ).first()
                if existing is not None:
                    current_result = existing.parse_results.filter(
                        parser_version=PARSER_VERSION,
                    ).first()
                    if current_result is not None:
                        if (
                            current_result.status
                            == InvoiceParseStatus.CONFIRMED
                            and existing.invoice_id
                        ):
                            counts["reused_count"] += 1
                            continue
                try:
                    if existing is None:
                        content, mime_type, resolved_name = (
                            resolved_client.download_drive_item(
                                access_token,
                                file_token=file_token,
                                file_type=item.get("type"),
                                file_name=str(item.get("name") or file_token),
                            )
                        )
                        if not content:
                            raise ValueError("Feishu returned an empty PDF")
                        if len(content) > settings.INVOICE_MAX_UPLOAD_BYTES:
                            raise ValueError("Invoice PDF exceeds size limit")
                        existing, document_reused = _store_source_document(
                            content=content,
                            file_name=resolved_name,
                            content_type=mime_type or "application/pdf",
                            file_token=file_token,
                            folder_token=folder_token,
                            file_url=str(item.get("url") or ""),
                            actor=actor,
                        )
                    else:
                        document_reused = True
                    invoice, invoice_reused = parse_and_create_invoice(
                        existing,
                        actor=actor,
                        source_type=InvoiceSourceType.FEISHU,
                        region_hint=region_hint,
                    )
                except (FeishuAPIError, OSError, ValueError):
                    counts["failed_count"] += 1
                    continue
                if invoice is None:
                    counts["skipped_count"] += 1
                elif document_reused or invoice_reused:
                    counts["reused_count"] += 1
                else:
                    counts["created_count"] += 1
            if not page.get("has_more"):
                break
            next_page = str(page.get("next_page_token") or "").strip()
            if not next_page or next_page in visited_pages:
                break
            visited_pages.add(next_page)
            page_token = next_page
    return counts
