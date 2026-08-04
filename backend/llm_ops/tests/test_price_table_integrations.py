from decimal import Decimal

from django.test import TestCase

from llm_ops.collection_services import price_item_payload
from llm_ops.models import (
    ChannelPriceItem,
    LLMModel,
    LLMProvider,
    ModelPriceItem,
    ModelSku,
    PriceCollectionSource,
    ProcurementChannel,
    SourceSkuOffering,
)
from llm_ops.price_table_validation import (
    ERROR_INVALID_USAGE_RANGE_SPEC,
    ERROR_MIXED_FLAT_AND_TIERED,
    ERROR_VOLUME_UNSUPPORTED,
    usage_range_spec,
)
from llm_ops.serializers import (
    ChannelPriceItemSerializer,
    ModelPriceItemSerializer,
)


class PriceTableIntegrationTests(TestCase):
    def setUp(self):
        self.provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        self.model = LLMModel.objects.create(
            provider=self.provider,
            name="GPT-5",
            code="gpt-5",
        )
        self.source = PriceCollectionSource.objects.create(
            provider=self.provider,
            name="OpenAI Official",
            slug="openai-official",
        )
        self.sku = ModelSku.objects.create(
            meta_model=self.model.meta_model,
            provider=self.provider,
            canonical_sku_code=self.model.code,
            upstream_model_name=self.model.code,
            display_name=self.model.name,
        )
        self.offering = SourceSkuOffering.objects.create(
            source=self.source,
            sku=self.sku,
            provider=self.provider,
            exposed_model_name=self.model.code,
        )
        self.channel = ProcurementChannel.objects.create(
            name="Supplier A",
            code="supplier-a",
        )

    def model_payload(self, **overrides):
        """Build one model price serializer payload."""
        payload = {
            "provider": self.provider.id,
            "model": self.model.id,
            "sku": self.sku.id,
            "offering": self.offering.id,
            "source": self.source.id,
            "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
            "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
            "currency": "USD",
            "unit_price": "1.000000",
            "tier_type": ModelPriceItem.TIER_USAGE_RANGE,
            "tier_start": "0",
            "tier_end": None,
            "spec": usage_range_spec(),
            "price_fingerprint": "model-tier",
        }
        payload.update(overrides)
        return payload

    def channel_payload(self, **overrides):
        """Build one channel price serializer payload."""
        payload = {
            "channel": self.channel.id,
            "model": self.model.id,
            "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
            "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
            "currency": "USD",
            "unit_price": "0.800000",
            "tier_type": ModelPriceItem.TIER_USAGE_RANGE,
            "tier_start": "0",
            "tier_end": None,
            "spec": usage_range_spec(),
            "price_fingerprint": "channel-tier",
        }
        payload.update(overrides)
        return payload

    def assert_price_table_error(self, serializer, expected_code):
        """Assert the DRF boundary preserves the shared error code."""
        self.assertFalse(serializer.is_valid())
        self.assertIn("price_table", serializer.errors, serializer.errors)
        error = serializer.errors["price_table"]
        self.assertEqual(str(error["code"]), expected_code)
        self.assertEqual(error["code"].code, expected_code)
        self.assertTrue(str(error["message"]))

    def test_collected_usage_range_payload_adds_contract_spec(self):
        payload = price_item_payload(
            {},
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            unit_price=Decimal("1"),
            spec={"region": "cn-beijing"},
            tier_start=Decimal("0"),
            tier_end=Decimal("1000000"),
        )

        self.assertEqual(payload["spec"]["region"], "cn-beijing")
        self.assertEqual(
            payload["spec"]["tier_metric"],
            "request_input_tokens",
        )
        self.assertEqual(payload["spec"]["tier_charge_mode"], "matched_tier")
        self.assertEqual(payload["spec"]["aggregation_period"], "request")

    def test_model_serializer_returns_stable_volume_error_code(self):
        serializer = ModelPriceItemSerializer(
            data=self.model_payload(tier_type=ModelPriceItem.TIER_VOLUME)
        )

        self.assert_price_table_error(serializer, ERROR_VOLUME_UNSUPPORTED)

    def test_model_serializer_rejects_non_object_tier_spec(self):
        serializer = ModelPriceItemSerializer(
            data=self.model_payload(spec=["request_input_tokens"])
        )

        self.assert_price_table_error(
            serializer,
            ERROR_INVALID_USAGE_RANGE_SPEC,
        )

    def test_channel_serializer_returns_same_volume_error_code(self):
        serializer = ChannelPriceItemSerializer(
            data=self.channel_payload(tier_type=ModelPriceItem.TIER_VOLUME)
        )

        self.assert_price_table_error(serializer, ERROR_VOLUME_UNSUPPORTED)

    def test_model_serializer_rejects_mixed_current_table(self):
        ModelPriceItem.objects.create(
            provider=self.provider,
            model=self.model,
            meta_model=self.model.meta_model,
            sku=self.sku,
            offering=self.offering,
            source=self.source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("1"),
            tier_type=ModelPriceItem.TIER_FLAT,
            price_fingerprint="existing-flat",
        )
        serializer = ModelPriceItemSerializer(data=self.model_payload())

        self.assert_price_table_error(
            serializer,
            ERROR_MIXED_FLAT_AND_TIERED,
        )

    def test_channel_serializer_accepts_valid_usage_range_contract(self):
        serializer = ChannelPriceItemSerializer(data=self.channel_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        item = serializer.save()

        self.assertEqual(item.meta_model_id, self.model.meta_model_id)
        self.assertEqual(
            item.spec["tier_metric"],
            "request_input_tokens",
        )
