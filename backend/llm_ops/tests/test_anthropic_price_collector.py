from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.anthropic import extract_models


ANTHROPIC_PRICING_MARKDOWN = "\n".join(
    [
        "## Model pricing",
        "",
        (
            "| Model | Base Input Tokens | 5m Cache Writes | "
            "1h Cache Writes | Cache Hits & Refreshes | Output Tokens |"
        ),
        (
            "| ----- | ----------------- | --------------- | "
            "--------------- | ---------------------- | ------------- |"
        ),
        (
            "| Claude Fable 5 | $10 / MTok | $12.50 / MTok | "
            "$20 / MTok | $1 / MTok | $50 / MTok |"
        ),
        (
            "| Claude Mythos 5 ([limited availability]"
            "(https://anthropic.com/glasswing)) | $10 / MTok | "
            "$12.50 / MTok | $20 / MTok | $1 / MTok | $50 / MTok |"
        ),
        (
            "| Claude Opus 4.8 | $5 / MTok | $6.25 / MTok | "
            "$10 / MTok | $0.50 / MTok | $25 / MTok |"
        ),
        (
            "| Claude Sonnet 4.5 | $3 / MTok | $3.75 / MTok | "
            "$6 / MTok | $0.30 / MTok | $15 / MTok |"
        ),
    ]
)


class AnthropicPriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_reads_model_pricing_table(self):
        models = extract_models(ANTHROPIC_PRICING_MARKDOWN)

        opus = next(
            item for item in models if item["model_id"] == "claude-opus-4-8"
        )
        mythos = next(
            item
            for item in models
            if item["model_id"] == "claude-mythos-5"
        )

        self.assertEqual(opus["input_price_per_million"], "5")
        self.assertEqual(opus["output_price_per_million"], "25")
        self.assertEqual(
            opus["price_rows"][0]["cache_hit_price_per_million"],
            "0.50",
        )
        self.assertEqual(mythos["display_name"], "Claude Mythos 5")

    def test_collect_vendor_price_catalog_returns_anthropic_payload(self):
        payload = collect_vendor_price_catalog(
            "anthropic",
            {
                "raw_markdown": ANTHROPIC_PRICING_MARKDOWN,
                "source_url": "https://example.com/anthropic-pricing",
                "provider_name": "Anthropic",
                "model_codes": ["claude-sonnet-4-5"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "anthropic")
        self.assertEqual(payload["provider"]["currency"], "USD")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(
            payload["models"][0]["model_id"],
            "claude-sonnet-4-5",
        )
