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
            settings.QUOTATION_UPLOAD_CHUNK_BYTES,
            1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_ALLOWED_EXTENSIONS,
            (".xlsx", ".pdf"),
        )
        self.assertEqual(
            settings.QUOTATION_ALLOWED_CURRENCIES,
            ("USD", "CNY", "EUR", "GBP", "MYR", "HKD"),
        )
        self.assertEqual(settings.QUOTATION_MAX_ITEMS, 200)
        self.assertEqual(settings.QUOTATION_XLSX_MAX_ENTRIES, 2048)
        self.assertEqual(
            settings.QUOTATION_XLSX_MAX_ENTRY_BYTES,
            64 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_XLSX_MAX_EXPANDED_BYTES,
            128 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_XLSX_MAX_COMPRESSION_RATIO,
            200,
        )
        self.assertEqual(settings.QUOTATION_XLSX_MAX_WORKSHEETS, 20)
        self.assertEqual(settings.QUOTATION_XLSX_MAX_ROWS, 5000)
        self.assertEqual(settings.QUOTATION_XLSX_MAX_COLUMNS, 200)
        self.assertEqual(settings.QUOTATION_XLSX_PARSED_COLUMNS, 20)
        self.assertEqual(
            settings.QUOTATION_XLSX_MAX_SHARED_STRINGS_BYTES,
            32 * 1024 * 1024,
        )
        self.assertEqual(settings.QUOTATION_XLSX_MAX_SHARED_STRINGS, 100000)
        self.assertEqual(
            settings.QUOTATION_PARSE_SOFT_TIME_LIMIT_SECONDS,
            90,
        )
        self.assertEqual(settings.QUOTATION_PARSE_TIME_LIMIT_SECONDS, 120)
        self.assertEqual(
            settings.QUOTATION_MAX_TEMPLATE_BYTES,
            6 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_MAX_PDF_BYTES,
            20 * 1024 * 1024,
        )
        self.assertEqual(
            settings.QUOTATION_MAX_SIGNATURE_BYTES,
            2 * 1024 * 1024,
        )
        self.assertEqual(settings.QUOTATION_SOFFICE_BINARY, "soffice")
        self.assertEqual(settings.QUOTATION_RENDER_TIMEOUT_SECONDS, 120)
        self.assertEqual(settings.QUOTATION_RENDER_CONCURRENCY, 1)
        self.assertEqual(settings.QUOTATION_RENDER_RETRY_SECONDS, 10)
