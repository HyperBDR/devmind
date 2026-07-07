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
            owner_code="alibaba",
            owner_name="阿里巴巴",
            owner_website="https://www.alibaba.com/",
        )
        MetaModel.objects.create(
            name="DeepSeek V3",
            code="deepseek-v3",
            owner_code=deepseek.code,
            owner_name=deepseek.name,
            owner_website=deepseek.website,
        )
        MetaModel.objects.create(
            name="Legacy SiliconFlow Model",
            code="legacy-siliconflow-model",
            owner_code=siliconflow.code,
            owner_name=siliconflow.name,
            owner_website=siliconflow.website,
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
            and r["owner_code"] != "deepseek"
        ]
        self.assertEqual(leaked, [])
        # No meta model is allowed to have a supplier alias as owner.
        alias_codes = {"siliconflow"}
        for row in rows:
            self.assertNotIn(row["owner_code"], alias_codes)
        # No meta model is allowed to lack an owner.
        unbound = [r for r in rows if not r["owner_code"]]
        self.assertEqual(unbound, [])

    def test_filter_by_alibaba_does_not_leak_deepseek(self):
        view = MetaModelViewSet()
        view.action = "list"
        view.kwargs = {}
        view.request = type("R", (), {
            "query_params": {"owner": "alibaba"},
        })()
        rows = self._serialize(view.get_queryset())
        leaked = [r for r in rows if r["code"].startswith("deepseek")]
        self.assertEqual(leaked, [])

    def test_filter_by_deepseek_returns_only_deepseek(self):
        view = MetaModelViewSet()
        view.action = "list"
        view.kwargs = {}
        view.request = type("R", (), {
            "query_params": {"owner": "deepseek"},
        })()
        rows = self._serialize(view.get_queryset())
        for row in rows:
            self.assertTrue(
                row["code"].startswith("deepseek"),
                f"non-deepseek code in deepseek filter: {row['code']}",
            )
            self.assertEqual(row["owner_code"], "deepseek")

    def test_unbound_meta_models_do_not_exist(self):
        orphans = MetaModel.objects.filter(owner_code="")
        self.assertEqual(orphans.count(), 0)
