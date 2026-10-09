import hashlib
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from mcp_server.models import McpRobotCredential
from mcp_server.oauth import DevMindTokenVerifier
from mcp_server.server import _require_robot_scope


@override_settings(
    MCP_OAUTH_ISSUER_URL="https://devmind.example/",
    MCP_OAUTH_RESOURCE_URL="https://devmind.example/mcp",
)
class McpRobotCredentialTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="mcp-admin",
            password="password",
            is_staff=True,
        )
        self.principal = User.objects.create_user(
            username="quote-robot",
            password="unused",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_admin_can_issue_and_revoke_secret_without_listing_it(self):
        response = self.client.post(
            "/api/v1/mcp/robots/",
            {
                "name": "Quote Reader",
                "user_id": self.principal.pk,
                "scopes": ["quotation:read"],
                "expires_in_days": 30,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        raw_token = response.data["token"]
        credential = McpRobotCredential.objects.get(
            pk=response.data["id"]
        )
        self.assertTrue(raw_token.startswith("dmrobot_"))
        self.assertEqual(
            credential.token_hash,
            hashlib.sha256(raw_token.encode()).hexdigest(),
        )
        access_token = DevMindTokenVerifier._load_robot_token(raw_token)
        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.subject, str(self.principal.pk))
        self.assertEqual(
            access_token.scopes,
            ["mcp:read", "quotation:read"],
        )
        self.assertEqual(
            access_token.resource,
            "https://devmind.example/mcp",
        )

        listed = self.client.get("/api/v1/mcp/robots/")
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(raw_token, str(listed.data))
        self.assertNotIn("token_hash", str(listed.data))

        revoked = self.client.delete(
            f"/api/v1/mcp/robots/{credential.pk}/"
        )
        self.assertEqual(revoked.status_code, 204)
        self.assertIsNone(
            DevMindTokenVerifier._load_robot_token(raw_token)
        )

    def test_non_admin_cannot_manage_robot_credentials(self):
        user = User.objects.create_user(
            username="ordinary-user",
            password="password",
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/mcp/robots/")

        self.assertEqual(response.status_code, 403)

    def test_robot_scope_is_enforced_per_mcp_tool(self):
        token = AccessToken(
            token="robot-secret",
            client_id="robot:123",
            scopes=["mcp:read", "quotation:read"],
            expires_at=None,
            resource="https://devmind.example/mcp",
            subject=str(self.principal.pk),
        )

        with patch("mcp_server.server.get_access_token", return_value=token):
            _require_robot_scope("quotation:read")
            with self.assertRaises(ToolError):
                _require_robot_scope("invoice:read")

    def test_oauth_user_tokens_keep_existing_scope_behavior(self):
        token = AccessToken(
            token="oauth-secret",
            client_id="standard-oauth-client",
            scopes=["mcp:read"],
            expires_at=None,
            resource="https://devmind.example/mcp",
            subject=str(self.principal.pk),
        )

        with patch("mcp_server.server.get_access_token", return_value=token):
            _require_robot_scope("quotation:read")
            _require_robot_scope("invoice:read")
