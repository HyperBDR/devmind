"""Closed operation contracts for the read-only snapshot BFF."""

from rest_framework import serializers

from agione_ops.serializers import StrictSerializer, SyncWindowSerializer

DIMENSIONS = (
    "date",
    "customerTenantId",
    "modelId",
    "userId",
    "status",
    "failureType",
)
METRICS = (
    "requestCount",
    "successCount",
    "failureCount",
    "successRate",
    "inputTokens",
    "outputTokens",
    "totalTokens",
    "p95LatencyMs",
    "distinctCustomers",
    "distinctUsers",
    "distinctModels",
)


class StrictString(serializers.CharField):
    """Do not coerce numeric identifiers or other JSON types to strings."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictInteger(serializers.IntegerField):
    """Pagination is a JSON integer, never a boolean or numeric string."""

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


def ids(max_length=500, required=False):
    return serializers.ListField(
        child=StrictString(max_length=200),
        max_length=max_length,
        required=required,
    )


class FiltersSerializer(StrictSerializer):
    model_ids = ids()
    statuses = serializers.ListField(
        child=serializers.ChoiceField(
            choices=("SUCCESS", "FAILURE", "UNKNOWN")
        ),
        max_length=3,
        required=False,
    )
    failure_types = ids(100)


class PageSerializer(StrictSerializer):
    page = StrictInteger(min_value=1, max_value=1000000, default=1)
    page_size = StrictInteger(min_value=1, max_value=200, default=50)


class AnalysisSerializer(PageSerializer):
    group_by = serializers.ListField(
        child=serializers.ChoiceField(choices=DIMENSIONS),
        min_length=1,
        max_length=2,
    )
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=METRICS),
        min_length=1,
        max_length=len(METRICS),
        default=["requestCount"],
    )
    user_ids = ids()

    def validate_group_by(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate dimensions.")
        return value


class TrendSerializer(StrictSerializer):
    series_by = serializers.ChoiceField(
        choices=DIMENSIONS,
        allow_null=True,
        required=False,
    )
    granularity = serializers.ChoiceField(
        choices=("hour", "day"),
        default="day",
    )
    user_ids = ids()


class SchemaSerializer(PageSerializer):
    option_dimension = serializers.ChoiceField(
        choices=DIMENSIONS,
        required=False,
    )
    search = StrictString(max_length=100, allow_blank=True, default="")


class CustomersSerializer(PageSerializer):
    search = StrictString(max_length=100, allow_blank=True, default="")
    signal = serializers.ChoiceField(
        choices=(
            "blocked",
            "decline",
            "inactive",
            "technical",
            "growth",
            "trial",
            "stable",
        ),
        allow_null=True,
        required=False,
    )


class ProfileSerializer(StrictSerializer):
    customer_id = StrictString(max_length=40)

    def validate_customer_id(self, value):
        if not value.isascii() or not value.isdecimal():
            raise serializers.ValidationError("Numeric customer ID required.")
        return value


class EvidenceSerializer(StrictSerializer):
    evidence_id = StrictString(max_length=40)

    def validate_evidence_id(self, value):
        if not value.isascii() or not value.isdecimal():
            raise serializers.ValidationError("Numeric evidence ID required.")
        return value


class RequestsSerializer(PageSerializer):
    group_key = serializers.DictField(
        child=StrictString(max_length=200),
        required=False,
    )
    user_ids = ids()

    def validate_group_key(self, value):
        aliases = {
            "customer_tenant_id": "customerTenantId",
            "model_id": "modelId",
            "user_id": "userId",
            "failure_type": "failureType",
        }
        value = {aliases.get(k, k): v for k, v in value.items()}
        if len(value) > 2 or set(value) - set(DIMENSIONS):
            raise serializers.ValidationError("Unsupported dimension.")
        if "status" in value and value["status"] not in (
            "SUCCESS",
            "FAILURE",
            "UNKNOWN",
        ):
            raise serializers.ValidationError("Invalid status.")
        return value


PAYLOADS = {
    "dashboard": StrictSerializer,
    "schema": SchemaSerializer,
    "analysis": AnalysisSerializer,
    "trend": TrendSerializer,
    "customers": CustomersSerializer,
    "profile": ProfileSerializer,
    "requests": RequestsSerializer,
    "evidence": EvidenceSerializer,
    "finance": StrictSerializer,
}


class SnapshotOperationSerializer(StrictSerializer):
    """Only typed operations, never paths, credentials or source selectors."""

    operation = serializers.ChoiceField(choices=tuple(PAYLOADS))
    data_version = serializers.UUIDField()
    window = SyncWindowSerializer(required=False)
    customer_ids = serializers.ListField(
        child=StrictString(max_length=40),
        min_length=1,
        max_length=500,
        required=False,
    )
    filters = FiltersSerializer(required=False)
    payload = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        payload = PAYLOADS[attrs["operation"]](data=attrs["payload"])
        payload.is_valid(raise_exception=True)
        attrs["payload"] = payload.validated_data
        customers = attrs.get("customer_ids", [])
        if any(not x.isascii() or not x.isdecimal() for x in customers):
            raise serializers.ValidationError("Numeric customer IDs required.")
        if len(set(customers)) != len(customers):
            raise serializers.ValidationError("Duplicate customer IDs.")
        return attrs

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if not isinstance(data.get("data_version"), str):
            raise serializers.ValidationError("dataVersion must be a UUID.")
        return result
