from django.test import SimpleTestCase

from llm_ops.skill_runner import (
    MODEL_PRICE_CATALOG_SCHEMA_VERSION,
    run_vendor_pricing_skill,
    standard_catalog_to_collected_catalog,
)


VOLCENGINE_HTML = (
    r'\"ops\":[{\"insert\":\"doubao-1.5-pro-32k\"}],'
    r'\"zoneId\":\"row01nj2n42rlpl8e7b6tvpmvqhysnzfp89bh\",'
    r'\"zoneType\":\"Z\"'
    r'\"ops\":[{\"insert\":\"2\"}],'
    r'\"zoneId\":\"row01s303uu1c1g40de7oaoizn05md89iimb6\",'
    r'\"zoneType\":\"Z\"'
    r'\"ops\":[{\"insert\":\"8\"}],'
    r'\"zoneId\":\"row015wt3pecycob8so1pho26k692zw2cgbsm\",'
    r'\"zoneType\":\"Z\"'
    r'\"ops\":[{\"insert\":\"0.4\"}],'
    r'\"zoneId\":\"row01cvklbb5m01p5jfrmdhooit6bknkyawsj\",'
    r'\"zoneType\":\"Z\"'
    r'\"ops\":[{\"insert\":\"标准推理\"}],'
    r'\"zoneId\":\"row01gagtwd6h2ui45oj1di8jtwno5ytnfdt6\",'
    r'\"zoneType\":\"Z\"'
)


BAIDU_HTML = """
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

ALIYUN_HTML = """
<table>
  <tr>
    <th>模型 ID（Model ID）</th><th>服务部署范围</th>
    <th>输入单价（每百万 Token）</th><th>输出单价（每百万 Token）</th>
    <th>免费额度</th>
  </tr>
  <tr>
    <td><p>qwen-new-2026</p><blockquote>上下文缓存享有折扣</blockquote></td>
    <td>中国内地</td><td>3.5 元</td><td>7 元</td><td>-</td>
  </tr>
</table>
"""


class ModelPriceSkillRunnerTests(SimpleTestCase):
    def test_aliyun_vendor_skill_returns_standard_catalog_json(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "source_url": (
                    "https://help.aliyun.com/zh/model-studio/model-pricing"
                ),
                "model_codes": ["deepseek-v4-pro"],
                "verify_source": False,
            },
        )

        self.assertEqual(
            payload["schema_version"],
            MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        )
        self.assertEqual(payload["source_type"], "vendor_python_skill")
        self.assertEqual(payload["provider"]["code"], "aliyun")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "deepseek-v4-pro")
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["input_price"],
            "12",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["output_price"],
            "24",
        )

    def test_standard_catalog_converts_to_collected_catalog(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "model_codes": ["deepseek-v4-flash"],
                "verify_source": False,
            },
        )

        catalog = standard_catalog_to_collected_catalog(payload)

        self.assertEqual(catalog.total_models, 1)
        self.assertEqual(catalog.models[0].model_id, "deepseek-v4-flash")
        self.assertEqual(catalog.models[0].currency, "CNY")
        self.assertEqual(
            catalog.models[0].price_rows[0].values["input_price"],
            "1",
        )

    def test_aliyun_vendor_skill_extracts_unconfigured_page_rows(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_HTML,
            },
        )

        self.assertEqual(payload["provider"]["code"], "aliyun")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "qwen-new-2026")
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["input_price"],
            "3.5",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["output_price"],
            "7",
        )

    def test_volcengine_vendor_skill_returns_standard_catalog_json(self):
        payload = run_vendor_pricing_skill(
            "volcengine",
            {
                "provider_name": "火山方舟",
                "currency": "CNY",
                "raw_html": VOLCENGINE_HTML,
            },
        )

        self.assertEqual(
            payload["schema_version"],
            MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        )
        self.assertEqual(payload["provider"]["code"], "volcengine")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(
            payload["models"][0]["model_id"],
            "doubao-1.5-pro-32k",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["input_price"],
            "2",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["output_price"],
            "8",
        )

    def test_baidu_vendor_skill_returns_standard_catalog_json(self):
        payload = run_vendor_pricing_skill(
            "baidu",
            {
                "provider_name": "百度千帆",
                "currency": "CNY",
                "raw_html": BAIDU_HTML,
            },
        )

        self.assertEqual(
            payload["schema_version"],
            MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        )
        self.assertEqual(payload["provider"]["code"], "baidu")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["models"][0]["model_id"], "ERNIE-4.5-21B-A3B")
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["input_price"],
            "1",
        )
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"]["output_price"],
            "4",
        )
