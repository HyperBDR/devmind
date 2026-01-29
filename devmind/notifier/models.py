"""
Data models for notifier app.
"""
from django.contrib.auth.models import User
from django.db import models

from .constants import Channel, Provider, Status


class NotificationRecord(models.Model):
    """
    Notification record model for tracking notification sending history.

    This model records all notification attempts, including success and
    failure cases, without depending on any business-specific models.
    """
    STATUS_CHOICES = [
        (Status.PENDING, 'Pending'),
        (Status.SUCCESS, 'Success'),
        (Status.FAILED, 'Failed'),
    ]

    PROVIDER_TYPE_CHOICES = [
        (Provider.FEISHU, 'Feishu'),
        (Provider.WECOM, 'WeCom'),
        (Provider.WECHAT, 'WeChat Work'),
        (Provider.EMAIL, 'Email'),
    ]

    # Notification channel information
    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPE_CHOICES,
        help_text="Notification provider type"
    )
    channel = models.CharField(
        max_length=50,
        default=Channel.WEBHOOK,
        help_text="Notification channel (webhook, email, sms, etc.)"
    )

    # User information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_records',
        help_text="User who should receive this notification"
    )

    # Source information (generic, not tied to specific business models)
    source_app = models.CharField(
        max_length=100,
        help_text="Source application that triggered the notification"
    )
    source_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source type (e.g., 'alert', 'task', 'event')"
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source identifier (e.g., alert_record_id)"
    )

    # Notification content (stored as JSON for flexibility)
    payload = models.JSONField(
        help_text="Notification payload sent to the provider"
    )

    # Status and response
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=Status.PENDING,
        db_index=True,
        help_text="Notification status"
    )
    response = models.JSONField(
        null=True,
        blank=True,
        help_text="Response from notification provider"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if notification failed"
    )

    # Metadata for notification type specific data (stored as JSON)
    # Examples:
    # For webhook: {"url": "https://...", "headers": {...}}
    # For email: {
    #     "recipient": "user@example.com",
    #     "subject": "...",
    #     "body_text": "...",
    #     "body_html": "...",
    #     "from_email": "...",
    #     "from_name": "..."
    # }
    # For SMS: {"phone_number": "+1234567890", "message": "..."}
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification type specific metadata stored as JSON"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the notification was created"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the notification was actually sent"
    )

    class Meta:
        db_table = 'notifier_notification_record'
        verbose_name = 'Notification Record'
        verbose_name_plural = 'Notification Records'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source_app', 'source_type']),
            models.Index(fields=['provider_type', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.provider_type} - {self.source_app} - "
            f"{self.status} - {self.created_at}"
        )
