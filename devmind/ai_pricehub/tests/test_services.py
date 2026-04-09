import pytest

from ai_pricehub.services import AIPriceHubService


def test_fetch_primary_vendor_models_supports_new_agione_square_list_payload(monkeypatch):
    service = AIPriceHubService()
    vendor = {
        "slug": "agione",
        "name": "AGIOne",
        "platform_slug": "agione",
        "currency": "CNY",
        "points_per_currency_unit": 10.0,
        "models_source": {
            "url": "https://agione.cc/hyperone/xapi/models/square/list?isPublic=1&sortField=publishTime&sortOrder=desc&needConfig=true"
        },
    }

    payload = {
        "status": 200,
        "result": [
            {
                "authorDisplayName": {
                    "en-US": {"name": "DeepSeek"},
                    "zh-CN": {"name": "DeepSeek"},
                },
                "authorUid": "deepseek",
                "description": {
                    "en-US": {"name": "DeepSeek-V3.2 public listing"},
                    "zh-CN": {"name": "DeepSeek-V3.2 公开模型"},
                },
                "displayName": "DeepSeek-V3.2",
                "metaModelUid": "deepseek/deepseek-v3.2",
                "minInputPrice": 20.0,
                "minOutputPrice": 30.0,
                "providerCount": 4,
                "series": "DeepSeek V3",
                "supportFunction": 1,
                "supportReasoning": 1,
                "tagList": [],
            }
        ],
    }

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    monkeypatch.setattr("ai_pricehub.services.requests.get", lambda *args, **kwargs: DummyResponse())

    catalog = service._fetch_primary_vendor_models(vendor)  # noqa: SLF001

    assert catalog["source_type"] == "agione_model_list"
    assert catalog["raw_payload"]["record_count"] == 1
    assert catalog["models"] == [
        {
            "model_name": "DeepSeek-V3.2",
            "aliases": [
                "DeepSeek-V3.2",
                "deepseek-v3.2",
                "deepseek/deepseek-v3.2",
                "DeepSeek-V3.2 public listing",
            ],
            "family": "deepseek-v3",
            "input_price_per_million": 2.0,
            "output_price_per_million": 3.0,
            "currency": "CNY",
            "notes": (
                "DeepSeek-V3.2 public listing "
                "AGIOne pricing converted from points using 10 points = 1 CNY "
                "(input_points=20.0, output_points=30.0)."
            ),
            "source_vendors": ["DeepSeek", "deepseek"],
            "is_aggregate": False,
        }
    ]


def test_fetch_primary_vendor_models_maps_qwen_to_aliyun_source_vendor(monkeypatch):
    service = AIPriceHubService()
    vendor = {
        "slug": "agione",
        "name": "AGIOne",
        "platform_slug": "agione",
        "currency": "CNY",
        "points_per_currency_unit": 10.0,
        "models_source": {
            "url": "https://agione.cc/hyperone/xapi/models/square/list?isPublic=1&sortField=publishTime&sortOrder=desc&needConfig=true"
        },
    }

    payload = {
        "status": 200,
        "result": [
            {
                "authorDisplayName": {
                    "en-US": {"name": "Qwen"},
                    "zh-CN": {"name": "Qwen"},
                },
                "authorUid": "qwen",
                "description": {
                    "en-US": {"name": "Qwen3 flagship model"},
                },
                "displayName": "qwen3-235b-a22b-instruct-2507",
                "metaModelUid": "qwen/qwen3-235b-a22b-instruct-2507",
                "minInputPrice": 20.0,
                "minOutputPrice": 80.0,
                "providerCount": 2,
                "series": "Qwen3",
                "tagList": [],
            }
        ],
    }
    detail_payload = {
        "status": 200,
        "result": {
            "records": [
                {
                    "isAggregate": True,
                    "name": "[Aggregate]qwen3-235b-a22b-instruct-2507",
                },
                {
                    "isAggregate": False,
                    "name": "[Aliyun]qwen3-235b-a22b-instruct-2507",
                    "providerDisplayName": {
                        "en-US": {"name": "Alibaba-china"},
                    },
                },
            ]
        },
    }

    class DummyResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    def fake_get(url, *args, **kwargs):
        if "model-list" in url:
            return DummyResponse(detail_payload)
        return DummyResponse(payload)

    monkeypatch.setattr("ai_pricehub.services.requests.get", fake_get)

    catalog = service._fetch_primary_vendor_models(vendor)  # noqa: SLF001

    assert catalog["models"][0]["source_vendors"] == [
        "Aliyun",
        "Alibaba Cloud",
        "aliyun",
        "Alibaba-china",
    ]


def test_fetch_primary_vendor_models_maps_z_ai_to_zhipu_source_vendor(monkeypatch):
    service = AIPriceHubService()
    vendor = {
        "slug": "agione",
        "name": "AGIOne",
        "platform_slug": "agione",
        "currency": "CNY",
        "points_per_currency_unit": 10.0,
        "models_source": {
            "url": "https://agione.cc/hyperone/xapi/models/square/list?isPublic=1&sortField=publishTime&sortOrder=desc&needConfig=true"
        },
    }

    payload = {
        "status": 200,
        "result": [
            {
                "authorDisplayName": {
                    "en-US": {"name": "Z.ai"},
                    "zh-CN": {"name": "Z.ai"},
                },
                "authorUid": "z-ai",
                "description": {
                    "en-US": {"name": "GLM 4.7 coding model"},
                },
                "displayName": "GLM 4.7",
                "metaModelUid": "z-ai/glm-4.7",
                "minInputPrice": 40.0,
                "minOutputPrice": 160.0,
                "providerCount": 4,
                "series": "glm-4",
                "tagList": [],
            }
        ],
    }
    detail_payload = {
        "status": 200,
        "result": {
            "records": [
                {
                    "isAggregate": True,
                    "name": "[Aggregate]GLM-4.7",
                },
                {
                    "isAggregate": False,
                    "name": "[Z.AI]GLM-4.7(Quicker)",
                    "providerDisplayName": {
                        "en-US": {"name": "Z.ai"},
                    },
                },
            ]
        },
    }

    class DummyResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    def fake_get(url, *args, **kwargs):
        if "model-list" in url:
            return DummyResponse(detail_payload)
        return DummyResponse(payload)

    monkeypatch.setattr("ai_pricehub.services.requests.get", fake_get)

    catalog = service._fetch_primary_vendor_models(vendor)  # noqa: SLF001

    assert catalog["models"][0]["source_vendors"] == [
        "Zhipu AI",
        "Zhipu",
        "Z.AI",
        "zhipu",
        "Z.ai",
    ]


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
