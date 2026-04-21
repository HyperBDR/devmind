"""Restricted platform tools for the recharge approval Agent.

Only includes tools that require DB record access:
  - finalize_recharge_approval_record: persist result after workflow success
  - mark_recharge_approval_failed: record failure state

The core business logic (parsing, resolution, Feishu submission, observability)
lives in the plan/execute workflow tools in the skills layer.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool

from cloud_billing.services.recharge_approval import (
    create_recharge_approval_event,
    normalize_feishu_status,
)


def build_recharge_approval_platform_tools(runner: Any) -> list[BaseTool]:
    """Build the minimal DB-scoped tools bound to one recharge approval record."""

    @tool
    def finalize_recharge_approval_record(
        request_payload_json: str = "{}",
        response_payload_json: str = "{}",
        instance_code: str = "",
        approval_code: str = "",
        status: str = "PENDING",
        summary: str = "",
    ) -> dict[str, Any]:
        """
        Finalize the current recharge approval record after Feishu submission.

        Note: execute_recharge_approval_plan already updates the record directly.
        This tool is provided for explicit persistence confirmation or recovery use.
        """
        try:
            request_payload = json.loads(request_payload_json or "{}")
        except json.JSONDecodeError:
            request_payload = {}
        try:
            response_payload = json.loads(response_payload_json or "{}")
        except json.JSONDecodeError:
            response_payload = {}

        normalized_status = normalize_feishu_status(status)
        runner.record.request_payload = request_payload if isinstance(request_payload, dict) else {}
        runner.record.response_payload = response_payload if isinstance(response_payload, dict) else {}
        runner.record.feishu_instance_code = instance_code or None
        runner.record.feishu_approval_code = approval_code or None
        runner.record.status = normalized_status
        runner.record.status_message = summary or normalized_status
        runner.record.latest_stage = "agent_execute"
        runner.record.save(
            update_fields=[
                "request_payload",
                "response_payload",
                "feishu_instance_code",
                "feishu_approval_code",
                "status",
                "status_message",
                "latest_stage",
                "updated_at",
            ]
        )
        return {
            "record_id": runner.record.id,
            "instance_code": instance_code,
            "approval_code": approval_code,
            "status": normalized_status,
        }

    @tool
    def mark_recharge_approval_failed(
        error_message: str,
        raw_output: str = "",
    ) -> dict[str, Any]:
        """Mark the current recharge approval record as failed."""
        runner.record.status = runner.record.STATUS_FAILED
        runner.record.status_message = error_message
        runner.record.latest_stage = "agent_execute"
        runner.record.save(
            update_fields=["status", "status_message", "latest_stage", "updated_at"]
        )
        create_recharge_approval_event(
            record=runner.record,
            event_type="approval_agent_failed",
            stage="agent_execute",
            source="agent_tool",
            message=error_message,
            payload={"raw_output": raw_output},
        )
        return {"record_id": runner.record.id, "status": runner.record.status}

    return [finalize_recharge_approval_record, mark_recharge_approval_failed]
