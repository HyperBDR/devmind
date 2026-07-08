from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from hyperbdr_dashboard.encryption import encryption_service


def _ensure_meta_model_from_model(instance, kwargs):
    """Copy the canonical model reference from the selected model."""
    if not instance.model_id:
        return

    model_meta_model_id = instance.model.meta_model_id
    if instance.meta_model_id == model_meta_model_id:
        return

    instance.meta_model_id = model_meta_model_id
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        kwargs["update_fields"] = list(set(update_fields) | {"meta_model"})


class PriceCollectionSource(models.Model):
    """Pricing source for official, supplier, or manual price catalogs."""

    CLOUD_PROVIDER_OFFICIAL_CODES = {
        "aliyun",
        "aliyun-wanx",
        "azure-openai",
        "baidu",
        "volcengine",
    }

    SOURCE_TYPE_AGIONE = "agione"
    SOURCE_TYPE_YUNCE = "yunce"
    SOURCE_TYPE_CUSTOM = "custom"

    SOURCE_CATEGORY_OFFICIAL_PROVIDER = "official_provider"
    SOURCE_CATEGORY_SUPPLIER = "supplier"
    SOURCE_CATEGORY_MANUAL = "manual"
    SOURCE_CATEGORY_UNKNOWN = "unknown"

    SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL = "model_provider_official"
    SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL = "cloud_provider_official"
    SOURCE_OWNER_SUPPLIER = "supplier"
    SOURCE_OWNER_INTERNAL = "internal"
    SOURCE_OWNER_UNKNOWN = "unknown"

    COLLECTION_METHOD_AUTO_COLLECT = "auto_collect"
    COLLECTION_METHOD_MANUAL_ENTRY = "manual_entry"
    COLLECTION_METHOD_MANUAL_IMPORT = "manual_import"
    COLLECTION_METHOD_API_SYNC = "api_sync"
    COLLECTION_METHOD_UNKNOWN = "unknown"

    SOURCE_TYPE_CHOICES = (
        (SOURCE_TYPE_AGIONE, "Agione"),
        (SOURCE_TYPE_YUNCE, "Yunce"),
        (SOURCE_TYPE_CUSTOM, "Custom"),
    )

    SOURCE_CATEGORY_CHOICES = (
        (SOURCE_CATEGORY_OFFICIAL_PROVIDER, "Official Provider"),
        (SOURCE_CATEGORY_SUPPLIER, "Supplier"),
        (SOURCE_CATEGORY_MANUAL, "Manual"),
        (SOURCE_CATEGORY_UNKNOWN, "Unknown"),
    )

    SOURCE_OWNER_TYPE_CHOICES = (
        (SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL, "Model Provider Official"),
        (SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL, "Cloud Provider Official"),
        (SOURCE_OWNER_SUPPLIER, "Supplier"),
        (SOURCE_OWNER_INTERNAL, "Internal"),
        (SOURCE_OWNER_UNKNOWN, "Unknown"),
    )

    COLLECTION_METHOD_CHOICES = (
        (COLLECTION_METHOD_AUTO_COLLECT, "Auto Collect"),
        (COLLECTION_METHOD_MANUAL_ENTRY, "Manual Entry"),
        (COLLECTION_METHOD_MANUAL_IMPORT, "Manual Import"),
        (COLLECTION_METHOD_API_SYNC, "API Sync"),
        (COLLECTION_METHOD_UNKNOWN, "Unknown"),
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    provider = models.ForeignKey(
        "LLMProvider",
        related_name="collection_sources",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        "ProcurementChannel",
        related_name="price_sources",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        default=SOURCE_TYPE_CUSTOM,
    )
    source_category = models.CharField(
        max_length=50,
        choices=SOURCE_CATEGORY_CHOICES,
        default=SOURCE_CATEGORY_UNKNOWN,
    )
    source_owner_type = models.CharField(
        max_length=50,
        choices=SOURCE_OWNER_TYPE_CHOICES,
        default=SOURCE_OWNER_UNKNOWN,
    )
    collection_method = models.CharField(
        max_length=50,
        choices=COLLECTION_METHOD_CHOICES,
        default=COLLECTION_METHOD_UNKNOWN,
    )
    endpoint_url = models.URLField(max_length=1000, blank=True, default="")
    currency = models.CharField(max_length=10, default="USD")
    is_enabled = models.BooleanField(default=True)
    updates_model_prices = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    last_collected_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        """Normalize required source classification fields before saving."""
        self._fill_required_classification_fields()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({"source_owner_type", "collection_method"})
            kwargs["update_fields"] = list(update_fields)
        super().save(*args, **kwargs)

    def _fill_required_classification_fields(self):
        """Apply source classification defaults for legacy creation paths."""
        if not self.source_owner_type:
            self.source_owner_type = self._default_source_owner_type()
        if not self.collection_method:
            self.collection_method = self._default_collection_method()

    def _default_source_owner_type(self):
        if self.source_category == self.SOURCE_CATEGORY_OFFICIAL_PROVIDER:
            provider_code = str(getattr(self.provider, "code", "")).lower()
            if provider_code in self.CLOUD_PROVIDER_OFFICIAL_CODES:
                return self.SOURCE_OWNER_CLOUD_PROVIDER_OFFICIAL
            return self.SOURCE_OWNER_MODEL_PROVIDER_OFFICIAL
        if self.source_category == self.SOURCE_CATEGORY_SUPPLIER:
            return self.SOURCE_OWNER_SUPPLIER
        if self.source_category == self.SOURCE_CATEGORY_MANUAL:
            return self.SOURCE_OWNER_INTERNAL
        return self.SOURCE_OWNER_UNKNOWN

    def _default_collection_method(self):
        if self.source_type == self.SOURCE_TYPE_YUNCE:
            return self.COLLECTION_METHOD_API_SYNC
        if self.source_category == self.SOURCE_CATEGORY_SUPPLIER:
            return self.COLLECTION_METHOD_UNKNOWN
        if self.source_category == self.SOURCE_CATEGORY_MANUAL:
            return self.COLLECTION_METHOD_MANUAL_ENTRY
        return self.COLLECTION_METHOD_UNKNOWN


class LLMOpsGlobalConfig(models.Model):
    """Singleton runtime configuration for LLM operations."""

    DEFAULT_META_MODEL_SYNC_CRON = "35 2 * * *"
    DEFAULT_PRICE_COLLECTION_CRON = "15 1,7,13,19 * * *"
    DEFAULT_META_MODEL_SOURCE_URL = "https://models.dev/models.json"
    ENCRYPTED_SECRET_PREFIX = "fernet:"

    singleton_key = models.CharField(
        max_length=50,
        unique=True,
        default="default",
        editable=False,
    )
    meta_model_sync_enabled = models.BooleanField(default=True)
    meta_model_sync_source_url = models.URLField(
        max_length=1000,
        default=DEFAULT_META_MODEL_SOURCE_URL,
    )
    meta_model_sync_cron = models.CharField(
        max_length=100,
        default=DEFAULT_META_MODEL_SYNC_CRON,
    )
    price_collection_enabled = models.BooleanField(default=True)
    price_collection_source_ids = models.JSONField(blank=True, default=list)
    price_collection_cron = models.CharField(
        max_length=100,
        default=DEFAULT_PRICE_COLLECTION_CRON,
    )
    price_sync_llm_config_uuid = models.UUIDField(
        blank=True,
        null=True,
        db_index=True,
    )
    feishu_approval_enabled = models.BooleanField(default=False)
    feishu_app_id = models.CharField(max_length=255, blank=True, default="")
    feishu_app_secret = models.TextField(blank=True, default="")
    feishu_approval_code = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    feishu_tenant_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    notes = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="llm_ops_global_config_updates",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM Ops Global Config"
        verbose_name_plural = "LLM Ops Global Config"

    def __str__(self) -> str:
        return "LLM Ops global config"

    @classmethod
    def encrypt_secret(cls, value: str) -> str:
        """Encrypt a secret unless it already uses the storage format."""
        if not value:
            return ""
        if value.startswith(cls.ENCRYPTED_SECRET_PREFIX):
            return value
        encrypted = encryption_service.encrypt(value)
        return f"{cls.ENCRYPTED_SECRET_PREFIX}{encrypted}"

    @classmethod
    def decrypt_secret(cls, value: str) -> str:
        """Decrypt a stored secret with plaintext fallback."""
        if not value:
            return ""
        if value.startswith(cls.ENCRYPTED_SECRET_PREFIX):
            encrypted = value[len(cls.ENCRYPTED_SECRET_PREFIX):]
            return encryption_service.decrypt(encrypted)
        return value

    def set_feishu_app_secret(self, value: str) -> None:
        """Store the Feishu app secret in encrypted form."""
        self.feishu_app_secret = self.encrypt_secret(value)

    def get_feishu_app_secret(self) -> str:
        """Return the decrypted Feishu app secret."""
        return self.decrypt_secret(self.feishu_app_secret)

    def save(self, *args, **kwargs):
        """Encrypt sensitive credentials before writing to the database."""
        if self.feishu_app_secret:
            self.feishu_app_secret = self.encrypt_secret(
                self.feishu_app_secret
            )
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Return the singleton config row."""
        instance, _created = cls.objects.get_or_create(
            singleton_key="default"
        )
        return instance


class LLMProvider(models.Model):
    """Price source provider, supplier, cloud host, or API platform."""

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=100, unique=True, db_index=True)
    website = models.URLField(max_length=1000, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class MetaModel(models.Model):
    """Canonical model identity shared by price sources and suppliers."""

    STATUS_ACTIVE = "active"
    STATUS_DEPRECATED = "deprecated"
    STATUS_UNKNOWN = "unknown"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_DEPRECATED, "Deprecated"),
        (STATUS_UNKNOWN, "Unknown"),
    )

    MODALITY_TEXT = "text"
    MODALITY_AUDIO = "audio"
    MODALITY_VIDEO = "video"
    MODALITY_MULTIMODAL = "multimodal"

    MODALITY_CHOICES = (
        (MODALITY_TEXT, "Text"),
        (MODALITY_AUDIO, "Audio"),
        (MODALITY_VIDEO, "Video"),
        (MODALITY_MULTIMODAL, "Multimodal"),
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=150, unique=True, db_index=True)
    family = models.CharField(max_length=120, blank=True, default="")
    owner_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )
    owner_name = models.CharField(max_length=255, blank=True, default="")
    owner_website = models.URLField(max_length=1000, blank=True, default="")
    modality = models.CharField(
        max_length=20,
        choices=MODALITY_CHOICES,
        default=MODALITY_TEXT,
    )
    aliases = models.JSONField(blank=True, default=list)
    capabilities = models.JSONField(blank=True, default=dict)
    context_window = models.PositiveIntegerField(default=0)
    max_output_tokens = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def save(self, *args, **kwargs):
        """Keep known model owners canonical before writing."""
        from .constants import resolve_meta_model_owner_fields

        owner = resolve_meta_model_owner_fields(self)
        changed_fields = []
        for field_name, value in owner.items():
            if getattr(self, field_name) != value:
                setattr(self, field_name, value)
                changed_fields.append(field_name)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and changed_fields:
            kwargs["update_fields"] = list(
                dict.fromkeys([*update_fields, *changed_fields])
            )
        super().save(*args, **kwargs)
        from .meta_model_lookup import register_meta_model_in_lookup_cache

        register_meta_model_in_lookup_cache(self)

    def delete(self, *args, **kwargs):
        """Clear lookup caches when a canonical model is removed."""
        result = super().delete(*args, **kwargs)
        from .meta_model_lookup import invalidate_meta_model_lookup_cache

        invalidate_meta_model_lookup_cache()
        return result

    def __str__(self) -> str:
        return self.name


class ModelSku(models.Model):
    """Provider-deployed SKU used for pricing and runtime routing."""

    VARIANT_OFFICIAL = "official"
    VARIANT_CLOUD_HOSTED = "cloud_hosted"
    VARIANT_ALIAS = "alias"
    VARIANT_RESELLER = "reseller"
    VARIANT_UNKNOWN = "unknown"

    VARIANT_CHOICES = (
        (VARIANT_OFFICIAL, "Official"),
        (VARIANT_CLOUD_HOSTED, "Cloud Hosted"),
        (VARIANT_ALIAS, "Alias"),
        (VARIANT_RESELLER, "Reseller"),
        (VARIANT_UNKNOWN, "Unknown"),
    )

    ROUTING_CANDIDATE = "candidate"
    ROUTING_CONFIRMED = "confirmed"
    ROUTING_LOCKED = "locked"

    ROUTING_STATUS_CHOICES = (
        (ROUTING_CANDIDATE, "Candidate"),
        (ROUTING_CONFIRMED, "Confirmed"),
        (ROUTING_LOCKED, "Locked"),
    )

    meta_model = models.ForeignKey(
        MetaModel,
        related_name="skus",
        on_delete=models.CASCADE,
    )
    provider = models.ForeignKey(
        LLMProvider,
        related_name="model_skus",
        on_delete=models.CASCADE,
    )
    canonical_sku_code = models.CharField(max_length=255, db_index=True)
    upstream_model_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    variant_type = models.CharField(
        max_length=50,
        choices=VARIANT_CHOICES,
        default=VARIANT_UNKNOWN,
    )
    region = models.CharField(max_length=80, blank=True, default="")
    mode = models.CharField(max_length=80, blank=True, default="")
    api_type = models.CharField(max_length=80, blank=True, default="")
    capabilities = models.JSONField(blank=True, default=dict)
    evidence = models.JSONField(blank=True, default=dict)
    routing_status = models.CharField(
        max_length=30,
        choices=ROUTING_STATUS_CHOICES,
        default=ROUTING_CANDIDATE,
        db_index=True,
    )
    is_routable = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider__name", "display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "canonical_sku_code",
                    "region",
                    "mode",
                    "api_type",
                ],
                name="uq_llm_ops_model_sku_identity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider.name} / {self.upstream_model_name}"


class SourceSkuOffering(models.Model):
    """A price source or channel offering for one model SKU."""

    METHOD_COLLECTED = "collected"
    METHOD_MANUAL = "manual"
    METHOD_DERIVED_DISCOUNT = "derived_discount"

    METHOD_CHOICES = (
        (METHOD_COLLECTED, "Collected"),
        (METHOD_MANUAL, "Manual"),
        (METHOD_DERIVED_DISCOUNT, "Derived Discount"),
    )

    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="sku_offerings",
        on_delete=models.CASCADE,
    )
    sku = models.ForeignKey(
        ModelSku,
        related_name="offerings",
        on_delete=models.CASCADE,
    )
    provider = models.ForeignKey(
        LLMProvider,
        related_name="sku_offerings",
        on_delete=models.CASCADE,
    )
    exposed_model_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )
    pricing_method = models.CharField(
        max_length=50,
        choices=METHOD_CHOICES,
        default=METHOD_COLLECTED,
    )
    upstream_offering = models.ForeignKey(
        "self",
        related_name="derived_offerings",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    discount_rules = models.JSONField(blank=True, default=dict)
    evidence = models.JSONField(blank=True, default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source__name", "sku__display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "sku", "exposed_model_name"],
                name="uq_llm_ops_source_sku_offering",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source.name} / {self.sku.upstream_model_name}"

    def clean(self):
        """Validate derived offering chains."""
        super().clean()
        if self.upstream_offering_id is None:
            return
        if self.pk and self.upstream_offering_id == self.pk:
            raise ValidationError(
                {
                    "upstream_offering": (
                        "Source SKU offering cannot reference itself."
                    )
                }
            )
        if self.pk and self.has_upstream_cycle():
            raise ValidationError(
                {
                    "upstream_offering": (
                        "Source SKU offering upstream chain has a cycle."
                    )
                }
            )

    def has_upstream_cycle(self) -> bool:
        """Return whether the upstream offering chain loops back here."""
        seen_ids = {self.pk}
        upstream = self.upstream_offering
        while upstream is not None:
            if upstream.pk in seen_ids:
                return True
            seen_ids.add(upstream.pk)
            upstream = upstream.upstream_offering
        return False

    def save(self, *args, **kwargs):
        """Validate offering chains before saving."""
        self.full_clean()
        super().save(*args, **kwargs)


class LLMModel(models.Model):
    """Provider-specific price record for one canonical model."""

    MODALITY_TEXT = MetaModel.MODALITY_TEXT
    MODALITY_AUDIO = MetaModel.MODALITY_AUDIO
    MODALITY_VIDEO = MetaModel.MODALITY_VIDEO
    MODALITY_MULTIMODAL = MetaModel.MODALITY_MULTIMODAL
    MODALITY_CHOICES = MetaModel.MODALITY_CHOICES

    PRICE_ROLE_OFFICIAL = "official"
    PRICE_ROLE_SUPPLIER = "supplier"
    PRICE_ROLE_CLOUD_HOSTED = "cloud_hosted"
    PRICE_ROLE_MARKET_REFERENCE = "market_reference"
    PRICE_ROLE_MANUAL = "manual"
    PRICE_ROLE_UNKNOWN = "unknown"

    PRICE_ROLE_CHOICES = (
        (PRICE_ROLE_OFFICIAL, "Official"),
        (PRICE_ROLE_SUPPLIER, "Supplier"),
        (PRICE_ROLE_CLOUD_HOSTED, "Cloud Hosted"),
        (PRICE_ROLE_MARKET_REFERENCE, "Market Reference"),
        (PRICE_ROLE_MANUAL, "Manual"),
        (PRICE_ROLE_UNKNOWN, "Unknown"),
    )

    meta_model = models.ForeignKey(
        MetaModel,
        related_name="provider_prices",
        on_delete=models.CASCADE,
    )
    sku = models.ForeignKey(
        ModelSku,
        related_name="legacy_models",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    provider = models.ForeignKey(
        LLMProvider,
        related_name="models",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=150, db_index=True)
    modality = models.CharField(
        max_length=20,
        choices=MODALITY_CHOICES,
        default=MODALITY_TEXT,
    )
    input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    output_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    cache_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    image_output_price_per_image = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    audio_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    audio_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_resolution_prices = models.JSONField(blank=True, default=dict)
    context_window = models.PositiveIntegerField(default=0)
    max_output_tokens = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, default="USD")
    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="models",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source_url = models.URLField(max_length=1000, blank=True, default="")
    price_role = models.CharField(
        max_length=50,
        choices=PRICE_ROLE_CHOICES,
        default=PRICE_ROLE_UNKNOWN,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    last_price_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["meta_model__name", "provider__name", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "source", "code"],
                name="uq_llm_ops_provider_model_code",
            )
        ]

    def save(self, *args, **kwargs):
        """Ensure direct model creation still links a canonical model."""
        if not self.meta_model_id:
            from .constants import (
                canonical_meta_model_identity,
                meta_model_owner_payload,
            )

            identity = canonical_meta_model_identity(self.code, self.name)
            code = identity["code"]
            name = identity["name"]
            owner = meta_model_owner_payload(code, self.provider)
            meta_model, _ = MetaModel.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    **owner,
                    "modality": self.modality,
                    "context_window": self.context_window,
                    "max_output_tokens": self.max_output_tokens,
                    "aliases": identity["aliases"],
                },
            )
            self.meta_model = meta_model
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.provider.name} / {self.name}"


class ModelPriceItem(models.Model):
    """Normalized official price item for one model and billing dimension."""

    DIMENSION_TEXT_INPUT = "text_input"
    DIMENSION_TEXT_OUTPUT = "text_output"
    DIMENSION_CACHE_INPUT = "cache_input"
    DIMENSION_IMAGE_INPUT = "image_input"
    DIMENSION_IMAGE_OUTPUT = "image_output"
    DIMENSION_AUDIO_INPUT = "audio_input"
    DIMENSION_AUDIO_OUTPUT = "audio_output"
    DIMENSION_VIDEO_INPUT = "video_input"
    DIMENSION_VIDEO_OUTPUT = "video_output"

    DIMENSION_CHOICES = (
        (DIMENSION_TEXT_INPUT, "Text Input"),
        (DIMENSION_TEXT_OUTPUT, "Text Output"),
        (DIMENSION_CACHE_INPUT, "Cache Input"),
        (DIMENSION_IMAGE_INPUT, "Image Input"),
        (DIMENSION_IMAGE_OUTPUT, "Image Output"),
        (DIMENSION_AUDIO_INPUT, "Audio Input"),
        (DIMENSION_AUDIO_OUTPUT, "Audio Output"),
        (DIMENSION_VIDEO_INPUT, "Video Input"),
        (DIMENSION_VIDEO_OUTPUT, "Video Output"),
    )

    UNIT_PER_1M_TOKENS = "per_1m_tokens"
    UNIT_PER_IMAGE = "per_image"
    UNIT_PER_SECOND = "per_second"
    UNIT_PER_GENERATION = "per_generation"

    BILLING_UNIT_CHOICES = (
        (UNIT_PER_1M_TOKENS, "Per 1M Tokens"),
        (UNIT_PER_IMAGE, "Per Image"),
        (UNIT_PER_SECOND, "Per Second"),
        (UNIT_PER_GENERATION, "Per Generation"),
    )

    TIER_FLAT = "flat"
    TIER_USAGE_RANGE = "usage_range"
    TIER_VOLUME = "volume"

    TIER_CHOICES = (
        (TIER_FLAT, "Flat"),
        (TIER_USAGE_RANGE, "Usage Range"),
        (TIER_VOLUME, "Volume"),
    )

    provider = models.ForeignKey(
        LLMProvider,
        related_name="price_items",
        on_delete=models.CASCADE,
    )
    sku = models.ForeignKey(
        ModelSku,
        related_name="price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    offering = models.ForeignKey(
        SourceSkuOffering,
        related_name="price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="price_items",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="price_items",
        on_delete=models.CASCADE,
    )
    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="model_price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    price_role = models.CharField(
        max_length=50,
        choices=LLMModel.PRICE_ROLE_CHOICES,
        default=LLMModel.PRICE_ROLE_UNKNOWN,
        db_index=True,
    )
    dimension = models.CharField(max_length=50, choices=DIMENSION_CHOICES)
    billing_unit = models.CharField(
        max_length=50,
        choices=BILLING_UNIT_CHOICES,
        default=UNIT_PER_1M_TOKENS,
    )
    currency = models.CharField(max_length=10, default="USD")
    unit_price = models.DecimalField(max_digits=14, decimal_places=6)
    tier_type = models.CharField(
        max_length=50,
        choices=TIER_CHOICES,
        default=TIER_FLAT,
    )
    tier_start = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
    )
    tier_end = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
    )
    spec = models.JSONField(blank=True, default=dict)
    source_url = models.URLField(max_length=1000, blank=True, default="")
    raw_payload = models.JSONField(blank=True, default=dict)
    price_fingerprint = models.CharField(max_length=64, db_index=True)
    derived_from_price_item = models.ForeignKey(
        "self",
        related_name="derived_price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    base_price_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    is_current = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateTimeField(auto_now_add=True)
    effective_to = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "provider__name",
            "sku__display_name",
            "dimension",
            "tier_start",
            "id",
        ]
        indexes = [
            models.Index(fields=["meta_model", "dimension", "is_current"]),
            models.Index(fields=["sku", "dimension", "is_current"]),
            models.Index(fields=["offering", "dimension", "is_current"]),
            models.Index(fields=["provider", "is_current"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "offering",
                    "dimension",
                    "billing_unit",
                    "currency",
                    "price_fingerprint",
                ],
                name="uq_llm_ops_offering_price_item_fingerprint",
            )
        ]

    def __str__(self) -> str:
        if self.sku_id:
            return f"{self.sku.display_name} / {self.dimension}"
        if self.model_id:
            return f"{self.model.name} / {self.dimension}"
        return self.dimension

    def save(self, *args, **kwargs):
        """Ensure direct legacy price item creation links a meta model."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class PriceCollectionRun(models.Model):
    """One execution of an external pricing collection job."""

    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="collection_runs",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    collected_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        source_name = self.source.name if self.source_id else "Deleted source"
        return f"{source_name} / {self.started_at:%Y-%m-%d %H:%M:%S}"


class CollectedModelPriceSnapshot(models.Model):
    """Latest normalized pricing payload collected for one source model."""

    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="model_price_snapshots",
        on_delete=models.CASCADE,
    )
    run = models.ForeignKey(
        PriceCollectionRun,
        related_name="model_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    provider = models.ForeignKey(
        LLMProvider,
        related_name="collected_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="collected_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    sku = models.ForeignKey(
        ModelSku,
        related_name="collected_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    offering = models.ForeignKey(
        SourceSkuOffering,
        related_name="collected_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="collected_price_snapshots",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source_platform_id = models.CharField(max_length=100, db_index=True)
    source_model_id = models.CharField(max_length=255, db_index=True)
    source_model_name = models.CharField(max_length=255)
    source_model_type = models.CharField(max_length=50, db_index=True)
    source_provider_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    currency = models.CharField(max_length=10, blank=True, default="")
    billing_unit = models.CharField(max_length=50, blank=True, default="")
    billing_mode = models.CharField(max_length=50, blank=True, default="")
    normalized_price_rows = models.JSONField(blank=True, default=list)
    raw_price_info = models.JSONField(blank=True, default=dict)
    raw_detail = models.JSONField(blank=True, default=dict)
    price_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    collected_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "source_model_type",
            "source_provider_name",
            "source_model_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "offering", "source_platform_id"],
                name="uq_llm_ops_offering_platform_snapshot",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source.name} / {self.source_model_name}"


class CollectedModelPriceHistory(models.Model):
    """Historical collected pricing version for one source model."""

    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="model_price_history",
        on_delete=models.CASCADE,
    )
    run = models.ForeignKey(
        PriceCollectionRun,
        related_name="model_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    provider = models.ForeignKey(
        LLMProvider,
        related_name="collected_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="collected_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    sku = models.ForeignKey(
        ModelSku,
        related_name="collected_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    offering = models.ForeignKey(
        SourceSkuOffering,
        related_name="collected_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="collected_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source_platform_id = models.CharField(max_length=100, db_index=True)
    source_model_id = models.CharField(max_length=255, db_index=True)
    source_model_name = models.CharField(max_length=255)
    source_model_type = models.CharField(max_length=50, db_index=True)
    source_provider_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    currency = models.CharField(max_length=10, blank=True, default="")
    billing_unit = models.CharField(max_length=50, blank=True, default="")
    billing_mode = models.CharField(max_length=50, blank=True, default="")
    normalized_price_rows = models.JSONField(blank=True, default=list)
    raw_price_info = models.JSONField(blank=True, default=dict)
    raw_detail = models.JSONField(blank=True, default=dict)
    price_fingerprint = models.CharField(max_length=64, db_index=True)
    changed_fields = models.JSONField(blank=True, default=list)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(blank=True, null=True)
    is_current = models.BooleanField(default=True, db_index=True)
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source",
                    "offering",
                    "source_platform_id",
                    "price_fingerprint",
                ],
                name="uq_llm_ops_offering_history_fingerprint",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source.name} / {self.source_model_name}"


class AuditLog(models.Model):
    """Append-only audit trail for LLM operations business changes."""

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_COLLECT = "collect"
    ACTION_IMPORT = "import"
    ACTION_BULK_UPSERT = "bulk_upsert"
    ACTION_BULK_DRAFT = "bulk_draft"
    ACTION_BULK_REPLACE = "bulk_replace"
    ACTION_TRANSITION = "transition"
    ACTION_OFFLINE = "offline"
    ACTION_RESTORE = "restore"
    ACTION_SYNC = "sync"

    ACTION_CHOICES = (
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_COLLECT, "Collect"),
        (ACTION_IMPORT, "Import"),
        (ACTION_BULK_UPSERT, "Bulk Upsert"),
        (ACTION_BULK_DRAFT, "Bulk Draft"),
        (ACTION_BULK_REPLACE, "Bulk Replace"),
        (ACTION_TRANSITION, "Transition"),
        (ACTION_OFFLINE, "Offline"),
        (ACTION_RESTORE, "Restore"),
        (ACTION_SYNC, "Sync"),
    )

    CATEGORY_CONFIGURATION = "configuration"
    CATEGORY_PRICING = "pricing"
    CATEGORY_PUBLISHING = "publishing"
    CATEGORY_APPROVAL = "approval"
    CATEGORY_COLLECTION = "collection"
    CATEGORY_RECONCILIATION = "reconciliation"

    CATEGORY_CHOICES = (
        (CATEGORY_CONFIGURATION, "Configuration"),
        (CATEGORY_PRICING, "Pricing"),
        (CATEGORY_PUBLISHING, "Publishing"),
        (CATEGORY_APPROVAL, "Approval"),
        (CATEGORY_COLLECTION, "Collection"),
        (CATEGORY_RECONCILIATION, "Reconciliation"),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="llm_ops_audit_logs",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    actor_identifier = models.CharField(max_length=255, blank=True, default="")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    target_type = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=100, blank=True, default="")
    target_repr = models.CharField(max_length=255, blank=True, default="")
    summary = models.CharField(max_length=500, blank=True, default="")
    before = models.JSONField(blank=True, default=dict)
    after = models.JSONField(blank=True, default=dict)
    changes = models.JSONField(blank=True, default=dict)
    metadata = models.JSONField(blank=True, default=dict)
    request_id = models.CharField(max_length=100, blank=True, default="")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["category", "action", "created_at"]),
            models.Index(fields=["target_type", "target_id", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        actor = self.actor_identifier or "system"
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {actor} {self.action}"


class ProcurementChannel(models.Model):
    """Upstream forwarding or reseller channel used for procurement."""

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=100, unique=True, db_index=True)
    api_endpoint = models.URLField(max_length=1000, blank=True, default="")
    currency = models.CharField(max_length=10, default="USD")
    settlement_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=1,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class ChannelModelPrice(models.Model):
    """Per-channel listing and price overrides for one model."""

    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="model_prices",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="channel_prices",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="channel_offerings",
        on_delete=models.CASCADE,
    )
    price_source = models.ForeignKey(
        PriceCollectionSource,
        related_name="channel_model_prices",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    is_listed = models.BooleanField(default=True)
    currency = models.CharField(max_length=10, blank=True, default="")
    settlement_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        blank=True,
        null=True,
    )
    custom_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_output_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_audio_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_audio_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_video_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_video_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    custom_video_resolution_prices = models.JSONField(blank=True, default=dict)
    tpm_limit = models.PositiveIntegerField(blank=True, null=True)
    rpm_limit = models.PositiveIntegerField(blank=True, null=True)
    latency_ms = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["channel__name", "model__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "model"],
                name="uq_llm_ops_channel_model_price",
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure channel model prices stay linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ChannelPriceItem(models.Model):
    """Normalized procurement price item for one channel."""

    SOURCE_MANUAL = "manual"
    SOURCE_COLLECTED = "collected"
    SOURCE_DERIVED_DISCOUNT = "derived_discount"

    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_COLLECTED, "Collected"),
        (SOURCE_DERIVED_DISCOUNT, "Derived Discount"),
    )

    COMPARISON_BELOW = "below_official"
    COMPARISON_SAME = "same_as_official"
    COMPARISON_ABOVE = "above_official"
    COMPARISON_UNKNOWN = "unknown"

    COMPARISON_CHOICES = (
        (COMPARISON_BELOW, "Below Official"),
        (COMPARISON_SAME, "Same As Official"),
        (COMPARISON_ABOVE, "Above Official"),
        (COMPARISON_UNKNOWN, "Unknown"),
    )

    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="price_items",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="channel_price_items",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="channel_price_items",
        on_delete=models.CASCADE,
    )
    base_price_item = models.ForeignKey(
        ModelPriceItem,
        related_name="channel_price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source = models.ForeignKey(
        PriceCollectionSource,
        related_name="channel_price_items",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    dimension = models.CharField(
        max_length=50,
        choices=ModelPriceItem.DIMENSION_CHOICES,
    )
    billing_unit = models.CharField(
        max_length=50,
        choices=ModelPriceItem.BILLING_UNIT_CHOICES,
    )
    currency = models.CharField(max_length=10, default="USD")
    unit_price = models.DecimalField(max_digits=14, decimal_places=6)
    tier_type = models.CharField(
        max_length=50,
        choices=ModelPriceItem.TIER_CHOICES,
        default=ModelPriceItem.TIER_FLAT,
    )
    tier_start = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
    )
    tier_end = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
    )
    spec = models.JSONField(blank=True, default=dict)
    price_source_type = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
    )
    settlement_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        blank=True,
        null=True,
    )
    comparison_status = models.CharField(
        max_length=50,
        choices=COMPARISON_CHOICES,
        default=COMPARISON_UNKNOWN,
    )
    delta_amount = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    delta_percent = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
    )
    raw_payload = models.JSONField(blank=True, default=dict)
    price_fingerprint = models.CharField(max_length=64, db_index=True)
    is_current = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateTimeField(auto_now_add=True)
    effective_to = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "channel__name",
            "model__name",
            "dimension",
            "tier_start",
            "id",
        ]
        indexes = [
            models.Index(fields=["channel", "meta_model", "is_current"]),
            models.Index(fields=["meta_model", "dimension", "is_current"]),
            models.Index(fields=["channel", "model", "is_current"]),
            models.Index(fields=["model", "dimension", "is_current"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "channel",
                    "model",
                    "dimension",
                    "billing_unit",
                    "currency",
                    "price_fingerprint",
                ],
                name="uq_llm_ops_channel_price_item_fingerprint",
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel.name} / {self.model.name} / {self.dimension}"

    def save(self, *args, **kwargs):
        """Ensure channel price items stay linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ChannelModelPriceHistory(models.Model):
    """Historical procurement price version for one channel/model pair."""

    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="model_price_history",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="channel_price_history",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="channel_price_history",
        on_delete=models.CASCADE,
    )
    price_source = models.ForeignKey(
        PriceCollectionSource,
        related_name="channel_model_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    is_listed = models.BooleanField(default=True)
    settlement_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        blank=True,
        null=True,
    )
    input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    output_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    image_output_price_per_image = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    audio_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    audio_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    video_resolution_prices = models.JSONField(blank=True, default=dict)
    currency = models.CharField(max_length=10, default="USD")
    price_fingerprint = models.CharField(max_length=64, db_index=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(blank=True, null=True)
    is_current = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "model", "price_fingerprint"],
                name="uq_llm_ops_channel_price_history_fingerprint",
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure channel price history stays linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ResalePlatform(models.Model):
    """Downstream resale platform such as Agione."""

    PLATFORM_TYPE_AGIONE = "agione"
    PLATFORM_TYPE_CLOUD_MARKETPLACE = "cloud_marketplace"
    PLATFORM_TYPE_API_GATEWAY = "api_gateway"
    PLATFORM_TYPE_RESELLER = "reseller"
    PLATFORM_TYPE_INTERNAL = "internal"
    PLATFORM_TYPE_OTHER = "other"

    ENV_PRODUCTION = "production"
    ENV_STAGING = "staging"
    ENV_SANDBOX = "sandbox"
    ENV_TEST = "test"

    ROUND_HALF_UP = "half_up"
    ROUND_UP = "up"
    ROUND_DOWN = "down"

    PLATFORM_TYPE_CHOICES = (
        (PLATFORM_TYPE_AGIONE, "Agione"),
        (PLATFORM_TYPE_CLOUD_MARKETPLACE, "Cloud Marketplace"),
        (PLATFORM_TYPE_API_GATEWAY, "API Gateway"),
        (PLATFORM_TYPE_RESELLER, "Reseller"),
        (PLATFORM_TYPE_INTERNAL, "Internal"),
        (PLATFORM_TYPE_OTHER, "Other"),
    )

    ENVIRONMENT_CHOICES = (
        (ENV_PRODUCTION, "Production"),
        (ENV_STAGING, "Staging"),
        (ENV_SANDBOX, "Sandbox"),
        (ENV_TEST, "Test"),
    )

    ROUNDING_CHOICES = (
        (ROUND_HALF_UP, "Half Up"),
        (ROUND_UP, "Up"),
        (ROUND_DOWN, "Down"),
    )

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=100, unique=True, db_index=True)
    platform_type = models.CharField(
        max_length=50,
        choices=PLATFORM_TYPE_CHOICES,
        default=PLATFORM_TYPE_AGIONE,
        db_index=True,
    )
    region_code = models.CharField(max_length=80, blank=True, default="")
    region_name = models.CharField(max_length=120, blank=True, default="")
    environment = models.CharField(
        max_length=30,
        choices=ENVIRONMENT_CHOICES,
        default=ENV_PRODUCTION,
    )
    website = models.URLField(max_length=1000, blank=True, default="")
    api_endpoint = models.URLField(max_length=1000, blank=True, default="")
    api_key = models.CharField(max_length=512, blank=True, default="")
    currency = models.CharField(max_length=10, default="USD")
    point_name = models.CharField(max_length=50, default="积分")
    points_per_currency_unit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=100,
    )
    point_rounding_mode = models.CharField(
        max_length=20,
        choices=ROUNDING_CHOICES,
        default=ROUND_HALF_UP,
    )
    point_decimal_places = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(6)],
    )
    fee_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    service_fee_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
    )
    auto_approve_max_margin_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=100,
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(blank=True, default=dict)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class ResaleListing(models.Model):
    """Downstream listing price for a model routed through a channel."""

    PUBLISH_NONE = "none"
    PUBLISH_ONLINE = "online"
    PUBLISH_OFFLINE = "offline"
    PUBLISH_DELETED = "deleted"

    PUBLISH_STATUS_CHOICES = (
        (PUBLISH_NONE, "Not Published"),
        (PUBLISH_ONLINE, "Published"),
        (PUBLISH_OFFLINE, "Offline"),
        (PUBLISH_DELETED, "Deleted"),
    )

    WORKFLOW_DRAFT = "draft"
    WORKFLOW_PENDING_PUBLISH = "pending_publish"
    WORKFLOW_ONLINE = "online"
    WORKFLOW_UPDATE_DRAFT = "update_draft"
    WORKFLOW_PENDING_UPDATE = "pending_update"
    WORKFLOW_PENDING_OFFLINE = "pending_offline"
    WORKFLOW_OFFLINE_EXCEPTION = "offline_exception"
    WORKFLOW_OFFLINE = "offline"
    WORKFLOW_DELETED = "deleted"

    WORKFLOW_STATUS_CHOICES = (
        (WORKFLOW_DRAFT, "Draft"),
        (WORKFLOW_PENDING_PUBLISH, "Pending Publish"),
        (WORKFLOW_ONLINE, "Online"),
        (WORKFLOW_UPDATE_DRAFT, "Update Draft"),
        (WORKFLOW_PENDING_UPDATE, "Pending Update"),
        (WORKFLOW_PENDING_OFFLINE, "Pending Offline"),
        (WORKFLOW_OFFLINE_EXCEPTION, "Offline Exception"),
        (WORKFLOW_OFFLINE, "Offline"),
        (WORKFLOW_DELETED, "Deleted"),
    )

    platform = models.ForeignKey(
        ResalePlatform,
        related_name="listings",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="resale_listings",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="resale_listings",
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="resale_listings",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    display_name = models.CharField(max_length=255, blank=True, default="")
    currency = models.CharField(max_length=10, blank=True, default="")
    retail_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    retail_output_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    retail_cache_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_image_output_price_per_image = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_audio_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_audio_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_video_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_video_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    publish_status = models.CharField(
        max_length=30,
        choices=PUBLISH_STATUS_CHOICES,
        default=PUBLISH_NONE,
        db_index=True,
    )
    workflow_status = models.CharField(
        max_length=30,
        choices=WORKFLOW_STATUS_CHOICES,
        default=WORKFLOW_DRAFT,
        db_index=True,
    )
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "platform__name",
            "model__name",
            "channel__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "model", "channel"],
                condition=models.Q(channel__isnull=False),
                name="uq_llm_ops_platform_model_channel_listing",
            ),
            models.UniqueConstraint(
                fields=["platform", "model"],
                condition=models.Q(channel__isnull=True),
                name="uq_llm_ops_platform_model_auto_listing",
            )
        ]

    def __str__(self) -> str:
        return f"{self.platform.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure resale listings stay linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ResaleListingExclusion(models.Model):
    """Model removed from a resale platform workbench list."""

    platform = models.ForeignKey(
        ResalePlatform,
        related_name="listing_exclusions",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="resale_listing_exclusions",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="resale_listing_exclusions",
        on_delete=models.CASCADE,
    )
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["platform__name", "model__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "model"],
                name="uq_llm_ops_resale_listing_exclusion",
            )
        ]

    def __str__(self) -> str:
        return f"{self.platform.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure listing exclusions stay linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ResaleListingPriceHistory(models.Model):
    """Historical downstream listing price version for one platform listing."""

    platform = models.ForeignKey(
        ResalePlatform,
        related_name="listing_price_history",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="resale_listing_price_history",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="resale_listing_price_history",
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="resale_listing_price_history",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    display_name = models.CharField(max_length=255, blank=True, default="")
    retail_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    retail_output_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )
    retail_cache_input_price_per_million = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_image_output_price_per_image = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_audio_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_audio_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_video_input_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    retail_video_output_price_per_second = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        blank=True,
        null=True,
    )
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    price_fingerprint = models.CharField(max_length=64, db_index=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(blank=True, null=True)
    is_current = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "platform",
                    "model",
                    "channel",
                    "price_fingerprint",
                ],
                condition=models.Q(channel__isnull=False),
                name="uq_llm_ops_listing_history_fingerprint",
            ),
            models.UniqueConstraint(
                fields=["platform", "model", "price_fingerprint"],
                condition=models.Q(channel__isnull=True),
                name="uq_llm_ops_auto_listing_history_fingerprint",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.platform.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure listing price history stays linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)


class ResaleWorkflowConfig(models.Model):
    """Visual workflow configuration for a resale platform."""

    platform = models.OneToOneField(
        ResalePlatform,
        related_name="workflow_config",
        on_delete=models.CASCADE,
    )
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["platform__name", "id"]

    def __str__(self) -> str:
        return f"{self.platform.name} workflow"


class UsageReconciliationRecord(models.Model):
    """Manual reconciliation record for production usage and billing."""

    STATUS_PERFECT = "perfect"
    STATUS_OVERCHARGED = "overcharged"
    STATUS_UNDERCHARGED = "undercharged"

    STATUS_CHOICES = (
        (STATUS_PERFECT, "Perfect"),
        (STATUS_OVERCHARGED, "Overcharged"),
        (STATUS_UNDERCHARGED, "Undercharged"),
    )

    date = models.DateField(db_index=True)
    channel = models.ForeignKey(
        ProcurementChannel,
        related_name="reconciliation_records",
        on_delete=models.CASCADE,
    )
    model = models.ForeignKey(
        LLMModel,
        related_name="reconciliation_records",
        on_delete=models.CASCADE,
    )
    meta_model = models.ForeignKey(
        MetaModel,
        related_name="reconciliation_records",
        on_delete=models.CASCADE,
    )
    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    audio_input_seconds = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
    )
    audio_output_seconds = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
    )
    video_input_seconds = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
    )
    video_output_seconds = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
    )
    video_resolution = models.CharField(max_length=50, blank=True, default="")
    charged_amount = models.DecimalField(max_digits=14, decimal_places=6)
    expected_amount = models.DecimalField(max_digits=14, decimal_places=6)
    discrepancy = models.DecimalField(max_digits=14, decimal_places=6)
    discrepancy_percent = models.DecimalField(max_digits=10, decimal_places=4)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PERFECT,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return f"{self.date} / {self.channel.name} / {self.model.name}"

    def save(self, *args, **kwargs):
        """Ensure reconciliation rows stay linked to canonical models."""
        _ensure_meta_model_from_model(self, kwargs)
        super().save(*args, **kwargs)
