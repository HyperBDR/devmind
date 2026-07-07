import threading
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from llm_ops.price_collectors import collect_vendor_price_catalog
from llm_ops.price_collectors.parsers import azure_openai


def retail_item(meter_name, price, dimension="Input", unit="1K"):
    product_name = "Azure OpenAI GPT5" if meter_name[:1].isdigit() else (
        "Azure OpenAI"
    )
    return {
        "serviceName": "Foundry Models",
        "productName": product_name,
        "skuName": f"gpt 4o {dimension} global",
        "meterName": meter_name,
        "unitOfMeasure": unit,
        "retailPrice": price,
        "currencyCode": "USD",
        "armRegionName": "eastus",
    }


class AzureOpenAIPriceCatalogCollectorTests(SimpleTestCase):
    def test_extract_models_keeps_only_standard_pricing(self):
        payload = collect_vendor_price_catalog(
            "azure-openai",
            {
                "provider_name": "Azure OpenAI",
                "currency": "USD",
                "raw_retail_items": [
                    retail_item("gpt 4o Input global Tokens", 0.005),
                    retail_item(
                        "gpt 4o Output global Tokens",
                        0.015,
                        "Output",
                    ),
                    retail_item(
                        "gpt 4o Priority Processing Input global Tokens",
                        0.006,
                    ),
                    retail_item(
                        "gpt 4o Priority Processing Output global Tokens",
                        0.018,
                        "Output",
                    ),
                    retail_item(
                        "gpt 4o Batch API Input global Tokens",
                        0.0025,
                    ),
                    retail_item(
                        "gpt 4o Batch API Output global Tokens",
                        0.0075,
                        "Output",
                    ),
                ],
            },
        )

        self.assertEqual(payload["total_models"], 1)
        values = payload["models"][0]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "5")
        self.assertEqual(values["output_price"], "15")

    def test_extract_models_prefers_gpt_55_short_context_global_prices(self):
        payload = collect_vendor_price_catalog(
            "azure-openai",
            {
                "provider_name": "Azure OpenAI",
                "currency": "USD",
                "raw_retail_items": [
                    retail_item("5.5 LongCo inp Gl 1M Tokens", 10, unit="1M"),
                    retail_item(
                        "5.5 LongCo cd inp Gl 1M Tokens",
                        1,
                        unit="1M",
                    ),
                    retail_item(
                        "5.5 LongCo opt Gl 1M Tokens",
                        45,
                        "Output",
                        "1M",
                    ),
                    retail_item("5.5 ShortCo inp Gl 1M Tokens", 5, unit="1M"),
                    retail_item(
                        "5.5 ShortCo cd inp Gl 1M Tokens",
                        0.5,
                        unit="1M",
                    ),
                    retail_item(
                        "5.5 ShortCo opt Gl 1M Tokens",
                        30,
                        "Output",
                        "1M",
                    ),
                    retail_item(
                        "5.5 ShortCo PP inp Gl 1M Tokens",
                        12.5,
                        unit="1M",
                    ),
                    retail_item(
                        "5.5 ShortCo PP opt Gl 1M Tokens",
                        75,
                        "Output",
                        "1M",
                    ),
                ],
            },
        )

        models = {item["model_id"]: item for item in payload["models"]}
        values = models["gpt-5.5"]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "5")
        self.assertEqual(values["cache_hit_input_price"], "0.5")
        self.assertEqual(values["output_price"], "30")
        self.assertEqual(values["deployment_scope"], "global")
        self.assertEqual(values["billing_scope"], "short_context")

    def test_extract_models_skips_audio_and_realtime_meters(self):
        payload = collect_vendor_price_catalog(
            "azure-openai",
            {
                "provider_name": "Azure OpenAI",
                "currency": "USD",
                "raw_retail_items": [
                    retail_item("gpt4omini-aud1217 Inp glbl Tokens", 0.01),
                    retail_item(
                        "gpt4omini-aud1217 Outp glbl Tokens",
                        0.02,
                        "Output",
                    ),
                    retail_item(
                        "gpt4omini-rt-txt1217 Inp glbl Tokens",
                        0.0006,
                    ),
                    retail_item(
                        "gpt4omini-rt-txt1217 Outp glbl Tokens",
                        0.0024,
                        "Output",
                    ),
                    retail_item("gpt 4o mini 0718 Inp glbl Tokens", 0.00015),
                    retail_item(
                        "gpt 4o mini 0718 Outp glbl Tokens",
                        0.0006,
                        "Output",
                    ),
                ],
            },
        )

        models = {item["model_id"]: item for item in payload["models"]}
        self.assertNotIn("gpt-4omini", models)
        values = models["gpt-4o-mini-0718"]["price_rows"][0]["values"]
        self.assertEqual(values["input_price"], "0.15")
        self.assertEqual(values["output_price"], "0.6")

    def test_fetch_retail_prices_fetches_later_pages_concurrently(self):
        second_page_started = threading.Event()
        third_page_started = threading.Event()

        class Response:
            def __init__(self, items, next_page_link=""):
                self.items = items
                self.next_page_link = next_page_link

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "Items": self.items,
                    "NextPageLink": self.next_page_link,
                }

        def fake_get(url, params=None, headers=None, timeout=None):
            skip = page_skip(url, params)
            if skip == 0:
                return Response(
                    [{} for _ in range(1000)],
                    (
                        azure_openai.RETAIL_PRICES_API_URL
                        + "?api-version=2023-01-01-preview&$skip=1000"
                    ),
                )
            if skip == 1000:
                second_page_started.set()
                if not third_page_started.wait(timeout=1):
                    raise AssertionError(
                        "Subsequent Azure price pages were fetched serially."
                    )
                return Response([{} for _ in range(1000)])
            if skip == 2000:
                third_page_started.set()
                return Response([{}])
            return Response([])

        self.patch_requests_get(fake_get)

        items = azure_openai.fetch_retail_prices(
            {
                "concurrent_pages": 2,
                "max_pages": 3,
            }
        )

        self.assertEqual(len(items), 2001)
        self.assertTrue(second_page_started.is_set())
        self.assertTrue(third_page_started.is_set())

    def patch_requests_get(self, fake_get):
        original_get = azure_openai.requests.get
        azure_openai.requests.get = fake_get
        self.addCleanup(setattr, azure_openai.requests, "get", original_get)


def page_skip(url, params):
    query = parse_qs(urlparse(url).query)
    if params:
        query.update({key: [value] for key, value in params.items()})
    return int((query.get("$skip") or ["0"])[0])
