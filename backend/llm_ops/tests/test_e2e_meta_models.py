"""End-to-end check: the meta-models serializer stays correct.

We avoid HTTP dispatching (which depends on a configured auth stack)
and exercise the serializer + view queryset directly. This still
verifies the data contract: every meta model returned to the UI is
attributed to the company that built it.
"""
from django.test import TestCase

from llm_ops.models import LLMProvider, MetaModel
from llm_ops.serializers import MetaModelSerializer
from llm_ops.views import MetaModelViewSet


class LLMOpsMetaModelsApiTests(TestCase):
    """The /v1/llm-ops/meta-models/ endpoint stays correct end-to-end."""

    def setUp(self):
        aliyun = LLMProvider.objects.create(name="阿里云", code="aliyun")
        deepseek = LLMProvider.objects.create(
            name="DeepSeek",
            code="deepseek",
        )
        siliconflow = LLMProvider.objects.create(
            name="硅基流动",
            code="siliconflow",
        )
        MetaModel.objects.create(
            name="Qwen Plus",
            code="qwen-plus",
            vendor=aliyun,
        )
        MetaModel.objects.create(
            name="DeepSeek V3",
            code="deepseek-v3",
            vendor=deepseek,
        )
        MetaModel.objects.create(
            name="Legacy SiliconFlow Model",
            code="legacy-siliconflow-model",
            vendor=siliconflow,
        )

    def _serialize(self, queryset):
        return list(MetaModelSerializer(queryset, many=True).data)

    def test_full_listing_has_no_wrong_attribution(self):
        view = MetaModelViewSet()
        view.action = "list"
        view.kwargs = {}
        view.request = type("R", (), {"query_params": {}})()
        queryset = view.get_queryset()
        rows = self._serialize(queryset)
        leaked = [
            r for r in rows
            if r["code"].startswith("deepseek")
            and r["effective_vendor_code"] != "deepseek"
        ]
        self.assertEqual(leaked, [])
        # No meta model is allowed to have a supplier alias as vendor.
        alias_codes = {"siliconflow"}
        for row in rows:
            self.assertNotIn(row["effective_vendor_code"], alias_codes)
        # No meta model is allowed to lack a vendor.
        unbound = [r for r in rows if not r["effective_vendor"]]
        self.assertEqual(unbound, [])

    def test_filter_by_aliyun_does_not_leak_deepseek(self):
        view = MetaModelViewSet()
        view.action = "list"
        aliyun = LLMProvider.objects.get(code="aliyun")
        view.kwargs = {}
        view.request = type("R", (), {
            "query_params": {"vendor": str(aliyun.id)},
        })()
        rows = self._serialize(view.get_queryset())
        leaked = [r for r in rows if r["code"].startswith("deepseek")]
        self.assertEqual(leaked, [])

    def test_filter_by_deepseek_returns_only_deepseek(self):
        view = MetaModelViewSet()
        view.action = "list"
        deepseek = LLMProvider.objects.get(code="deepseek")
        view.kwargs = {}
        view.request = type("R", (), {
            "query_params": {"vendor": str(deepseek.id)},
        })()
        rows = self._serialize(view.get_queryset())
        for row in rows:
            self.assertTrue(
                row["code"].startswith("deepseek"),
                f"non-deepseek code in deepseek filter: {row['code']}",
            )
            self.assertEqual(row["effective_vendor_code"], "deepseek")

    def test_unbound_meta_models_do_not_exist(self):
        orphans = MetaModel.objects.filter(vendor__isnull=True)
        self.assertEqual(orphans.count(), 0)
