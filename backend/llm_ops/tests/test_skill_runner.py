import json

from django.test import SimpleTestCase

from llm_ops.price_collectors import (
    collect_vendor_price_catalog,
    vendor_price_collector_exists,
)
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

DEEPSEEK_HTML = """
<table style="text-align:center">
  <tr>
    <td colspan="2">模型</td>
    <td>deepseek-v4-flash<sup>(1)</sup></td>
    <td>deepseek-v4-pro</td>
  </tr>
  <tr><td colspan="2">上下文长度</td><td colspan="2">1M</td></tr>
  <tr>
    <td rowspan="3">价格</td>
    <td>百万tokens输入（缓存命中）</td>
    <td>0.02元</td>
    <td>0.025元</td>
  </tr>
  <tr>
    <td>百万tokens输入（缓存未命中）</td>
    <td>1元</td>
    <td>3元</td>
  </tr>
  <tr>
    <td>百万tokens输出</td>
    <td>2元</td>
    <td>6元</td>
  </tr>
</table>
"""

ALIYUN_HTML = """
<table>
  <tr>
    <th>模型 ID（Model ID）</th><th>服务部署范围</th>
    <th>输入单价（每百万 Token）</th>
    <th>输出单价（每百万 Token）</th>
    <th>免费额度</th>
  </tr>
  <tr>
    <td>
      <p>qwen-new-2026</p>
      <blockquote>上下文缓存享有折扣</blockquote>
    </td>
    <td>中国内地</td><td>3.5 元</td><td>7 元</td><td>-</td>
  </tr>
</table>
"""

ALIYUN_MULTI_MARKET_HTML = """
<table>
  <tr>
    <th>模型 ID</th><th>服务部署范围</th><th>输入单价</th>
    <th>输出单价</th>
  </tr>
  <tr>
    <td>qwen-plus</td><td>中国内地</td><td>0.8 元</td><td>2 元</td>
  </tr>
  <tr>
    <td>qwen-plus</td><td>国际</td><td>USD 0.12</td><td>USD 0.30</td>
  </tr>
</table>
"""

ALIYUN_QWEN37_HTML = """
<table>
  <tr>
    <th>模型 ID（Model ID）</th><th>服务部署范围</th><th>模式</th>
    <th>单次请求的输入 Token 数</th>
    <th>输入单价（每百万 Token）</th>
    <th>输出单价（每百万 Token）</th><th>免费额度</th>
  </tr>
  <tr>
    <td>
      <p>qwen3.7-max</p>
      <blockquote>当前能力等同于 qwen3.7-max-2026-05-20</blockquote>
    </td>
    <td>中国内地</td><td>非思考和思考模式</td>
    <td>0&lt;Token≤1M</td><td>12 元</td><td>36 元</td><td>-</td>
  </tr>
</table>
"""

ALIYUN_TIERED_HTML = """
<table>
  <tr>
    <th>模型 ID（Model ID）</th><th>服务部署范围</th><th>模式</th>
    <th>单次请求的输入 Token 数</th>
    <th>输入单价（每百万 Token）</th>
    <th>输出单价（每百万 Token）</th><th>免费额度</th>
  </tr>
  <tr>
    <td rowspan="2"><p>qwen3.6-max-preview</p></td>
    <td rowspan="2">中国内地</td>
    <td rowspan="2">非思考和思考模式</td>
    <td>0&lt;Token≤128K</td><td>9 元</td><td>54 元</td>
    <td rowspan="2">-</td>
  </tr>
  <tr>
    <td>128K&lt;Token≤256K</td><td>15 元</td><td>90 元</td>
  </tr>
</table>
"""

ALIYUN_PREFIXED_MODEL_HTML = """
<table>
  <tr>
    <th>模型 ID（Model ID）</th><th>服务部署范围</th><th>模式</th>
    <th>输入单价（每百万 Token）</th>
    <th>输出单价（每百万 Token）</th><th>免费额度</th>
  </tr>
  <tr>
    <td>ZHIPU/GLM-5</td><td>中国内地</td><td>非思考和思考模式</td>
    <td>8 元</td><td>28 元</td><td>-</td>
  </tr>
  <tr>
    <td>siliconflow/deepseek-v3.2</td><td>中国内地</td>
    <td>非思考和思考模式</td>
    <td>2 元</td><td>3 元</td><td>-</td>
  </tr>
  <tr>
    <td>128K</td><td>中国内地</td><td>非思考和思考模式</td>
    <td>12 元</td><td>12 元</td><td>-</td>
  </tr>
</table>
"""


def siliconflow_html(pricing_items):
    payload = json.dumps(
        {"pricingApiItems": pricing_items},
        ensure_ascii=False,
    )
    escaped = json.dumps(payload, ensure_ascii=False)[1:-1]
    return f'<script>self.__next_f.push([1,"{escaped}"])</script>'


SILICONFLOW_HTML = siliconflow_html(
    [
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Pro",
            "playgroundSort": 81000,
            "skuName": "deepseek-ai/deepseek-v4-pro.online",
            "componentCode": "input-tokens",
            "coordinateDesc": "",
            "price_scenario": "兜底价",
            "realTimePriceCnyUnit": "0.012000",
            "unitZhCnName": "K tokens",
        },
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Pro",
            "playgroundSort": 81000,
            "skuName": "deepseek-ai/deepseek-v4-pro.online",
            "componentCode": "output-tokens",
            "coordinateDesc": "",
            "price_scenario": "兜底价",
            "realTimePriceCnyUnit": "0.024000",
            "unitZhCnName": "K tokens",
        },
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Pro",
            "playgroundSort": 81000,
            "skuName": "deepseek-ai/deepseek-v4-pro.online",
            "componentCode": "cached-input-tokens",
            "coordinateDesc": "",
            "price_scenario": "兜底价",
            "realTimePriceCnyUnit": "0.000100",
            "unitZhCnName": "K tokens",
        },
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Flash",
            "playgroundSort": 80900,
            "skuName": "deepseek-ai/deepseek-v4-flash.online",
            "componentCode": "input-tokens",
            "coordinateDesc": "",
            "price_scenario": "活动价",
            "realTimePriceCnyUnit": "0.001000",
            "unitZhCnName": "K tokens",
        },
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Flash",
            "playgroundSort": 80900,
            "skuName": "deepseek-ai/deepseek-v4-flash.online",
            "componentCode": "output-tokens",
            "coordinateDesc": "",
            "price_scenario": "活动价",
            "realTimePriceCnyUnit": "0.002000",
            "unitZhCnName": "K tokens",
        },
        {
            "playgroundName": "deepseek-ai/DeepSeek-V4-Flash",
            "playgroundSort": 80900,
            "skuName": "deepseek-ai/deepseek-v4-flash.online",
            "componentCode": "cached-input-tokens",
            "coordinateDesc": "",
            "price_scenario": "兜底价",
            "realTimePriceCnyUnit": "0.000020",
            "unitZhCnName": "K tokens",
        },
    ]
)


class ModelPriceSkillRunnerTests(SimpleTestCase):
    def test_aliyun_formal_provider_adapter_returns_standard_catalog(self):
        self.assertTrue(vendor_price_collector_exists("aliyun"))

        payload = collect_vendor_price_catalog(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_HTML,
            },
        )

        self.assertEqual(
            payload["schema_version"],
            MODEL_PRICE_CATALOG_SCHEMA_VERSION,
        )
        self.assertEqual(payload["source_type"], "provider_adapter")
        self.assertEqual(
            payload["raw_payload"]["collector"],
            "llm_ops.price_collectors.aliyun",
        )
        self.assertEqual(payload["models"][0]["model_id"], "qwen-new-2026")

    def test_aliyun_provider_adapter_preserves_multi_market_prices(self):
        payload = collect_vendor_price_catalog(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_MULTI_MARKET_HTML,
            },
        )

        self.assertEqual(payload["total_models"], 1)
        model = payload["models"][0]
        self.assertEqual(model["model_id"], "qwen-plus")
        rows = model["price_rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["values"]["currency"], "CNY")
        self.assertEqual(rows[0]["values"]["deployment_scope"], "中国内地")
        self.assertEqual(rows[1]["values"]["currency"], "USD")
        self.assertEqual(rows[1]["values"]["deployment_scope"], "国际")
        self.assertEqual(rows[1]["values"]["input_price"], "0.12")

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
        self.assertEqual(payload["source_type"], "provider_adapter")
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

    def test_deepseek_provider_adapter_extracts_cny_official_prices(self):
        payload = collect_vendor_price_catalog(
            "deepseek",
            {
                "provider_name": "DeepSeek",
                "currency": "CNY",
                "raw_html": DEEPSEEK_HTML,
            },
        )

        self.assertEqual(payload["source_type"], "provider_adapter")
        self.assertEqual(payload["provider"]["code"], "deepseek")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 2)
        flash = payload["models"][0]
        pro = payload["models"][1]
        self.assertEqual(flash["model_id"], "deepseek-v4-flash")
        self.assertEqual(pro["model_id"], "deepseek-v4-pro")
        self.assertEqual(
            flash["price_rows"][0]["values"]["cache_hit_input_price"],
            "0.02",
        )
        self.assertEqual(
            flash["price_rows"][0]["values"]["input_price"],
            "1",
        )
        self.assertEqual(
            pro["price_rows"][0]["values"]["output_price"],
            "6",
        )

    def test_siliconflow_provider_adapter_extracts_supplier_prices(self):
        self.assertTrue(vendor_price_collector_exists("siliconflow"))

        payload = collect_vendor_price_catalog(
            "siliconflow",
            {
                "provider_name": "SiliconFlow",
                "currency": "CNY",
                "raw_html": SILICONFLOW_HTML,
            },
        )

        self.assertEqual(payload["source_type"], "provider_adapter")
        self.assertEqual(payload["provider"]["code"], "siliconflow")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 2)
        pro = payload["models"][0]
        flash = payload["models"][1]
        self.assertEqual(pro["model_id"], "deepseek-ai/DeepSeek-V4-Pro")
        self.assertEqual(pro["provider"], "DeepSeek")
        self.assertEqual(
            pro["price_rows"][0]["values"]["input_price"],
            "12",
        )
        self.assertEqual(
            pro["price_rows"][0]["values"]["output_price"],
            "24",
        )
        self.assertEqual(
            pro["price_rows"][0]["values"]["cache_hit_input_price"],
            "0.1",
        )
        self.assertEqual(flash["model_id"], "deepseek-ai/DeepSeek-V4-Flash")
        self.assertEqual(
            flash["price_rows"][0]["values"]["input_price"],
            "1",
        )

    def test_siliconflow_provider_adapter_skips_free_models(self):
        payload = collect_vendor_price_catalog(
            "siliconflow",
            {
                "provider_name": "SiliconFlow",
                "currency": "CNY",
                "raw_html": siliconflow_html(
                    [
                        {
                            "playgroundName": (
                                "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
                            ),
                            "playgroundSort": 80100,
                            "skuName": "free-text-model.online",
                            "componentCode": "input-tokens",
                            "coordinateDesc": "",
                            "price_scenario": "活动价",
                            "realTimePriceCnyUnit": "0",
                            "unitZhCnName": "K tokens",
                        },
                        {
                            "playgroundName": (
                                "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
                            ),
                            "playgroundSort": 80100,
                            "skuName": "free-text-model.online",
                            "componentCode": "output-tokens",
                            "coordinateDesc": "",
                            "price_scenario": "活动价",
                            "realTimePriceCnyUnit": "0",
                            "unitZhCnName": "K tokens",
                        },
                        {
                            "playgroundName": "deepseek-ai/DeepSeek-V4-Pro",
                            "playgroundSort": 81000,
                            "skuName": "deepseek-ai/deepseek-v4-pro.online",
                            "componentCode": "input-tokens",
                            "coordinateDesc": "",
                            "price_scenario": "兜底价",
                            "realTimePriceCnyUnit": "0.012000",
                            "unitZhCnName": "K tokens",
                        },
                        {
                            "playgroundName": "deepseek-ai/DeepSeek-V4-Pro",
                            "playgroundSort": 81000,
                            "skuName": "deepseek-ai/deepseek-v4-pro.online",
                            "componentCode": "output-tokens",
                            "coordinateDesc": "",
                            "price_scenario": "兜底价",
                            "realTimePriceCnyUnit": "0.024000",
                            "unitZhCnName": "K tokens",
                        },
                    ]
                ),
            },
        )

        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(
            payload["models"][0]["model_id"],
            "deepseek-ai/DeepSeek-V4-Pro",
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
        self.assertEqual(
            payload["models"][0]["price_rows"][0]["values"][
                "cache_hit_input_price"
            ],
            "0.35",
        )

    def test_aliyun_vendor_skill_extracts_seven_column_qwen_rows(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_QWEN37_HTML,
            },
        )

        self.assertEqual(payload["provider"]["code"], "aliyun")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "qwen3.7-max")
        values = payload["models"][0]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "12")
        self.assertEqual(values["output_price"], "36")
        self.assertEqual(values["input_token_range"], "0-1000000")

    def test_aliyun_vendor_skill_preserves_tiered_token_prices(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_TIERED_HTML,
            },
        )

        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(
            payload["models"][0]["model_id"],
            "qwen3.6-max-preview",
        )
        rows = payload["models"][0]["price_rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["values"]["input_token_range"], "0-128000")
        self.assertEqual(rows[0]["values"]["input_price"], "9")
        self.assertEqual(rows[0]["values"]["cache_hit_input_price"], "0.9")
        self.assertEqual(
            rows[1]["values"]["input_token_range"],
            "128000-256000",
        )
        self.assertEqual(rows[1]["values"]["output_price"], "90")
        self.assertEqual(rows[1]["values"]["cache_hit_input_price"], "1.5")

    def test_aliyun_vendor_skill_filters_non_model_rows(self):
        payload = run_vendor_pricing_skill(
            "aliyun",
            {
                "provider_name": "阿里云",
                "currency": "CNY",
                "raw_html": ALIYUN_PREFIXED_MODEL_HTML,
            },
        )

        model_ids = [model["model_id"] for model in payload["models"]]
        self.assertEqual(model_ids, ["GLM-5"])
        values = payload["models"][0]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "8")
        self.assertEqual(values["output_price"], "28")

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
