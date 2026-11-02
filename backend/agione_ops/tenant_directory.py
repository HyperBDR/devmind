"""Read the authorized Operator tenant directory for classification."""

from django.conf import settings
from django.core.cache import cache

from agione_ops.client import AgioneOpsError
from agione_ops.models import TenantClassification, TenantClassificationChange
from agione_ops.native_account_scope import (
    EMAIL_PATTERN, internal_tenant_types,
)
from agione_ops.native_client import NativeClient
from agione_ops.native_analytics import tenant_display_name
from agione_ops.native_finance_refresh import _operator
from agione_ops.native_queries import LiveSource


def operator_overrides(operator):
    """Read overrides scoped to one authorized Operator."""
    return dict(TenantClassification.objects.filter(
        operator=operator,
    ).values_list("tenant_id", "classification"))


def overrides_for(connection, user):
    """Return manual classifications only for the authorized Operator."""
    operator = _operator(connection, user)
    if not operator:
        return {}
    return operator_overrides(operator)


def classification_version(connection, user):
    """Include the last change so reversing a choice still changes version."""
    from agione_ops.native_sync import digest

    operator = _operator(connection, user)
    if not operator:
        return digest([{}, None])
    changes = TenantClassificationChange.objects.filter(operator=operator)
    last = changes.order_by("-pk").values_list("pk", flat=True).first()
    return digest([overrides_for(connection, user), last])


def cache_directory(operator, rows, *, store=True):
    """Cache a sanitized directory under its source credential epoch."""
    types = internal_tenant_types(rows)
    for row in rows:
        tenant_id = str(row["tenantId"])
        email = row.get("adminEmail")
        if (f"tenant:{tenant_id}" not in types and isinstance(email, str)
                and EMAIL_PATTERN.fullmatch(email.strip().lower())):
            types[f"tenant:{tenant_id}"] = "external"
    clean = [
        {"tenantId": str(row["tenantId"]), "customerName":
         tenant_display_name(row, str(row["tenantId"]), allow_email=True)}
        for row in rows
    ]
    key = (
        "agione:tenant-directory:v3:"
        f"{operator.pk}:{operator.config_version}:{operator.credential_version}"
    )
    if store:
        try:
            cache.set(key, (clean, types), timeout=60)
        except Exception:
            pass
    return clean, types


def tenant_directory(connection, user, *, use_cache=False, refresh=False):
    """Return all tenants visible to the uniquely authorized Operator."""
    operator = _operator(connection, user)
    if not operator:
        raise AgioneOpsError("OPERATOR_NOT_AVAILABLE", status_code=409)
    if getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False) is not True:
        raise AgioneOpsError("NATIVE_DISABLED", status_code=503)
    key = (
        "agione:tenant-directory:v3:"
        f"{operator.pk}:{operator.config_version}:{operator.credential_version}"
    )
    cached = None
    if use_cache and not refresh:
        try:
            cached = cache.get(key)
        except Exception:
            pass
    if cached is not None:
        rows, types = cached
        return operator, rows, types, operator_overrides(operator)
    source = LiveSource(operator, user, NativeClient)
    try:
        try:
            rows = source.pages(
                "/coperation/tenant/op-customers", {"identityCode": "EU"},
                directory=True, key="tenantId", directory_page_size=100,
            )
        except AgioneOpsError as error:
            if error.code != "SOURCE_REJECTED":
                raise
            rows = source.pages(
                "/coperation/tenant/op-customers", {"identityCode": "EU"},
                directory=True, key="tenantId",
            )
        source.guard()
    finally:
        source.close()
    rows, types = cache_directory(operator, rows, store=use_cache)
    return operator, rows, types, operator_overrides(operator)
