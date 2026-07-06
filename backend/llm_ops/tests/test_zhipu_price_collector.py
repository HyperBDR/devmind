import json

from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.zhipu import extract_models


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
      name:"GLM-5.2",
      upDownText:["1M"],
      inPrice:["8元"],
      outPrice:["28元"],
      hit:["2元"]
    },
    {
      name:"",
      upDownText:["输入长度 [32+)"],
      inPrice:["8元"],
      outPrice:["28元"]
    }
  ]
}]}
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

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "glm-5.2")
        self.assertEqual(models[0]["input_price_per_million"], "8")
        self.assertEqual(models[0]["output_price_per_million"], "28")

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
