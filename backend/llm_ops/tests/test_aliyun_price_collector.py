from django.test import SimpleTestCase

from llm_ops.price_collectors.parsers.aliyun import extract_models


ALIYUN_REGIONAL_PRICING_HTML = """
<section>
  <h4>华北 2（北京）</h4>
  <table>
    <tr>
      <th>模型 ID（Model ID）</th>
      <th>输入单价（每百万 Token）</th>
      <th>输出单价（每百万 Token）</th>
      <th>免费额度</th>
    </tr>
    <tr>
      <td>deepseek-v4-flash-0731</td>
      <td><p>忙时 3 元</p><p>闲时 1.5 元</p></td>
      <td><p>忙时 9 元</p><p>闲时 4.5 元</p></td>
      <td>100 万 Token</td>
    </tr>
    <tr>
      <td>deepseek-v4-flash</td>
      <td>1 元</td>
      <td>2 元</td>
      <td>100 万 Token</td>
    </tr>
  </table>
</section>
<section>
  <h4>新加坡</h4>
  <table>
    <tr>
      <th>模型 ID（Model ID）</th>
      <th>服务部署范围</th>
      <th>输入单价（每百万 Token）</th>
      <th>输出单价（每百万 Token）</th>
    </tr>
    <tr>
      <td>deepseek-v4-flash-0731</td>
      <td>国际</td>
      <td><p>忙时 3.208 元</p><p>闲时 1.604 元</p></td>
      <td><p>忙时 9.625 元</p><p>闲时 4.813 元</p></td>
    </tr>
  </table>
</section>
<section>
  <h4>日本（东京）</h4>
  <table>
    <tr>
      <th>模型 ID（Model ID）</th>
      <th>服务部署范围</th>
      <th>输入单价（每百万 Token）</th>
      <th>输出单价（每百万 Token）</th>
    </tr>
    <tr>
      <td>deepseek-v4-flash</td>
      <td>日本</td>
      <td>1.499 元</td>
      <td>2.998 元</td>
    </tr>
  </table>
</section>
"""


class AliyunPriceCollectorTests(SimpleTestCase):
    def test_collects_only_beijing_prices_with_normalized_location(self):
        models = extract_models(ALIYUN_REGIONAL_PRICING_HTML)

        self.assertEqual(
            [model["model_id"] for model in models],
            ["deepseek-v4-flash", "deepseek-v4-flash-0731"],
        )
        for model in models:
            for row in model["price_rows"]:
                self.assertEqual(row["access_region"], "cn-beijing")
                self.assertEqual(
                    row["deployment_scope"],
                    "china_mainland",
                )
                self.assertEqual(row["region"], "cn-beijing")

    def test_keeps_peak_and_off_peak_prices_as_structured_conditions(self):
        models = extract_models(ALIYUN_REGIONAL_PRICING_HTML)
        model = next(
            item
            for item in models
            if item["model_id"] == "deepseek-v4-flash-0731"
        )

        self.assertEqual(len(model["price_rows"]), 2)
        rows = {
            row["pricing_condition"]["code"]: row
            for row in model["price_rows"]
        }
        self.assertEqual(set(rows), {"peak", "off_peak"})
        self.assertEqual(rows["peak"]["input_price_per_million"], "3")
        self.assertEqual(rows["peak"]["output_price_per_million"], "9")
        self.assertEqual(
            rows["peak"]["cache_hit_price_per_million"],
            "0.3",
        )
        self.assertEqual(
            rows["off_peak"]["input_price_per_million"],
            "1.5",
        )
        self.assertEqual(
            rows["off_peak"]["output_price_per_million"],
            "4.5",
        )
        self.assertEqual(
            rows["off_peak"]["cache_hit_price_per_million"],
            "0.15",
        )
        self.assertEqual(
            rows["peak"]["pricing_condition"]["timezone"],
            "Asia/Shanghai",
        )

    def test_marks_fixed_prices_as_all_time(self):
        models = extract_models(ALIYUN_REGIONAL_PRICING_HTML)
        model = next(
            item
            for item in models
            if item["model_id"] == "deepseek-v4-flash"
        )

        self.assertEqual(
            model["price_rows"][0]["pricing_condition"],
            {"type": "always", "code": "all_time"},
        )
