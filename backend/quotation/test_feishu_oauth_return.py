from urllib.parse import parse_qs, urlparse

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(
    FEISHU_APP_ID="cli_test",
    FEISHU_APP_SECRET="secret_test",
    FEISHU_BASE_URL="https://open.feishu.test",
)
class FeishuOAuthReturnTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="oauth-user",
            email="oauth@example.com",
            password="password",
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_oauth_start_preserves_quote_desk_return_path_in_state(self):
        response = self.api.get(
            "/api/v1/quotation/feishu/oauth/start",
            {"return_to": "/quotation/imports?tab=queue"},
        )

        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.data["authorize_url"]).query)
        payload = jwt.decode(
            query["state"][0],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        self.assertEqual(payload["sub"], self.user.email)
        self.assertEqual(payload["return_to"], "/quotation/imports?tab=queue")

    def test_oauth_start_rejects_external_return_path_in_state(self):
        response = self.api.get(
            "/api/v1/quotation/feishu/oauth/start",
            {"return_to": "https://evil.example/phish"},
        )

        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.data["authorize_url"]).query)
        payload = jwt.decode(
            query["state"][0],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        self.assertEqual(payload["return_to"], "/quotation/list")

    def test_oauth_callback_redirects_back_to_quote_desk_return_path(self):
        state = jwt.encode(
            {
                "sub": self.user.email,
                "purpose": "feishu_oauth",
                "nonce": "test-nonce",
                "return_to": "/quotation/list?from=feishu",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        class FakeClient:
            def exchange_code_for_user_token(self, code):
                from quotation.services.feishu_client import FeishuTokenBundle

                return FeishuTokenBundle(
                    access_token="access-token",
                    refresh_token="refresh-token",
                    expires_in=7200,
                    scope="drive:file",
                )

            def get_user_info(self, access_token):
                return {
                    "open_id": "ou_test",
                    "union_id": "on_test",
                    "name": "OAuth User",
                }

        with override_settings(FRONTEND_URL="http://localhost:18000"):
            from unittest.mock import patch

            with patch("quotation.views.feishu._client", return_value=FakeClient()):
                response = self.api.get(
                    "/api/v1/quotation/feishu/oauth/callback",
                    {"code": "auth-code", "state": state},
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "http://localhost:18000/quotation/list?from=feishu&feishu=connected",
        )
