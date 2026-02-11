"""
LLM call tracker for easy-divine.

Provides unified interface for LLM API calls with automatic usage
tracking and cost analysis.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction

from llm_tracker.llm_service import get_llm_service
from llm_tracker.models import LLMUsage

logger = logging.getLogger(__name__)


class LLMTracker:
    """
    Unified LLM API call tracker.

    Wraps LLM API calls to automatically extract and record token
    usage information for cost analysis and monitoring.
    """

    @staticmethod
    def call_and_track(
        messages: list,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[Dict] = None,
        node_name: str = "unknown",
        state: Optional[Dict] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Call LLM API with automatic usage tracking and logging.

        LLM params (first): messages, json_mode, max_tokens, temperature,
        response_format. Tracking (last): node_name, state.

        Returns:
            (response_content, usage_dict)

        Raises:
            ValueError: If messages are empty or response is empty
        """
        if not messages:
            raise ValueError("Messages cannot be empty")

        llm_service = get_llm_service()

        if max_tokens is None:
            provider = getattr(settings, "LLM_PROVIDER", "openai").lower()
            if provider == "azure_openai":
                config = getattr(settings, "AZURE_OPENAI_CONFIG", {})
                max_tokens = config.get("max_tokens", 60000)
            elif provider == "gemini":
                config = getattr(settings, "GEMINI_CONFIG", {})
                max_tokens = config.get("max_tokens", 60000)
            else:
                config = getattr(settings, "OPENAI_CONFIG", {})
                max_tokens = config.get("max_tokens", 60000)

        if temperature is None:
            provider = getattr(settings, "LLM_PROVIDER", "openai").lower()
            if provider == "azure_openai":
                config = getattr(settings, "AZURE_OPENAI_CONFIG", {})
                temperature = config.get("temperature", 1.0)
            elif provider == "gemini":
                config = getattr(settings, "GEMINI_CONFIG", {})
                temperature = config.get("temperature", 0.7)
            else:
                config = getattr(settings, "OPENAI_CONFIG", {})
                temperature = config.get("temperature", 1.0)

        chat_kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "raw_response": True,
        }

        if json_mode:
            if response_format is None:
                response_format = {"type": "json_object"}
            chat_kwargs["response_format"] = response_format
        elif response_format is not None:
            chat_kwargs["response_format"] = response_format

        effective_state = {**(state or {}), "node_name": node_name}
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        logger.info(
            f"LLM request; node_name={node_name}, "
            f"message_count={len(messages)}, total_chars={total_chars}, "
            f"json_mode={json_mode}"
        )

        try:
            response_obj = llm_service.chat(**chat_kwargs)

            if response_obj is None:
                logger.error(
                    f"LLM service returned None response; "
                    f"node_name={node_name}"
                )
                raise ValueError(
                    f"[{node_name}] LLM service returned None response"
                )

            response_content = None
            usage = None
            actual_model = None

            if hasattr(response_obj, "response_metadata"):
                metadata = response_obj.response_metadata
                if isinstance(metadata, dict):
                    actual_model = metadata.get("model_name")

            if hasattr(response_obj, "content"):
                response_content = response_obj.content
                if hasattr(response_obj, "usage_metadata"):
                    usage_meta = response_obj.usage_metadata
                    if isinstance(usage_meta, dict):
                        usage = {
                            "model": actual_model or "unknown",
                            "prompt_tokens": usage_meta.get("input_tokens", 0),
                            "completion_tokens": usage_meta.get(
                                "output_tokens", 0
                            ),
                            "total_tokens": usage_meta.get("total_tokens", 0),
                        }
                        if "input_token_details" in usage_meta:
                            details = usage_meta["input_token_details"]
                            if isinstance(details, dict):
                                usage["cached_tokens"] = details.get(
                                    "cache_read", 0
                                )
                        if "output_token_details" in usage_meta:
                            details = usage_meta["output_token_details"]
                            if isinstance(details, dict):
                                usage["reasoning_tokens"] = details.get(
                                    "reasoning", 0
                                )
            else:
                response_content = (
                    str(response_obj) if response_obj else None
                )

            if not response_content or not str(response_content).strip():
                model_val = actual_model or "unknown"
                logger.warning(
                    f"LLM returned empty response; node_name={node_name}, "
                    f"model={model_val}"
                )
                raise ValueError("LLM returned empty response")

            if not usage:
                model_val = actual_model or "unknown"
                logger.debug(
                    f"No usage_metadata on response; node_name={node_name}, "
                    f"model={model_val}"
                )
                usage = {
                    "model": actual_model or "unknown",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

            usage.setdefault("cached_tokens", 0)
            usage.setdefault("reasoning_tokens", 0)

            if state is not None:
                tracking_data = {
                    "node": effective_state.get("node_name", "unknown"),
                    "model": usage["model"],
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "cached_tokens": usage.get("cached_tokens", 0),
                    "reasoning_tokens": usage.get("reasoning_tokens", 0),
                    "success": True,
                    "error": None,
                }
                state.setdefault("llm_calls", []).append(tracking_data)

            LLMTracker._save_usage_to_db(
                state=effective_state,
                model=usage["model"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
                cached_tokens=usage.get("cached_tokens", 0),
                reasoning_tokens=usage.get("reasoning_tokens", 0),
                success=True,
                error=None,
            )

            node = effective_state.get("node_name", "unknown")
            logger.info(
                f"LLM call succeeded; node_name={node}, "
                f"model={usage['model']}, total_tokens={usage['total_tokens']}"
            )

            return str(response_content), usage

        except Exception as e:
            node = effective_state.get("node_name", "unknown")
            err_type = type(e).__name__
            logger.error(
                f"LLM call failed; node_name={node}, error_type={err_type}, "
                f"error={e}"
            )
            logger.exception(e)

            if state is not None:
                tracking_data = {
                    "node": effective_state.get("node_name", "unknown"),
                    "model": "unknown",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "success": False,
                    "error": str(e),
                }
                state.setdefault("llm_calls", []).append(tracking_data)

            LLMTracker._save_usage_to_db(
                state=effective_state,
                model="unknown",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cached_tokens=0,
                reasoning_tokens=0,
                success=False,
                error=str(e),
            )

            raise

    @staticmethod
    def _save_usage_to_db(
        state: Optional[Dict] = None,
        node_name: str = "unknown",
        model: str = "unknown",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Save LLM usage record to database.

        Metadata: node_name (param or state), source_type, source_task_id,
        source_path, and state.get("metadata") merged. Param node_name
        is used when state has no "node_name" for compatibility.
        """
        try:
            state = state or {}
            user_id = state.get("user_id")
            node_name = state.get("node_name", node_name)

            metadata = {}
            if node_name and node_name != "unknown":
                metadata["node_name"] = node_name

            source_type = state.get("source_type")
            if source_type:
                metadata["source_type"] = source_type
            source_task_id = (
                state.get("source_task_id")
                or state.get("celery_task_id")
                or state.get("task_id")
            )
            if source_task_id:
                metadata["source_task_id"] = str(source_task_id)
            source_path = state.get("source_path")
            if source_path:
                metadata["source_path"] = source_path

            extra = state.get("metadata")
            if isinstance(extra, dict):
                metadata.update(extra)

            with transaction.atomic():
                LLMUsage.objects.create(
                    user_id=user_id,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cached_tokens=cached_tokens,
                    reasoning_tokens=reasoning_tokens,
                    success=success,
                    error=error,
                    metadata=metadata,
                )

        except Exception as e:
            logger.warning(
                f"Failed to save LLM usage record; node_name={node_name}, "
                f"model={model}, user_id={user_id}, error={e}",
                exc_info=True,
            )
