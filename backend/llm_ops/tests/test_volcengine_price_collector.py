from django.test import SimpleTestCase
from llm_ops.collection_services import parse_price_range, price_item_payload
from llm_ops.models import ModelPriceItem
from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.volcengine import extract_models
from llm_ops.price_table_validation import validate_price_table_groups
from llm_ops.skill_runner import standard_catalog_run_metadata

VOLCENGINE_HTML = (
    r"\"ops\":[{\"insert\":\"doubao-1.5-pro-32k\"}],"
    r"\"zoneId\":\"row01nj2n42rlpl8e7b6tvpmvqhysnzfp89bh\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"2\"}],"
    r"\"zoneId\":\"row01s303uu1c1g40de7oaoizn05md89iimb6\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"8\"}],"
    r"\"zoneId\":\"row015wt3pecycob8so1pho26k692zw2cgbsm\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"0.4\"}],"
    r"\"zoneId\":\"row01cvklbb5m01p5jfrmdhooit6bknkyawsj\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"标准推理\"}],"
    r"\"zoneId\":\"row01gagtwd6h2ui45oj1di8jtwno5ytnfdt6\","
    r"\"zoneType\":\"Z\""
)


VOLCENGINE_FIRST_TIER_HTML = (
    r"\"ops\":[{\"insert\":\"doubao-seed-1-6\"}],"
    r"\"zoneId\":\"tier01nj2n42rlpl8e7b6tvpmvqhysnzfp89bh\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"2.4\"}],"
    r"\"zoneId\":\"tier01s303uu1c1g40de7oaoizn05md89iimb6\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"24\"}],"
    r"\"zoneId\":\"tier015wt3pecycob8so1pho26k692zw2cgbsm\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"输入长度 (0, 128]\"}],"
    r"\"zoneId\":\"tier01gagtwd6h2ui45oj1di8jtwno5ytnfdt6\","
    r"\"zoneType\":\"Z\""
)


VOLCENGINE_MULTI_TIER_HTML = (
    VOLCENGINE_FIRST_TIER_HTML
    + r"\"ops\":[{\"insert\":\"doubao-seed-1-6\"}],"
    r"\"zoneId\":\"tier02nj2n42rlpl8e7b6tvpmvqhysnzfp89bh\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"4.8\"}],"
    r"\"zoneId\":\"tier02s303uu1c1g40de7oaoizn05md89iimb6\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"48\"}],"
    r"\"zoneId\":\"tier025wt3pecycob8so1pho26k692zw2cgbsm\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"输入长度 (128, 256]\"}],"
    r"\"zoneId\":\"tier02gagtwd6h2ui45oj1di8jtwno5ytnfdt6\","
    r"\"zoneType\":\"Z\""
)


VOLCENGINE_SECTION_DUPLICATE_HTML = (
    VOLCENGINE_FIRST_TIER_HTML
    + r"\"ops\":[{\"insert\":\"doubao-seed-1-6\"}],"
    r"\"zoneId\":\"batch1sd9qqqvyjh64sfk1ym6h608eym82d47r\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"1.2\"}],"
    r"\"zoneId\":\"batch1g1jev13gq4vtdf1u98drambg5e4iydrp\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"12\"}],"
    r"\"zoneId\":\"batch1r0s2ipdcp1is8youke6te708kops5in5\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"输入长度 (0, 128]\"}],"
    r"\"zoneId\":\"batch18tq8h7zdnkenawut121k9pl3482469oc\","
    r"\"zoneType\":\"Z\""
)


VOLCENGINE_COMPLETE_TIER_HTML = (
    VOLCENGINE_MULTI_TIER_HTML
    + r"\"ops\":[{\"insert\":\"doubao-seed-1-6\"}],"
    r"\"zoneId\":\"tier03nj2n42rlpl8e7b6tvpmvqhysnzfp89bh\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"9.6\"}],"
    r"\"zoneId\":\"tier03s303uu1c1g40de7oaoizn05md89iimb6\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"96\"}],"
    r"\"zoneId\":\"tier035wt3pecycob8so1pho26k692zw2cgbsm\","
    r"\"zoneType\":\"Z\""
    r"\"ops\":[{\"insert\":\"输入长度 > 256\"}],"
    r"\"zoneId\":\"tier03gagtwd6h2ui45oj1di8jtwno5ytnfdt6\","
    r"\"zoneType\":\"Z\""
)


class VolcEnginePriceCatalogCollectorTests(SimpleTestCase):
    def test_complete_tiers_support_an_unbounded_final_range(self):
        models = extract_models(VOLCENGINE_COMPLETE_TIER_HTML)

        model = models[0]

        self.assertEqual(
            [row["input_token_range"] for row in model["price_rows"]],
            ["0-128000", "128000-256000", "256000+"],
        )

        payloads = []
        for row in model["price_rows"]:
            tier_start, tier_end = parse_price_range(
                row["input_token_range"]
            )
            payloads.append(
                price_item_payload(
                    {},
                    dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                    billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                    unit_price=row["input_price_per_million"],
                    tier_start=tier_start,
                    tier_end=tier_end,
                )
            )
            payloads.append(
                price_item_payload(
                    {},
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                    billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                    unit_price=row["output_price_per_million"],
                    tier_start=tier_start,
                    tier_end=tier_end,
                )
            )

        validate_price_table_groups(payloads)

    def test_extract_models_keeps_online_price_when_batch_has_same_tier(self):
        models = extract_models(VOLCENGINE_SECTION_DUPLICATE_HTML)

        model = models[0]

        self.assertEqual(model["input_price_per_million"], "2.4")
        self.assertNotIn("price_rows", model)

    def test_extract_models_keeps_each_official_token_length_tier(self):
        models = extract_models(VOLCENGINE_MULTI_TIER_HTML)

        model = models[0]

        self.assertEqual(
            [row["input_token_range"] for row in model["price_rows"]],
            ["0-128000", "128000-256000"],
        )
        self.assertEqual(
            [row["output_price_per_million"] for row in model["price_rows"]],
            ["24", "48"],
        )

    def test_catalog_preserves_each_official_token_length_tier(self):
        payload = collect_vendor_price_catalog(
            "volcengine",
            {
                "raw_html": VOLCENGINE_MULTI_TIER_HTML,
                "provider_name": "火山方舟",
            },
        )

        rows = payload["models"][0]["price_rows"]

        self.assertEqual(
            [row["values"]["input_token_range"] for row in rows],
            ["0-128000", "128000-256000"],
        )

    def test_catalog_preserves_complete_official_token_length_tiers(self):
        payload = collect_vendor_price_catalog(
            "volcengine",
            {
                "raw_html": VOLCENGINE_COMPLETE_TIER_HTML,
                "provider_name": "火山方舟",
            },
        )
        model = payload["models"][0]

        self.assertEqual(
            [
                row["values"]["input_token_range"]
                for row in model["price_rows"]
            ],
            ["0-128000", "128000-256000", "256000+"],
        )

    def test_extract_models_preserves_official_token_length_tier(self):
        models = extract_models(VOLCENGINE_FIRST_TIER_HTML)

        model = models[0]

        self.assertEqual(
            model["input_token_range"],
            "0-128000",
        )
        self.assertEqual(
            model["output_token_range"],
            "0-128000",
        )

    def test_extract_models_reads_document_zone_prices(self):
        models = extract_models(VOLCENGINE_HTML)

        model = models[0]

        self.assertEqual(model["model_id"], "doubao-1.5-pro-32k")
        self.assertEqual(model["input_price_per_million"], "2")
        self.assertEqual(model["output_price_per_million"], "8")
        self.assertEqual(model["cache_hit_price_per_million"], "0.4")
        self.assertIn("标准推理", model["notes"])

    def test_collect_vendor_price_catalog_returns_volcengine_payload(self):
        payload = collect_vendor_price_catalog(
            "volcengine",
            {
                "provider_name": "火山方舟",
                "currency": "CNY",
                "raw_html": VOLCENGINE_HTML,
                "model_codes": ["doubao-1.5-pro-32k"],
            },
        )

        self.assertEqual(
            payload["schema_version"],
            "llm_ops.model_price_catalog.v1",
        )
        self.assertEqual(payload["provider"]["code"], "volcengine")
        self.assertEqual(payload["provider"]["currency"], "CNY")
        self.assertEqual(payload["total_models"], 1)
        self.assertEqual(
            payload["models"][0]["model_id"],
            "doubao-1.5-pro-32k",
        )
        values = payload["models"][0]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "2")
        self.assertEqual(values["output_price"], "8")

    def test_empty_live_parse_marks_static_fallback_payload(self):
        payload = collect_vendor_price_catalog(
            "volcengine",
            {
                "raw_html": "<html></html>",
                "verify_source": False,
            },
        )

        self.assertEqual(payload["provider"]["code"], "volcengine")
        self.assertEqual(payload["total_models"], 1)
        self.assertTrue(payload["raw_payload"]["fallback_used"])
        self.assertEqual(
            payload["raw_payload"]["fallback_reason"],
            "official_page_parse_empty",
        )

        metadata = standard_catalog_run_metadata(payload)

        self.assertTrue(metadata["vendor_catalog_fallback_used"])
        self.assertEqual(
            metadata["vendor_catalog_fallback_reason"],
            "official_page_parse_empty",
        )
