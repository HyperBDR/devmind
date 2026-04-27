#!/usr/bin/env python3
"""Submit Feishu recharge approvals with duplicate detection and strict validation."""

from __future__ import annotations

import argparse
import datetime as dt
import copy
import hashlib
import re
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

AUTH_BASE_URL = "https://open.feishu.cn"
APPROVAL_BASE_URL = "https://www.feishu.cn"
DEFAULT_LOOKBACK_DAYS = 90
HISTORY_BATCH_SIZE = 10
TIMEZONE_OFFSET = "+08:00"
HTTP_TRACES: list[dict[str, Any]] = []
CURRENT_ARGS: argparse.Namespace | None = None
SENSITIVE_KEY_MARKERS = ("SECRET", "TOKEN", "PASSWORD", "KEY", "AUTHORIZATION")

FIELD_CLOUD_TYPE = "公有云类型"
FIELD_PAYMENT_TYPE = "支付类型"
FIELD_RECHARGE_CUSTOMER = "充值客户名称"
FIELD_RECHARGE_ACCOUNT = "充值云账号"
FIELD_PAYMENT_NOTE = "付款说明"
FIELD_PAYMENT_WAY = "支付方式"
FIELD_PAYMENT_COMPANY = "付款公司"
FIELD_REMIT_METHOD = "付款方式"  # 付款方式（转账/支付宝），区别于"支付方式"（公司支付/充值报销）
FIELD_AMOUNT = "付款金额"
FIELD_EXPECTED_DATE = "期望到账时间"
FIELD_NOTE1 = "说明 1"  # text 字段，提示用户关联报销审批
FIELD_REMARK = "备注"

BASE_MANAGED_FIELDS = [
    FIELD_CLOUD_TYPE,
    FIELD_PAYMENT_TYPE,
    FIELD_RECHARGE_CUSTOMER,
    FIELD_RECHARGE_ACCOUNT,
    FIELD_PAYMENT_WAY,
    FIELD_PAYMENT_COMPANY,
    FIELD_REMIT_METHOD,
    FIELD_AMOUNT,
    FIELD_EXPECTED_DATE,
    FIELD_NOTE1,
    FIELD_REMARK,
]

PAYMENT_TYPE_VALUES = {"仅充值", "仅划拨", "充值+划拨", "费用结算"}
PAYMENT_WAY_VALUES = {"公司支付", "充值报销"}
REMIT_METHOD_VALUES = {"转账", "支付宝"}


class ApprovalError(RuntimeError):
    """Raised when Feishu API calls fail."""


def reset_http_traces() -> None:
    HTTP_TRACES.clear()


def get_http_traces() -> list[dict[str, Any]]:
    return copy.deepcopy(HTTP_TRACES)


def redact_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    import re

    text = re.sub(
        r"(?i)(secret|token|password|authorization|app_secret)(['\"\s:=]+)([^,'\"\s}]+)",
        r"\1\2***REDACTED***",
        text,
    )
    text = re.sub(r"\b\d{12,}\b", lambda match: f"***{match.group(0)[-4:]}", text)
    return text


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_upper = str(key).upper()
            if any(marker in key_upper for marker in SENSITIVE_KEY_MARKERS):
                result[key] = "***REDACTED***"
            else:
                result[key] = sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def preview_payload(value: Any, limit: int = 2000) -> Any:
    sanitized = sanitize_payload(value)
    text = json.dumps(sanitized, ensure_ascii=False) if not isinstance(sanitized, str) else sanitized
    if len(text) <= limit:
        return sanitized
    return redact_text(text[:limit])


def debug(message: str) -> None:
    print(message, file=sys.stderr)


def record_http_trace(
    *,
    endpoint_name: str,
    url: str,
    method: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    started_at: str,
    latency_ms: int,
    success: bool,
    http_status: int | None = None,
    response: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    HTTP_TRACES.append(
        {
            "sequence": len(HTTP_TRACES) + 1,
            "endpoint_name": endpoint_name,
            "method": method,
            "url": url,
            "started_at": started_at,
            "latency_ms": latency_ms,
            "success": success,
            "http_status": http_status,
            "feishu_code": (response or {}).get("code"),
            "feishu_msg": (response or {}).get("msg", ""),
            "error": redact_text(error),
            "request_preview": {
                "payload": preview_payload(payload),
                "headers": preview_payload(headers),
            },
            "response_preview": preview_payload(response or {"error": error}),
        }
    )


def request_file_sha256(args: argparse.Namespace) -> str:
    request_file = getattr(args, "request_file", "")
    if not request_file:
        return ""
    try:
        return hashlib.sha256(Path(request_file).expanduser().resolve().read_bytes()).hexdigest()
    except OSError:
        return ""


def build_script_trace(args: argparse.Namespace, *, success: bool, exit_code: int | str) -> dict[str, Any]:
    return {
        "script_path": str(Path(__file__).resolve()),
        "script_name": Path(__file__).name,
        "args": sanitize_payload(sys.argv[1:]),
        "command": getattr(args, "command", ""),
        "request_file": str(Path(getattr(args, "request_file", "")).expanduser().resolve()) if getattr(args, "request_file", "") else "",
        "request_file_sha256": request_file_sha256(args),
        "env_keys": sorted(
            key
            for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APPROVAL_CODE", "FEISHU_USER_ID", "FEISHU_USER_IDENTIFIER")
            if os.getenv(key)
        ),
        "success": success,
        "exit_code": exit_code,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List pending recharge approvals or submit a new recharge approval. "
            "Use environment variables for FEISHU_APP_ID, FEISHU_APP_SECRET, and FEISHU_APPROVAL_CODE."
        )
    )
    def add_runtime_options(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--user-id",
            default=None,
            help="Applicant user_id. Falls back to FEISHU_USER_ID when omitted.",
        )
        target.add_argument(
            "--user-identifier",
            default=None,
            help=(
                "Applicant email address or mobile number. Falls back to "
                "FEISHU_USER_IDENTIFIER and is resolved to user_id before submit."
            ),
        )
        target.add_argument(
            "--lookback-days",
            type=int,
            default=None,
            help=f"How many past days to scan for instances. Default: {DEFAULT_LOOKBACK_DAYS}",
        )
        target.add_argument(
            "--output",
            default=None,
            help="Optional JSON output path.",
        )
        target.add_argument(
            "--indent",
            type=int,
            default=None,
            help="JSON indentation. Default: 2",
        )
        target.add_argument(
            "--include-http-traces",
            action="store_true",
            help="Include sanitized per-request HTTP traces in stdout.",
        )

    parser.add_argument(
        "--base-url",
        default=APPROVAL_BASE_URL,
        help="Approval API base URL. Default: https://www.feishu.cn",
    )
    parser.add_argument(
        "--auth-base-url",
        default=AUTH_BASE_URL,
        help="Auth API base URL. Default: https://open.feishu.cn",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Applicant user_id. Falls back to FEISHU_USER_ID when omitted.",
    )
    parser.add_argument(
        "--user-identifier",
        default=None,
        help=(
            "Applicant email address or mobile number. Falls back to "
            "FEISHU_USER_IDENTIFIER and is resolved to user_id before submit."
        ),
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="How many past days to scan for instances. Default: 30",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=None,
        help="JSON indentation. Default: 2",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list-pending",
        help="List current PENDING instances for the configured approval flow.",
    )
    add_runtime_options(list_parser)
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max instances to return after filtering. Default: 20",
    )

    history_parser = subparsers.add_parser(
        "validate-history",
        help="Compare the current request against historical approved instances with the same recharge account.",
    )
    add_runtime_options(history_parser)
    history_parser.add_argument(
        "--request-file",
        required=True,
        help="Path to a request JSON file.",
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max matched history instances to return. Default: 20",
    )

    submit_parser = subparsers.add_parser(
        "submit",
        help="Submit a recharge approval from a request JSON file.",
    )
    add_runtime_options(submit_parser)
    submit_parser.add_argument(
        "--request-file",
        required=True,
        help="Path to a request JSON file.",
    )
    submit_parser.add_argument(
        "--skip-duplicate-check",
        action="store_true",
        help="Skip checking pending instances before submit.",
    )

    args = parser.parse_args()
    if args.user_id is None:
        args.user_id = ""
    if args.user_identifier is None:
        args.user_identifier = ""
    if args.lookback_days is None:
        args.lookback_days = DEFAULT_LOOKBACK_DAYS
    if args.output is None:
        args.output = ""
    if args.indent is None:
        args.indent = 2
    return args


def emit_payload(args: argparse.Namespace, payload: dict[str, Any], *, success: bool, exit_code: int = 0) -> None:
    payload["script_trace"] = build_script_trace(
        args, success=success, exit_code=exit_code)
    if getattr(args, "include_http_traces", False):
        payload["http_traces"] = get_http_traces()
    if args.output:
        write_json(args.output, payload, args.indent)
    print(json.dumps(payload, ensure_ascii=False, indent=args.indent))


def getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Environment variable {name} is required.")
    return value


def read_json(path_str: str) -> Any:
    path = Path(path_str).expanduser().resolve()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Request file not found: {path}") from exc
    except OSError as exc:
        raise SystemExit(f"Could not read request file {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Request file is not valid JSON: {path}: {exc}") from exc


def write_json(path_str: str, payload: Any, indent: int) -> None:
    path = Path(path_str).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
                    indent=indent) + "\n", encoding="utf-8")


def api_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int = 30,
    endpoint_name: str = "",
) -> dict[str, Any]:
    method = "POST"
    endpoint_name = endpoint_name or url.rstrip("/").rsplit("/", 1)[-1]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    start = time.monotonic()
    http_status: int | None = None
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            http_status = getattr(response, "status", None) or getattr(response, "code", None)
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        record_http_trace(
            endpoint_name=endpoint_name,
            url=url,
            method=method,
            payload=payload,
            headers=headers,
            started_at=started_at,
            latency_ms=int((time.monotonic() - start) * 1000),
            success=False,
            http_status=exc.code,
            response={"error": body},
            error=f"HTTP {exc.code}: {body}",
        )
        raise ApprovalError(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        record_http_trace(
            endpoint_name=endpoint_name,
            url=url,
            method=method,
            payload=payload,
            headers=headers,
            started_at=started_at,
            latency_ms=int((time.monotonic() - start) * 1000),
            success=False,
            http_status=http_status,
            response={"error": str(exc.reason)},
            error=f"Network error: {exc.reason}",
        )
        raise ApprovalError(f"Network error for {url}: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        record_http_trace(
            endpoint_name=endpoint_name,
            url=url,
            method=method,
            payload=payload,
            headers=headers,
            started_at=started_at,
            latency_ms=int((time.monotonic() - start) * 1000),
            success=False,
            http_status=http_status,
            response={"raw_body": body},
            error=f"Invalid JSON response: {body}",
        )
        raise ApprovalError(
            f"Invalid JSON response from {url}: {body}") from exc

    code = data.get("code", 0)
    success = code in (0, None)
    record_http_trace(
        endpoint_name=endpoint_name,
        url=url,
        method=method,
        payload=payload,
        headers=headers,
        started_at=started_at,
        latency_ms=int((time.monotonic() - start) * 1000),
        success=success,
        http_status=http_status,
        response=data,
        error="" if success else f"Feishu API error {code}: {data.get('msg', '')}",
    )
    if code not in (0, None):
        raise ApprovalError(
            f"Feishu API error {code} for {url}: {data.get('msg', '')}")
    return data


def get_tenant_access_token(app_id: str, app_secret: str, auth_base_url: str) -> str:
    response = api_request(
        url=f"{auth_base_url.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        payload={"app_id": app_id, "app_secret": app_secret},
        headers={"Content-Type": "application/json; charset=utf-8"},
        endpoint_name="tenant_token",
    )
    token = response.get("tenant_access_token")
    if not token:
        raise ApprovalError("No tenant_access_token returned by auth API.")
    return str(token)


def _resolve_user_id(auth_base_url: str, token: str, identifier: str) -> str:
    """
    Resolve a Feishu user_id from an email or mobile number.

    Uses the user_id_type query parameter with user_id (not open_id) because the Feishu approval
    API requires user_id format.
    """
    payload: dict[str, Any] = {
        "include_resigned": True, "emails": [], "mobiles": []}
    is_email = "@" in identifier
    if is_email:
        payload["emails"] = [identifier]
    else:
        payload["mobiles"] = [identifier.strip().lstrip("+")]

    result = api_request(
        url=f"{auth_base_url.rstrip('/')}/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id",
        payload=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        endpoint_name="resolve_user_id",
    )
    user_list = result.get("data", {}).get("user_list", [])
    if not user_list:
        raise ApprovalError(
            f"Could not resolve user_id from identifier: {identifier!r}. "
            "Ensure the email/mobile is registered in Feishu."
        )
    resolved = user_list[0].get("user_id", "")
    if not resolved:
        raise ApprovalError(
            f"Could not resolve user_id from identifier: {identifier!r}. "
            "Feishu returned no user_id in response."
        )
    return str(resolved)


def approval_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def get_approval_definition(base_url: str, token: str, approval_code: str) -> dict[str, Any]:
    return api_request(
        url=f"{base_url.rstrip('/')}/approval/openapi/v2/approval/get",
        payload={"approval_code": approval_code},
        headers=approval_headers(token),
        endpoint_name="approval_get",
    )


def list_instances(
    base_url: str,
    token: str,
    approval_code: str,
    start_time_ms: int,
    end_time_ms: int,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    return api_request(
        url=f"{base_url.rstrip('/')}/approval/openapi/v2/instance/list",
        payload={
            "approval_code": approval_code,
            "start_time": start_time_ms,
            "end_time": end_time_ms,
            "limit": limit,
            "offset": offset,
        },
        headers=approval_headers(token),
        endpoint_name="instance_list",
    )


def get_instance(base_url: str, token: str, approval_code: str, instance_code: str) -> dict[str, Any]:
    return api_request(
        url=f"{base_url.rstrip('/')}/approval/openapi/v2/instance/get",
        payload={"approval_code": approval_code,
                 "instance_code": instance_code},
        headers=approval_headers(token),
        endpoint_name="instance_get",
    )


def _is_deleted_history_instance_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("http 404", "http 410", "not found", "deleted", "gone")
    )


def _history_instance_sort_key(value: Any) -> int:
    """Normalize history timestamps for descending recency sort."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def _history_instances_recent_first(
    base_url: str,
    token: str,
    approval_code: str,
    instance_codes: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    """
    Load instance details and order them from newest to oldest.

    Feishu list endpoints do not always guarantee the order we need for
    sync/preflight decisions, so we normalize by the live instance start time.
    """
    instances: list[tuple[int, int, str, dict[str, Any]]] = []
    for original_index, instance_code in enumerate(instance_codes):
        try:
            detail = get_instance(base_url, token, approval_code, instance_code)
        except ApprovalError as exc:
            if _is_deleted_history_instance_error(exc):
                debug(
                    "Feishu history lookup: skip deleted instance "
                    f"(instance_code={instance_code}, error={exc})"
                )
                continue
            raise
        data = detail.get("data", {}) or {}
        sort_time = _history_instance_sort_key(
            data.get("start_time") or data.get("end_time")
        )
        instances.append((sort_time, original_index, instance_code, data))

    instances.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(instance_code, data) for _, _, instance_code, data in instances]


def _list_history_instance_codes(
    base_url: str,
    token: str,
    approval_code: str,
    start_time_ms: int,
    end_time_ms: int,
    *,
    batch_size: int = HISTORY_BATCH_SIZE,
) -> list[str]:
    instance_codes: list[str] = []
    offset = 0
    while True:
        listed = list_instances(
            base_url,
            token,
            approval_code,
            start_time_ms,
            end_time_ms,
            limit=batch_size,
            offset=offset,
        )
        page_codes = listed.get("data", {}).get("instance_code_list", []) or []
        if not page_codes:
            break
        for code in page_codes:
            code_text = str(code or "").strip()
            if code_text:
                instance_codes.append(code_text)
        if len(page_codes) < batch_size:
            break
        offset += batch_size
    return instance_codes


def create_instance(base_url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return api_request(
        url=f"{base_url.rstrip('/')}/approval/openapi/v2/instance/create",
        payload=payload,
        headers=approval_headers(token),
        endpoint_name="instance_create",
    )


def parse_definition_schema(definition: dict[str, Any]) -> list[dict[str, Any]]:
    form_raw = definition.get("data", {}).get("form", "[]")
    if isinstance(form_raw, list):
        return form_raw
    return json.loads(form_raw)


def build_schema_by_name(schema: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in schema if isinstance(item, dict) and item.get("name")}


def normalize_date(value: str) -> str:
    date_obj = dt.datetime.strptime(value, "%Y-%m-%d").date()
    return f"{date_obj.isoformat()}T00:00:00{TIMEZONE_OFFSET}"


def default_expected_date() -> str:
    tz = dt.timezone(dt.timedelta(hours=8))
    target = dt.datetime.now(tz).date() + dt.timedelta(days=7)
    return target.isoformat()


def build_remark(request_data: dict[str, Any]) -> str:
    payee = request_data["payee"]
    lines = [
        f"账户类型：{payee['type']}",
        f"户名：{payee['account_name']}",
        f"账号：{payee['account_number']}",
        f"银行：{payee['bank_name']}",
        f"银行地区：{payee['bank_region']}",
        f"支行：{payee['bank_branch']}",
    ]
    return "\n".join(lines)


def parse_remark_lines(remark: str | None) -> dict[str, str]:
    if not remark:
        return {}
    result: dict[str, str] = {}
    for line in str(remark).splitlines():
        line = line.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        result[key.strip()] = value.strip()
    return result


def payee_from_remark(remark: str | None) -> dict[str, str]:
    remark_map = parse_remark_lines(remark)
    return {
        "type": str(
            remark_map.get("账户类型")
            or remark_map.get("收款账户类型")
            or ""
        ).strip(),
        "account_name": str(remark_map.get("户名") or "").strip(),
        "account_number": str(remark_map.get("账号") or "").strip(),
        "bank_name": str(remark_map.get("银行") or "").strip(),
        "bank_region": str(remark_map.get("银行地区") or "").strip(),
        "bank_branch": str(remark_map.get("支行") or "").strip(),
    }


def request_data_from_history_form(form_map: dict[str, Any]) -> dict[str, Any]:
    remark_map = parse_remark_lines(form_map.get(FIELD_REMARK))
    payee = {
        "type": str(remark_map.get("账户类型") or "").strip(),
        "account_name": str(remark_map.get("户名") or "").strip(),
        "account_number": str(remark_map.get("账号") or "").strip(),
        "bank_name": str(remark_map.get("银行") or "").strip(),
        "bank_region": str(remark_map.get("银行地区") or "").strip(),
        "bank_branch": str(remark_map.get("支行") or "").strip(),
    }
    request_data = {
        "cloud_type": str(form_map.get(FIELD_CLOUD_TYPE) or "").strip(),
        "payment_type": str(form_map.get(FIELD_PAYMENT_TYPE) or "仅充值").strip(),
        "recharge_customer_name": str(form_map.get(FIELD_RECHARGE_CUSTOMER) or "").strip(),
        "recharge_account": str(form_map.get(FIELD_RECHARGE_ACCOUNT) or "").strip(),
        "payment_way": str(form_map.get(FIELD_PAYMENT_WAY) or "公司支付").strip(),
        "payment_company": str(form_map.get(FIELD_PAYMENT_COMPANY) or "").strip(),
        "remit_method": str(form_map.get(FIELD_REMIT_METHOD) or "转账").strip(),
        "amount": form_map.get(FIELD_AMOUNT),
        "currency": "CNY",
        "payee": payee,
    }
    payment_note = str(form_map.get(FIELD_PAYMENT_NOTE) or "").strip()
    if payment_note:
        request_data["payment_note"] = payment_note
    return request_data


def option_text_to_key(field_schema: dict[str, Any], submitted_text: str) -> str:
    options = field_schema.get("option") or []
    mapping = {str(item.get("text", "")).strip(): str(
        item.get("value", "")).strip() for item in options}
    if submitted_text not in mapping:
        allowed = ", ".join(sorted(text for text in mapping if text))
        raise SystemExit(
            f"Invalid option for '{field_schema['name']}': {submitted_text}. Allowed values: {allowed}"
        )
    return mapping[submitted_text]


def require_field(request_data: dict[str, Any], key: str) -> Any:
    value = request_data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise SystemExit(f"Request file is missing required field: {key}")
    return value


def split_amount_and_currency(value: Any) -> tuple[Any, str]:
    if value is None:
        return "", ""
    if isinstance(value, (int, float)):
        return value, ""

    text = str(value).strip()
    if not text:
        return "", ""

    match = re.match(
        r"^\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*([A-Za-z]{3,5})?\s*$",
        text,
    )
    if not match:
        return value, ""

    amount_text = match.group(1).replace(",", "")
    currency = str(match.group(2) or "").strip().upper()
    try:
        amount_value: Any = int(amount_text)
    except ValueError:
        amount_value = float(amount_text)
    return amount_value, currency


def normalize_request_data(request_data: dict[str, Any]) -> dict[str, Any]:
    """
    Repair common parsed-field confusion before Feishu option validation.

    The approval form has two similarly named fields:
    - 支付类型/payment_type: 仅充值, 仅划拨, 充值+划拨, 费用结算
    - 付款方式/remit_method: 转账, 支付宝

    Free-form recharge text and LLM extraction can accidentally put "转账" into
    payment_type. Normalize that at the request boundary so the form builder
    validates the right value against the right widget.
    """
    payment_type = str(request_data.get("payment_type") or "").strip()
    payment_way = str(request_data.get("payment_way") or "").strip()
    remit_method = str(request_data.get("remit_method") or "").strip()

    if payment_type in REMIT_METHOD_VALUES:
        if not remit_method:
            request_data["remit_method"] = payment_type
        request_data["payment_type"] = "仅充值"

    if payment_way in REMIT_METHOD_VALUES:
        if not str(request_data.get("remit_method") or "").strip():
            request_data["remit_method"] = payment_way
        request_data["payment_way"] = "公司支付"

    amount_value, currency = split_amount_and_currency(
        request_data.get("amount"))
    request_data["amount"] = amount_value
    existing_currency = str(request_data.get("currency") or "").strip().upper()
    request_data["currency"] = existing_currency or currency or "CNY"

    return request_data


def validate_unsupported_account_widgets(
    request_data: dict[str, Any],
    schema_by_name: dict[str, dict[str, Any]],
) -> None:
    """
    Reject approval definitions that require Feishu account widgets we cannot fill.

    This flow writes payee details into 备注. If the live approval definition makes a
    dedicated 收款账户 widget required for the selected 支付方式, the API cannot
    complete the instance creation reliably and the submission must stop here.
    """
    account_schema = schema_by_name.get("收款账户")
    if not account_schema or not account_schema.get("required"):
        return
    payment_way = str(request_data.get("payment_way", "公司支付")).strip()
    if payment_way != "公司支付":
        return
    raise SystemExit(
        "Approval definition requires 收款账户 when 支付方式=公司支付. "
        "This skill writes payee information to 备注, and the API cannot populate "
        "the 收款账户 widget for this form."
    )


def _infer_payee_from_history(cloud_type: str, recharge_account: str, token: str) -> dict[str, Any] | None:
    """
    Search completed approval instances for matching cloud_type + recharge_account
    and extract the payee from the 备注 field.
    """
    now = dt.datetime.now(dt.timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - dt.timedelta(days=90)).timestamp() * 1000)
    approval_code = getenv_required("FEISHU_APPROVAL_CODE")

    for code in _list_history_instance_codes(
        APPROVAL_BASE_URL,
        token,
        approval_code,
        start_ms,
        end_ms,
    ):
        try:
            detail = get_instance(
                APPROVAL_BASE_URL, token, approval_code, code,
            )
        except ApprovalError as exc:
            if _is_deleted_history_instance_error(exc):
                continue
            raise
        data = detail.get("data", {})
        status = str(data.get("status") or "").strip().upper()
        # Use any completed instance (APPROVED, PASSED, DONE, CANCELED) as history
        if status == "DELETED" or status not in {"APPROVED", "PASSED", "DONE", "CANCELED"}:
            continue
        form_list = data.get("form", "[]")
        if isinstance(form_list, str):
            form_list = json.loads(form_list)
        form_map = form_list_to_name_map(form_list)
        if str(form_map.get(FIELD_CLOUD_TYPE) or "").strip() != cloud_type:
            continue
        if str(form_map.get(FIELD_RECHARGE_ACCOUNT) or "").strip() != recharge_account:
            continue
        remark_map = _parse_remark_lines(form_map.get(FIELD_REMARK))
        payee = {
            "type": str(remark_map.get("账户类型") or remark_map.get("收款账户类型") or "").strip(),
            "account_name": str(remark_map.get("户名") or "").strip(),
            "account_number": str(remark_map.get("账号") or "").strip(),
            "bank_name": str(remark_map.get("银行") or "").strip(),
            "bank_region": str(remark_map.get("银行地区") or "").strip(),
            "bank_branch": str(remark_map.get("支行") or "").strip(),
        }
        if payee.get("account_name") and payee.get("account_number"):
            return payee
    return None


def _parse_remark_lines(remark: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not remark:
        return result
    for line in str(remark).splitlines():
        line = line.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        result[key.strip()] = value.strip()
    return result


def validate_request(request_data: dict[str, Any]) -> None:
    normalize_request_data(request_data)
    for key in [
        "cloud_type",
        "recharge_customer_name",
        "recharge_account",
        "payment_company",
        "amount",
        "currency",
    ]:
        require_field(request_data, key)

    payee: dict[str, Any]
    raw_payee = request_data.get("payee")
    if not isinstance(raw_payee, dict):
        raw_payee = {}

    payee = payee_from_remark(request_data.get("remark"))
    for key in ("type", "account_name", "account_number", "bank_name", "bank_region", "bank_branch"):
        if str(raw_payee.get(key) or "").strip():
            payee[key] = str(raw_payee.get(key) or "").strip()

    # If payee is empty or missing required sub-fields, try to infer from history.
    payee_keys = ("type", "account_name", "account_number", "bank_name", "bank_region", "bank_branch")
    missing_keys = [k for k in payee_keys if not str(
        payee.get(k) or "").strip()]
    if missing_keys:
        cloud_type = str(request_data.get("cloud_type") or "").strip()
        recharge_account = str(request_data.get(
            "recharge_account") or "").strip()
        try:
            token = get_tenant_access_token(
                getenv_required("FEISHU_APP_ID"),
                getenv_required("FEISHU_APP_SECRET"),
                os.getenv("FEISHU_AUTH_BASE_URL", AUTH_BASE_URL),
            )
            inferred = _infer_payee_from_history(cloud_type, recharge_account, token)
            if inferred:
                request_data["payee"] = inferred
                payee = inferred
            else:
                raise SystemExit(
                    f"Request is missing required payee fields: {missing_keys}. "
                    f"No historical approval found for cloud_type={cloud_type}, "
                    f"recharge_account={recharge_account}."
                )
        except SystemExit:
            raise
        except Exception as exc:
            raise SystemExit(
                f"Request is missing required payee fields: {missing_keys}. "
                f"Also failed to infer from Feishu history: {exc}"
            ) from exc
    else:
        request_data["payee"] = payee

    for key in payee_keys:
        require_field(payee, key)


def build_form_payload(request_data: dict[str, Any], schema_by_name: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    normalize_request_data(request_data)
    payee = request_data["payee"]
    payment_type = str(request_data.get("payment_type", "仅充值")).strip()
    payment_way = str(request_data.get("payment_way", "公司支付")).strip()
    remit_method = str(request_data.get("remit_method", "转账")).strip()
    payment_note = str(request_data.get("payment_note", "")).strip()
    remark = str(request_data.get("remark") or build_remark(request_data))
    expected_date = str(request_data.get("expected_date")
                        or default_expected_date()).strip()

    dropdown_fields = {
        FIELD_CLOUD_TYPE: str(request_data["cloud_type"]).strip(),
        FIELD_PAYMENT_TYPE: payment_type,
        FIELD_PAYMENT_WAY: payment_way,
        FIELD_PAYMENT_COMPANY: str(request_data["payment_company"]).strip(),
        FIELD_REMIT_METHOD: remit_method,
    }

    form_payload: list[dict[str, Any]] = []

    # Add dropdown fields first: 公有云类型, 支付类型, 支付方式, 付款公司, 付款方式
    for field_name, submitted_text in dropdown_fields.items():
        field_schema = schema_by_name.get(field_name)
        if not field_schema:
            raise SystemExit(
                f"Approval definition is missing expected field: {field_name}")
        form_payload.append(
            {
                "id": field_schema["id"],
                "type": field_schema["type"],
                "value": option_text_to_key(field_schema, submitted_text),
            }
        )

    # Build simple fields in the correct submission order:
    # 充值客户名称, 充值云账号, [付款说明, ]说明 1, 付款金额, 期望到账时间, [备注]
    # Note: FIELD_NOTE1 (说明 1) is a fixed-value text field; insert it at the
    # correct position within simple_fields so the final order matches successful
    # submissions exactly.
    simple_fields: list[tuple[str, str]] = [
        (FIELD_RECHARGE_CUSTOMER, request_data["recharge_customer_name"]),
        (FIELD_RECHARGE_ACCOUNT, request_data["recharge_account"]),
        (FIELD_AMOUNT, request_data["amount"]),
        (FIELD_EXPECTED_DATE, normalize_date(expected_date)),
        (FIELD_REMARK, remark),
    ]
    # Insert payment_note at position 3 (after 充值云账号)
    if payment_note:
        simple_fields.insert(2, (FIELD_PAYMENT_NOTE, payment_note))
    # Insert 说明 1 at the correct position:
    # - with payment_note (6 fields): insert at index 3 → [customer, account, payment_note, 说明1, amount, date, remark]
    # - without payment_note (5 fields): insert at index 2 → [customer, account, 说明1, amount, date, remark]
    note1_schema = schema_by_name.get(FIELD_NOTE1)
    note1_insert_at = 3 if payment_note else 2
    if note1_schema:
        simple_fields.insert(note1_insert_at, (FIELD_NOTE1, "请填写<员工费用报销>并关联此申请"))

    for field_name, value in simple_fields:
        field_schema = schema_by_name.get(field_name)
        if not field_schema:
            raise SystemExit(
                f"Approval definition is missing expected field: {field_name}")
        form_payload.append(
            {"id": field_schema["id"], "type": field_schema["type"], "value": value})

    return form_payload


def form_list_to_name_map(form_payload: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in form_payload:
        name = item.get("name")
        if not name:
            continue
        value = item.get("value")
        if item.get("type") == "amount" and isinstance(value, (int, float)):
            result[name] = float(value)
        else:
            result[name] = value
    return result


def _parse_amount(value: Any) -> float:
    """Parse an amount that may be a string like '200.00 CNY', '¥200', or '1,234.56'."""
    amount, _currency = split_amount_and_currency(value)
    if isinstance(amount, (int, float)):
        return float(amount)
    s = str(amount).strip()
    s = re.sub(r"[^\d.,\-]", "", s)
    s = s.replace(",", "")
    return float(s)


def expected_name_map(request_data: dict[str, Any]) -> dict[str, Any]:
    normalize_request_data(request_data)
    payment_type = str(request_data.get("payment_type", "仅充值")).strip()
    payment_way = str(request_data.get("payment_way", "公司支付")).strip()
    remit_method = str(request_data.get("remit_method", "转账")).strip()
    result: dict[str, Any] = {
        FIELD_CLOUD_TYPE: str(request_data["cloud_type"]).strip(),
        FIELD_PAYMENT_TYPE: payment_type,
        FIELD_RECHARGE_CUSTOMER: str(request_data["recharge_customer_name"]).strip(),
        FIELD_RECHARGE_ACCOUNT: str(request_data["recharge_account"]).strip(),
        FIELD_PAYMENT_WAY: payment_way,
        FIELD_PAYMENT_COMPANY: str(request_data["payment_company"]).strip(),
        FIELD_REMIT_METHOD: remit_method,
        FIELD_AMOUNT: _parse_amount(request_data["amount"]),
        "currency": str(request_data.get("currency") or "CNY").strip().upper(),
        FIELD_EXPECTED_DATE: normalize_date(
            str(request_data.get("expected_date")
                or default_expected_date()).strip()
        ),
        FIELD_REMARK: str(request_data.get("remark") or build_remark(request_data)),
        FIELD_NOTE1: "请填写<员工费用报销>并关联此申请",
    }
    payment_note = str(request_data.get("payment_note", "")).strip()
    if payment_note:
        result[FIELD_PAYMENT_NOTE] = payment_note
    return result


def extract_payee_from_request(request_data: dict[str, Any]) -> dict[str, str]:
    payee = request_data.get("payee")
    if not isinstance(payee, dict):
        payee = payee_from_remark(request_data.get("remark"))
    return {
        "账户类型": str(payee["type"]).strip(),
        "户名": str(payee["account_name"]).strip(),
        "账号": str(payee["account_number"]).strip(),
        "银行": str(payee["bank_name"]).strip(),
        "银行地区": str(payee["bank_region"]).strip(),
        "支行": str(payee["bank_branch"]).strip(),
    }


def same_cloud_recharge_account(form_map: dict[str, Any], expected: dict[str, Any]) -> bool:
    if form_map.get(FIELD_CLOUD_TYPE) != expected[FIELD_CLOUD_TYPE]:
        return False
    expected_account = expected[FIELD_RECHARGE_ACCOUNT]
    form_account = form_map.get(FIELD_RECHARGE_ACCOUNT)
    if not expected_account and not form_account:
        return False
    return form_account == expected_account


def summarize_pending_instances(
    base_url: str,
    token: str,
    approval_code: str,
    lookback_days: int,
    limit: int,
) -> list[dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    end_time_ms = int(now.timestamp() * 1000)
    start_time_ms = int(
        (now - dt.timedelta(days=lookback_days)).timestamp() * 1000)
    listed = list_instances(base_url, token, approval_code,
                            start_time_ms, end_time_ms, limit=100)
    pending: list[dict[str, Any]] = []
    for instance_code in listed.get("data", {}).get("instance_code_list", []):
        detail = get_instance(base_url, token, approval_code, instance_code)
        data = detail.get("data", {})
        if data.get("status") != "PENDING":
            continue
        form_map = form_list_to_name_map(json.loads(data.get("form", "[]")))
        pending.append(
            {
                "instance_code": instance_code,
                "serial_number": data.get("serial_number"),
                "status": data.get("status"),
                "user_id": data.get("user_id"),
                "start_time": data.get("start_time"),
                "cloud_type": form_map.get(FIELD_CLOUD_TYPE),
                "recharge_customer_name": form_map.get(FIELD_RECHARGE_CUSTOMER),
                "recharge_account": form_map.get(FIELD_RECHARGE_ACCOUNT),
                "amount": form_map.get(FIELD_AMOUNT),
                "payment_company": form_map.get(FIELD_PAYMENT_COMPANY),
                "expected_date": form_map.get(FIELD_EXPECTED_DATE),
            }
        )
        if len(pending) >= limit:
            break
    return pending


def detect_duplicate_or_conflict(
    base_url: str,
    token: str,
    approval_code: str,
    request_data: dict[str, Any],
    lookback_days: int,
) -> dict[str, Any] | None:
    expected = expected_name_map(request_data)
    now = dt.datetime.now(dt.timezone.utc)
    end_time_ms = int(now.timestamp() * 1000)
    start_time_ms = int(
        (now - dt.timedelta(days=lookback_days)).timestamp() * 1000)
    listed = list_instances(base_url, token, approval_code,
                            start_time_ms, end_time_ms, limit=100)

    for instance_code in listed.get("data", {}).get("instance_code_list", []):
        detail = get_instance(base_url, token, approval_code, instance_code)
        data = detail.get("data", {})
        if data.get("status") != "PENDING":
            continue
        form_map = form_list_to_name_map(json.loads(data.get("form", "[]")))
        if not same_cloud_recharge_account(form_map, expected):
            continue

        mismatches = []
        for field_name in list(expected.keys()):
            existing_value = form_map.get(field_name)
            expected_value = expected.get(field_name)
            if existing_value != expected_value:
                mismatches.append(
                    {
                        "field": field_name,
                        "existing": existing_value,
                        "requested": expected_value,
                    }
                )

        if mismatches:
            raise SystemExit(
                json.dumps(
                    {
                        "error": "pending_approval_conflict",
                        "message": "A pending approval already exists for the same recharge account, but the content does not match.",
                        "instance_code": instance_code,
                        "serial_number": data.get("serial_number"),
                        "mismatches": mismatches,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )

        return {
            "instance_code": instance_code,
            "serial_number": data.get("serial_number"),
            "status": data.get("status"),
            "user_id": data.get("user_id"),
            "start_time": data.get("start_time"),
            "matched_cloud_type": expected[FIELD_CLOUD_TYPE],
            "matched_recharge_account": expected[FIELD_RECHARGE_ACCOUNT],
        }
    return None


def historical_status_matches(status: str | None) -> bool:
    return str(status or "").strip().upper() in {"APPROVED", "PASSED", "DONE"}


def validate_against_history(
    base_url: str,
    token: str,
    approval_code: str,
    request_data: dict[str, Any],
    lookback_days: int,
    limit: int,
) -> dict[str, Any]:
    expected = expected_name_map(request_data)
    expected_payee = extract_payee_from_request(request_data)
    now = dt.datetime.now(dt.timezone.utc)
    end_time_ms = int(now.timestamp() * 1000)
    start_time_ms = int(
        (now - dt.timedelta(days=lookback_days)).timestamp() * 1000)
    instance_codes = _list_history_instance_codes(
        base_url,
        token,
        approval_code,
        start_time_ms,
        end_time_ms,
    )

    matches: list[dict[str, Any]] = []
    for instance_code, data in _history_instances_recent_first(
        base_url,
        token,
        approval_code,
        instance_codes,
    ):
        if not historical_status_matches(data.get("status")):
            continue
        form_map = form_list_to_name_map(json.loads(data.get("form", "[]")))
        if not same_cloud_recharge_account(form_map, expected):
            continue

        remark_map = parse_remark_lines(form_map.get(FIELD_REMARK))
        field_comparisons = []
        compare_fields = [
            FIELD_CLOUD_TYPE,
            FIELD_PAYMENT_TYPE,
            FIELD_RECHARGE_CUSTOMER,
            FIELD_RECHARGE_ACCOUNT,
            FIELD_PAYMENT_NOTE,
            FIELD_PAYMENT_WAY,
            FIELD_PAYMENT_COMPANY,
            FIELD_REMIT_METHOD,
            FIELD_AMOUNT,
        ]
        for field_name in compare_fields:
            if field_name not in expected:
                continue
            existing_value = form_map.get(field_name)
            expected_value = expected[field_name]
            field_comparisons.append(
                {
                    "field": field_name,
                    "existing": existing_value,
                    "requested": expected_value,
                    "match": existing_value == expected_value,
                }
            )

        payee_comparisons = []
        for field_name, expected_value in expected_payee.items():
            existing_value = remark_map.get(field_name)
            payee_comparisons.append(
                {
                    "field": field_name,
                    "existing": existing_value,
                    "requested": expected_value,
                    "match": existing_value == expected_value,
                }
            )

        matches.append(
            {
                "instance_code": instance_code,
                "serial_number": data.get("serial_number"),
                "status": data.get("status"),
                "user_id": data.get("user_id"),
                "start_time": data.get("start_time"),
                "all_match": all(item["match"] for item in field_comparisons + payee_comparisons),
                "bank_info_match": all(item["match"] for item in payee_comparisons),
                "field_mismatches": [item for item in field_comparisons if not item["match"]],
                "payee_mismatches": [item for item in payee_comparisons if not item["match"]],
                "field_comparisons": field_comparisons,
                "payee_comparisons": payee_comparisons,
            }
        )
        if len(matches) >= limit:
            break

    fully_matched = [item for item in matches if item["all_match"]]
    bank_matched = [item for item in matches if item["bank_info_match"]]
    return {
        "approval_code": approval_code,
        "cloud_type": expected[FIELD_CLOUD_TYPE],
        "recharge_account": expected[FIELD_RECHARGE_ACCOUNT],
        "summary": {
            "has_historical_match": bool(matches),
            "has_fully_matched_history": bool(fully_matched),
            "has_bank_info_match": bool(bank_matched),
            "matched_count": len(matches),
            "fully_matched_count": len(fully_matched),
            "bank_info_matched_count": len(bank_matched),
        },
        "matched_instances": matches,
    }


def find_historical_recharge_request(
    base_url: str,
    token: str,
    approval_code: str,
    cloud_type: str,
    recharge_account: str,
    lookback_days: int,
    limit: int,
) -> dict[str, Any]:
    cloud_type = str(cloud_type or "").strip()
    recharge_account = str(recharge_account or "").strip()
    now = dt.datetime.now(dt.timezone.utc)
    end_time_ms = int(now.timestamp() * 1000)
    start_time_ms = int(
        (now - dt.timedelta(days=lookback_days)).timestamp() * 1000)
    debug(
        "Feishu history lookup: listing approval instances "
        f"(approval_code={approval_code}, lookback_days={lookback_days}, "
        f"cloud_type={cloud_type}, recharge_account={recharge_account}, "
        f"start_time_ms={start_time_ms}, end_time_ms={end_time_ms})"
    )
    instance_codes = _list_history_instance_codes(
        base_url,
        token,
        approval_code,
        start_time_ms,
        end_time_ms,
    )
    debug(
        "Feishu history lookup: received instance list "
        f"(count={len(instance_codes)}, approval_code={approval_code})"
    )

    inspected = 0
    matched_count = 0
    for instance_code, data in _history_instances_recent_first(
        base_url,
        token,
        approval_code,
        instance_codes,
    ):
        status = str(data.get("status") or "").strip()
        if not historical_status_matches(data.get("status")):
            debug(
                "Feishu history lookup: skip instance with non-historical status "
                f"(instance_code={instance_code}, status={status})"
            )
            continue
        form_map = form_list_to_name_map(json.loads(data.get("form", "[]")))
        instance_cloud_type = str(form_map.get(FIELD_CLOUD_TYPE) or "").strip()
        instance_recharge_account = str(
            form_map.get(FIELD_RECHARGE_ACCOUNT) or ""
        ).strip()
        cloud_type_match = instance_cloud_type == cloud_type
        recharge_account_match = instance_recharge_account == recharge_account
        debug(
            "Feishu history lookup: compare instance "
            f"(instance_code={instance_code}, status={status}, "
            f"cloud_type={instance_cloud_type}, expected_cloud_type={cloud_type}, "
            f"cloud_type_match={cloud_type_match}, "
            f"recharge_account={instance_recharge_account}, "
            f"expected_recharge_account={recharge_account}, "
            f"recharge_account_match={recharge_account_match})"
        )
        if (
            not cloud_type_match
            or not recharge_account_match
        ):
            continue
        matched_count += 1
        inspected += 1
        request_data = request_data_from_history_form(form_map)
        try:
            validate_request(request_data)
        except SystemExit as exc:
            debug(
                "Feishu history lookup: matched instance failed request validation "
                f"(instance_code={instance_code}, status={status}, error={exc})"
            )
            if inspected >= limit:
                break
            continue
        debug(
            "Feishu history lookup: matched historical recharge request "
            f"(instance_code={instance_code}, status={status}, "
            f"inspected={inspected}, matched_count={matched_count})"
        )
        return {
            "found": True,
            "approval_code": approval_code,
            "cloud_type": cloud_type,
            "recharge_account": recharge_account,
            "inspected_count": inspected,
            "matched_count": matched_count,
            "source_instance": {
                "instance_code": instance_code,
                "serial_number": data.get("serial_number"),
                "status": data.get("status"),
                "user_id": data.get("user_id"),
                "start_time": data.get("start_time"),
            },
            "request_data": request_data,
        }
        if inspected >= limit:
            break

    return {
        "found": False,
        "approval_code": approval_code,
        "cloud_type": cloud_type,
        "recharge_account": recharge_account,
        "inspected_count": inspected,
        "matched_count": matched_count,
        "request_data": {},
    }


def main() -> int:
    global CURRENT_ARGS
    reset_http_traces()
    args = parse_args()
    CURRENT_ARGS = args
    app_id = getenv_required("FEISHU_APP_ID")
    app_secret = getenv_required("FEISHU_APP_SECRET")
    approval_code = getenv_required("FEISHU_APPROVAL_CODE")
    user_id = args.user_id or os.getenv("FEISHU_USER_ID", "").strip()
    user_identifier = args.user_identifier or os.getenv(
        "FEISHU_USER_IDENTIFIER", "").strip()

    if args.command == "list-pending":
        token = get_tenant_access_token(app_id, app_secret, args.auth_base_url)
        pending = summarize_pending_instances(
            args.base_url, token, approval_code, args.lookback_days, args.limit
        )
        payload = {"approval_code": approval_code,
                   "pending_instances": pending}
        emit_payload(args, payload, success=True, exit_code=0)
        return 0

    if args.command == "validate-history":
        request_data = read_json(args.request_file)
        if not isinstance(request_data, dict):
            raise SystemExit("Request file must contain a JSON object.")
        validate_request(request_data)
        token = get_tenant_access_token(app_id, app_secret, args.auth_base_url)
        payload = validate_against_history(
            args.base_url,
            token,
            approval_code,
            request_data,
            args.lookback_days,
            args.limit,
        )
        emit_payload(args, payload, success=True, exit_code=0)
        return 0

    if not user_id and not user_identifier:
        raise SystemExit(
            "Provide --user-id, set FEISHU_USER_ID, pass --user-identifier, "
            "or set FEISHU_USER_IDENTIFIER."
        )

    request_data = read_json(args.request_file)
    if not isinstance(request_data, dict):
        raise SystemExit("Request file must contain a JSON object.")
    validate_request(request_data)

    token = get_tenant_access_token(app_id, app_secret, args.auth_base_url)

    if not user_id and user_identifier:
        user_id = _resolve_user_id(args.auth_base_url, token, user_identifier)

    definition = get_approval_definition(args.base_url, token, approval_code)
    schema_by_name = build_schema_by_name(parse_definition_schema(definition))
    # validate_unsupported_account_widgets(request_data, schema_by_name)
    form_payload = build_form_payload(request_data, schema_by_name)

    existing = None
    if not args.skip_duplicate_check:
        existing = detect_duplicate_or_conflict(
            args.base_url, token, approval_code, request_data, args.lookback_days
        )
    if existing:
        payload = {
            "approval_code": approval_code,
            "deduplicated": True,
            "duplicate_match_field": f"{FIELD_CLOUD_TYPE}+{FIELD_RECHARGE_ACCOUNT}",
            "existing_instance": existing,
        }
        emit_payload(args, payload, success=True, exit_code=0)
        return 0

    request_payload = {
        "approval_code": approval_code,
        "user_id": user_id,
        "form": json.dumps(form_payload, ensure_ascii=False),
    }
    response = create_instance(args.base_url, token, request_payload)
    payload = {
        "approval_code": approval_code,
        "deduplicated": False,
        "request_payload": request_payload,
        "response": response,
    }
    emit_payload(args, payload, success=True, exit_code=0)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApprovalError as exc:
        failure_payload: dict[str, Any] = {"error": str(exc)}
        if CURRENT_ARGS is not None:
            if getattr(CURRENT_ARGS, "include_http_traces", False):
                failure_payload["http_traces"] = get_http_traces()
            failure_payload["script_trace"] = build_script_trace(
                CURRENT_ARGS,
                success=False,
                exit_code=1,
            )
        elif get_http_traces():
            failure_payload["http_trace_count"] = len(get_http_traces())
        print(json.dumps(failure_payload, ensure_ascii=False, indent=2))
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
