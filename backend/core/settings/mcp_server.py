"""Settings for MCP OAuth endpoints and accepted transport hosts."""

import os
from urllib.parse import urlsplit


def _setting(name, default):
    """Use a nonempty environment override or its computed default."""
    return os.getenv(name, "").strip() or default


def _production_base_url():
    """Reuse the configured site origin or the hosted DevMind origin."""
    for name in ("SITE_DOMAIN", "FRONTEND_URL"):
        value = os.getenv(name, "").strip()
        if not value:
            continue
        parsed = urlsplit(value if "://" in value else f"https://{value}")
        host = parsed.hostname or ""
        if (
            not host
            or host in {"localhost", "host.docker.internal", "::1"}
            or host.startswith("127.")
            or host.endswith((".localhost", ".example.com"))
            or parsed.username is not None
            or parsed.password is not None
        ):
            continue
        return f"https://{parsed.netloc}"
    return "https://tower.oneprocloud.com"


_development = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
_public_base_url = "" if _development else _production_base_url()
_client_base_url = _setting(
    "MCP_OAUTH_CLIENT_BASE_URL",
    "http://host.docker.internal:18000" if _development else _public_base_url,
).rstrip("/")
_browser_base_url = _setting(
    "MCP_OAUTH_BROWSER_BASE_URL",
    "http://localhost:18000" if _development else _public_base_url,
).rstrip("/")

MCP_OAUTH_ISSUER_URL = _setting(
    "MCP_OAUTH_ISSUER_URL", _client_base_url
).strip().rstrip("/") + "/"
MCP_OAUTH_RESOURCE_URL = _setting(
    "MCP_OAUTH_RESOURCE_URL", f"{_client_base_url}/mcp"
).strip().rstrip("/")
MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL = _setting(
    "MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL",
    f"{_browser_base_url}/authorize",
).strip()
MCP_OAUTH_TOKEN_ENDPOINT_URL = _setting(
    "MCP_OAUTH_TOKEN_ENDPOINT_URL", f"{_client_base_url}/token"
).strip()
MCP_OAUTH_REGISTRATION_ENDPOINT_URL = _setting(
    "MCP_OAUTH_REGISTRATION_ENDPOINT_URL",
    f"{_client_base_url}/register",
).strip()
MCP_OAUTH_REVOCATION_ENDPOINT_URL = _setting(
    "MCP_OAUTH_REVOCATION_ENDPOINT_URL", f"{_client_base_url}/revoke"
).strip()
MCP_OAUTH_CONSENT_URL = _setting(
    "MCP_OAUTH_CONSENT_URL",
    f"{_browser_base_url}/oauth/mcp/authorize",
).strip()
MCP_OAUTH_SCOPES = [
    scope.strip()
    for scope in _setting("MCP_OAUTH_SCOPES", "mcp:read").split(",")
    if scope.strip()
]
_default_hosts = (
    [
        "localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*",
        "host.docker.internal", "host.docker.internal:*",
    ]
    if _development else []
)
for _url in (
    MCP_OAUTH_ISSUER_URL,
    MCP_OAUTH_RESOURCE_URL,
    MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL,
    MCP_OAUTH_TOKEN_ENDPOINT_URL,
    MCP_OAUTH_REGISTRATION_ENDPOINT_URL,
    MCP_OAUTH_REVOCATION_ENDPOINT_URL,
    MCP_OAUTH_CONSENT_URL,
):
    _host = urlsplit(_url).hostname
    if _host:
        _host = f"[{_host}]" if ":" in _host else _host
        for _host_pattern in (_host, f"{_host}:*"):
            if _host_pattern not in _default_hosts:
                _default_hosts.append(_host_pattern)
MCP_ALLOWED_HOSTS = [
    host.strip()
    for host in _setting(
        "MCP_ALLOWED_HOSTS", ",".join(_default_hosts)
    ).split(",")
    if host.strip()
]
