from __future__ import annotations

from typing import Any, Optional, TypeVar

from agentcore_metering.adapters.django.services.litellm_params import (
    build_litellm_params_from_config,
)
from agentcore_metering.adapters.django.trackers.llm import (
    LLMTracker,
    _repair_json_obj,
)

from ai_pricehub.llm_config import resolve_parser_llm_settings

SchemaT = TypeVar("SchemaT")


def build_tracking_state(
    *,
    record_id: int,
    trace_id: str,
    node_name: str,
    source_task_id: str = "",
    user_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    state = {
        "node_name": node_name,
        "source_type": "recharge_approval",
        "source_task_id": source_task_id,
        "metadata": {
            "trace_id": trace_id,
            "source_record_id": record_id,
            "stage": node_name,
        },
    }
    if user_id is not None:
        state["user_id"] = user_id
    if metadata:
        state["metadata"].update(metadata)
    return state


def invoke_tracked_structured_llm(
    *,
    schema: type[SchemaT],
    messages: Any,
    preferred_config_uuid: Optional[str],
    node_name: str,
    state: Optional[dict[str, Any]] = None,
    max_tokens: int = 4000,
    temperature: float = 0,
) -> tuple[SchemaT, dict[str, Any], dict[str, Any]]:
    llm_settings = resolve_parser_llm_settings(preferred_config_uuid)
    config_uuid = str(llm_settings.get("config_uuid") or "").strip()

    if config_uuid:
        content, usage = LLMTracker.call_and_track(
            messages=messages,
            json_mode=True,
            json_repair=True,
            max_tokens=max_tokens,
            temperature=temperature,
            node_name=node_name,
            state=state,
            model_uuid=config_uuid,
        )
    else:
        provider = str(
            llm_settings.get("provider") or "openai_compatible"
        ).strip().lower()
        config = {
            "model": llm_settings.get("model") or "",
            "api_key": llm_settings.get("api_key") or "",
            "api_base": llm_settings.get("api_base") or "",
        }
        params = build_litellm_params_from_config(provider, config)
        params["messages"] = messages
        params["response_format"] = {"type": "json_object"}
        params["max_tokens"] = max_tokens
        params["temperature"] = temperature
        effective_state = {
            **(state or {}),
            "node_name": (state or {}).get("node_name") or node_name,
        }
        content, usage = LLMTracker._call_and_track_non_stream_once(
            params=params,
            effective_state=effective_state,
            node_name=node_name,
            state=state,
            model=str(params.get("model") or "unknown"),
        )
        content = _repair_json_obj(content)

    parsed = schema.model_validate_json(content)
    return parsed, usage, llm_settings
