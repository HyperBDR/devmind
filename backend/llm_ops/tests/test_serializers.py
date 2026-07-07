from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from llm_ops.models import (
    LLMModel,
    LLMOpsGlobalConfig,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    ModelSku,
    PriceCollectionRun,
    PriceCollectionSource,
    ProcurementChannel,
    ResalePlatform,
    SourceSkuOffering,
)
from llm_ops.serializers import (
    LLMModelSerializer,
    LLMOpsGlobalConfigSerializer,
    ManualPriceImportRequestSerializer,
    ModelPriceItemSerializer,
    PriceCollectionSourceSerializer,
    ProcurementChannelSerializer,
    ResalePlatformSerializer,
    UsageReconciliationRecordSerializer,
)


class LLMOpsGlobalConfigSerializerTests(TestCase):
    @patch("llm_ops.models.encryption_service.decrypt")
    def test_plaintext_secret_falls_back_without_decrypt(self, mock_decrypt):
        mock_decrypt.side_effect = AssertionError(
            "Plaintext values should not be decrypted."
        )
        config = LLMOpsGlobalConfig.get_solo()
        LLMOpsGlobalConfig.objects.filter(pk=config.pk).update(
            feishu_app_secret="legacy-plaintext-secret"
        )

        config.refresh_from_db()

        self.assertEqual(
            config.get_feishu_app_secret(),
            "legacy-plaintext-secret",
        )

    def test_blank_secret_clears_existing_secret(self):
        config = LLMOpsGlobalConfig.get_solo()
        config.set_feishu_app_secret("existing-secret")
        config.save()

        serializer = LLMOpsGlobalConfigSerializer(
            config,
            data={"feishu_app_secret": ""},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.feishu_app_secret, "")
        self.assertEqual(updated.get_feishu_app_secret(), "")


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

    def test_accepts_point_decimal_places(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "point_decimal_places": 2,
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

    def test_rejects_point_rate_with_too_many_decimal_places(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100.123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("points_per_currency_unit", serializer.errors)

    def test_rejects_too_many_point_decimal_places(self):
        serializer = ResalePlatformSerializer(
            data={
                "name": "Agione Test",
                "code": "agione-test",
                "currency": "CNY",
                "points_per_currency_unit": "100",
                "point_decimal_places": 7,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("point_decimal_places", serializer.errors)

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

    def test_meta_model_serializer_exposes_owner_fields(self):
        """The serializer reports plain owner fields."""
        from llm_ops.models import LLMProvider, MetaModel
        from llm_ops.serializers import MetaModelSerializer
        aliyun = LLMProvider.objects.create(
            name="阿里云",
            code="aliyun",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1 0528",
            code="deepseek-r1-0528",
            owner_code=aliyun.code,
            owner_name=aliyun.name,
            owner_website=aliyun.website,
        )
        data = MetaModelSerializer(meta_model).data
        self.assertEqual(data["owner_code"], "deepseek")
        self.assertEqual(data["owner_name"], "DeepSeek")

    def test_meta_model_serializer_exposes_release_date(self):
        from llm_ops.serializers import MetaModelSerializer

        openai = LLMProvider.objects.create(
            name="OpenAI",
            code="openai",
        )
        meta = MetaModel.objects.create(
            name="GPT Test",
            code="gpt-test",
            owner_code=openai.code,
            owner_name=openai.name,
            owner_website=openai.website,
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
    def test_create_generates_unique_slug_when_requested_slug_exists(self):
        PriceCollectionSource.objects.create(
            name="已有价格源",
            slug="price-source",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
        )
        serializer = PriceCollectionSourceSerializer(
            data={
                "name": "测试价格源",
                "slug": "price-source",
                "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_MANUAL
                ),
                "currency": "CNY",
                "is_enabled": True,
                "updates_model_prices": False,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        source = serializer.save()
        self.assertEqual(source.slug, "price-source-2")

    def test_create_maps_owner_type_and_keeps_slug_unique(self):
        PriceCollectionSource.objects.create(
            name="Existing Supplier",
            slug="supplier-api",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        serializer = PriceCollectionSourceSerializer(
            data={
                "name": "Supplier API",
                "slug": "supplier-api",
                "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                "source_owner_type": (
                    PriceCollectionSource.SOURCE_OWNER_SUPPLIER
                ),
                "currency": "USD",
                "is_enabled": True,
                "updates_model_prices": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        source = serializer.save()
        self.assertEqual(
            source.source_category,
            PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
        )
        self.assertEqual(source.slug, "supplier-api-2")

    def test_manual_import_method_defaults_owner_type(self):
        serializer = PriceCollectionSourceSerializer(
            data={
                "name": "Manual Import",
                "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_MANUAL
                ),
                "collection_method": (
                    PriceCollectionSource.COLLECTION_METHOD_MANUAL_IMPORT
                ),
                "currency": "CNY",
                "is_enabled": True,
                "updates_model_prices": False,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        source = serializer.save()
        self.assertEqual(
            source.source_owner_type,
            PriceCollectionSource.SOURCE_OWNER_INTERNAL,
        )

    def test_create_generates_slug_for_chinese_name(self):
        serializer = PriceCollectionSourceSerializer(
            data={
                "name": "人工录入价格源",
                "source_type": PriceCollectionSource.SOURCE_TYPE_CUSTOM,
                "source_category": (
                    PriceCollectionSource.SOURCE_CATEGORY_MANUAL
                ),
                "currency": "CNY",
                "is_enabled": True,
                "updates_model_prices": False,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        source = serializer.save()
        self.assertEqual(source.slug, "manual-source")

    def test_partial_update_without_slug_preserves_existing_slug(self):
        source = PriceCollectionSource.objects.create(
            name="已有价格源",
            slug="price-source",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
        )
        serializer = PriceCollectionSourceSerializer(
            source,
            data={"name": "改名价格源"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.slug, "price-source")

    def test_official_catalog_with_third_party_model_is_cloud_provider(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
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
        self.assertEqual(data["source_owner_type"], "cloud_provider_official")
        self.assertEqual(data["collection_method"], "unknown")
        self.assertEqual(data["business_source_category"], "cloud_hosted")

    def test_source_representation_includes_stable_summary_fields(self):
        provider = LLMProvider.objects.create(name="DeepSeek", code="deepseek")
        source = PriceCollectionSource.objects.create(
            name="DeepSeek Official",
            slug="deepseek-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://api-docs.deepseek.com/quick_start/pricing",
            updates_model_prices=True,
        )
        model = LLMModel.objects.create(
            provider=provider,
            source=source,
            name="DeepSeek Chat",
            code="deepseek-chat",
        )
        ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            meta_model=model.meta_model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="CNY",
            unit_price=Decimal("0.150000"),
            price_fingerprint="deepseek-input",
        )
        PriceCollectionRun.objects.create(
            source=source,
            status=PriceCollectionRun.STATUS_SUCCEEDED,
        )

        data = PriceCollectionSourceSerializer(source).data

        self.assertEqual(data["model_count"], 1)
        self.assertEqual(data["price_item_count"], 1)
        self.assertEqual(data["latest_run_status"], "succeeded")
        self.assertTrue(data["capabilities"]["can_collect_prices"])
        self.assertTrue(data["capabilities"]["updates_model_prices"])

    def test_supplier_collector_representation_infers_auto_collect(self):
        source = PriceCollectionSource.objects.create(
            name="SiliconFlow Pricing",
            slug="siliconflow-pricing",
            source_category=PriceCollectionSource.SOURCE_CATEGORY_SUPPLIER,
            source_owner_type=PriceCollectionSource.SOURCE_OWNER_SUPPLIER,
            collection_method=PriceCollectionSource.COLLECTION_METHOD_UNKNOWN,
            endpoint_url="https://siliconflow.cn/pricing",
            currency="CNY",
            updates_model_prices=True,
        )

        data = PriceCollectionSourceSerializer(source).data

        self.assertEqual(data["source_category"], "supplier")
        self.assertEqual(data["collection_method"], "auto_collect")
        self.assertTrue(data["capabilities"]["can_collect_prices"])


class LLMModelSerializerTests(TestCase):
    def test_official_source_model_becomes_cloud_hosted_when_vendor_differs(
        self,
    ):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
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

        self.assertEqual(data["business_source_category"], "cloud_hosted")
        self.assertEqual(data["price_role"], "cloud_hosted")
        self.assertEqual(data["meta_model_owner_name"], "DeepSeek")
        self.assertEqual(data["meta_model_owner_code"], "deepseek")


class ManualPriceImportRequestSerializerTests(TestCase):
    def test_accepts_model_provider_different_from_source_provider(self):
        source_provider = LLMProvider.objects.create(
            name="Alibaba Cloud",
            code="aliyun",
        )
        model_provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        source = PriceCollectionSource.objects.create(
            name="Aliyun Manual Sheet",
            slug="aliyun-manual-sheet",
            provider=source_provider,
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            currency="CNY",
        )

        serializer = ManualPriceImportRequestSerializer(
            data={
                "source": source.id,
                "provider": model_provider.id,
                "rows": [
                    {
                        "model_code": "deepseek-r1",
                        "model_name": "DeepSeek R1",
                        "input_price_per_million": "4.000000",
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["provider"],
            model_provider,
        )
        self.assertFalse(serializer.validated_data["updates_model_prices"])

    def test_accepts_existing_source_without_bound_provider(self):
        source = PriceCollectionSource.objects.create(
            name="Agione Manual Sheet",
            slug="agione-manual-sheet",
            source_type=PriceCollectionSource.SOURCE_TYPE_CUSTOM,
            source_category=PriceCollectionSource.SOURCE_CATEGORY_MANUAL,
            currency="CNY",
        )

        serializer = ManualPriceImportRequestSerializer(
            data={
                "source": source.id,
                "rows": [
                    {
                        "model_code": "deepseek-r1",
                        "model_name": "DeepSeek R1",
                        "provider_code": "deepseek",
                        "input_price_per_million": "4.000000",
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("provider"))
        self.assertFalse(serializer.validated_data["updates_model_prices"])

    def test_new_manual_source_import_never_promotes_model_prices(self):
        provider = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )

        serializer = ManualPriceImportRequestSerializer(
            data={
                "provider": provider.id,
                "source_name": "Manual Sheet",
                "source_slug": "manual-sheet",
                "currency": "CNY",
                "updates_model_prices": True,
                "rows": [
                    {
                        "model_code": "deepseek-r1",
                        "model_name": "DeepSeek R1",
                        "input_price_per_million": "4.000000",
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["updates_model_prices"])

    def test_manual_import_never_promotes_prices(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="OpenAI Official",
            slug="openai-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            updates_model_prices=True,
        )

        serializer = ManualPriceImportRequestSerializer(
            data={
                "source": source.id,
                "provider": provider.id,
                "currency": "USD",
                "updates_model_prices": True,
                "rows": [
                    {
                        "model_code": "gpt-4o-mini",
                        "model_name": "GPT-4o mini",
                        "input_price_per_million": "0.150000",
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["updates_model_prices"])


class ModelPriceItemSerializerTests(TestCase):
    def test_official_source_price_item_becomes_cloud_hosted(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        meta_model = MetaModel.objects.create(
            name="DeepSeek R1",
            code="deepseek-r1",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
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

        self.assertEqual(data["business_source_category"], "cloud_hosted")
        self.assertEqual(data["price_role"], "cloud_hosted")
        self.assertEqual(data["meta_model_owner_name"], "DeepSeek")
        self.assertEqual(data["meta_model_owner_code"], "deepseek")
        self.assertTrue(data["source_is_enabled"])

    def test_price_item_serializes_disabled_source_state(self):
        provider = LLMProvider.objects.create(name="OpenAI", code="openai")
        source = PriceCollectionSource.objects.create(
            name="Inactive Source",
            slug="inactive-source",
            provider=provider,
            is_enabled=False,
        )
        model = LLMModel.objects.create(
            provider=provider,
            name="GPT-4o",
            code="gpt-4o",
        )
        item = ModelPriceItem.objects.create(
            provider=provider,
            model=model,
            meta_model=model.meta_model,
            source=source,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal("2.5"),
            price_fingerprint="inactive-source-input",
        )

        data = ModelPriceItemSerializer(item).data

        self.assertFalse(data["source_is_enabled"])

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
        source = PriceCollectionSource.objects.create(
            name="DeepSeek Official",
            slug="deepseek-official",
            provider=deepseek,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
        )
        sku = ModelSku.objects.create(
            meta_model=model.meta_model,
            provider=deepseek,
            canonical_sku_code=model.code,
            upstream_model_name=model.code,
            display_name=model.name,
            variant_type=ModelSku.VARIANT_OFFICIAL,
        )
        offering = SourceSkuOffering.objects.create(
            source=source,
            sku=sku,
            provider=deepseek,
            exposed_model_name=model.code,
        )
        wrong_meta = MetaModel.objects.create(
            name="阿里云 DeepSeek R1 250528",
            code="aliyun-deepseek-r1-250528",
            owner_code=aliyun.code,
            owner_name=aliyun.name,
            owner_website=aliyun.website,
        )

        serializer = ModelPriceItemSerializer(
            data={
                "provider": deepseek.id,
                "model": model.id,
                "sku": sku.id,
                "offering": offering.id,
                "source": source.id,
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
        self.assertEqual(
            MetaModel.objects.filter(owner_code=self.deepseek.code).count(),
            1,
        )

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
            MetaModel.objects.filter(owner_code=self.deepseek.code).count(),
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

    def test_mainstream_online_model_families_have_canonical_owners(self):
        from llm_ops.constants import canonical_owner_for_model_code

        cases = {
            "qwen-plus": "alibaba",
            "qwq-plus": "alibaba",
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

        for model_code, owner_code in cases.items():
            with self.subTest(model_code=model_code):
                spec = canonical_owner_for_model_code(model_code)
                self.assertIsNotNone(spec)
                self.assertEqual(spec["code"], owner_code)
