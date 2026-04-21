"""
Data models for data_collector: config, raw records, attachments.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class CollectorConfig(models.Model):
    """
    Per-user, per-platform collection config. No global scope.
    Drives schedule and runtime state; unique (user, platform).
    """

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text="Public identifier for API and Beat tasks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="data_collector_configs",
        help_text="Owner of this config",
    )
    platform = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Platform identifier, e.g. jira, feishu",
    )
    key = models.CharField(
        max_length=128,
        help_text="Config key, e.g. jira_config_collector",
    )
    value = models.JSONField(
        default=dict,
        help_text=(
            "Auth, schedule_cron, cleanup_cron, retention_days, "
            "initial_range, runtime_state (timestamps)"
        ),
    )
    is_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether collection is enabled",
    )
    version = models.IntegerField(
        default=0,
        help_text="Optimistic lock for concurrent updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_collector_config"
        verbose_name = "Collector Config"
        verbose_name_plural = "Collector Configs"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform"],
                name="data_collector_config_user_platform_uniq",
            )
        ]
        ordering = ["user", "platform"]

    def __str__(self):
        u, p = self.user_id, self.platform
        return f"CollectorConfig(user={u}, platform={p})"


class RawDataRecord(models.Model):
    """
    One raw data record from a platform.
    Keyed by (user, platform, source_unique_id).
    """

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
        help_text="Public identifier",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="data_collector_records",
    )
    platform = models.CharField(max_length=32, db_index=True)
    source_unique_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Platform-side unique id (e.g. issue key)",
    )
    raw_data = models.JSONField(
        default=dict,
        help_text="Full raw payload from platform",
    )
    filter_metadata = models.JSONField(
        default=dict,
        help_text="Key fields for filtering (type, status, project, etc.)",
    )
    data_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash for change detection (e.g. MD5)",
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if no longer present on platform (after validate)",
    )
    source_created_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    first_collected_at = models.DateTimeField(null=True, blank=True)
    last_collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_collector_raw_data_record"
        verbose_name = "Raw Data Record"
        verbose_name_plural = "Raw Data Records"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform", "source_unique_id"],
                name="data_collector_record_user_platform_sid_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["user", "platform"]),
            models.Index(fields=["platform", "is_deleted"]),
        ]
        ordering = ["-last_collected_at"]

    def __str__(self):
        return f"RawDataRecord({self.platform}/{self.source_unique_id})"


class RawDataAttachment(models.Model):
    """
    Attachment for a raw data record. Unique per (raw_record, source_file_id)
    when source_file_id is set.
    """

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text="Public identifier for download API",
    )
    raw_record = models.ForeignKey(
        RawDataRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    source_file_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Platform file id for dedup",
    )
    file_name = models.CharField(max_length=512)
    file_path = models.CharField(
        max_length=1024,
        help_text="Absolute path on server",
    )
    file_url = models.CharField(
        max_length=1024,
        help_text="HTTP path for download (/media/storage/data_collector/...)",
    )
    file_type = models.CharField(max_length=128, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_md5 = models.CharField(max_length=32, blank=True)
    source_created_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "data_collector_raw_data_attachment"
        verbose_name = "Raw Data Attachment"
        verbose_name_plural = "Raw Data Attachments"
        constraints = [
            models.UniqueConstraint(
                fields=["raw_record", "source_file_id"],
                condition=Q(source_file_id__isnull=False),
                name="data_collector_attachment_record_source_uniq",
            )
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"RawDataAttachment({self.file_name})"
