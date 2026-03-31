import pytest

from ai_pricehub.services import AIPriceHubService


def test_build_vendor_model_queries_filters_primary_models_by_source_vendor():
    service = AIPriceHubService()
    vendor_data = {
        "slug": "aliyun",
        "name": "Aliyun",
        "aliases": ["Alibaba Cloud"],
    }
    primary_models = [
        {
            "model_name": "qwen3-235b-a22b-instruct-2507",
            "aliases": ["Qwen3-235B-A22B-Instruct-2507"],
            "source_vendors": ["Aliyun"],
        },
        {
            "model_name": "DeepSeek-V3.2",
            "aliases": ["deepseek-v3.2"],
            "source_vendors": ["Alibaba Cloud"],
        },
        {
            "model_name": "GLM-4.7",
            "aliases": ["glm-4.7"],
            "source_vendors": ["Zhipu"],
        },
    ]

    queries = service._build_vendor_model_queries(vendor_data, primary_models)  # noqa: SLF001

    assert queries == [
        "qwen3-235b-a22b-instruct-2507",
        "Qwen3-235B-A22B-Instruct-2507",
        "DeepSeek-V3.2",
        "deepseek-v3.2",
    ]


def test_build_vendor_model_queries_includes_aliases_for_qwq_plus():
    service = AIPriceHubService()
    vendor_data = {
        "slug": "aliyun",
        "name": "Aliyun",
        "aliases": ["Alibaba Cloud"],
    }
    primary_models = [
        {
            "model_name": "QwQ-Plus",
            "aliases": [
                "qwq-plus",
                "Model QwQ-Plus from Alibaba Cloud",
            ],
            "source_vendors": ["Alibaba Cloud"],
        }
    ]

    queries = service._build_vendor_model_queries(vendor_data, primary_models)  # noqa: SLF001

    assert queries == [
        "QwQ-Plus",
        "qwq-plus",
        "Model QwQ-Plus from Alibaba Cloud",
    ]


def test_sync_configured_sources_raises_for_strict_api_vendor_failure(monkeypatch):
    service = AIPriceHubService()

    monkeypatch.setattr(
        "ai_pricehub.services.config_loader.get_primary_vendor_configs",
        lambda: [
            {
                "slug": "agione",
                "name": "AGIOne",
                "platform_slug": "agione",
                "parser_llm_config_uuid": None,
            }
        ],
    )
    monkeypatch.setattr(
        "ai_pricehub.services.config_loader.get_comparison_vendors",
        lambda: [
            {
                "slug": "aliyun",
                "name": "Aliyun",
                "aliases": ["Alibaba Cloud"],
                "acquisition": {"method": "api"},
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "_fetch_primary_vendor_models",
        lambda vendor: {
            "models": [
                {
                    "model_name": "QwQ-Plus",
                    "aliases": ["qwq-plus"],
                    "source_vendors": ["Aliyun"],
                }
            ],
            "raw_payload": {},
            "source_type": "agione_model_list",
        },
    )
    monkeypatch.setattr(
        service,
        "_fetch_comparison_vendor_catalog",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Aliyun API unavailable")),
    )

    with pytest.raises(ValueError, match="Aliyun API unavailable"):
        service.sync_configured_sources(platform_slug="agione")
