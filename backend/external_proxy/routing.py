"""Routing table builder for OpenResty consumption.

NOTE: secrets (static_token, hmac_secret) leave this function in
plaintext. They are encrypted at rest in the DB (see
`external_proxy.encrypted_fields`), but they have to be decrypted
here for OpenResty to use them as auth headers. The endpoint that
returns this table is restricted to docker-network callers via
`_is_internal_request`; a stricter alternative would be to keep
secrets server-side and have Lua call back into Django per request.
"""
from .models import ExternalSite


def build_routing_table():
    """Build routing table for OpenResty consumption."""
    sites = ExternalSite.objects.filter(
        is_active=True,
    ).order_by("-order")
    table = []
    for site in sites:
        entry = {
            "id": site.id,
            "slug": site.slug,
            "target_host": site.target_host,
            "target_scheme": site.target_scheme,
            "verify_tls": site.verify_tls,
            "access_mode": site.access_mode,
            "external_url": site.external_url,
            "auth_type": site.auth_type,
            "required_feature": site.required_feature or "admin_console",
        }
        if site.auth_type == ExternalSite.AUTH_TYPE_STATIC_TOKEN:
            entry["static_token"] = site.static_token
        elif site.auth_type == ExternalSite.AUTH_TYPE_HMAC:
            entry["hmac_secret"] = site.hmac_secret
        table.append(entry)
    return table
