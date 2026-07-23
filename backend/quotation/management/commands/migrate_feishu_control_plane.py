from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from quotation.models import (
    DocumentAsset,
    DocumentReplica,
    ReplicaSyncStatus,
    StorageConnection,
    StorageMount,
    StorageMountPurpose,
)
from quotation.services.feishu_client import extract_feishu_token_from_url


MIGRATION_MARKER = "legacy_file_token_v1"


class Command(BaseCommand):
    help = "Plan, apply, or roll back legacy Feishu replica mappings."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--rollback", action="store_true")

    def handle(self, *args, **options):
        if options["rollback"]:
            self._rollback()
            return
        self._migrate(apply=options["apply"])

    def _legacy_root_token(self) -> str:
        raw = (
            settings.QUOTATION_FEISHU_ARCHIVE_FOLDER_TOKEN
            or settings.QUOTATION_FEISHU_ARCHIVE_FOLDER_URL
            or settings.FEISHU_TEST_FOLDER_TOKEN
        )
        if not raw:
            return ""
        return extract_feishu_token_from_url(raw)

    def _ensure_default_route(self, *, root_token: str):
        connection, connection_created = (
            StorageConnection.objects.get_or_create(
                provider="feishu",
                external_tenant_id="legacy-default",
                defaults={
                    "display_name": "Legacy Feishu archive",
                    "app_id": settings.FEISHU_APP_ID,
                    "app_secret": settings.FEISHU_APP_SECRET,
                    "is_default": True,
                    "metadata": {"migration_marker": MIGRATION_MARKER},
                },
            )
        )
        connection_updates = []
        if connection.display_name != "Legacy Feishu archive":
            connection.display_name = "Legacy Feishu archive"
            connection_updates.append("display_name")
        if settings.FEISHU_APP_ID and connection.app_id != settings.FEISHU_APP_ID:
            connection.app_id = settings.FEISHU_APP_ID
            connection_updates.append("app_id")
        if (
            settings.FEISHU_APP_SECRET
            and connection.get_app_secret() != settings.FEISHU_APP_SECRET
        ):
            connection.app_secret = settings.FEISHU_APP_SECRET
            connection_updates.append("app_secret")
        if not connection.is_default:
            connection.is_default = True
            connection_updates.append("is_default")
        if connection_created:
            connection_updates = []
        elif connection_updates:
            connection.save(update_fields=[*connection_updates, "updated_at"])

        mount, mount_created = StorageMount.objects.get_or_create(
            connection=connection,
            scope_key="",
            purpose=StorageMountPurpose.QUOTATION_ARCHIVE,
            document_type="",
            defaults={
                "root_folder_token": root_token,
                "root_folder_name": "Configured archive folder",
                "is_default": True,
                "metadata": {"migration_marker": MIGRATION_MARKER},
            },
        )
        mount_updates = []
        if mount.root_folder_token != root_token:
            mount.root_folder_token = root_token
            mount_updates.append("root_folder_token")
        if mount.root_folder_name != "Configured archive folder":
            mount.root_folder_name = "Configured archive folder"
            mount_updates.append("root_folder_name")
        if not mount.is_default:
            mount.is_default = True
            mount_updates.append("is_default")
        if mount_created:
            mount_updates = []
        elif mount_updates:
            mount.save(update_fields=[*mount_updates, "updated_at"])

        return connection, mount

    def _migrate(self, *, apply: bool) -> None:
        root_token = self._legacy_root_token()
        if not root_token:
            self.stdout.write(
                "SKIPPED: no legacy Feishu archive folder is configured"
            )
            return
        assets = (
            DocumentAsset.objects.exclude(feishu_file_token__isnull=True)
            .exclude(feishu_file_token="")
            .select_related("quotation")
            .order_by("created_at", "id")
        )
        existing = DocumentReplica.objects.filter(
            metadata__migration_marker=MIGRATION_MARKER
        ).count()
        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(
            f"{mode}: assets={assets.count()} existing_replicas={existing}"
        )
        if not apply:
            return

        with transaction.atomic():
            connection, mount = self._ensure_default_route(
                root_token=root_token
            )
            created = 0
            skipped = 0
            for asset in assets:
                version = max(
                    getattr(asset.quotation, "version_current", 1) or 1,
                    1,
                ) if asset.quotation_id else 1
                _, replica_created = DocumentReplica.objects.get_or_create(
                    asset=asset,
                    connection=connection,
                    version=version,
                    defaults={
                        "mount": mount,
                        "remote_file_token": asset.feishu_file_token or "",
                        "remote_url": asset.feishu_url or "",
                        "folder_token": (
                            asset.feishu_folder_token or root_token
                        ),
                        "folder_path": asset.feishu_folder_path,
                        "sync_status": ReplicaSyncStatus.SYNCED,
                        "metadata": {"migration_marker": MIGRATION_MARKER},
                    },
                )
                if replica_created:
                    created += 1
                else:
                    skipped += 1
        self.stdout.write(
            f"DONE: replicas_created={created} replicas_skipped={skipped}"
        )

    def _rollback(self) -> None:
        with transaction.atomic():
            replicas = DocumentReplica.objects.filter(
                metadata__migration_marker=MIGRATION_MARKER
            )
            replica_count = replicas.count()
            replicas.delete()
            mounts = StorageMount.objects.filter(
                metadata__migration_marker=MIGRATION_MARKER,
                document_replicas__isnull=True,
            )
            mount_count = mounts.count()
            mounts.delete()
            connections = StorageConnection.objects.filter(
                metadata__migration_marker=MIGRATION_MARKER,
                mounts__isnull=True,
                document_replicas__isnull=True,
            )
            connection_count = connections.count()
            connections.delete()
        self.stdout.write(
            "ROLLED BACK: "
            f"replicas={replica_count} mounts={mount_count} "
            f"connections={connection_count}"
        )
