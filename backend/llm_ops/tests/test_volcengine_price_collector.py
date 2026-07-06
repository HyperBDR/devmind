from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers.volcengine import extract_models
from llm_ops.skill_runner import standard_catalog_run_metadata


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


class VolcEnginePriceCatalogCollectorTests(SimpleTestCase):
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
