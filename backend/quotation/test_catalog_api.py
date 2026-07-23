from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from quotation.models import UserQuotationCatalog


def catalog_payload(name="Product A"):
    return {
        "version": "onepro-template-may-2026-v1",
        "products": [
            {
                "id": "product-a",
                "name": name,
                "code": "SW-A",
                "listPrice": 100,
                "category": "Software License",
                "description": "Product description",
            }
        ],
        "services": [],
        "discounts": [
            {
                "id": "discount-10",
                "name": "10%",
                "percentage": 10,
            }
        ],
        "productLines": [{"value": "BDR", "label": "HyperBDR"}],
        "paymentTerms": [{"value": "CIA", "label": "CIA (Cash in Advance)"}],
    }


class UserQuotationCatalogApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user(
            username="alice-catalog@example.com",
            email="alice-catalog@example.com",
            password="password",
        )
        self.bob = user_model.objects.create_user(
            username="bob-catalog@example.com",
            email="bob-catalog@example.com",
            password="password",
        )
        self.api = APIClient()

    def test_get_returns_empty_catalog_for_new_user(self):
        self.api.force_authenticate(self.alice)

        response = self.api.get("/api/v1/quotation/catalog")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["initialized"])
        self.assertEqual(response.data["products"], [])
        self.assertEqual(response.data["services"], [])

    def test_put_persists_complete_catalog_for_current_user(self):
        payload = catalog_payload()
        payload["products"][0]["currency"] = "CNY"
        self.api.force_authenticate(self.alice)

        response = self.api.put(
            "/api/v1/quotation/catalog",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["initialized"])
        self.assertEqual(response.data["products"][0]["name"], "Product A")
        catalog = UserQuotationCatalog.objects.get(user=self.alice)
        self.assertEqual(catalog.products[0]["name"], "Product A")
        self.assertEqual(catalog.products[0]["currency"], "CNY")

    def test_catalog_data_is_isolated_per_user(self):
        UserQuotationCatalog.objects.create(
            user=self.alice,
            initialized=True,
            **{
                "catalog_version": "v1",
                "products": catalog_payload("Alice Product")["products"],
            },
        )
        UserQuotationCatalog.objects.create(
            user=self.bob,
            initialized=True,
            **{
                "catalog_version": "v1",
                "products": catalog_payload("Bob Product")["products"],
            },
        )
        self.api.force_authenticate(self.bob)

        response = self.api.get("/api/v1/quotation/catalog")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["products"][0]["name"], "Bob Product")

    def test_legacy_import_does_not_overwrite_server_catalog(self):
        UserQuotationCatalog.objects.create(
            user=self.alice,
            initialized=True,
            catalog_version="v1",
            products=catalog_payload("Server Product")["products"],
        )
        self.api.force_authenticate(self.alice)

        response = self.api.post(
            "/api/v1/quotation/catalog/import-legacy",
            catalog_payload("Browser Product"),
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["imported"])
        self.assertEqual(
            response.data["catalog"]["products"][0]["name"],
            "Server Product",
        )

    def test_repeated_legacy_import_is_idempotent(self):
        self.api.force_authenticate(self.alice)
        payload = catalog_payload("Browser Product")

        first = self.api.post(
            "/api/v1/quotation/catalog/import-legacy",
            payload,
            format="json",
        )
        second = self.api.post(
            "/api/v1/quotation/catalog/import-legacy",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["imported"])
        self.assertFalse(second.data["imported"])
        self.assertEqual(
            UserQuotationCatalog.objects.filter(user=self.alice).count(), 1
        )

    def test_bootstrap_uses_defaults_only_when_catalog_is_empty(self):
        self.api.force_authenticate(self.alice)

        first = self.api.post(
            "/api/v1/quotation/catalog/bootstrap",
            catalog_payload("Default Product"),
            format="json",
        )
        second = self.api.post(
            "/api/v1/quotation/catalog/bootstrap",
            catalog_payload("Changed Default"),
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["created"])
        self.assertFalse(second.data["created"])
        self.assertEqual(
            second.data["catalog"]["products"][0]["name"],
            "Default Product",
        )
