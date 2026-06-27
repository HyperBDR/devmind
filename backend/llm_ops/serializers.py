from decimal import Decimal

from rest_framework import serializers

from .collectors.official import OFFICIAL_PROVIDER_CONFIGS
from .models import (
    AuditLog,
    ChannelModelPrice,
    ChannelModelPriceHistory,
    CollectedModelPriceHistory,
    CollectedModelPriceSnapshot,
    LLMModel,
    ModelPriceItem,
    LLMProvider,
    MetaModel,
    PriceCollectionSource,
    PriceCollectionRun,
    ProcurementChannel,
    ResaleListingExclusion,
    ChannelPriceItem,
    ResaleListing,
    ResaleListingPriceHistory,
    ResalePlatform,
    ResaleWorkflowConfig,
    UsageReconciliationRecord,
)
from .services import (
    SUPPORTED_DISPLAY_CURRENCIES,
    calculate_channel_model_cost,
    normalize_currency,
    price_role_for_source,
    stable_fingerprint,
)
from .workflow_config import validate_resale_workflow_config


class PriceCollectionSourceSerializer(serializers.ModelSerializer):
    """Serializer for pricing sources and their business category."""

    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
        allow_null=True,
    )
    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
        allow_null=True,
    )
    business_source_category = serializers.SerializerMethodField()

    class Meta:
        model = PriceCollectionSource
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "last_collected_at")

    def get_business_source_category(self, instance):
        return business_source_category_for_catalog(instance)


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for immutable LLM operations audit records."""

    actor_username = serializers.CharField(
        source="actor.username",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = tuple(
            field.name for field in AuditLog._meta.fields
        )


class PriceCollectionRunSerializer(serializers.ModelSerializer):
    """Serializer for external pricing collection runs."""

    source_name = serializers.CharField(source="source.name", read_only=True)
    source_provider_name = serializers.CharField(
        source="source.provider.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = PriceCollectionRun
        fields = "__all__"
        read_only_fields = (
            "started_at",
            "finished_at",
        )


class CollectedModelPriceSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for latest normalized collected model price payloads."""

    source_name = serializers.CharField(source="source.name", read_only=True)
    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
        allow_null=True,
    )
    model_name = serializers.CharField(
        source="model.name",
        read_only=True,
        allow_null=True,
    )
    model_code = serializers.CharField(
        source="model.code",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = CollectedModelPriceSnapshot
        fields = "__all__"
        read_only_fields = ("collected_at",)


class CollectedModelPriceHistorySerializer(serializers.ModelSerializer):
    """Serializer for historical collected model price versions."""

    source_name = serializers.CharField(source="source.name", read_only=True)
    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
        allow_null=True,
    )
    model_name = serializers.CharField(
        source="model.name",
        read_only=True,
        allow_null=True,
    )
    model_code = serializers.CharField(
        source="model.code",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = CollectedModelPriceHistory
        fields = "__all__"
        read_only_fields = (
            "collected_at",
            "effective_from",
            "effective_to",
            "is_current",
        )


class LLMProviderSerializer(serializers.ModelSerializer):
    """Serializer for original LLM providers."""

    model_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = LLMProvider
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def create(self, validated_data):
        """Create provider and keep its official price source aligned."""
        provider = super().create(validated_data)
        sync_provider_official_source(provider)
        return provider

    def update(self, instance, validated_data):
        """Update provider and keep its official price source aligned."""
        provider = super().update(instance, validated_data)
        sync_provider_official_source(provider)
        return provider


def sync_provider_official_source(provider: LLMProvider) -> None:
    """Create or update the provider-bound official collection source."""
    config = OFFICIAL_PROVIDER_CONFIGS.get(provider.code)
    if config is None:
        return
    source, created = PriceCollectionSource.objects.get_or_create(
        slug=f"{provider.code}-official",
        defaults={
            "provider": provider,
            "name": f"{provider.name} 官方价格",
            "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            "source_category": (
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            "endpoint_url": config.source_url,
            "currency": config.currency,
            "is_enabled": True,
            "updates_model_prices": True,
            "notes": (
                "官方公开价格采集源；可使用官方价格页或 "
                "https://models.dev/api.json 作为数据源。"
            ),
        },
    )
    if created:
        return

    desired_fields = {
        "provider": provider,
        "name": f"{provider.name} 官方价格",
        "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
        "source_category": (
            PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ),
        "updates_model_prices": True,
        "notes": (
            "官方公开价格采集源；可使用官方价格页或 "
            "https://models.dev/api.json 作为数据源。"
        ),
    }
    if not source.endpoint_url:
        desired_fields["endpoint_url"] = config.source_url

    changed_fields = []
    for field, value in desired_fields.items():
        if getattr(source, field) != value:
            setattr(source, field, value)
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        source.save(update_fields=changed_fields)


def ensure_meta_model_for_price_data(data: dict) -> MetaModel:
    """Create or update a canonical model identity for a price record.

    The lookup key is the canonical ``code`` field, but the
    collector may report a price record under a slightly
    different spelling (for example ``deepseek-r1-250528`` for
    the row that is canonically known as ``deepseek-r1-0528``).
    To avoid creating duplicate meta-model rows, the function
    first searches the ``aliases`` JSONField for any match
    against the reported code or the legacy raw code. When a
    match is found the existing row is reused and the new code
    is added to its alias set so future lookups succeed without
    a database scan.
    """
    from .constants import canonical_meta_model_identity

    reported_code = str(data.get("code") or data.get("name") or "").strip()
    reported_name = str(data.get("name") or reported_code).strip()
    identity = canonical_meta_model_identity(reported_code, reported_name)
    code = identity["code"]
    name = identity["name"]
    provider = data.get("provider")
    raw_alias = str(data.get("raw_code") or "").strip()

    # Defensive: try to reuse a row whose ``aliases`` already
    # records this code (or a legacy spelling of it). This
    # keeps the canonical row count to one per release even
    # when multiple price sources disagree on the spelling.
    #
    # The lookup is implemented in Python rather than via
    # ``aliases__contains`` because SQLite (the default dev
    # backend) does not support the JSON ``contains`` lookup.
    # The meta-model table is small enough (low hundreds of
    # rows) that an in-process scan stays well below 5 ms even
    # on a developer laptop.
    tokens = [
        t
        for t in (
            raw_alias,
            reported_code,
            reported_name,
            code,
            name,
            *identity["aliases"],
        )
        if t
    ]
    existing = None
    if tokens:
        all_meta = list(MetaModel.objects.all())
        alias_index = {
            alias: meta
            for meta in all_meta
            for alias in (meta.aliases or [])
        }
        for token in tokens:
            hit = alias_index.get(token)
            if hit is not None:
                existing = hit
                break
        # When the reported code/name does not appear in any
        # alias, fall back to a normalised name match. This
        # covers the common case where two price sources
        # disagree on the code spelling (for example
        # ``deepseek-r1-0528`` vs ``deepseek-r1-250528``)
        # but agree on the human readable name.
        if existing is None and name:
            normalised = name.strip().lower().replace(" ", "")
            for meta in all_meta:
                if (meta.name or "").strip().lower().replace(" ", "") == normalised:
                    existing = meta
                    break
    if existing is not None:
        merged = list(existing.aliases or [])
        for token in tokens:
            if token and token not in merged:
                merged.append(token)
        changed = merged != list(existing.aliases or [])
        if changed:
            existing.aliases = merged
            existing.save(update_fields=["aliases", "updated_at"])
        return existing

    seed_aliases: list[str] = []
    for token in tokens:
        if token and token not in seed_aliases and token != code:
            seed_aliases.append(token)

    defaults = {
        "name": name,
        "vendor": provider,
        "modality": data.get("modality") or MetaModel.MODALITY_TEXT,
        "context_window": data.get("context_window") or 0,
        "max_output_tokens": data.get("max_output_tokens") or 0,
        "status": MetaModel.STATUS_ACTIVE,
        "aliases": seed_aliases,
    }
    meta_model, _ = MetaModel.objects.update_or_create(
        code=code,
        defaults=defaults,
    )
    return meta_model


class MetaModelSerializer(serializers.ModelSerializer):
    """Serializer for canonical model identities.

    The ``vendor`` field is recomputed through the canonical
    vendor rules so the API never returns a supplier alias
    (``siliconflow``) or a wrong attribution (deepseek model
    owned by Aliyun). The original pointer is preserved on
    ``raw_vendor`` for debugging.
    """

    vendor_name = serializers.CharField(
        source="vendor.name",
        read_only=True,
        allow_null=True,
    )
    provider_price_count = serializers.IntegerField(
        read_only=True,
        required=False,
    )
    raw_vendor = serializers.IntegerField(
        source="vendor_id",
        read_only=True,
        allow_null=True,
    )
    effective_vendor = serializers.SerializerMethodField()
    effective_vendor_code = serializers.SerializerMethodField()
    effective_vendor_name = serializers.SerializerMethodField()
    release_date = serializers.SerializerMethodField()

    class Meta:
        model = MetaModel
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def get_effective_vendor(self, instance):
        canonical = self._canonical_vendor(instance)
        if canonical is not None:
            return canonical["provider"].id
        return instance.vendor_id

    def get_effective_vendor_code(self, instance):
        canonical = self._canonical_vendor(instance)
        if canonical is not None:
            return canonical["provider"].code
        if instance.vendor_id:
            return instance.vendor.code
        return ""

    def get_effective_vendor_name(self, instance):
        canonical = self._canonical_vendor(instance)
        if canonical is not None:
            return canonical["provider"].name
        if instance.vendor_id:
            return instance.vendor.name
        return ""

    def get_release_date(self, instance):
        metadata = instance.metadata or {}
        models_dev = metadata.get("models_dev") or {}
        return (
            models_dev.get("release_date")
            or models_dev.get("last_updated")
            or ""
        )

    @staticmethod
    def _canonical_vendor(instance):
        from .constants import canonical_vendor_for_model_code

        spec = canonical_vendor_for_model_code(instance.code)
        if not spec:
            return None
        from .seed_data import ensure_canonical_vendor_row
        provider = ensure_canonical_vendor_row(spec)
        if not provider:
            return None
        return {"spec": spec, "provider": provider}


class LLMModelSerializer(serializers.ModelSerializer):
    """Serializer for model SKUs and benchmark prices."""

    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    meta_model_vendor = serializers.IntegerField(
        source="meta_model.vendor_id",
        read_only=True,
        allow_null=True,
    )
    meta_model_vendor_name = serializers.CharField(
        source="meta_model.vendor.name",
        read_only=True,
        allow_null=True,
    )
    meta_model_vendor_code = serializers.CharField(
        source="meta_model.vendor.code",
        read_only=True,
        allow_null=True,
    )
    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
    )
    provider_code = serializers.CharField(
        source="provider.code",
        read_only=True,
    )
    source_name = serializers.CharField(
        source="source.name",
        read_only=True,
        allow_null=True,
    )
    source_category = serializers.CharField(
        source="source.source_category",
        read_only=True,
        allow_null=True,
    )
    source_endpoint_url = serializers.CharField(
        source="source.endpoint_url",
        read_only=True,
        allow_null=True,
    )
    business_source_category = serializers.SerializerMethodField()

    class Meta:
        model = LLMModel
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "meta_model": {"required": False},
        }

    def validate(self, attrs):
        source = attrs.get("source")
        if source and not attrs.get("price_role"):
            attrs["price_role"] = price_role_for_source(
                source,
                meta_model=attrs.get("meta_model"),
            )
        return attrs

    def create(self, validated_data):
        if not validated_data.get("meta_model"):
            validated_data["meta_model"] = ensure_meta_model_for_price_data(
                validated_data,
            )
        if validated_data.get("source"):
            validated_data["price_role"] = price_role_for_source(
                validated_data["source"],
                meta_model=validated_data.get("meta_model"),
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get("meta_model") and not instance.meta_model_id:
            merged = {
                "name": validated_data.get("name", instance.name),
                "code": validated_data.get("code", instance.code),
                "provider": validated_data.get("provider", instance.provider),
                "modality": validated_data.get("modality", instance.modality),
                "context_window": validated_data.get(
                    "context_window",
                    instance.context_window,
                ),
                "max_output_tokens": validated_data.get(
                    "max_output_tokens",
                    instance.max_output_tokens,
                ),
            }
            validated_data["meta_model"] = ensure_meta_model_for_price_data(
                merged,
            )
        if validated_data.get("source", instance.source):
            validated_data["price_role"] = price_role_for_source(
                validated_data.get("source", instance.source),
                meta_model=validated_data.get(
                    "meta_model",
                    instance.meta_model,
                ),
            )
        return super().update(instance, validated_data)

    def get_business_source_category(self, instance):
        return business_source_category_for_model(instance)


class ModelPriceItemSerializer(serializers.ModelSerializer):
    """Serializer for normalized official model price items."""

    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
    )
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    meta_model_vendor = serializers.IntegerField(
        source="meta_model.vendor_id",
        read_only=True,
        allow_null=True,
    )
    meta_model_vendor_name = serializers.CharField(
        source="meta_model.vendor.name",
        read_only=True,
        allow_null=True,
    )
    meta_model_vendor_code = serializers.CharField(
        source="meta_model.vendor.code",
        read_only=True,
        allow_null=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    source_name = serializers.CharField(
        source="source.name",
        read_only=True,
        allow_null=True,
    )
    source_category = serializers.CharField(
        source="source.source_category",
        read_only=True,
        allow_null=True,
    )
    source_endpoint_url = serializers.CharField(
        source="source.endpoint_url",
        read_only=True,
        allow_null=True,
    )
    source_channel_name = serializers.CharField(
        source="source.channel.name",
        read_only=True,
        allow_null=True,
    )
    source_provider_name = serializers.CharField(
        source="source.provider.name",
        read_only=True,
        allow_null=True,
    )
    business_source_category = serializers.SerializerMethodField()

    class Meta:
        model = ModelPriceItem
        fields = "__all__"
        extra_kwargs = {
            "meta_model": {"required": False},
        }
        read_only_fields = (
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        )

    def validate_currency(self, value):
        return validate_currency_code(value, required=True)

    def validate_unit_price(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("unit_price must be >= 0.")
        return value

    def create(self, validated_data):
        validated_data["meta_model"] = validated_data["model"].meta_model
        validated_data.setdefault(
            "price_fingerprint",
            model_price_item_fingerprint(validated_data),
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        model = validated_data.get("model", instance.model)
        validated_data["meta_model"] = model.meta_model
        if price_item_fingerprint_fields_touched(validated_data):
            validated_data["price_fingerprint"] = model_price_item_fingerprint(
                validated_data,
                instance=instance,
            )
        return super().update(instance, validated_data)

    def get_business_source_category(self, instance):
        return business_source_category_for_price_item(instance)


def canonical_vendor_for_meta_model(meta_model):
    """Resolve the real vendor for one canonical meta model."""
    if meta_model is None:
        return None

    canonical = MetaModelSerializer._canonical_vendor(meta_model)
    if canonical is not None:
        return canonical["provider"]
    return meta_model.vendor


def business_source_category_for_source_model(*, source, meta_model):
    """Return official only when the source vendor owns the model."""
    raw_category = source.source_category
    if (
        raw_category
        != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return raw_category

    source_vendor_id = source.provider_id
    model_vendor = canonical_vendor_for_meta_model(meta_model)
    model_vendor_id = getattr(model_vendor, "id", None)
    if not source_vendor_id or not model_vendor_id:
        return raw_category
    if source_vendor_id == model_vendor_id:
        return raw_category
    return PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER


def business_source_category_for_model(model):
    """Return the business category for one provider model row."""
    source = model.source
    if source is None:
        return PriceCollectionSource.SOURCE_CATEGORY_UNKNOWN
    return business_source_category_for_source_model(
        source=source,
        meta_model=model.meta_model,
    )


def business_source_category_for_price_item(item):
    """Return the business category for one normalized price row."""
    source = item.source or getattr(item.model, "source", None)
    if source is None:
        return PriceCollectionSource.SOURCE_CATEGORY_UNKNOWN
    meta_model = item.meta_model or getattr(item.model, "meta_model", None)
    return business_source_category_for_source_model(
        source=source,
        meta_model=meta_model,
    )


def business_source_category_for_catalog(source):
    """Return the business category for a whole price catalog."""
    raw_category = source.source_category
    if (
        raw_category
        != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
    ):
        return raw_category

    models = list(
        source.models.select_related("meta_model", "meta_model__vendor")
    )
    if not models:
        return raw_category

    for model in models:
        category = business_source_category_for_source_model(
            source=source,
            meta_model=model.meta_model,
        )
        if (
            category
            != PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
        ):
            return PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER
    return raw_category


def price_item_fingerprint_fields_touched(data: dict) -> bool:
    """Return whether a price-affecting field changed."""
    fields = {
        "source",
        "dimension",
        "billing_unit",
        "currency",
        "unit_price",
        "tier_type",
        "tier_start",
        "tier_end",
        "spec",
    }
    return bool(fields.intersection(data.keys()))


def model_price_item_fingerprint(
    data: dict,
    *,
    instance: ModelPriceItem | None = None,
) -> str:
    """Build a stable fingerprint for one normalized price item."""
    return stable_fingerprint(
        {
            "source": related_id(data, "source", instance),
            "dimension": data.get(
                "dimension",
                getattr(instance, "dimension", ""),
            ),
            "billing_unit": data.get(
                "billing_unit",
                getattr(instance, "billing_unit", ""),
            ),
            "currency": data.get("currency", getattr(instance, "currency", "")),
            "unit_price": str(
                data.get("unit_price", getattr(instance, "unit_price", "")),
            ),
            "tier_type": data.get(
                "tier_type",
                getattr(instance, "tier_type", ""),
            ),
            "tier_start": str(
                data.get("tier_start", getattr(instance, "tier_start", "")) or ""
            ),
            "tier_end": str(
                data.get("tier_end", getattr(instance, "tier_end", "")) or ""
            ),
            "spec": data.get("spec", getattr(instance, "spec", {}) or {}),
        }
    )


def related_id(data: dict, field: str, instance) -> int | None:
    """Return the id for a relation in serializer validated data."""
    if field in data:
        value = data[field]
        return value.id if value is not None else None
    if instance is None:
        return None
    value = getattr(instance, field, None)
    return value.id if value is not None else None


class ProcurementChannelSerializer(serializers.ModelSerializer):
    """Serializer for upstream procurement channels."""

    configured_model_count = serializers.IntegerField(
        read_only=True,
        required=False,
    )
    listed_model_count = serializers.IntegerField(
        read_only=True,
        required=False,
    )
    total_model_count = serializers.IntegerField(
        read_only=True,
        required=False,
    )
    listed_provider_count = serializers.IntegerField(
        read_only=True,
        required=False,
    )

    class Meta:
        model = ProcurementChannel
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate_settlement_ratio(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("settlement_ratio must be > 0.")
        return value

    def validate_currency(self, value):
        return validate_currency_code(value, required=True)


class ChannelModelPriceSerializer(serializers.ModelSerializer):
    """Serializer for channel model listing and price overrides."""

    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    provider_name = serializers.CharField(
        source="model.provider.name",
        read_only=True,
    )
    price_source_name = serializers.CharField(
        source="price_source.name",
        read_only=True,
        allow_null=True,
    )
    price_source_category = serializers.CharField(
        source="price_source.source_category",
        read_only=True,
        allow_null=True,
    )
    price_source_endpoint_url = serializers.CharField(
        source="price_source.endpoint_url",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChannelModelPrice
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "meta_model": {"required": False},
        }

    def validate(self, attrs):
        if "currency" in attrs:
            attrs["currency"] = validate_currency_code(
                attrs.get("currency"),
                required=False,
            )
        ratio = attrs.get("settlement_ratio")
        if ratio is not None and ratio <= Decimal("0"):
            raise serializers.ValidationError(
                {"settlement_ratio": "settlement_ratio must be > 0."}
            )
        price_fields = (
            "custom_input_price_per_million",
            "custom_output_price_per_million",
            "custom_audio_input_price_per_second",
            "custom_audio_output_price_per_second",
            "custom_video_input_price_per_second",
            "custom_video_output_price_per_second",
        )
        validate_non_negative_prices(attrs, price_fields)
        return attrs

    def create(self, validated_data):
        validated_data["meta_model"] = validated_data["model"].meta_model
        return super().create(validated_data)

    def update(self, instance, validated_data):
        model = validated_data.get("model", instance.model)
        validated_data["meta_model"] = model.meta_model
        return super().update(instance, validated_data)


class ChannelModelPriceHistorySerializer(serializers.ModelSerializer):
    """Serializer for historical channel/model price versions."""

    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    provider_name = serializers.CharField(
        source="model.provider.name",
        read_only=True,
    )
    price_source_name = serializers.CharField(
        source="price_source.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChannelModelPriceHistory
        fields = "__all__"
        read_only_fields = (
            "effective_from",
            "effective_to",
            "is_current",
            "created_at",
        )


class ChannelPriceItemSerializer(serializers.ModelSerializer):
    """Serializer for normalized channel procurement price items."""

    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
    )
    provider_name = serializers.CharField(
        source="model.provider.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    source_name = serializers.CharField(
        source="source.name",
        read_only=True,
        allow_null=True,
    )
    source_category = serializers.CharField(
        source="source.source_category",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChannelPriceItem
        fields = "__all__"
        extra_kwargs = {
            "meta_model": {"required": False},
        }
        read_only_fields = (
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        )

    def validate_currency(self, value):
        return validate_currency_code(value, required=True)

    def validate_unit_price(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("unit_price must be >= 0.")
        return value

    def create(self, validated_data):
        validated_data["meta_model"] = validated_data["model"].meta_model
        return super().create(validated_data)

    def update(self, instance, validated_data):
        model = validated_data.get("model", instance.model)
        validated_data["meta_model"] = model.meta_model
        return super().update(instance, validated_data)


class ResalePlatformSerializer(serializers.ModelSerializer):
    """Serializer for downstream resale platforms."""

    listing_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ResalePlatform
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate_fee_rate(self, value):
        if value < Decimal("0") or value >= Decimal("1"):
            raise serializers.ValidationError("fee_rate must be >= 0 and < 1.")
        return value

    def validate_service_fee_rate(self, value):
        if value < Decimal("0") or value >= Decimal("1"):
            raise serializers.ValidationError(
                "service_fee_rate must be >= 0 and < 1."
            )
        return value

    def validate_auto_approve_max_margin_rate(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError(
                "auto_approve_max_margin_rate must be >= 0."
            )
        return value

    def validate_currency(self, value):
        return validate_currency_code(value, required=True)

    def validate_points_per_currency_unit(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "points_per_currency_unit must be > 0."
            )
        return value

    def validate_metadata(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object.")
        return value


class ResaleListingSerializer(serializers.ModelSerializer):
    """Serializer for downstream resale listing prices."""

    platform_name = serializers.CharField(
        source="platform.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ResaleListing
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "meta_model": {"required": False},
        }
        validators = []

    def validate(self, attrs):
        if "currency" in attrs:
            attrs["currency"] = validate_currency_code(
                attrs.get("currency"),
                required=False,
            )
        validate_non_negative_prices(
            attrs,
            (
                "retail_input_price_per_million",
                "retail_output_price_per_million",
                "retail_cache_input_price_per_million",
                "retail_image_output_price_per_image",
                "retail_audio_input_price_per_second",
                "retail_audio_output_price_per_second",
                "retail_video_input_price_per_second",
                "retail_video_output_price_per_second",
            ),
        )
        return attrs

    def create(self, validated_data):
        validated_data["meta_model"] = validated_data["model"].meta_model
        return super().create(validated_data)

    def update(self, instance, validated_data):
        model = validated_data.get("model", instance.model)
        validated_data["meta_model"] = model.meta_model
        return super().update(instance, validated_data)


class ResaleListingExclusionSerializer(serializers.ModelSerializer):
    """Serializer for models removed from a resale workbench list."""

    platform_name = serializers.CharField(
        source="platform.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )

    class Meta:
        model = ResaleListingExclusion
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            "meta_model": {"required": False},
        }

    def create(self, validated_data):
        validated_data["meta_model"] = validated_data["model"].meta_model
        return super().create(validated_data)

    def update(self, instance, validated_data):
        model = validated_data.get("model", instance.model)
        validated_data["meta_model"] = model.meta_model
        return super().update(instance, validated_data)


class ResaleListingPriceHistorySerializer(serializers.ModelSerializer):
    """Serializer for historical downstream listing price versions."""

    platform_name = serializers.CharField(
        source="platform.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ResaleListingPriceHistory
        fields = "__all__"
        read_only_fields = (
            "effective_from",
            "effective_to",
            "is_current",
            "created_at",
        )


class ResaleWorkflowConfigSerializer(serializers.ModelSerializer):
    """Serializer for resale workflow visual configuration."""

    platform_name = serializers.CharField(
        source="platform.name",
        read_only=True,
    )

    class Meta:
        model = ResaleWorkflowConfig
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate_config(self, value):
        return validate_resale_workflow_config(value)


class UsageReconciliationRecordSerializer(serializers.ModelSerializer):
    """Serializer for usage reconciliation records."""

    channel_name = serializers.CharField(
        source="channel.name",
        read_only=True,
    )
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_code = serializers.CharField(source="model.code", read_only=True)
    meta_model_name = serializers.CharField(
        source="meta_model.name",
        read_only=True,
    )
    meta_model_code = serializers.CharField(
        source="meta_model.code",
        read_only=True,
    )
    provider_name = serializers.CharField(
        source="model.provider.name",
        read_only=True,
    )
    expected_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        read_only=True,
    )
    discrepancy = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        read_only=True,
    )
    discrepancy_percent = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        read_only=True,
    )
    status = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = UsageReconciliationRecord
        fields = "__all__"
        extra_kwargs = {
            "meta_model": {"required": False},
        }
        read_only_fields = (
            "created_at",
            "updated_at",
            "expected_amount",
            "discrepancy",
            "discrepancy_percent",
            "status",
        )

    def _apply_calculation(self, attrs):
        channel = attrs.get("channel")
        model = attrs.get("model")
        if not channel or not model:
            return attrs
        attrs["meta_model"] = model.meta_model

        expected = calculate_channel_model_cost(
            channel,
            model,
            input_tokens=attrs.get("input_tokens") or 0,
            output_tokens=attrs.get("output_tokens") or 0,
            audio_input_seconds=attrs.get("audio_input_seconds") or 0,
            audio_output_seconds=attrs.get("audio_output_seconds") or 0,
            video_input_seconds=attrs.get("video_input_seconds") or 0,
            video_output_seconds=attrs.get("video_output_seconds") or 0,
            video_resolution=attrs.get("video_resolution") or "",
        )
        charged = attrs.get("charged_amount") or Decimal("0")
        discrepancy = expected - charged
        discrepancy_percent = Decimal("0")
        if expected:
            discrepancy_percent = (discrepancy / expected) * Decimal("100")

        status = UsageReconciliationRecord.STATUS_PERFECT
        if discrepancy < Decimal("-0.05"):
            status = UsageReconciliationRecord.STATUS_OVERCHARGED
        elif discrepancy > Decimal("0.05"):
            status = UsageReconciliationRecord.STATUS_UNDERCHARGED

        attrs["expected_amount"] = expected
        attrs["discrepancy"] = discrepancy.quantize(Decimal("0.000001"))
        attrs["discrepancy_percent"] = discrepancy_percent.quantize(
            Decimal("0.0001")
        )
        attrs["status"] = status
        return attrs

    def create(self, validated_data):
        return super().create(self._apply_calculation(validated_data))

    def update(self, instance, validated_data):
        merged = {
            field.name: getattr(instance, field.name)
            for field in instance._meta.fields
            if field.name not in ("id", "created_at", "updated_at")
        }
        merged.update(validated_data)
        self._apply_calculation(merged)
        for key, value in merged.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class YunceCollectionRequestSerializer(serializers.Serializer):
    """Validate Yunce collection request credentials."""

    source_id = serializers.PrimaryKeyRelatedField(
        queryset=PriceCollectionSource.objects.filter(
            source_type=PriceCollectionSource.SOURCE_TYPE_YUNCE,
            is_enabled=True,
        ),
        required=False,
        source="source",
        write_only=True,
    )
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    base_url = serializers.URLField(required=False)


class ManualPriceImportRowSerializer(serializers.Serializer):
    """Validate one manually imported model pricing row."""

    model_code = serializers.CharField(max_length=150)
    model_name = serializers.CharField(max_length=255, required=False)
    modality = serializers.ChoiceField(
        choices=LLMModel.MODALITY_CHOICES,
        required=False,
    )
    currency = serializers.CharField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)
    input_price_per_million = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    output_price_per_million = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    cache_input_price_per_million = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    image_output_price_per_image = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    audio_input_price_per_second = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    audio_output_price_per_second = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    video_input_price_per_second = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    video_output_price_per_second = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        allow_null=True,
    )

    def validate_currency(self, value):
        return validate_currency_code(value, required=False)

    def validate(self, attrs):
        price_fields = (
            "input_price_per_million",
            "output_price_per_million",
            "cache_input_price_per_million",
            "image_output_price_per_image",
            "audio_input_price_per_second",
            "audio_output_price_per_second",
            "video_input_price_per_second",
            "video_output_price_per_second",
        )
        validate_non_negative_prices(attrs, price_fields)
        if not any(attrs.get(field) is not None for field in price_fields):
            raise serializers.ValidationError(
                "At least one price field is required."
            )
        return attrs


class ManualPriceImportRequestSerializer(serializers.Serializer):
    """Validate a manual pricing table import request."""

    source = serializers.PrimaryKeyRelatedField(
        queryset=PriceCollectionSource.objects.all(),
        required=False,
        write_only=True,
    )
    provider = serializers.PrimaryKeyRelatedField(
        queryset=LLMProvider.objects.filter(is_active=True),
    )
    source_name = serializers.CharField(max_length=255)
    source_slug = serializers.SlugField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    source_url = serializers.URLField(required=False, allow_blank=True)
    currency = serializers.CharField(default="USD")
    updates_model_prices = serializers.BooleanField(default=True)
    rows = ManualPriceImportRowSerializer(many=True)

    def validate_currency(self, value):
        return validate_currency_code(value, required=True)


def validate_non_negative_prices(attrs, fields):
    """Reject negative price values in DRF serializer attrs."""
    errors = {}
    for field in fields:
        value = attrs.get(field)
        if value is not None and value < Decimal("0"):
            errors[field] = "price must be >= 0."
    if errors:
        raise serializers.ValidationError(errors)


def validate_currency_code(value, *, required: bool) -> str:
    """Normalize and validate settlement currency codes."""
    currency = normalize_currency(value)
    if not currency and required:
        raise serializers.ValidationError("currency is required.")
    if currency and currency not in SUPPORTED_DISPLAY_CURRENCIES:
        raise serializers.ValidationError("currency must be CNY or USD.")
    return currency
