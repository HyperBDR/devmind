import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentType,
    Quotation,
    RemoteFileCleanup,
)
from rest_framework.test import APIClient


class DocumentLifecycleApiTests(TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.storage = Path(self._temp.name)
        self.settings_override = self.settings(
            QUOTATION_STORAGE=str(self.storage),
            QUOTATION_DOCUMENT_RETENTION_DAYS=30,
        )
        self.settings_override.enable()
        self.user = User.objects.create_user(
            username="lifecycle-owner",
            email="lifecycle@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.quotation = Quotation.objects.create(
            quote_no="Q-LIFECYCLE-001",
            source_type="document_import",
            project_name="Lifecycle policy",
            payment_terms="CIA",
            quote_date="2026-08-18",
            expire_date="2026-09-18",
            issuer_contact_name="Lifecycle Owner",
            issuer_contact_email=self.user.email,
            client_company="Example",
            contact_person="Customer",
            email="customer@example.com",
            created_by_email=self.user.email,
        )
        self.asset = self.create_asset(
            asset_id="lifecycle-source",
            file_name="source.xlsx",
            source="feishu",
        )
        self.generated_asset = self.create_asset(
            asset_id="lifecycle-generated",
            file_name="generated.pdf",
            source="local",
        )

    def tearDown(self):
        self.settings_override.disable()
        self._temp.cleanup()

    def create_asset(
        self,
        *,
        asset_id: str,
        file_name: str,
        source: str,
    ) -> DocumentAsset:
        storage_key = f"documents/{self.quotation.id}/{asset_id}"
        path = self.storage / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_name.encode())
        return DocumentAsset.objects.create(
            id=asset_id,
            quotation=self.quotation,
            doc_type=(
                DocumentType.EXCEL
                if file_name.endswith(".xlsx")
                else DocumentType.PDF
            ),
            file_name=file_name,
            mime_type="application/octet-stream",
            storage_key=storage_key,
            size_bytes=path.stat().st_size,
            source=source,
            created_by_email=self.user.email,
        )

    def test_archive_hides_document_and_preserves_recoverable_assets(self):
        response = self.api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}",
            {"reason": "duplicate upload"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["document"]["lifecycle_state"], "archived"
        )
        self.assertEqual(response.data["impact"]["quotation"], "archived")
        self.assertEqual(response.data["impact"]["versions"], "retained")
        self.assertEqual(response.data["impact"]["assets_affected"], 2)
        self.asset.refresh_from_db()
        self.generated_asset.refresh_from_db()
        self.quotation.refresh_from_db()
        self.assertEqual(self.asset.lifecycle_state, "archived")
        self.assertEqual(self.generated_asset.lifecycle_state, "archived")
        self.assertIsNotNone(self.asset.purge_after)
        self.assertIsNotNone(self.quotation.archived_at)
        self.assertTrue((self.storage / self.asset.storage_key).exists())
        self.assertTrue(
            (self.storage / self.generated_asset.storage_key).exists()
        )

        active = self.api.get("/api/v1/quotation/documents?source=feishu")
        archived = self.api.get(
            "/api/v1/quotation/documents?source=feishu&lifecycle=archived"
        )
        download = self.api.get(
            f"/api/v1/quotation/documents/{self.asset.id}/download"
        )

        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.data, [])
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(
            [item["id"] for item in archived.data], [self.asset.id]
        )
        self.assertEqual(download.status_code, 409)
        quote_detail = self.api.get(
            f"/api/v1/quotation/quotations/{self.quotation.id}"
        )
        self.assertEqual(quote_detail.status_code, 403)
        archive_event = AuditEvent.objects.get(
            module="document",
            action="archive",
        )
        self.assertEqual(archive_event.event_name, "document.archived")

    def test_restore_recovers_document_group_before_purge(self):
        archived = self.api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}"
        )
        self.assertEqual(archived.status_code, 200)

        restored = self.api.post(
            f"/api/v1/quotation/documents/{self.asset.id}/restore",
            {},
            format="json",
        )

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(
            restored.data["document"]["lifecycle_state"], "active"
        )
        self.asset.refresh_from_db()
        self.generated_asset.refresh_from_db()
        self.quotation.refresh_from_db()
        self.assertEqual(self.asset.lifecycle_state, "active")
        self.assertEqual(self.generated_asset.lifecycle_state, "active")
        self.assertIsNone(self.asset.purge_after)
        self.assertIsNone(self.quotation.archived_at)
        restore_event = AuditEvent.objects.get(
            module="document",
            action="restore",
        )
        self.assertEqual(restore_event.event_name, "document.restored")

    def test_archive_without_quotation_remains_recoverable(self):
        storage_key = "documents/unassigned-source"
        path = self.storage / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unassigned")
        asset = DocumentAsset.objects.create(
            id="unassigned-source",
            doc_type=DocumentType.EXCEL,
            file_name="unassigned.xlsx",
            mime_type="application/octet-stream",
            storage_key=storage_key,
            size_bytes=path.stat().st_size,
            source="feishu",
            created_by_email=self.user.email,
        )

        response = self.api.delete(f"/api/v1/quotation/documents/{asset.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["impact"]["quotation"], "retained")
        asset.refresh_from_db()
        self.assertEqual(asset.lifecycle_state, "archived")
        self.assertTrue(path.exists())

    def test_repeated_archive_does_not_extend_retention(self):
        first = self.api.delete(f"/api/v1/quotation/documents/{self.asset.id}")
        self.assertEqual(first.status_code, 200)
        first_purge_after = first.data["document"]["purge_after"]

        second = self.api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}"
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["impact"]["assets_affected"], 0)
        self.assertEqual(
            second.data["document"]["purge_after"],
            first_purge_after,
        )

    def test_other_user_cannot_archive_or_restore_document(self):
        other = User.objects.create_user(
            username="lifecycle-other",
            email="lifecycle-other@example.com",
            password="password",
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other)

        archived = other_api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}"
        )

        self.assertEqual(archived.status_code, 403)
        self.assertTrue(
            DocumentAsset.objects.filter(pk=self.asset.id).exists()
        )

        self.api.delete(f"/api/v1/quotation/documents/{self.asset.id}")
        restored = other_api.post(
            f"/api/v1/quotation/documents/{self.asset.id}/restore",
            {},
            format="json",
        )
        self.assertEqual(restored.status_code, 403)

    def test_legal_hold_blocks_archive(self):
        self.asset.legal_hold_at = timezone.now()
        self.asset.legal_hold_reason = "contract dispute"
        self.asset.save(update_fields=["legal_hold_at", "legal_hold_reason"])

        response = self.api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "legal_hold")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.lifecycle_state, "active")

    def test_restore_rejects_expired_retention_window(self):
        archived = self.api.delete(
            f"/api/v1/quotation/documents/{self.asset.id}"
        )
        self.assertEqual(archived.status_code, 200)
        DocumentAsset.objects.filter(pk=self.asset.id).update(
            purge_after=timezone.now() - timedelta(seconds=1)
        )

        response = self.api.post(
            f"/api/v1/quotation/documents/{self.asset.id}/restore",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "retention_expired")


class DocumentRetentionPurgeTests(TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.storage = Path(self._temp.name)
        self.settings_override = self.settings(
            QUOTATION_STORAGE=str(self.storage),
        )
        self.settings_override.enable()
        self.quotation = Quotation.objects.create(
            quote_no="Q-PURGE-001",
            source_type="document_import",
            project_name="Retention purge",
            payment_terms="CIA",
            quote_date="2026-08-18",
            expire_date="2026-09-18",
            issuer_contact_name="Lifecycle Owner",
            issuer_contact_email="lifecycle@example.com",
            client_company="Example",
            contact_person="Customer",
            email="customer@example.com",
            created_by_email="lifecycle@example.com",
        )
        self.asset = self.create_archived_asset(
            "purge-source",
            "source.xlsx",
            "feishu",
        )
        self.generated_asset = self.create_archived_asset(
            "purge-generated",
            "generated.pdf",
            "local",
        )

    def tearDown(self):
        self.settings_override.disable()
        self._temp.cleanup()

    def create_archived_asset(
        self,
        asset_id: str,
        file_name: str,
        source: str,
    ) -> DocumentAsset:
        storage_key = f"documents/{self.quotation.id}/{asset_id}"
        path = self.storage / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_name.encode())
        return DocumentAsset.objects.create(
            id=asset_id,
            quotation=self.quotation,
            doc_type=(
                DocumentType.EXCEL
                if file_name.endswith(".xlsx")
                else DocumentType.PDF
            ),
            file_name=file_name,
            mime_type="application/octet-stream",
            storage_key=storage_key,
            size_bytes=path.stat().st_size,
            source=source,
            created_by_email="lifecycle@example.com",
            lifecycle_state="archived",
            archived_at=timezone.now() - timedelta(days=31),
            purge_after=timezone.now() - timedelta(seconds=1),
        )

    def test_dry_run_reports_candidates_without_deleting(self):
        from quotation.services.document_lifecycle import (
            purge_archived_documents,
        )

        result = purge_archived_documents(dry_run=True, batch_size=1)

        self.assertEqual(result["eligible"], 2)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["purged"], 0)
        self.assertTrue(
            DocumentAsset.objects.filter(pk=self.asset.id).exists()
        )
        self.assertTrue((self.storage / self.asset.storage_key).exists())

    def test_purge_honors_batch_limit_and_removes_local_content(self):
        from quotation.services.document_lifecycle import (
            purge_archived_documents,
        )

        result = purge_archived_documents(dry_run=False, batch_size=1)

        self.assertEqual(result["eligible"], 2)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["purged"], 1)
        self.assertEqual(DocumentAsset.objects.count(), 1)

    def test_purge_skips_legal_hold(self):
        from quotation.services.document_lifecycle import (
            purge_archived_documents,
        )

        DocumentAsset.objects.filter(pk=self.asset.id).update(
            legal_hold_at=timezone.now(),
            legal_hold_reason="investigation",
        )

        result = purge_archived_documents(dry_run=False, batch_size=10)

        self.assertEqual(result["eligible"], 0)
        self.assertEqual(result["purged"], 0)
        self.assertTrue(
            DocumentAsset.objects.filter(pk=self.asset.id).exists()
        )
        self.assertTrue(
            DocumentAsset.objects.filter(pk=self.generated_asset.id).exists()
        )

    def test_purge_does_not_delete_unowned_remote_file(self):
        from quotation.services.document_lifecycle import (
            purge_archived_documents,
        )

        self.asset.feishu_file_token = "shared-remote-file"
        self.asset.save(update_fields=["feishu_file_token"])

        result = purge_archived_documents(dry_run=False, batch_size=1)

        self.assertEqual(result["purged"], 1)
        self.assertFalse(
            RemoteFileCleanup.objects.filter(
                remote_file_token="shared-remote-file"
            ).exists()
        )

    def test_management_command_rejects_invalid_batch_size(self):
        with self.assertRaises(CommandError):
            call_command(
                "purge_quotation_documents",
                batch_size=0,
                stdout=StringIO(),
            )
