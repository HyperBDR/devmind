from django.contrib import admin

from .models import PriceSourceConfig, PricingRecord


@admin.register(PriceSourceConfig)
class PriceSourceConfigAdmin(admin.ModelAdmin):
    list_display = (
        "vendor_name",
        "vendor_slug",
        "region",
        "endpoint_url",
        "currency",
        "points_per_currency_unit",
        "is_enabled",
        "updated_at",
    )
    search_fields = ("vendor_name", "vendor_slug", "region")
    list_filter = ("is_enabled", "currency")


@admin.register(PricingRecord)
class PricingRecordAdmin(admin.ModelAdmin):
    list_display = (
        "vendor_name",
        "model_name",
        "role",
        "currency",
        "input_price_per_million",
        "output_price_per_million",
        "collected_hour",
        "synced_at",
    )
    search_fields = ("vendor_name", "model_name", "vendor_slug", "model_slug")
    list_filter = ("role", "currency", "vendor_slug", "collected_hour")
