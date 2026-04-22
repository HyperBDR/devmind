from __future__ import annotations

import hashlib
import logging
import os
import re
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)
_HEX_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _clean_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _stringify_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in metadata.items() if value is not None}


def _fallback_trace_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex()


def extract_message_text(value: Any) -> str:
    """Best-effort flattening of a result payload into text."""
    chunks: list[str] = []

    def visit(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            text = node.strip()
            if text:
                chunks.append(text)
            return
        if isinstance(node, dict):
            if "content" in node:
                visit(node.get("content"))
                return
            if "text" in node:
                visit(node.get("text"))
                return
            for key in ("output", "final", "response", "message"):
                if key in node:
                    visit(node.get(key))
            return
        if hasattr(node, "content"):
            visit(getattr(node, "content"))
            return
        if isinstance(node, list):
            for item in node:
                visit(item)
            return

    visit(value)
    return "\n".join(chunks).strip()


def _extract_langfuse_generation_output(response: Any) -> tuple[str, dict[str, int], str]:
    output_text = ""
    model_name = "unknown"
    usage: dict[str, int] = {}

    generations = getattr(response, "generations", None) or []
    if generations and generations[0]:
        generation = generations[0][0]
        message = getattr(generation, "message", None)
        if message is not None:
            output_text = extract_message_text(message)
            response_meta = getattr(message, "response_metadata", {}) or {}
            usage_meta = response_meta.get("token_usage", {}) if isinstance(response_meta, dict) else {}
            if isinstance(response_meta, dict):
                model_name = response_meta.get("model") or response_meta.get("model_name") or model_name
        else:
            output_text = str(getattr(generation, "text", "") or "")
            usage_meta = {}
    else:
        usage_meta = {}

    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        model_name = llm_output.get("model_name") or model_name
        usage_meta = llm_output.get("token_usage") or usage_meta

    if isinstance(usage_meta, dict):
        prompt_tokens = int(usage_meta.get("prompt_tokens") or usage_meta.get("input_tokens") or 0)
        completion_tokens = int(usage_meta.get("completion_tokens") or usage_meta.get("output_tokens") or 0)
        total_tokens = int(usage_meta.get("total_tokens") or (prompt_tokens + completion_tokens))
        usage = {
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": total_tokens,
        }

    return model_name, usage, output_text


def _load_langfuse_settings() -> dict[str, Any] | None:
    try:
        from core.settings.langfuse import (
            LANGFUSE_ENABLED,
            LANGFUSE_HOST,
            LANGFUSE_PUBLIC_KEY,
            LANGFUSE_SECRET_KEY,
            LANGFUSE_SAMPLE_RATE,
            LANGFUSE_TIMEOUT,
        )
    except ImportError:
        try:
            from backend.core.settings.langfuse import (
                LANGFUSE_ENABLED,
                LANGFUSE_HOST,
                LANGFUSE_PUBLIC_KEY,
                LANGFUSE_SECRET_KEY,
                LANGFUSE_SAMPLE_RATE,
                LANGFUSE_TIMEOUT,
            )
        except ImportError as exc:
            logger.warning("Langfuse tracing disabled: %s", exc)
            return None

    if not LANGFUSE_ENABLED or not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return None

    return {
        "public_key": str(LANGFUSE_PUBLIC_KEY),
        "secret_key": str(LANGFUSE_SECRET_KEY),
        "host": str(LANGFUSE_HOST),
        "sample_rate": LANGFUSE_SAMPLE_RATE,
        "timeout": LANGFUSE_TIMEOUT,
    }


def _configure_langfuse_env(config: dict[str, Any]) -> None:
    os.environ["LANGFUSE_PUBLIC_KEY"] = str(config["public_key"])
    os.environ["LANGFUSE_SECRET_KEY"] = str(config["secret_key"])
    os.environ["LANGFUSE_BASE_URL"] = str(config["host"])
    os.environ["LANGFUSE_SAMPLE_RATE"] = str(config.get("sample_rate", 1.0))
    os.environ["LANGFUSE_TIMEOUT"] = str(config.get("timeout", 10))


@dataclass
class ObservationLease:
    context_manager: Any
    observation: Any
    kind: str
    closed: bool = False

    def close(self, exc_type: type[BaseException] | None = None, exc: BaseException | None = None, tb: Any = None) -> None:
        if self.closed:
            return
        if hasattr(self.context_manager, "__exit__"):
            self.context_manager.__exit__(exc_type, exc, tb)
        self.closed = True


@dataclass
class LangfuseObserver:
    client: Any
    trace_id: str
    name: str
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        trace_seed: str,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> "LangfuseObserver" | None:
        config = _load_langfuse_settings()
        if config is None:
            return None

        try:
            from langfuse import get_client
        except ImportError as exc:
            logger.warning("Langfuse tracing disabled: %s", exc)
            return None

        try:
            _configure_langfuse_env(config)
            client = get_client()
            seed = str(trace_seed or "").strip()
            normalized_seed = seed.lower()

            if _HEX_TRACE_ID_RE.fullmatch(normalized_seed):
                trace_id = normalized_seed
            else:
                create_trace_id = getattr(client, "create_trace_id", None)
                if callable(create_trace_id):
                    trace_id = create_trace_id(seed=seed) if seed else create_trace_id()
                else:
                    trace_id = _fallback_trace_id(seed or name)

            return cls(
                client=client,
                trace_id=str(trace_id),
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
                tags=tags or [],
            )
        except Exception as exc:
            logger.warning("Langfuse tracing disabled: %s", exc)
            return None

    def current_trace_id(self) -> str:
        getter = getattr(self.client, "get_current_trace_id", None)
        if callable(getter):
            try:
                current = getter()
                if current:
                    return str(current)
            except Exception:
                logger.debug("Failed to read current Langfuse trace id.", exc_info=True)
        return self.trace_id

    @contextmanager
    def root_observation_scope(self, *, input_payload: Any = None) -> Iterator[Any]:
        root_ctx = self._start_root_observation(input_payload=input_payload)
        attrs_ctx = self._propagate_attributes_scope()
        try:
            with root_ctx as root_observation:
                with attrs_ctx:
                    yield root_observation
        finally:
            self.safe_flush()

    def start_generation_observation(
        self,
        *,
        name: str,
        input_payload: Any,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return self._start_observation(
            as_type="generation",
            name=name,
            input_payload=input_payload,
            metadata=metadata,
        )

    def start_tool_observation(
        self,
        *,
        name: str,
        input_payload: Any,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return self._start_observation(
            as_type="tool",
            name=name,
            input_payload=input_payload,
            metadata=metadata,
        )

    def end_observation(
        self,
        observation: Any,
        *,
        output: Any = None,
        level: str | None = None,
        status_message: str | None = None,
        model: str | None = None,
        usage_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if observation is None:
            return

        if isinstance(observation, ObservationLease):
            lease = observation
            target = lease.observation
        else:
            lease = None
            target = observation

        payload = _clean_payload(
            {
                "output": output,
                "level": level,
                "status_message": status_message,
                "model": model,
                "usage_details": usage_details,
                "metadata": metadata,
            }
        )
        minimal_payload = _clean_payload(
            {
                "output": output,
                "level": level,
                "status_message": status_message,
            }
        )

        for method_name in ("end", "update"):
            method = getattr(target, method_name, None)
            if not callable(method):
                continue
            try:
                method(**payload)
                break
            except TypeError:
                if minimal_payload:
                    try:
                        method(**minimal_payload)
                        break
                    except Exception:
                        logger.debug("Langfuse %s fallback payload failed.", method_name, exc_info=True)
            except Exception:
                logger.debug("Langfuse %s failed.", method_name, exc_info=True)

        if lease is not None:
            lease.close()

    def safe_flush(self) -> None:
        flush = getattr(self.client, "flush", None)
        if callable(flush):
            try:
                flush()
            except Exception:
                logger.debug("Langfuse flush failed.", exc_info=True)

    def _start_root_observation(self, *, input_payload: Any) -> Any:
        starter = getattr(self.client, "start_as_current_observation", None)
        if not callable(starter):
            return nullcontext(None)

        payload = _clean_payload(
            {
                "as_type": "agent",
                "name": self.name,
                "input": input_payload,
                "trace_context": {"trace_id": self.trace_id},
                "metadata": self.metadata or None,
                "tags": self.tags or None,
            }
        )
        try:
            context_or_observation = starter(**payload)
            if hasattr(context_or_observation, "__enter__"):
                return context_or_observation
            return nullcontext(context_or_observation)
        except Exception:
            logger.debug("Langfuse root observation setup failed.", exc_info=True)
            return nullcontext(None)

    def _propagate_attributes_scope(self):
        try:
            from langfuse import propagate_attributes
        except ImportError:
            return nullcontext()

        attributes = _clean_payload(
            {
                "trace_name": self.name,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "metadata": _stringify_metadata(self.metadata),
                "tags": self.tags or None,
            }
        )
        try:
            return propagate_attributes(**attributes)
        except Exception:
            logger.debug("Langfuse propagate_attributes failed.", exc_info=True)
            return nullcontext()

    def _start_observation(
        self,
        *,
        as_type: str,
        name: str,
        input_payload: Any,
        metadata: dict[str, Any] | None,
    ) -> Any:
        payload = _clean_payload(
            {
                "as_type": as_type,
                "name": name,
                "input": input_payload,
                "trace_context": {"trace_id": self.current_trace_id()},
                "metadata": metadata,
            }
        )

        starter = getattr(self.client, "start_observation", None)
        if callable(starter):
            try:
                return starter(**payload)
            except Exception:
                logger.debug("Langfuse start_observation failed for %s.", as_type, exc_info=True)

        starter = getattr(self.client, "start_as_current_observation", None)
        if not callable(starter):
            return None

        try:
            context_manager = starter(**payload)
            if hasattr(context_manager, "__enter__"):
                observation = context_manager.__enter__()
                return ObservationLease(
                    context_manager=context_manager,
                    observation=observation,
                    kind=as_type,
                )
            return ObservationLease(
                context_manager=nullcontext(),
                observation=context_manager,
                kind=as_type,
            )
        except Exception:
            logger.debug("Langfuse start_observation failed for %s.", as_type, exc_info=True)
            return None


class LangfuseAgentCallbackHandler(BaseCallbackHandler):
    """LangChain-core callback that records LLM calls as Langfuse generation observations."""

    def __init__(self, *, observer: LangfuseObserver, metadata: dict[str, Any]) -> None:
        self.observer = observer
        self.metadata = metadata
        self.inputs: dict[str, str] = {}
        self._generation_observations: dict[str, Any] = {}
        self._tool_observations: dict[str, Any] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        input_text = extract_message_text(messages)
        self.inputs[key] = input_text
        self._generation_observations[key] = self.observer.start_generation_observation(
            name="chat_model",
            input_payload=input_text,
            metadata={
                **self.metadata,
                "run_id": key,
                "parent_run_id": str(parent_run_id) if parent_run_id else "",
            },
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        model_name, usage, output_text = _extract_langfuse_generation_output(response)
        observation = self._generation_observations.pop(key, None)
        self.observer.end_observation(
            observation,
            output=output_text,
            model=model_name,
            usage_details=usage or None,
            metadata=self.metadata,
        )
        self.observer.safe_flush()

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        observation = self._generation_observations.pop(key, None)
        self.observer.end_observation(
            observation,
            output=None,
            level="ERROR",
            status_message=str(error),
            metadata=self.metadata,
        )
        self.observer.safe_flush()

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        input_text = extract_message_text(input_str)
        self.inputs[key] = input_text
        self._tool_observations[key] = self.observer.start_tool_observation(
            name=str(serialized.get("name") or serialized.get("id") or "tool"),
            input_payload=input_text,
            metadata={
                **self.metadata,
                "run_id": key,
                "parent_run_id": str(parent_run_id) if parent_run_id else "",
            },
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        observation = self._tool_observations.pop(key, None)
        self.observer.end_observation(
            observation,
            output=extract_message_text(output),
            metadata=self.metadata,
        )
        self.observer.safe_flush()

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        observation = self._tool_observations.pop(key, None)
        self.observer.end_observation(
            observation,
            output=None,
            level="ERROR",
            status_message=str(error),
            metadata=self.metadata,
        )
        self.observer.safe_flush()


class LangfuseRuntime:
    """Light wrapper that binds a root observation scope and callback handler."""

    def __init__(self, *, observer: LangfuseObserver, callback_handler: LangfuseAgentCallbackHandler) -> None:
        self.observer = observer
        self.callback_handler = callback_handler
        self._root_input: Any = None
        self._scope_cm: Any = None

    def set_root_input(self, input_payload: Any) -> None:
        self._root_input = input_payload

    def start_tool_observation(
        self,
        *,
        name: str,
        input_payload: Any,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return self.observer.start_tool_observation(
            name=name,
            input_payload=input_payload,
            metadata=metadata,
        )

    def end_observation(self, observation: Any, **kwargs: Any) -> None:
        self.observer.end_observation(observation, **kwargs)

    def safe_flush(self) -> None:
        self.observer.safe_flush()

    def __enter__(self) -> Any:
        self._scope_cm = self.observer.root_observation_scope(input_payload=self._root_input)
        return self._scope_cm.__enter__()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._scope_cm is None:
            return False
        return bool(self._scope_cm.__exit__(exc_type, exc, tb))


def build_langfuse_runtime(
    *,
    runner_name: str,
    record: Any,
    user_id: int | None,
    source_task_id: str | None,
) -> LangfuseRuntime | None:
    metadata = {
        "runner": runner_name,
        "source_task_id": source_task_id or "",
    }
    user_id_value = str(user_id) if user_id else None
    if user_id_value:
        metadata["user_id"] = user_id_value
    if record:
        metadata["record_id"] = getattr(record, "id", None) or str(record)
        metadata["record_trace_id"] = str(getattr(record, "trace_id", "") or "")

    trace_seed = str(getattr(record, "trace_id", "") or "") if record else ""
    observer = LangfuseObserver.create(
        name=runner_name,
        trace_seed=trace_seed,
        user_id=user_id_value,
        session_id=source_task_id or None,
        metadata=metadata,
        tags=["agent", "langgraph"],
    )
    if observer is None:
        return None

    callback_handler = LangfuseAgentCallbackHandler(observer=observer, metadata=metadata)
    return LangfuseRuntime(observer=observer, callback_handler=callback_handler)


def create_langfuse_observer(**kwargs: Any) -> LangfuseObserver | None:
    return LangfuseObserver.create(**kwargs)
