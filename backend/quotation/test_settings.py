from django.conf import settings
from django.test import SimpleTestCase


class QuotationSettingsTests(SimpleTestCase):
    def test_quotation_settings_keep_existing_defaults(self):
        self.assertEqual(
            settings.QUOTATION_STORAGE,
            f"{settings.STORAGE_ROOT}/quotation",
        )
        self.assertEqual(
            settings.FEISHU_OAUTH_REDIRECT_URI,
            (
                f"{settings.FRONTEND_URL.rstrip('/')}"
                "/api/v1/quotation/feishu/oauth/callback"
            ),
        )
        self.assertIn("drive:file:upload", settings.FEISHU_OAUTH_SCOPES)
        self.assertIn("offline_access", settings.FEISHU_OAUTH_SCOPES)
        self.assertTrue(settings.QUOTATION_STORAGE_ROUTER_ENABLED)
        self.assertTrue(settings.QUOTATION_DOCUMENT_REPLICA_ENABLED)

    def test_quotation_limits_have_production_defaults(self):
        self.assertEqual(
            settings.QUOTATION_MAX_UPLOAD_BYTES,
            50 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_ALLOWED_EXTENSIONS,
            (".xlsx", ".pdf"),
        )
        self.assertEqual(
            settings.QUOTATION_MAX_PDF_HTML_BYTES,
            5 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_MAX_PDF_XLSX_BYTES,
            6 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_MAX_XLSX_EXPANDED_BYTES,
            50 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_MAX_PDF_BYTES,
            20 * 1024 * 1024,
        )
        self.assertEqual(settings.GOTENBERG_URL, "http://gotenberg:3000")
        self.assertEqual(settings.GOTENBERG_TIMEOUT_SECONDS, 30)
