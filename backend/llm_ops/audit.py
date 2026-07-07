from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from ipaddress import ip_address
from typing import Any

from django.db import models

from .models import AuditLog


AUDIT_FIELD_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "llm_ops.PriceCollectionSource": (
        "name",
        "slug",
        "provider_id",
        "channel_id",
        "source_type",
        "source_category",
        "source_owner_type",
        "collection_method",
        "endpoint_url",
        "currency",
        "is_enabled",
        "updates_model_prices",
        "notes",
    ),
    "llm_ops.LLMOpsGlobalConfig": (
        "meta_model_sync_enabled",
        "meta_model_sync_source_url",
        "meta_model_sync_cron",
        "price_collection_enabled",
        "price_collection_source_ids",
        "price_collection_cron",
        "feishu_approval_enabled",
        "feishu_app_id",
        "feishu_approval_code",
        "feishu_tenant_key",
        "notes",
    ),
    "llm_ops.LLMProvider": (
        "name",
        "code",
        "website",
        "notes",
        "is_active",
    ),
    "llm_ops.MetaModel": (
        "name",
        "code",
        "family",
        "owner_code",
        "owner_name",
        "owner_website",
        "modality",
        "aliases",
        "capabilities",
        "context_window",
        "max_output_tokens",
        "status",
        "metadata",
    ),
    "llm_ops.LLMModel": (
        "meta_model_id",
        "provider_id",
        "source_id",
        "name",
        "code",
        "modality",
        "currency",
        "price_role",
        "is_active",
    ),
    "llm_ops.ModelPriceItem": (
        "provider_id",
        "model_id",
        "meta_model_id",
        "source_id",
        "price_role",
        "dimension",
        "billing_unit",
        "currency",
        "unit_price",
        "tier_type",
        "tier_start",
        "tier_end",
        "spec",
        "source_url",
        "price_fingerprint",
        "is_current",
    ),
    "llm_ops.ProcurementChannel": (
        "name",
        "code",
        "api_endpoint",
        "currency",
        "settlement_ratio",
        "is_active",
        "notes",
    ),
    "llm_ops.ChannelModelPrice": (
        "channel_id",
        "model_id",
        "meta_model_id",
        "price_source_id",
        "is_listed",
        "currency",
        "settlement_ratio",
        "custom_input_price_per_million",
        "custom_output_price_per_million",
        "custom_audio_input_price_per_second",
        "custom_audio_output_price_per_second",
        "custom_video_input_price_per_second",
        "custom_video_output_price_per_second",
        "custom_video_resolution_prices",
        "tpm_limit",
        "rpm_limit",
        "latency_ms",
        "notes",
    ),
    "llm_ops.ChannelPriceItem": (
        "channel_id",
        "model_id",
        "meta_model_id",
        "base_price_item_id",
        "source_id",
        "dimension",
        "billing_unit",
        "currency",
        "unit_price",
        "tier_type",
        "tier_start",
        "tier_end",
        "spec",
        "price_source_type",
        "settlement_ratio",
        "comparison_status",
        "delta_amount",
        "delta_percent",
        "price_fingerprint",
        "is_current",
    ),
    "llm_ops.ResalePlatform": (
        "name",
        "code",
        "website",
        "api_endpoint",
        "currency",
        "point_name",
        "points_per_currency_unit",
        "point_rounding_mode",
        "point_decimal_places",
        "fee_rate",
        "service_fee_rate",
        "auto_approve_max_margin_rate",
        "is_active",
        "notes",
    ),
    "llm_ops.ResaleListing": (
        "platform_id",
        "model_id",
        "meta_model_id",
        "channel_id",
        "currency",
        "retail_input_price_per_million",
        "retail_output_price_per_million",
        "retail_cache_input_price_per_million",
        "retail_image_output_price_per_image",
        "retail_audio_input_price_per_second",
        "retail_audio_output_price_per_second",
        "retail_video_input_price_per_second",
        "retail_video_output_price_per_second",
        "retail_video_resolution_prices",
        "publish_status",
        "workflow_status",
        "is_active",
        "notes",
    ),
    "llm_ops.ResaleListingExclusion": (
        "platform_id",
        "model_id",
        "meta_model_id",
        "reason",
    ),
    "llm_ops.UsageReconciliationRecord": (
        "channel_id",
        "model_id",
        "date",
        "input_tokens",
        "output_tokens",
        "currency",
        "cost_amount",
        "reported_amount",
        "difference_amount",
        "status",
        "notes",
    ),
}


def audit_target_type(instance: models.Model) -> str:
    """Return the stable audit target type for a model instance."""
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


def snapshot_instance(instance: models.Model | None) -> dict[str, Any]:
    """Return a safe JSON snapshot for supported model fields."""
    if instance is None:
        return {}

    target_type = audit_target_type(instance)
    field_names = AUDIT_FIELD_ALLOWLIST.get(target_type, ())
    payload: dict[str, Any] = {}
    for field_name in field_names:
        try:
            value = getattr(instance, field_name)
        except AttributeError:
            continue
        payload[field_name] = serialize_value(value)
    return payload


def diff_snapshots(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return field-level changes between two audit snapshots."""
    left = before or {}
    right = after or {}
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(left) | set(right)):
        if left.get(key) == right.get(key):
            continue
        changes[key] = {
            "before": left.get(key),
            "after": right.get(key),
        }
    return changes


def record_audit_log(
    *,
    request,
    action: str,
    category: str,
    target,
    summary: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    changes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one audit log row for a committed business operation."""
    actor = getattr(request, "user", None)
    if not getattr(actor, "is_authenticated", False):
        actor = None

    target_type = target
    target_id = ""
    target_repr = ""
    if isinstance(target, models.Model):
        target_type = audit_target_type(target)
        target_id = str(target.pk or "")
        target_repr = str(target)[:255]

    before_payload = before or {}
    after_payload = after or {}
    return AuditLog.objects.create(
        actor=actor,
        actor_identifier=actor_identifier(actor),
        action=action,
        category=category,
        target_type=str(target_type),
        target_id=target_id,
        target_repr=target_repr,
        summary=summary[:500],
        before=before_payload,
        after=after_payload,
        changes=changes
        if changes is not None
        else diff_snapshots(before_payload, after_payload),
        metadata=serialize_value(metadata or {}),
        request_id=request_id(request),
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )


def actor_identifier(actor) -> str:
    """Return a stable textual actor identifier."""
    if actor is None:
        return "anonymous"
    username = getattr(actor, "get_username", lambda: "")() or ""
    email = getattr(actor, "email", "") or ""
    if username and email:
        return f"{username} <{email}>"
    return username or email or str(getattr(actor, "pk", ""))


def request_id(request) -> str:
    """Return a request id propagated by middleware or upstream proxies."""
    if request is None:
        return ""
    meta = getattr(request, "META", {})
    return (
        meta.get("HTTP_X_REQUEST_ID")
        or meta.get("HTTP_X_CORRELATION_ID")
        or ""
    )[:100]


def client_ip(request) -> str | None:
    """Return the best-effort client IP address."""
    if request is None:
        return None
    meta = getattr(request, "META", {})
    forwarded_for = meta.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return normalize_ip_address(forwarded_for.split(",")[0].strip())
    return normalize_ip_address(meta.get("REMOTE_ADDR"))


def normalize_ip_address(value) -> str | None:
    """Return a valid IP address string or None."""
    if not value:
        return None
    try:
        return str(ip_address(str(value).strip()))
    except ValueError:
        return None


def user_agent(request) -> str:
    """Return the user agent with a bounded size."""
    if request is None:
        return ""
    return (getattr(request, "META", {}).get("HTTP_USER_AGENT", "") or "")[:500]


def serialize_value(value):
    """Convert model values to JSON-safe primitives."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value
