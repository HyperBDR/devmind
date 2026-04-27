"""Recharge approval Agent definition — thin role layer over plan/execute tools."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
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
    normalize_feishu_status,
    parse_recharge_info as _parse_recharge_info,
)

from .platform_tools import build_recharge_approval_platform_tools

logger = logging.getLogger(__name__)

RECHARGE_APPROVAL_MODE_ENV = "RECHARGE_APPROVAL_MODE"
RECHARGE_APPROVAL_MODE_LOCAL = "local"


def _is_local_mode() -> bool:
    return os.environ.get(RECHARGE_APPROVAL_MODE_ENV, "").strip().lower() == RECHARGE_APPROVAL_MODE_LOCAL


def _load_skill_tools_module():
    """Load the skill tools module dynamically using importlib."""
    import importlib.util, sys
    from cloud_billing.services.recharge_approval import _approval_skill_path

    tools_path = _approval_skill_path() / "tools.py"
    module_name = "feishu_recharge_approval_tools"
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
                self.record.resolved_submitter_user_id or self.resolved_submitter_user_id
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


# =============================================================================
# Local executor (RECHARGE_APPROVAL_MODE=local)
# Inline Feishu API calls — no subprocess, no local JSON file.
# =============================================================================

AUTH_BASE = "https://open.feishu.cn"
APPROVAL_BASE_DEFAULT = "https://www.feishu.cn"

# Form field names (must match Feishu approval definition)
_F_CLOUD_TYPE = "公有云类型"
_F_RECHARGE_ACCOUNT = "充值云账号"
_F_PAYMENT_TYPE = "支付类型"
_F_PAYMENT_WAY = "支付方式"
_F_PAYMENT_COMPANY = "付款公司"
_F_REMIT_METHOD = "付款方式"
_F_RECHARGE_CUSTOMER = "充值客户名称"
_F_AMOUNT = "付款金额"
_F_EXPECTED_DATE = "期望到账时间"
_F_NOTE1 = "说明 1"
_F_REMARK = "备注"
_F_PAYMENT_NOTE = "付款说明"


def _local_feishu_token() -> str:
    import urllib.error, urllib.request

    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    if not app_id or not os.getenv("FEISHU_APP_SECRET"):
        raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set.")
    payload = json.dumps({"app_id": app_id, "app_secret": os.getenv("FEISHU_APP_SECRET")}).encode()
    req = urllib.request.Request(
        f"{AUTH_BASE}/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    logger.info("[LocalExecutor] Requesting Feishu tenant token (app_id=%s)", app_id[:8] + "***")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    code = data.get("code", -1)
    if code != 0:
        logger.error("[LocalExecutor] Feishu auth failed code=%s msg=%s", code, data.get("msg", ""))
        raise RuntimeError(f"Feishu auth failed code={code}: {data.get('msg')}")
    token = data.get("tenant_access_token", "")
    if not token:
        logger.error("[LocalExecutor] Feishu auth returned empty token")
        raise RuntimeError("No tenant_access_token in auth response.")
    logger.info("[LocalExecutor] Feishu token obtained successfully")
    return str(token)


def _local_api(url: str, payload: Dict[str, Any], token: str, method: str = "POST") -> Dict[str, Any]:
    import urllib.error, urllib.request

    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }, method=method)
    try:
        logger.debug("[LocalExecutor] Feishu API: %s %s", method, url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        logger.error("[LocalExecutor] Feishu API HTTP error: %s %s code=%s body=%s",
                     method, url, exc.code, body_text[:300])
        raise RuntimeError(f"Feishu API HTTP {exc.code} for {url}: {body_text}") from exc
    except urllib.error.URLError as exc:
        logger.error("[LocalExecutor] Feishu network error: %s %s error=%s", method, url, exc.reason)
        raise RuntimeError(f"Feishu network error for {url}: {exc.reason}") from exc
    code = result.get("code", -1)
    if code != 0:
        logger.error("[LocalExecutor] Feishu API error: %s %s code=%s msg=%s",
                     method, url, code, result.get("msg", ""))
        raise RuntimeError(f"Feishu API error {code} for {url}: {result.get('msg', '')}")
    return result


def _local_get_approval(token: str, approval_code: str, base_url: str) -> Dict[str, Any]:
    logger.info("[LocalExecutor] Fetching approval definition: approval_code=%s", approval_code)
    return _local_api(f"{base_url}/approval/openapi/v2/approval/get", {"approval_code": approval_code}, token)


def _local_list_instances(
    token: str, approval_code: str, start_ms: int, end_ms: int, base_url: str,
) -> List[str]:
    codes: List[str] = []
    offset = 0
    while True:
        result = _local_api(
            f"{base_url}/approval/openapi/v2/instance/list",
            {
                "approval_code": approval_code,
                "start_time": start_ms,
                "end_time": end_ms,
                "limit": 100,
                "offset": offset,
            },
            token,
        )
        page_codes = result.get("data", {}).get("instance_code_list", []) or []
        for code in page_codes:
            code_text = str(code or "").strip()
            if code_text:
                codes.append(code_text)
        has_more = result.get("data", {}).get("has_more", False)
        if not has_more or len(page_codes) < 100:
            break
        offset += 100
    logger.info("[LocalExecutor] Listed %d instances from Feishu (approval_code=%s)", len(codes), approval_code)
    return codes


def _local_get_instance(token: str, approval_code: str, instance_code: str, base_url: str) -> Dict[str, Any]:
    return _local_api(
        f"{base_url}/approval/openapi/v2/instance/get",
        {"approval_code": approval_code, "instance_code": instance_code},
        token,
    )


def _local_create_instance(
    token: str, approval_code: str, user_id: str, form_payload: list, base_url: str,
) -> Dict[str, Any]:
    logger.info("[LocalExecutor] Creating approval instance: approval_code=%s user_id=%s***",
                approval_code, user_id[:8] if len(user_id) > 8 else user_id)
    return _local_api(
        f"{base_url}/approval/openapi/v2/instance/create",
        {"approval_code": approval_code, "user_id": user_id, "form": json.dumps(form_payload, ensure_ascii=False)},
        token,
    )


def _local_resolve_user_id(identifier: str, token: str) -> str:
    is_email = "@" in identifier
    logger.info("[LocalExecutor] Resolving Feishu user_id from identifier: %s (type=%s)",
                identifier[:6] + "***" if len(identifier) > 6 else identifier, "email" if is_email else "mobile")
    payload: Dict[str, Any] = {"include_resigned": True, "emails": [], "mobiles": []}
    if is_email:
        payload["emails"] = [identifier]
    else:
        payload["mobiles"] = [identifier.strip().lstrip("+")]
    result = _local_api(
        f"{AUTH_BASE}/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id",
        payload, token,
    )
    user_list = result.get("data", {}).get("user_list", [])
    if not user_list:
        logger.warning("[LocalExecutor] Feishu user not found for identifier=%s", identifier[:6] + "***")
        raise RuntimeError(f"Could not resolve user_id from identifier: {identifier!r}")
    uid = user_list[0].get("user_id", "")
    if not uid:
        logger.warning("[LocalExecutor] Feishu returned empty user_id for identifier=%s", identifier[:6] + "***")
        raise RuntimeError(f"Could not resolve user_id from identifier: {identifier!r}")
    logger.info("[LocalExecutor] Resolved user_id=%s for identifier=%s", uid[:8] + "***", identifier[:6] + "***")
    return str(uid)


def _form_to_name_map(form_list: List) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for item in form_list:
        name = item.get("name")
        if not name:
            continue
        value = item.get("value", "")
        if item.get("type") == "amount" and isinstance(value, (int, float)):
            result[name] = float(value)
        else:
            result[name] = value
    return result


def _build_remark(payee: Dict[str, Any]) -> str:
    return "\n".join([
        f"账户类型：{payee.get('type', '')}",
        f"户名：{payee.get('account_name', '')}",
        f"账号：{payee.get('account_number', '')}",
        f"银行：{payee.get('bank_name', '')}",
        f"银行地区：{payee.get('bank_region', '')}",
        f"支行：{payee.get('bank_branch', '')}",
    ])


def _split_amount(value: Any) -> tuple:
    if value is None:
        return "", ""
    if isinstance(value, (int, float)):
        return value, ""
    text = str(value).strip()
    if not text:
        return "", ""
    match = re.match(r"^\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*([A-Za-z]{3,5})?\s*$", text)
    if not match:
        return value, ""
    amount_text = match.group(1).replace(",", "")
    currency = str(match.group(2) or "").strip().upper()
    try:
        amt = int(amount_text)
    except ValueError:
        amt = float(amount_text)
    return amt, currency


def _normalize_request_data(data: Dict[str, Any]) -> None:
    payment_type = str(data.get("payment_type") or "").strip()
    payment_way = str(data.get("payment_way") or "").strip()
    remit_method = str(data.get("remit_method") or "").strip()
    if payment_type in {"转账", "支付宝"}:
        if not remit_method:
            data["remit_method"] = payment_type
        data["payment_type"] = "仅充值"
    if payment_way in {"转账", "支付宝"}:
        if not str(data.get("remit_method") or "").strip():
            data["remit_method"] = payment_way
        data["payment_way"] = "公司支付"
    amount_val, currency = _split_amount(data.get("amount"))
    data["amount"] = amount_val
    existing_currency = str(data.get("currency") or "").strip().upper()
    data["currency"] = existing_currency or currency or "CNY"


def _parse_schema(definition: Dict[str, Any]) -> list:
    form_raw = definition.get("data", {}).get("form", "[]")
    return form_raw if isinstance(form_raw, list) else json.loads(form_raw)


def _schema_by_name(schema: list) -> Dict[str, Dict[str, Any]]:
    return {item["name"]: item for item in schema if isinstance(item, dict) and item.get("name")}


def _option_text_to_key(field_schema: Dict[str, Any], submitted_text: str) -> str:
    mapping = {str(item.get("text", "")).strip(): str(item.get("value", "")).strip()
               for item in field_schema.get("option") or []}
    if submitted_text not in mapping:
        raise RuntimeError(f"Invalid option for '{field_schema['name']}': {submitted_text}")
    return mapping[submitted_text]


def _normalize_date(value: str) -> str:
    date_obj = datetime.strptime(value[:10], "%Y-%m-%d").date()
    return f"{date_obj.isoformat()}T00:00:00+08:00"


def _default_expected_date() -> str:
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    target = (now_utc + timedelta(days=7)).date()
    return target.isoformat()


def _build_form_payload(data: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> list:
    _normalize_request_data(data)

    required_fields = [
        ("cloud_type", "cloud_type"),
        ("recharge_customer_name", "充值客户名称"),
        ("recharge_account", "充值云账号"),
        ("payment_company", "付款公司"),
        ("amount", "付款金额"),
    ]
    for field_key, label in required_fields:
        if not str(data.get(field_key) or "").strip():
            raise RuntimeError(f"Missing required field: {label}")

    payee = data.get("payee", {})
    payment_type = str(data.get("payment_type", "仅充值")).strip()
    payment_way = str(data.get("payment_way", "公司支付")).strip()
    remit_method = str(data.get("remit_method", "转账")).strip()
    payment_note = str(data.get("payment_note", "")).strip()
    remark = str(data.get("remark") or _build_remark(payee))
    expected_date = str(data.get("expected_date") or _default_expected_date()).strip()

    form_payload: list = []
    # Dropdown fields
    for fname, text in [
        (_F_CLOUD_TYPE, str(data.get("cloud_type", "")).strip()),
        (_F_PAYMENT_TYPE, payment_type),
        (_F_PAYMENT_WAY, payment_way),
        (_F_PAYMENT_COMPANY, str(data.get("payment_company", "")).strip()),
        (_F_REMIT_METHOD, remit_method),
    ]:
        fs = schema.get(fname)
        if not fs:
            raise RuntimeError(f"Approval definition missing expected field: {fname}")
        form_payload.append({"id": fs["id"], "type": fs["type"], "value": _option_text_to_key(fs, text)})

    # Simple fields
    simple_fields = [
        (_F_RECHARGE_CUSTOMER, data.get("recharge_customer_name", "")),
        (_F_RECHARGE_ACCOUNT, data.get("recharge_account", "")),
        (_F_AMOUNT, data.get("amount", "")),
        (_F_EXPECTED_DATE, _normalize_date(expected_date)),
        (_F_REMARK, remark),
    ]
    if payment_note:
        simple_fields.insert(2, (_F_PAYMENT_NOTE, payment_note))
    if schema.get(_F_NOTE1):
        insert_at = 3 if payment_note else 2
        simple_fields.insert(insert_at, (_F_NOTE1, "请填写<员工费用报销>并关联此申请"))
    for fname, value in simple_fields:
        fs = schema.get(fname)
        if not fs:
            raise RuntimeError(f"Approval definition missing expected field: {fname}")
        form_payload.append({"id": fs["id"], "type": fs["type"], "value": value})
    return form_payload


def _detect_duplicate(token: str, approval_code: str, data: Dict[str, Any], base_url: str) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=15)).timestamp() * 1000)
    cloud_type = str(data.get("cloud_type", "")).strip()
    account = str(data.get("recharge_account", "")).strip()
    logger.info("[LocalExecutor] Checking duplicate: cloud_type=%s account=%s lookback=15d", cloud_type, account)
    for code in _local_list_instances(token, approval_code, start_ms, end_ms, base_url):
        try:
            detail = _local_get_instance(token, approval_code, code, base_url)
        except Exception as exc:
            logger.warning("[LocalExecutor] Failed to get instance %s: %s", code, exc)
            continue
        form_list = detail.get("data", {}).get("form", "[]")
        if isinstance(form_list, str):
            form_list = json.loads(form_list)
        form_map = _form_to_name_map(form_list)
        logger.debug("[LocalExecutor] Inspecting instance code=%s cloud=%s account=%s status=%s",
                      code, form_map.get(_F_CLOUD_TYPE), form_map.get(_F_RECHARGE_ACCOUNT),
                      detail.get("data", {}).get("status"))
        inst_status = detail.get("data", {}).get("status", "")
        if inst_status != "PENDING":
            continue
        if form_map.get(_F_CLOUD_TYPE) == cloud_type and form_map.get(_F_RECHARGE_ACCOUNT) == account:
            matched = {
                "instance_code": code,
                "serial_number": detail.get("data", {}).get("serial_number"),
                "status": detail.get("data", {}).get("status"),
                "user_id": detail.get("data", {}).get("user_id"),
            }
            logger.info("[LocalExecutor] Duplicate found: instance_code=%s serial=%s status=%s",
                        code, matched.get("serial_number"), matched.get("status"))
            return matched
    logger.info("[LocalExecutor] No duplicate found for cloud_type=%s account=%s", cloud_type, account)
    return None


def _execute_local(
    *,
    record: RechargeApprovalRecord,
    raw_recharge_info: str,
    submitter_identifier: str,
    submitter_user_label: str,
    resolved_submitter_user_id: str,
) -> Dict[str, Any]:
    """
    Execute recharge approval without LLM:
      1. Parse recharge info
      2. Resolve Feishu user_id (if not provided)
      3. Detect duplicate on Feishu (PENDING with same cloud_type + recharge_account)
      4. Build form payload and submit
      5. Update record and return result
    No local JSON file, no subprocess.
    """
    source = "local_script_executor"
    record_id = getattr(record, "id", "?")
    trace_id = str(getattr(record, "trace_id", ""))
    logger.info("[LocalExecutor] === START record_id=%s trace_id=%s ===", record_id, trace_id)
    create_recharge_approval_event(
        record=record, event_type="local_execution_started", stage="skill_workflow",
        source=source, message="Recharge approval local execution started.",
        payload={"submitter_identifier": submitter_identifier},
    )

    try:
        # Step 1: parse
        logger.info("[LocalExecutor] Step 1/6: Parsing recharge info (raw length=%d)", len(raw_recharge_info or ""))
        create_recharge_approval_event(
            record=record, event_type="workflow_step_parse_started", stage="skill_workflow",
            source=source, message="Parsing recharge info.",
        )
        try:
            parsed_payload = _parse_recharge_info(raw_recharge_info)
        except (ValueError, json.JSONDecodeError) as exc:
            if raw_recharge_info:
                logger.info("[LocalExecutor] First parse failed, retrying with raw_recharge_info")
                parsed_payload = _parse_recharge_info(raw_recharge_info)
            else:
                logger.error("[LocalExecutor] Parse failed: %s", exc)
                raise RuntimeError(f"Failed to parse recharge info: {exc}") from exc

        logger.info("[LocalExecutor] Parse OK: cloud_type=%s account=%s amount=%s",
                    parsed_payload.get("cloud_type"), parsed_payload.get("recharge_account"),
                    parsed_payload.get("amount"))
        create_recharge_approval_event(
            record=record, event_type="workflow_step_parse_completed", stage="skill_workflow",
            source=source, message="Recharge info parsed.",
            payload={"cloud_type": parsed_payload.get("cloud_type", ""),
                     "recharge_account": parsed_payload.get("recharge_account", ""),
                     "amount": parsed_payload.get("amount", ""),
                     "currency": parsed_payload.get("currency", "")},
        )

        # Step 2: Feishu auth + config
        approval_code = os.getenv("FEISHU_APPROVAL_CODE", "").strip()
        if not approval_code:
            logger.error("[LocalExecutor] FEISHU_APPROVAL_CODE not set")
            raise RuntimeError("FEISHU_APPROVAL_CODE is not set.")
        base_url = os.getenv("FEISHU_APPROVAL_BASE_URL", APPROVAL_BASE_DEFAULT).strip()
        logger.info("[LocalExecutor] Step 2/6: Getting Feishu token (approval_code=%s base_url=%s)",
                    approval_code, base_url)
        token = _local_feishu_token()

        # Step 3: resolve user_id
        resolved_user_id = resolved_submitter_user_id
        submitter_ident = submitter_identifier
        if not resolved_user_id and submitter_ident:
            logger.info("[LocalExecutor] Step 3/6: Resolving user_id from identifier=%s", submitter_ident[:6] + "***")
            resolved_user_id = _local_resolve_user_id(submitter_ident, token)
            create_recharge_approval_event(
                record=record, event_type="workflow_step_resolve_completed", stage="skill_workflow",
                source=source, message=f"Resolved user_id={resolved_user_id[:8]}***",
                payload={"user_id": resolved_user_id, "identifier": submitter_ident},
            )
        elif resolved_user_id:
            logger.info("[LocalExecutor] Step 3/6: Using pre-resolved user_id=%s***",
                        resolved_user_id[:8] if len(resolved_user_id) > 8 else resolved_user_id)
        else:
            logger.warning("[LocalExecutor] Step 3/6: No submitter identifier provided")

        if not resolved_user_id:
            logger.error("[LocalExecutor] No Feishu user_id available")
            raise RuntimeError("No Feishu user_id available.")

        # Step 4: duplicate check
        logger.info("[LocalExecutor] Step 4/6: Checking duplicate on Feishu")
        create_recharge_approval_event(
            record=record, event_type="workflow_step_dedup_started", stage="skill_workflow",
            source=source, message="Checking for duplicate pending approvals.",
        )
        existing = _detect_duplicate(token, approval_code, parsed_payload, base_url)

        # Step 5: get schema + build form
        logger.info("[LocalExecutor] Step 5/6: Fetching approval definition and building form")
        definition = _local_get_approval(token, approval_code, base_url)
        schema = _schema_by_name(_parse_schema(definition))
        form_payload = _build_form_payload(parsed_payload, schema)
        logger.info("[LocalExecutor] Form built with %d fields", len(form_payload))

        # Step 6: submit or deduplicate
        if existing:
            instance_code = str(existing.get("instance_code", ""))
            serial = str(existing.get("serial_number", ""))
            logger.info("[LocalExecutor] Step 6/6: DEDUPLICATE — reusing instance code=%s serial=%s",
                        instance_code, serial)
            create_recharge_approval_event(
                record=record, event_type="workflow_deduplicated", stage="skill_workflow",
                source=source, message=f"Reused existing pending instance {serial or instance_code}",
                payload={"existing_instance": existing},
            )
        else:
            logger.info("[LocalExecutor] Step 6/6: Submitting to Feishu (user_id=%s*** form_fields=%d)",
                        resolved_user_id[:8], len(form_payload))
            response = _local_create_instance(token, approval_code, resolved_user_id, form_payload, base_url)
            instance_code = str(response.get("data", {}).get("instance_code", "") or "")
            logger.info("[LocalExecutor] Submission response: instance_code=%s", instance_code)
            create_recharge_approval_event(
                record=record, event_type="workflow_step_submit_started", stage="skill_workflow",
                source=source, message=f"Submitted new instance instance={instance_code}",
            )

        finished_at = datetime.now(timezone.utc)
        normalized_status = normalize_feishu_status("PENDING")
        summary = (
            f"Reused existing pending instance {existing.get('serial_number', '') if existing else ''}"
            if existing else
            f"Submitted new instance instance={instance_code}"
        )

        # Notification message
        from cloud_billing.services.recharge_approval import (
            build_notification_message_from_payload as _build_notification_message,
        )
        trigger_user_label = (
            getattr(getattr(record, "triggered_by", None), "username", None)
            or getattr(record, "triggered_by_username_snapshot", "")
            or ""
        )
        notification_msg = _build_notification_message(
            parsed_payload, notification_type="submitted",
            trigger_source=getattr(record, "trigger_source", "manual") or "manual",
            trigger_reason=getattr(record, "trigger_reason", "") or "",
            trigger_user_label=trigger_user_label,
            submitter_label=submitter_user_label or submitter_identifier or "",
            provider_name=getattr(getattr(record, "provider", None), "display_name", None) or "",
            approval_status="已提交",
        )

        # Update record
        record.request_payload = parsed_payload
        record.response_payload = {"deduplicated": bool(existing), "instance_code": instance_code}
        record.feishu_instance_code = instance_code or None
        record.feishu_approval_code = approval_code
        record.status = normalized_status
        record.status_message = summary
        record.latest_stage = "skill_workflow"
        record.context_payload = {**(record.context_payload or {}), "notification_message": notification_msg}
        record.submitted_at = finished_at
        record.submitter_identifier = submitter_identifier
        record.resolved_submitter_user_id = resolved_user_id
        record.submitter_user_label = submitter_user_label
        record.save(update_fields=[
            "request_payload", "response_payload", "feishu_instance_code",
            "feishu_approval_code", "status", "status_message", "latest_stage",
            "context_payload", "submitted_at", "submitter_identifier",
            "resolved_submitter_user_id", "submitter_user_label", "updated_at",
        ])

        logger.info("[LocalExecutor] === COMPLETE record_id=%s instance_code=%s status=%s ===",
                    record_id, instance_code, normalized_status)
        create_recharge_approval_event(
            record=record, event_type="local_execution_completed", stage="skill_workflow",
            source=source, message=summary,
            payload={"success": True, "deduplicated": bool(existing),
                     "instance_code": instance_code, "approval_code": approval_code,
                     "status": normalized_status, "summary": summary},
        )

        return {
            "submitter_identifier": submitter_identifier,
            "resolved_submitter_user_id": resolved_user_id,
            "submitter_user_label": submitter_user_label,
            "request_payload": parsed_payload,
            "submission_payload": record.response_payload,
            "notification_message": notification_msg,
            "success": True,
            "status": normalized_status,
            "approval_code": approval_code,
            "instance_code": instance_code,
            "summary": summary,
            "error_message": "",
        }

    except Exception as exc:
        logger.error("[LocalExecutor] === FAILED record_id=%s error=%s ===", record_id, exc, exc_info=True)
        record.status = record.STATUS_FAILED
        record.status_message = str(exc)
        record.latest_stage = "skill_workflow"
        record.save(update_fields=["status", "status_message", "latest_stage", "updated_at"])
        create_recharge_approval_event(
            record=record, event_type="local_execution_failed", stage="skill_workflow",
            source=source, message=str(exc), payload={"error": str(exc)},
        )
        raise


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
    if _is_local_mode():
        logger.info(
            "RECHARGE_APPROVAL_MODE=local; executing via local script "
            "(record_id=%s, trace_id=%s)",
            record.id,
            record.trace_id,
        )
        return _execute_local(
            record=record,
            raw_recharge_info=raw_recharge_info,
            submitter_identifier=submitter_identifier,
            submitter_user_label=submitter_user_label,
            resolved_submitter_user_id=resolved_submitter_user_id,
        )

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