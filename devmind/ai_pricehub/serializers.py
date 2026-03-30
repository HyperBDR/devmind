from rest_framework import serializers


class PriceSourceConfigSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    vendor_slug = serializers.CharField(required=False, default="agione")
    platform_slug = serializers.CharField()
    vendor_name = serializers.CharField()
    region = serializers.CharField(allow_blank=True, required=False)
    endpoint_url = serializers.URLField()
    currency = serializers.CharField()
    points_per_currency_unit = serializers.FloatField()
    is_enabled = serializers.BooleanField(required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    updated_at = serializers.DateTimeField(read_only=True)


class VendorItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class ModelItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    vendor_id = serializers.IntegerField()
    vendor_slug = serializers.CharField(allow_blank=True, allow_null=True)
    vendor_name = serializers.CharField()
    platform_slug = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    platform_name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    platform_region = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    slug = serializers.CharField()
    name = serializers.CharField()
    family = serializers.CharField(allow_blank=True, allow_null=True)
    role = serializers.CharField()
    source_url = serializers.CharField(allow_blank=True, allow_null=True)
    input_price_per_million = serializers.FloatField(allow_null=True)
    output_price_per_million = serializers.FloatField(allow_null=True)
    currency = serializers.CharField()
    source_vendors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    is_aggregate = serializers.BooleanField(required=False)


class ComparisonItemSerializer(serializers.Serializer):
    model_id = serializers.IntegerField()
    vendor_id = serializers.IntegerField()
    vendor_slug = serializers.CharField(allow_blank=True, allow_null=True)
    vendor_name = serializers.CharField()
    platform_slug = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    platform_name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    platform_region = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    model_name = serializers.CharField()
    family = serializers.CharField(allow_blank=True, allow_null=True)
    role = serializers.CharField()
    input_price_per_million = serializers.FloatField(allow_null=True)
    output_price_per_million = serializers.FloatField(allow_null=True)
    currency = serializers.CharField(allow_blank=True, allow_null=True)
    input_advantage = serializers.FloatField(allow_null=True)
    output_advantage = serializers.FloatField(allow_null=True)
    input_advantage_ratio = serializers.FloatField(allow_null=True)
    output_advantage_ratio = serializers.FloatField(allow_null=True)
