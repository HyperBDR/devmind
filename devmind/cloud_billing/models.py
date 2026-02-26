"""
Data models for cloud billing management.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from .constants import (
    WEBHOOK_STATUS_FAILED,
    WEBHOOK_STATUS_PENDING,
    WEBHOOK_STATUS_SUCCESS,
)


class CloudProvider(models.Model):
    """
    Cloud provider configuration model.
    """
    PROVIDER_TYPES = [
        ('aws', 'AWS'),
        ('huawei', 'Huawei Cloud (China)'),
        ('huawei-intl', 'Huawei Cloud (International)'),
        ('alibaba', 'Alibaba Cloud'),
        ('azure', 'Azure'),
    ]

    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the provider, e.g., 'aws_china'"
    )
    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPES,
        help_text="Cloud provider type"
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Display name for the provider, e.g., 'AWS China'"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Optional notes or description for this provider"
    )
    config = models.JSONField(
        help_text="Authentication configuration stored as JSON"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this provider is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cloud_providers'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_cloud_providers'
    )

    class Meta:
        db_table = 'cloud_billing_provider'
        verbose_name = 'Cloud Provider'
        verbose_name_plural = 'Cloud Providers'
        indexes = [
            models.Index(fields=['provider_type', 'is_active']),
            models.Index(fields=['name']),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.display_name} ({self.name})"


class BillingData(models.Model):
    """
    Billing data history model.
    """
    HOUR_CHOICES = [(i, i) for i in range(24)]

    provider = models.ForeignKey(
        CloudProvider,
        on_delete=models.CASCADE,
        related_name='billing_data'
    )
    period = models.CharField(
        max_length=7,
        help_text="Billing period in YYYY-MM format, e.g., '2025-01'"
    )
    hour = models.IntegerField(
        choices=HOUR_CHOICES,
        help_text="Collection hour, 0-23"
    )
    total_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Cumulative total cost for the period"
    )
    hourly_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Incremental cost for this hour (current - previous hour)"
    )
    currency = models.CharField(
        max_length=10,
        default='USD',
        help_text="Currency code, e.g., 'USD', 'CNY'"
    )
    service_costs = models.JSONField(
        default=dict,
        help_text="Service cost breakdown, format: {'service_name': cost, ...}"
    )
    account_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Account ID"
    )
    collected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    class Meta:
        db_table = 'cloud_billing_data'
        verbose_name = 'Billing Data'
        verbose_name_plural = 'Billing Data'
        unique_together = [('provider', 'account_id', 'period', 'hour')]
        indexes = [
            models.Index(fields=['provider', 'account_id', 'period', 'hour']),
            models.Index(fields=['provider', 'period', 'hour']),
            models.Index(fields=['period', 'hour']),
            models.Index(fields=['collected_at']),
        ]
        ordering = ['-period', '-hour']

    def __str__(self):
        return (
            f"{self.provider.display_name} - {self.period} "
            f"{self.hour:02d}:00"
        )


class AlertRule(models.Model):
    """
    Alert rule model for billing cost monitoring.
    """
    provider = models.OneToOneField(
        CloudProvider,
        on_delete=models.CASCADE,
        related_name='alert_rule',
        help_text="Cloud provider for this alert rule"
    )
    cost_threshold = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Absolute cost threshold"
    )
    growth_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Growth percentage threshold, e.g., 5.0 means 5%"
    )
    growth_amount_threshold = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Growth amount threshold, e.g., 1000.00 means alert when "
            "cost increases by 1000.00"
        )
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this alert rule is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_alert_rules'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_alert_rules'
    )

    class Meta:
        db_table = 'cloud_billing_alert_rule'
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        indexes = [
            models.Index(fields=['provider', 'is_active']),
        ]

    def clean(self):
        """
        Validate that at least one threshold is set.
        """
        if (not self.cost_threshold and not self.growth_threshold and
                not self.growth_amount_threshold):
            raise ValidationError(
                "At least one of cost_threshold, growth_threshold, "
                "or growth_amount_threshold must be set."
            )

    def save(self, *args, **kwargs):
        """
        Validate before saving.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        thresholds = []
        if self.cost_threshold:
            thresholds.append(f"Cost: {self.cost_threshold}")
        if self.growth_threshold:
            thresholds.append(f"Growth: {self.growth_threshold}%")
        if self.growth_amount_threshold:
            thresholds.append(f"Growth Amount: {self.growth_amount_threshold}")
        return f"{self.provider.display_name} - {', '.join(thresholds)}"


class AlertRecord(models.Model):
    """
    Alert record model for tracking billing alerts.
    """
    WEBHOOK_STATUS_CHOICES = [
        (WEBHOOK_STATUS_PENDING, 'Pending'),
        (WEBHOOK_STATUS_SUCCESS, 'Success'),
        (WEBHOOK_STATUS_FAILED, 'Failed'),
    ]

    provider = models.ForeignKey(
        CloudProvider,
        on_delete=models.CASCADE,
        related_name='alert_records'
    )
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alert_records'
    )
    current_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Current hour cost"
    )
    previous_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Previous hour cost"
    )
    increase_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Cost increase amount"
    )
    increase_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Cost increase percentage"
    )
    currency = models.CharField(
        max_length=10,
        help_text="Currency code"
    )
    alert_message = models.TextField(
        help_text="Alert message content"
    )
    webhook_status = models.CharField(
        max_length=20,
        choices=WEBHOOK_STATUS_CHOICES,
        default=WEBHOOK_STATUS_PENDING,
        db_index=True
    )
    webhook_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Webhook response content"
    )
    webhook_error = models.TextField(
        blank=True,
        help_text="Webhook error message if failed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    class Meta:
        db_table = 'cloud_billing_alert_record'
        verbose_name = 'Alert Record'
        verbose_name_plural = 'Alert Records'
        indexes = [
            models.Index(fields=['provider', 'created_at']),
            models.Index(fields=['webhook_status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        time_str = self.created_at.strftime('%Y-%m-%d %H:%M')
        return (
            f"{self.provider.display_name} - {time_str} - "
            f"{self.increase_percent}%"
        )
