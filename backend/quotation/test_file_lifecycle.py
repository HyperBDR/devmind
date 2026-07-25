from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from quotation.models import (
    DocumentAsset,
    DocumentReplica,
    Quotation,
    StorageConnection,
    StorageMount,
)
from quotation.services.storage import document_storage_key, write_document
from rest_framework.test import APIClient


def create_quote(user):
    today = date.today()
    return Quotation.objects.create(
        quote_no="DELETE-FILES-001",
        project_name="Storage cleanup",
        quote_date=today,
        expire_date=today + timedelta(days=30),
        issuer_contact_name="Owner",
        issuer_contact_email=user.email,
        client_company="Client",
        contact_person="Contact",
        email="contact@example.com",
        created_by_email=user.email,
    )


class QuotationFileLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="file-owner@example.com",
            email="file-owner@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_deleting_quotation_removes_document_after_commit(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(QUOTATION_STORAGE=storage_root):
                quote = create_quote(self.user)
                asset = DocumentAsset.objects.create(
                    quotation=quote,
                    doc_type="pdf",
                    file_name="quote.pdf",
                    mime_type="application/pdf",
                    storage_key=document_storage_key(
                        "11111111-1111-1111-1111-111111111111", quote.id
                    ),
                    size_bytes=4,
                    created_by_email=self.user.email,
                )
                path = write_document(b"%PDF", asset.storage_key)
                self.assertTrue(path.exists())

                with self.captureOnCommitCallbacks(execute=True):
                    response = self.api.delete(
                        f"/api/v1/quotation/quotations/{quote.id}"
                    )

                self.assertEqual(response.status_code, 204)
                self.assertFalse(Path(path).exists())

    def test_missing_document_file_does_not_block_quotation_delete(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(QUOTATION_STORAGE=storage_root):
                quote = create_quote(self.user)
                DocumentAsset.objects.create(
                    quotation=quote,
                    doc_type="pdf",
                    file_name="missing.pdf",
                    mime_type="application/pdf",
                    storage_key=document_storage_key(
                        "22222222-2222-2222-2222-222222222222", quote.id
                    ),
                    size_bytes=0,
                    created_by_email=self.user.email,
                )

                with self.captureOnCommitCallbacks(execute=True):
                    response = self.api.delete(
                        f"/api/v1/quotation/quotations/{quote.id}"
                    )

                self.assertEqual(response.status_code, 204)
                self.assertFalse(Quotation.objects.filter(pk=quote.pk).exists())

    def test_remote_cleanup_callback_failure_does_not_skip_local_cleanup(self):
        with TemporaryDirectory() as storage_root:
            with override_settings(QUOTATION_STORAGE=storage_root):
                quote = create_quote(self.user)
                asset = DocumentAsset.objects.create(
                    quotation=quote,
                    doc_type="pdf",
                    file_name="quote.pdf",
                    mime_type="application/pdf",
                    storage_key=document_storage_key(
                        "33333333-3333-3333-3333-333333333333",
                        quote.id,
                    ),
                    size_bytes=4,
                    created_by_email=self.user.email,
                )
                connection = StorageConnection.objects.create(
                    display_name="Cleanup failure archive",
                    app_id="app-id",
                    app_secret="app-secret",
                )
                mount = StorageMount.objects.create(
                    connection=connection,
                    root_folder_token="folder-token",
                )
                DocumentReplica.objects.create(
                    asset=asset,
                    connection=connection,
                    mount=mount,
                    remote_file_token="cleanup-failure-token",
                    metadata={"remote_file_owned": True},
                )
                path = write_document(b"%PDF", asset.storage_key)
                patcher = patch(
                    "quotation.services.storage_control."
                    "RemoteFileCleanup.objects.filter",
                    side_effect=OperationalError("database unavailable"),
                )
                try:
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.api.delete(
                            f"/api/v1/quotation/quotations/{quote.id}"
                        )
                        patcher.start()
                finally:
                    patcher.stop()

                self.assertEqual(response.status_code, 204)
                self.assertFalse(Path(path).exists())
