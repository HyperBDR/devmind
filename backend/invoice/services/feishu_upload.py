"""Upload locally created Invoice PDFs through the managed Feishu route."""

from __future__ import annotations

from django.db import DatabaseError, transaction

from invoice.models import (
    Invoice,
    InvoiceAccessRole,
    InvoiceDocument,
    InvoiceSourceType,
    InvoiceStatus,
)
from invoice.permissions import (
    get_invoice_access_role,
    has_invoice_upload_access,
)
from invoice.services.documents import (
    invoice_storage,
    latest_downloadable_document,
)
from quotation.services.storage_control import (
    StorageRouter,
    preserve_remote_file_reference,
)
from quotation.services.feishu_service import (
    folder_token_for_item,
    is_folder_drive_item,
)
from quotation.services.feishu_client import FeishuAPIError


class InvoiceFeishuUploadError(ValueError):
    """Raised when an Invoice cannot be uploaded to Feishu."""


def invoice_feishu_targets(
    folder_token: str = "",
    *,
    actor=None,
) -> dict[str, object]:
    """Return one Invoice folder and its direct child folders."""
    try:
        route = StorageRouter().resolve(scope_key="invoice")
    except (DatabaseError, LookupError, OSError) as exc:
        raise InvoiceFeishuUploadError(
            "Feishu storage is not configured for invoices."
        ) from exc
    root_token = route.mount.root_folder_token
    current_token = folder_token.strip() or root_token
    current_name = (
        route.mount.root_folder_name
        or route.connection.display_name
        or "Invoice archive"
    )
    if current_token != root_token:
        metadata = route.provider.client.get_folder_meta(
            route.provider.access_token(),
            current_token,
        )
        current_name = str(
            metadata.get("name")
            or metadata.get("folder_name")
            or current_token
        )
    files = route.provider._folder_files(
        access_token=route.provider.access_token(),
        folder_token=current_token,
    )
    folders: list[dict[str, str]] = []
    for item in files:
        if not is_folder_drive_item(item):
            continue
        token = folder_token_for_item(item).strip()
        name = str(item.get("name") or "").strip()
        if token and name:
            if (
                actor is not None
                and get_invoice_access_role(actor) != InvoiceAccessRole.ADMIN
                and not has_invoice_upload_access(actor, token)
            ):
                continue
            folders.append({"token": token, "name": name})
    return {
        "current": {"token": current_token, "name": current_name},
        "items": folders,
    }


def upload_invoice_to_feishu(
    invoice: Invoice,
    *,
    actor=None,
    folder_token: str = "",
) -> tuple[InvoiceDocument, bool]:
    """Upload the current Invoice PDF and persist its Feishu reference."""
    if invoice.source_type != InvoiceSourceType.MANUAL:
        raise InvoiceFeishuUploadError(
            "Only invoices created here can be uploaded to Feishu."
        )
    document = latest_downloadable_document(invoice)
    if (
        invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PAID}
        or document is None
    ):
        raise InvoiceFeishuUploadError(
            "Issue the invoice before uploading it to Feishu."
        )
    if document.feishu_file_token and document.feishu_url:
        return document, True

    storage = invoice_storage()
    path = storage.resolve(document.storage_key)
    if not path.is_file():
        raise InvoiceFeishuUploadError("The generated invoice PDF is missing.")

    try:
        route = StorageRouter().resolve(scope_key="invoice")
    except (DatabaseError, LookupError, OSError) as exc:
        raise InvoiceFeishuUploadError(
            "Feishu storage is not configured for invoices."
        ) from exc
    target_folder = folder_token.strip() or route.mount.root_folder_token
    if not has_invoice_upload_access(actor, target_folder):
        raise InvoiceFeishuUploadError(
            "Upload access to this Feishu folder is required."
        )
    if target_folder != route.mount.root_folder_token:
        try:
            route.provider.client.get_folder_meta(
                route.provider.access_token(),
                target_folder,
            )
        except FeishuAPIError as exc:
            raise InvoiceFeishuUploadError(
                "The selected Feishu folder is not available for invoices."
            ) from exc
    uploaded = route.provider.upload(
        route.mount,
        file_name=document.file_name,
        content=path.read_bytes(),
        folder_token=target_folder,
    )
    token = str(uploaded.get("file_token") or uploaded.get("token") or "")
    if not token:
        raise InvoiceFeishuUploadError(
            "Feishu did not return a file token for the upload."
        )
    remote_url = str(uploaded.get("url") or "")
    remote_folder = target_folder
    reused = bool(uploaded.get("reused"))
    with transaction.atomic():
        preserve_remote_file_reference(
            token,
            connection=route.connection,
            owned=not reused,
        )
        document = InvoiceDocument.objects.select_for_update().get(
            pk=document.pk
        )
        document.feishu_file_token = token
        document.feishu_folder_token = remote_folder
        document.feishu_url = remote_url[:1000]
        document.feishu_file_owned = not reused
        document.feishu_owner_connection_id = (
            str(route.connection.id) if not reused else ""
        )
        document.save(
            update_fields=[
                "feishu_file_token",
                "feishu_folder_token",
                "feishu_url",
                "feishu_file_owned",
                "feishu_owner_connection_id",
                "updated_at",
            ]
        )
    return document, reused
