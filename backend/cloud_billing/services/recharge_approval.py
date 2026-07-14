"""
Service helpers for recharge approval submission and callback tracking.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional, Tuple


from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from cloud_billing.models import (
    AlertRecord,
    CloudProvider,
    RechargeApprovalEvent,
    RechargeApprovalLLMRun,
    RechargeApprovalRecord,
)
from cloud_billing.services.parser_llm_config import (
    resolve_parser_llm_settings,
)

if TYPE_CHECKING:
    from agentcore_metering.adapters.django.models import LLMUsage

logger = logging.getLogger(__name__)


class MissingRechargeFieldsError(ValueError):
    """
    Raised when recharge info is missing required fields.

    Carries the list of missing field names for structured error responses.
    """

    def __init__(self, missing_fields: List[str], message: str = ""):
        self.missing_fields = missing_fields
        default_message = (
            "Recharge info is missing required fields: "
            + ", ".join(missing_fields)
        )
        super().__init__(message or default_message)


CLOUD_TYPE_LABELS = {
    "aws": "AWS",
    "huawei": "华为云",
    "huawei-intl": "华为云",
    "alibaba": "阿里云",
    "azure": "Azure",
    "tencentcloud": "腾讯云",
    "volcengine": "火山引擎",
    "baidu": "百度智能云",
    "zhipu": "智谱",
}


RECHARGE_INFO_KEY_MAP = {
    "cloud_type": "cloud_type",
    "公有云类型": "cloud_type",
    "payment_type": "payment_type",
    "支付类型": "payment_type",
    "recharge_customer_name": "recharge_customer_name",
    "充值客户名称": "recharge_customer_name",
    "recharge_account": "recharge_account",
    "充值云账号": "recharge_account",
    "payment_way": "payment_way",
    "支付方式": "payment_way",
    "payment_company": "payment_company",
    "付款公司": "payment_company",
    "remit_method": "remit_method",
    "付款方式": "remit_method",
    "amount": "amount",
    "付款金额": "amount",
    "payment_note": "payment_note",
    "付款说明": "payment_note",
    "expected_date": "expected_date",
    "期望到账时间": "expected_date",
    "remark": "remark",
    "备注": "remark",
    "payee.type": "payee.type",
    "账户类型": "payee.type",
    "收款账户类型": "payee.type",
    "payee.account_name": "payee.account_name",
    "户名": "payee.account_name",
    "payee.account_number": "payee.account_number",
    "账号": "payee.account_number",
    "payee.bank_name": "payee.bank_name",
    "银行": "payee.bank_name",
    "payee.bank_region": "payee.bank_region",
    "银行地区": "payee.bank_region",
    "银行所在地区": "payee.bank_region",
    "payee.bank_branch": "payee.bank_branch",
    "支行": "payee.bank_branch",
    "银行支行": "payee.bank_branch",
}

FEISHU_STATUS_MAP = {
    "PENDING": RechargeApprovalRecord.STATUS_SUBMITTED,
    "APPROVING": RechargeApprovalRecord.STATUS_SUBMITTED,
    "APPROVED": RechargeApprovalRecord.STATUS_APPROVED,
    "REJECTED": RechargeApprovalRecord.STATUS_REJECTED,
    "CANCELED": RechargeApprovalRecord.STATUS_CANCELED,
    "CANCELLED": RechargeApprovalRecord.STATUS_CANCELED,
    "FAILED": RechargeApprovalRecord.STATUS_FAILED,
}

# ---------------------------------------------------------------------------
# Feishu API base URL (also defined later; define early for preflight module)
# ---------------------------------------------------------------------------
FEISHU_APPROVAL_BASE_URL = "https://www.feishu.cn"


def _looks_like_legacy_submitter_identifier(value: str) -> bool:
    """Return True when a submitter value looks like email or mobile.

    Used by backend tasks and view shims to coerce a historical submitter
    string (email or phone) into the legacy ``submitter_identifier`` form
    when the new ``submitter_user_id`` flow is not applicable.
    """
    text = str(value or "").strip()
    return bool(
        text and ("@" in text or re.match(r"^\+?\d[\d\s-]{5,}$", text))
    )



def _redact_feishu_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Return Feishu request headers with credentials redacted."""
    redacted = dict(headers)
    if "Authorization" in redacted:
        redacted["Authorization"] = "Bearer ***REDACTED***"
    return redacted


def _redact_feishu_form_for_log(value: Any) -> Any:
    """Return a Feishu approval form payload with submitted values redacted."""
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return "***REDACTED_FORM***"

    if isinstance(parsed, list):
        redacted_items: List[Any] = []
        for item in parsed:
            if isinstance(item, dict) and "value" in item:
                redacted_items.append(
                    {
                        **item,
                        "value": "***REDACTED***",
                    }
                )
            else:
                redacted_items.append(_redact_feishu_payload_for_log(item))
        return redacted_items

    if isinstance(parsed, dict):
        redacted_form: Dict[str, Any] = {}
        for key, item in parsed.items():
            if key == "value":
                redacted_form[key] = "***REDACTED***"
            else:
                redacted_form[key] = _redact_feishu_payload_for_log(item)
        return redacted_form

    return "***REDACTED_FORM***"


def _redact_feishu_payload_for_log(value: Any) -> Any:
    """Return Feishu payload data safe enough for application logs."""
    sensitive_keys = (
        "account",
        "amount",
        "authorization",
        "bank",
        "customer",
        "email",
        "mobile",
        "name",
        "payee",
        "password",
        "remark",
        "secret",
        "token",
        "user",
    )
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key == "form":
                redacted[key] = _redact_feishu_form_for_log(item)
            elif any(part in normalized_key for part in sensitive_keys):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact_feishu_payload_for_log(item)
        return redacted
    if isinstance(value, list):
        return [_redact_feishu_payload_for_log(item) for item in value]
    return value


def _redact_feishu_body_for_log(body: str) -> str:
    """Return a redacted Feishu response body for logs."""
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return "***REDACTED_BODY***"
    return json.dumps(
        _redact_feishu_payload_for_log(payload),
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Preflight inspection constants (mirrors skill script field names)
# ---------------------------------------------------------------------------
_F_FIELD_CLOUD_TYPE = "公有云类型"
_F_FIELD_RECHARGE_ACCOUNT = "充值云账号"
_F_FIELD_RECHARGE_CUSTOMER = "充值客户名称"
_F_FIELD_PAYMENT_TYPE = "支付类型"
_F_FIELD_PAYMENT_WAY = "支付方式"
_F_FIELD_PAYMENT_COMPANY = "付款公司"
_F_FIELD_REMIT_METHOD = "付款方式"
_F_FIELD_AMOUNT = "付款金额"
_F_FIELD_EXPECTED_DATE = "期望到账时间"
_F_FIELD_NOTE1 = "说明 1"
_F_FIELD_REMARK = "备注"
_F_FIELD_PAYMENT_NOTE = "付款说明"
_F_REMIT_METHOD_VALUES = {"转账", "支付宝"}
_F_PAYMENT_WAY_VALUES = {"公司支付", "充值报销"}


def _feishu_api_request(
    url: str,
    payload: Dict[str, Any],
    token: str,
    timeout: int = 30,
) -> Optional[Dict[str, Any]]:
    import urllib.error
    import urllib.request

    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        logger.info(
            "Feishu API Request\n"
            "method=POST\n"
            "url=%s\n"
            "headers=%s\n"
            "payload=%s",
            url,
            json.dumps(_redact_feishu_headers(headers), ensure_ascii=False),
            json.dumps(
                _redact_feishu_payload_for_log(payload),
                ensure_ascii=False,
            ),
        )
        req = urllib.request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = getattr(resp, "status", None) or getattr(
                resp, "code", None
            )
            response_body = resp.read().decode("utf-8")
            data = json.loads(response_body)
            logger.info(
                "Feishu API Response\n"
                "method=POST\n"
                "url=%s\n"
                "http_status=%s\n"
                "feishu_code=%s\n"
                "feishu_msg=%s\n"
                "body=%s",
                url,
                status_code,
                data.get("code"),
                data.get("msg", ""),
                _redact_feishu_body_for_log(response_body),
            )
            if data.get("code") != 0:
                logger.warning(
                    "Feishu API error: url=%s code=%s msg=%s body=%s",
                    url,
                    data.get("code"),
                    data.get("msg", ""),
                    _redact_feishu_body_for_log(response_body),
                )
                return None
            return data
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.warning(
            "Feishu API HTTP Error\n"
            "method=POST\n"
            "url=%s\n"
            "http_status=%s\n"
            "payload=%s\n"
            "body=%s",
            url,
            exc.code,
            json.dumps(
                _redact_feishu_payload_for_log(payload),
                ensure_ascii=False,
            ),
            _redact_feishu_body_for_log(body_text),
        )
    except urllib.error.URLError as exc:
        logger.warning("Feishu network error: url=%s error=%s", url, exc.reason)
    except Exception as exc:
        logger.warning("Feishu request exception: url=%s error=%s", url, exc)
    return None


def _feishu_list_approval_instances(
    token: str,
    approval_code: str,
    start_time_ms: int,
    end_time_ms: int,
    *,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
    limit: int = 100,
) -> List[str]:
    base = approval_base_url.rstrip("/")
    url = f"{base}/approval/openapi/v2/instance/list"
    payload = {
        "approval_code": approval_code,
        "start_time": start_time_ms,
        "end_time": end_time_ms,
        "limit": limit,
    }
    data = _feishu_api_request(url, payload, token)
    if not data:
        return []
    codes = data.get("data", {}).get("instance_code_list", []) or []
    return [str(c).strip() for c in codes if str(c or "").strip()]


def _feishu_get_instance(
    token: str,
    approval_code: str,
    instance_code: str,
    *,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> Optional[Dict[str, Any]]:
    base = approval_base_url.rstrip("/")
    url = f"{base}/approval/openapi/v2/instance/get"
    payload = {"approval_code": approval_code, "instance_code": instance_code}
    return _feishu_api_request(url, payload, token)


def _feishu_preview_instance(
    token: str,
    instance_code: str,
    task_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Preview the Feishu approval nodes after the current task."""
    # Source: https://open.feishu.cn/document/server-docs/approval-v4/
    # instance/approval-preview
    url = (
        "https://open.feishu.cn/open-apis/approval/v4/instances/preview"
        "?user_id_type=user_id"
    )
    payload = {
        "instance_code": instance_code,
        "task_id": task_id,
        "user_id": user_id,
    }
    return _feishu_api_request(url, payload, token)


def _history_sort_key(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return 0


def _history_instances_recent_first(
    token: str,
    approval_code: str,
    instance_codes: List[str],
    *,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> List[Tuple[str, Dict[str, Any]]]:
    instances: List[Tuple[int, int, str, Dict[str, Any]]] = []
    for idx, code in enumerate(instance_codes):
        detail = _feishu_get_instance(token, approval_code, code, approval_base_url=approval_base_url)
        if not detail:
            continue
        data = detail.get("data", {}) or {}
        sort_time = _history_sort_key(data.get("start_time") or data.get("end_time"))
        instances.append((sort_time, idx, code, data))
    instances.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(code, data) for _, _, code, data in instances]


def _inspect_form_list_to_name_map(form_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
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


def _extract_cloud_type_from_instance_data(data: Dict[str, Any]) -> str:
    cloud_type = str(
        data.get("cloud_type")
        or data.get("provider_cloud_type")
        or ""
    ).strip()
    if cloud_type:
        return cloud_type

    form_list_raw = data.get("form", "[]")
    if isinstance(form_list_raw, str):
        try:
            form_list_raw = json.loads(form_list_raw)
        except json.JSONDecodeError:
            form_list_raw = []
    if not isinstance(form_list_raw, list):
        return ""

    form_map = _inspect_form_list_to_name_map(form_list_raw)
    return str(form_map.get(_F_FIELD_CLOUD_TYPE) or "").strip()


def _inspect_same_cloud_recharge_account(
    form_map: Dict[str, Any],
    expected: Dict[str, Any],
) -> bool:
    if form_map.get(_F_FIELD_CLOUD_TYPE) != expected[_F_FIELD_CLOUD_TYPE]:
        return False
    expected_account = expected[_F_FIELD_RECHARGE_ACCOUNT]
    form_account = form_map.get(_F_FIELD_RECHARGE_ACCOUNT)
    if not expected_account and not form_account:
        return False
    return form_account == expected_account


def _inspect_split_amount(value: Any) -> Tuple[Any, str]:
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


def _inspect_normalize_request_data(request_data: Dict[str, Any]) -> None:
    payment_type = str(request_data.get("payment_type") or "").strip()
    payment_way = str(request_data.get("payment_way") or "").strip()
    remit_method = str(request_data.get("remit_method") or "").strip()
    if payment_type in _F_REMIT_METHOD_VALUES:
        if not remit_method:
            request_data["remit_method"] = payment_type
        request_data["payment_type"] = "仅充值"
    if payment_way in _F_PAYMENT_WAY_VALUES:
        if not str(request_data.get("remit_method") or "").strip():
            request_data["remit_method"] = payment_way
        request_data["payment_way"] = "公司支付"
    amount_value, currency = _inspect_split_amount(request_data.get("amount"))
    request_data["amount"] = amount_value
    existing_currency = str(request_data.get("currency") or "").strip().upper()
    request_data["currency"] = existing_currency or currency or "CNY"


def _inspect_expected_name_map(request_data: Dict[str, Any]) -> Dict[str, Any]:
    _inspect_normalize_request_data(request_data)
    return {
        _F_FIELD_CLOUD_TYPE: str(request_data["cloud_type"]).strip(),
        _F_FIELD_RECHARGE_ACCOUNT: str(request_data["recharge_account"]).strip(),
    }


def _inspect_account_state(
    token: str,
    approval_code: str,
    request_data: Dict[str, Any],
    lookback_days: int,
    *,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> Dict[str, Any]:
    try:
        import datetime as dt

        expected = _inspect_expected_name_map(request_data)
        now = dt.datetime.now(dt.timezone.utc)
        end_time_ms = int(now.timestamp() * 1000)
        start_time_ms = int((now - dt.timedelta(days=lookback_days)).timestamp() * 1000)
        instance_codes = _feishu_list_approval_instances(
            token,
            approval_code,
            start_time_ms,
            end_time_ms,
            approval_base_url=approval_base_url,
            limit=100,
        )
        finished_match: Optional[Tuple[str, Dict[str, Any]]] = None
        for instance_code, data in _history_instances_recent_first(
            token,
            approval_code,
            instance_codes,
            approval_base_url=approval_base_url,
        ):
            form_list_raw = data.get("form", "[]")
            if isinstance(form_list_raw, str):
                try:
                    form_list_raw = json.loads(form_list_raw)
                except json.JSONDecodeError:
                    form_list_raw = []
            form_map = _inspect_form_list_to_name_map(
                form_list_raw if isinstance(form_list_raw, list) else []
            )
            if not _inspect_same_cloud_recharge_account(form_map, expected):
                continue
            status = str(data.get("status") or "").strip().upper()
            logger.info(
                "[Preflight inspect] instance=%s status=%s "
                "form_cloud=%r form_account=%r expected_account=%r",
                instance_code,
                status,
                form_map.get(_F_FIELD_CLOUD_TYPE),
                form_map.get(_F_FIELD_RECHARGE_ACCOUNT),
                expected[_F_FIELD_RECHARGE_ACCOUNT],
            )
            if status in {"PENDING", "APPROVING"}:
                return {
                    "state": "ongoing",
                    "approval_code": approval_code,
                    "cloud_type": expected[_F_FIELD_CLOUD_TYPE],
                    "recharge_account": expected[_F_FIELD_RECHARGE_ACCOUNT],
                    "instance_code": instance_code,
                    "serial_number": data.get("serial_number"),
                    "status": status,
                    "user_id": data.get("user_id"),
                    "start_time": data.get("start_time"),
                    "raw": data,
                }
            if finished_match is None:
                finished_match = (instance_code, data)

        if finished_match is not None:
            instance_code, data = finished_match
            return {
                "state": "finished",
                "approval_code": approval_code,
                "cloud_type": expected[_F_FIELD_CLOUD_TYPE],
                "recharge_account": expected[_F_FIELD_RECHARGE_ACCOUNT],
                "instance_code": instance_code,
                "serial_number": data.get("serial_number"),
                "status": data.get("status"),
                "user_id": data.get("user_id"),
                "start_time": data.get("start_time"),
                "matches": [
                    {
                        "instance_code": instance_code,
                        "serial_number": data.get("serial_number"),
                        "status": data.get("status"),
                        "user_id": data.get("user_id"),
                        "start_time": data.get("start_time"),
                    }
                ],
            }
        return {
            "state": "none",
            "approval_code": approval_code,
            "cloud_type": expected[_F_FIELD_CLOUD_TYPE],
            "recharge_account": expected[_F_FIELD_RECHARGE_ACCOUNT],
            "matches": [],
        }
    except Exception as exc:
        logger.warning(
            "[Preflight inspect] unexpected error, treating as no matches: %s",
            exc,
            exc_info=True,
        )
        return {"state": "none", "approval_code": approval_code, "matches": []}


RECHARGE_REQUIRED_FIELDS = [
    "cloud_type",
    "recharge_customer_name",
    "recharge_account",
    "payment_company",
]
PAYEE_REQUIRED_FIELDS = [
    "type",
    "account_name",
    "account_number",
    "bank_name",
    "bank_region",
    "bank_branch",
]
PAYMENT_TYPE_VALUES = {"仅充值", "仅划拨", "充值+划拨", "费用结算"}
PAYMENT_WAY_VALUES = {"公司支付", "充值报销"}
REMIT_METHOD_VALUES = {"转账", "支付宝"}
RECHARGE_REMARK_PLACEHOLDERS = {"备注", "remark"}
RECHARGE_METADATA_FIELDS = {
    "approval_code",
    "instance_code",
    "source_instance",
    "source_instance_code",
    "submitter_identifier",
    "submitter_user_label",
}


def normalize_recharge_request_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    payment_type = str(payload.get("payment_type") or "").strip()
    payment_way = str(payload.get("payment_way") or "").strip()
    remit_method = str(payload.get("remit_method") or "").strip()
    amount_present = "amount" in payload
    currency_present = "currency" in payload
    amount_value = payload.get("amount")
    currency_value = str(payload.get("currency") or "").strip().upper()

    if payment_type in REMIT_METHOD_VALUES:
        if not remit_method:
            payload["remit_method"] = payment_type
        payload["payment_type"] = "仅充值"

    if payment_way in REMIT_METHOD_VALUES:
        if not str(payload.get("remit_method") or "").strip():
            payload["remit_method"] = payment_way
        payload["payment_way"] = "公司支付"

    if amount_present or str(amount_value or "").strip():
        amount_value, inferred_currency = _split_amount_and_currency(amount_value)
        payload["amount"] = amount_value
        if inferred_currency and not currency_value:
            currency_value = inferred_currency
        if currency_value:
            payload["currency"] = currency_value
        else:
            payload.pop("currency", None)
    else:
        payload.pop("amount", None)
        if currency_present:
            if currency_value:
                payload["currency"] = currency_value
            else:
                payload.pop("currency", None)
        else:
            payload.pop("currency", None)

    return payload


def sanitize_recharge_request_payload(
    payload: Dict[str, Any],
    *,
    drop_recharge_account: bool = False,
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    sanitized = dict(payload)
    remark = str(sanitized.get("remark") or "").strip()
    if remark in RECHARGE_REMARK_PLACEHOLDERS:
        sanitized.pop("remark", None)
    if drop_recharge_account:
        sanitized.pop("recharge_account", None)
    for field_name in RECHARGE_METADATA_FIELDS:
        sanitized.pop(field_name, None)

    return sanitized


def validate_recharge_request_payload(
    payload: Dict[str, Any],
    *,
    require_cloud_type: bool = True,
) -> Dict[str, Any]:
    """
    Normalize and validate a recharge approval payload.

    Raises ValueError with a readable message when required fields are missing.
    """
    if not isinstance(payload, dict):
        raise ValueError("Recharge info must resolve to an object.")

    normalized = normalize_recharge_request_fields(dict(payload))
    normalized = sanitize_recharge_request_payload(normalized)

    missing_fields = []
    required_fields = list(RECHARGE_REQUIRED_FIELDS)
    if not require_cloud_type and "cloud_type" in required_fields:
        required_fields.remove("cloud_type")

    for key in required_fields:
        value = normalized.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_fields.append(key)

    payee = normalized.get("payee")
    if not isinstance(payee, dict):
        missing_fields.append("payee")
    else:
        for key in PAYEE_REQUIRED_FIELDS:
            value = payee.get(key)
            if value is None or (isinstance(value, str) and not str(value).strip()):
                missing_fields.append(f"payee.{key}")

    if missing_fields:
        raise MissingRechargeFieldsError(missing_fields)
    return normalized


def serialize_recharge_request_payload(
    payload: Dict[str, Any],
    *,
    require_cloud_type: bool = True,
) -> str:
    """
    Serialize a validated recharge payload into canonical JSON text.
    """
    normalized = validate_recharge_request_payload(
        payload,
        require_cloud_type=require_cloud_type,
    )
    return json.dumps(normalized, ensure_ascii=False, indent=2)


def prepare_recharge_request_payload(
    raw_recharge_info: str,
    *,
    cloud_type: str = "",
    require_cloud_type: bool = True,
) -> Dict[str, Any]:
    """
    Parse and validate recharge info from either JSON or textarea input.
    """
    payload = parse_recharge_info(raw_recharge_info)
    if cloud_type and not str(payload.get("cloud_type") or "").strip():
        payload["cloud_type"] = cloud_type
    return validate_recharge_request_payload(
        payload,
        require_cloud_type=require_cloud_type,
    )


def _trigger_source_label(source: str) -> str:
    labels = {
        "manual": "人工触发",
        "alert": "告警触发",
    }
    return labels.get(source, source)


def build_notification_message_from_payload(
    payload: Dict[str, Any],
    *,
    notification_type: str = "submitted",
    trigger_source: str = "manual",
    trigger_reason: str = "",
    trigger_user_label: str = "",
    submitter_label: str = "",
    provider_name: str = "",
    approval_status: str = "已提交",
) -> str:
    """
    Build a notification message from the parsed recharge approval payload.

    Returns a plain-text multi-line message with key: value pairs.
    The key is the field label (Chinese) and the value is from the payload.
    """
    _ = notification_type  # reserved for future status-specific messages
    sep = ": "

    def fmt_value(val: Any) -> str:
        if val is None:
            return "—"
        text = str(val).strip()
        return text if text else "—"

    def fmt_amount(amount_val: Any, currency_val: str) -> str:
        if amount_val is None or amount_val == "":
            return "—"
        currency = str(currency_val or "CNY").strip().upper() or "CNY"
        # Handle amount that already includes currency suffix (e.g. "439.23 CNY")
        amount_text = str(amount_val).strip()
        for curr in ("CNY", "USD", "EUR", "GBP", "JPY", "HKD"):
            if amount_text.upper().endswith(f" {curr}") or amount_text.upper().endswith(curr):
                currency = curr
                amount_text = amount_text[: amount_text.upper().rfind(curr)].strip()
                break
        try:
            num = float(amount_text)
            return f"{num:,.2f} {currency}"
        except (ValueError, TypeError):
            return f"{amount_text} {currency}" if amount_text else "—"

    def fmt_label(label: str) -> str:
        label_text = str(label or "").strip()
        return f"**{label_text}**" if label_text else ""

    def remark_is_payee_details_only(text: Any) -> bool:
        remark_text = str(text or "").strip()
        if not remark_text:
            return True
        allowed_keys = {
            "账户类型",
            "收款账户类型",
            "户名",
            "账号",
            "银行",
            "银行地区",
            "支行",
        }
        lines = [line.strip() for line in remark_text.splitlines() if line.strip()]
        if not lines:
            return True
        if lines[0] in {"备注", "remark"}:
            lines = lines[1:]
        if not lines:
            return True
        for line in lines:
            if "：" not in line and ":" not in line:
                return False
            key, _value = (
                line.split("：", 1) if "：" in line else line.split(":", 1)
            )
            if key.strip() not in allowed_keys:
                return False
        return True

    def collect_receipt_info_lines(
        payee: Any, remark_text: Any
    ) -> list[str]:
        receipt_lines: list[str] = []
        seen_labels: set[str] = set()

        def add_line(label: str, value: Any) -> None:
            label_text = str(label or "").strip()
            value_text = fmt_value(value)
            if not label_text or value_text == "—" or label_text in seen_labels:
                return
            seen_labels.add(label_text)
            receipt_lines.append(f"  - {label_text}: {value_text}")

        if isinstance(payee, dict):
            add_line("账户类型", payee.get("type"))
            add_line("户名", payee.get("account_name"))
            add_line("账号", payee.get("account_number"))
            add_line("银行", payee.get("bank_name"))
            add_line("银行地区", payee.get("bank_region"))
            add_line("支行", payee.get("bank_branch"))

        if receipt_lines:
            return receipt_lines

        remark_payload = str(remark_text or "").strip()
        if not remark_payload or not remark_is_payee_details_only(remark_payload):
            return receipt_lines

        label_map = {
            "账户类型": "账户类型",
            "收款账户类型": "账户类型",
            "户名": "户名",
            "账号": "账号",
            "银行": "银行",
            "银行地区": "银行地区",
            "银行所在地区": "银行地区",
            "支行": "支行",
            "银行支行": "支行",
        }
        for line in remark_payload.splitlines():
            raw_line = line.strip()
            if not raw_line or raw_line in {"备注", "remark"}:
                continue
            if "：" in raw_line:
                key, value = raw_line.split("：", 1)
            elif ":" in raw_line:
                key, value = raw_line.split(":", 1)
            else:
                continue
            label = label_map.get(key.strip())
            if label:
                add_line(label, value.strip())
        return receipt_lines

    submitter_identifier_text = str(
        payload.get("submitter_identifier") or ""
    ).strip()
    submitter_display = fmt_value(submitter_label)
    if (
        submitter_identifier_text
        and submitter_identifier_text not in submitter_display
    ):
        submitter_display = f"{submitter_display} / {submitter_identifier_text}"

    lines = [
        f"{fmt_label('触发方式')}{sep}{_trigger_source_label(trigger_source)}",
        f"{fmt_label('触发人')}{sep}{fmt_value(trigger_user_label)}",
        f"{fmt_label('审批发起人')}{sep}{submitter_display}",
    ]
    if trigger_reason:
        lines.append(f"{fmt_label('触发原因')}{sep}{fmt_value(trigger_reason)}")
    lines.append(f"{fmt_label('公有云类型')}{sep}{fmt_value(provider_name)}")
    lines.append(f"{fmt_label('充值账号')}{sep}{fmt_value(payload.get('recharge_account'))}")
    lines.append(f"{fmt_label('充值客户')}{sep}{fmt_value(payload.get('recharge_customer_name'))}")
    lines.append(
        f"{fmt_label('付款金额')}{sep}{fmt_amount(payload.get('amount'), payload.get('currency'))}"
    )
    lines.append(f"{fmt_label('付款公司')}{sep}{fmt_value(payload.get('payment_company'))}")
    lines.append(f"{fmt_label('支付方式')}{sep}{fmt_value(payload.get('payment_way'))}")
    lines.append(f"{fmt_label('付款方式')}{sep}{fmt_value(payload.get('remit_method'))}")
    expected_date = str(payload.get("expected_date") or "").strip()
    if expected_date:
        lines.append(f"{fmt_label('期望到账时间')}{sep}{expected_date}")
    receipt_info_lines = collect_receipt_info_lines(
        payload.get("payee"), payload.get("remark")
    )
    if receipt_info_lines:
        lines.append(fmt_label("收款信息"))
        lines.extend(receipt_info_lines)
    else:
        payment_note = str(payload.get("payment_note") or "").strip()
        remark = payload.get("remark")
        if payment_note:
            lines.append(f"{fmt_label('备注')}{sep}{payment_note}")
        elif remark and not remark_is_payee_details_only(remark):
            lines.append(f"{fmt_label('备注')}{sep}{str(remark).strip()}")
    lines.append(f"{fmt_label('审批状态')}{sep}{approval_status}")
    return "\n".join(lines)


def _workspace_root() -> Path:
    """Workspace root: env var WORKSPACE_ROOT takes precedence, else infer from file location."""
    env_root = os.environ.get("WORKSPACE_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    # In Docker: /opt/backend/cloud_billing/services/recharge_approval.py -> /opt/backend/
    # In local: /path/to/OnePro/devmind/backend/cloud_billing/services/recharge_approval.py -> /path/to/OnePro/devmind/backend/
    return Path(__file__).resolve().parents[2]


def _skill_root_path() -> Path:
    return _workspace_root() / "cloud_billing" / "skills"


def _approval_skill_path() -> Path:
    return _skill_root_path() / "feishu-cloud-billing-approval"


def _load_skill_script_module(relative_path: str):
    script_path = _approval_skill_path() / relative_path
    spec = importlib.util.spec_from_file_location(
        f"cloud_billing_skill_{script_path.stem}",
        script_path,
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load skill script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _redact_observability_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(
        r"(?i)(secret|token|password|authorization|app_secret)(['\"\s:=]+)([^,'\"\s}]+)",
        r"\1\2***REDACTED***",
        text,
    )
    return re.sub(r"\b\d{12,}\b", lambda match: f"***{match.group(0)[-4:]}", text)


def _redact_observability_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if any(seg in str(key).upper() for seg in ("AUTHORIZATION", "TOKEN", "SECRET", "PASSWORD", "KEY")):
                result[key] = "***REDACTED***"
            else:
                result[key] = _redact_observability_payload(item)
        return result
    if isinstance(value, list):
        return [_redact_observability_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_observability_text(value)
    return value


def _parse_json_object_safely(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_script_stdout_from_error(error_text: str) -> str:
    marker = "Stdout:"
    if marker not in error_text:
        return ""
    stdout = error_text.split(marker, 1)[1].strip()
    return "" if stdout == "(empty)" else stdout




# Feishu API endpoints
FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_USER_QUERY_URL = "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id"
FEISHU_APPROVAL_BASE_URL = "https://www.feishu.cn"


def _get_feishu_config() -> Dict[str, str]:
    """Get Feishu configuration from environment or provider config."""
    return {
        "app_id": os.environ.get("FEISHU_APP_ID", ""),
        "app_secret": os.environ.get("FEISHU_APP_SECRET", ""),
    }


def _get_feishu_access_token() -> Optional[str]:
    """Get Feishu tenant access token with detailed logging."""
    config = _get_feishu_config()
    if not config["app_id"] or not config["app_secret"]:
        logger.warning(
            "Feishu token request skipped: FEISHU_APP_ID or FEISHU_APP_SECRET not configured"
        )
        return None

    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "app_id": config["app_id"],
            "app_secret": config["app_secret"],
        }).encode("utf-8")

        request = urllib.request.Request(
            url=FEISHU_AUTH_URL,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        logger.info(
            "Feishu API Request\n"
            "method=POST\n"
            "url=%s\n"
            "headers=%s\n"
            "payload=%s",
            FEISHU_AUTH_URL,
            json.dumps(
                {"Content-Type": "application/json; charset=utf-8"},
                ensure_ascii=False,
            ),
            json.dumps({
                "app_id": config["app_id"],
                "app_secret": "***"  # Mask secret
            }, ensure_ascii=False),
        )

        start_time = time.monotonic()
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            latency_ms = int((time.monotonic() - start_time) * 1000)

        data = json.loads(body)
        log_data = {
            **data,
            "tenant_access_token": "***REDACTED***"
            if data.get("tenant_access_token")
            else "",
        }

        logger.info(
            "Feishu API Response\n"
            "method=POST\n"
            "url=%s\n"
            "latency_ms=%s\n"
            "feishu_code=%s\n"
            "feishu_msg=%s\n"
            "body=%s",
            FEISHU_AUTH_URL,
            latency_ms,
            data.get("code"),
            data.get("msg", ""),
            json.dumps(log_data, ensure_ascii=False),
        )

        if data.get("code") == 0:
            token = data.get("tenant_access_token", "")
            logger.info(
                "Feishu token obtained successfully, expires_in=%s seconds",
                data.get("expire", "unknown")
            )
            return token
        else:
            logger.error(
                "Feishu token request failed: code=%s, msg=%s",
                data.get("code"),
                data.get("msg", "")
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(
            "Feishu API HTTP Error\n"
            "method=POST\n"
            "url=%s\n"
            "http_status=%s\n"
            "body=%s",
            FEISHU_AUTH_URL,
            e.code,
            _redact_feishu_body_for_log(body),
        )
    except urllib.error.URLError as e:
        logger.error(
            "Feishu API Network Error: POST %s\n"
            "Protocol: HTTPS\n"
            "Error: %s",
            FEISHU_AUTH_URL,
            str(e.reason)
        )
    except Exception as e:
        logger.error(
            "Feishu token request exception: POST %s\n"
            "Protocol: HTTPS\n"
            "Error: %s",
            FEISHU_AUTH_URL,
            str(e)
        )

    return None


FEISHU_CONTACT_BASE_URL = "https://open.feishu.cn/open-apis/contact/v3"
FEISHU_ROOT_DEPARTMENT_ID = "0"
FEISHU_CONTACT_PAGE_SIZE = 50
FEISHU_USERS_CACHE_KEY_PREFIX = "cloud_billing:feishu_users:v3"
FEISHU_USERS_CACHE_TTL_SECONDS = int(
    os.getenv("FEISHU_USERS_CACHE_TTL_SECONDS", "3600")
)
FEISHU_USERS_WALK_DEPARTMENTS = os.getenv(
    "FEISHU_USERS_WALK_DEPARTMENTS",
    "auto",
).strip().lower()
FEISHU_USERS_DEPARTMENT_MAX_WORKERS = int(
    os.getenv("FEISHU_USERS_DEPARTMENT_MAX_WORKERS", "8")
)
FEISHU_USERS_MAX_DEPARTMENTS = int(
    os.getenv("FEISHU_USERS_MAX_DEPARTMENTS", "500")
)
_FEISHU_USERS_CACHE_LOCK = threading.Lock()
FEISHU_LIST_USERS_URL = (
    f"{FEISHU_CONTACT_BASE_URL}/users?"
    "user_id_type=user_id&department_id_type=open_department_id"
    f"&department_id={FEISHU_ROOT_DEPARTMENT_ID}"
    f"&page_size={FEISHU_CONTACT_PAGE_SIZE}&fetch_child=true"
)


def list_feishu_users(*, force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    List all users from Feishu Contact API (with pagination).

    Tries the full /users endpoint with child departments enabled, then walks
    all visible departments and merges users by user_id/email/mobile.
    """
    cache_key = f"{FEISHU_USERS_CACHE_KEY_PREFIX}:{FEISHU_USERS_WALK_DEPARTMENTS}"
    if not force_refresh:
        cached_users = cache.get(cache_key)
        if isinstance(cached_users, list):
            logger.info(
                "Feishu list users returned %d cached users",
                len(cached_users),
            )
            return cached_users

    with _FEISHU_USERS_CACHE_LOCK:
        if not force_refresh:
            cached_users = cache.get(cache_key)
            if isinstance(cached_users, list):
                logger.info(
                    "Feishu list users returned %d cached users",
                    len(cached_users),
                )
                return cached_users
        return _list_feishu_users_uncached(cache_key)


def _list_feishu_users_uncached(cache_key: str) -> List[Dict[str, str]]:
    """Fetch Feishu users from remote API and refresh the shared cache."""
    token = _get_feishu_access_token()
    if not token:
        logger.warning("Cannot list Feishu users: no access token.")
        return []

    users = []

    # Try full contact API first. fetch_child=true should include users in
    # child departments when the app has visibility for those departments.
    result = _fetch_feishu_user_page(token, FEISHU_LIST_USERS_URL)
    if result is not None:
        users = result

    should_walk_departments = FEISHU_USERS_WALK_DEPARTMENTS not in {
        "0",
        "false",
        "no",
        "off",
    }

    # The root users endpoint can return only direct contacts even when
    # fetch_child=true. Walk every visible department unless explicitly
    # disabled, then merge and cache the result.
    if users and should_walk_departments:
        users = _dedupe_feishu_users(
            users + _list_feishu_users_by_departments(token)
        )

    if not users:
        logger.info("Root contact API returned no users, trying departments")
        users = _list_feishu_users_by_departments(token)

    # Populate missing fields from the per-user search endpoint when possible.
    if users and any(
        not u.get("name") or not (u.get("email") or u.get("mobile"))
        for u in users
    ):
        logger.info("Enriching Feishu users with per-user contact data")
        _enrich_user_details(token, users)

    _apply_feishu_user_display_names(users)
    cache.set(
        cache_key,
        users,
        timeout=FEISHU_USERS_CACHE_TTL_SECONDS,
    )
    logger.info("Feishu list users returned %d users", len(users))
    return users


def _build_feishu_contact_url(path: str, params: Dict[str, Any]) -> str:
    """Build a Feishu Contact API URL with encoded query parameters."""
    from urllib.parse import urlencode

    clean_params = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    return f"{FEISHU_CONTACT_BASE_URL}{path}?{urlencode(clean_params)}"


def _build_feishu_user_list_url(
    *,
    department_id: str,
    fetch_child: bool,
) -> str:
    return _build_feishu_contact_url(
        "/users",
        {
            "user_id_type": "user_id",
            "department_id_type": "open_department_id",
            "department_id": department_id,
            "page_size": FEISHU_CONTACT_PAGE_SIZE,
            "fetch_child": str(fetch_child).lower(),
        },
    )


def _append_page_token(url: str, page_token: str) -> str:
    """Return URL with an updated Feishu page_token query parameter."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page_token"] = page_token
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _dedupe_feishu_users(users: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Deduplicate Feishu users while preserving the first seen order."""
    deduped: List[Dict[str, str]] = []
    seen = set()
    for user in users:
        key = (
            user.get("user_id")
            or user.get("email")
            or user.get("mobile")
            or user.get("name")
            or ""
        )
        key = str(key).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(user)
    return deduped


def _format_email_local_name(email: str) -> str:
    """Format an email local part as a readable display name."""
    local_part = str(email or "").split("@", 1)[0].strip()
    if not local_part:
        return ""
    words = [
        word
        for word in re.split(r"[._\-\s]+", local_part)
        if word
    ]
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _apply_feishu_user_display_names(users: List[Dict[str, str]]) -> None:
    """Populate display names for Feishu users in-place."""
    emails = sorted(
        {
            str(user.get("email") or "").strip().lower()
            for user in users
            if str(user.get("email") or "").strip()
        }
    )
    local_user_names: Dict[str, str] = {}
    if emails:
        batch_size = 500
        for start in range(0, len(emails), batch_size):
            batch = emails[start:start + batch_size]
            for user in User.objects.filter(email__in=batch).iterator():
                email = str(user.email or "").strip().lower()
                display_name = (
                    f"{user.first_name or ''} {user.last_name or ''}".strip()
                    or user.get_username()
                )
                if email and display_name:
                    local_user_names[email] = display_name

    for user in users:
        email = str(user.get("email") or "").strip()
        name = str(user.get("name") or "").strip()
        display_name = (
            name
            or local_user_names.get(email.lower(), "")
            or _format_email_local_name(email)
            or str(user.get("user_id") or "").strip()
        )
        user["name"] = name or display_name
        user["display_name"] = display_name


def _fetch_feishu_department_users(
    token: str,
    department_id: str,
) -> List[Dict[str, str]]:
    """Fetch users from one Feishu department."""
    url = _build_feishu_user_list_url(
        department_id=department_id,
        fetch_child=False,
    )
    page_users = _fetch_feishu_user_page(token, url)
    return page_users or []


def _limit_feishu_departments(department_ids: List[str]) -> List[str]:
    """Limit Feishu department traversal to protect request latency."""
    if len(department_ids) <= FEISHU_USERS_MAX_DEPARTMENTS:
        return department_ids
    logger.warning(
        "Feishu department traversal limited from %d to %d departments",
        len(department_ids),
        FEISHU_USERS_MAX_DEPARTMENTS,
    )
    return department_ids[:FEISHU_USERS_MAX_DEPARTMENTS]


def _list_feishu_users_by_departments(
    token: str,
) -> List[Dict[str, str]]:
    """List users from every visible Feishu department and deduplicate."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    department_ids = _limit_feishu_departments(
        _list_feishu_departments(token)
    )
    if not department_ids:
        return []
    max_workers = max(1, min(FEISHU_USERS_DEPARTMENT_MAX_WORKERS, 16))
    users: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_feishu_department_users,
                token,
                department_id,
            ): department_id
            for department_id in department_ids
        }
        for future in as_completed(futures):
            department_id = futures[future]
            try:
                users.extend(future.result())
            except Exception as exc:
                logger.warning(
                    "Feishu department user fetch failed: department_id=%s "
                    "error=%s",
                    department_id,
                    exc,
                )
    return _dedupe_feishu_users(users)


def _list_feishu_departments(token: str) -> List[str]:
    """List all visible Feishu department ids using breadth-first traversal."""
    import urllib.error
    import urllib.request

    department_ids = [FEISHU_ROOT_DEPARTMENT_ID]
    queue = [FEISHU_ROOT_DEPARTMENT_ID]
    seen = {FEISHU_ROOT_DEPARTMENT_ID}
    max_departments = max(1, FEISHU_USERS_MAX_DEPARTMENTS)

    while queue and len(department_ids) < max_departments:
        department_id = queue.pop(0)
        base_url = _build_feishu_contact_url(
            f"/departments/{department_id}/children",
            {
                "department_id_type": "open_department_id",
                "page_size": FEISHU_CONTACT_PAGE_SIZE,
            },
        )
        url = base_url
        while url:
            try:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                }
                logger.info(
                    "Feishu API Request\n"
                    "method=GET\n"
                    "url=%s\n"
                    "headers=%s",
                    url,
                    json.dumps(
                        _redact_feishu_headers(headers),
                        ensure_ascii=False,
                    ),
                )
                request = urllib.request.Request(
                    url=url,
                    headers=headers,
                    method="GET",
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    status_code = getattr(response, "status", None) or getattr(
                        response,
                        "code",
                        None,
                    )
                    body = response.read().decode("utf-8")
                data = json.loads(body)
                logger.info(
                    "Feishu API Response\n"
                    "method=GET\n"
                    "url=%s\n"
                    "http_status=%s\n"
                    "feishu_code=%s\n"
                    "feishu_msg=%s\n"
                    "body=%s",
                    url,
                    status_code,
                    data.get("code"),
                    data.get("msg", ""),
                    _redact_feishu_body_for_log(body),
                )
                if data.get("code") != 0:
                    logger.warning(
                        "Feishu list departments failed: code=%s, msg=%s, url=%s body=%s",
                        data.get("code"),
                        data.get("msg", ""),
                        url,
                        _redact_feishu_body_for_log(body),
                    )
                    break

                page_data = data.get("data", {}) or {}
                for item in page_data.get("items", []) or []:
                    child_id = str(
                        item.get("open_department_id")
                        or item.get("department_id")
                        or ""
                    ).strip()
                    if child_id and child_id not in seen:
                        seen.add(child_id)
                        department_ids.append(child_id)
                        queue.append(child_id)
                        if len(department_ids) >= max_departments:
                            logger.warning(
                                "Feishu department traversal reached "
                                "the configured limit of %d departments",
                                max_departments,
                            )
                            queue.clear()
                            url = ""
                            break

                if len(department_ids) >= max_departments:
                    break

                page_token = str(page_data.get("page_token") or "").strip()
                if page_data.get("has_more") and page_token:
                    url = _append_page_token(base_url, page_token)
                else:
                    url = ""
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                logger.warning(
                    "Feishu list departments HTTP error: url=%s status=%s body=%s",
                    url,
                    exc.code,
                    _redact_feishu_body_for_log(body),
                )
                break
            except urllib.error.URLError as exc:
                logger.warning(
                    "Feishu list departments network error: %s",
                    str(exc.reason),
                )
                break
            except Exception as exc:
                logger.warning("Feishu list departments exception: %s", str(exc))
                break

    logger.info(
        "Feishu visible departments returned %d departments",
        len(department_ids),
    )
    return department_ids


def _fetch_feishu_user_page(token: str, url: str) -> Optional[List[Dict[str, str]]]:
    """Fetch one page of users from a Feishu contact API endpoint."""
    import urllib.request
    import urllib.error

    import_result: Optional[List[Dict[str, str]]] = None
    base_url = url
    page_users = []

    while base_url:
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            logger.info(
                "Feishu API Request\n"
                "method=GET\n"
                "url=%s\n"
                "headers=%s",
                base_url,
                json.dumps(
                    _redact_feishu_headers(headers),
                    ensure_ascii=False,
                ),
            )
            request = urllib.request.Request(
                url=base_url,
                headers=headers,
                method="GET",
            )

            start_time = time.monotonic()
            with urllib.request.urlopen(request, timeout=10) as response:
                status_code = getattr(response, "status", None) or getattr(
                    response,
                    "code",
                    None,
                )
                body = response.read().decode("utf-8")
                latency_ms = int((time.monotonic() - start_time) * 1000)

            data = json.loads(body)

            logger.info(
                "Feishu API Response\n"
                "method=GET\n"
                "url=%s\n"
                "http_status=%s\n"
                "latency_ms=%s\n"
                "feishu_code=%s\n"
                "feishu_msg=%s\n"
                "body=%s",
                base_url,
                status_code,
                latency_ms,
                data.get("code"),
                data.get("msg", ""),
                _redact_feishu_body_for_log(body),
            )

            if data.get("code") != 0:
                logger.warning(
                    "Feishu list users failed: code=%s, msg=%s, url=%s body=%s",
                    data.get("code"),
                    data.get("msg", ""),
                    base_url,
                    _redact_feishu_body_for_log(body),
                )
                break

            for item in data.get("data", {}).get("items", []):
                page_users.append({
                    "user_id": str(item.get("user_id") or "").strip(),
                    "name": str(item.get("name") or item.get("en_name") or "").strip(),
                    "email": str(item.get("email") or "").strip(),
                    "mobile": str(item.get("mobile") or "").strip(),
                })

            page_data = data.get("data", {})
            has_more = page_data.get("has_more", False)
            page_token = page_data.get("page_token")
            if has_more and page_token:
                base_url = _append_page_token(url, page_token)
            else:
                base_url = None

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.warning(
                "Feishu list users HTTP error: url=%s status=%s body=%s",
                base_url,
                e.code,
                _redact_feishu_body_for_log(body),
            )
            break
        except urllib.error.URLError as e:
            logger.warning(
                "Feishu list users network error: %s",
                str(e.reason),
            )
            break
        except Exception as e:
            logger.warning("Feishu list users exception: %s", str(e))
            break
        else:
            import_result = page_users

    return import_result


def _enrich_user_details(token: str, users: List[Dict[str, str]]) -> None:
    """
    Fetch email/mobile for each user individually from the full contact API.
    Only populates fields that are currently empty.
    """
    import urllib.request
    import urllib.error

    for user in users:
        if user.get("email") or user.get("mobile"):
            continue

        try:
            # Use user search endpoint to get full details per user
            search_url = (
                "https://open.feishu.cn/open-apis/contact/v3/users/search?"
                "user_id_type=user_id&department_id_type=open_department_id"
                "&page_size=50"
            )
            payload_obj = {
                "query_user": {"user_ids": [user["user_id"]]},
            }
            payload = json.dumps(payload_obj).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            logger.info(
                "Feishu API Request\n"
                "method=POST\n"
                "url=%s\n"
                "headers=%s\n"
                "payload=%s",
                search_url,
                json.dumps(
                    _redact_feishu_headers(headers),
                    ensure_ascii=False,
                ),
                json.dumps(
                    _redact_feishu_payload_for_log(payload_obj),
                    ensure_ascii=False,
                ),
            )

            request = urllib.request.Request(
                url=search_url,
                data=payload,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                status_code = getattr(response, "status", None) or getattr(
                    response,
                    "code",
                    None,
                )
                body = response.read().decode("utf-8")

            data = json.loads(body)
            logger.info(
                "Feishu API Response\n"
                "method=POST\n"
                "url=%s\n"
                "http_status=%s\n"
                "feishu_code=%s\n"
                "feishu_msg=%s\n"
                "body=%s",
                search_url,
                status_code,
                data.get("code"),
                data.get("msg", ""),
                _redact_feishu_body_for_log(body),
            )
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                if items:
                    item = items[0]
                    if not user.get("name"):
                        user["name"] = str(
                            item.get("name") or item.get("en_name") or ""
                        ).strip()
                    user["email"] = str(item.get("email") or "").strip()
                    user["mobile"] = str(item.get("mobile") or "").strip()
        except Exception:
            pass


def inspect_recharge_account_submission_state(
    raw_recharge_info: str,
    *,
    approval_code: str,
    lookback_days: int = 30,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> dict[str, Any]:
    """
    Inspect Feishu for ongoing/finished instances matching the recharge request.

    Directly calls Feishu APIs (no skill script). Returns a normalized state
    used by check_ongoing_recharge_approval_submission to decide whether to block.
    """
    request_data = parse_recharge_info(raw_recharge_info)
    token = _get_feishu_access_token()
    if not token:
        return {
            "state": "none",
            "approval_code": approval_code,
            "recharge_account": extract_recharge_account_from_payload(request_data),
            "matches": [],
        }
    return _inspect_account_state(
        token,
        approval_code,
        request_data,
        lookback_days,
        approval_base_url=approval_base_url,
    )


def check_ongoing_recharge_approval_submission(
    provider: CloudProvider,
    raw_recharge_info: str,
    *,
    approval_code: str,
    lookback_days: int = 30,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> dict[str, Any]:
    """
    Check whether a recharge approval submission should be blocked.

    This keeps the preflight decision in one place while allowing callers to
    render their own response shape.
    """
    result: dict[str, Any] = {
        "blocked": False,
        "reason": "",
        "record_id": 0,
        "instance_code": "",
        "approval_code": "",
        "status": "",
        "recharge_account": "",
        "account_state": None,
        "excluded_duplicate_instance_codes": [],
    }
    if not approval_code or not str(raw_recharge_info or "").strip():
        return result

    try:
        account_state = inspect_recharge_account_submission_state(
            raw_recharge_info,
            approval_code=approval_code,
            lookback_days=lookback_days,
            approval_base_url=approval_base_url,
        )
    except Exception as exc:
        logger.warning(
            "Failed to inspect recharge account submission state; "
            "blocking submission until the preflight check is fixed "
            "(error=%s, exc_info=True).",
            exc,
            exc_info=True,
        )
        result.update(
            {
                "blocked": True,
                "reason": "preflight_check_failed",
                "status": "error",
                "message": "充值审批预检失败，请修复预检后再提交。",
            }
        )
        return result

    result["account_state"] = account_state
    recharge_account = str(
        account_state.get("recharge_account") or ""
    ).strip()
    recovered_instance_codes = [
        str(record.feishu_instance_code or "").strip()
        for record in find_recovered_recharge_approvals_for_account(
            provider=provider,
            recharge_account=recharge_account,
        )
        if str(record.feishu_instance_code or "").strip()
    ]
    result["excluded_duplicate_instance_codes"] = (
        recovered_instance_codes
    )
    if account_state.get("state") != "ongoing":
        return result

    ongoing_instance_code = str(
        account_state.get("instance_code") or ""
    ).strip()
    blocking_record = find_ongoing_recharge_approval_for_account(
        provider=provider,
        recharge_account=recharge_account,
    )
    ongoing_record = None
    if ongoing_instance_code:
        remote_record = RechargeApprovalRecord.objects.filter(
            provider=provider,
            feishu_instance_code=ongoing_instance_code,
        ).first()
        if (
            remote_record is not None
            and remote_record.fulfillment_status
            == RechargeApprovalRecord.FULFILLMENT_RECOVERED
        ):
            if blocking_record is None:
                result["excluded_duplicate_instance_codes"] = list(
                    dict.fromkeys(
                        [
                            *recovered_instance_codes,
                            ongoing_instance_code,
                        ]
                    )
                )
                return result
            ongoing_record = blocking_record
            ongoing_instance_code = str(
                blocking_record.feishu_instance_code or ""
            ).strip()
        else:
            ongoing_record = remote_record or blocking_record
    elif recharge_account:
        ongoing_record = blocking_record
        if ongoing_record is not None:
            ongoing_instance_code = str(
                ongoing_record.feishu_instance_code or ""
            ).strip()
        elif recovered_instance_codes:
            result["excluded_duplicate_instance_codes"] = (
                recovered_instance_codes
            )
            return result

    status_text = str(account_state.get("status") or "").strip()
    if not status_text and ongoing_record is not None:
        status_text = str(ongoing_record.status or "").strip()

    approval_code_text = str(account_state.get("approval_code") or "").strip()
    if not approval_code_text and ongoing_record is not None:
        approval_code_text = str(ongoing_record.feishu_approval_code or "").strip()

    message_parts = [
        f"充值账号 {recharge_account or '未知'} 已有一笔正在审批中的充值申请",
    ]
    if ongoing_instance_code:
        message_parts.append(f"实例号：{ongoing_instance_code}")
    elif ongoing_record is not None:
        message_parts.append(f"本地记录：{ongoing_record.id}")
    else:
        message_parts.append("飞书未返回实例号")
    if approval_code_text:
        message_parts.append(f"审批码：{approval_code_text}")
    if status_text:
        message_parts.append(f"状态：{status_text}")
    if ongoing_record is not None and not ongoing_instance_code:
        record_status_message = str(ongoing_record.status_message or "").strip()
        if record_status_message:
            message_parts.append(f"本地状态说明：{record_status_message}")

    result.update(
        {
            "blocked": True,
            "reason": "ongoing_approval_exists",
            "record_id": ongoing_record.id if ongoing_record else 0,
            "instance_code": ongoing_instance_code,
            "approval_code": approval_code_text,
            "status": status_text,
            "recharge_account": recharge_account,
            "message": "；".join(message_parts) + "，请先确认上一单是否已结束，再继续提交。",
        }
    )
    return result


def _resolve_user_id_by_email_or_mobile(
    identifier: str,
    access_token: str,
) -> Optional[Tuple[str, str]]:
    """
    Query Feishu user_id by email or mobile phone.

    Returns user_id (not open_id) because the Feishu approval API
    requires user_id format.

    Args:
        identifier: Email or mobile number
        access_token: Feishu tenant access token

    Returns:
        A tuple of (user_id, user_name) if found, None otherwise.
    """
    if not identifier or not access_token:
        return None

    # Determine if it's email or mobile
    # Feishu approval API requires user_id format (not open_id)
    is_email = "@" in identifier
    payload = {
        "include_resigned": True,
        "emails": [],
        "mobiles": [],
    }

    if is_email:
        payload["emails"] = [identifier]
    else:
        # Clean mobile number
        mobile = identifier.strip().lstrip("+")
        payload["mobiles"] = [mobile]

    try:
        import urllib.request
        import urllib.error

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        logger.info(
            "Feishu API Request\n"
            "method=POST\n"
            "url=%s\n"
            "headers=%s\n"
            "payload=%s",
            FEISHU_USER_QUERY_URL,
            json.dumps(_redact_feishu_headers(headers), ensure_ascii=False),
            json.dumps(
                _redact_feishu_payload_for_log(payload),
                ensure_ascii=False,
            ),
        )

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=FEISHU_USER_QUERY_URL,
            data=data,
            headers=headers,
            method="POST",
        )

        start_time = time.monotonic()
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            latency_ms = int((time.monotonic() - start_time) * 1000)

        result = json.loads(body)

        logger.info(
            "Feishu API Response\n"
            "method=POST\n"
            "url=%s\n"
            "latency_ms=%s\n"
            "feishu_code=%s\n"
            "feishu_msg=%s\n"
            "body=%s",
            FEISHU_USER_QUERY_URL,
            latency_ms,
            result.get("code"),
            result.get("msg", ""),
            _redact_feishu_body_for_log(body),
        )

        if result.get("code") == 0:
            users = result.get("data", {}).get("user_list", [])
            if users:
                user = users[0] or {}
                user_id = str(user.get("user_id") or "").strip()
                user_name = str(
                    user.get("name") or user.get("en_name") or ""
                ).strip()
                logger.info(
                    "Feishu user resolved: identifier=%s -> user_id=%s, name=%s",
                    identifier,
                    user_id,
                    user_name or "(not set)",
                )
                if user_id:
                    return user_id, user_name
            else:
                logger.warning(
                    "Feishu user not found: identifier=%s, response=%s",
                    identifier,
                    _redact_feishu_payload_for_log(result),
                )
        else:
            logger.error(
                "Feishu user query failed: code=%s, msg=%s, identifier=%s",
                result.get("code"),
                result.get("msg", ""),
                identifier
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(
            "Feishu API HTTP Error\n"
            "method=POST\n"
            "url=%s\n"
            "http_status=%s\n"
            "payload=%s\n"
            "body=%s",
            FEISHU_USER_QUERY_URL,
            e.code,
            json.dumps(
                _redact_feishu_payload_for_log(payload),
                ensure_ascii=False,
            ),
            _redact_feishu_body_for_log(body),
        )
    except urllib.error.URLError as e:
        logger.error(
            "Feishu API Network Error: POST %s\n"
            "Protocol: HTTPS\n"
            "Error: %s",
            FEISHU_USER_QUERY_URL,
            str(e.reason)
        )
    except Exception as e:
        logger.error(
            "Feishu user query exception: POST %s\n"
            "Protocol: HTTPS\n"
            "Error: %s",
            FEISHU_USER_QUERY_URL,
            str(e)
        )

    return None


def _extract_text_from_messages(messages: Any) -> str:
    chunks = []
    for batch in messages or []:
        for message in batch or []:
            content = getattr(message, "content", "")
            if isinstance(content, str):
                chunks.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if text:
                            chunks.append(str(text))
    return "\n\n".join(chunks)


def _extract_usage_from_llm_result(response: LLMResult) -> Tuple[str, Dict[str, Any], str]:
    llm_output = response.llm_output or {}
    generations = response.generations or []
    generation = generations[0][0] if generations and generations[0] else None
    message = getattr(generation, "message", None)
    output_text = ""
    if message is not None:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            output_text = content
        else:
            output_text = json.dumps(content, ensure_ascii=False)
    usage_meta = {}
    response_meta = getattr(message, "response_metadata", {}) if message else {}
    if isinstance(response_meta, dict):
        usage_meta = response_meta.get("token_usage") or {}
    usage_data = getattr(message, "usage_metadata", {}) if message else {}
    if isinstance(usage_data, dict):
        usage_meta = {
            "prompt_tokens": usage_data.get("input_tokens", usage_meta.get("prompt_tokens", 0)),
            "completion_tokens": usage_data.get("output_tokens", usage_meta.get("completion_tokens", 0)),
            "total_tokens": usage_data.get("total_tokens", usage_meta.get("total_tokens", 0)),
        }
    model_name = (
        llm_output.get("model_name")
        or response_meta.get("model")
        or response_meta.get("model_name")
        or "unknown"
    )
    prompt_tokens = int(usage_meta.get("prompt_tokens") or 0)
    completion_tokens = int(usage_meta.get("completion_tokens") or 0)
    total_tokens = int(usage_meta.get("total_tokens") or (prompt_tokens + completion_tokens))
    return model_name, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }, output_text


class RechargeApprovalAgentResult(BaseModel):
    submitter_identifier: str = ""
    resolved_submitter_user_id: str = ""
    submitter_user_label: str = ""
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    status: str = ""
    approval_code: str = ""
    instance_code: str = ""
    summary: str = ""
    error_message: str = ""


class RechargeApprovalParsedPayload(BaseModel):
    cloud_type: str = ""
    payment_type: str = ""
    recharge_customer_name: str = ""
    recharge_account: str = ""
    payment_way: str = ""
    payment_company: str = ""
    remit_method: str = ""
    amount: Any = ""
    currency: str = ""
    payment_note: str = ""
    expected_date: str = ""
    remark: str = ""
    payee: Dict[str, Any] = Field(default_factory=dict)


class FeishuHttpToolInput(BaseModel):
    """Input schema for feishu_http_request tool."""
    url: str
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Any = None


@tool
def feishu_http_request(
    tool_input: Annotated[str, "JSON string with url, method, headers, body fields."],
) -> str:
    """
    Make an HTTP request to Feishu APIs.

    All calls are intercepted by the agent callback handler and recorded
    as RechargeApprovalLLMRun entries with runner_type=skill_http.
    """
    import urllib.error
    import urllib.request

    parsed = json.loads(tool_input)
    url = parsed["url"]
    method = str(parsed.get("method", "POST")).upper()
    headers = {
        **({"Content-Type": "application/json; charset=utf-8"}),
        **parsed.get("headers", {}),
    }
    # Mask sensitive headers
    for k in list(headers):
        if any(seg in k.upper() for seg in ("AUTHORIZATION", "TOKEN", "SECRET", "PASSWORD", "KEY")):
            headers[k] = "***REDACTED***"
    body = parsed.get("body")
    body_bytes = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


class RechargeApprovalAgentCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        *,
        record: RechargeApprovalRecord,
        user_id: Optional[int],
        langfuse_runtime: Any | None = None,
    ) -> None:
        if langfuse_runtime is None:
            from agent_runner.observability.langfuse import (
                create_langfuse_observer,
            )

            langfuse_runtime = create_langfuse_observer(
                name="RechargeApprovalAgentRunner",
                trace_seed=str(getattr(record, "trace_id", "") or ""),
                user_id=str(user_id) if user_id else None,
                session_id=str(getattr(record, "id", "") or ""),
                metadata={
                    "record_id": getattr(record, "id", None),
                    "record_trace_id": str(
                        getattr(record, "trace_id", "") or ""
                    ),
                    "component": "recharge_approval_callback",
                },
                tags=["agent", "recharge_approval", "tool"],
            )

        self.record = record
        self.user_id = user_id
        self.langfuse_runtime = langfuse_runtime
        self.starts: Dict[str, Any] = {}
        self.inputs: Dict[str, str] = {}
        self._tool_starts: Dict[str, Dict[str, Any]] = {}
        self._tool_observations: Dict[str, Any] = {}

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ) -> Any:
        key = str(run_id)
        self.starts[key] = timezone.now()
        self.inputs[key] = _extract_text_from_messages(messages)
        create_recharge_approval_event(
            record=self.record,
            event_type="agent_llm_started",
            stage="agent_reasoning",
            source="deepagent",
            message="Deepagent LLM call started.",
            payload={"run_id": key},
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        **kwargs,
    ) -> Any:
        from agentcore_metering.adapters.django.models import LLMUsage

        key = str(run_id)
        started_at = self.starts.get(key) or timezone.now()
        finished_at = timezone.now()
        model_name, usage_payload, output_text = _extract_usage_from_llm_result(response)
        llm_usage = LLMUsage.objects.create(
            user_id=self.user_id,
            model=model_name,
            prompt_tokens=usage_payload.get("prompt_tokens", 0),
            completion_tokens=usage_payload.get("completion_tokens", 0),
            total_tokens=usage_payload.get("total_tokens", 0),
            success=True,
            error=None,
            metadata={
                "trace_id": str(self.record.trace_id),
                "source_type": "recharge_approval",
                "source_record_id": self.record.id,
                "stage": "agent_reasoning",
                "node_name": "recharge_approval_agent",
            },
            started_at=started_at,
        )
        create_recharge_approval_llm_run(
            record=self.record,
            stage="agent_reasoning",
            runner_type="llm",
            provider="deepagent",
            model=model_name,
            input_snapshot=self.inputs.get(key, ""),
            output_snapshot=output_text,
            usage_payload=usage_payload,
            llm_usage_id=llm_usage.id,
            success=True,
            started_at=started_at,
            finished_at=finished_at,
        )
        create_recharge_approval_event(
            record=self.record,
            event_type="agent_llm_completed",
            stage="agent_reasoning",
            source="deepagent",
            message="Deepagent LLM call completed.",
            payload={"run_id": key, "model": model_name, **usage_payload},
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        **kwargs,
    ) -> Any:
        key = str(run_id)
        started_at = self.starts.get(key) or timezone.now()
        finished_at = timezone.now()
        create_recharge_approval_llm_run(
            record=self.record,
            stage="agent_reasoning",
            runner_type="llm",
            provider="deepagent",
            model="unknown",
            input_snapshot=self.inputs.get(key, ""),
            success=False,
            error_message=str(error),
            started_at=started_at,
            finished_at=finished_at,
        )
        create_recharge_approval_event(
            record=self.record,
            event_type="agent_llm_failed",
            stage="agent_reasoning",
            source="deepagent",
            message=str(error),
            payload={"run_id": key, "error": str(error)},
        )

    # -------------------------------------------------------------------------
    # Tool callbacks — intercept skill script and HTTP tool calls
    # -------------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        self._tool_starts[key] = {
            "started_at": timezone.now(),
            "input": input_str,
        }
        tool_name = str(serialized.get("name") or "")
        if self.langfuse_runtime is not None:
            observation = self.langfuse_runtime.start_tool_observation(
                name=tool_name or "tool",
                input_payload=input_str,
                metadata={
                    "record_id": self.record.id,
                    "record_trace_id": str(self.record.trace_id),
                    "run_id": key,
                },
            )
            if observation is not None:
                self._tool_observations[key] = observation

        if tool_name == "feishu_http_request":
            create_recharge_approval_event(
                record=self.record,
                event_type="skill_http_started",
                stage="skill_execute",
                source="feishu_http_request",
                message="Feishu HTTP request started.",
                payload={"run_id": key, "input_preview": input_str[:300]},
            )
        elif tool_name == "submit_recharge_approval_via_script":
            create_recharge_approval_event(
                record=self.record,
                event_type="skill_script_started",
                stage="skill_execute",
                source="run_skill_script",
                message="Skill script execution started.",
                payload={"run_id": key, "input_preview": input_str[:500]},
            )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        start_info = self._tool_starts.pop(key, {})
        started_at = start_info.get("started_at") or timezone.now()
        finished_at = timezone.now()
        input_str = start_info.get("input", "")
        tool_name = str((kwargs.get("serialized") or {}).get("name") or "")
        observation = self._tool_observations.pop(key, None)

        if tool_name == "feishu_http_request":
            output_text = ""
            if hasattr(output, "content"):
                output_text = str(output.content or "")
            elif isinstance(output, str):
                output_text = output
            else:
                output_text = str(output)
            try:
                resp_json = json.loads(output_text)
                status = resp_json.get("code", -1)
                success = status == 0
            except Exception:
                success = False
            create_recharge_approval_llm_run(
                record=self.record,
                stage="skill_execute",
                runner_type="skill_http",
                provider="urllib.request",
                model="",
                input_snapshot=input_str[:2000],
                output_snapshot=output_text[:2000],
                parsed_payload={"success": success},
                stdout="",
                stderr="",
                success=success,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=max(
                    0, int((finished_at - started_at).total_seconds() * 1000)
                ),
            )
            create_recharge_approval_event(
                record=self.record,
                event_type="skill_http_completed",
                stage="skill_execute",
                source="feishu_http_request",
                message="Feishu HTTP request completed.",
                payload={"run_id": key, "success": success},
            )
            if observation is not None and self.langfuse_runtime is not None:
                self.langfuse_runtime.end_observation(
                    observation,
                    output=output_text[:4000],
                    metadata={"success": success, "tool_name": tool_name},
                )
                safe_flush = getattr(self.langfuse_runtime, "safe_flush", None)
                if callable(safe_flush):
                    safe_flush()

        elif tool_name == "submit_recharge_approval_via_script":
            output_text = ""
            if hasattr(output, "content"):
                output_text = str(output.content or "")
            elif isinstance(output, str):
                output_text = output
            else:
                output_text = str(output)
            parsed_output = _parse_json_object_safely(output_text)
            script_trace = _redact_observability_payload(
                parsed_output.get("script_trace") or {}
            )
            if not isinstance(script_trace, dict):
                script_trace = {}
            script_trace.setdefault("tool_name", tool_name)
            script_trace.setdefault("tool_input_preview", _redact_observability_text(input_str[:2000]))
            http_traces = parsed_output.get("http_traces") or []
            create_recharge_approval_llm_run(
                record=self.record,
                stage="skill_execute",
                runner_type="script",
                provider="subprocess",
                model=str(script_trace.get("script_name") or "submit_recharge_approval.py"),
                input_snapshot=json.dumps(script_trace, ensure_ascii=False, indent=2)[:4000],
                output_snapshot=_redact_observability_text(output_text[:4000]),
                parsed_payload=script_trace,
                stdout=_redact_observability_text(output_text[:8000]),
                stderr="",
                success=True,
                started_at=started_at,
                finished_at=finished_at,
            )
            if isinstance(http_traces, list):
                for item in http_traces:
                    if not isinstance(item, dict):
                        continue
                    sanitized = _redact_observability_payload(item)
                    endpoint_name = str(sanitized.get("endpoint_name") or "http")
                    success = bool(sanitized.get("success"))
                    now = timezone.now()
                    create_recharge_approval_llm_run(
                        record=self.record,
                        stage="skill_execute",
                        runner_type="skill_http",
                        provider="urllib.request",
                        model=endpoint_name,
                        input_snapshot=json.dumps(
                            sanitized.get("request_preview", {}),
                            ensure_ascii=False,
                            indent=2,
                        )[:4000],
                        output_snapshot=json.dumps(
                            sanitized.get("response_preview", {}),
                            ensure_ascii=False,
                            indent=2,
                        )[:4000],
                        parsed_payload={
                            **sanitized,
                            "parent_tool_run_id": key,
                        },
                        stdout=json.dumps(
                            sanitized.get("response_preview", {}),
                            ensure_ascii=False,
                        )[:8000],
                        stderr=str(sanitized.get("error") or ""),
                        success=success,
                        error_message=str(sanitized.get("error") or ""),
                        started_at=now,
                        finished_at=now,
                    )
            create_recharge_approval_event(
                record=self.record,
                event_type="skill_script_completed",
                stage="skill_execute",
                source="run_skill_script",
                message="Skill script execution completed.",
                payload={"run_id": key, "http_trace_count": len(http_traces) if isinstance(http_traces, list) else 0},
            )
            if observation is not None and self.langfuse_runtime is not None:
                self.langfuse_runtime.end_observation(
                    observation,
                    output=output_text[:4000],
                    metadata={"tool_name": tool_name, "http_trace_count": len(http_traces) if isinstance(http_traces, list) else 0},
                )
                safe_flush = getattr(self.langfuse_runtime, "safe_flush", None)
                if callable(safe_flush):
                    safe_flush()

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id,
        **kwargs: Any,
    ) -> Any:
        key = str(run_id)
        start_info = self._tool_starts.pop(key, {})
        started_at = start_info.get("started_at") or timezone.now()
        finished_at = timezone.now()
        input_str = start_info.get("input", "")
        tool_name = str((kwargs.get("serialized") or {}).get("name") or "")
        observation = self._tool_observations.pop(key, None)

        error_text = str(error)

        if tool_name == "feishu_http_request":
            error_text = str(error)
            create_recharge_approval_llm_run(
                record=self.record,
                stage="skill_execute",
                runner_type="skill_http",
                provider="agent_runner",
                model="",
                input_snapshot=input_str[:2000],
                output_snapshot="",
                parsed_payload={},
                stdout="",
                stderr=error_text,
                success=False,
                error_message=error_text,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=max(
                    0, int((finished_at - started_at).total_seconds() * 1000)
                ),
            )
            create_recharge_approval_event(
                record=self.record,
                event_type="skill_http_failed",
                stage="skill_execute",
                source=tool_name,
                message=error_text,
                payload={
                    "run_id": key,
                    "error": error_text,
                },
            )
            if observation is not None and self.langfuse_runtime is not None:
                self.langfuse_runtime.end_observation(
                    observation,
                    level="ERROR",
                    status_message=error_text,
                    metadata={"tool_name": tool_name},
                )
                safe_flush = getattr(self.langfuse_runtime, "safe_flush", None)
                if callable(safe_flush):
                    safe_flush()
        elif tool_name == "submit_recharge_approval_via_script":
            if observation is not None and self.langfuse_runtime is not None:
                self.langfuse_runtime.end_observation(
                    observation,
                    level="ERROR",
                    status_message=error_text,
                    metadata={"tool_name": tool_name},
                )
                safe_flush = getattr(self.langfuse_runtime, "safe_flush", None)
                if callable(safe_flush):
                    safe_flush()
def build_deep_agent_model(user_id: Optional[int] = None):
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import AzureChatOpenAI, ChatOpenAI

    llm_settings = resolve_parser_llm_settings(None)
    provider = str(llm_settings.get("provider") or "openai").strip().lower()
    model_name = str(llm_settings.get("model") or "").strip()
    if not model_name:
        raise ValueError("LLM config is missing model.")
    api_key = llm_settings.get("api_key") or ""
    api_base = llm_settings.get("api_base") or ""

    if provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            base_url=api_base or None,
            temperature=0,
        )
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0,
        )
    if provider == "azure_openai":
        return AzureChatOpenAI(
            model=model_name,
            azure_deployment=model_name,
            api_key=api_key,
            azure_endpoint=api_base,
            api_version="2024-02-01",
            temperature=0,
        )
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base or None,
        temperature=0,
    )


# Removed (moved to cloud_billing.agents.recharge_approval.definition):
#   @tool submit_recharge_approval_via_script,
#   prepare_recharge_skill_script_environment,
#   prepare_recharge_skill_script_invocation,
#   _request_file_arg

# Canonical RechargeApprovalAgentRunner moved to
# cloud_billing.agents.recharge_approval.definition. It uses explicit
# plan/execute workflow tools so the request JSON is materialized before the
# Feishu submission script runs.
# execute_recharge_approval_agent() below delegates there.
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
    from cloud_billing.agents.recharge_approval.definition import (
        execute_recharge_approval_agent as execute_agent_definition,
    )

    return execute_agent_definition(
        record=record,
        raw_recharge_info=raw_recharge_info,
        user_id=user_id,
        source_task_id=source_task_id,
        submitter_identifier=submitter_identifier,
        submitter_user_label=submitter_user_label,
        resolved_submitter_user_id=resolved_submitter_user_id,
    )


def parse_recharge_info(raw_recharge_info: str) -> Dict[str, Any]:
    """
    Parse provider recharge info.

    Accept JSON or newline-delimited key/value text.
    """
    text = str(raw_recharge_info or "").strip()
    if not text:
        raise ValueError("Recharge info is empty.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = _parse_key_value_text(text)

    if not isinstance(payload, dict):
        raise ValueError("Recharge info must resolve to an object.")
    if not payload:
        raise ValueError("Recharge info did not contain recognizable fields.")
    return sanitize_recharge_request_payload(
        normalize_recharge_request_fields(payload)
    )


def _split_amount_and_currency(value: Any) -> tuple[Any, str]:
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


def _parse_key_value_text(text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    payee: Dict[str, Any] = {}
    lines = [
        raw_line.strip()
        for raw_line in text.splitlines()
        if raw_line.strip() and not raw_line.strip().startswith("#")
    ]

    index = 0
    while index < len(lines):
        line = lines[index]
        if "：" in line:
            key, value = line.split("：", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            normalized_candidate = RECHARGE_INFO_KEY_MAP.get(line.strip())
            if not normalized_candidate:
                index += 1
                continue
            key = line
            value = ""
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if RECHARGE_INFO_KEY_MAP.get(candidate):
                    break
                value = candidate
                break
            index = lookahead

        normalized_key = RECHARGE_INFO_KEY_MAP.get(key.strip(), key.strip())
        cleaned_value = value.strip()
        if not cleaned_value:
            index += 1
            continue

        if normalized_key.startswith("payee."):
            payee_key = normalized_key.split(".", 1)[1]
            if payee_key == "account_number":
                cleaned_value = "".join(cleaned_value.split())
            payee[payee_key] = cleaned_value
        elif normalized_key == "amount":
            amount_value, currency = _split_amount_and_currency(cleaned_value)
            payload[normalized_key] = amount_value
            if currency and not str(payload.get("currency") or "").strip():
                payload["currency"] = currency
        elif normalized_key == "currency":
            payload[normalized_key] = str(cleaned_value).strip().upper()
        else:
            payload[normalized_key] = cleaned_value
        index += 1

    if payee:
        payload["payee"] = payee
    if payload and ("currency" not in payload or not str(payload.get("currency") or "").strip()):
        payload["currency"] = "CNY"
    return payload


def normalize_feishu_status(status: Optional[str]) -> str:
    normalized = str(status or "").strip().upper()
    return FEISHU_STATUS_MAP.get(
        normalized, RechargeApprovalRecord.STATUS_SUBMITTED
    )


def extract_recharge_account_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(
        payload.get("recharge_account")
        or payload.get("充值云账号")
        or ""
    ).strip()


def extract_recharge_account_from_record(record: RechargeApprovalRecord) -> str:
    account = extract_recharge_account_from_payload(record.request_payload)
    if account:
        return account
    account = extract_recharge_account_from_payload(record.context_payload)
    if account:
        return account
    account = extract_recharge_account_from_payload(record.response_payload)
    if account:
        return account
    account = extract_recharge_account_from_payload(record.callback_payload)
    if account:
        return account
    try:
        payload = parse_recharge_info(record.raw_recharge_info)
    except Exception:
        return ""
    return extract_recharge_account_from_payload(payload)


def snapshot_username(user: Optional[User]) -> str:
    if not user:
        return ""
    return str(getattr(user, "username", "") or "").strip()


# Canonical RechargeApprovalAgentRunner moved to cloud_billing.agents.recharge_approval.definition.
# Tests importing from services.recharge_approval should update to import from definition.py.

ONGOING_RECHARGE_APPROVAL_STATUSES = {
    RechargeApprovalRecord.STATUS_PENDING,
    RechargeApprovalRecord.STATUS_SUBMITTED,
}
PENDING_FEISHU_TASK_STATUSES = {
    "PENDING",
    "APPROVING",
    "IN_PROGRESS",
    "TODO",
    "WAITING",
}


def extract_pending_approval_targets(
    detail: Any,
) -> List[Dict[str, str]]:
    """Extract current Feishu approvers and merge duplicate users."""
    if not isinstance(detail, dict):
        return []
    data = detail.get("data") or detail.get("event") or detail
    if not isinstance(data, dict):
        return []
    tasks = data.get("task_list") or data.get("tasks") or []
    if not isinstance(tasks, list):
        return []

    targets_by_user: Dict[str, Dict[str, str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = str(
            task.get("status") or task.get("task_status") or ""
        ).strip().upper()
        if status not in PENDING_FEISHU_TASK_STATUSES:
            continue
        raw_user_ids = (
            task.get("user_ids")
            or task.get("assignee_ids")
            or task.get("user_id")
            or task.get("assignee_id")
            or []
        )
        if not isinstance(raw_user_ids, list):
            raw_user_ids = [raw_user_ids]
        node_id = str(
            task.get("node_id") or task.get("node_code") or ""
        ).strip()
        node_name = str(
            task.get("node_name")
            or task.get("name")
            or node_id
            or "待审批"
        ).strip()
        task_id = str(task.get("task_id") or task.get("id") or "").strip()
        for raw_user_id in raw_user_ids:
            user_id = str(raw_user_id or "").strip()
            if not user_id:
                continue
            target = targets_by_user.get(user_id)
            if target is None:
                targets_by_user[user_id] = {
                    "user_id": user_id,
                    "node_id": node_id,
                    "node_name": node_name,
                    "task_id": task_id,
                }
                continue
            existing_names = [
                value.strip()
                for value in target["node_name"].split("/")
                if value.strip()
            ]
            if node_name not in existing_names:
                target["node_name"] = (
                    f"{target['node_name']} / {node_name}"
                )

    return list(targets_by_user.values())


def _decimal_or_none(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _build_recharge_recovery_evidence(
    record: RechargeApprovalRecord,
    *,
    recharge_account: str,
    current_balance: Optional[Decimal],
    current_days_remaining: Optional[int],
    observed_at,
) -> Optional[dict[str, Any]]:
    alert_record = record.alert_record
    context = record.context_payload or {}
    alert_type = str(
        getattr(alert_record, "alert_type", "")
        or context.get("alert_type")
        or ""
    ).strip()
    evidence = {
        "recharge_account": recharge_account,
        "observed_at": observed_at.isoformat(),
    }
    balance_threshold_value = getattr(
        alert_record,
        "balance_threshold",
        None,
    )
    if balance_threshold_value is None:
        balance_threshold_value = context.get("balance_threshold")
    balance_threshold = _decimal_or_none(balance_threshold_value)
    baseline_balance_value = context.get("last_observed_balance")
    if baseline_balance_value is None:
        baseline_balance_value = getattr(
            alert_record,
            "current_balance",
            None,
        )
    if baseline_balance_value is None:
        baseline_balance_value = context.get("current_balance")
    baseline_balance = _decimal_or_none(baseline_balance_value)
    balance_was_triggered = balance_threshold is not None and (
        alert_type == AlertRecord.ALERT_TYPE_BALANCE
        or (
            baseline_balance is not None
            and baseline_balance < balance_threshold
        )
    )

    days_threshold_value = getattr(
        alert_record,
        "days_remaining_threshold",
        None,
    )
    if days_threshold_value is None:
        days_threshold_value = context.get("days_remaining_threshold")
    baseline_days_value = getattr(
        alert_record,
        "current_days_remaining",
        None,
    )
    if baseline_days_value is None:
        baseline_days_value = context.get("current_days_remaining")
    try:
        days_threshold = int(days_threshold_value)
    except (TypeError, ValueError):
        days_threshold = None
    try:
        baseline_days = int(baseline_days_value)
    except (TypeError, ValueError):
        baseline_days = None
    days_was_triggered = days_threshold is not None and (
        alert_type == AlertRecord.ALERT_TYPE_DAYS_REMAINING
        or (
            baseline_days is not None
            and baseline_days < days_threshold
        )
    )

    signal_details = []
    balance_increase_detected = (
        current_balance is not None
        and baseline_balance is not None
        and current_balance > baseline_balance
    )
    if balance_was_triggered:
        balance_threshold_recovered = (
            current_balance is not None
            and current_balance >= balance_threshold
        )
        if not (
            balance_increase_detected
            or balance_threshold_recovered
        ):
            return None
        balance_details = {
            "baseline_balance": (
                str(baseline_balance)
                if baseline_balance is not None
                else ""
            ),
            "observed_balance": str(current_balance),
            "threshold": str(balance_threshold),
        }
        if baseline_balance is not None:
            estimated_recharge_amount = (
                current_balance - baseline_balance
            )
            if estimated_recharge_amount > 0:
                balance_details["estimated_recharge_amount"] = str(
                    estimated_recharge_amount
                )
        signal_details.append(
            (
                (
                    "balance_threshold_recovered"
                    if balance_threshold_recovered
                    else "positive_balance_change_detected"
                ),
                balance_details,
            )
        )
    if (
        days_was_triggered
        and balance_increase_detected
        and not balance_was_triggered
    ):
        estimated_recharge_amount = current_balance - baseline_balance
        signal_details.append(
            (
                "positive_balance_change_detected",
                {
                    "baseline_balance": str(baseline_balance),
                    "observed_balance": str(current_balance),
                    "estimated_recharge_amount": str(
                        estimated_recharge_amount
                    ),
                },
            )
        )
    if days_was_triggered:
        if (
            current_days_remaining is None
            or current_days_remaining < days_threshold
        ):
            if not balance_increase_detected:
                return None
        else:
            days_evidence = {
                "baseline_days_remaining": (
                    baseline_days if baseline_days is not None else ""
                ),
                "observed_days_remaining": current_days_remaining,
                "threshold": days_threshold,
            }
            if current_balance is not None:
                days_evidence["observed_balance"] = str(
                    current_balance
                )
            signal_details.append(
                (
                    "days_remaining_threshold_recovered",
                    days_evidence,
                )
            )
    if not signal_details:
        return None
    for signal, details in signal_details:
        if details.get("estimated_recharge_amount"):
            evidence["estimated_recharge_amount"] = details[
                "estimated_recharge_amount"
            ]
            break
    if len(signal_details) == 1:
        signal, details = signal_details[0]
        evidence["signal"] = signal
        evidence.update(details)
        return evidence

    evidence["signal"] = "all_triggered_health_signals_recovered"
    evidence["signals"] = [signal for signal, _details in signal_details]
    evidence["signal_details"] = {
        signal: details for signal, details in signal_details
    }
    return evidence


def reconcile_recharge_approvals_for_account(
    *,
    provider: CloudProvider,
    recharge_account: str,
    current_balance: Optional[Decimal],
    current_days_remaining: Optional[int],
    observed_at=None,
    allow_provider_fallback: bool = False,
) -> list[dict[str, Any]]:
    """Reconcile ongoing auto approvals against recovered account health."""
    recharge_account = str(recharge_account or "").strip()
    if not recharge_account and not allow_provider_fallback:
        return []
    observed_at = observed_at or timezone.now()
    records = RechargeApprovalRecord.objects.select_related(
        "alert_record"
    ).filter(
        provider=provider,
        trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_ALERT,
        status__in=ONGOING_RECHARGE_APPROVAL_STATUSES,
        fulfillment_status=RechargeApprovalRecord.FULFILLMENT_PENDING,
    )
    results = []
    for record in records:
        context = record.context_payload or {}
        billing_account_id = str(
            context.get("billing_account_id") or ""
        ).strip()
        configured_recharge_account = extract_recharge_account_from_record(
            record
        )
        account_matches = (
            billing_account_id == recharge_account
            if billing_account_id
            else configured_recharge_account == recharge_account
        )
        if not account_matches and not (
            allow_provider_fallback
            and not billing_account_id
            and not configured_recharge_account
        ):
            continue

        evidence = _build_recharge_recovery_evidence(
            record,
            recharge_account=recharge_account,
            current_balance=current_balance,
            current_days_remaining=current_days_remaining,
            observed_at=observed_at,
        )
        if evidence is None:
            if current_balance is not None:
                last_observed_balance = _decimal_or_none(
                    context.get("last_observed_balance")
                )
                if (
                    "last_observed_balance" not in context
                    or last_observed_balance != current_balance
                ):
                    context = dict(context)
                    context["last_observed_balance"] = str(
                        current_balance
                    )
                    context["last_balance_observed_at"] = (
                        observed_at.isoformat()
                    )
                    record.context_payload = context
                    record.save(
                        update_fields=["context_payload", "updated_at"]
                    )
            continue
        record.fulfillment_status = (
            RechargeApprovalRecord.FULFILLMENT_RECOVERED
        )
        record.fulfilled_at = observed_at
        record.fulfillment_evidence = evidence
        record.latest_stage = "fulfillment_recovered"
        record.save(
            update_fields=[
                "fulfillment_status",
                "fulfilled_at",
                "fulfillment_evidence",
                "latest_stage",
                "updated_at",
            ]
        )
        create_recharge_approval_event(
            record=record,
            event_type="recharge_fulfillment_recovered",
            stage="fulfillment_recovered",
            source="billing_balance",
            message=(
                "Recharge objective recovered; the approval remains active "
                "and no longer blocks a new submission."
            ),
            payload=evidence,
        )
        results.append(
            {
                "record_id": record.id,
                "recovered": True,
                "submission_block_released": True,
                "balance_recovery_detected": bool(
                    evidence.get("estimated_recharge_amount")
                ),
            }
        )
    return results


def find_ongoing_recharge_approval_for_account(
    *,
    provider: CloudProvider,
    recharge_account: str,
    allow_provider_fallback: bool = False,
) -> Optional[RechargeApprovalRecord]:
    recharge_account = str(recharge_account or "").strip()
    if not recharge_account and not allow_provider_fallback:
        return None

    queryset = RechargeApprovalRecord.objects.filter(
        provider=provider,
        status__in=ONGOING_RECHARGE_APPROVAL_STATUSES,
        fulfillment_status=RechargeApprovalRecord.FULFILLMENT_PENDING,
    ).order_by("-submitted_at", "-updated_at", "-created_at")
    for record in queryset:
        billing_account_id = str(
            (record.context_payload or {}).get("billing_account_id") or ""
        ).strip()
        configured_recharge_account = extract_recharge_account_from_record(
            record
        )
        account_matches = bool(recharge_account) and (
            billing_account_id == recharge_account
            or configured_recharge_account == recharge_account
        )
        fallback_matches = (
            allow_provider_fallback
            and not billing_account_id
            and not configured_recharge_account
        )
        if account_matches or fallback_matches:
            return record
    return None


def find_recovered_recharge_approval_for_account(
    *,
    provider: CloudProvider,
    recharge_account: str,
) -> Optional[RechargeApprovalRecord]:
    records = find_recovered_recharge_approvals_for_account(
        provider=provider,
        recharge_account=recharge_account,
    )
    return records[0] if records else None


def find_recovered_recharge_approvals_for_account(
    *,
    provider: CloudProvider,
    recharge_account: str,
) -> List[RechargeApprovalRecord]:
    recharge_account = str(recharge_account or "").strip()
    if not recharge_account:
        return []

    queryset = RechargeApprovalRecord.objects.filter(
        provider=provider,
        status__in=ONGOING_RECHARGE_APPROVAL_STATUSES,
        fulfillment_status=RechargeApprovalRecord.FULFILLMENT_RECOVERED,
    ).order_by("-submitted_at", "-updated_at", "-created_at")
    return [
        record
        for record in queryset
        if extract_recharge_account_from_record(record) == recharge_account
    ]


def refresh_recharge_approval_record_status(
    record: RechargeApprovalRecord,
    *,
    approval_base_url: str = FEISHU_APPROVAL_BASE_URL,
) -> dict[str, Any]:
    """
    Refresh a recharge approval record against Feishu live status.

    Returns a dict with:
    - is_ongoing: whether the live instance is still in progress
    - live_status: normalized live status
    - live_status_text: raw status text from Feishu, when available
    - detail: raw Feishu detail payload, when available
    """
    approval_code = str(record.feishu_approval_code or "").strip()
    instance_code = str(record.feishu_instance_code or "").strip()
    if not approval_code or not instance_code:
        return {
            "is_ongoing": record.status in ONGOING_RECHARGE_APPROVAL_STATUSES,
            "live_status": record.status,
            "live_status_text": record.status_message or "",
            "detail": None,
        }

    token = _get_feishu_access_token()
    if not token:
        return {
            "is_ongoing": record.status in ONGOING_RECHARGE_APPROVAL_STATUSES,
            "live_status": record.status,
            "live_status_text": record.status_message or "",
            "detail": None,
        }

    detail = _feishu_get_instance(
        token,
        approval_code,
        instance_code,
        approval_base_url=approval_base_url,
    )
    if not detail:
        return {
            "is_ongoing": record.status in ONGOING_RECHARGE_APPROVAL_STATUSES,
            "live_status": record.status,
            "live_status_text": record.status_message or "",
            "detail": None,
        }

    data = detail.get("data") or {}
    cloud_type = _extract_cloud_type_from_instance_data(data)
    live_status_text = str(
        data.get("status") or data.get("approval_status") or ""
    ).strip()
    normalized_status = normalize_feishu_status(live_status_text)
    timeline = data.get("timeline") or data.get("approval_timeline") or []
    if normalized_status in ONGOING_RECHARGE_APPROVAL_STATUSES:
        update_fields = []
        if record.status != normalized_status:
            record.status = normalized_status
            update_fields.append("status")
        if live_status_text and record.status_message != live_status_text:
            record.status_message = live_status_text
            update_fields.append("status_message")
        if isinstance(timeline, list) and record.approval_timeline != timeline:
            record.approval_timeline = timeline
            update_fields.append("approval_timeline")
        if update_fields:
            record.latest_stage = "status_check"
            update_fields.extend(["latest_stage", "updated_at"])
            record.save(update_fields=update_fields)
        return {
            "is_ongoing": True,
            "live_status": normalized_status,
            "live_status_text": live_status_text,
            "detail": detail,
        }

    latest_node_name = ""
    latest_node_status = ""
    if isinstance(timeline, list) and timeline:
        latest_node = timeline[-1]
        if isinstance(latest_node, dict):
            latest_node_name = str(
                latest_node.get("node_name")
                or latest_node.get("name")
                or latest_node.get("type")
                or ""
            ).strip()
            latest_node_status = str(
                latest_node.get("status")
                or latest_node.get("type")
                or live_status_text
            ).strip()

    callback_payload = dict(detail)
    if cloud_type:
        callback_payload["cloud_type"] = cloud_type
    if isinstance(data, dict):
        callback_data = dict(data)
        if cloud_type:
            callback_data["cloud_type"] = cloud_type
        callback_payload["data"] = callback_data

    update_fields = {
        "status": normalized_status,
        "status_message": live_status_text or record.status_message,
        "latest_stage": "status_check",
        "callback_payload": callback_payload,
        "last_callback_at": timezone.now(),
    }
    if isinstance(timeline, list):
        update_fields["approval_timeline"] = timeline
    if latest_node_name:
        update_fields["latest_node_name"] = latest_node_name
    if latest_node_status:
        update_fields["latest_node_status"] = latest_node_status

    for field_name, value in update_fields.items():
        setattr(record, field_name, value)
    record.save(
        update_fields=list(update_fields.keys()) + ["updated_at"],
    )
    return {
        "is_ongoing": False,
        "live_status": normalized_status,
        "live_status_text": live_status_text,
        "detail": detail,
    }


def get_pending_recharge_approval_targets(
    record: RechargeApprovalRecord,
) -> List[Dict[str, str]]:
    """Load the live instance and return its current pending approvers."""
    refresh_result = refresh_recharge_approval_record_status(record)
    if not refresh_result.get("is_ongoing"):
        return []

    live_detail = refresh_result.get("detail")
    live_data = (
        live_detail.get("data")
        if isinstance(live_detail, dict)
        else None
    )
    if not isinstance(live_data, dict) and isinstance(live_detail, dict):
        live_data = live_detail
    if isinstance(live_data, dict) and any(
        key in live_data for key in ("task_list", "tasks")
    ):
        return extract_pending_approval_targets(live_detail)

    candidates = [
        record.callback_payload,
        record.response_payload,
    ]
    for candidate in candidates:
        targets = extract_pending_approval_targets(candidate)
        if targets:
            return targets
    return []


def _approval_progress_status(statuses: List[str]) -> str:
    """Collapse multiple task statuses into one node status."""
    normalized = {
        str(status or "").strip().upper()
        for status in statuses
        if str(status or "").strip()
    }
    if normalized & PENDING_FEISHU_TASK_STATUSES:
        return "PENDING"
    for status in (
        "REJECTED",
        "TRANSFERRED",
    ):
        if status in normalized:
            return status
    if normalized and normalized <= {"APPROVED", "DONE"}:
        return "APPROVED"
    return next(iter(normalized), "NOT_STARTED")


def _extract_approval_progress_nodes(detail: Any) -> list[dict[str, Any]]:
    """Normalize and group task entries from an approval instance."""
    if not isinstance(detail, dict):
        return []
    data = detail.get("data") or detail.get("event") or detail
    if not isinstance(data, dict):
        return []
    tasks = data.get("task_list") or data.get("tasks") or []
    if not isinstance(tasks, list):
        return []

    nodes_by_id: dict[str, dict[str, Any]] = {}
    node_statuses: dict[str, List[str]] = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        node_id = str(
            task.get("node_id")
            or task.get("node_code")
            or f"task-{index}"
        ).strip()
        node = nodes_by_id.get(node_id)
        if node is None:
            node = {
                "node_id": node_id,
                "node_name": str(
                    task.get("node_name")
                    or task.get("name")
                    or "待审批"
                ).strip(),
                "status": "NOT_STARTED",
                "user_ids": [],
                "start_time": str(
                    task.get("start_time") or ""
                ).strip(),
                "end_time": str(
                    task.get("end_time") or ""
                ).strip(),
            }
            nodes_by_id[node_id] = node
            node_statuses[node_id] = []
        raw_user_ids = (
            task.get("user_ids")
            or task.get("assignee_ids")
            or task.get("user_id")
            or task.get("assignee_id")
            or []
        )
        if not isinstance(raw_user_ids, list):
            raw_user_ids = [raw_user_ids]
        for raw_user_id in raw_user_ids:
            user_id = str(raw_user_id or "").strip()
            if user_id and user_id not in node["user_ids"]:
                node["user_ids"].append(user_id)
        node_statuses[node_id].append(
            str(
                task.get("status")
                or task.get("task_status")
                or ""
            )
        )
        end_time = str(task.get("end_time") or "").strip()
        if end_time and end_time != "0":
            node["end_time"] = end_time

    for node_id, node in nodes_by_id.items():
        node["status"] = _approval_progress_status(
            node_statuses[node_id]
        )
    return list(nodes_by_id.values())


def _append_preview_approval_nodes(
    nodes: list[dict[str, Any]],
    preview: Any,
) -> None:
    """Append future approval nodes without duplicating active tasks."""
    if not isinstance(preview, dict):
        return
    data = preview.get("data") or preview
    if not isinstance(data, dict):
        return
    preview_nodes = data.get("preview_nodes") or []
    if not isinstance(preview_nodes, list):
        return
    existing_node_ids = {
        str(node.get("node_id") or "").strip() for node in nodes
    }
    for index, raw_node in enumerate(preview_nodes):
        if not isinstance(raw_node, dict):
            continue
        user_ids = raw_node.get("user_id_list") or []
        if not isinstance(user_ids, list):
            user_ids = [user_ids]
        normalized_user_ids = [
            str(user_id or "").strip()
            for user_id in user_ids
            if str(user_id or "").strip()
        ]
        node_type = str(raw_node.get("node_type") or "").strip()
        if not node_type and not normalized_user_ids:
            continue
        node_id = str(
            raw_node.get("node_id") or f"preview-{index}"
        ).strip()
        if node_id in existing_node_ids:
            continue
        existing_node_ids.add(node_id)
        nodes.append(
            {
                "node_id": node_id,
                "node_name": str(
                    raw_node.get("node_name") or "待审批"
                ).strip(),
                "status": "NOT_STARTED",
                "user_ids": normalized_user_ids,
                "start_time": "",
                "end_time": "",
            }
        )


def get_recharge_approval_progress(
    record: RechargeApprovalRecord,
) -> list[dict[str, Any]]:
    """Return handled, active, and previewed approval nodes."""
    refresh_result = refresh_recharge_approval_record_status(record)
    detail = refresh_result.get("detail")
    if not isinstance(detail, dict):
        for candidate in (
            record.callback_payload,
            record.response_payload,
        ):
            if isinstance(candidate, dict):
                detail = candidate
                break
    nodes = _extract_approval_progress_nodes(detail)

    data = detail.get("data") if isinstance(detail, dict) else None
    if not isinstance(data, dict) and isinstance(detail, dict):
        data = detail
    nodes.sort(
        key=lambda node: (
            _history_sort_key(node.get("start_time")) == 0,
            _history_sort_key(node.get("start_time")),
        )
    )
    tasks = data.get("task_list") if isinstance(data, dict) else []
    pending_task = next(
        (
            task
            for task in tasks or []
            if isinstance(task, dict)
            and str(task.get("status") or "").strip().upper()
            in PENDING_FEISHU_TASK_STATUSES
        ),
        None,
    )
    instance_code = str(
        getattr(record, "feishu_instance_code", "") or ""
    ).strip()
    if pending_task and instance_code:
        task_id = str(
            pending_task.get("id")
            or pending_task.get("task_id")
            or ""
        ).strip()
        user_id = str(
            pending_task.get("user_id")
            or pending_task.get("assignee_id")
            or ""
        ).strip()
        token = _get_feishu_access_token()
        if token and task_id and user_id:
            preview = _feishu_preview_instance(
                token,
                instance_code,
                task_id,
                user_id,
            )
            _append_preview_approval_nodes(nodes, preview)

    try:
        users = list_feishu_users()
    except Exception:
        logger.warning(
            "Could not resolve approval progress user names",
            exc_info=True,
        )
        users = []
    names_by_user_id = {
        str(user.get("user_id") or "").strip(): str(
            user.get("display_name") or user.get("name") or ""
        ).strip()
        for user in users
        if isinstance(user, dict)
        and str(user.get("user_id") or "").strip()
    }
    progress = [
        {
            "node_id": node["node_id"],
            "node_name": node["node_name"],
            "status": node["status"],
            "approver_names": [
                names_by_user_id[user_id]
                for user_id in node["user_ids"]
                if names_by_user_id.get(user_id)
            ],
            "start_time": node["start_time"],
            "end_time": node["end_time"],
        }
        for node in nodes
    ]
    instance_start_time = str(
        (data or {}).get("start_time") or ""
    ).strip()
    submitter_name = str(
        getattr(record, "submitter_user_label", "") or ""
    ).strip()
    if not submitter_name:
        submitter_user_id = str(
            (data or {}).get("user_id") or ""
        ).strip()
        submitter_name = names_by_user_id.get(submitter_user_id, "")
    progress.insert(
        0,
        {
            "node_id": "__start__",
            "node_name": "发起",
            "node_kind": "start",
            "status": "APPROVED",
            "approver_names": (
                [submitter_name] if submitter_name else []
            ),
            "start_time": instance_start_time,
            "end_time": instance_start_time,
        },
    )

    instance_status = str(
        (data or {}).get("status") or "PENDING"
    ).strip().upper()
    end_statuses = {
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "CANCELED": "CANCELED",
        "CANCELLED": "CANCELED",
        "DELETED": "CANCELED",
    }
    instance_end_time = str(
        (data or {}).get("end_time") or ""
    ).strip()
    if instance_end_time == "0":
        instance_end_time = ""
    progress.append(
        {
            "node_id": "__end__",
            "node_name": "结束",
            "node_kind": "end",
            "status": end_statuses.get(
                instance_status,
                "NOT_STARTED",
            ),
            "approver_names": [],
            "start_time": instance_end_time,
            "end_time": instance_end_time,
        }
    )
    return progress


def find_ongoing_recharge_approval_for_submitter(
    *,
    provider: CloudProvider,
    submitter_identifier: str = "",
    resolved_submitter_user_id: str = "",
) -> Optional[RechargeApprovalRecord]:
    """
    Return the newest ongoing recharge approval for the same submitter.

    A submitter matches when either the resolved Feishu user_id or the raw
    submitter identifier matches a pending/submitted approval record.
    """
    queryset = RechargeApprovalRecord.objects.filter(
        provider=provider,
        status__in=ONGOING_RECHARGE_APPROVAL_STATUSES,
    )
    match = Q()
    if resolved_submitter_user_id:
        match |= Q(resolved_submitter_user_id=resolved_submitter_user_id)
    if submitter_identifier:
        match |= Q(submitter_identifier=submitter_identifier)
    if not match:
        return None
    return queryset.filter(match).order_by(
        "-submitted_at",
        "-updated_at",
        "-created_at",
    ).first()


def resolve_submitter_identity(
    *,
    provider_config: Optional[Dict[str, Any]],
    explicit_identifier: str = "",
    explicit_user_id: str = "",
    explicit_label: str = "",
) -> Tuple[str, str, str]:
    approval_cfg = (provider_config or {}).get("recharge_approval") or {}
    identifier = str(
        explicit_identifier
        or approval_cfg.get("submitter_identifier")
        or approval_cfg.get("submitter_email")
        or approval_cfg.get("submitter_mobile")
        or approval_cfg.get("submitter_contact")
        or approval_cfg.get("identifier")
        or ""
    ).strip()
    label = str(
        explicit_label
        or approval_cfg.get("submitter_user_label")
        or approval_cfg.get("submitter_name")
        or ""
    ).strip()

    logger.info(
        "Resolve submitter identity:\n"
        "  identifier: %s\n"
        "  label: %s\n"
        "  explicit_identifier: %s\n"
        "  explicit_user_id: %s\n"
        "  source: provider_config.recharge_approval",
        identifier or "(not set)",
        label or "(not set)",
        explicit_identifier or "(not set)",
        explicit_user_id or "(not set)",
    )

    resolved_user_id = str(
        explicit_user_id
        or approval_cfg.get("resolved_submitter_user_id")
        or approval_cfg.get("submitter_user_id")
        or approval_cfg.get("user_id")
        or ""
    ).strip()
    resolved_user_name = ""

    if identifier:
        access_token = _get_feishu_access_token()
        resolved_identity = _resolve_user_id_by_email_or_mobile(
            identifier,
            access_token or "",
        )
        if resolved_identity:
            resolved_lookup_user_id, resolved_user_name = resolved_identity
            if not resolved_user_id:
                resolved_user_id = resolved_lookup_user_id

    if not resolved_user_id:
        resolved_user_id = os.getenv("FEISHU_USER_ID", "").strip()

    if resolved_user_id:
        logger.info(
            "Submitter user_id found in config: %s",
            resolved_user_id[:10] + "***" if len(resolved_user_id) > 10 else resolved_user_id
        )
    else:
        logger.warning(
            "Cannot resolve submitter: no user_id provided or configured"
        )

    logger.info(
        "Submitter identity resolved:\n"
        "  identifier: %s\n"
        "  label: %s\n"
        "  user_name: %s\n"
        "  resolved_user_id: %s",
        identifier or "(not set)",
        label or "(not set)",
        resolved_user_name or "(not set)",
        (
            resolved_user_id[:10] + "***"
            if resolved_user_id and len(resolved_user_id) > 10
            else (resolved_user_id or "(not set)")
        ),
    )

    return identifier, (resolved_user_name or label), resolved_user_id


def create_recharge_approval_event(
    *,
    record: RechargeApprovalRecord,
    event_type: str,
    stage: str = "",
    source: str = "",
    message: str = "",
    payload: Optional[Dict[str, Any]] = None,
    operator: Optional[User] = None,
    operator_label: str = "",
) -> RechargeApprovalEvent:
    return RechargeApprovalEvent.objects.create(
        record=record,
        trace_id=record.trace_id,
        event_type=event_type,
        stage=stage,
        source=source,
        message=message,
        payload=payload or {},
        operator=operator,
        operator_label=operator_label or snapshot_username(operator),
    )


def create_recharge_approval_llm_run(
    *,
    record: RechargeApprovalRecord,
    stage: str,
    runner_type: str,
    provider: str = "",
    model: str = "",
    input_snapshot: str = "",
    output_snapshot: str = "",
    parsed_payload: Optional[Dict[str, Any]] = None,
    usage_payload: Optional[Dict[str, Any]] = None,
    stdout: str = "",
    stderr: str = "",
    success: bool = True,
    error_message: str = "",
    llm_usage_id=None,
    parent_span_id=None,
    started_at=None,
    finished_at=None,
    latency_ms=None,
):
    if latency_ms is None and started_at and finished_at:
        latency_ms = max(
            0,
            int((finished_at - started_at).total_seconds() * 1000),
        )

    run = RechargeApprovalLLMRun.objects.create(
        record=record,
        trace_id=record.trace_id,
        parent_span_id=parent_span_id,
        runner_type=runner_type,
        stage=stage,
        llm_usage_id=llm_usage_id,
        provider=provider,
        model=model,
        input_snapshot=input_snapshot,
        output_snapshot=output_snapshot,
        parsed_payload=parsed_payload or {},
        usage_payload=usage_payload or {},
        stdout=stdout,
        stderr=stderr,
        success=success,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=latency_ms,
    )
    record.latest_stage = stage
    record.last_latency_ms = latency_ms
    record.llm_trace_summary = {
        "runner_type": runner_type,
        "provider": provider,
        "model": model,
        "success": success,
        "error_message": error_message,
        "latency_ms": latency_ms,
        "stage": stage,
    }
    if llm_usage_id:
        record.latest_llm_usage_id = llm_usage_id
    record.save(
        update_fields=[
            "latest_stage",
            "last_latency_ms",
            "llm_trace_summary",
            "latest_llm_usage",
            "updated_at",
        ],
    )
    return run


def is_complete_recharge_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in RECHARGE_REQUIRED_FIELDS:
        value = payload.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
    payee = payload.get("payee")
    if not isinstance(payee, dict):
        return False
    for key in PAYEE_REQUIRED_FIELDS:
        value = payee.get(key)
        if value is None or (isinstance(value, str) and not str(value).strip()):
            return False
    return True


def build_llm_parse_messages(raw_recharge_info: str) -> list[dict[str, str]]:
    schema_hint = {
        "cloud_type": "string",
        "payment_type": "string, optional, default 仅充值",
        "recharge_customer_name": "string",
        "recharge_account": "string",
        "payment_way": "string, optional, default 公司支付",
        "payment_company": "string",
        "remit_method": "string, optional, default 转账",
        "amount": "number",
        "currency": "string, optional, default CNY",
        "payment_note": "string, optional",
        "expected_date": "YYYY-MM-DD, optional",
        "remark": "string, optional",
        "payee": {
            "type": "string",
            "account_name": "string",
            "account_number": "string",
            "bank_name": "string",
            "bank_region": "string",
            "bank_branch": "string",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You extract recharge approval fields from user-provided text. "
                "Return only one JSON object. Keep unknown fields empty strings "
                "instead of inventing values. Preserve original account numbers "
                "and names exactly. Split amount and currency into separate "
                "fields; amount should be numeric and currency should be a "
                "short code such as CNY."
            ),
        },
        {
            "role": "user",
            "content": (
                "Convert the following recharge information into a JSON object "
                "that matches this schema:\n"
                f"{json.dumps(schema_hint, ensure_ascii=False)}\n\n"
                "Input text:\n"
                f"{raw_recharge_info}"
            ),
        },
    ]


def latest_usage_for_trace(
    *,
    trace_id,
    record_id: int,
    stage: str,
    user_id: Optional[int],
) -> Optional[LLMUsage]:
    from agentcore_metering.adapters.django.models import LLMUsage

    queryset = LLMUsage.objects.filter(
        metadata__trace_id=str(trace_id),
        metadata__source_record_id=record_id,
        metadata__stage=stage,
    )
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    return queryset.order_by("-created_at").first()


def parse_recharge_info_with_tracking(
    *,
    raw_recharge_info: str,
    record: RechargeApprovalRecord,
    user_id: Optional[int] = None,
    source_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse recharge info and record execution evidence.

    Try JSON/key-value parsing first. If required fields are still missing,
    fall back to agentcore metering LLM tracking.
    """
    started_at = timezone.now()
    raw_text = str(raw_recharge_info or "").strip()
    parsed_from_json = False
    try:
        candidate = json.loads(raw_text)
        parsed_from_json = isinstance(candidate, dict)
    except json.JSONDecodeError:
        parsed_from_json = False
    try:
        payload = parse_recharge_info(raw_recharge_info)
    except ValueError:
        payload = {}
    if parsed_from_json or is_complete_recharge_payload(payload):
        finished_at = timezone.now()
        create_recharge_approval_llm_run(
            record=record,
            stage="parse_input",
            runner_type="agent",
            provider="local-parser",
            model="heuristic-parser",
            input_snapshot=raw_recharge_info,
            output_snapshot=json.dumps(payload, ensure_ascii=False),
            parsed_payload=payload,
            success=True,
            started_at=started_at,
            finished_at=finished_at,
        )
        create_recharge_approval_event(
            record=record,
            event_type="parse_completed",
            stage="parse_input",
            source="agent",
            message="Recharge info parsed by heuristic parser.",
            payload=payload,
        )
        return payload

    from cloud_billing.tracked_llm import (
        build_tracking_state,
        invoke_tracked_structured_llm,
    )

    llm_state = {
        **build_tracking_state(
            record_id=record.id,
            trace_id=str(record.trace_id),
            node_name="parse_input",
            source_task_id=source_task_id or "",
            user_id=user_id,
        )
    }
    llm_started_at = timezone.now()
    parsed_model, usage, llm_settings = invoke_tracked_structured_llm(
        schema=RechargeApprovalParsedPayload,
        messages=build_llm_parse_messages(raw_recharge_info),
        preferred_config_uuid=None,
        node_name="parse_input",
        state=llm_state,
    )
    llm_finished_at = timezone.now()
    parsed_payload = parsed_model.model_dump()
    usage_row = latest_usage_for_trace(
        trace_id=record.trace_id,
        record_id=record.id,
        stage="parse_input",
        user_id=user_id,
    )
    create_recharge_approval_llm_run(
        record=record,
        stage="parse_input",
        runner_type="llm",
        provider=str(llm_settings.get("provider") or "agentcore_metering"),
        model=str(usage.get("model") or llm_settings.get("model") or ""),
        input_snapshot=raw_recharge_info,
        output_snapshot=json.dumps(parsed_payload, ensure_ascii=False),
        parsed_payload=parsed_payload,
        usage_payload=usage,
        llm_usage_id=getattr(usage_row, "id", None),
        success=True,
        started_at=llm_started_at,
        finished_at=llm_finished_at,
    )
    create_recharge_approval_event(
        record=record,
        event_type="parse_completed",
        stage="parse_input",
        source="llm",
        message="Recharge info parsed by LLM.",
        payload=parsed_payload,
    )
    return parsed_payload
