from decimal import Decimal

from django.test import TestCase

from llm_ops.models import LLMModel, LLMProvider, MetaModel, ProcurementChannel
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

    def test_meta_model_serializer_exposes_canonical_vendor(self):
        """The serializer always reports the canonical vendor."""
        from llm_ops.models import LLMProvider, MetaModel
        from llm_ops.serializers import MetaModelSerializer
        aliyun = LLMProvider.objects.create(
            name="阿里云",
            code="aliyun",
        )
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        # Manually inserted with the wrong vendor (legacy state).
        wrong = MetaModel.objects.create(
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
            vendor=aliyun,
        )
        data = MetaModelSerializer(wrong).data
        self.assertEqual(data["effective_vendor_code"], "deepseek")
        self.assertEqual(data["effective_vendor_name"], "DeepSeek")
        self.assertEqual(data["effective_vendor"], deepseek.id)
        # The raw pointer is preserved for auditing.
        self.assertEqual(data["raw_vendor"], aliyun.id)



class EnsureMetaModelForPriceDataTests(TestCase):
    """Verify the dedup behaviour of ``ensure_meta_model_for_price_data``.

    A price record may be reported under several spellings
    (for example ``deepseek-r1-0528`` vs ``deepseek-r1-250528``)
    while the canonical row only stores one of them. The helper
    must never create a duplicate meta model in that case, and
    must keep the alias set in sync so future lookups succeed
    without a manual merge.
    """

    def setUp(self):
        self.deepseek = LLMProvider.objects.create(
            name="DeepSeek", code="deepseek"
        )
        self.aliyun = LLMProvider.objects.create(
            name="阿里云", code="aliyun"
        )

    def test_creates_canonical_row_on_first_call(self):
        from llm_ops.serializers import ensure_meta_model_for_price_data

        meta = ensure_meta_model_for_price_data(
            {
                "code": "deepseek-r1-0528",
                "name": "DeepSeek R1 0528",
                "provider": self.deepseek,
            }
        )
        self.assertEqual(meta.code, "deepseek-r1-0528")
        self.assertEqual(MetaModel.objects.filter(vendor=self.deepseek).count(), 1)

    def test_reuses_existing_row_when_alias_known(self):
        from llm_ops.serializers import ensure_meta_model_for_price_data

        canonical = ensure_meta_model_for_price_data(
            {
                "code": "deepseek-r1-0528",
                "name": "DeepSeek R1 0528",
                "provider": self.deepseek,
            }
        )
        # The volcengine collector reports the same release
        # under the 250528 spelling. The helper must reuse the
        # canonical row instead of creating a parallel row,
        # because the collector now publishes the canonical
        # name "DeepSeek R1 0528" alongside the legacy code.
        alias_report = ensure_meta_model_for_price_data(
            {
                "code": "deepseek-r1-250528",
                "name": "DeepSeek R1 0528",
                "provider": self.deepseek,
            }
        )
        self.assertEqual(alias_report.id, canonical.id)
        self.assertIn("deepseek-r1-250528", alias_report.aliases)
        self.assertEqual(
            MetaModel.objects.filter(vendor=self.deepseek).count(),
            1,
        )

    def test_aliases_are_idempotent(self):
        from llm_ops.serializers import ensure_meta_model_for_price_data

        canonical = ensure_meta_model_for_price_data(
            {
                "code": "deepseek-r1-0528",
                "name": "DeepSeek R1 0528",
                "provider": self.deepseek,
            }
        )
        # Reporting the same alternate code twice must not
        # duplicate the alias entry either.
        for _ in range(2):
            ensure_meta_model_for_price_data(
                {
                    "code": "deepseek-r1-250528",
                    "name": "DeepSeek R1 0528",
                    "provider": self.deepseek,
                }
            )
        canonical.refresh_from_db()
        self.assertEqual(
            sum(
                1
                for alias in canonical.aliases
                if alias == "deepseek-r1-250528"
            ),
            1,
        )

    def test_raw_code_path_also_reuses_canonical(self):
        from llm_ops.serializers import ensure_meta_model_for_price_data

        canonical = ensure_meta_model_for_price_data(
            {
                "code": "deepseek-r1-0528",
                "name": "DeepSeek R1 0528",
                "provider": self.deepseek,
            }
        )
        # ``raw_code`` carries the spelling the collector
        # actually saw. Even when ``code`` is missing the
        # helper must still find the canonical row through
        # the alias index that the previous call seeded.
        reused = ensure_meta_model_for_price_data(
            {
                "code": "",
                "name": "DeepSeek R1 0528",
                "raw_code": "deepseek-r1-250528",
                "provider": self.deepseek,
            }
        )
        self.assertEqual(reused.id, canonical.id)
        self.assertIn("deepseek-r1-250528", reused.aliases)
