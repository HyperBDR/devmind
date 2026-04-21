"""Recharge approval Agent definition — thin role layer over plan/execute tools."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from deepagents.backends.utils import create_file_data
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from agent_runner import AgentRunner, SkillSpec
from cloud_billing.models import RechargeApprovalRecord
from cloud_billing.services.recharge_approval import (
    RechargeApprovalAgentCallbackHandler,
    _approval_skill_path,
    _skill_root_path,
    _workspace_root,
    build_deep_agent_model,
    create_recharge_approval_event,
    create_recharge_approval_llm_run,
)

from .platform_tools import build_recharge_approval_platform_tools


def _load_skill_tools_module():
    """Load the skill tools module dynamically using importlib."""
    import importlib.util, sys
    from cloud_billing.services.recharge_approval import _approval_skill_path

    tools_path = _approval_skill_path() / "tools.py"
    module_name = "feishu_recharge_approval_tools"
    # Register in sys.modules first so that exec_module re-uses the existing
    # entry (instead of creating a fresh module object each time). This lets
    # callers monkeypatch module-level functions before / after load.
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load skill tools: {tools_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_recharge_plan_execute_tools_from_runner(runner_ref: Any) -> List[BaseTool]:
    """Build plan/execute workflow tools from a runner instance."""
    module = _load_skill_tools_module()
    return module.build_recharge_plan_execute_tools(runner_ref)


class RechargeApprovalAgentResult(BaseModel):
    submitter_identifier: str = ""
    resolved_submitter_user_id: str = ""
    submitter_user_label: str = ""
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    submission_payload: Dict[str, Any] = Field(default_factory=dict)
    notification_message: str = ""
    success: bool = True
    status: str = ""
    approval_code: str = ""
    instance_code: str = ""
    summary: str = ""
    error_message: str = ""


class RechargeApprovalAgentRunner(AgentRunner):
    """
    Recharge approval Agent — thin role definition layer.

    The Agent's only jobs are:
      1. Call plan_recharge_approval_workflow with the raw recharge info
      2. Call execute_recharge_approval_plan with the generated request_file
      3. Return the result as a structured response

    All business logic (parsing, resolution, Feishu submission, duplicate
    detection, DB updates, observability) lives inside the plan/execute tools.
    """

    SKILL_DIRS = [_skill_root_path()]
    SKILL_dirs = SKILL_DIRS

    def __init__(
        self,
        *,
        record: RechargeApprovalRecord,
        raw_recharge_info: str,
        user_id: Optional[int] = None,
        source_task_id: Optional[str] = None,
        submitter_identifier: str = "",
        submitter_user_label: str = "",
        resolved_submitter_user_id: str = "",
    ) -> None:
        super().__init__(
            record=record,
            user_id=user_id,
            source_task_id=source_task_id,
            workspace_root=_workspace_root(),
        )
        self.raw_recharge_info = raw_recharge_info
        self.submitter_identifier = submitter_identifier
        self.submitter_user_label = submitter_user_label
        self.resolved_submitter_user_id = resolved_submitter_user_id

    # -------------------------------------------------------------------------
    # Agent definition
    # -------------------------------------------------------------------------

    def build_system_prompt_fragments(self) -> List[str]:
        skill_md = (_approval_skill_path() / "SKILL.md").read_text(encoding="utf-8")
        return [
            "You are the recharge approval agent for DevMind cloud billing.",
            f"\n## Skill: feishu-cloud-billing-approval\n\n{skill_md}",
        ]

    def build_skill_specs(self) -> List[SkillSpec]:
        return []

    def build_skill_state_files(self) -> Dict[str, Any]:
        skill_md = _approval_skill_path() / "SKILL.md"
        file_data = create_file_data(skill_md.read_text(encoding="utf-8"))
        return {
            "/cloud_billing/skills/feishu-cloud-billing-approval/SKILL.md": file_data,
            "/SKILL.md": file_data,
        }

    def build_tools(self) -> List[BaseTool]:
        """
        Agent toolset (4 tools):

        plan_recharge_approval_workflow — parse and write the request JSON file
        execute_recharge_approval_plan  — submit using the generated JSON file
        finalize_recharge_approval_record — persist result (optional, already done internally)
        mark_recharge_approval_failed   — mark record failed after error

        The runner context (record, raw_recharge_info, submitter, etc.) is
        captured in the workflow tool's closure. The Agent does NOT pass these
        through tool arguments — the tool reads them directly from the runner.
        """
        return [
            *build_recharge_plan_execute_tools_from_runner(self),
            *build_recharge_approval_platform_tools(self),
        ]

    def build_user_context(self) -> str:
        ctx = {
            "record_id": self.record.id,
            "trace_id": str(self.record.trace_id),
            "provider_id": self.record.provider.id,
            "provider_type": self.record.provider.provider_type,
            "raw_recharge_info": self.raw_recharge_info,
            "submitter_identifier": self.submitter_identifier,
            "submitter_user_label": self.submitter_user_label,
            "resolved_submitter_user_id": self.resolved_submitter_user_id,
        }
        return (
            "You are the recharge approval agent for DevMind cloud billing.\n"
            "Your task: submit a recharge approval to Feishu.\n\n"
            "## Context\n"
            f"{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
            "## Your task\n"
            "1. Review the raw_recharge_info above.\n"
            "2. Call plan_recharge_approval_workflow with the raw_recharge_info. This must create the request JSON file first.\n"
            "3. Call execute_recharge_approval_plan with the request_file returned by the plan step.\n"
            "4. Return the execute result as your structured response.\n"
            "5. If either step raises an error, call mark_recharge_approval_failed, then return an error result.\n"
        )

    def get_llm_model(self) -> BaseChatModel | str:
        return build_deep_agent_model(self.user_id)

    def get_response_format(self) -> type[RechargeApprovalAgentResult] | None:
        return RechargeApprovalAgentResult

    def record_llm_run(
        self,
        runner_type: str,
        provider: str,
        model: str,
        input_snapshot: str,
        output_snapshot: str,
        usage_payload: Dict[str, Any],
        stdout: str,
        stderr: str,
        started_at: Any,
        finished_at: Any,
        success: bool,
        **kwargs: Any,
    ) -> None:
        create_recharge_approval_llm_run(
            record=self.record,
            stage="agent_execute",
            runner_type=runner_type,
            provider=provider,
            model=model,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            parsed_payload=kwargs.get("parsed_payload") or {},
            usage_payload=usage_payload,
            stdout=stdout,
            stderr=stderr,
            llm_usage_id=None,
            success=success,
            error_message=str(kwargs.get("error_message") or ""),
            started_at=started_at,
            finished_at=finished_at,
        )

    def record_event(
        self,
        event_type: str,
        stage: str,
        source: str,
        message: str,
        payload: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        create_recharge_approval_event(
            record=self.record,
            event_type=event_type,
            stage=stage,
            source=source,
            message=message,
            payload=payload or {},
        )

    def _build_callback_handler(self, *, langfuse_runtime: Any | None = None) -> Any:
        return RechargeApprovalAgentCallbackHandler(
            record=self.record,
            user_id=self.user_id,
            langfuse_runtime=langfuse_runtime,
        )

    def recover_structured_response(self, result: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Recover from deepagent final-message failures after the workflow tool
        has already persisted a successful Feishu submission.
        """
        self.record.refresh_from_db()
        if self.record.status == RechargeApprovalRecord.STATUS_FAILED:
            return None
        if not self.record.request_payload:
            return None
        if not self.record.response_payload and not self.record.feishu_instance_code:
            return None

        summary = self.record.status_message or self.record.status
        return {
            "submitter_identifier": self.record.submitter_identifier or self.submitter_identifier,
            "resolved_submitter_user_id": (
                self.record.resolved_submitter_user_id
                or self.resolved_submitter_user_id
            ),
            "submitter_user_label": (
                self.record.submitter_user_label or self.submitter_user_label
            ),
            "request_payload": self.record.request_payload or {},
            "submission_payload": self.record.response_payload or {},
            "notification_message": self.record.context_payload.get("notification_message") or "",
            "success": True,
            "status": self.record.status or RechargeApprovalRecord.STATUS_SUBMITTED,
            "approval_code": self.record.feishu_approval_code or "",
            "instance_code": self.record.feishu_instance_code or "",
            "summary": summary,
            "error_message": "",
        }


def execute_recharge_approval_agent(
    *,
    record: RechargeApprovalRecord,
    raw_recharge_info: str,
    user_id: Optional[int] = None,
    source_task_id: Optional[str] = None,
    submitter_identifier: str = "",
    submitter_user_label: str = "",
    resolved_submitter_user_id: str = "",
) -> Dict[str, Any]:
    runner = RechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=raw_recharge_info,
        user_id=user_id,
        source_task_id=source_task_id,
        submitter_identifier=submitter_identifier,
        submitter_user_label=submitter_user_label,
        resolved_submitter_user_id=resolved_submitter_user_id,
    )
    return runner.execute()
