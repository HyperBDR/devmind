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

    def test_oauth_start_is_disabled_for_system_archive_folder(self):
        response = self.api.get(
            "/api/v1/quotation/feishu/oauth/start",
            {"return_to": "/quotation/imports?tab=queue"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("system-managed archive folder", response.data["detail"])

    def test_oauth_callback_is_disabled_for_system_archive_folder(self):
        response = self.api.get(
            "/api/v1/quotation/feishu/oauth/callback",
            {"code": "auth-code", "state": "state"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("system-managed archive folder", response.data["detail"])
