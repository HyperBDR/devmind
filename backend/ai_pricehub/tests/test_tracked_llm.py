import pytest

from ai_pricehub import tracked_llm
from ai_pricehub.extraction import ExtractedPricingCatalog


@pytest.mark.unit
def test_invoke_tracked_structured_llm_uses_llmtracker_with_model_uuid(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        tracked_llm,
        "resolve_parser_llm_settings",
        lambda preferred_config_uuid=None: {
            "config_uuid": "cfg-123",
            "label": "Parser Model",
            "source": "selected",
            "provider": "openai_compatible",
            "model": "model-a",
            "api_key": "secret",
            "api_base": "https://example.com",
        },
    )
    monkeypatch.setattr(
        tracked_llm.LLMTracker,
        "call_and_track",
        lambda **kwargs: (
            calls.update(kwargs)
            or ('{"models":[{"model_name":"DeepSeek-V3.2","aliases":["DeepSeek-V3.2"],"family":"text","currency":"CNY"}]}', {"total_tokens": 12})
        ),
    )

    result, usage, settings = tracked_llm.invoke_tracked_structured_llm(
        schema=ExtractedPricingCatalog,
        messages=[{"role": "user", "content": "extract"}],
        preferred_config_uuid="cfg-123",
        node_name="test_node",
        state={"source_type": "ai_pricehub"},
    )

    assert result.models[0].model_name == "DeepSeek-V3.2"
    assert usage["total_tokens"] == 12
    assert settings["config_uuid"] == "cfg-123"
    assert calls["model_uuid"] == "cfg-123"
    assert calls["json_mode"] is True


@pytest.mark.unit
def test_invoke_tracked_structured_llm_uses_tracked_fallback_without_model_uuid(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        tracked_llm,
        "resolve_parser_llm_settings",
        lambda preferred_config_uuid=None: {
            "config_uuid": "",
            "label": "Env Model",
            "source": "settings",
            "provider": "openai_compatible",
            "model": "model-b",
            "api_key": "secret",
            "api_base": "https://example.com",
        },
    )
    monkeypatch.setattr(
        tracked_llm,
        "build_litellm_params_from_config",
        lambda provider, config: {
            "model": config["model"],
            "api_key": config["api_key"],
            "api_base": config["api_base"],
        },
    )
    monkeypatch.setattr(
        tracked_llm.LLMTracker,
        "_call_and_track_non_stream_once",
        lambda **kwargs: (
            captured.update(kwargs)
            or ('{"models":[{"model_name":"Qwen3","aliases":["Qwen3"],"family":"text","currency":"CNY"}]}', {"total_tokens": 7})
        ),
    )

    result, usage, settings = tracked_llm.invoke_tracked_structured_llm(
        schema=ExtractedPricingCatalog,
        messages=[{"role": "user", "content": "extract"}],
        preferred_config_uuid=None,
        node_name="test_node",
        state={"source_type": "ai_pricehub"},
    )

    assert result.models[0].model_name == "Qwen3"
    assert usage["total_tokens"] == 7
    assert settings["source"] == "settings"
    assert captured["params"]["model"] == "model-b"
    assert captured["params"]["response_format"] == {"type": "json_object"}
