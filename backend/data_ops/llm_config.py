from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError, ProgrammingError

try:
    from agentcore_metering.adapters.django.models import LLMConfig
except (ImportError, RuntimeError):
    LLMConfig = None


def _row_label(row: Any) -> str:
    config = getattr(row, "config", {}) or {}
    model = str(config.get("model") or "").strip()
    provider = str(getattr(row, "provider", "") or "").strip().lower()
    if provider and model:
        return f"{model} ({provider})"
    return model or provider or str(getattr(row, "uuid", "") or "")


def _default_llm_row() -> Any | None:
    if LLMConfig is None:
        return None
    try:
        return (
            LLMConfig.objects.filter(
                scope=LLMConfig.Scope.GLOBAL,
                model_type=LLMConfig.MODEL_TYPE_LLM,
                is_active=True,
            )
            .order_by("-is_default", "created_at", "id")
            .first()
        )
    except (OperationalError, ProgrammingError):
        return None


def resolve_data_ops_llm_settings(
    preferred_config_uuid: str | None = None,
) -> dict[str, Any]:
    selected_row = None
    source = "settings"

    if LLMConfig is not None and preferred_config_uuid:
        try:
            selected_row = (
                LLMConfig.objects.filter(
                    uuid=preferred_config_uuid,
                    model_type=LLMConfig.MODEL_TYPE_LLM,
                    is_active=True,
                )
                .order_by("-is_default", "created_at", "id")
                .first()
            )
        except (
            OperationalError,
            ProgrammingError,
            ValidationError,
            ValueError,
        ):
            selected_row = None
        if selected_row is not None:
            source = "selected"

    if selected_row is None:
        selected_row = _default_llm_row()
        if selected_row is not None:
            source = "default"

    if selected_row is not None:
        config = selected_row.config or {}
        return {
            "source": source,
            "config_uuid": str(selected_row.uuid),
            "provider": (selected_row.provider or "").strip().lower(),
            "model": str(config.get("model") or "").strip(),
            "api_key": config.get("api_key") or "",
            "api_base": str(config.get("api_base") or "").strip(),
            "config": config,
            "label": _row_label(selected_row),
        }

    provider = getattr(settings, "LLM_PROVIDER", "openai").lower()
    if provider == "azure_openai":
        config = dict(getattr(settings, "AZURE_OPENAI_CONFIG", {}) or {})
        model = config.get("deployment") or config.get("model") or ""
        config["model"] = model
        return {
            "source": "settings",
            "config_uuid": "",
            "provider": "azure_openai",
            "model": model,
            "api_key": config.get("api_key") or "",
            "api_base": config.get("api_base") or "",
            "config": config,
            "label": model or "Azure OpenAI default",
        }

    config = dict(getattr(settings, "OPENAI_CONFIG", {}) or {})
    return {
        "source": "settings",
        "config_uuid": "",
        "provider": "openai_compatible",
        "model": config.get("model") or "",
        "api_key": config.get("api_key") or "",
        "api_base": config.get("api_base") or "",
        "config": config,
        "label": config.get("model") or "OpenAI compatible default",
    }
