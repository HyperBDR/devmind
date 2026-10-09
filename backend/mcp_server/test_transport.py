"""Check authenticated MCP requests with production proxy Host headers."""

from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase, override_settings
from mcp.server.auth.provider import AccessToken
from starlette.testclient import TestClient

from mcp_server.server import build_asgi_app
from mcp_server.test_settings import load_settings


class McpTransportHostTests(SimpleTestCase):
    def setUp(self):
        generated = load_settings()
        self.values = {
            key: value for key, value in generated.items()
            if key.startswith("MCP_")
        }
        self.token = AccessToken(
            token="test-transport-token",
            client_id="test-transport-client",
            scopes=["mcp:read"],
            resource=self.values["MCP_OAUTH_RESOURCE_URL"],
        )

    def request(self, host, authenticated=True):
        """Send a real tools/list request through ASGI and SDK middleware."""
        headers = {
            "Host": host,
            "Accept": "application/json, text/event-stream",
        }
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token.token}"
        with override_settings(DEBUG=False, **self.values):
            with patch(
                "mcp_server.oauth.DevMindTokenVerifier.verify_token",
                new_callable=AsyncMock,
                return_value=self.token,
            ) as verify:
                with TestClient(
                    build_asgi_app(),
                    base_url="https://tower.oneprocloud.com",
                ) as client:
                    response = client.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/list",
                        },
                    )
                if authenticated:
                    verify.assert_awaited_once_with(self.token.token)
                else:
                    verify.assert_not_awaited()
        return response

    def test_authenticated_proxy_and_direct_hosts_reach_mcp(self):
        for host in ("tower.oneprocloud.com", "tower.oneprocloud.com:443"):
            with self.subTest(host=host):
                response = self.request(host)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('"tools"', response.text)
                self.assertIn('"search_quotations"', response.text)

    def test_authenticated_ipv6_hosts_reach_mcp(self):
        generated = load_settings(
            MCP_OAUTH_CLIENT_BASE_URL="https://[2001:db8::1]",
            MCP_OAUTH_BROWSER_BASE_URL="https://[2001:db8::1]",
        )
        self.values = {
            key: value for key, value in generated.items()
            if key.startswith("MCP_")
        }
        self.token.resource = self.values["MCP_OAUTH_RESOURCE_URL"]
        for host in ("[2001:db8::1]", "[2001:db8::1]:443"):
            with self.subTest(host=host):
                response = self.request(host)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('"tools"', response.text)

    def test_authenticated_unrelated_hosts_are_rejected(self):
        for host in (
            "untrusted.company.test", "tower.oneprocloud.com.evil.test",
        ):
            with self.subTest(host=host):
                response = self.request(host)
                self.assertEqual(response.status_code, 421, response.text)

    def test_authentication_remains_required(self):
        response = self.request("tower.oneprocloud.com", authenticated=False)
        self.assertEqual(response.status_code, 401, response.text)
