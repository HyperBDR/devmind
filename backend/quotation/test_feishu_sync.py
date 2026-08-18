import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.periodic_registry import TASK_REGISTRY
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from quotation.models import (
    DocumentAsset,
    DocumentType,
    FeishuFileSnapshot,
    FeishuSyncDifference,
    FeishuSyncDifferenceStatus,
    FeishuSyncDifferenceType,
    FeishuSyncState,
    FeishuSyncStatus,
    SyncJob,
    SyncJobStatus,
    SyncJobType,
)
from quotation.periodic_tasks import register_periodic_tasks
from quotation.services.feishu_client import FeishuAPIError
from quotation.services.feishu_sync import authorized_sync_targets
from quotation.services.storage import write_document
from quotation.tasks import (
    _mark_feishu_sync_states_failed,
    dispatch_feishu_sync,
    sync_feishu_folder_task,
)
from quotation.views.feishu.files import FeishuFolderSyncView
from rest_framework.test import APIClient


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    FEISHU_APP_ID="sync-app",
    FEISHU_APP_SECRET="sync-secret",
    QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN="folder-root",
    QUOTATION_STORAGE_ROUTER_ENABLED=False,
)
class FeishuAutomaticSyncTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_override = override_settings(
            QUOTATION_STORAGE=self.temp_dir.name,
        )
        self.storage_override.enable()
        self.user = User.objects.create_user(
            username="sync-admin",
            email="sync-admin@example.com",
            password="password",
            is_staff=True,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        cache.clear()

    def tearDown(self):
        cache.clear()
        self.storage_override.disable()
        self.temp_dir.cleanup()

    def create_remote_asset(self, *, modified_time="100"):
        asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/remote/quote.pdf",
            size_bytes=8,
            source="feishu",
            feishu_file_token="file-1",
            feishu_folder_token="folder-root",
            feishu_folder_path=[
                {"token": "folder-root", "name": "Quotation Archive"}
            ],
            created_by_email=self.user.email,
        )
        write_document(b"old-file", asset.storage_key)
        state = FeishuSyncState.objects.create(
            requested_by=self.user,
            root_folder_token="folder-root",
            root_folder_name="Quotation Archive",
            status=FeishuSyncStatus.SYNCED,
        )
        fingerprint = f"file-1|folder-root|Quote.pdf|8|{modified_time}"
        snapshot = FeishuFileSnapshot.objects.create(
            state=state,
            asset=asset,
            remote_file_token="file-1",
            folder_token="folder-root",
            folder_path=asset.feishu_folder_path,
            file_name=asset.file_name,
            file_type="file",
            size_bytes=asset.size_bytes,
            modified_time=modified_time,
            metadata_fingerprint=fingerprint,
        )
        return asset, state, snapshot

    def test_modified_file_reuses_asset_and_enqueues_one_new_parse(self):
        asset, _state, _snapshot = self.create_remote_asset()
        downloads = []

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [
                        {
                            "token": "file-1",
                            "name": "Quote.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "200",
                        }
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                downloads.append(kwargs["file_token"])
                return b"new-file", "application/pdf", "Quote.pdf"

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            with patch(
                "quotation.views.feishu.files.parse_and_create_quotation",
                return_value=(
                    SimpleNamespace(
                        status="not_quotation",
                        quotation_id=None,
                    ),
                    False,
                ),
            ) as parse_document:
                response = self.api.post(
                    "/api/v1/quotation/feishu/sync-folder",
                    {"async": False},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.id, DocumentAsset.objects.get().id)
        self.assertEqual(
            (Path(self.temp_dir.name) / asset.storage_key).read_bytes(),
            b"new-file",
        )
        self.assertEqual(downloads, ["file-1"])
        parse_document.assert_called_once()
        difference = FeishuSyncDifference.objects.get(
            difference_type=FeishuSyncDifferenceType.MODIFIED
        )
        self.assertEqual(
            difference.status,
            FeishuSyncDifferenceStatus.APPLIED,
        )

    def test_deleted_file_is_marked_without_hard_deleting_local_asset(self):
        asset, state, snapshot = self.create_remote_asset()

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {"files": [], "has_more": False}

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/sync-folder",
                {"async": False},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(DocumentAsset.objects.filter(pk=asset.pk).exists())
        snapshot.refresh_from_db()
        state.refresh_from_db()
        self.assertTrue(snapshot.deleted_in_feishu)
        self.assertEqual(state.status, FeishuSyncStatus.HAS_DIFF)
        difference = FeishuSyncDifference.objects.get(
            difference_type=FeishuSyncDifferenceType.DELETED
        )
        self.assertEqual(
            difference.status,
            FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
        )

    def test_incomplete_pagination_does_not_mark_unseen_files_deleted(self):
        asset, state, snapshot = self.create_remote_asset()

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [],
                    "has_more": True,
                    "next_page_token": None,
                }

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = self.api.post(
                "/api/v1/quotation/feishu/sync-folder",
                {"async": False},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(DocumentAsset.objects.filter(pk=asset.pk).exists())
        snapshot.refresh_from_db()
        state.refresh_from_db()
        self.assertFalse(snapshot.deleted_in_feishu)
        self.assertEqual(state.status, FeishuSyncStatus.FAILED)
        self.assertFalse(
            FeishuSyncDifference.objects.filter(
                difference_type=FeishuSyncDifferenceType.DELETED
            ).exists()
        )

    def test_moved_and_renamed_file_updates_snapshot_and_asset(self):
        asset, _state, snapshot = self.create_remote_asset()

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                if folder_token == "folder-root":
                    return {
                        "files": [
                            {
                                "token": "folder-child",
                                "name": "FY2026",
                                "type": "folder",
                            }
                        ],
                        "has_more": False,
                    }
                return {
                    "files": [
                        {
                            "token": "file-1",
                            "name": "Renamed Quote.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "100",
                        }
                    ],
                    "has_more": False,
                }

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            with patch(
                "quotation.views.feishu.files.parse_and_create_quotation",
                return_value=(
                    SimpleNamespace(
                        status="not_quotation",
                        quotation_id=None,
                    ),
                    False,
                ),
            ):
                response = self.api.post(
                    "/api/v1/quotation/feishu/sync-folder",
                    {"async": False},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        asset.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(asset.file_name, "Renamed Quote.pdf")
        self.assertEqual(asset.feishu_folder_token, "folder-child")
        self.assertEqual(snapshot.file_name, "Renamed Quote.pdf")
        self.assertEqual(snapshot.folder_token, "folder-child")
        self.assertSetEqual(
            set(
                FeishuSyncDifference.objects.values_list(
                    "difference_type",
                    flat=True,
                )
            ),
            {
                FeishuSyncDifferenceType.MOVED,
                FeishuSyncDifferenceType.RENAMED,
            },
        )

    def test_permission_and_missing_errors_have_distinct_states(self):
        class FakeClient:
            def __init__(self, error):
                self.error = error

            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                raise self.error

        cases = (
            (
                FeishuAPIError("permission denied", code=99991663),
                502,
                FeishuSyncStatus.PERMISSION,
            ),
            (
                FeishuAPIError("folder does not exist", code=1069645),
                404,
                FeishuSyncStatus.MISSING,
            ),
        )
        for error, expected_code, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                with patch(
                    "quotation.views.feishu.common._client",
                    return_value=FakeClient(error),
                ):
                    response = self.api.post(
                        "/api/v1/quotation/feishu/sync-folder",
                        {"async": False},
                        format="json",
                    )
                self.assertEqual(response.status_code, expected_code)
                self.assertEqual(
                    FeishuSyncState.objects.get().status,
                    expected_status,
                )

    def test_partial_failure_can_retry_without_duplicate_assets(self):
        fail_second_download = True

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [
                        {
                            "token": "file-1",
                            "name": "Quote 1.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "100",
                        },
                        {
                            "token": "file-2",
                            "name": "Quote 2.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "100",
                        },
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                nonlocal fail_second_download
                if kwargs["file_token"] == "file-2" and fail_second_download:
                    fail_second_download = False
                    raise FeishuAPIError("temporary timeout")
                return b"pdf-file", "application/pdf", kwargs["file_name"]

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            with patch(
                "quotation.views.feishu.files.parse_and_create_quotation",
                return_value=(
                    SimpleNamespace(
                        status="not_quotation",
                        quotation_id=None,
                    ),
                    False,
                ),
            ):
                first = self.api.post(
                    "/api/v1/quotation/feishu/sync-folder",
                    {"async": False},
                    format="json",
                )
                second = self.api.post(
                    "/api/v1/quotation/feishu/sync-folder",
                    {"async": False},
                    format="json",
                )

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(len(first.data["errors"]), 1)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["errors"], [])
        self.assertEqual(DocumentAsset.objects.count(), 2)
        self.assertEqual(
            DocumentAsset.objects.values("feishu_file_token")
            .distinct()
            .count(),
            2,
        )
        self.assertEqual(FeishuFileSnapshot.objects.count(), 2)

    def test_repeated_discovery_enqueues_only_one_parse_job(self):
        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [
                        {
                            "token": "parse-file",
                            "name": "Parse Once.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "100",
                        }
                    ],
                    "has_more": False,
                }

            def download_drive_item(self, access_token, **kwargs):
                return b"pdf-file", "application/pdf", kwargs["file_name"]

        request = SimpleNamespace(user=self.user)
        target = {"folder_token": "folder-root"}
        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            with patch(
                "quotation.tasks.parse_document_task.apply_async"
            ) as enqueue_parse:
                first = FeishuFolderSyncView()._sync(
                    request,
                    enqueue_parsing=True,
                    targets=[target],
                )
                second = FeishuFolderSyncView()._sync(
                    request,
                    enqueue_parsing=True,
                    targets=[target],
                )

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["queued_parse_count"], 1)
        self.assertEqual(second.data["queued_parse_count"], 0)
        self.assertEqual(DocumentAsset.objects.count(), 1)
        enqueue_parse.assert_called_once()

    def test_login_trigger_reuses_an_active_sync_job(self):
        with patch(
            "quotation.tasks.sync_feishu_folder_task.apply_async"
        ) as enqueue:
            enqueue.return_value.id = "celery-sync"
            first = self.api.post("/api/v1/quotation/feishu/sync-on-login")
            second = self.api.post("/api/v1/quotation/feishu/sync-on-login")

        self.assertEqual(first.status_code, 202, first.data)
        self.assertEqual(second.status_code, 202, second.data)
        self.assertEqual(first.data["sync_job_id"], second.data["sync_job_id"])
        self.assertEqual(SyncJob.objects.count(), 1)
        enqueue.assert_called_once()

    def test_same_folder_uses_one_state_across_sync_actors(self):
        asset, state, snapshot = self.create_remote_asset()
        regular = User.objects.create_user(
            username="regular-user",
            email="regular@example.com",
            password="password",
        )
        asset.created_by_email = regular.email
        asset.save(update_fields=["created_by_email"])
        self.api.force_authenticate(regular)

        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": "Quotation Archive"}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                return {
                    "files": [
                        {
                            "token": "file-1",
                            "name": "Quote.pdf",
                            "type": "file",
                            "size": 8,
                            "modified_time": "100",
                        }
                    ],
                    "has_more": False,
                }

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            with patch(
                "quotation.views.feishu.files.parse_and_create_quotation",
                return_value=(
                    SimpleNamespace(
                        status="not_quotation",
                        quotation_id=None,
                    ),
                    False,
                ),
            ):
                response = self.api.post(
                    "/api/v1/quotation/feishu/sync-folder",
                    {"async": False},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        snapshot.refresh_from_db()
        self.assertEqual(FeishuSyncState.objects.count(), 1)
        self.assertEqual(snapshot.state_id, state.id)

    def test_regular_user_sync_targets_are_limited_to_owned_folders(self):
        regular = User.objects.create_user(
            username="folder-owner",
            email="owner@example.com",
            password="password",
        )
        self.assertEqual(authorized_sync_targets(regular), [])
        DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="Owned.pdf",
            mime_type="application/pdf",
            storage_key="documents/owned.pdf",
            size_bytes=1,
            source="feishu",
            feishu_file_token="owned-file",
            feishu_folder_token="owned-folder",
            created_by_email=regular.email,
        )

        targets = authorized_sync_targets(regular)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].folder_token, "owned-folder")

    def test_timeout_marks_async_sync_for_retry(self):
        job = SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.QUEUED,
            actor=self.user,
            payload_json={
                "targets": [{"folder_token": "folder-root"}],
            },
        )
        with patch(
            "quotation.views.feishu.files.FeishuFolderSyncView._sync",
            side_effect=TimeoutError("Feishu timed out"),
        ):
            with self.assertRaises(TimeoutError):
                sync_feishu_folder_task.run(job.id, self.user.id)

        job.refresh_from_db()
        self.assertEqual(job.status, SyncJobStatus.RETRYING)
        self.assertEqual(job.error_code, "folder_sync_retry")

    def test_exhausted_async_failure_updates_folder_state(self):
        _asset, state, _snapshot = self.create_remote_asset()
        job = SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.FAILED,
            actor=self.user,
            payload_json={
                "targets": [{"folder_token": "folder-root"}],
            },
        )

        _mark_feishu_sync_states_failed(job, TimeoutError("timed out"))

        state.refresh_from_db()
        self.assertEqual(state.status, FeishuSyncStatus.FAILED)
        self.assertEqual(state.error_code, "folder_sync_failed")
        self.assertEqual(state.error_message, "TimeoutError")

    def test_only_admin_can_resolve_feishu_deletion(self):
        asset, state, snapshot = self.create_remote_asset()
        local_path = Path(self.temp_dir.name) / asset.storage_key
        difference = FeishuSyncDifference.objects.create(
            state=state,
            snapshot=snapshot,
            difference_type=FeishuSyncDifferenceType.DELETED,
            status=FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            file_token="file-1",
            previous_metadata={"file_name": asset.file_name},
        )
        regular = User.objects.create_user(
            username="non-admin",
            email="non-admin@example.com",
            password="password",
        )
        url = (
            "/api/v1/quotation/feishu/sync-differences/"
            f"{difference.id}/resolve"
        )
        self.api.force_authenticate(regular)
        denied = self.api.post(url, {"action": "delete"}, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(DocumentAsset.objects.filter(pk=asset.pk).exists())

        self.api.force_authenticate(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            resolved = self.api.post(
                url,
                {"action": "delete"},
                format="json",
            )
        self.assertEqual(resolved.status_code, 200, resolved.data)
        self.assertFalse(DocumentAsset.objects.filter(pk=asset.pk).exists())
        self.assertFalse(local_path.exists())
        difference.refresh_from_db()
        self.assertEqual(
            difference.status,
            FeishuSyncDifferenceStatus.ARCHIVED,
        )

    def test_sync_status_hides_another_users_file_details(self):
        other = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="password",
        )
        asset, state, snapshot = self.create_remote_asset()
        difference = FeishuSyncDifference.objects.create(
            state=state,
            snapshot=snapshot,
            difference_type=FeishuSyncDifferenceType.DELETED,
            status=FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            file_token="file-1",
            previous_metadata={"file_name": asset.file_name},
        )
        self.api.force_authenticate(other)

        response = self.api.get("/api/v1/quotation/feishu/sync-status")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(asset.file_name, str(response.data))
        self.assertNotIn(difference.file_token, str(response.data))

    def test_sync_status_reports_queued_login_job_as_syncing(self):
        SyncJob.objects.create(
            job_type=SyncJobType.PULL,
            status=SyncJobStatus.QUEUED,
            actor=self.user,
            scope_key="feishu:login-test",
            payload_json={
                "targets": [{"folder_token": "folder-root"}],
            },
        )

        response = self.api.get("/api/v1/quotation/feishu/sync-status")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], FeishuSyncStatus.SYNCING)

    def test_sync_status_filters_shared_state_and_sensitive_metadata(self):
        regular = User.objects.create_user(
            username="shared-state-user",
            email="shared-state@example.com",
            password="password",
        )
        visible_asset, state, visible_snapshot = self.create_remote_asset()
        visible_asset.created_by_email = regular.email
        visible_asset.save(update_fields=["created_by_email"])
        state.requested_by = regular
        state.status = FeishuSyncStatus.HAS_DIFF
        state.difference_count = 2
        state.error_code = "feishu_api_error"
        state.error_message = "request failed for sensitive-file-token"
        state.save(
            update_fields=[
                "requested_by",
                "status",
                "difference_count",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        hidden_asset = DocumentAsset.objects.create(
            doc_type=DocumentType.PDF,
            file_name="Hidden Quote.pdf",
            mime_type="application/pdf",
            storage_key="documents/remote/hidden.pdf",
            size_bytes=4,
            source="feishu",
            feishu_file_token="hidden-file-token",
            feishu_folder_token="folder-root",
            created_by_email="hidden-owner@example.com",
        )
        hidden_snapshot = FeishuFileSnapshot.objects.create(
            state=state,
            asset=hidden_asset,
            remote_file_token="hidden-file-token",
            folder_token="folder-root",
            file_name=hidden_asset.file_name,
            file_type="file",
            size_bytes=hidden_asset.size_bytes,
            metadata_fingerprint="hidden-fingerprint",
        )
        FeishuSyncDifference.objects.create(
            state=state,
            snapshot=visible_snapshot,
            difference_type=FeishuSyncDifferenceType.DELETED,
            status=FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            file_token="file-1",
            previous_metadata={
                "file_name": visible_asset.file_name,
                "folder_token": "sensitive-folder-token",
                "folder_path": [
                    {
                        "token": "sensitive-folder-token",
                        "name": "Sensitive Folder",
                    }
                ],
            },
            error_message="download failed for sensitive-file-token",
        )
        FeishuSyncDifference.objects.create(
            state=state,
            snapshot=hidden_snapshot,
            difference_type=FeishuSyncDifferenceType.DELETED,
            status=FeishuSyncDifferenceStatus.PENDING_CONFIRMATION,
            file_token="hidden-file-token",
            previous_metadata={"file_name": hidden_asset.file_name},
        )
        self.api.force_authenticate(regular)

        response = self.api.get("/api/v1/quotation/feishu/sync-status")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["difference_count"], 1)
        self.assertEqual(len(response.data["differences"]), 1)
        serialized = str(response.data)
        self.assertIn(visible_asset.file_name, serialized)
        self.assertNotIn(hidden_asset.file_name, serialized)
        self.assertNotIn("hidden-file-token", serialized)
        self.assertNotIn("sensitive-folder-token", serialized)
        self.assertNotIn("sensitive-file-token", serialized)
        self.assertNotIn("Sensitive Folder", serialized)

    def test_synchronous_sync_rejects_user_without_authorized_folders(self):
        regular = User.objects.create_user(
            username="no-folder-user",
            email="no-folder@example.com",
            password="password",
        )
        self.api.force_authenticate(regular)

        response = self.api.post(
            "/api/v1/quotation/feishu/sync-folder",
            {"async": False},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_periodic_sync_uses_configured_interval_and_dispatcher(self):
        TASK_REGISTRY.clear()

        with override_settings(QUOTATION_FEISHU_SYNC_INTERVAL_SECONDS=600):
            register_periodic_tasks()

        entry = TASK_REGISTRY._entries["quotation_feishu_periodic_sync"]
        self.assertEqual(entry["task"], "quotation.tasks.dispatch_feishu_sync")
        self.assertEqual(entry["schedule"], 600)
        with patch(
            "quotation.tasks.enqueue_feishu_sync",
            return_value=(None, False),
        ) as enqueue:
            dispatch_feishu_sync()
        enqueue.assert_called_once_with(actor=None, trigger="periodic")

    def test_multi_target_sync_reports_failure_when_every_target_fails(self):
        class FakeClient:
            def get_tenant_access_token(self):
                return "tenant-token"

            def get_folder_meta(self, access_token, folder_token):
                return {"token": folder_token, "name": folder_token}

            def list_folder_files(self, access_token, folder_token, **kwargs):
                raise FeishuAPIError("permission denied", code=99991663)

        with patch(
            "quotation.views.feishu.common._client",
            return_value=FakeClient(),
        ):
            response = FeishuFolderSyncView()._sync(
                SimpleNamespace(user=self.user),
                targets=[
                    {"folder_token": "folder-a"},
                    {"folder_token": "folder-b"},
                ],
            )

        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(len(response.data["errors"]), 2)
