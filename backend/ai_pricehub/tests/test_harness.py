import pytest

from ai_pricehub.harness import PricingHarnessAgent


@pytest.mark.unit
def test_fetch_vendor_catalog_skips_parser_for_api_only_strategy():
    harness = PricingHarnessAgent(
        deterministic_fetcher=lambda vendor: {
            "models": [],
            "raw_payload": {
                "api_only": True,
                "api_error": "Aliyun API unavailable",
            },
            "source_type": "vendor_python_skill",
        },
        agent_fetcher=lambda *args, **kwargs: pytest.fail("parser fallback should not run"),
    )

    with pytest.raises(ValueError, match="Aliyun API unavailable"):
        harness.fetch_vendor_catalog(
            {
                "slug": "aliyun",
                "name": "Aliyun",
                "acquisition": {"method": "api"},
            }
        )


@pytest.mark.unit
def test_fetch_vendor_catalog_allows_parser_fallback_for_api_only_when_non_strict():
    harness = PricingHarnessAgent(
        deterministic_fetcher=lambda vendor: {
            "models": [],
            "raw_payload": {
                "api_only": True,
                "api_error": "Aliyun API unavailable",
            },
            "source_type": "vendor_python_skill",
        },
        agent_fetcher=lambda *args, **kwargs: {
            "models": [{"model_name": "qwen-plus"}],
            "raw_payload": {"source": "parser"},
            "source_type": "vendor_agent_skill",
        },
    )

    payload = harness.fetch_vendor_catalog(
        {
            "slug": "aliyun",
            "name": "Aliyun",
            "acquisition": {"method": "api"},
        },
        strict_api_only=False,
    )

    assert payload.get("models") == [{"model_name": "qwen-plus"}]
    assert (payload.get("raw_payload") or {}).get("source_stage") == "tracked_parser"
