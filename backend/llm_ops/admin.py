from django.contrib import admin

from .models import (
    AuditLog,
    ChannelModelPrice,
    ChannelModelPriceHistory,
    ChannelPriceItem,
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResaleListing,
    ResaleListingExclusion,
    ResaleListingPriceHistory,
    ResalePlatform,
    ResaleWorkflowConfig,
    UsageReconciliationRecord,
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "actor_identifier",
        "category",
        "action",
        "target_type",
        "target_id",
        "summary",
    )
    list_filter = ("category", "action", "target_type", "created_at")
    search_fields = (
        "actor_identifier",
        "target_type",
        "target_id",
        "target_repr",
        "summary",
    )
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)


@admin.register(PriceCollectionSource)
class PriceCollectionSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_category",
        "provider",
        "channel",
        "slug",
        "source_type",
        "currency",
        "is_enabled",
    )
    list_filter = (
        "source_category",
        "provider",
        "channel",
        "source_type",
        "is_enabled",
        "currency",
    )
    search_fields = (
        "name",
        "slug",
        "provider__name",
        "channel__name",
        "endpoint_url",
    )


@admin.register(PriceCollectionRun)
class PriceCollectionRunAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "status",
        "started_at",
        "finished_at",
        "collected_count",
        "created_count",
        "updated_count",
    )
    list_filter = ("source", "status")
    search_fields = ("source__name", "error_message")


@admin.register(CollectedModelPriceSnapshot)
class CollectedModelPriceSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "source_model_name",
        "source_provider_name",
        "source_model_type",
        "currency",
        "collected_at",
    )
    list_filter = ("source", "source_model_type", "currency")
    search_fields = (
        "source_model_name",
        "source_model_id",
        "source_provider_name",
    )


@admin.register(CollectedModelPriceHistory)
class CollectedModelPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "source_model_name",
        "source_provider_name",
        "source_model_type",
        "currency",
        "effective_from",
        "effective_to",
        "is_current",
    )
    list_filter = (
        "source",
        "source_model_type",
        "currency",
        "is_current",
    )
    search_fields = (
        "source_model_name",
        "source_model_id",
        "source_provider_name",
        "price_fingerprint",
    )


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "website", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(MetaModel)
class MetaModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "vendor",
        "modality",
        "status",
        "context_window",
        "max_output_tokens",
    )
    list_filter = ("vendor", "modality", "status")
    search_fields = ("name", "code", "family")


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider",
        "code",
        "modality",
        "currency",
        "is_active",
    )
    list_filter = ("provider", "modality", "currency", "is_active")
    search_fields = ("name", "code", "provider__name")


@admin.register(ModelPriceItem)
class ModelPriceItemAdmin(admin.ModelAdmin):
    list_display = (
        "model",
        "dimension",
        "billing_unit",
        "currency",
        "unit_price",
        "tier_type",
        "is_current",
    )
    list_filter = (
        "provider",
        "dimension",
        "billing_unit",
        "currency",
        "is_current",
    )
    search_fields = ("model__name", "model__code", "provider__name")


@admin.register(ProcurementChannel)
class ProcurementChannelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "currency",
        "settlement_ratio",
        "is_active",
    )
    list_filter = ("currency", "is_active")
    search_fields = ("name", "code", "api_endpoint")


@admin.register(ChannelModelPrice)
class ChannelModelPriceAdmin(admin.ModelAdmin):
    list_display = (
        "channel",
        "model",
        "price_source",
        "currency",
        "is_listed",
        "settlement_ratio",
    )
    list_filter = ("channel", "price_source", "currency", "is_listed")
    search_fields = (
        "channel__name",
        "model__name",
        "model__code",
        "price_source__name",
    )


@admin.register(ChannelModelPriceHistory)
class ChannelModelPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "channel",
        "model",
        "price_source",
        "currency",
        "input_price_per_million",
        "output_price_per_million",
        "effective_from",
        "is_current",
    )
    list_filter = ("channel", "price_source", "currency", "is_current")
    search_fields = (
        "channel__name",
        "model__name",
        "model__code",
        "price_source__name",
    )


@admin.register(ChannelPriceItem)
class ChannelPriceItemAdmin(admin.ModelAdmin):
    list_display = (
        "channel",
        "model",
        "source",
        "dimension",
        "billing_unit",
        "currency",
        "unit_price",
        "comparison_status",
        "is_current",
    )
    list_filter = (
        "channel",
        "source",
        "dimension",
        "billing_unit",
        "currency",
        "comparison_status",
        "is_current",
    )
    search_fields = ("channel__name", "model__name", "model__code")


@admin.register(ResalePlatform)
class ResalePlatformAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "platform_type",
        "region_code",
        "environment",
        "currency",
        "has_api_key",
        "points_per_currency_unit",
        "fee_rate",
        "service_fee_rate",
        "auto_approve_max_margin_rate",
        "is_active",
    )
    list_filter = ("platform_type", "environment", "currency", "is_active")
    search_fields = ("name", "code", "region_code", "region_name")

    def has_api_key(self, obj):
        return bool(obj.api_key)

    has_api_key.boolean = True
    has_api_key.short_description = "API Key"


@admin.register(ResaleWorkflowConfig)
class ResaleWorkflowConfigAdmin(admin.ModelAdmin):
    list_display = ("platform", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("platform__name", "platform__code", "notes")


@admin.register(ResaleListing)
class ResaleListingAdmin(admin.ModelAdmin):
    list_display = ("platform", "model", "channel", "currency", "is_active")
    list_filter = ("platform", "currency", "is_active")
    search_fields = ("platform__name", "model__name", "model__code")


@admin.register(ResaleListingExclusion)
class ResaleListingExclusionAdmin(admin.ModelAdmin):
    list_display = ("platform", "model", "updated_at")
    list_filter = ("platform",)
    search_fields = ("platform__name", "model__name", "model__code")


@admin.register(ResaleListingPriceHistory)
class ResaleListingPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "model",
        "channel",
        "currency",
        "retail_input_price_per_million",
        "retail_output_price_per_million",
        "effective_from",
        "is_current",
    )
    list_filter = ("platform", "channel", "currency", "is_current")
    search_fields = ("platform__name", "model__name", "model__code")


@admin.register(UsageReconciliationRecord)
class UsageReconciliationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "channel",
        "model",
        "charged_amount",
        "expected_amount",
        "status",
    )
    list_filter = ("status", "channel", "date")
    search_fields = ("channel__name", "model__name", "model__code")
