from django.test import SimpleTestCase
from django.urls import Resolver404, resolve


class QuotationIntegrationRouteTests(SimpleTestCase):
    def test_quotation_feishu_status_uses_devmind_api_prefix(self):
        match = resolve("/api/v1/quotation/feishu/status")

        self.assertEqual(match.func.view_class.__name__, "FeishuStatusView")

    def test_flat_feishu_prefix_is_not_registered_in_devmind(self):
        with self.assertRaises(Resolver404):
            resolve("/api/v1/feishu/status")
