"""Strict direct-query contracts without historical dataset identifiers."""

from djangorestframework_camel_case.util import camelize
from rest_framework import serializers

from agione_ops.serializers import StrictSerializer, SyncWindowSerializer


class LiveQuerySerializer(StrictSerializer):
    operation = serializers.ChoiceField(choices=[
        "dashboard", "schema", "analysis", "trend", "customers",
        "profile", "requests", "evidence", "finance",
    ])
    window = SyncWindowSerializer(required=False)
    customer_ids = serializers.ListField(
        child=serializers.RegexField(r"^[0-9]{1,40}$"),
        max_length=1000, allow_empty=False, required=False,
    )
    filters = serializers.JSONField(required=False, default=dict)
    payload = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        filters, payload = camelize(attrs["filters"]), camelize(attrs["payload"])
        attrs["filters"], attrs["payload"] = filters, payload
        if not isinstance(filters, dict) or not isinstance(payload, dict):
            raise serializers.ValidationError("Invalid query structure.")
        allowed_filters = {"modelIds", "statuses", "failureTypes"}
        if set(filters) - allowed_filters:
            raise serializers.ValidationError("Unsupported filter.")
        for name, values in filters.items():
            if (not isinstance(values, list) or len(values) > 200 or
                    any(not isinstance(x, str) or not 1 <= len(x) <= 160
                        for x in values)):
                raise serializers.ValidationError("Invalid filter values.")
            if name == "statuses" and set(values) - {
                "SUCCESS", "FAILURE", "UNKNOWN"
            }:
                raise serializers.ValidationError("Invalid result filter.")
        allowed_payloads = {
            "dashboard": set(),
            "schema": {"optionDimension", "search", "page", "pageSize"},
            "analysis": {"groupBy", "metrics", "page", "pageSize", "userIds"},
            "trend": {"seriesBy", "granularity", "userIds"},
            "customers": {"search", "signal", "page", "pageSize"},
            "profile": {"customerId"},
            "requests": {"groupKey", "page", "pageSize", "userIds"},
            "evidence": {"evidenceId"},
            "finance": {"customerId", "offset", "limit"},
        }
        if set(payload) - allowed_payloads[attrs["operation"]]:
            raise serializers.ValidationError("Unsupported operation payload.")
        for key, maximum in (("page", 10000), ("pageSize", 200),
                             ("offset", 100000), ("limit", 50)):
            if key in payload and (type(payload[key]) is not int or
                    not (0 if key == "offset" else 1) <= payload[key] <= maximum):
                raise serializers.ValidationError("Invalid pagination.")
        for key in ("customerId", "evidenceId"):
            if key in payload:
                import re
                if not isinstance(payload[key], str) or not re.fullmatch(
                    r"[0-9]{1,40}", payload[key]
                ):
                    raise serializers.ValidationError("Invalid identifier.")
        for key in ("search", "signal", "optionDimension", "granularity"):
            if key in payload and (not isinstance(payload[key], str) or
                                   len(payload[key]) > 100):
                raise serializers.ValidationError("Invalid option.")
        attrs["customerIds"] = attrs.pop("customer_ids", None)
        if attrs.get("window"):
            window = attrs["window"]
            attrs["window"] = {
                "start": window["start"].isoformat(),
                "endExclusive": window["end_exclusive"].isoformat(),
                "timezone": window.get("timezone", "Asia/Shanghai"),
            }
        return attrs
