"""
AI Price Hub provider adapter for data_collector.

This provider reuses the existing ai_pricehub sync implementation and wraps
it into the common data_collector collect flow.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from django.utils import timezone

from .base import BaseProvider


class AIPriceHubProvider(BaseProvider):
    """Adapter provider that runs ai_pricehub sync as a collector platform."""

    def authenticate(self, auth_config: dict) -> bool:
        # AI Price Hub sync currently does not require per-request credentials.
        return True

    def list_projects(self, auth_config: dict) -> list[dict]:
        # Keep the same shape as other providers for frontend compatibility.
        return [{"key": "sync", "id": "sync", "name": "Pricing sync"}]

    def collect(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        **kwargs: Any,
    ) -> list[dict]:
        # Lazy import to avoid hard dependency during isolated data_collector tests.
        from ai_pricehub.services import ai_pricehub_service

        project_keys = kwargs.get("project_keys") or []
        source_task_id = kwargs.get("task_id")
        platform_slug = str(project_keys[0]).strip() if project_keys else None
        if platform_slug == "sync":
            platform_slug = None

        result = ai_pricehub_service.sync_configured_sources(
            platform_slug=platform_slug or None,
            task_id=str(source_task_id).strip() if source_task_id else None,
            strict_api_failure_raises=False,
        )
        collected_at = timezone.now()
        source_unique_id = (
            f"pricing-sync:{platform_slug or 'all'}:"
            f"{collected_at.strftime('%Y%m%d%H%M%S')}"
        )
        raw_data = {
            "platform_slug": platform_slug or "",
            "sync_result": result,
        }
        data_hash = hashlib.sha256(
            json.dumps(raw_data, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return [
            {
                "source_unique_id": source_unique_id,
                "raw_data": raw_data,
                "filter_metadata": {
                    "task_type": "ai_pricehub_sync",
                    "platform_slug": platform_slug or "",
                },
                "data_hash": data_hash,
                "source_created_at": collected_at,
                "source_updated_at": collected_at,
            }
        ]

    def validate(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        source_unique_ids: list[str],
    ) -> list[str]:
        # No remote entity lifecycle to validate here.
        return []

    def fetch_attachments(self, auth_config: dict, raw_record: Any) -> list[dict]:
        return []
