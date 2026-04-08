import importlib.util
from pathlib import Path

import pytest


def _load_aliyun_pricing_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "pricing-vendor-agent"
        / "scripts"
        / "vendor_pricing_aliyun.py"
    )
    spec = importlib.util.spec_from_file_location("test_vendor_pricing_aliyun", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


aliyun_pricing = _load_aliyun_pricing_module()


@pytest.mark.unit
def test_extract_table_text_prefers_td_rows():
    html = """
    <html>
      <body>
        <p>noise text</p>
        <table>
          <tr><th>模型名称</th><th>输入单价（每百万Token）</th><th>输出单价（每百万Token）</th></tr>
          <tr><td>DeepSeek-V3.2</td><td>2 元</td><td>3 元</td></tr>
          <tr><td>Qwen3</td><td>1 元</td><td>4 元</td></tr>
        </table>
      </body>
    </html>
    """

    table_text = aliyun_pricing._extract_table_text(html)  # noqa: SLF001

    assert "模型名称 | 输入单价（每百万Token） | 输出单价（每百万Token）" in table_text
    assert "DeepSeek-V3.2 | 2 元 | 3 元" in table_text
    assert "Qwen3 | 1 元 | 4 元" in table_text
    assert "noise text" not in table_text


@pytest.mark.unit
def test_resolve_aliyun_pricing_url_prefers_static_help_page_by_default():
    vendor = {
        "slug": "aliyun",
        "pricing_url": "https://bailian.console.aliyun.com/cn-beijing/?tab=doc#/doc/?type=model&url=2987148",
    }

    resolved = aliyun_pricing._resolve_aliyun_pricing_url(vendor)  # noqa: SLF001

    assert resolved == "https://help.aliyun.com/zh/model-studio/model-pricing"


@pytest.mark.unit
def test_resolve_target_models_uses_primary_model_queries():
    vendor = {
        "_primary_model_queries": [
            "qwen3-235b-a22b-instruct-2507",
            "DeepSeek-V3.2",
            "qwen3-235b-a22b-instruct-2507",
        ]
    }

    resolved = aliyun_pricing._resolve_target_models(vendor)  # noqa: SLF001

    assert resolved == [
        "qwen3-235b-a22b-instruct-2507",
        "deepseek-v3.2",
    ]


@pytest.mark.unit
def test_resolve_target_models_filters_out_description_like_queries():
    vendor = {
        "_primary_model_queries": [
            "GLM-4.7",
            "z-ai/glm-4.7",
            "A professional model focused on programming and agent capabilities.",
            "qwen/qwen-plus",
        ]
    }

    resolved = aliyun_pricing._resolve_target_models(vendor)  # noqa: SLF001

    assert resolved == [
        "glm-4.7",
        "z-ai/glm-4.7",
        "qwen/qwen-plus",
    ]


@pytest.mark.unit
def test_sync_vendor_catalog_reports_api_only_attempt_state(monkeypatch):
    monkeypatch.setattr(
        aliyun_pricing,
        "_query_models_via_api",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        aliyun_pricing,
        "_extract_models_from_api_payloads",
        lambda **kwargs: [],
    )

    result = aliyun_pricing.sync_vendor_catalog(
        {
            "_primary_model_queries": ["QwQ-Plus"],
            "acquisition": {"method": "api", "cookie": "test-cookie"},
        }
    )

    assert result["raw_payload"]["api_attempted"] is True
    assert result["raw_payload"]["api_used"] is False
    assert result["raw_payload"]["page_fallback_used"] is False


@pytest.mark.unit
def test_sync_vendor_catalog_falls_back_to_public_pricing_page_without_cookie(monkeypatch):
    monkeypatch.setattr(
        aliyun_pricing,
        "_fetch_text",
        lambda url: "<html>public pricing page</html>",
    )
    monkeypatch.setattr(
        aliyun_pricing,
        "_extract_models_deterministic",
        lambda html: [
            {
                "model_name": "qwen-plus",
                "aliases": ["qwen-plus"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 0.8,
                "output_price_per_million": 2.0,
                "market_scope": "domestic",
                "notes": "Aliyun China mainland pricing row for mode default.",
            }
        ],
    )

    result = aliyun_pricing.sync_vendor_catalog(
        {
            "_primary_model_queries": ["qwen-plus"],
            "acquisition": {"method": "api"},
        }
    )

    assert result["models"] == [
        {
            "model_name": "qwen-plus",
            "aliases": ["qwen-plus"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 0.8,
            "output_price_per_million": 2.0,
            "market_scope": "domestic",
            "notes": "Aliyun China mainland pricing row for mode default.",
        }
    ]
    assert result["raw_payload"]["api_attempted"] is True
    assert result["raw_payload"]["api_used"] is False
    assert result["raw_payload"]["page_fallback_used"] is True
    assert "Aliyun API cookie is required" in (result["raw_payload"]["api_error"] or "")


@pytest.mark.unit
def test_sync_vendor_catalog_merges_public_page_models_when_api_is_partial(monkeypatch):
    monkeypatch.setattr(
        aliyun_pricing,
        "_query_models_via_api",
        lambda **kwargs: [{"model_query": "qwen-plus", "payload": {"ok": True}}],
    )
    monkeypatch.setattr(
        aliyun_pricing,
        "_extract_models_from_api_payloads",
        lambda **kwargs: [
            {
                "model_name": "qwen-plus",
                "aliases": ["qwen-plus"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 0.8,
                "output_price_per_million": 2.0,
                "market_scope": "domestic",
                "notes": "API domestic price.",
            }
        ],
    )
    monkeypatch.setattr(
        aliyun_pricing,
        "_fetch_text",
        lambda url: "<html>public pricing page</html>",
    )
    monkeypatch.setattr(
        aliyun_pricing,
        "_extract_models_deterministic",
        lambda html: [
            {
                "model_name": "qwen-plus",
                "aliases": ["qwen-plus"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 0.8,
                "output_price_per_million": 2.0,
                "market_scope": "domestic",
                "notes": "Page domestic price.",
            },
            {
                "model_name": "qwen2.5-7b-instruct",
                "aliases": ["qwen2.5-7b-instruct"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 0.5,
                "output_price_per_million": 1.0,
                "market_scope": "domestic",
                "notes": "Page-only domestic price.",
            },
        ],
    )

    result = aliyun_pricing.sync_vendor_catalog(
        {
            "_primary_model_queries": ["qwen-plus", "qwen2.5-7b-instruct"],
            "acquisition": {"method": "api", "cookie": "test-cookie"},
        }
    )

    assert result["models"] == [
        {
            "model_name": "qwen-plus",
            "aliases": ["qwen-plus"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 0.8,
            "output_price_per_million": 2.0,
            "market_scope": "domestic",
            "notes": "API domestic price.",
        },
        {
            "model_name": "qwen2.5-7b-instruct",
            "aliases": ["qwen2.5-7b-instruct"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 0.5,
            "output_price_per_million": 1.0,
            "market_scope": "domestic",
            "notes": "Page-only domestic price.",
        },
    ]
    assert result["raw_payload"]["api_used"] is True
    assert result["raw_payload"]["page_fallback_used"] is True


@pytest.mark.unit
def test_build_api_form_data_uses_model_query_and_region():
    payload = aliyun_pricing._build_api_form_data(  # noqa: SLF001
        region="cn-beijing",
        model_query="qwen3-235b-a22b-instruct-2507",
    )

    assert payload["region"] == "cn-beijing"
    params = payload["params"]
    assert "qwen3-235b-a22b-instruct-2507" in params
    assert "queryPrice" in params
    assert "cn-beijing" in params


@pytest.mark.unit
def test_finalize_models_keeps_highest_range_price_per_market_scope():
    models = aliyun_pricing._finalize_models(  # noqa: SLF001
        [
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.0,
                "output_price_per_million": 4.0,
                "market_scope": "domestic",
                "notes": "range 0-32k",
            },
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 2.0,
                "output_price_per_million": 8.0,
                "market_scope": "domestic",
                "notes": "range 32k-128k",
            },
        ]
    )

    assert models == [
        {
            "model_name": "qwen3-235b-a22b-instruct-2507",
            "aliases": ["qwen3-235b-a22b-instruct-2507"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 8.0,
            "market_scope": "domestic",
            "notes": "range 32k-128k",
        }
    ]


@pytest.mark.unit
def test_finalize_models_keeps_only_domestic_records():
    models = aliyun_pricing._finalize_models(  # noqa: SLF001
        [
            {
                "model_name": "DeepSeek-V3.2",
                "aliases": ["DeepSeek-V3.2"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 2.0,
                "output_price_per_million": 3.0,
                "market_scope": "domestic",
                "notes": "China mainland standard",
            },
            {
                "model_name": "DeepSeek-V3.2",
                "aliases": ["DeepSeek-V3.2"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.688,
                "output_price_per_million": 6.752,
                "market_scope": "international",
                "notes": "International standard",
            },
            {
                "model_name": "DeepSeek-V3.2",
                "aliases": ["DeepSeek-V3.2"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.5,
                "output_price_per_million": 5.0,
                "market_scope": "global",
                "notes": "Global standard",
            },
        ]
    )

    assert models == [
        {
            "model_name": "DeepSeek-V3.2",
            "aliases": ["DeepSeek-V3.2"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 3.0,
            "market_scope": "domestic",
            "notes": "China mainland standard",
        }
    ]


@pytest.mark.unit
def test_merge_models_prefers_primary_domestic_price():
    models = aliyun_pricing._merge_models(  # noqa: SLF001
        primary_items=[
            {
                "model_name": "Qwen3-235B-A22B-Instruct-2507",
                "aliases": ["Qwen3-235B-A22B-Instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 2.0,
                "output_price_per_million": 8.0,
                "market_scope": "domestic",
                "notes": "Deterministic domestic row",
            }
        ],
        supplemental_items=[
            {
                "model_name": "Qwen3-235B-A22B-Instruct-2507",
                "aliases": ["Qwen3-235B-A22B-Instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.688,
                "output_price_per_million": 6.752,
                "market_scope": "unknown",
                "notes": "LLM extracted price",
            }
        ],
    )

    assert models == [
        {
            "model_name": "Qwen3-235B-A22B-Instruct-2507",
            "aliases": ["Qwen3-235B-A22B-Instruct-2507"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 8.0,
            "market_scope": "domestic",
            "notes": "Deterministic domestic row",
        }
    ]


@pytest.mark.unit
def test_extract_models_deterministic_infers_domestic_scope_from_preceding_context():
    html = """
    <html>
      <body>
        <div>中国内地</div>
        <table>
          <tr><th>模型名称</th><th>模式</th><th>输入单价（每百万Token）</th><th>输出单价（每百万Token）</th></tr>
          <tr><td>Qwen3-235B-A22B-Instruct-2507</td><td>仅非思考模式</td><td>2 元</td><td>8 元</td></tr>
        </table>
        <div>全球</div>
        <table>
          <tr><th>模型名称</th><th>模式</th><th>输入单价（每百万Token）</th><th>输出单价（每百万Token）</th></tr>
          <tr><td>Qwen3-235B-A22B-Instruct-2507</td><td>仅非思考模式</td><td>1.688 元</td><td>6.752 元</td></tr>
        </table>
      </body>
    </html>
    """

    models = aliyun_pricing._extract_models_deterministic(html)  # noqa: SLF001

    assert models == [
        {
            "model_name": "Qwen3-235B-A22B-Instruct-2507",
            "aliases": ["Qwen3-235B-A22B-Instruct-2507"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 8.0,
            "market_scope": "domestic",
            "notes": "Aliyun China mainland pricing row for mode 仅非思考模式.",
        }
    ]


@pytest.mark.unit
def test_finalize_models_prefers_higher_unknown_price_when_same_model_appears_multiple_times():
    models = aliyun_pricing._finalize_models(  # noqa: SLF001
        [
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.688,
                "output_price_per_million": 6.752,
                "market_scope": "unknown",
                "notes": "Aliyun default pricing row for mode 仅非思考模式.",
            },
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 2.0,
                "output_price_per_million": 8.0,
                "market_scope": "unknown",
                "notes": "Aliyun default pricing row for mode 仅非思考模式.",
            },
        ]
    )

    assert models == [
        {
            "model_name": "qwen3-235b-a22b-instruct-2507",
            "aliases": ["qwen3-235b-a22b-instruct-2507"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 8.0,
            "market_scope": "unknown",
            "notes": "Aliyun default pricing row for mode 仅非思考模式.",
        }
    ]


@pytest.mark.unit
def test_finalize_models_prefers_higher_domestic_price_when_same_model_appears_multiple_times():
    models = aliyun_pricing._finalize_models(  # noqa: SLF001
        [
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 1.688,
                "output_price_per_million": 6.752,
                "market_scope": "domestic",
                "notes": "Aliyun China mainland pricing row for mode 仅非思考模式.",
            },
            {
                "model_name": "qwen3-235b-a22b-instruct-2507",
                "aliases": ["qwen3-235b-a22b-instruct-2507"],
                "family": "text",
                "currency": "CNY",
                "input_price_per_million": 2.0,
                "output_price_per_million": 8.0,
                "market_scope": "domestic",
                "notes": "Aliyun China mainland pricing row for mode 仅非思考模式.",
            },
        ]
    )

    assert models == [
        {
            "model_name": "qwen3-235b-a22b-instruct-2507",
            "aliases": ["qwen3-235b-a22b-instruct-2507"],
            "family": "text",
            "currency": "CNY",
            "input_price_per_million": 2.0,
            "output_price_per_million": 8.0,
            "market_scope": "domestic",
            "notes": "Aliyun China mainland pricing row for mode 仅非思考模式.",
        }
    ]
