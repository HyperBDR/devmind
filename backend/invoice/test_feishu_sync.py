from datetime import date, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.periodic_registry import TASK_REGISTRY
from invoice.models import (
    Invoice,
    InvoiceAccessGrant,
    InvoiceDocument,
    InvoiceParseResult,
    InvoiceSourceType,
    InvoiceSyncRun,
    InvoiceSyncStatus,
)
from invoice.parsing.schemas import (
    ParsedInvoice,
    ParsedInvoiceDocumentData,
    ParsedInvoiceItem,
)
from invoice.periodic_tasks import register_periodic_tasks
from invoice.services.feishu_sync import sync_invoice_feishu_folder
from invoice.tasks import (
    enqueue_invoice_feishu_sync,
    sync_invoice_feishu_task,
)


class ReadOnlyFeishuClient:
    def __init__(self):
        self.download_count = 0
        self.tenant_token_requests = 0

    def get_tenant_access_token(self):
        self.tenant_token_requests += 1
        return "tenant-token"

    def list_folder_files(
        self,
        access_token,
        folder_token,
        *,
        page_size,
        page_token,
    ):
        if folder_token == "root-folder-token":
            return {
                "files": [
                    {
                        "token": "customer-folder-token",
                        "name": "Customer - Malaysia",
                        "type": "folder",
                    },
                    {
                        "token": "ignored-file-token",
                        "name": "notes.txt",
                        "type": "file",
                    },
                ],
                "has_more": False,
            }
        return {
            "files": [
                {
                    "token": "invoice-file-token",
                    "name": "sales-invoice.pdf",
                    "type": "file",
                    "url": "https://example.feishu.cn/file/token",
                }
            ],
            "has_more": False,
        }

    def download_drive_item(
        self,
        access_token,
        *,
        file_token,
        file_type,
        file_name,
    ):
        self.download_count += 1
        return b"%PDF-1.4 invoice", "application/pdf", file_name

    def upload_file(self, *args, **kwargs):
        raise AssertionError("Invoice sync must not upload to Feishu")

    def delete_file(self, *args, **kwargs):
        raise AssertionError("Invoice sync must not delete from Feishu")


@override_settings(
    INVOICE_FEISHU_FOLDER_TOKEN="root-folder-token",
    INVOICE_FEISHU_FOLDER_URL="",
)
class InvoiceFeishuSyncTests(TestCase):
    def test_sync_reuses_managed_quote_storage_connection(self):
        client = ReadOnlyFeishuClient()
        context = (
            client,
            "managed-token",
            "quote-folder-token",
            None,
            None,
        )

        with patch.object(
            client,
            "list_folder_files",
            return_value={"files": [], "has_more": False},
        ) as list_files, patch(
            "invoice.services.feishu_sync.configured_drive_context",
            return_value=context,
            create=True,
        ) as configured_context:
            result = sync_invoice_feishu_folder()

        self.assertEqual(result["discovered_count"], 0)
        self.assertEqual(client.tenant_token_requests, 0)
        configured_context.assert_called_once_with(scope_key="invoice")
        list_files.assert_called_once_with(
            "managed-token",
            "root-folder-token",
            page_size=200,
            page_token=None,
        )

    def test_sync_creates_sales_records_without_review(self):
        parsed = ParsedInvoiceDocumentData(
            invoice=ParsedInvoice(
                invoice_no="INV-FEISHU-1",
                invoice_date=date(2026, 9, 9),
                customer_name="Feishu Customer",
                total_amount=Decimal("88.00"),
                items=[
                    ParsedInvoiceItem(
                        line_no=1,
                        product_name="Cloud service",
                        quantity=Decimal("1"),
                        unit_price=Decimal("88.00"),
                        net_amount=Decimal("88.00"),
                        total_amount=Decimal("88.00"),
                    )
                ],
            )
        )
        client = ReadOnlyFeishuClient()

        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root), patch(
                "invoice.services.imports.parse_invoice_pdf",
                return_value=parsed,
            ):
                first = sync_invoice_feishu_folder(client=client)
                second = sync_invoice_feishu_folder(client=client)

        invoice = Invoice.objects.get(invoice_no="INV-FEISHU-1")
        document = InvoiceDocument.objects.get(
            feishu_file_token="invoice-file-token"
        )
        self.assertEqual(invoice.source_type, InvoiceSourceType.FEISHU)
        self.assertEqual(invoice.region, "Malaysia")
        self.assertEqual(document.invoice_id, invoice.id)
        self.assertEqual(document.feishu_folder_token, "customer-folder-token")
        self.assertEqual(first["created_count"], 1)
        self.assertEqual(first["skipped_count"], 1)
        self.assertEqual(second["reused_count"], 1)
        self.assertEqual(client.download_count, 1)

    def test_sync_reprocesses_results_from_the_previous_parser(self):
        old = ParsedInvoiceDocumentData(
            invoice=ParsedInvoice(
                invoice_no="INV-FEISHU-1",
                invoice_date=date(2026, 9, 9),
                customer_name="Feishu Customer",
                total_amount=Decimal("88.00"),
            )
        )
        current = ParsedInvoiceDocumentData(
            invoice=ParsedInvoice(
                invoice_no="INV-FEISHU-1",
                invoice_date=date(2026, 9, 9),
                customer_name="Feishu Customer",
                total_amount=Decimal("88.00"),
                bank_name="DBS Bank Limited, Hong Kong Branch",
                bank_swift_code="DBSSHKHH",
                signatory_name="Natalie Chan",
            )
        )
        client = ReadOnlyFeishuClient()

        with TemporaryDirectory() as storage_root:
            with override_settings(INVOICE_STORAGE=storage_root), patch(
                "invoice.services.imports.parse_invoice_pdf",
                side_effect=[old, current],
            ) as parse_pdf:
                sync_invoice_feishu_folder(client=client)
                result = InvoiceParseResult.objects.get()
                result.parser_version = "0.5.2"
                result.save(update_fields=["parser_version"])
                sync_invoice_feishu_folder(client=client)

        invoice = Invoice.objects.get(invoice_no="INV-FEISHU-1")
        self.assertEqual(parse_pdf.call_count, 2)
        self.assertEqual(
            invoice.bank_name,
            "DBS Bank Limited, Hong Kong Branch",
        )
        self.assertEqual(invoice.bank_swift_code, "DBSSHKHH")
        self.assertEqual(invoice.signatory_name, "Natalie Chan")

    def test_task_records_completed_sync_counts(self):
        run = InvoiceSyncRun.objects.create()
        counts = {
            "discovered_count": 4,
            "created_count": 2,
            "reused_count": 1,
            "skipped_count": 1,
            "failed_count": 0,
        }

        with patch(
            "invoice.tasks.sync_invoice_feishu_folder",
            return_value=counts,
        ):
            result = sync_invoice_feishu_task.run(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, InvoiceSyncStatus.SUCCESS)
        self.assertEqual(run.created_count, 2)
        self.assertEqual(result["run_id"], run.id)

    @override_settings(INVOICE_FEISHU_SYNC_STALE_SECONDS=60)
    def test_enqueue_recovers_stale_running_sync(self):
        stale = InvoiceSyncRun.objects.create(
            status=InvoiceSyncStatus.RUNNING,
            started_at=timezone.now() - timedelta(hours=1),
        )

        with patch.object(
            sync_invoice_feishu_task,
            "apply_async",
        ) as apply_async:
            run, reused = enqueue_invoice_feishu_sync()

        stale.refresh_from_db()
        self.assertFalse(reused)
        self.assertNotEqual(run.id, stale.id)
        self.assertEqual(stale.status, InvoiceSyncStatus.FAILED)
        self.assertEqual(stale.error_message, "stale_run_recovered")
        apply_async.assert_called_once()

    def test_periodic_sync_uses_configured_interval(self):
        TASK_REGISTRY.clear()

        with override_settings(INVOICE_FEISHU_SYNC_INTERVAL_SECONDS=600):
            register_periodic_tasks()

        entry = TASK_REGISTRY._entries["invoice_feishu_periodic_sync"]
        self.assertEqual(entry["task"], "invoice.tasks.dispatch_feishu_sync")
        self.assertEqual(entry["schedule"], 600)

    def test_invoice_user_can_start_and_read_sync_status(self):
        grantor = User.objects.create_user("invoice-sync-admin")
        user = User.objects.create_user("invoice-sync-user")
        InvoiceAccessGrant.objects.create(
            user=user,
            granted_by=grantor,
            role="invoice_user",
        )
        client = APIClient()
        client.force_authenticate(user)
        run = InvoiceSyncRun.objects.create(requested_by=user)

        with patch(
            "invoice.views.enqueue_invoice_feishu_sync",
            return_value=(run, False),
        ):
            started = client.post("/api/v1/invoice/feishu/sync")
        status = client.get("/api/v1/invoice/feishu/sync")

        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.data["id"], run.id)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.data["id"], run.id)
