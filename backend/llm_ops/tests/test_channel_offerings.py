from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from llm_ops.models import (
    ChannelModelPrice,
    ChannelOffering,
    LLMModel,
    LLMProvider,
    MetaModel,
    ProcurementChannel,
)


class ChannelOfferingAPITests(TestCase):
    """Protect procurement offering identity and legacy API behavior."""

    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username="offering-ops",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(user)
        self.provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai-offering-tests",
        )
        self.meta_model = MetaModel.objects.create(
            name="GPT-5",
            code="gpt-5-offering-tests",
        )
        self.model = LLMModel.objects.create(
            provider=self.provider,
            meta_model=self.meta_model,
            name="GPT-5",
            code="gpt-5-offering-tests",
        )
        self.channel = ProcurementChannel.objects.create(
            name="Supplier",
            code="supplier-offering-tests",
        )

    def test_same_channel_and_model_accept_two_procurement_offerings(self):
        first = self._create_offering("sku-primary", "Primary SKU")
        second = self._create_offering("sku-backup", "Backup SKU")

        for offering in (first, second):
            response = self.client.post(
                reverse("channel-model-price-list"),
                {
                    "channel": self.channel.id,
                    "model": self.model.id,
                    "offering": offering.id,
                    "custom_input_price_per_million": "2.5",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)

        self.assertEqual(ChannelModelPrice.objects.count(), 2)
        self.assertEqual(
            set(
                ChannelModelPrice.objects.values_list(
                    "offering__offering_key",
                    flat=True,
                )
            ),
            {"sku-primary", "sku-backup"},
        )

    def test_legacy_price_payload_creates_and_returns_default_offering(self):
        response = self.client.post(
            reverse("channel-model-price-list"),
            {
                "channel": self.channel.id,
                "model": self.model.id,
                "custom_input_price_per_million": "2.5",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        price = ChannelModelPrice.objects.get()
        self.assertIsNotNone(price.offering_id)
        self.assertEqual(response.data["offering"], price.offering_id)
        self.assertEqual(
            response.data["offering_key"],
            price.offering.offering_key,
        )
        self.assertTrue(price.offering.is_default)

    def test_price_rejects_offering_from_another_meta_model(self):
        other_meta_model = MetaModel.objects.create(
            name="Claude",
            code="claude-offering-tests",
        )
        offering = ChannelOffering.objects.create(
            channel=self.channel,
            meta_model=other_meta_model,
            offering_key="claude-sku",
            display_name="Claude SKU",
        )

        response = self.client.post(
            reverse("channel-model-price-list"),
            {
                "channel": self.channel.id,
                "model": self.model.id,
                "offering": offering.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("offering", response.data)

    def _create_offering(self, key, name):
        response = self.client.post(
            reverse("channel-offering-list"),
            {
                "channel": self.channel.id,
                "meta_model": self.meta_model.id,
                "model": self.model.id,
                "offering_key": key,
                "display_name": name,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return ChannelOffering.objects.get(pk=response.data["id"])
