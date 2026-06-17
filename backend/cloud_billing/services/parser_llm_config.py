from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

try:
    from agentcore_metering.adapters.django.models import LLMConfig
except ImportError:  # pragma: no cover - optional dependency during partial installs
    LLMConfig = None


def _row_to_reference(row: Any) -> dict[str, str]:
    config = getattr(row, "config", {}) or {}
    model = str(config.get("model") or "").strip()
    provider = str(getattr(row, "provider", "") or "").strip().lower()
    label = model or provider or str(getattr(row, "uuid", "") or "")
    if provider and model:
        label = f"{model} ({provider})"
    return {
        "uuid": str(getattr(row, "uuid", "") or ""),
        "label": label,
    }


def get_llm_config_reference(config_uuid: str | None) -> dict[str, str]:
    if not config_uuid:
        return {"uuid": "", "label": ""}
    if LLMConfig is None:
        return {"uuid": str(config_uuid), "label": str(config_uuid)}
    try:
        row = (
            LLMConfig.objects.filter(
                uuid=config_uuid,
                model_type=LLMConfig.MODEL_TYPE_LLM,
            )
            .order_by("-is_active", "-is_default", "created_at", "id")
            .first()
        )
    except (OperationalError, ProgrammingError):
        row = None
    if row is None:
        return {"uuid": str(config_uuid), "label": str(config_uuid)}
    return _row_to_reference(row)


def _get_default_llm_row() -> Any | None:
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


def resolve_parser_llm_settings(
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
        except (OperationalError, ProgrammingError):
            selected_row = None
        if selected_row is not None:
            source = "selected"

    if selected_row is None:
        selected_row = _get_default_llm_row()
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
            "label": _row_to_reference(selected_row)["label"],
        }

    return {
        "source": "settings",
        "config_uuid": "",
        "provider": "openai_compatible",
        "model": getattr(settings, "AI_PRICEHUB_PARSER_LLM_MODEL", ""),
        "api_key": getattr(settings, "AI_PRICEHUB_PARSER_LLM_API_KEY", ""),
        "api_base": getattr(settings, "AI_PRICEHUB_PARSER_LLM_BASE_URL", ""),
        "label": getattr(settings, "AI_PRICEHUB_PARSER_LLM_MODEL", "") or "Global default",
    }
