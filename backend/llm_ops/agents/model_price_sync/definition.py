"""DeepAgent definition for LLM Ops model price synchronization."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from agent_runner import AgentRunner, SkillSpec
from llm_ops.global_config import (
    price_sync_source_queryset,
    selected_price_collection_sources,
)
from llm_ops.llm_config import resolve_price_sync_llm_settings
from llm_ops.models import LLMOpsGlobalConfig, PriceCollectionSource
from llm_ops.source_collectors import (
    collect_price_source,
    source_supports_code_collection,
)

logger = logging.getLogger(__name__)


def _message_content(content: Any) -> Any:
    """Return message content in a LiteLLM-compatible shape."""
    if isinstance(content, (str, list)):
        return content
    if content is None:
        return ""
    return str(content)


def _normalize_tool_call(raw_call: Any) -> dict[str, Any] | None:
    """Return an OpenAI-compatible tool call payload."""
    if not raw_call:
        return None
    if isinstance(raw_call, dict):
        if "function" in raw_call:
            return raw_call
        call_id = raw_call.get("id")
        name = raw_call.get("name")
        args = raw_call.get("args") or raw_call.get("arguments") or {}
    else:
        call_id = getattr(raw_call, "id", None)
        name = getattr(raw_call, "name", None)
        args = getattr(raw_call, "args", None) or {}
    if not name:
        return None
    if not isinstance(args, str):
        args = json.dumps(args, ensure_ascii=False)
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args or "{}"},
    }


def _message_to_litellm(message: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain message to a LiteLLM message dict."""
    message_type = getattr(message, "type", "")
    role_map = {
        "ai": "assistant",
        "human": "user",
        "system": "system",
        "tool": "tool",
    }
    payload = {
        "role": role_map.get(message_type, message_type or "user"),
        "content": _message_content(getattr(message, "content", "")),
    }
    if message_type == "tool":
        tool_call_id = getattr(message, "tool_call_id", "")
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
    if message_type == "ai":
        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        raw_tool_calls = (
            additional_kwargs.get("tool_calls")
            or getattr(message, "tool_calls", None)
            or []
        )
        tool_calls = [
            item for item in (_normalize_tool_call(c) for c in raw_tool_calls)
            if item
        ]
        if tool_calls:
            payload["tool_calls"] = tool_calls
    return payload


def _tool_to_litellm_schema(tool_item: Any) -> dict[str, Any]:
    """Convert a LangChain tool into an OpenAI-compatible tool schema."""
    if isinstance(tool_item, dict):
        return tool_item
    try:
        from langchain_core.utils.function_calling import (
            convert_to_openai_tool,
        )

        return convert_to_openai_tool(tool_item)
    except Exception:
        args_schema = getattr(tool_item, "args_schema", None)
        if args_schema is not None and hasattr(
            args_schema,
            "model_json_schema",
        ):
            parameters = args_schema.model_json_schema()
        else:
            parameters = {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": getattr(tool_item, "name", ""),
                "description": getattr(tool_item, "description", "") or "",
                "parameters": parameters,
            },
        }


class LiteLLMTrackedChatModel(BaseChatModel):
    """LangChain chat model backed by agentcore-metering LiteLLM calls."""

    provider: str = "openai_compatible"
    model_name: str = ""
    config_uuid: str = ""
    config_payload: dict[str, Any] = Field(default_factory=dict)
    node_name: str = "llm_ops_model_price_sync_agent"
    user_id: int | None = None
    temperature: float = 0
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None

    @property
    def _llm_type(self) -> str:
        """Return the LangChain model type identifier."""
        return "agentcore_litellm_tracked_chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        """Return stable params for tracing and cache keys."""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "config_uuid": self.config_uuid,
        }

    def bind_tools(
        self,
        tools: list[Any],
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> "LiteLLMTrackedChatModel":
        """Bind tool schemas for DeepAgent tool-calling runs."""
        del kwargs
        return self.model_copy(
            update={
                "bound_tools": [_tool_to_litellm_schema(t) for t in tools],
                "tool_choice": tool_choice,
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Call LiteLLM through agentcore-metering and return a chat result."""
        del run_manager
        from agentcore_metering.adapters.django.services import (
            litellm_params,
        )
        from agentcore_metering.adapters.django.trackers.llm import LLMTracker

        litellm_messages = [_message_to_litellm(m) for m in messages]
        state: dict[str, Any] = {"node_name": self.node_name}
        if self.user_id is not None:
            state["user_id"] = self.user_id

        max_tokens = kwargs.get("max_tokens")
        temperature = kwargs.get("temperature", self.temperature)
        tools = kwargs.get("tools") or self.bound_tools or None
        tool_choice = kwargs.get("tool_choice", self.tool_choice)

        if self.config_uuid:
            message_payload, usage = LLMTracker.call_and_track(
                messages=litellm_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                node_name=self.node_name,
                state=state,
                model_uuid=self.config_uuid,
                tools=tools,
                tool_choice=tool_choice,
                return_message=True,
            )
        else:
            params = litellm_params.build_litellm_params_from_config(
                self.provider,
                self.config_payload,
            )
            params["messages"] = litellm_messages
            params["temperature"] = temperature
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            if stop:
                params["stop"] = stop
            if tools:
                params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice
            call_once = LLMTracker._call_and_track_non_stream_once
            message_payload, usage = call_once(
                params=params,
                effective_state=state,
                node_name=self.node_name,
                state=state,
                model=str(params.get("model") or self.model_name),
                return_message=True,
            )

        tool_calls = message_payload.get("tool_calls") or []
        message = AIMessage(
            content=message_payload.get("content") or "",
            additional_kwargs={"tool_calls": tool_calls} if tool_calls else {},
            response_metadata={
                "model_name": usage.get("model") or self.model_name,
                "token_usage": usage,
            },
        )
        generation = ChatGeneration(message=message)
        return ChatResult(
            generations=[generation],
            llm_output={
                "model_name": usage.get("model") or self.model_name,
                "token_usage": usage,
            },
        )


def _load_skill_tools_module():
    """Load the model price sync skill tools from the skill directory."""
    import importlib.util
    import sys

    tools_path = _skill_dir() / "tools.py"
    module_name = "llm_ops_model_price_sync_skill_tools"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load skill tools: {tools_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _skill_dir() -> Path:
    """Return the model price sync skill directory."""
    return Path(__file__).resolve().parents[2] / "skills" / "model-price-sync"


def build_llm_ops_agent_model(
    config: LLMOpsGlobalConfig | None = None,
    user_id: int | None = None,
) -> BaseChatModel:
    """Build the chat model from the admin-managed LLM config."""
    preferred_uuid = ""
    if config is not None:
        preferred_uuid = str(config.price_sync_llm_config_uuid or "")
    llm_settings = resolve_price_sync_llm_settings(preferred_uuid)
    provider = str(
        llm_settings.get("provider") or "openai_compatible"
    ).strip().lower()
    if provider in {"google", "google_genai"}:
        provider = "gemini"
    model_name = str(llm_settings.get("model") or "").strip()
    if not model_name:
        raise ValueError("LLM Ops price sync Agent model is not configured.")

    api_key = llm_settings.get("api_key") or ""
    api_base = llm_settings.get("api_base") or ""
    config_payload = dict(llm_settings.get("config") or {})
    config_payload.update(
        {
            "model": model_name,
            "api_key": api_key,
            "api_base": api_base,
        }
    )
    if provider == "azure_openai":
        config_payload.setdefault(
            "deployment",
            config_payload.get("azure_deployment")
            or config_payload.get("deployment_name")
            or model_name,
        )
        config_payload.setdefault(
            "api_version",
            config_payload.get("api_ver") or "2024-02-01",
        )

    return LiteLLMTrackedChatModel(
        provider=provider,
        model_name=model_name,
        config_uuid=str(llm_settings.get("config_uuid") or ""),
        config_payload=config_payload,
        user_id=user_id,
        temperature=0,
    )


class ModelPriceSyncAgentResult(BaseModel):
    """Structured response emitted by the model price sync Agent."""

    success: bool = True
    sources: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    source_results: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class ModelPriceSyncAgentRunner(AgentRunner):
    """DeepAgent runner that synchronizes configured model price sources."""

    SKILL_DIRS = [_skill_dir()]
    SKILL_dirs = SKILL_DIRS

    def __init__(
        self,
        *,
        config: LLMOpsGlobalConfig | None = None,
        source_ids: list[int] | None = None,
        verify_source: bool = True,
        user_id: int | None = None,
        source_task_id: str | None = None,
    ) -> None:
        super().__init__(
            record=None,
            user_id=user_id,
            source_task_id=source_task_id,
        )
        self.config = config
        self.source_ids = source_ids
        self.verify_source = verify_source
        self._sources: list[PriceCollectionSource] | None = None
        self.source_results: dict[str, Any] = {}
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self._agent_model: BaseChatModel | None = None

    def build_system_prompt_fragments(self) -> list[str]:
        skill_md = (_skill_dir() / "SKILL.md").read_text(encoding="utf-8")
        return [
            "You are the DevMind LLM Ops model price sync Agent.",
            f"## Skill: model-price-sync\n\n{skill_md}",
        ]

    def build_skill_specs(self) -> list[SkillSpec]:
        spec = SkillSpec.load_from_skill_dir(_skill_dir())
        spec.model = self._get_agent_model()
        return [spec]

    def build_tools(self) -> list[BaseTool]:
        return []

    def get_skill_tools(
        self,
        skill_name: str,
    ) -> list[BaseTool] | type[NotImplemented]:
        if skill_name != "model-price-sync":
            return NotImplemented

        module = _load_skill_tools_module()
        return module.build_model_price_sync_tools(self)

    def build_user_context(self) -> str:
        config = self.config or LLMOpsGlobalConfig.get_solo()
        context = {
            "price_collection_enabled": config.price_collection_enabled,
            "configured_source_ids": self.source_ids,
            "verify_source": self.verify_source,
        }
        return (
            "Synchronize configured LLM Ops model price sources.\n"
            "Call the model-price-sync skill and return structured JSON.\n\n"
            f"Context:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    def get_llm_model(self) -> BaseChatModel:
        return self._get_agent_model()

    def get_response_format(self) -> type[ModelPriceSyncAgentResult]:
        return ModelPriceSyncAgentResult

    def execute(self) -> dict[str, Any]:
        """Run the Agent only when there is work requiring an LLM."""
        sources = self.list_configured_sources()
        if not sources:
            return self._current_result(sources)
        if not any(
            source.is_enabled and source.updates_model_prices
            for source in sources
        ):
            for source in sources:
                key = source.slug or str(source.id)
                if key not in self.source_results:
                    self.skipped += 1
                    self.source_results[key] = {"skipped": True}
            return self._current_result(sources)
        if all(source_supports_code_collection(source) for source in sources):
            for source in sources:
                self.collect_source(source.id)
            return self._current_result(sources)
        return super().execute()

    def list_configured_sources(self) -> list[PriceCollectionSource]:
        """Return sources selected for this Agent run."""
        if self._sources is not None:
            return self._sources
        if self.source_ids is not None:
            self._sources = self._sources_by_ids(self.source_ids)
            return self._sources

        config = self.config or LLMOpsGlobalConfig.get_solo()
        if not config.price_collection_enabled:
            self._sources = []
            return self._sources
        self._sources = selected_price_collection_sources(config)
        return self._sources

    def _get_agent_model(self) -> BaseChatModel:
        """Return one cached chat model for the main Agent and skill."""
        if self._agent_model is None:
            config = self.config or LLMOpsGlobalConfig.get_solo()
            self._agent_model = build_llm_ops_agent_model(
                config,
                user_id=self.user_id,
            )
        return self._agent_model

    def collect_source(self, source_id: int) -> dict[str, Any]:
        """Collect and persist one configured source."""
        source = self._source_by_id(source_id)
        key = source.slug or str(source.id)
        if not source.is_enabled or not source.updates_model_prices:
            self.skipped += 1
            self.source_results[key] = {"skipped": True}
            return self.source_results[key]

        try:
            result = collect_price_source(
                source,
                verify_source=self.verify_source,
            )
        except Exception as exc:
            self.failed += 1
            self.source_results[key] = {
                "success": False,
                "error": str(exc),
            }
            return self.source_results[key]

        self.succeeded += 1
        self.source_results[key] = result
        return result

    def collect_source_catalog(self, source_id: int) -> dict[str, Any]:
        """Collect standard catalog JSON without persisting prices."""
        from llm_ops.collection_services import (
            collect_official_provider_standard_catalog,
        )

        source = self._source_by_id(source_id)
        if not source.is_enabled or not source.updates_model_prices:
            return {"skipped": True}
        if not source.provider_id:
            raise ValueError("Price source does not have a provider.")
        return collect_official_provider_standard_catalog(
            provider=source.provider,
            source=source,
            verify_source=self.verify_source,
        )

    def recover_structured_response(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._current_result(self.list_configured_sources())

    def _current_result(
        self,
        sources: list[PriceCollectionSource],
    ) -> dict[str, Any]:
        """Return the current structured sync result."""
        return {
            "success": self.failed == 0,
            "sources": len(sources),
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "source_results": self.source_results,
            "error_message": "",
        }

    def record_llm_run(
        self,
        runner_type: str,
        provider: str,
        model: str,
        input_snapshot: str,
        output_snapshot: str,
        usage_payload: dict[str, Any],
        stdout: str,
        stderr: str,
        started_at: Any,
        finished_at: Any,
        success: bool,
        **kwargs: Any,
    ) -> None:
        logger.info(
            "llm_ops model price sync Agent LLM run provider=%s model=%s",
            provider,
            model,
        )

    def record_event(
        self,
        event_type: str,
        stage: str,
        source: str,
        message: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        logger.info(
            "llm_ops model price sync Agent event type=%s stage=%s "
            "source=%s message=%s payload=%s",
            event_type,
            stage,
            source,
            message,
            payload or {},
        )

    def _source_by_id(self, source_id: int) -> PriceCollectionSource:
        sources = {
            source.id: source
            for source in self.list_configured_sources()
        }
        try:
            normalized_id = int(source_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("source_id must be an integer.") from exc
        source = sources.get(normalized_id)
        if source is None:
            raise ValueError("Source is not selected for this Agent run.")
        return source

    @staticmethod
    def _sources_by_ids(source_ids: list[int]) -> list[PriceCollectionSource]:
        normalized = []
        for value in source_ids:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                continue
        if not normalized:
            return []
        source_map = {
            source.id: source
            for source in price_sync_source_queryset()
            .filter(id__in=normalized)
            .select_related("provider", "channel")
        }
        return [
            source_map[source_id]
            for source_id in normalized
            if source_id in source_map
        ]


def execute_model_price_sync_agent(
    *,
    source_ids: list[int] | None = None,
    verify_source: bool = True,
    user_id: int | None = None,
    source_task_id: str | None = None,
) -> dict[str, Any]:
    """Execute the runtime model price sync Agent."""
    runner = ModelPriceSyncAgentRunner(
        source_ids=source_ids,
        verify_source=verify_source,
        user_id=user_id,
        source_task_id=source_task_id,
    )
    return runner.execute()
