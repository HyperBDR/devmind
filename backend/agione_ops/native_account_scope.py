"""Classify verified account identities without storing email addresses."""

import re


INTERNAL_DOMAINS = frozenset({
    "oneprocloud.com", "oneprocloud.test", "oneprocloud.cn", "onepro.cloud",
})
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def classify_account(identity, tenant_id, user_id):
    """Classify only when the requested identity and returned tenant match."""
    if not isinstance(identity, dict) or not tenant_id or not user_id:
        return "unknown"
    if (str(identity.get("tenantId") or "") != str(tenant_id)
            or str(identity.get("userId") or "") != str(user_id)):
        return "unknown"
    email = identity.get("email")
    if not isinstance(email, str) or len(email) > 254:
        return "unknown"
    email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        return "unknown"
    return "internal" if email.rsplit("@", 1)[1] in INTERNAL_DOMAINS else "external"


def include_external(account_type):
    """Keep unknown identities visible while excluding verified internal users."""
    return account_type in {"external", "unknown"}


def classify_rows(rows, lookup):
    """Build a tenant-scoped classification without retaining identities."""
    pairs = {
        (str(row.get("customer_id") or ""), str(row.get("user_id") or ""))
        for row in rows if row.get("subject_type") == "USER"
        and row.get("customer_id") and row.get("user_id")
    }
    identities = {}
    result = {}
    for tenant, user in sorted(pairs):
        if user not in identities:
            identities[user] = lookup(user)
        result[f"{tenant}:{user}"] = classify_account(
            identities[user], tenant, user,
        )
    return result


def external_rows(rows, types):
    """Remove verified internal users; retain unverifiable and project calls."""
    return [row for row in rows if row.get("subject_type") != "USER"
            or include_external(types.get(
                f"{row.get('customer_id')}:{row.get('user_id')}", "unknown"
            ))]


def merge_account_types(previous, current):
    """Keep known results when a later lookup cannot verify an identity."""
    result = dict(previous)
    for key, value in current.items():
        if value != "unknown" or key not in result:
            result[key] = value
    return result


def external_finance_directory(rows):
    """Exclude tenants whose administrator has a verified internal email."""
    eligible = set()
    for row in rows:
        tenant = str(row.get("tenantId") or "")
        email = row.get("adminEmail")
        email = email.strip().lower() if isinstance(email, str) else ""
        if (not EMAIL_PATTERN.fullmatch(email)
                or email.rsplit("@", 1)[1] not in INTERNAL_DOMAINS):
            eligible.add(tenant)
    return eligible
