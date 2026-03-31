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
