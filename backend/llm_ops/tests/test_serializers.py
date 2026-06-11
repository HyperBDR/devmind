from decimal import Decimal

from django.test import TestCase

from llm_ops.models import LLMModel, LLMProvider, ProcurementChannel
from llm_ops.serializers import (
    ProcurementChannelSerializer,
    ResalePlatformSerializer,
    UsageReconciliationRecordSerializer,
)


class ProcurementChannelSerializerTests(TestCase):
    def test_rejects_unsupported_settlement_currency(self):
        serializer = ProcurementChannelSerializer(
            data={
                "name": "Euro Channel",
                "code": "euro-channel",
                "currency": "EUR",
                "settlement_ratio": "1",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("currency", serializer.errors)


class ResalePlatformSerializerTests(TestCase):
    def test_rejects_non_positive_point_rate(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "0",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("points_per_currency_unit", serializer.errors)


class UsageReconciliationRecordSerializerTests(TestCase):
    def test_create_calculates_reconciliation_fields(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
            input_price_per_million=Decimal("2.5"),
            output_price_per_million=Decimal("10"),
        )
        channel = ProcurementChannel.objects.create(
            name="Direct",
            code="direct",
            settlement_ratio=Decimal("1"),
        )
        serializer = UsageReconciliationRecordSerializer(
            data={
                "date": "2026-06-02",
                "channel": channel.id,
                "model": model.id,
                "input_tokens": 1_000_000,
                "output_tokens": 1_000_000,
                "charged_amount": "20",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        record = serializer.save()

        self.assertEqual(record.expected_amount, Decimal("12.500000"))
        self.assertEqual(record.discrepancy, Decimal("-7.500000"))
        self.assertEqual(record.status, "overcharged")
