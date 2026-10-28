"""Append-only validated historical Demo imports owned by DevMind."""

from django.core.exceptions import ValidationError
from django.db import models


class ImmutableSnapshotQuerySet(models.QuerySet):
    """Reject mutation through the public ORM API."""

    def update(self, **kwargs):
        raise ValidationError("Historical snapshots are immutable.")

    def delete(self):
        raise ValidationError("Historical snapshots are immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Historical snapshots are immutable.")

    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Historical snapshots are immutable.")
        return super().bulk_create(objs, **kwargs)


class ImmutableDemoSnapshot(models.Model):
    """One canonical, allowlisted import for a source/version principal."""

    owner_connection_id = models.UUIDField()
    connection_id = models.CharField(max_length=32)
    source_id = models.CharField(max_length=160)
    version = models.UUIDField()
    schema_version = models.PositiveSmallIntegerField(default=1)
    digest = models.CharField(max_length=64)
    source_digest = models.CharField(max_length=64)
    metadata = models.JSONField()
    content = models.JSONField()
    imported_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableSnapshotQuerySet.as_manager()

    class Meta:
        app_label = "agione_ops"
        db_table = "devmind_agione_immutable_demo_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=("owner_connection_id", "connection_id", "source_id",
                        "version"),
                name="agione_immutable_snapshot_identity",
            ),
        ]

    def save(self, *args, **kwargs):
        """Only insertion is supported; identical rewrites are rejected too."""
        if not self._state.adding:
            raise ValidationError("Historical snapshots are immutable.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical snapshots are immutable.")

    def __str__(self):
        return f"{self.connection_id}/{self.version}"
