from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.baidu import extract_models


BAIDU_PRICING_HTML = """
<table>
  <tr>
    <th>模型名称</th><th>版本</th><th>服务</th><th>计费项</th>
    <th>在线价格</th><th>预留</th><th>预留</th><th>预留</th>
    <th>单位</th>
  </tr>
  <tr>
    <td>文本</td><td>ERNIE-4.5-21B-A3B</td><td>推理服务</td>
    <td>输入</td><td>0.001</td><td>-</td><td>-</td><td>-</td>
    <td>千Token</td>
  </tr>
  <tr>
    <td>文本</td><td>ERNIE-4.5-21B-A3B</td><td>推理服务</td>
    <td>输出</td><td>0.004</td><td>-</td><td>-</td><td>-</td>
    <td>千Token</td>
  </tr>
</table>
"""

BAIDU_CACHE_PRICING_HTML = """
<table>
  <tr>
    <th>模型名称</th><th>版本</th><th>服务</th><th>计费项</th>
    <th>在线价格</th><th>预留</th><th>预留</th><th>预留</th>
    <th>单位</th>
  </tr>
  <tr>
    <td>文本</td><td>ERNIE-4.5-Turbo-128K</td><td>推理服务</td>
    <td>0-128K输入</td><td>0.0008</td><td>-</td><td>-</td><td>-</td>
    <td>千Tokens</td>
  </tr>
  <tr>
    <td>文本</td><td>ERNIE-4.5-Turbo-128K</td><td>推理服务</td>
    <td>命中缓存输入</td><td>0.00008</td>
    <td>-</td><td>-</td><td>-</td><td>千Tokens</td>
  </tr>
  <tr>
    <td>文本</td><td>ERNIE-4.5-Turbo-128K</td><td>推理服务</td>
    <td>输出</td><td>0.0032</td><td>-</td><td>-</td><td>-</td>
    <td>千Tokens</td>
  </tr>
</table>
"""


class BaiduPriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_from_qianfan_pricing_table(self):
        models = extract_models(BAIDU_PRICING_HTML)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "ERNIE-4.5-21B-A3B")
        self.assertEqual(models[0]["input_price_per_million"], "1")
        self.assertEqual(models[0]["output_price_per_million"], "4")

    def test_extract_models_preserves_cache_hit_price(self):
        models = extract_models(BAIDU_CACHE_PRICING_HTML)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "ERNIE-4.5-Turbo-128K")
        self.assertEqual(models[0]["input_price_per_million"], "0.8")
        self.assertEqual(models[0]["output_price_per_million"], "3.2")
        self.assertEqual(models[0]["cache_hit_price_per_million"], "0.08")

    def test_collect_vendor_price_catalog_returns_baidu_payload(self):
        payload = collect_vendor_price_catalog(
            "baidu",
            {
                "provider_name": "百度千帆",
                "currency": "CNY",
                "raw_html": BAIDU_PRICING_HTML,
                "model_codes": ["ERNIE-4.5-21B-A3B"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "baidu")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "ERNIE-4.5-21B-A3B")
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["input_price"],
            "1",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["output_price"],
            "4",
        )
