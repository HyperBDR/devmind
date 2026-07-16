"""Persistent conversations and app-scoped assistant memories."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class AssistantConversation(models.Model):
    """One user conversation permanently bound to one app."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_conversations",
    )
    tenant_id = models.CharField(max_length=128, blank=True, default="")
    app_key = models.CharField(max_length=64, db_index=True)
    capability_version = models.CharField(max_length=32, default="1")
    title = models.CharField(max_length=255, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(
                fields=["user", "app_key", "-updated_at"],
                name="assistant_user_app_updated_idx",
            ),
        ]


class AssistantMessage(models.Model):
    """One message inside an app-scoped conversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class AssistantMemory(models.Model):
    """Optional long-term memory isolated by user, tenant, and app."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_memories",
    )
    tenant_id = models.CharField(max_length=128, blank=True, default="")
    app_key = models.CharField(max_length=64, db_index=True)
    key = models.CharField(max_length=128)
    value = models.JSONField()
    source_conversation = models.ForeignKey(
        AssistantConversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="memories",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tenant_id", "app_key", "key"],
                name="assistant_unique_user_app_memory",
            ),
        ]
