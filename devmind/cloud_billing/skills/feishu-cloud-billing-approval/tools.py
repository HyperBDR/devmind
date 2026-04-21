"""
LangChain tools for the feishu-recharge-approval skill.

These tools are loaded by AgentRunner via SkillSpec.load_from_skill_dir()
and attached to the skill sub-agent (or the main agent when no sub-agents are used).

Architecture:
- Recharge approval submission uses an explicit plan → execute flow.
  plan_recharge_approval_workflow parses and materializes the request JSON first.
  execute_recharge_approval_plan then submits using that pre-created JSON file.
- Payee bank/account details are carried in 备注, not in structured request JSON.
- The remaining tools (resolve_submitter_user_id, get_approval_definition, etc.) are
  read-only informational tools kept for recovery/debugging use.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time as time_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

AUTH_BASE = "https://open.feishu.cn"
APPROVAL_BASE = "https://www.feishu.cn"
TZ_OFFSET = "+08:00"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _token() -> str:
    import urllib.error, urllib.request

    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set.")
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        f"{AUTH_BASE}/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    code = data.get("code", -1)
    if code != 0:
        raise RuntimeError(f"Feishu auth failed code={code}: {data.get('msg')}")
    token = data.get("tenant_access_token", "")
    if not token:
        raise RuntimeError("No tenant_access_token in auth response.")
    return str(token)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def _api(url: str, payload: Dict[str, Any], token: str, method: str = "POST") -> Dict[str, Any]:
    import urllib.error, urllib.request

    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers=_headers(token), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(f"Feishu API HTTP {exc.code} for {url}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Feishu network error for {url}: {exc.reason}") from exc
    code = result.get("code", -1)
    if code != 0:
        raise RuntimeError(f"Feishu API error {code} for {url}: {result.get('msg', '')}")
    return result


def _approval_config() -> Dict[str, str]:
    approval_code = os.getenv("FEISHU_APPROVAL_CODE", "").strip()
    if not approval_code:
        raise RuntimeError("FEISHU_APPROVAL_CODE is not set.")
    return {
        "approval_code": approval_code,
        "approval_base_url": os.getenv("FEISHU_APPROVAL_BASE_URL", APPROVAL_BASE).strip(),
    }


# ---------------------------------------------------------------------------
# Historical payee inference
# ---------------------------------------------------------------------------

def _find_payee_from_history(
    cloud_type: str,
    recharge_account: str,
    lookback_days: int = 365,
) -> Dict[str, Any] | None:
    """
    Search Feishu approval history for a matching instance and extract its payee.

    Returns the payee dict (account_name, account_number, bank_name, etc.) if found,
    or None if no historical match exists.
    """
    try:
        cfg = _approval_config()
        token = _token()
        base_url = cfg.get("approval_base_url", APPROVAL_BASE)
        approval_code = cfg["approval_code"]
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)

    try:
        listed = _api(
            f"{base_url}/approval/openapi/v2/instance/list",
            {"approval_code": approval_code, "start_time": start_ms, "end_time": end_ms, "limit": 100},
            token,
        )
    except Exception:
        return None

    cloud_type = str(cloud_type or "").strip()
    recharge_account = str(recharge_account or "").strip()

    for code in listed.get("data", {}).get("instance_code_list", []):
        try:
            detail = _api(
                f"{base_url}/approval/openapi/v2/instance/get",
                {"approval_code": approval_code, "instance_code": code},
                token,
            )
        except Exception:
            continue
        data = detail.get("data", {})
        status = str(data.get("status") or "").strip().upper()
        # Use any completed instance (APPROVED, PASSED, DONE, CANCELED) as history
        # since the payee info is already in the remark regardless of approval outcome.
        if status not in {"APPROVED", "PASSED", "DONE", "CANCELED"}:
            continue
        form_list = data.get("form", "[]")
        if isinstance(form_list, str):
            try:
                form_list = json.loads(form_list)
            except Exception:
                continue
        form_map = _form_list_to_name_map(form_list)
        if str(form_map.get("公有云类型") or "").strip() != cloud_type:
            continue
        if str(form_map.get("充值云账号") or "").strip() != recharge_account:
            continue
        remark_map = _parse_remark_lines(form_map.get("备注"))
        # Support both 收款类型 and 收款账户类型 as the type field key
        payee_type = (
            remark_map.get("收款类型")
            or remark_map.get("收款账户类型")
            or ""
        ).strip()
        payee: Dict[str, Any] = {
            "type": payee_type,
            "account_name": str(remark_map.get("户名") or "").strip(),
            "account_number": str(remark_map.get("账号") or "").strip(),
            "bank_name": str(remark_map.get("银行") or "").strip(),
            "bank_region": str(remark_map.get("银行地区") or "").strip(),
            "bank_branch": str(remark_map.get("支行") or "").strip(),
        }
        if payee.get("account_name") and payee.get("account_number"):
            return payee
    return None


# ---------------------------------------------------------------------------
# User resolution
# ---------------------------------------------------------------------------

def _resolve_user_id(identifier: str) -> str:
    """
    Resolve a Feishu user_id (not open_id) from an email or mobile number.
    Required because the Feishu approval API accepts user_id format.
    """
    token = _token()
    payload: Dict[str, Any] = {"include_resigned": True, "emails": [], "mobiles": []}
    if "@" in identifier:
        payload["emails"] = [identifier]
    else:
        payload["mobiles"] = [identifier.strip().lstrip("+")]
    result = _api(
        f"{AUTH_BASE}/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id",
        payload,
        token,
    )
    user_list = result.get("data", {}).get("user_list", [])
    if not user_list:
        raise RuntimeError(
            f"Could not resolve user_id from identifier: {identifier!r}. "
            "Ensure the email/mobile is registered in Feishu."
        )
    uid = user_list[0].get("user_id", "")
    if not uid:
        raise RuntimeError(
            f"Could not resolve user_id from identifier: {identifier!r}. "
            "Feishu returned no user_id in response."
        )
    logger.info("Resolved user_id=%s from identifier=%s", uid[:8] + "***", identifier)
    return str(uid)


# ---------------------------------------------------------------------------
# Form helpers
# ---------------------------------------------------------------------------

def _form_list_to_name_map(form_list: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    lines = [
        f"收款类型：{payee.get('type', '')}",
        f"户名：{payee.get('account_name', '')}",
        f"账号：{payee.get('account_number', '')}",
        f"银行：{payee.get('bank_name', '')}",
        f"银行地区：{payee.get('bank_region', '')}",
        f"支行：{payee.get('bank_branch', '')}",
    ]
    return "\n".join(lines)


def _extract_payee_from_remark(remark: str | None) -> Dict[str, str]:
    remark_map = _parse_remark_lines(remark)
    return {
        "type": str(
            remark_map.get("收款类型")
            or remark_map.get("收款账户类型")
            or ""
        ).strip(),
        "account_name": str(remark_map.get("户名") or "").strip(),
        "account_number": str(remark_map.get("账号") or "").strip(),
        "bank_name": str(remark_map.get("银行") or "").strip(),
        "bank_region": str(remark_map.get("银行地区") or "").strip(),
        "bank_branch": str(remark_map.get("支行") or "").strip(),
    }


def _merge_payee_from_sources(
    *,
    payee: Dict[str, Any] | None,
    remark: str | None,
) -> Dict[str, str]:
    merged = _extract_payee_from_remark(remark)
    if isinstance(payee, dict):
        for key in ("type", "account_name", "account_number", "bank_name", "bank_region", "bank_branch"):
            value = str(payee.get(key) or "").strip()
            if value:
                merged[key] = value
    return merged


def _parse_remark_lines(remark: str | None) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not remark:
        return result
    for line in str(remark).splitlines():
        line = line.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def resolve_submitter_user_id(
    identifier: Annotated[str, "Submitter email address or mobile number (e.g. user@example.com or 13800138000)."],
) -> Dict[str, str]:
    """
    Resolve a Feishu user_id from a submitter's email address or mobile number.

    The approval API requires user_id format (not open_id). This tool queries
    the Feishu contact API and returns the resolved user_id.
    """
    user_id = _resolve_user_id(identifier)
    return {"identifier": identifier, "user_id": user_id}


@tool
def get_approval_definition(
    approval_code: Annotated[str, "The approval definition code."],
) -> Dict[str, Any]:
    """
    Fetch the live approval definition schema from Feishu.

    Returns form field IDs, types, dropdown options, and validation rules.
    Use this before building a submission payload to ensure dropdown values match.
    """
    token = _token()
    cfg = _approval_config()
    base_url = cfg.get("approval_base_url", APPROVAL_BASE)
    result = _api(
        f"{base_url}/approval/openapi/v2/approval/get",
        {"approval_code": approval_code},
        token,
    )
    logger.info("Fetched approval definition for %s", approval_code)
    return result


@tool
def list_pending_instances(
    lookback_days: Annotated[int, "How many past days to scan."] = 30,
    limit: Annotated[int, "Max instances to return."] = 50,
) -> List[Dict[str, Any]]:
    """
    List PENDING approval instances for the configured approval flow.

    Returns each instance decoded into a name-to-value map for easy inspection.
    """
    token = _token()
    cfg = _approval_config()
    base_url = cfg.get("approval_base_url", APPROVAL_BASE)
    approval_code = cfg["approval_code"]

    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)

    listed = _api(
        f"{base_url}/approval/openapi/v2/instance/list",
        {"approval_code": approval_code, "start_time": start_ms, "end_time": end_ms, "limit": 100},
        token,
    )

    pending: List[Dict[str, Any]] = []
    for code in listed.get("data", {}).get("instance_code_list", []):
        detail = _api(
            f"{base_url}/approval/openapi/v2/instance/get",
            {"approval_code": approval_code, "instance_code": code},
            token,
        )
        data = detail.get("data", {})
        if data.get("status") != "PENDING":
            continue
        form_list = data.get("form", "[]")
        if isinstance(form_list, str):
            form_list = json.loads(form_list)
        form_map = _form_list_to_name_map(form_list)
        pending.append({
            "instance_code": code,
            "serial_number": data.get("serial_number"),
            "status": data.get("status"),
            "user_id": data.get("user_id"),
            "start_time": data.get("start_time"),
            **form_map,
        })
        if len(pending) >= limit:
            break
    logger.info("Found %d pending instances (lookback=%d days)", len(pending), lookback_days)
    return pending


@tool
def check_duplicate_approval(
    recharge_account: Annotated[str, "充值云账号 to check."],
    cloud_type: Annotated[str, "公有云类型 to check."] = "",
    lookback_days: Annotated[int, "Days to scan."] = 30,
) -> Dict[str, Any]:
    """
    Check for a PENDING approval with the same cloud type and recharge account.

    Returns has_duplicate=false if none found.
    Returns has_duplicate=true with instance details if one is found.
    Raises if a duplicate with mismatched fields exists.
    """
    token = _token()
    cfg = _approval_config()
    base_url = cfg.get("approval_base_url", APPROVAL_BASE)
    approval_code = cfg["approval_code"]

    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)

    listed = _api(
        f"{base_url}/approval/openapi/v2/instance/list",
        {"approval_code": approval_code, "start_time": start_ms, "end_time": end_ms, "limit": 100},
        token,
    )

    for code in listed.get("data", {}).get("instance_code_list", []):
        detail = _api(
            f"{base_url}/approval/openapi/v2/instance/get",
            {"approval_code": approval_code, "instance_code": code},
            token,
        )
        data = detail.get("data", {})
        if data.get("status") != "PENDING":
            continue
        form_list = data.get("form", "[]")
        if isinstance(form_list, str):
            form_list = json.loads(form_list)
        form_map = _form_list_to_name_map(form_list)
        if cloud_type and form_map.get("公有云类型") != cloud_type:
            continue
        if form_map.get("充值云账号") != recharge_account:
            continue
        return {
            "has_duplicate": True,
            "instance_code": code,
            "serial_number": data.get("serial_number"),
            "status": data.get("status"),
            "user_id": data.get("user_id"),
            "cloud_type": form_map.get("公有云类型"),
            "recharge_account": form_map.get("充值云账号"),
            "existing_form": form_map,
        }
    return {"has_duplicate": False}


@tool
def create_approval_instance(
    approval_code: Annotated[str, "Approval definition code."],
    user_id: Annotated[str, "Feishu user_id of the applicant (user_id format, not open_id)."],
    form: Annotated[List[Any], "Approval form as a list of {id, type, value} objects."],
) -> Dict[str, Any]:
    """
    Create a new Feishu approval instance.

    Dropdown fields must use the option value, not the display text.
    """
    cfg = _approval_config()
    base_url = cfg.get("approval_base_url", APPROVAL_BASE)
    token = _token()
    result = _api(
        f"{base_url}/approval/openapi/v2/instance/create",
        {"approval_code": approval_code, "user_id": user_id, "form": json.dumps(form, ensure_ascii=False)},
        token,
    )
    instance_code = result.get("data", {}).get("instance_code", "")
    logger.info(
        "Created approval instance: approval_code=%s user_id=%s*** instance_code=%s",
        approval_code, user_id[:8], instance_code,
    )
    return result


@tool
def validate_history(
    request_json: Annotated[str, "Request JSON as a string."],
    lookback_days: Annotated[int, "Days to look back."] = 30,
) -> Dict[str, Any]:
    """
    Compare the current request against historical approved instances with the same recharge account.

    Returns per-field match booleans so the agent can decide whether to proceed.
    """
    try:
        request_data = json.loads(request_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid request JSON: {exc}")

    token = _token()
    cfg = _approval_config()
    base_url = cfg.get("approval_base_url", APPROVAL_BASE)
    approval_code = cfg["approval_code"]
    cloud_type = request_data.get("cloud_type", request_data.get("公有云类型", ""))
    recharge_account = request_data.get("recharge_account", "")

    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)

    listed = _api(
        f"{base_url}/approval/openapi/v2/instance/list",
        {"approval_code": approval_code, "start_time": start_ms, "end_time": end_ms, "limit": 100},
        token,
    )

    matches: List[Dict[str, Any]] = []
    for code in listed.get("data", {}).get("instance_code_list", []):
        detail = _api(
            f"{base_url}/approval/openapi/v2/instance/get",
            {"approval_code": approval_code, "instance_code": code},
            token,
        )
        data = detail.get("data", {})
        if data.get("status") not in {"APPROVED", "PASSED", "DONE"}:
            continue
        form_list = data.get("form", "[]")
        if isinstance(form_list, str):
            form_list = json.loads(form_list)
        form_map = _form_list_to_name_map(form_list)
        if form_map.get("公有云类型") != cloud_type:
            continue
        if form_map.get("充值云账号") != recharge_account:
            continue

        remark_map = _parse_remark_lines(form_map.get("备注"))
        request_field_map = {
            "公有云类型": "cloud_type",
            "支付类型": "payment_type",
            "充值客户名称": "recharge_customer_name",
            "充值云账号": "recharge_account",
            "支付方式": "payment_way",
            "付款公司": "payment_company",
            "付款方式": "remit_method",
            "付款金额": "amount",
        }
        field_comps = []
        for fname, request_key in request_field_map.items():
            requested = request_data.get(request_key, request_data.get(fname))
            field_comps.append({
                "field": fname,
                "existing": form_map.get(fname),
                "requested": requested,
                "match": form_map.get(fname) == requested,
            })

        payee_comps = []
        payee = request_data.get("payee", {})
        for fname, fkey in [("户名", "account_name"), ("账号", "account_number"),
                             ("银行", "bank_name"), ("银行地区", "bank_region"), ("支行", "bank_branch")]:
            payee_comps.append({
                "field": fname,
                "existing": remark_map.get(fname),
                "requested": payee.get(fkey, ""),
                "match": remark_map.get(fname) == payee.get(fkey, ""),
            })

        matches.append({
            "instance_code": code,
            "serial_number": data.get("serial_number"),
            "status": data.get("status"),
            "all_match": all(c["match"] for c in field_comps + payee_comps),
            "bank_info_match": all(c["match"] for c in payee_comps),
        })

    return {
        "approval_code": approval_code,
        "cloud_type": cloud_type,
        "recharge_account": recharge_account,
        "has_fully_matched_history": any(m["all_match"] for m in matches),
        "has_bank_info_match": any(m["bank_info_match"] for m in matches),
        "matched_count": len(matches),
        "matched_instances": matches,
    }


# ---------------------------------------------------------------------------
# Tool list — imported by RechargeApprovalAgentRunner.build_tools()
# ---------------------------------------------------------------------------

def get_tools(runner_ref: Any = None) -> List[Any]:
    """
    Return the skill tools.

    If runner_ref is provided (RechargeApprovalAgentRunner instance), the
    plan → execute workflow tools are included.

    When runner_ref is None (e.g. legacy callers, tests), only the read-only
    informational tools are returned.
    """
    tools: List[Any] = [
        resolve_submitter_user_id,
        get_approval_definition,
        list_pending_instances,
        check_duplicate_approval,
        create_approval_instance,
        validate_history,
    ]
    if runner_ref is not None:
        tools.extend(build_recharge_plan_execute_tools(runner_ref))
    return tools


# ---------------------------------------------------------------------------
# WorkflowPlan / WorkflowResult — structured workflow tool return values
# ---------------------------------------------------------------------------

class WorkflowPlan(BaseModel):
    """Structured result returned by plan_recharge_approval_workflow."""

    success: bool = True
    error_message: str = ""
    request_file: str = ""
    request_file_name: str = ""
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    submitter_identifier: str = ""
    resolved_submitter_user_id: str = ""
    summary: str = ""


class WorkflowResult(BaseModel):
    """Structured result returned by execute_recharge_approval_plan."""

    success: bool = True
    error_message: str = ""
    deduplicated: bool = False
    existing_instance_code: str = ""
    existing_serial_number: str = ""
    instance_code: str = ""
    approval_code: str = ""
    status: str = ""
    summary: str = ""
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    notification_message: str = ""


# ---------------------------------------------------------------------------
# RunnerContext — the interface the workflow tool uses to talk to the runner
# ---------------------------------------------------------------------------

class RunnerContext:
    """
    Runtime context passed to the recharge approval workflow tools.

    Captures the RechargeApprovalAgentRunner instance fields and helper
    functions via closure. The Agent does NOT pass these through tool
    arguments — the tool reads them directly from the runner.
    """

    def __init__(
        self,
        record: Any,
        raw_recharge_info: str,
        submitter_identifier: str,
        submitter_user_label: str,
        resolved_submitter_user_id: str,
        parse_recharge_info_fn: Any,
        resolve_submitter_fn: Any,
        create_event_fn: Any,
        create_llm_run_fn: Any,
        normalize_status_fn: Any,
        workspace_root_fn: Any,
        token_fn: Any = None,
    ) -> None:
        self.record = record
        self.raw_recharge_info = raw_recharge_info
        self.submitter_identifier = submitter_identifier
        self.submitter_user_label = submitter_user_label
        self.resolved_submitter_user_id = resolved_submitter_user_id
        self._parse_recharge_info = parse_recharge_info_fn
        self._resolve_submitter = resolve_submitter_fn
        self._create_event = create_event_fn
        self._create_llm_run = create_llm_run_fn
        self._normalize_status = normalize_status_fn
        self._workspace_root = workspace_root_fn
        self._token_fn = token_fn

    def parse_recharge_info(self, raw: str) -> Dict[str, Any]:
        return self._parse_recharge_info(raw)

    def resolve_submitter_user_id(self, identifier: str, token: str) -> str:
        # Delegate to the closure in tools.py, which uses _token internally
        return self._resolve_submitter(identifier, token)

    def create_event(
        self,
        event_type: str,
        stage: str,
        source: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._create_event(
            record=self.record,
            event_type=event_type,
            stage=stage,
            source=source,
            message=message,
            payload=payload or {},
        )

    def create_llm_run(
        self,
        runner_type: str,
        provider: str,
        model: str,
        input_snapshot: str,
        output_snapshot: str,
        parsed_payload: Dict[str, Any],
        usage_payload: Dict[str, Any],
        stdout: str,
        stderr: str,
        success: bool,
        error_message: str = "",
        started_at: Any = None,
        finished_at: Any = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        self._create_llm_run(
            record=self.record,
            stage="skill_workflow",
            runner_type=runner_type,
            provider=provider,
            model=model,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            parsed_payload=parsed_payload,
            usage_payload=usage_payload,
            stdout=stdout,
            stderr=stderr,
            success=success,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=latency_ms,
        )

    def normalize_status(self, status: str) -> str:
        return self._normalize_status(status)

    def workspace_root(self) -> Path:
        return self._workspace_root()


def _build_workflow_runner_context(runner_ref: Any) -> RunnerContext:
    """
    Build a RunnerContext from a RechargeApprovalAgentRunner instance.

    Imports helpers lazily from services.py to avoid circular import at
    module-load time (tools.py is imported before Django is fully set up).
    """
    from cloud_billing.services.recharge_approval import (
        create_recharge_approval_event,
        create_recharge_approval_llm_run,
        normalize_feishu_status,
        parse_recharge_info,
        _workspace_root,
    )

    def resolve_submitter_closure(identifier: str, token: str) -> str:
        # Delegate to the existing _resolve_user_id helper in this module
        return _resolve_user_id(identifier)

    return RunnerContext(
        record=runner_ref.record,
        raw_recharge_info=runner_ref.raw_recharge_info,
        submitter_identifier=runner_ref.submitter_identifier,
        submitter_user_label=runner_ref.submitter_user_label,
        resolved_submitter_user_id=runner_ref.resolved_submitter_user_id,
        parse_recharge_info_fn=parse_recharge_info,
        resolve_submitter_fn=resolve_submitter_closure,
        create_event_fn=create_recharge_approval_event,
        create_llm_run_fn=create_recharge_approval_llm_run,
        normalize_status_fn=normalize_feishu_status,
        workspace_root_fn=_workspace_root,
    )


# ---------------------------------------------------------------------------
# plan_recharge_approval_workflow / execute_recharge_approval_plan
# ---------------------------------------------------------------------------

def _safe_filename_part(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
    text = text.strip(".-_")
    return (text or fallback)[:80]


def _request_file_for_payload(ctx: RunnerContext, parsed_payload: Dict[str, Any]) -> Path:
    provider = getattr(ctx.record, "provider", None)
    provider_id = getattr(provider, "id", "") or getattr(ctx.record, "provider_id", "")
    provider_name = getattr(provider, "name", "") or "provider"
    account_id = (
        parsed_payload.get("platform_account_id")
        or parsed_payload.get("account_id")
        or parsed_payload.get("recharge_account")
        or parsed_payload.get("充值云账号")
        or "unknown-account"
    )
    record_id = getattr(ctx.record, "id", "") or "new"
    filename = (
        "recharge-workflow-submit-"
        f"provider-{_safe_filename_part(provider_id or provider_name)}-"
        f"account-{_safe_filename_part(account_id)}-"
        f"record-{_safe_filename_part(record_id)}.json"
    )
    return Path("/tmp") / filename


def build_recharge_plan_execute_tools(runner_ref: Any) -> List[BaseTool]:
    """
    Factory — creates plan and execute tools bound to runner_ref.

    The plan tool must run first so the request JSON exists before execution.
    The execute tool only consumes that materialized JSON file.
    """

    ctx = _build_workflow_runner_context(runner_ref)

    def _mark_failed(error_text: str, *, started_at: Any, source: str) -> None:
        finished_at_err = datetime.now(timezone.utc)
        ctx.create_event(
            event_type="workflow_failed",
            stage="skill_workflow",
            source=source,
            message=error_text,
            payload={"error": error_text},
        )
        ctx.record.status = ctx.record.STATUS_FAILED
        ctx.record.status_message = error_text
        ctx.record.latest_stage = "skill_workflow"
        ctx.record.save(
            update_fields=["status", "status_message", "latest_stage", "updated_at"]
        )
        ctx.create_llm_run(
            runner_type="workflow",
            provider=source,
            model=source,
            input_snapshot="",
            output_snapshot="",
            parsed_payload={"error": error_text},
            usage_payload={},
            stdout="",
            stderr=error_text,
            success=False,
            error_message=error_text,
            started_at=started_at,
            finished_at=finished_at_err,
            latency_ms=max(0, int((finished_at_err - started_at).total_seconds() * 1000)),
        )

    @tool
    def plan_recharge_approval_workflow(
        raw_recharge_info: Annotated[
            str,
            (
                "Raw recharge info as JSON string or newline-delimited key:value text. "
                "Required fields: cloud_type, recharge_customer_name, recharge_account, "
                "payment_company, amount, currency. Payee account details must be written into "
                "备注 instead of remaining as structured JSON fields. If the amount is "
                "written like '200.00 CNY', split it into amount and currency."
            ),
        ],
        submitter_identifier: Annotated[
            str,
            "Submitter email address or mobile number (e.g. user@example.com). Overrides runner context.",
        ] = "",
    ) -> WorkflowPlan:
        """
        Plan the recharge approval workflow and write the request JSON file.

        This tool must be called before execute_recharge_approval_plan.
        """
        started_at = datetime.now(timezone.utc)
        input_snapshot = json.dumps(
            {
                "raw_recharge_info": raw_recharge_info,
                "submitter_identifier": submitter_identifier,
            },
            ensure_ascii=False,
        )
        source = "plan_recharge_approval_workflow"

        ctx.create_event(
            event_type="workflow_started",
            stage="skill_workflow",
            source=source,
            message="Recharge approval workflow planning started.",
            payload={"submitter_identifier": submitter_identifier},
        )

        try:
            ctx.create_event(
                event_type="workflow_step_parse_started",
                stage="skill_workflow",
                source=source,
                message="Parsing recharge info.",
            )
            try:
                parsed_payload = ctx.parse_recharge_info(raw_recharge_info)
            except (ValueError, json.JSONDecodeError) as exc:
                if ctx.raw_recharge_info:
                    parsed_payload = ctx.parse_recharge_info(ctx.raw_recharge_info)
                else:
                    raise RuntimeError(f"Failed to parse recharge info: {exc}") from exc

            ctx.create_event(
                event_type="workflow_step_parse_completed",
                stage="skill_workflow",
                source=source,
                message="Recharge info parsed.",
                payload={
                    "cloud_type": parsed_payload.get("cloud_type", ""),
                    "recharge_account": parsed_payload.get("recharge_account", ""),
                    "amount": parsed_payload.get("amount", ""),
                    "currency": parsed_payload.get("currency", ""),
                },
            )

            payee = parsed_payload.get("payee")
            if not payee or not isinstance(payee, dict) or not payee.get("account_name"):
                cloud_type = str(parsed_payload.get("cloud_type") or parsed_payload.get("公有云类型") or "").strip()
                recharge_account = str(parsed_payload.get("recharge_account") or "").strip()
                if cloud_type and recharge_account:
                    ctx.create_event(
                        event_type="workflow_step_infer_payee_started",
                        stage="skill_workflow",
                        source=source,
                        message="Payee missing from request; inferring from Feishu history.",
                    )
                    inferred_payee = _find_payee_from_history(cloud_type, recharge_account)
                    if inferred_payee:
                        parsed_payload["payee"] = inferred_payee
                        ctx.create_event(
                            event_type="workflow_step_infer_payee_completed",
                            stage="skill_workflow",
                            source=source,
                            message="Payee inferred from historical approval.",
                            payload={
                                "account_name": inferred_payee.get("account_name", ""),
                                "account_number": str(inferred_payee.get("account_number", ""))[:6] + "***",
                            },
                        )
                    else:
                        ctx.create_event(
                            event_type="workflow_step_infer_payee_failed",
                            stage="skill_workflow",
                            source=source,
                            message="Could not infer payee from Feishu history; submission may fail.",
                        )

            payee = parsed_payload.get("payee")
            if isinstance(payee, dict):
                payee_remark = _build_remark(payee)
                existing_remark = str(parsed_payload.get("remark") or "").strip()
                if existing_remark:
                    if payee_remark not in existing_remark:
                        parsed_payload["remark"] = f"{existing_remark}\n{payee_remark}"
                    else:
                        parsed_payload["remark"] = existing_remark
                else:
                    parsed_payload["remark"] = payee_remark
                parsed_payload.pop("payee", None)

            submitter_ident = submitter_identifier or ctx.submitter_identifier
            resolved_user_id = ctx.resolved_submitter_user_id
            if not resolved_user_id and submitter_ident:
                ctx.create_event(
                    event_type="workflow_step_resolve_started",
                    stage="skill_workflow",
                    source=source,
                    message=f"Resolving submitter: {submitter_ident}",
                )
                resolved_user_id = _resolve_user_id(submitter_ident)
                ctx.create_event(
                    event_type="workflow_step_resolve_completed",
                    stage="skill_workflow",
                    source=source,
                    message=f"Resolved user_id={resolved_user_id[:8]}***",
                    payload={"user_id": resolved_user_id, "identifier": submitter_ident},
                )

            request_file = _request_file_for_payload(ctx, parsed_payload)
            request_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = request_file.with_suffix(request_file.suffix + ".tmp")
            tmp_file.write_text(
                json.dumps(parsed_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp_file.replace(request_file)

            plan = WorkflowPlan(
                success=True,
                request_file=str(request_file),
                request_file_name=request_file.name,
                request_payload=parsed_payload,
                submitter_identifier=submitter_ident,
                resolved_submitter_user_id=resolved_user_id,
                summary=f"Request JSON generated at {request_file.name}",
            )
            ctx.create_event(
                event_type="workflow_plan_created",
                stage="skill_workflow",
                source=source,
                message="Recharge approval request JSON generated.",
                payload={
                    "request_file": str(request_file),
                    "request_file_name": request_file.name,
                    "recharge_account": parsed_payload.get("recharge_account", ""),
                },
            )
            finished_at = datetime.now(timezone.utc)
            ctx.create_llm_run(
                runner_type="workflow_plan",
                provider=source,
                model=source,
                input_snapshot=input_snapshot,
                output_snapshot=json.dumps(plan.model_dump(), ensure_ascii=False),
                parsed_payload=plan.model_dump(),
                usage_payload={},
                stdout="",
                stderr="",
                success=True,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
            )
            return plan
        except Exception as exc:
            _mark_failed(str(exc), started_at=started_at, source=source)
            raise

    @tool
    def execute_recharge_approval_plan(
        request_file: Annotated[
            str,
            "Absolute path to the request JSON generated by plan_recharge_approval_workflow.",
        ],
        submitter_identifier: Annotated[
            str,
            "Submitter email address or mobile number returned by the plan step.",
        ] = "",
        resolved_submitter_user_id: Annotated[
            str,
            "Resolved Feishu user_id returned by the plan step.",
        ] = "",
    ) -> WorkflowResult:
        """
        Execute a previously generated recharge approval plan.

        This tool fails fast if the request JSON file does not exist.
        """
        started_at = datetime.now(timezone.utc)
        source = "execute_recharge_approval_plan"
        request_path = Path(request_file).expanduser()
        input_snapshot = json.dumps(
            {
                "request_file": str(request_path),
                "submitter_identifier": submitter_identifier,
                "resolved_submitter_user_id": resolved_submitter_user_id,
            },
            ensure_ascii=False,
        )

        try:
            if not request_path.exists():
                raise RuntimeError(
                    f"Request JSON file does not exist; run plan_recharge_approval_workflow first: {request_path}"
                )
            parsed_payload = json.loads(request_path.read_text(encoding="utf-8"))
            if not isinstance(parsed_payload, dict):
                raise RuntimeError(f"Request JSON must contain an object: {request_path}")

            submitter_ident = submitter_identifier or ctx.submitter_identifier
            resolved_user_id = resolved_submitter_user_id or ctx.resolved_submitter_user_id
            if not resolved_user_id and submitter_ident:
                resolved_user_id = _resolve_user_id(submitter_ident)

            script_path = (
                ctx.workspace_root()
                / "cloud_billing"
                / "skills"
                / "feishu-cloud-billing-approval"
                / "scripts"
                / "submit_recharge_approval.py"
            )

            env: Dict[str, str] = {**os.environ}
            for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APPROVAL_CODE"):
                env.setdefault(key, os.environ.get(key, ""))

            cmd: List[str] = [
                sys.executable,
                str(script_path),
                "submit",
                "--request-file",
                str(request_path),
            ]
            if resolved_user_id:
                cmd.extend(["--user-id", resolved_user_id])
            elif submitter_ident:
                cmd.extend(["--user-identifier", submitter_ident])

            ctx.create_event(
                event_type="workflow_step_script_started",
                stage="skill_workflow",
                source=source,
                message="Running Feishu approval script.",
                payload={"script": str(script_path.name), "request_file": str(request_path)},
            )

            script_start = time_module.monotonic()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            script_latency_ms = int((time_module.monotonic() - script_start) * 1000)
            script_finished = datetime.now(timezone.utc)
            script_started_approx = _subtract_ms(script_finished, script_latency_ms)

            stdout_text = (result.stdout or "").strip()
            try:
                script_output: Dict[str, Any] = json.loads(stdout_text)
            except json.JSONDecodeError:
                script_output = {"raw_stdout": stdout_text}

            # Record script execution as a LLM run
            ctx.create_llm_run(
                runner_type="workflow_script",
                provider="subprocess",
                model="submit_recharge_approval.py",
                input_snapshot=json.dumps(
                    {"request_file": str(request_path), "args": cmd[2:]},
                    ensure_ascii=False,
                ),
                output_snapshot=stdout_text[:4000],
                parsed_payload={
                    "script": "submit_recharge_approval.py",
                    "exit_code": result.returncode,
                    "success": result.returncode == 0,
                    "latency_ms": script_latency_ms,
                },
                usage_payload={"latency_ms": script_latency_ms},
                stdout=stdout_text[:8000],
                stderr=(result.stderr or "")[:2000],
                success=result.returncode == 0,
                error_message="" if result.returncode == 0 else (result.stderr or ""),
                started_at=script_started_approx,
                finished_at=script_finished,
                latency_ms=script_latency_ms,
            )

            # Record individual HTTP traces from script stdout
            for trace in script_output.get("http_traces", []):
                if not isinstance(trace, dict):
                    continue
                endpoint = str(trace.get("endpoint_name") or "http")
                ctx.create_llm_run(
                    runner_type="skill_http",
                    provider="urllib.request",
                    model=endpoint,
                    input_snapshot=json.dumps(
                        trace.get("request_preview", {}), ensure_ascii=False
                    )[:4000],
                    output_snapshot=json.dumps(
                        trace.get("response_preview", {}), ensure_ascii=False
                    )[:4000],
                    parsed_payload={**trace, "parent_script": "submit_recharge_approval.py"},
                    usage_payload={},
                    stdout=json.dumps(trace.get("response_preview", {}), ensure_ascii=False)[
                        :8000
                    ],
                    stderr=str(trace.get("error") or ""),
                    success=bool(trace.get("success")),
                    error_message=str(trace.get("error") or ""),
                    started_at=script_finished,
                    finished_at=script_finished,
                    latency_ms=int(trace.get("latency_ms") or 0),
                )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Script exited {result.returncode}: "
                    f"{(result.stderr or '').strip() or stdout_text[:500]}"
                )

            # ── Step 6: Process result ─────────────────────────────────────
            deduplicated = bool(script_output.get("deduplicated"))
            existing: Dict[str, Any] = script_output.get("existing_instance") or {}
            response_data: Dict[str, Any] = script_output.get("response") or {}

            instance_code = str(
                existing.get("instance_code")
                or response_data.get("data", {}).get("instance_code")
                or ""
            )
            approval_code = str(
                script_output.get("approval_code") or env.get("FEISHU_APPROVAL_CODE", "")
            )

            raw_status = ""
            if deduplicated:
                raw_status = str(existing.get("status") or "PENDING")
            elif response_data:
                raw_status = "PENDING"
            normalized_status = ctx.normalize_status(raw_status)

            summary_parts: List[str] = []
            if deduplicated:
                summary_parts.append(
                    f"Reused existing pending instance "
                    f"{existing.get('serial_number') or existing.get('instance_code', '')}"
                )
            else:
                summary_parts.append("Submitted new instance")
            if instance_code:
                summary_parts.append(f"instance={instance_code}")
            summary = "; ".join(summary_parts)

            # Build the pre-formatted notification message from the parsed payload
            from cloud_billing.services.recharge_approval import (
                build_notification_message_from_payload,
            )

            trigger_user_label = (
                getattr(ctx.record.triggered_by, "username", None) or
                ctx.record.triggered_by_username_snapshot or
                ""
            )
            notification_msg = build_notification_message_from_payload(
                parsed_payload,
                notification_type="submitted",
                trigger_source=getattr(ctx.record, "trigger_source", "manual") or "manual",
                trigger_reason=getattr(ctx.record, "trigger_reason", "") or "",
                trigger_user_label=trigger_user_label,
                submitter_label=ctx.submitter_user_label or ctx.submitter_identifier or "",
                provider_name=(
                    getattr(getattr(ctx.record, "provider", None), "display_name", None)
                    or ""
                ),
                approval_status="已提交",
            )

            # Update the DB record directly
            ctx.record.request_payload = parsed_payload
            ctx.record.response_payload = script_output
            ctx.record.feishu_instance_code = instance_code or None
            ctx.record.feishu_approval_code = approval_code or None
            ctx.record.status = normalized_status
            ctx.record.status_message = summary
            ctx.record.latest_stage = "skill_workflow"
            ctx.record.context_payload = {
                **(ctx.record.context_payload or {}),
                "notification_message": notification_msg,
            }
            ctx.record.save(
                update_fields=[
                    "request_payload",
                    "response_payload",
                    "feishu_instance_code",
                    "feishu_approval_code",
                    "status",
                    "status_message",
                    "latest_stage",
                    "context_payload",
                    "updated_at",
                ]
            )

            result_obj = WorkflowResult(
                success=True,
                deduplicated=deduplicated,
                existing_instance_code=str(existing.get("instance_code") or ""),
                existing_serial_number=str(existing.get("serial_number") or ""),
                instance_code=instance_code,
                approval_code=approval_code,
                status=normalized_status,
                summary=summary,
                request_payload=parsed_payload,
                notification_message=notification_msg,
            )

            ctx.create_event(
                event_type="workflow_completed",
                stage="skill_workflow",
                source=source,
                message=summary,
                payload=result_obj.model_dump(),
            )

            # Record the overall workflow tool call
            finished_at = datetime.now(timezone.utc)
            ctx.create_llm_run(
                runner_type="workflow",
                provider=source,
                model=source,
                input_snapshot=input_snapshot,
                output_snapshot=json.dumps(result_obj.model_dump(), ensure_ascii=False),
                parsed_payload=result_obj.model_dump(),
                usage_payload={},
                stdout="",
                stderr="",
                success=True,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=max(
                    0, int((finished_at - started_at).total_seconds() * 1000)
                ),
            )

            return result_obj

        except Exception as exc:
            _mark_failed(str(exc), started_at=started_at, source=source)
            raise

    return [plan_recharge_approval_workflow, execute_recharge_approval_plan]


def _subtract_ms(dt: Any, ms: int) -> Any:
    """Subtract milliseconds from a timezone-aware datetime."""
    from datetime import timedelta
    return dt - timedelta(milliseconds=ms)
