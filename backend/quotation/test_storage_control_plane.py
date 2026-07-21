from datetime import timedelta
from io import StringIO
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from quotation.metrics import storage_metrics_snapshot
from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentReplica,
    DocumentType,
    ReplicaSyncStatus,
    StorageAuthMode,
    StorageConnection,
    StorageMount,
    StorageMountPurpose,
    SyncJob,
)
from quotation.services.feishu_client import FeishuAPIError, _external_call
from quotation.services.storage_control import (
    FeishuStorageProvider,
    StorageRoute,
    StorageRouter,
    register_uploaded_replica,
)


class StorageControlPlaneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="storage-admin",
            email="storage@example.com",
            password="password",
        )
        self.connection = StorageConnection.objects.create(
            display_name="Feishu Organization A",
            external_tenant_id="tenant-a",
            app_id="app-a",
            app_secret="secret-a",
            is_default=True,
        )
        self.mount = StorageMount.objects.create(
            connection=self.connection,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            root_folder_token="folder-a",
            root_folder_name="Quotation Archive",
            is_default=True,
        )

    def test_connection_credentials_are_encrypted_at_rest(self):
        stored = StorageConnection.objects.get(pk=self.connection.pk)

        self.assertTrue(stored.app_secret.startswith("enc::"))
        self.assertNotIn("secret-a", stored.app_secret)
        self.assertEqual(stored.get_app_secret(), "secret-a")

    def test_router_prefers_document_specific_mount(self):
        typed = StorageMount.objects.create(
            connection=self.connection,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            document_type=DocumentType.PDF,
            root_folder_token="pdf-folder",
        )

        route = StorageRouter().resolve(document_type=DocumentType.PDF)

        self.assertEqual(route.mount, typed)
        self.assertEqual(route.connection, self.connection)

    def test_existing_upload_registers_replica_job_and_audit(self):
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/quote.pdf",
            source="feishu_upload",
            feishu_file_token="file-a",
            feishu_url="https://example.feishu.cn/file/file-a",
        )
        request = RequestFactory().post("/api/v1/quotation/feishu/upload")
        request.user = self.user
        request.audit_request_id = "request-replica"
        request.audit_trace_id = "trace-replica"
        route = StorageRoute(
            connection=self.connection,
            mount=self.mount,
            provider=StorageRouter().resolve().provider,
        )

        replica = register_uploaded_replica(
            request=request,
            asset=asset,
            route=route,
            remote_file_token="file-a",
            remote_url="https://example.feishu.cn/file/file-a",
            folder_token="folder-a",
        )

        self.assertEqual(replica.sync_status, ReplicaSyncStatus.SYNCED)
        job = SyncJob.objects.get(replica=replica)
        self.assertEqual(job.request_id, "request-replica")
        self.assertEqual(job.trace_id, "trace-replica")
        self.assertEqual(job.storage_connection, self.connection)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_name="document.replica_sync_succeeded",
                storage_connection_id=self.connection.id,
                sync_job_id=job.id,
            ).exists()
        )

    def test_external_call_records_low_cardinality_metrics(self):
        with _external_call("GET drive.file.meta", self.connection.id):
            pass

        snapshot = storage_metrics_snapshot()

        self.assertTrue(
            any(
                row["provider"] == "feishu"
                and row["operation"] == "GET drive.file.meta"
                and row["result"] == "success"
                for row in snapshot["requests"]
            )
        )

    def test_managed_credential_refresh_failure_is_audited_and_alerted(self):
        connection = StorageConnection.objects.create(
            display_name="Managed account",
            external_tenant_id="managed-account",
            auth_mode=StorageAuthMode.MANAGED_ACCOUNT,
            access_token="expired-token",
            refresh_token="refresh-token",
            token_expires_at=timezone.now() - timedelta(minutes=1),
        )
        provider = FeishuStorageProvider(connection)
        provider.client.refresh_user_token = Mock(
            side_effect=FeishuAPIError("refresh failed", code=10014)
        )

        with self.assertRaises(FeishuAPIError):
            provider.access_token()

        event = AuditEvent.objects.get(
            event_name="feishu.oauth.refresh_failed"
        )
        self.assertEqual(event.storage_connection_id, connection.id)
        self.assertEqual(event.error_code, "feishu_10014")
        self.assertTrue(
            event.security_alerts.filter(
                rule="credential_refresh_failure"
            ).exists()
        )

    @override_settings(
        FEISHU_APP_ID="legacy-app",
        FEISHU_APP_SECRET="legacy-secret",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="legacy-folder-token",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_URL="",
        FEISHU_TEST_FOLDER_TOKEN="",
    )
    def test_legacy_mapping_migration_is_reversible(self):
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.EXCEL,
            file_name="Legacy.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
            storage_key="legacy.xlsx",
            source="feishu_upload",
            feishu_file_token="legacy-file-token",
            feishu_url="https://example.feishu.cn/file/legacy-file-token",
        )

        call_command(
            "migrate_feishu_control_plane",
            "--apply",
            stdout=StringIO(),
        )

        self.assertTrue(DocumentReplica.objects.filter(asset=asset).exists())

        call_command(
            "migrate_feishu_control_plane",
            "--rollback",
            stdout=StringIO(),
        )
        asset.refresh_from_db()
        self.assertFalse(DocumentReplica.objects.filter(asset=asset).exists())
        self.assertEqual(asset.feishu_file_token, "legacy-file-token")

    @override_settings(
        FEISHU_APP_ID="",
        FEISHU_APP_SECRET="",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_URL="",
        FEISHU_TEST_FOLDER_TOKEN="",
    )
    def test_legacy_mapping_skips_when_archive_is_not_configured(self):
        output = StringIO()
        connection_count = StorageConnection.objects.count()
        mount_count = StorageMount.objects.count()

        call_command(
            "migrate_feishu_control_plane",
            "--apply",
            stdout=output,
        )

        self.assertIn("SKIPPED", output.getvalue())
        self.assertEqual(StorageConnection.objects.count(), connection_count)
        self.assertEqual(StorageMount.objects.count(), mount_count)
        self.assertFalse(
            StorageConnection.objects.filter(
                external_tenant_id="legacy-default"
            ).exists()
        )

    @override_settings(
        FEISHU_APP_ID="new-app",
        FEISHU_APP_SECRET="new-secret",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="new-folder-token",
        QUOTATION_FEISHU_ARCHIVE_FOLDER_URL="",
        FEISHU_TEST_FOLDER_TOKEN="",
    )
    def test_legacy_mapping_migration_refreshes_default_route(self):
        connection = StorageConnection.objects.create(
            provider="feishu",
            external_tenant_id="legacy-default",
            display_name="Legacy Feishu archive",
            app_id="old-app",
            app_secret="old-secret",
        )
        mount = StorageMount.objects.create(
            connection=connection,
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            root_folder_token="old-folder-token",
            root_folder_name="Old archive",
        )

        call_command(
            "migrate_feishu_control_plane",
            "--apply",
            stdout=StringIO(),
        )

        connection.refresh_from_db()
        mount.refresh_from_db()
        self.assertEqual(connection.app_id, "new-app")
        self.assertEqual(connection.get_app_secret(), "new-secret")
        self.assertTrue(connection.is_default)
        self.assertEqual(mount.root_folder_token, "new-folder-token")
        self.assertEqual(mount.root_folder_name, "Configured archive folder")
        self.assertTrue(mount.is_default)
