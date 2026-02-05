"""
LLM Usage model for tracking token consumption and cost analysis.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class LLMUsage(models.Model):
    """
    Stores LLM API token usage records for statistics and cost analysis.

    Each record represents a single LLM API call for tracking token
    consumption and supporting admin cost analysis.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_usages",
        db_index=True,
        help_text="User who triggered this LLM call",
    )

    model = models.CharField(
        max_length=200,
        db_index=True,
        help_text="LLM model name used for this call",
    )
    prompt_tokens = models.IntegerField(
        default=0,
        help_text="Number of input/prompt tokens used",
    )
    completion_tokens = models.IntegerField(
        default=0,
        help_text="Number of output/completion tokens generated",
    )
    total_tokens = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Total tokens used (prompt + completion)",
    )
    cached_tokens = models.IntegerField(
        default=0,
        help_text="Number of cached tokens (if applicable)",
    )
    reasoning_tokens = models.IntegerField(
        default=0,
        help_text="Number of reasoning tokens (for o1 models)",
    )
    success = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the LLM call succeeded",
    )
    error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if the call failed",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Context and source info: node_name, source_type, source_task_id, "
            "source_path, etc. Flat structure for flexible querying."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this LLM call was made",
    )

    class Meta:
        db_table = "llm_tracker_usage"
        ordering = ["-created_at"]
        verbose_name = _("LLM Usage")
        verbose_name_plural = _("LLM Usages")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["model", "-created_at"]),
            models.Index(fields=["total_tokens", "-created_at"]),
            models.Index(fields=["success", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        node_name = self.metadata.get("node_name", "")
        node_info = f"{node_name} - " if node_name else ""
        return (
            f"{node_info}{self.model} "
            f"({self.total_tokens} tokens) - {self.created_at}"
        )
