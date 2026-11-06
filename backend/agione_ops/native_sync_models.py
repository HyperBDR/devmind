"""Durable native collection state and sanitized immutable publications."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from agione_ops.models import ImmutableModel, _publication_run


class NativeSyncState(models.Model):
    """Checkpoint the normalized directory once per UUID-only domain run."""

    run = models.OneToOneField(
        "agione_ops.SyncRun", primary_key=True, on_delete=models.PROTECT,
        related_name="native_state",
    )
    directory = models.JSONField(default=dict)
    model_names = models.JSONField(default=dict)
    directory_complete = models.BooleanField(default=False)
    directory_count = models.PositiveIntegerField(default=0)
    role_state = models.CharField(max_length=32, default="not_verified")
    watermark = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "devmind_agione_native_sync_state"


class NativeSyncShard(models.Model):
    """Persist retryable half-open day/hour/bisected collection intervals."""

    run = models.ForeignKey(
        "agione_ops.SyncRun", on_delete=models.PROTECT,
        related_name="native_shards",
    )
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    status = models.CharField(max_length=16, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    pages_read = models.PositiveIntegerField(default=0)
    record_count = models.PositiveBigIntegerField(default=0)
    excluded_count = models.PositiveBigIntegerField(default=0)
    error_code = models.CharField(max_length=80, default="", blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "devmind_agione_native_sync_shard"
        ordering = ["window_start", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "window_start", "window_end"],
                name="dm_agione_native_shard_uq",
            ),
            models.CheckConstraint(
                condition=Q(window_end__gt=F("window_start")),
                name="dm_agione_native_shard_window",
            ),
        ]


class NativeStagedRecord(models.Model):
    """Normalized analytics whitelist, never source logs or credentials."""

    run = models.ForeignKey(
        "agione_ops.SyncRun", on_delete=models.PROTECT,
        related_name="native_staging",
    )
    shard = models.ForeignKey(
        NativeSyncShard, on_delete=models.PROTECT, related_name="records",
    )
    record_id = models.CharField(max_length=40)
    occurred_at = models.DateTimeField()
    content_digest = models.CharField(max_length=64)
    data = models.JSONField()

    class Meta:
        db_table = "devmind_agione_native_staged_record"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "record_id"],
                name="dm_agione_native_stage_uq",
            ),
        ]


class NativeFinanceRun(models.Model):
    """Durable status for one independently scheduled finance refresh."""

    connection = models.ForeignKey("agione_ops.SourceConnection", on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    run = models.ForeignKey("agione_ops.SyncRun", on_delete=models.PROTECT)
    generation = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=16, default="queued")
    error_code = models.CharField(max_length=80, blank=True, default="")
    attempt = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "devmind_agione_native_finance_run"
        indexes = [models.Index(fields=["connection", "user", "-created_at"],
                                name="dm_finance_history_idx")]


class NativeFinanceProjection(models.Model):
    """Last authorized finance result and its independent refresh state."""

    connection = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
        related_name="finance_projections",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operator = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
        related_name="operator_finance_projections",
    )
    run = models.ForeignKey("agione_ops.SyncRun", on_delete=models.PROTECT)
    config_version = models.PositiveBigIntegerField()
    credential_version = models.PositiveBigIntegerField()
    operator_config_version = models.PositiveBigIntegerField()
    operator_credential_version = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, default="queued")
    error_code = models.CharField(max_length=80, default="", blank=True)
    data = models.JSONField(null=True, blank=True)
    content_digest = models.CharField(max_length=64, default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devmind_agione_native_finance_projection"
        constraints = [models.UniqueConstraint(
            fields=["connection", "user"], name="dm_agione_finance_user_uq",
        )]


class NativeSnapshotChunk(ImmutableModel):
    """Persist one ordered batch independently of staging retention."""

    version = models.ForeignKey(
        "agione_ops.DatasetVersion", on_delete=models.CASCADE,
        related_name="native_chunks",
    )
    position = models.PositiveIntegerField()
    rows = models.JSONField()

    class Meta:
        db_table = "devmind_agione_native_snapshot_chunk"
        unique_together = [("version", "position")]

    def _lock_for_insert(self, using):
        """Only the owning running task may add unpublished chunks."""
        from agione_ops.models import DatasetVersion

        version = DatasetVersion.objects.using(using).get(pk=self.version_id)
        _publication_run(version.run_id, using, lock=True)
        if NativePublishedSnapshot.objects.using(using).filter(
            pk=self.version_id,
        ).exists():
            raise ValidationError("Snapshot is already published.")


class NativePublishedSnapshot(ImmutableModel):
    """Pin directory/models/analytics to one atomic DatasetVersion."""

    version = models.OneToOneField(
        "agione_ops.DatasetVersion", primary_key=True,
        on_delete=models.PROTECT, related_name="native_snapshot",
    )
    data = models.JSONField()
    content_digest = models.CharField(max_length=64)

    class Meta:
        db_table = "devmind_agione_native_published_snapshot"

    def _lock_for_insert(self, using):
        """Serialize publication against domain run terminal transitions."""
        from agione_ops.models import DatasetVersion

        version = DatasetVersion.objects.using(using).get(pk=self.version_id)
        _publication_run(version.run_id, using, lock=True)

    def clean(self):
        """Reject unnormalized publication outside a running native task."""
        super().clean()
        from agione_ops.models import DatasetVersion
        from agione_ops.native_sync import validate_snapshot_data

        version = DatasetVersion.objects.get(pk=self.version_id)
        run = _publication_run(version.run_id, self._state.db or "default")
        if run.connection.source_kind != "native":
            raise ValidationError("Native publication requires native source.")
        if "chunkDigests" in self.data:
            from agione_ops.snapshot_chunks import validate_manifest
            validate_manifest(self, run, version)
            return
        validate_snapshot_data(self.data, self.content_digest)
        metadata = self.data["metadata"]
        if (
            metadata["configVersion"] != run.config_version
            or metadata["credentialVersion"] != run.credential_version
        ):
            raise ValidationError("Snapshot security epoch mismatch.")
        if run.native_shards.exclude(status__in=["succeeded", "split"]).exists():
            raise ValidationError("Snapshot requires complete shards.")
        if not run.native_state.directory_complete:
            raise ValidationError("Snapshot requires a complete directory.")
        if len(self.data["rows"]) != run.native_staging.count():
            raise ValidationError("Snapshot requires all staged records.")
        for row in self.data["rows"]:
            from agione_ops.native_analytics import parse_time

            if not version.window_start <= parse_time(
                row["occurred_at"]
            ) < version.window_end:
                raise ValidationError("Snapshot row outside version window.")
        return None


class NativeSnapshotLease(models.Model):
    """Protect recently accessed versions from retention cleanup."""

    version = models.OneToOneField(
        "agione_ops.DatasetVersion", primary_key=True,
        on_delete=models.CASCADE, related_name="native_lease",
    )
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "devmind_agione_native_snapshot_lease"


# Imported at the bottom of models.py by the owning integration agent.
MODEL_CLASSES = (
    NativeSyncState, NativeSyncShard, NativeStagedRecord,
    NativePublishedSnapshot, NativeSnapshotLease,
)


class NativeAccountScope(models.Model):
    """Sanitized account classifications for one authorized viewer."""

    connection = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
        related_name="account_scopes",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operator = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
        related_name="operator_account_scopes",
    )
    run = models.ForeignKey("agione_ops.SyncRun", on_delete=models.PROTECT)
    config_version = models.PositiveBigIntegerField()
    credential_version = models.PositiveBigIntegerField()
    operator_config_version = models.PositiveBigIntegerField()
    operator_credential_version = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, default="queued")
    error_code = models.CharField(max_length=80, default="", blank=True)
    data = models.JSONField(default=dict)
    names = models.JSONField(default=dict)
    content_digest = models.CharField(max_length=64, default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devmind_agione_native_account_scope"
        constraints = [models.UniqueConstraint(
            fields=["connection", "user"], name="dm_agione_account_scope_uq",
        )]


class TenantClassification(models.Model):
    """Manual tenant classification scoped to the authorized Operator."""

    operator = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
        related_name="tenant_classifications",
    )
    tenant_id = models.CharField(max_length=40)
    classification = models.CharField(
        max_length=8, choices=[("internal", "Internal"), ("external", "External")],
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devmind_agione_tenant_classification"
        constraints = [models.UniqueConstraint(
            fields=["operator", "tenant_id"], name="dm_agione_tenant_class_uq",
        )]


class TenantClassificationChange(models.Model):
    """Append-only record of a manual classification change."""

    operator = models.ForeignKey(
        "agione_ops.SourceConnection", on_delete=models.PROTECT,
    )
    tenant_id = models.CharField(max_length=40)
    classification = models.CharField(max_length=9)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devmind_agione_tenant_classification_change"
