import json

from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.minimax import extract_models


MINIMAX_PRICING_JSON = json.dumps(
    {
        "apiPricing": {
            "currencySymbol": "¥",
            "m3": {
                "prices": [
                    {
                        "model": "MiniMax-M2.1",
                        "input": "0.8",
                        "output": "8",
                    },
                    {
                        "model": "MiniMax-Text-01",
                        "inputPrice": "¥1 / 1M tokens",
                        "outputPrice": "¥8 / 1M tokens",
                    },
                ],
            },
        },
    }
)

MINIMAX_PRICING_TABLE = """
<table>
  <tr>
    <th>模型</th>
    <th>输入</th>
    <th>输出</th>
  </tr>
  <tr>
    <td>MiniMax-M2.1</td>
    <td>¥0.8 / 百万 tokens</td>
    <td>¥8 / 百万 tokens</td>
  </tr>
</table>
"""

MINIMAX_THOUSAND_TOKEN_TABLE = """
<table>
  <tr>
    <th>模型</th>
    <th>输入</th>
    <th>输出</th>
  </tr>
  <tr>
    <td>MiniMax-M2.1</td>
    <td>¥0.0008 / 千 tokens</td>
    <td>¥0.008 / 千 tokens</td>
  </tr>
</table>
"""

MINIMAX_TOKEN_PLAN_FAQ_HTML = """
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "faqs": [
        {
          "question": "Token Plan 支持哪些模型？",
          "answer": "支持所有平台模型；1,000 积分 = ¥7。"
        }
      ]
    }
  }
}
</script>
"""


class MiniMaxPriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_from_structured_api_pricing_json(self):
        models = extract_models(MINIMAX_PRICING_JSON)

        model_ids = {item["model_id"] for item in models}
        self.assertEqual(
            model_ids,
            {"minimax-m2.1", "minimax-text-01"},
        )
        m2 = next(
            item for item in models if item["model_id"] == "minimax-m2.1"
        )
        self.assertEqual(m2["input_price_per_million"], "0.8")
        self.assertEqual(m2["output_price_per_million"], "8")

    def test_extract_models_from_plain_html_pricing_table(self):
        models = extract_models(MINIMAX_PRICING_TABLE)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "minimax-m2.1")
        self.assertEqual(models[0]["input_price_per_million"], "0.8")
        self.assertEqual(models[0]["output_price_per_million"], "8")

    def test_extract_models_normalizes_thousand_token_prices(self):
        models = extract_models(MINIMAX_THOUSAND_TOKEN_TABLE)

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["model_id"], "minimax-m2.1")
        self.assertEqual(models[0]["input_price_per_million"], "0.8")
        self.assertEqual(models[0]["output_price_per_million"], "8")

    def test_token_plan_faq_without_model_prices_returns_empty_catalog(self):
        payload = collect_vendor_price_catalog(
            "minimax",
            {
                "raw_html": MINIMAX_TOKEN_PLAN_FAQ_HTML,
                "source_url": "https://example.com/minimax-token-plan",
            },
        )

        self.assertEqual(payload["provider"]["code"], "minimax")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 0)
        self.assertEqual(payload["models"], [])

    def test_collect_vendor_price_catalog_returns_minimax_payload(self):
        payload = collect_vendor_price_catalog(
            "minimax",
            {
                "raw_html": MINIMAX_PRICING_TABLE,
                "source_url": "https://example.com/minimax-pricing",
                "provider_name": "MiniMax",
                "model_codes": ["minimax-m2.1"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "minimax")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(payload["models"][0]["model_id"], "minimax-m2.1")
