from django.db import models


class PriceSourceConfig(models.Model):
    """Primary vendor configuration managed from admin console."""

    vendor_slug = models.CharField(max_length=100, db_index=True, default="agione")
    platform_slug = models.CharField(max_length=100, unique=True, db_index=True)
    vendor_name = models.CharField(max_length=255)
    region = models.CharField(max_length=100, blank=True, default="")
    endpoint_url = models.URLField(max_length=1000)
    parser_llm_config_uuid = models.UUIDField(blank=True, null=True, db_index=True)
    currency = models.CharField(max_length=10, default="CNY")
    points_per_currency_unit = models.FloatField(default=10.0)
    is_enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor_slug", "region", "vendor_name", "id"]

    def __str__(self) -> str:
        suffix = f" / {self.region}" if self.region else ""
        return f"{self.vendor_name}{suffix} ({self.platform_slug})"


class PricingRecord(models.Model):
    """Hourly pricing snapshot for one vendor/model pair."""

    vendor_slug = models.CharField(max_length=100, db_index=True)
    vendor_name = models.CharField(max_length=255, db_index=True)
    vendor_pricing_url = models.URLField(max_length=1000, blank=True, null=True)
    model_slug = models.CharField(max_length=100, db_index=True)
    model_name = models.CharField(max_length=255, db_index=True)
    family = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=50, default="comparison", db_index=True)
    description = models.TextField(blank=True, null=True)
    source_url = models.URLField(max_length=1000, blank=True, null=True)
    input_price_per_million = models.FloatField(blank=True, null=True)
    output_price_per_million = models.FloatField(blank=True, null=True)
    currency = models.CharField(max_length=10, default="USD")
    source_type = models.CharField(max_length=50, default="catalog")
    raw_payload = models.JSONField(blank=True, null=True)
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    collected_hour = models.DateTimeField(db_index=True)
    synced_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vendor_slug", "model_slug", "collected_hour"],
                name="uq_ai_pricehub_vendor_model_hour",
            )
        ]
        ordering = ["-collected_hour", "model_name", "id"]

    def __str__(self) -> str:
        return (
            f"{self.vendor_name} / {self.model_name} / "
            f"{self.collected_hour:%Y-%m-%d %H:00}"
        )
