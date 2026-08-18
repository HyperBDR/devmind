import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from llm_ops.collection_services import (
    sync_model_price_items,
    upsert_collected_offering,
)
from llm_ops.models import (
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    PriceCollectionSource,
)
from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.zhipu import extract_models
from llm_ops.skill_runner import standard_catalog_to_collected_catalog


ZHIPU_PRICING_JSON = json.dumps(
    {
        "modelPrices": [
            {
                "modelCode": "GLM-4.7",
                "inputPrice": "0.5",
                "outputPrice": "2",
            },
            {
                "modelName": "GLM-4.7-Flash",
                "promptUnitPrice": "¥0.0001 / 千tokens",
                "completionUnitPrice": "¥0.0004 / 千tokens",
            },
        ]
    }
)

ZHIPU_PRICING_TABLE = """
<table>
  <tr>
    <th>模型名称</th>
    <th>输入价格</th>
    <th>输出价格</th>
  </tr>
  <tr>
    <td>GLM-4.7</td>
    <td>¥0.5 / 百万 tokens</td>
    <td>¥2 / 百万 tokens</td>
  </tr>
</table>
"""

ZHIPU_SHELL_HTML = """
<!DOCTYPE html>
<html>
  <head><title>智谱AI开放平台</title></head>
  <body>
    <noscript>
      We're sorry but 智谱AI开放平台 doesn't work properly without
      JavaScript enabled.
    </noscript>
    <div id="app"></div>
    <script src="/js/app.4b35422d.js"></script>
  </body>
</html>
"""

ZHIPU_BUNDLE_MODEL_LIST = """
newModel:{model:[{
  modelName:"文本模型",
  unit2:"百万tokens",
  modelList:[
    {
      name:"GLM-5.1",
      rowspan:2,
      upDownText:["输入长度 [0, 32)"],
      inPrice:["6元"],
      outPrice:["24元"],
      hit:["1.3元"]
    },
    {
      name:"",
      upDownText:["输入长度 [32+)"],
      inPrice:["8元"],
      outPrice:["28元"],
      hit:["2元"]
    },
    {
      name:"GLM-4.7",
      rowspan:3,
      upDownText:["输入长度 [0, 32)", "输出长度 [0, 0.2)"],
      inPrice:["2元"],
      outPrice:["8元"]
    },
    {
      name:"",
      upDownText:["输入长度 [0, 32)", "输出长度 [0.2+)"],
      inPrice:["3元"],
      outPrice:["14元"]
    },
    {
      name:"",
      upDownText:["输入长度 [32, 200)"],
      inPrice:["4元"],
      outPrice:["16元"]
    },
    {
      name:"GLM-4.7-Flash",
      upDownText:["200K"],
      inPrice:["免费"],
      outPrice:["免费"]
    }
  ]
}]}
"""

ZHIPU_CDN_SCRIPT_URL = (
    "https://static.bigmodel.cn/"
    "wd-paas-front/js/app.a4a9eb95.js"
)

ZHIPU_CDN_SHELL_HTML = f"""
<!DOCTYPE html>
<html>
  <body>
    <div id="app"></div>
    <script src="{ZHIPU_CDN_SCRIPT_URL}"></script>
  </body>
</html>
"""


class ZhipuPriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_from_structured_pricing_json(self):
        models = extract_models(ZHIPU_PRICING_JSON)

        model_ids = {item["model_id"] for item in models}
        self.assertEqual(model_ids, {"glm-4.7", "glm-4.7-flash"})
        glm = next(item for item in models if item["model_id"] == "glm-4.7")
        flash = next(
            item for item in models if item["model_id"] == "glm-4.7-flash"
        )
        self.assertEqual(glm["input_price_per_million"], "0.5")
        self.assertEqual(glm["output_price_per_million"], "2")
        self.assertEqual(flash["input_price_per_million"], "0.1")
        self.assertEqual(flash["output_price_per_million"], "0.4")

    def test_extract_models_from_plain_html_pricing_table(self):
        models = extract_models(ZHIPU_PRICING_TABLE)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "glm-4.7")
        self.assertEqual(models[0]["input_price_per_million"], "0.5")
        self.assertEqual(models[0]["output_price_per_million"], "2")

    def test_extract_models_from_bigmodel_bundle_model_list(self):
        models = extract_models(ZHIPU_BUNDLE_MODEL_LIST)

        self.assertEqual(
            [model["model_id"] for model in models],
            ["glm-4.7", "glm-5.1"],
        )
        glm_51 = next(
            model for model in models if model["model_id"] == "glm-5.1"
        )
        self.assertEqual(
            glm_51["price_rows"],
            [
                {
                    "input_price_per_million": "6",
                    "output_price_per_million": "24",
                    "cache_hit_price_per_million": "1.3",
                    "input_token_range": "0-32000",
                },
                {
                    "input_price_per_million": "8",
                    "output_price_per_million": "28",
                    "cache_hit_price_per_million": "2",
                    "input_token_range": "32000+",
                },
            ],
        )
        glm_47 = next(
            model for model in models if model["model_id"] == "glm-4.7"
        )
        self.assertEqual(
            glm_47["price_rows"],
            [
                {
                    "input_price_per_million": "2",
                    "output_price_per_million": "8",
                    "input_token_range": "0-32000",
                    "output_token_range": "0-200",
                    "usage_condition_mode": "multi_metric",
                },
                {
                    "input_price_per_million": "3",
                    "output_price_per_million": "14",
                    "input_token_range": "0-32000",
                    "output_token_range": "200+",
                    "usage_condition_mode": "multi_metric",
                },
                {
                    "input_price_per_million": "4",
                    "output_price_per_million": "16",
                    "input_token_range": "32000-200000",
                    "usage_condition_mode": "multi_metric",
                },
            ],
        )

    def test_catalog_preserves_bigmodel_usage_conditions(self):
        payload = collect_vendor_price_catalog(
            "zhipu",
            {
                "raw_html": ZHIPU_BUNDLE_MODEL_LIST,
                "provider_name": "智谱",
                "model_codes": ["glm-4.7"],
            },
        )

        rows = payload["models"][0]["price_rows"]

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0]["values"],
            {
                "input_price": "2",
                "output_price": "8",
                "input_token_range": "0-32000",
                "output_token_range": "0-200",
                "usage_condition_mode": "multi_metric",
            },
        )

    def test_js_shell_without_model_prices_returns_empty_catalog(self):
        payload = collect_vendor_price_catalog(
            "zhipu",
            {
                "raw_html": ZHIPU_SHELL_HTML,
                "source_url": "https://example.com/bigmodel-pricing",
            },
        )

        self.assertEqual(payload["provider"]["code"], "zhipu")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 0)
        self.assertEqual(payload["models"], [])

    @patch("llm_ops.price_collectors.parsers.zhipu.requests.get")
    def test_collects_models_from_trusted_bigmodel_cdn_bundle(
        self,
        mocked_get,
    ):
        page_response = Mock()
        page_response.text = ZHIPU_CDN_SHELL_HTML
        page_response.encoding = "utf-8"
        bundle_response = Mock()
        bundle_response.text = ZHIPU_BUNDLE_MODEL_LIST
        bundle_response.encoding = "utf-8"
        mocked_get.side_effect = [page_response, bundle_response]

        payload = collect_vendor_price_catalog(
            "zhipu",
            {"source_url": "https://bigmodel.cn/pricing"},
        )

        self.assertEqual(payload["total_models"], 2)
        self.assertEqual(payload["models"][0]["model_id"], "glm-4.7")
        requested_urls = [call.args[0] for call in mocked_get.call_args_list]
        self.assertEqual(
            requested_urls,
            [
                "https://bigmodel.cn/pricing",
                ZHIPU_CDN_SCRIPT_URL,
            ],
        )

    def test_collect_vendor_price_catalog_returns_zhipu_payload(self):
        payload = collect_vendor_price_catalog(
            "zhipu",
            {
                "raw_html": ZHIPU_PRICING_TABLE,
                "source_url": "https://example.com/bigmodel-pricing",
                "provider_name": "智谱",
                "model_codes": ["glm-4.7"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "zhipu")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "glm-4.7")


class ZhipuPriceCatalogPersistenceTests(TestCase):
    def test_glm_conditions_persist_idempotently_with_source_evidence(self):
        provider = LLMProvider.objects.create(name="智谱", code="zhipu")
        source = PriceCollectionSource.objects.create(
            name="智谱官方",
            slug="zhipu-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://bigmodel.cn/pricing",
            currency="CNY",
            is_enabled=True,
            updates_model_prices=True,
        )
        meta_model = MetaModel.objects.create(
            code="glm-4.7",
            name="GLM-4.7",
            owner_code="zhipu",
            owner_name="智谱",
        )
        payload = collect_vendor_price_catalog(
            "zhipu",
            {
                "raw_html": ZHIPU_BUNDLE_MODEL_LIST,
                "source_url": source.endpoint_url,
                "provider_name": provider.name,
                "model_codes": [meta_model.code],
            },
        )
        item = standard_catalog_to_collected_catalog(payload).models[0]
        offering, _ = upsert_collected_offering(
            item,
            source=source,
            source_url=source.endpoint_url,
            meta_model=meta_model,
        )

        first_items = sync_model_price_items(
            item,
            source=source,
            offering=offering,
            source_url=source.endpoint_url,
        )
        second_items = sync_model_price_items(
            item,
            source=source,
            offering=offering,
            source_url=source.endpoint_url,
        )

        input_items = [
            price_item
            for price_item in first_items
            if price_item.dimension == ModelPriceItem.DIMENSION_TEXT_INPUT
        ]
        output_items = [
            price_item
            for price_item in first_items
            if price_item.dimension == ModelPriceItem.DIMENSION_TEXT_OUTPUT
        ]
        self.assertEqual(len(input_items), 3)
        self.assertEqual(len(output_items), 3)
        self.assertEqual(
            {price_item.id for price_item in first_items},
            {price_item.id for price_item in second_items},
        )
        first_rule = next(
            price_item
            for price_item in input_items
            if price_item.unit_price == Decimal("2")
        )
        self.assertEqual(
            first_rule.spec["usage_conditions"],
            {
                "input_tokens": {"start": "0", "end": "32000"},
                "output_tokens": {"start": "0", "end": "200"},
            },
        )
        self.assertEqual(
            first_rule.raw_payload["values"]["input_token_range"],
            "0-32000",
        )
        self.assertEqual(first_rule.currency, "CNY")
