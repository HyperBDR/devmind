"""Tools for the LLM Ops model price sync skill."""
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool


def build_model_price_sync_tools(runner_ref: Any) -> list[BaseTool]:
    """Build tools bound to one model price sync Agent runner."""

    @tool
    def list_configured_price_sources() -> dict[str, Any]:
        """List model price sources selected by runtime configuration."""
        sources = runner_ref.list_configured_sources()
        return {
            "sources": [
                {
                    "id": source.id,
                    "slug": source.slug,
                    "name": source.name,
                    "provider_code": (
                        source.provider.code if source.provider_id else ""
                    ),
                    "source_category": source.source_category,
                    "endpoint_url": source.endpoint_url,
                    "currency": source.currency,
                    "is_enabled": source.is_enabled,
                    "updates_model_prices": source.updates_model_prices,
                }
                for source in sources
            ],
        }

    @tool
    def collect_model_price_source(source_id: int) -> dict[str, Any]:
        """Collect and persist model prices for one configured source."""
        return runner_ref.collect_source(source_id)

    @tool
    def mark_model_price_sync_failed(error_message: str) -> dict[str, Any]:
        """Record an Agent-level price sync failure."""
        runner_ref.record_event(
            event_type="price_sync_agent_failed",
            stage="agent_execute",
            source="model_price_sync_tool",
            message=error_message,
            payload={"error": error_message},
        )
        return {"success": False, "error_message": error_message}

    return [
        list_configured_price_sources,
        collect_model_price_source,
        mark_model_price_sync_failed,
    ]
