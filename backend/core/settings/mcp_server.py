"""Settings for MCP OAuth endpoints and accepted transport hosts."""

import os


_client_base_url = os.getenv(
    "MCP_OAUTH_CLIENT_BASE_URL",
    "http://host.docker.internal:18000",
).strip().rstrip("/")
_browser_base_url = os.getenv(
    "MCP_OAUTH_BROWSER_BASE_URL",
    "http://localhost:18000",
).strip().rstrip("/")

MCP_OAUTH_ISSUER_URL = os.getenv(
    "MCP_OAUTH_ISSUER_URL", _client_base_url
).strip().rstrip("/") + "/"
MCP_OAUTH_RESOURCE_URL = os.getenv(
    "MCP_OAUTH_RESOURCE_URL", f"{_client_base_url}/mcp"
).strip().rstrip("/")
MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL = os.getenv(
    "MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL",
    f"{_browser_base_url}/authorize",
).strip()
MCP_OAUTH_TOKEN_ENDPOINT_URL = os.getenv(
    "MCP_OAUTH_TOKEN_ENDPOINT_URL", f"{_client_base_url}/token"
).strip()
MCP_OAUTH_REGISTRATION_ENDPOINT_URL = os.getenv(
    "MCP_OAUTH_REGISTRATION_ENDPOINT_URL",
    f"{_client_base_url}/register",
).strip()
MCP_OAUTH_REVOCATION_ENDPOINT_URL = os.getenv(
    "MCP_OAUTH_REVOCATION_ENDPOINT_URL", f"{_client_base_url}/revoke"
).strip()
MCP_OAUTH_CONSENT_URL = os.getenv(
    "MCP_OAUTH_CONSENT_URL",
    f"{_browser_base_url}/oauth/mcp/authorize",
).strip()
MCP_OAUTH_SCOPES = [
    scope.strip()
    for scope in os.getenv("MCP_OAUTH_SCOPES", "mcp:read").split(",")
    if scope.strip()
]
MCP_ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "MCP_ALLOWED_HOSTS",
        "localhost:*,127.0.0.1:*,host.docker.internal:*",
    ).split(",")
    if host.strip()
]
