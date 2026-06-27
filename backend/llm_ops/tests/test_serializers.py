from decimal import Decimal

from django.test import TestCase

from llm_ops.models import (
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionSource,
    ProcurementChannel,
    ResalePlatform,
)
from llm_ops.serializers import (
    LLMModelSerializer,
    ModelPriceItemSerializer,
    PriceCollectionSourceSerializer,
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
    def test_accepts_platform_api_key(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "api_key": "agione-secret-key",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_accepts_platform_metadata(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Singapore",
                "code": "agione-sg",
                "platform_type": "agione",
                "region_code": "ap-southeast-1",
                "region_name": "Singapore",
                "environment": "production",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "metadata": {
                    "tenant_id": "tenant-001",
                    "settlement_cycle": "monthly",
                },
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_converts_null_metadata_to_empty_object(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "metadata": None,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        platform = serializer.save()
        self.assertEqual(platform.metadata, {})

    def test_converts_blank_metadata_to_empty_object(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "metadata": "",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        platform = serializer.save()
        self.assertEqual(platform.metadata, {})

    def test_partial_update_without_metadata_preserves_value(self):
        platform = ResalePlatform.objects.create(
            name="Agione Test",
            code="agione-test",
            currency="CNY",
            points_per_currency_unit=Decimal("100"),
            metadata={"tenant_id": "tenant-001"},
        )
        serializer = ResalePlatformSerializer(
            platform,
            data={"name": "Agione Updated"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.metadata, {"tenant_id": "tenant-001"})

    def test_rejects_non_object_metadata(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "metadata": ["tenant-001"],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("metadata", serializer.errors)

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

    def test_rejects_invalid_service_fee_rate(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "service_fee_rate": "1.2",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("service_fee_rate", serializer.errors)

    def test_rejects_negative_auto_approve_margin(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "auto_approve_max_margin_rate": "-1",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("auto_approve_max_margin_rate", serializer.errors)


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

    def test_meta_model_serializer_exposes_release_date(self):
        from llm_ops.serializers import MetaModelSerializer

        openai = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        meta = MetaModel.objects.create(
            name="GPT Test",
            code="gpt-test",
            vendor=openai,
            metadata={
                "models_dev": {
                    "release_date": "2024-07-18",
                    "last_updated": "2024-08-01",
                },
            },
        )

        data = MetaModelSerializer(meta).data

        self.assertEqual(data["release_date"], "2024-07-18")


class PriceCollectionSourceSerializerTests(TestCase):
    def test_official_catalog_with_third_party_model_is_supplier(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=deepseek,
        )
        source = PriceCollectionSource.objects.create(
            name="阿里云官方价格",
            slug="aliyun-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        LLMModel.objects.create(
            provider=aliyun,
            meta_model=meta_model,
            source=source,
            name="deepseek-r1",
            code="deepseek-r1",
        )

        data = PriceCollectionSourceSerializer(source).data

        self.assertEqual(data["source_category"], "official_provider")
        self.assertEqual(data["business_source_category"], "supplier")


class LLMModelSerializerTests(TestCase):
    def test_official_source_model_becomes_supplier_when_vendor_differs(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=deepseek,
        )
        source = PriceCollectionSource.objects.create(
            name="阿里云官方价格",
            slug="aliyun-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        model = LLMModel.objects.create(
            provider=aliyun,
            meta_model=meta_model,
            source=source,
            name="deepseek-r1",
            code="deepseek-r1",
        )

        data = LLMModelSerializer(model).data

        self.assertEqual(data["business_source_category"], "supplier")
        self.assertEqual(data["meta_model_vendor"], deepseek.id)
        self.assertEqual(data["meta_model_vendor_name"], "DeepSeek")
        self.assertEqual(data["meta_model_vendor_code"], "deepseek")


class ModelPriceItemSerializerTests(TestCase):
    def test_official_source_price_item_becomes_supplier(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            vendor=deepseek,
        )
        source = PriceCollectionSource.objects.create(
            name="阿里云官方价格",
            slug="aliyun-official",
            provider=aliyun,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        model = LLMModel.objects.create(
            provider=aliyun,
            meta_model=meta_model,
            source=source,
            name="deepseek-r1",
            code="deepseek-r1",
        )
        item = ModelPriceItem.objects.create(
            provider=aliyun,
            model=model,
            meta_model=meta_model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("0.55"),
            price_fingerprint="aliyun-deepseek-r1-input",
        )

        data = ModelPriceItemSerializer(item).data

        self.assertEqual(data["business_source_category"], "supplier")
        self.assertEqual(data["meta_model_vendor"], deepseek.id)
        self.assertEqual(data["meta_model_vendor_name"], "DeepSeek")
        self.assertEqual(data["meta_model_vendor_code"], "deepseek")

    def test_price_item_meta_model_follows_canonical_model(self):
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        aliyun = LLMProvider.objects.create(
            name="阿里云",
            code="aliyun",
        )
        model = LLMModel.objects.create(
            provider=deepseek,
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
            input_price_per_million=Decimal("4"),
            output_price_per_million=Decimal("16"),
        )
        wrong_meta = MetaModel.objects.create(
            name="阿里云 DeepSeek R1 250528",
            code="aliyun-deepseek-r1-250528",
            vendor=aliyun,
        )

        serializer = ModelPriceItemSerializer(
            data={
                "provider": deepseek.id,
                "model": model.id,
                "meta_model": wrong_meta.id,
                "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
                "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
                "currency": "USD",
                "unit_price": "0.550000",
                "price_fingerprint": "deepseek-r1-input",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        item = serializer.save()

        self.assertEqual(item.meta_model_id, model.meta_model_id)
        self.assertEqual(item.meta_model.code, "deepseek-r1")
        self.assertNotEqual(item.meta_model_id, wrong_meta.id)


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
        self.assertEqual(meta.code, "deepseek-r1")
        self.assertEqual(meta.name, "DeepSeek R1")
        self.assertIn("deepseek-r1-0528", meta.aliases)
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
        self.assertEqual(canonical.code, "deepseek-r1")
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
        self.assertEqual(canonical.code, "deepseek-r1")
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

    def test_mainstream_online_model_families_have_canonical_vendors(self):
        from llm_ops.constants import canonical_vendor_for_model_code

        cases = {
            "grok-4": "xai",
            "llama-3.3-70b-instruct": "meta",
            "mistral-large-latest": "mistral",
            "ernie-4.5-21b-a3b": "baidu",
            "glm-4.7": "zhipu",
            "hunyuan-t1": "tencent",
            "hy3-preview": "tencent",
            "baichuan-m2-32b": "baichuan",
            "yi-large": "01ai",
            "step-2-mini": "stepfun",
            "command-a": "cohere",
        }

        for model_code, vendor_code in cases.items():
            with self.subTest(model_code=model_code):
                spec = canonical_vendor_for_model_code(model_code)
                self.assertIsNotNone(spec)
                self.assertEqual(spec["code"], vendor_code)
