"""Connection authority, synchronization runs and immutable dataset versions."""

import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone as django_timezone

from agione_ops.encryption import decrypt_credentials, encrypt_credentials

CONNECTION_CONFIG_FIELDS = frozenset(
    {
        "name",
        "platform",
        "principal_kind",
        "source_kind",
        "endpoint",
        "expected_tenant_id",
        "verified_tenant_id",
        "enabled",
        "credential_ciphertext",
        "key_id",
        "synthetic_fixture",
    }
)

STABLE_IDENTITY_FIELDS = frozenset(
    {
        "platform",
        "principal_kind",
        "source_kind",
        "expected_tenant_id",
    }
)
IDENTITY_CONFIG_FIELDS = CONNECTION_CONFIG_FIELDS - {
    "name",
    "enabled",
    "verified_tenant_id",
}


class ConnectionQuerySet(models.QuerySet):
    """Ensure bulk configuration changes invalidate existing run snapshots."""

    def update(self, **kwargs):
        """Lease and progress writes do not change the configuration epoch."""

        if STABLE_IDENTITY_FIELDS.intersection(kwargs):
            raise ValidationError("Connection identity cannot change.")
        if IDENTITY_CONFIG_FIELDS.intersection(kwargs):
            kwargs["verified_tenant_id"] = ""
            kwargs["verified_at"] = None
        if CONNECTION_CONFIG_FIELDS.intersection(kwargs):
            kwargs["config_version"] = F("config_version") + 1
        if {"credential_ciphertext", "key_id"}.intersection(kwargs):
            kwargs["credential_version"] = F("credential_version") + 1
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        """Require revision-aware saves for configuration updates."""

        if CONNECTION_CONFIG_FIELDS.intersection(fields):
            raise ValidationError("Use revision-aware connection saves.")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class SourceConnection(models.Model):
    """One stable upstream identity; credential rotation never changes UUID."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    platform = models.CharField(
        max_length=8, choices=[("pro", "Pro"), ("cc", "CC")]
    )
    principal_kind = models.CharField(
        max_length=16,
        choices=[("provider", "Provider"), ("operator", "Operator")],
    )
    source_kind = models.CharField(
        max_length=16,
        default="synthetic",
        choices=[
            ("synthetic", "Synthetic"),
            ("demo_snapshot", "Demo snapshot (read-only)"),
            ("native", "AGIOne direct API"),
        ],
    )
    endpoint = models.URLField(blank=True, default="")
    expected_tenant_id = models.CharField(
        max_length=160, blank=True, default=""
    )
    verified_tenant_id = models.CharField(
        max_length=160, blank=True, default=""
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)
    credential_ciphertext = models.TextField(blank=True, default="")
    credential_version = models.PositiveBigIntegerField(default=1)
    key_id = models.CharField(max_length=80, blank=True, default="")
    config_version = models.PositiveBigIntegerField(default=1)
    synthetic_fixture = models.CharField(max_length=64, default="basic")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agione_connections_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active_run_id = models.UUIDField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_epoch = models.PositiveBigIntegerField(default=0)
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    objects = ConnectionQuerySet.as_manager()

    class Meta:
        db_table = "devmind_agione_source_connection"
        permissions = [
            ("manage_connections", "Configure AGIOne connections"),
            ("view_business", "Read AGIOne business data"),
            ("run_sync", "Synchronize AGIOne business data"),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        """Only configured HTTPS addresses may be stored; none are executed."""

        super().clean()
        if self.endpoint:
            parsed = urlsplit(self.endpoint)
            allowed = getattr(
                settings, "AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS", ()
            )
            try:
                port = parsed.port
            except ValueError:
                raise ValidationError({"endpoint": "Endpoint is not allowed."})
            if (
                parsed.scheme != "https"
                or parsed.hostname not in allowed
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or port not in (None, 443)
            ):
                raise ValidationError({"endpoint": "Endpoint is not allowed."})

    def save(self, *args, **kwargs):
        """Advance security epochs under the same row lock as the change."""

        using = kwargs.get("using") or self._state.db or "default"
        self.full_clean(validate_unique=False, validate_constraints=False)
        with transaction.atomic(using=using):
            previous = None
            if not self._state.adding:
                previous = (
                    type(self)
                    .objects.using(using)
                    .select_for_update()
                    .get(pk=self.pk)
                )
            if previous is not None and any(
                getattr(previous, field) != getattr(self, field)
                for field in STABLE_IDENTITY_FIELDS
            ):
                raise ValidationError("Connection identity cannot change.")
            invalidated = previous is not None and any(
                getattr(previous, field) != getattr(self, field)
                for field in IDENTITY_CONFIG_FIELDS
            )
            if invalidated:
                self.verified_tenant_id = ""
                self.verified_at = None
            changed = previous is not None and any(
                getattr(previous, field) != getattr(self, field)
                for field in CONNECTION_CONFIG_FIELDS
            )
            if previous is not None:
                for field in (
                    "active_run_id",
                    "lease_token",
                    "lease_epoch",
                    "lease_expires_at",
                ):
                    setattr(self, field, getattr(previous, field))
                self.config_version = previous.config_version + int(changed)
                rotated = any(
                    getattr(previous, field) != getattr(self, field)
                    for field in ("credential_ciphertext", "key_id")
                )
                self.credential_version = previous.credential_version + int(
                    rotated
                )
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                    "config_version",
                    "credential_version",
                    "updated_at",
                }
                if invalidated:
                    kwargs["update_fields"].update(
                        {"verified_tenant_id", "verified_at"}
                    )
            return super().save(*args, **kwargs)

    def set_credentials(self, payload, key_id=None):
        """Set write-only encrypted state; persist explicitly with save()."""

        self.credential_ciphertext, self.key_id = encrypt_credentials(
            payload, key_id
        )

    def get_credentials(self):
        """Decrypt only with this connection's dedicated key identifier."""

        return decrypt_credentials(self.credential_ciphertext, self.key_id)


class GrantQuerySet(models.QuerySet):
    """Every grant mutation invalidates existing connection run snapshots."""

    def update(self, **kwargs):
        """Revoke/regrant cannot revive a run holding the old epoch."""

        if {"connection", "connection_id", "user", "user_id"}.intersection(
            kwargs
        ):
            raise ValidationError("Grant identity cannot change.")
        using = self.db
        with transaction.atomic(using=using):
            connections = list(self.values_list("connection_id", flat=True))
            SourceConnection.objects.using(using).filter(
                pk__in=connections
            ).update(
                config_version=F("config_version") + 1,
            )
            kwargs["revision"] = F("revision") + 1
            return super().update(**kwargs)

    def delete(self):
        """Deletion plus recreation still changes a monotonic parent epoch."""

        using = self.db
        with transaction.atomic(using=using):
            connections = list(self.values_list("connection_id", flat=True))
            SourceConnection.objects.using(using).filter(
                pk__in=connections
            ).update(
                config_version=F("config_version") + 1,
            )
            return super().delete()

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Use revision-aware grant saves.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Use revision-aware grant saves.")


class ConnectionGrant(models.Model):
    """Explicit per-user connection scope, independent of feature visibility."""

    connection = models.ForeignKey(
        SourceConnection, on_delete=models.PROTECT, related_name="grants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agione_connection_grants",
    )
    can_view = models.BooleanField(default=False)
    can_sync = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    objects = GrantQuerySet.as_manager()

    class Meta:
        db_table = "devmind_agione_connection_grant"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "user"],
                name="dm_agione_conn_grant_uq",
            )
        ]

    def save(self, *args, **kwargs):
        """Serialize grant changes against the connection security epoch."""

        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            SourceConnection.objects.using(using).select_for_update().get(
                pk=self.connection_id
            )
            if not self._state.adding:
                prior = type(self).objects.using(using).get(pk=self.pk)
                if (
                    prior.connection_id != self.connection_id
                    or prior.user_id != self.user_id
                ):
                    raise ValidationError("Grant identity cannot change.")
                self.revision = prior.revision + 1
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                    "revision",
                    "updated_at",
                }
            result = super().save(*args, **kwargs)
            SourceConnection.objects.using(using).filter(
                pk=self.connection_id
            ).update(config_version=F("config_version") + 1)
            return result

    def delete(self, *args, **kwargs):
        """Route ordinary instance deletion through epoch-aware deletion."""

        return (
            type(self)
            .objects.using(kwargs.get("using") or self._state.db or "default")
            .filter(pk=self.pk)
            .delete()
        )


class SyncRun(models.Model):
    """Domain authority for authorization, progress and version publication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        SourceConnection, on_delete=models.PROTECT, related_name="sync_runs"
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agione_sync_runs",
    )
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="Asia/Shanghai")
    kind = models.CharField(
        max_length=16, default="current", choices=[("current", "Current")]
    )
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    credential_version = models.PositiveBigIntegerField()
    config_version = models.PositiveBigIntegerField()
    grant_revision = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=24,
        default="queued",
        choices=[
            (value, value)
            for value in (
                "queued",
                "running",
                "retrying",
                "succeeded",
                "failed",
                "revoked",
                "interrupted",
                "dispatch_failed",
            )
        ],
    )
    celery_id = models.CharField(max_length=128, blank=True, default="")
    phase = models.CharField(max_length=64, default="queued")
    processed_count = models.PositiveBigIntegerField(default=0)
    total_count = models.PositiveBigIntegerField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    lease_epoch = models.PositiveBigIntegerField(default=0)
    attempt = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "devmind_agione_sync_run"
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "initiated_by", "idempotency_key"],
                name="dm_agione_run_idem_uq",
            ),
            models.CheckConstraint(
                condition=Q(window_end__gt=F("window_start")),
                name="dm_agione_run_window_ck",
            ),
        ]

    def clean(self):
        super().clean()
        if django_timezone.is_naive(
            self.window_start
        ) or django_timezone.is_naive(self.window_end):
            raise ValidationError("Timezone-aware windows are required.")
        if self.window_start >= self.window_end:
            raise ValidationError("Window end must be after its start.")


def _publication_run(run_id, using, lock=False):
    """Read publication authority from the database, never a relation cache."""

    queryset = SyncRun.objects.using(using)
    if lock:
        queryset = queryset.select_for_update()
    run = queryset.filter(pk=run_id).first()
    if run is None or run.status != "running":
        raise ValidationError(
            "Publication requires a running sync transaction."
        )
    return run


class ImmutableQuerySet(models.QuerySet):
    """Published data supports inserts and reads, never in-place mutation."""

    def update(self, **kwargs):
        raise ValidationError("Published data is immutable.")

    def delete(self):
        raise ValidationError("Published data is immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Published data is immutable.")

    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Published data is immutable.")
        objs = list(objs)
        with transaction.atomic(using=self.db):
            for obj in objs:
                hook = getattr(obj, "_lock_for_insert", None)
                if hook is not None:
                    hook(self.db)
                obj.full_clean(
                    validate_unique=False, validate_constraints=False
                )
            return super().bulk_create(objs, **kwargs)


class ImmutableModel(models.Model):
    """Never update or delete a published runtime object."""

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if (
            not self._state.adding
            or args
            or kwargs.get("force_update")
            or kwargs.get("update_fields") is not None
        ):
            raise ValidationError("Published data is immutable.")
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            hook = getattr(self, "_lock_for_insert", None)
            if hook is not None:
                hook(using)
            self.full_clean(validate_unique=False, validate_constraints=False)
            kwargs["force_insert"] = True
            kwargs["using"] = using
            return super().save(**kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Published data is immutable.")


class DatasetVersion(ImmutableModel):
    """One complete immutable publication, never a partially visible sync."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        SourceConnection, on_delete=models.PROTECT, related_name="versions"
    )
    run = models.OneToOneField(
        SyncRun, on_delete=models.PROTECT, related_name="published_version"
    )
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="Asia/Shanghai")
    published_at = models.DateTimeField(default=django_timezone.now)
    coverage = models.JSONField(default=dict, blank=True)
    schema_version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "devmind_agione_dataset_version"
        ordering = ["-published_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(window_end__gt=F("window_start")),
                name="dm_agione_version_window_ck",
            )
        ]

    def _lock_for_insert(self, using):
        """Only the locked running task may create its immutable version."""

        _publication_run(self.run_id, using, lock=True)

    def clean(self):
        super().clean()
        run = _publication_run(self.run_id, self._state.db or "default")
        if (
            self.connection_id != run.connection_id
            or self.window_start != run.window_start
            or self.window_end != run.window_end
            or self.timezone != run.timezone
        ):
            raise ValidationError(
                "Version must match its connection and run window."
            )


class CallFact(ImmutableModel):
    """Immutable normalized request revision scoped to one connection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        SourceConnection, on_delete=models.PROTECT, related_name="call_facts"
    )
    upstream_record_id = models.CharField(max_length=160)
    content_hash = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()
    customer_id = models.CharField(max_length=160)
    model_id = models.CharField(max_length=160)
    status = models.CharField(
        max_length=16,
        choices=[
            ("success", "Success"),
            ("failure", "Failure"),
            ("unknown", "Unknown"),
        ],
    )
    input_tokens = models.PositiveBigIntegerField(null=True, blank=True)
    output_tokens = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "devmind_agione_call_fact"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "upstream_record_id", "content_hash"],
                name="dm_agione_fact_revision_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["connection", "occurred_at"],
                name="dm_agione_fact_conn_time",
            )
        ]

    def clean(self):
        super().clean()
        if django_timezone.is_naive(self.occurred_at):
            raise ValidationError(
                "Timezone-aware request timestamps are required."
            )


class VersionCall(ImmutableModel):
    """Pin one request identity to one immutable fact in a dataset version."""

    version = models.ForeignKey(
        DatasetVersion, on_delete=models.PROTECT, related_name="calls"
    )
    fact = models.ForeignKey(
        CallFact, on_delete=models.PROTECT, related_name="version_links"
    )
    upstream_record_id = models.CharField(max_length=160)

    class Meta:
        db_table = "devmind_agione_version_call"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "upstream_record_id"],
                name="dm_agione_version_request_uq",
            )
        ]

    def _lock_for_insert(self, using):
        """Serialize link insertion against terminal publication status."""

        version = DatasetVersion.objects.using(using).get(pk=self.version_id)
        _publication_run(version.run_id, using, lock=True)

    def clean(self):
        super().clean()
        using = self._state.db or "default"
        version = DatasetVersion.objects.using(using).get(pk=self.version_id)
        fact = CallFact.objects.using(using).get(pk=self.fact_id)
        _publication_run(version.run_id, using)
        if (
            version.connection_id != fact.connection_id
            or self.upstream_record_id != fact.upstream_record_id
        ):
            raise ValidationError(
                "Version facts must match connection and request identity."
            )
        if not version.window_start <= fact.occurred_at < version.window_end:
            raise ValidationError("Fact is outside the published window.")


class DemoSnapshotBinding(ImmutableModel):
    """One explicitly authorized local Demo principal, never rebound in place."""

    connection = models.OneToOneField(
        SourceConnection,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="demo_snapshot_binding",
    )
    demo_connection_id = models.CharField(max_length=32, unique=True)
    source_id = models.CharField(max_length=160)
    tenant_id = models.CharField(max_length=160)
    principal_kind = models.CharField(max_length=16)
    platform = models.CharField(max_length=8)
    scope_type = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devmind_agione_demo_snapshot_binding"

    def clean(self):
        """Keep historical rows but prevent creating retired bindings."""
        raise ValidationError("Demo snapshot bindings are no longer supported.")


from agione_ops.snapshot_store_models import ImmutableDemoSnapshot
from agione_ops.native_sync_models import (
    NativeAccountScope,
    NativeFinanceProjection,
    NativePublishedSnapshot,
    NativeSnapshotLease,
    NativeStagedRecord,
    NativeSyncShard,
    NativeSyncState,
)
