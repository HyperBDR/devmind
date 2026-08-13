from decimal import Decimal

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
from llm_ops.price_collectors.parsers.google import extract_models
from llm_ops.skill_runner import standard_catalog_to_collected_catalog

GOOGLE_PRICING_HTML = """
<h3>Gemini 2.5</h3>
<table>
  <tr>
    <th>Model</th>
    <th>Type</th>
    <th>Price (/1M tokens) <= 200K input tokens</th>
    <th>Price (/1M tokens) > 200K input tokens</th>
    <th>Price (/1M cached input tokens) <= 200K</th>
    <th>Price (/1M cached input tokens) > 200K</th>
  </tr>
  <tr>
    <td rowspan="3">Gemini 2.5 Pro</td>
    <td>Input (text, image, video, audio)</td>
    <td>$1.25</td>
    <td>$2.50</td>
    <td>$0.13</td>
    <td>$0.25</td>
  </tr>
  <tr>
    <td>Output (text)</td>
    <td>$10.00</td>
    <td>$15.00</td>
    <td>-</td>
    <td>-</td>
  </tr>
  <tr>
    <td>Output (audio)</td>
    <td>$20.00</td>
    <td>$30.00</td>
    <td>-</td>
    <td>-</td>
  </tr>
</table>
<h3>Flex/Batch</h3>
<table>
  <tr><th>Model</th><th>Type</th><th>Price</th></tr>
  <tr>
    <td rowspan="2">Gemini 2.5 Pro</td>
    <td>Input (text)</td>
    <td>$0.62</td>
  </tr>
  <tr><td>Output (text)</td><td>$5.00</td></tr>
</table>
<h3>Gemini 2.0</h3>
<table>
  <tr><th>Model</th><th>Type</th><th>Price</th></tr>
  <tr>
    <td rowspan="3">Gemini 2.0 Flash</td>
    <td>1M Input tokens</td>
    <td>$0.15</td>
  </tr>
  <tr><td>1M Input audio tokens</td><td>$1.00</td></tr>
  <tr><td>1M Output text tokens</td><td>$0.60</td></tr>
</table>
"""


GOOGLE_128K_PRICING_HTML = """
<h3>Gemini 2.0</h3>
<table>
  <tr>
    <th>Model</th>
    <th>Type</th>
    <th>Price ( =&lt; 128K input tokens)</th>
    <th>Price ( &gt; 128K input tokens)</th>
  </tr>
  <tr>
    <td rowspan="2">Gemini 2.0 Flash</td>
    <td>Input (text)</td>
    <td>$1.25</td>
    <td>$2.50</td>
  </tr>
  <tr>
    <td>Output (text)</td>
    <td>$5.00</td>
    <td>$10.00</td>
  </tr>
</table>
"""


class GooglePriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_uses_context_boundary_from_table_header(self):
        models = extract_models(GOOGLE_128K_PRICING_HTML)

        pro = next(
            item
            for item in models
            if item["model_id"] == "gemini-2.0-flash"
        )

        self.assertEqual(
            [row["input_token_range"] for row in pro["price_rows"]],
            ["0-128000", "128000+"],
        )

    def test_extract_models_preserves_standard_context_tiers(self):
        models = extract_models(GOOGLE_PRICING_HTML)

        pro = next(
            item for item in models if item["model_id"] == "gemini-2.5-pro"
        )
        self.assertEqual(pro["input_price_per_million"], "1.25")
        self.assertEqual(pro["output_price_per_million"], "10.00")
        self.assertEqual(len(pro["price_rows"]), 2)
        self.assertEqual(
            pro["price_rows"][0]["input_token_range"],
            "0-200000",
        )
        self.assertEqual(
            pro["price_rows"][1]["input_token_range"],
            "200000+",
        )
        self.assertEqual(
            pro["price_rows"][0]["cache_hit_price_per_million"],
            "0.13",
        )

    def test_extract_models_skips_batch_and_audio_only_prices(self):
        models = extract_models(GOOGLE_PRICING_HTML)

        pro = next(
            item for item in models if item["model_id"] == "gemini-2.5-pro"
        )
        flash = next(
            item
            for item in models
            if item["model_id"] == "gemini-2.0-flash"
        )

        self.assertNotEqual(pro["input_price_per_million"], "0.62")
        self.assertEqual(flash["input_price_per_million"], "0.15")
        self.assertEqual(flash["output_price_per_million"], "0.60")

    def test_collect_vendor_price_catalog_returns_google_payload(self):
        payload = collect_vendor_price_catalog(
            "google",
            {
                "raw_html": GOOGLE_PRICING_HTML,
                "source_url": "https://example.com/google-pricing",
                "provider_name": "Google",
                "model_codes": ["gemini-2.0-flash"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "google")
        self.assertEqual(payload["provider"]["currency"], "USD")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(
            payload["models"][0]["model_id"],
            "gemini-2.0-flash",
        )


class GooglePriceCatalogPersistenceTests(TestCase):
    def test_standard_context_tiers_persist_as_usage_ranges(self):
        provider = LLMProvider.objects.create(
            name="Google",
            code="google",
        )
        source = PriceCollectionSource.objects.create(
            name="Google Gemini Official",
            slug="google-official",
            provider=provider,
            source_category=(
                PriceCollectionSource.SOURCE_CATEGORY_OFFICIAL_PROVIDER
            ),
            endpoint_url="https://example.com/google-pricing",
            currency="USD",
            is_enabled=True,
            updates_model_prices=True,
        )
        meta_model = MetaModel.objects.create(
            code="gemini-2.5-pro",
            name="Gemini 2.5 Pro",
            owner_code="google",
            owner_name="Google",
        )
        payload = collect_vendor_price_catalog(
            "google",
            {
                "raw_html": GOOGLE_PRICING_HTML,
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

        price_items = sync_model_price_items(
            item,
            source=source,
            offering=offering,
            source_url=source.endpoint_url,
        )

        input_items = sorted(
            (
                price_item
                for price_item in price_items
                if price_item.dimension == ModelPriceItem.DIMENSION_TEXT_INPUT
            ),
            key=lambda price_item: price_item.tier_start,
        )
        self.assertEqual(len(input_items), 2)
        self.assertEqual(
            [price_item.tier_type for price_item in input_items],
            [
                ModelPriceItem.TIER_USAGE_RANGE,
                ModelPriceItem.TIER_USAGE_RANGE,
            ],
        )
        self.assertEqual(input_items[0].tier_start, Decimal("0"))
        self.assertEqual(input_items[0].tier_end, Decimal("200000"))
        self.assertEqual(input_items[0].unit_price, Decimal("1.25"))
        self.assertEqual(input_items[1].tier_start, Decimal("200000"))
        self.assertIsNone(input_items[1].tier_end)
        self.assertEqual(input_items[1].unit_price, Decimal("2.50"))
