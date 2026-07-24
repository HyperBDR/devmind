from datetime import date, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from quotation.metrics import export_metrics_snapshot
from quotation.models import (
    DocumentReplica,
    ExportJob,
    Quotation,
    QuotationTemplate,
    QuotationTemplateStatus,
    QuotationVersion,
    StorageConnection,
    StorageMount,
)
from quotation.services.export_archive import sync_export_asset
from quotation.services.export_jobs import create_export_job
from quotation.services.export_renderer import (
    build_default_template_bytes,
    ensure_default_template,
)
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.quotation_service import build_quotation_snapshot
from quotation.services.storage import resolve_document_path
from quotation.services.storage_control import FeishuStorageProvider
from quotation.tasks import render_quotation_export_task, sync_document_replica_task
from rest_framework.test import APIClient


class QuotationExportFixture(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.settings_override = override_settings(QUOTATION_STORAGE=self.storage.name)
        self.settings_override.enable()
        self.user = get_user_model().objects.create_user(
            username="export-owner@example.com",
            email="export-owner@example.com",
            password="password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-exporter@example.com",
            email="other-exporter@example.com",
            password="password",
        )
        today = date.today()
        self.quotation = Quotation.objects.create(
            quote_no="EXPORT-001",
            project_name="Async export",
            quote_date=today,
            expire_date=today + timedelta(days=30),
            issuer_contact_name="Owner",
            issuer_contact_email=self.user.email,
            client_company="Client",
            contact_person="Contact",
            email="contact@example.com",
            created_by_email=self.user.email,
            version_current=1,
        )
        self.version = QuotationVersion.objects.create(
            quotation=self.quotation,
            version_no=1,
            status="generated",
            snapshot_json=build_quotation_snapshot(self.quotation),
            operator_email=self.user.email,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        self.settings_override.disable()
        self.storage.cleanup()


class QuotationExportApiTests(QuotationExportFixture):

    @patch("quotation.tasks.render_quotation_export_task.apply_async")
    def test_create_export_pins_versions_and_enqueues_after_commit(
        self,
        apply_async,
    ):
        apply_async.return_value.id = "celery-task-id"

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
                {
                    "formats": ["xlsx", "pdf"],
                    "quotation_version": 1,
                    "archive_to_feishu": False,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 202)
        job = ExportJob.objects.select_related(
            "quotation_version",
            "template",
        ).get(pk=response.data["job_id"])
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.quotation_version, self.version)
        self.assertEqual(job.quotation_version_no, 1)
        self.assertEqual(job.template_version, job.template.version)
        self.assertEqual(job.formats, ["pdf", "xlsx"])
        self.assertNotEqual(job.idempotency_key, "")
        apply_async.assert_called_once_with(
            args=[job.id],
            queue="quotation_render",
        )

    @patch("quotation.tasks.render_quotation_export_task.apply_async")
    def test_repeated_request_reuses_the_same_export_job(self, apply_async):
        apply_async.return_value.id = "celery-task-id"
        payload = {
            "formats": ["xlsx"],
            "quotation_version": 1,
            "archive_to_feishu": False,
        }

        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(
                f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
                payload,
                format="json",
            )
        with self.captureOnCommitCallbacks(execute=True):
            second = self.client.post(
                f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
                payload,
                format="json",
            )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(first.data["job_id"], second.data["job_id"])
        self.assertEqual(ExportJob.objects.count(), 1)
        apply_async.assert_called_once()

    @patch(
        "quotation.tasks.render_quotation_export_task.apply_async",
        side_effect=RuntimeError("broker unavailable"),
    )
    def test_enqueue_failure_is_visible_and_can_be_retried(self, _apply):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
                {"formats": ["xlsx"], "quotation_version": 1},
                format="json",
            )

        job = ExportJob.objects.get(pk=response.data["job_id"])
        self.assertEqual(job.status, "render_failed")
        self.assertEqual(job.error_code, "export_enqueue_failed")

    @patch("quotation.tasks.render_quotation_export_task.apply_async")
    def test_export_without_version_snapshots_current_quote(self, apply_async):
        apply_async.return_value.id = "celery-task-id"
        self.quotation.project_name = "Current project"
        self.quotation.save(update_fields=["project_name", "updated_at"])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
                {"formats": ["xlsx"]},
                format="json",
            )

        job = ExportJob.objects.select_related("quotation_version").get(
            pk=response.data["job_id"]
        )
        self.assertEqual(
            job.quotation_version.snapshot_json["project_name"],
            "Current project",
        )
        self.assertEqual(job.quotation_version_no, 2)

    def test_export_status_is_visible_only_to_quote_owner(self):
        response = self.client.post(
            f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
            {"formats": ["xlsx"], "quotation_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 202)

        self.client.force_authenticate(self.other_user)
        denied = self.client.get(f"/api/v1/quotation/exports/{response.data['job_id']}")

        self.assertEqual(denied.status_code, 403)

    def test_export_rejects_unknown_quotation_version(self):
        response = self.client.post(
            f"/api/v1/quotation/quotations/{self.quotation.id}/exports",
            {"formats": ["xlsx"], "quotation_version": 99},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "quotation version not found",
        )

    def test_staff_can_upload_and_activate_a_versioned_template(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        previous = ensure_default_template(created_by=self.user)
        upload = SimpleUploadedFile(
            "quotation-v2.xlsx",
            build_default_template_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            "/api/v1/quotation/templates",
            {
                "name": previous.name,
                "version": 2,
                "status": "active",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        previous.refresh_from_db()
        template = QuotationTemplate.objects.get(pk=response.data["id"])
        self.assertEqual(previous.status, "archived")
        self.assertEqual(template.status, "active")
        self.assertTrue(resolve_document_path(template.storage_key).is_file())

    def test_database_allows_only_one_active_template(self):
        ensure_default_template(created_by=self.user)
        duplicate = QuotationTemplate(
            name="Concurrent active template",
            version=1,
            storage_key="templates/concurrent.xlsx",
            content_hash="a" * 64,
            status=QuotationTemplateStatus.ACTIVE,
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                duplicate.save(force_insert=True)

    def test_non_staff_cannot_manage_templates(self):
        response = self.client.get("/api/v1/quotation/templates")

        self.assertEqual(response.status_code, 403)


class QuotationExportTaskTests(QuotationExportFixture):
    def create_job(self, formats, *, archive_to_feishu=False):
        with patch("quotation.tasks.render_quotation_export_task.apply_async"):
            job, _ = create_export_job(
                quotation=self.quotation,
                formats=formats,
                actor=self.user,
                quotation_version_no=1,
                archive_to_feishu=archive_to_feishu,
            )
        return job

    @patch(
        "quotation.services.export_pipeline.convert_xlsx_to_pdf",
        return_value=b"%PDF-rendered",
    )
    def test_render_task_persists_versioned_assets(self, _convert):
        before = export_metrics_snapshot()
        job = self.create_job(["xlsx", "pdf"])
        self.quotation.project_name = "Changed after queue"
        self.quotation.save(update_fields=["project_name", "updated_at"])

        result = render_quotation_export_task.run(job.id)

        job.refresh_from_db()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(job.status, "completed")
        assets = {asset.doc_type: asset for asset in job.assets.all()}
        self.assertEqual(set(assets), {"excel", "pdf"})
        for asset in assets.values():
            self.assertEqual(asset.quotation_version, self.version)
            self.assertEqual(asset.template_version, job.template_version)
            self.assertEqual(asset.renderer_version, job.renderer_version)
            self.assertEqual(len(asset.content_hash), 64)
            self.assertTrue(resolve_document_path(asset.storage_key).is_file())
        self.assertTrue(
            resolve_document_path(assets["excel"].storage_key)
            .read_bytes()
            .startswith(b"PK\x03\x04")
        )
        self.assertTrue(
            resolve_document_path(assets["pdf"].storage_key)
            .read_bytes()
            .startswith(b"%PDF-")
        )

        render_quotation_export_task.run(job.id)
        self.assertEqual(job.assets.count(), 2)
        after = export_metrics_snapshot()
        self.assertGreater(
            after["durations"]["render"]["count"],
            before["durations"].get("render", {}).get("count", 0),
        )
        self.assertGreater(
            after["results"]["render"]["success"],
            before["results"].get("render", {}).get("success", 0),
        )

    @patch("quotation.tasks.sync_document_replica_task.apply_async")
    def test_render_queues_archive_only_after_assets_commit(self, apply_async):
        apply_async.return_value.id = "sync-task"
        job = self.create_job(["xlsx"], archive_to_feishu=True)

        with self.captureOnCommitCallbacks(execute=True):
            result = render_quotation_export_task.run(job.id)

        job.refresh_from_db()
        asset = job.assets.get()
        self.assertEqual(result["status"], "upload_queued")
        self.assertEqual(job.status, "upload_queued")
        apply_async.assert_called_once_with(
            args=[job.id, asset.id],
            queue="quotation_sync",
        )

    @patch(
        "quotation.tasks.sync_document_replica_task.apply_async",
        side_effect=RuntimeError("broker unavailable"),
    )
    def test_archive_enqueue_failure_keeps_rendered_assets(self, _apply):
        job = self.create_job(["xlsx"], archive_to_feishu=True)

        with self.captureOnCommitCallbacks(execute=True):
            render_quotation_export_task.run(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, "upload_failed")
        self.assertEqual(job.error_code, "archive_enqueue_failed")
        self.assertEqual(job.assets.count(), 1)
        self.assertTrue(resolve_document_path(job.assets.get().storage_key).is_file())

    def test_redelivered_render_recovers_an_in_progress_job(self):
        job = self.create_job(["xlsx"])
        ExportJob.objects.filter(pk=job.id).update(status="rendering_excel")

        result = render_quotation_export_task.run(job.id)

        job.refresh_from_db()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.assets.count(), 1)

    @patch(
        "quotation.services.export_pipeline.convert_xlsx_to_pdf",
        side_effect=ValueError("invalid PDF"),
    )
    def test_pdf_failure_creates_no_partial_excel_asset(self, _convert):
        job = self.create_job(["xlsx", "pdf"])

        with self.assertRaises(ValueError):
            render_quotation_export_task.run(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, "render_failed")
        self.assertEqual(job.assets.count(), 0)

    def create_storage_route(self):
        connection = StorageConnection.objects.create(
            display_name="Quotation archive",
            app_id="app-id",
            app_secret="app-secret",
            status="active",
            is_default=True,
        )
        return StorageMount.objects.create(
            connection=connection,
            root_folder_token="folder-token",
            root_folder_name="Archive",
            enabled=True,
            is_default=True,
        )

    def test_provider_reuses_same_name_when_mount_policy_requires_it(self):
        mount = self.create_storage_route()
        mount.conflict_policy = "reuse"
        mount.save(update_fields=["conflict_policy", "updated_at"])
        provider = FeishuStorageProvider(mount.connection)
        existing = {
            "token": "existing-token",
            "name": "Quote.xlsx",
            "type": "file",
            "url": "https://example.test/existing",
        }

        with patch.object(provider, "access_token", return_value="token"):
            with patch.object(
                provider.client,
                "list_folder_files",
                return_value={"files": [existing], "has_more": False},
            ):
                with patch.object(
                    provider.client,
                    "upload_file",
                ) as upload:
                    result = provider.upload(
                        mount,
                        file_name="Quote.xlsx",
                        content=b"xlsx",
                    )

        self.assertEqual(result["file_token"], "existing-token")
        self.assertTrue(result["reused"])
        upload.assert_not_called()

    def test_provider_renames_same_name_when_mount_policy_requires_it(self):
        mount = self.create_storage_route()
        provider = FeishuStorageProvider(mount.connection)
        files = [
            {"token": "one", "name": "Quote.xlsx", "type": "file"},
            {"token": "two", "name": "Quote (1).xlsx", "type": "file"},
        ]

        with patch.object(provider, "access_token", return_value="token"):
            with patch.object(
                provider.client,
                "list_folder_files",
                return_value={"files": files, "has_more": False},
            ):
                with patch.object(
                    provider.client,
                    "upload_file",
                    return_value={"file_token": "new-token"},
                ) as upload:
                    provider.upload(
                        mount,
                        file_name="Quote.xlsx",
                        content=b"xlsx",
                    )

        self.assertEqual(
            upload.call_args.kwargs["file_name"],
            "Quote (2).xlsx",
        )

    @patch("quotation.tasks.sync_document_replica_task.apply_async")
    def render_archived_job(self, _apply_async):
        job = self.create_job(["xlsx"], archive_to_feishu=True)
        render_quotation_export_task.run(job.id)
        return job, job.assets.get()

    @patch(
        "quotation.services.storage_control.FeishuStorageProvider.upload",
        return_value={"file_token": "remote-file", "url": "https://x"},
    )
    def test_replica_task_is_idempotent_by_content_hash(self, upload):
        self.create_storage_route()
        job, asset = self.render_archived_job()

        first = sync_document_replica_task.run(job.id, asset.id)
        second = sync_document_replica_task.run(job.id, asset.id)

        job.refresh_from_db()
        replica = DocumentReplica.objects.get(asset=asset)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "completed")
        self.assertEqual(job.status, "completed")
        self.assertEqual(replica.sync_status, "synced")
        self.assertEqual(replica.content_hash, asset.content_hash)
        upload.assert_called_once()

    @patch(
        "quotation.services.storage_control.FeishuStorageProvider.upload",
        side_effect=FeishuAPIError("permission denied", code=999),
    )
    def test_terminal_upload_failure_keeps_local_asset(self, _upload):
        self.create_storage_route()
        job, asset = self.render_archived_job()
        asset_path = resolve_document_path(asset.storage_key)

        result = sync_document_replica_task.run(job.id, asset.id)

        job.refresh_from_db()
        self.assertEqual(result["status"], "upload_failed")
        self.assertEqual(job.status, "upload_failed")
        self.assertEqual(job.error_code, "feishu_999")
        self.assertTrue(asset_path.is_file())
        self.assertEqual(job.assets.count(), 1)

    @patch(
        "quotation.services.storage_control.FeishuStorageProvider.upload",
        return_value={"file_token": "remote-file", "url": "https://x"},
    )
    @patch(
        "quotation.services.export_pipeline.convert_xlsx_to_pdf",
        return_value=b"%PDF-rendered",
    )
    def test_successful_sibling_upload_preserves_terminal_failure(
        self,
        _convert,
        _upload,
    ):
        mount = self.create_storage_route()
        job = self.create_job(["xlsx", "pdf"], archive_to_feishu=True)
        with patch("quotation.tasks.sync_document_replica_task.apply_async"):
            render_quotation_export_task.run(job.id)
        failed_asset = job.assets.get(doc_type="excel")
        successful_asset = job.assets.get(doc_type="pdf")
        DocumentReplica.objects.create(
            asset=failed_asset,
            connection=mount.connection,
            mount=mount,
            version=1,
            sync_status="failed",
        )
        ExportJob.objects.filter(pk=job.id).update(
            status="upload_failed",
            error_code="feishu_999",
            error_message="Remote quotation archiving failed",
        )

        result = sync_export_asset(job.id, successful_asset.id)

        job.refresh_from_db()
        self.assertEqual(result["status"], "upload_failed")
        self.assertEqual(job.status, "upload_failed")
        self.assertEqual(job.error_code, "feishu_999")

    @patch("quotation.tasks.sync_document_replica_task.apply_async")
    def test_retry_upload_requeues_existing_assets_only(self, apply_async):
        job = self.create_job(["xlsx"])
        render_quotation_export_task.run(job.id)
        asset = job.assets.get()
        ExportJob.objects.filter(pk=job.id).update(
            status="upload_failed",
            archive_to_feishu=True,
            error_code="feishu_999",
        )
        apply_async.return_value.id = "retry-task"

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/quotation/exports/{job.id}/retry-upload",
                {},
                format="json",
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "upload_queued")
        apply_async.assert_called_once_with(
            args=[job.id, asset.id],
            queue="quotation_sync",
        )
        self.assertEqual(job.assets.count(), 1)
