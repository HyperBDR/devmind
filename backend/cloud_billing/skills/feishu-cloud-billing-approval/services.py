"""Feishu recharge approval skill capability layer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _submit_module():
    script = Path(__file__).resolve().parent / "scripts" / "submit_recharge_approval.py"
    spec = importlib.util.spec_from_file_location("feishu_recharge_submit_service", script)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load submit recharge approval script: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_tenant_access_token(app_id: str, app_secret: str, auth_base_url: str) -> str:
    return _submit_module().get_tenant_access_token(app_id, app_secret, auth_base_url)


def resolve_submitter_user_id(auth_base_url: str, token: str, identifier: str) -> str:
    return _submit_module()._resolve_user_id(auth_base_url, token, identifier)


def get_approval_definition(base_url: str, token: str, approval_code: str) -> dict[str, Any]:
    return _submit_module().get_approval_definition(base_url, token, approval_code)


def list_approval_instances(
    base_url: str,
    token: str,
    approval_code: str,
    start_time_ms: int,
    end_time_ms: int,
    limit: int = 100,
) -> dict[str, Any]:
    return _submit_module().list_instances(
        base_url,
        token,
        approval_code,
        start_time_ms,
        end_time_ms,
        limit=limit,
    )


def get_approval_instance(
    base_url: str,
    token: str,
    approval_code: str,
    instance_code: str,
) -> dict[str, Any]:
    return _submit_module().get_instance(base_url, token, approval_code, instance_code)


def infer_recharge_request_from_history(
    base_url: str,
    token: str,
    approval_code: str,
    cloud_type: str,
    recharge_account: str,
    lookback_days: int,
    limit: int,
) -> dict[str, Any]:
    return _submit_module().find_historical_recharge_request(
        base_url,
        token,
        approval_code,
        cloud_type,
        recharge_account,
        lookback_days,
        limit,
    )


def inspect_pending_recharge_approval(
    base_url: str,
    token: str,
    approval_code: str,
    request_data: dict[str, Any],
    lookback_days: int,
) -> dict[str, Any]:
    return _submit_module().inspect_recharge_account_state(
        base_url,
        token,
        approval_code,
        request_data,
        lookback_days,
    )


def submit_recharge_approval_instance(
    base_url: str,
    token: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    return _submit_module().create_instance(base_url, token, request_payload)


def validate_recharge_request_payload(request_data: dict[str, Any]) -> None:
    return _submit_module().validate_request(request_data)
