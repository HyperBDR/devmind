"""
OneProCloud After-Sales Work Order (售后工单) provider.

Authentication: base_url + username + password; or bearer_token directly.
POST /api/hyper/auth/login to obtain Bearer token.
Table API: GET /api/hyper/table/{table_name} with pagination.

Expected auth_config:
{
    "base_url": "https://support.oneprocloud.com",   # optional, env fallback
    "username": "...",
    "password": "...",
    "bearer_token": "...",     # optional, takes precedence over username/password
    "table_name": "after_sale_incident",  # optional, defaults to after_sale_incident
}
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from .base import BaseProvider

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://support.oneprocloud.com"
DEFAULT_TABLE_NAME = "after_sale_incident"
REQUEST_TIMEOUT = 60
BATCH_SIZE = 200
# Default SLA thresholds per priority
SLA_MAP = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}


# ── Token 缓存 ─────────────────────────────────────
_token_cache: dict = {}


def _jwt_exp(token: str) -> Optional[int]:
    """从 JWT 中解析 exp 字段（unix 秒），解析失败返回 None"""
    try:
        payload_b64 = token.split(".")[1]
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += "=" * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("exp")
    except Exception:
        return None


def _is_token_valid(token: str) -> bool:
    """检查 token 是否有效（提前 5 分钟视为过期）"""
    exp = _jwt_exp(token)
    if exp is None:
        return True  # 无法解析时保守返回有效，依赖 401 触发刷新
    now = datetime.now(timezone.utc).timestamp()
    return now < (exp - 300)


def _fmt_priority(v: Any) -> str:
    try:
        n = int(v)
        return {1: "P1", 2: "P2", 3: "P3", 4: "P4"}.get(n, "P3")
    except (TypeError, ValueError):
        s = str(v).strip().upper()
        if s.startswith("P") and len(s) <= 3:
            return s
        return "P3"


def _fmt_state(v: Any) -> str:
    state_map = {
        1: "New",
        2: "In Progress",
        3: "On Hold",
        4: "Resolved",
        5: "Closed",
        6: "Canceled",
        7: "Pending",
    }
    if v is None:
        return "Unknown"
    try:
        return state_map.get(int(v), "Unknown")
    except (TypeError, ValueError):
        return str(v)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except Exception:
            pass
    try:
        ts = int(str(value)[:10])
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    return None


class AfterSalesIncidentProvider(BaseProvider):
    """
    OneProCloud After-Sales Work Order data collection provider.

    Collects records from the OneProCloud ITSM table API and returns items
    in the standard collector format.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._base_url: str = DEFAULT_BASE_URL
        self._table_name: str = DEFAULT_TABLE_NAME

    def _resolve_config(self, auth_config: dict) -> tuple[str, str, str]:
        base_url = (
            auth_config.get("base_url")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        token = (auth_config.get("bearer_token") or "").strip()
        table_name = (auth_config.get("table_name") or DEFAULT_TABLE_NAME).strip()
        return base_url, token, table_name

    def _do_login(self, auth_config: dict) -> str | None:
        username = (auth_config.get("username") or "").strip()
        password = auth_config.get("password") or ""
        if not username or not password:
            return None
        url = f"{self._base_url}/api/hyper/auth/login"
        payload = {
            "user_name": username,
            "user_password": password,
            "auth_type": "glide.local.authentication",
            "preferred_language": "zh",
        }
        logger.info("[Login] 请求 body: %s", payload)
        try:
            resp = requests.post(url, json=payload, timeout=30, verify=False)
            if resp.status_code == 200:
                body = resp.json()
                token = (
                    body.get("token")
                    or body.get("data", {}).get("token")
                    or resp.headers.get("X-Subject-Token")
                )
                if token:
                    logger.info("AfterSalesIncidentProvider login successful, token obtained")
                    return token
                resp_text = resp.text
                token_in_body = "token" in resp_text
                logger.warning(
                    "Login succeeded but no JWT or X-Subject-Token (token in body: %s): %s",
                    token_in_body,
                    resp_text[:500],
                )
                return None
            logger.warning("Login failed: %s %s", resp.status_code, resp.text[:500])
            return None
        except Exception as e:
            logger.warning("Login exception: %s", e)
            return None

    def _ensure_token(self, auth_config: dict, force_refresh: bool = False) -> str | None:
        if not force_refresh and self._token and _is_token_valid(self._token):
            return self._token
        # Try direct bearer token first
        _, token, _ = self._resolve_config(auth_config)
        if token and (force_refresh or not _is_token_valid(token)):
            # bearer token 已过期或强制刷新，走登录
            token = None
        if token:
            self._token = token
            return token
        # Fall back to login
        self._token = self._do_login(auth_config)
        return self._token
        return self._token

    def _build_headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36"
            ),
        }

    def _record_to_item(self, raw: dict, table_name: str) -> dict | None:
        data_map = raw.get("record_data_map", raw)
        number = data_map.get("number") or raw.get("number")
        if not number:
            return None

        created_str = data_map.get("sys_created_on") or raw.get("sys_created_on")
        updated_str = data_map.get("sys_updated_on") or raw.get("sys_updated_on")
        source_created_at = _parse_datetime(created_str)
        source_updated_at = _parse_datetime(updated_str)

        priority = _fmt_priority(data_map.get("priority"))
        sla_limit = SLA_MAP.get(priority, 24)
        if source_created_at and source_updated_at:
            resolve_seconds = (source_updated_at - source_created_at).total_seconds()
            resolve_hours = max(0.0, resolve_seconds / 3600)
            is_sla_met = resolve_hours <= sla_limit
        else:
            resolve_hours = None
            is_sla_met = None

        group_name = (
            data_map.get("assignment_group_special_name")
            or data_map.get("assignment_group")
        )
        assignee_name = (
            data_map.get("assigned_to_special_name")
            or data_map.get("assigned_to")
        )
        company_name = (
            data_map.get("company_special_name")
            or data_map.get("company")
        )
        caller_name = (
            data_map.get("caller_id_special_name")
            or data_map.get("u_caller_special_name")
        )

        raw_data = {
            "table_name": table_name,
            "record": data_map,
            "_derived": {
                "resolve_hours": round(resolve_hours, 2) if resolve_hours is not None else None,
                "sla_limit": sla_limit,
                "is_sla_met": is_sla_met,
                "priority_formatted": priority,
                "state_formatted": _fmt_state(data_map.get("state")),
            },
        }
        payload_str = json.dumps(raw_data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        filter_metadata = {
            "priority": priority,
            "state": _fmt_state(data_map.get("state")),
            "category": data_map.get("category"),
            "assignment_group": group_name,
            "company": company_name,
        }

        return {
            "source_unique_id": str(number),
            "raw_data": raw_data,
            "filter_metadata": filter_metadata,
            "data_hash": data_hash,
            "source_created_at": source_created_at,
            "source_updated_at": source_updated_at,
        }

    # ---------- BaseProvider implementation ----------

    def authenticate(self, auth_config: dict) -> bool:
        """Verify OneProCloud credentials via login endpoint."""
        if not auth_config:
            return False
        self._base_url, _, self._table_name = self._resolve_config(auth_config)
        token = self._ensure_token(auth_config)
        if not token:
            return False
        # Quick smoke-test: try fetching with the token
        url = f"{self._base_url}/api/hyper/table/{self._table_name}"
        params = {"sysparm_limit": 1, "sysparm_offset": 0}
        try:
            resp = requests.get(
                url,
                headers=self._build_headers(token),
                params=params,
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                logger.info("AfterSalesIncidentProvider authenticate: success")
                return True
            if resp.status_code == 401:
                logger.warning(
                    "AfterSalesIncidentProvider authenticate: 收到 401，尝试重新登录..."
                )
                new_token = self._ensure_token(auth_config, force_refresh=True)
                if new_token:
                    resp = requests.get(
                        url,
                        headers=self._build_headers(new_token),
                        params=params,
                        timeout=30,
                        verify=False,
                    )
                    if resp.status_code == 200:
                        logger.info("AfterSalesIncidentProvider authenticate: success (刷新后)")
                        return True
                    logger.warning(
                        "AfterSalesIncidentProvider authenticate failed after refresh: %s %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                return False
            logger.warning(
                "AfterSalesIncidentProvider authenticate failed: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
        except Exception as e:
            logger.warning("AfterSalesIncidentProvider authenticate exception: %s", e)
            return False

    def collect(
        self,
        auth_config: dict,
        start_time,
        end_time,
        user_id: int,
        platform: str,
        **kwargs,
    ) -> list[dict]:
        """
        Fetch after-sales work order records from OneProCloud table API.
        Returns list of collector items.
        """
        self._base_url, _, self._table_name = self._resolve_config(auth_config)
        token = self._ensure_token(auth_config)
        if not token:
            logger.warning("AfterSalesIncidentProvider.collect: no token, returning []")
            return []

        headers = self._build_headers(token)
        url = f"{self._base_url}/api/hyper/table/{self._table_name}"
        out: list[dict] = []
        offset = 0

        while True:
            params = {
                "sysparm_limit": BATCH_SIZE,
                "sysparm_offset": offset,
                "sysparm_display_value": "true",
            }
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    verify=False,
                )
            except Exception as e:
                logger.warning(
                    "AfterSalesIncidentProvider.collect request failed at offset %s: %s",
                    offset,
                    e,
                )
                break

            if resp.status_code == 401:
                logger.warning(
                    "AfterSalesIncidentProvider.collect: 收到 401，Token 可能已过期，尝试重新登录..."
                )
                new_token = self._ensure_token(auth_config, force_refresh=True)
                if new_token:
                    headers = self._build_headers(new_token)
                    logger.info("AfterSalesIncidentProvider.collect: Token 已刷新，重试当前批次")
                    continue
                logger.warning("AfterSalesIncidentProvider.collect: Token 刷新失败，停止拉取")
                break
            if resp.status_code != 200:
                logger.warning(
                    "AfterSalesIncidentProvider.collect API failed [%s]: %s",
                    resp.status_code,
                    resp.text[:300],
                )
                break

            body = resp.json()
            records = body.get("data", [])
            if not records:
                break

            for raw in records:
                if not isinstance(raw, dict):
                    continue
                item = self._record_to_item(raw, self._table_name)
                if item:
                    out.append(item)

            logger.info(
                "AfterSalesIncidentProvider.collect offset=%s fetched=%s total=%s",
                offset,
                len(records),
                len(out),
            )
            offset += BATCH_SIZE
            if len(records) < BATCH_SIZE:
                break

        logger.info(
            "AfterSalesIncidentProvider.collect done, returning %s items",
            len(out),
        )
        return out

    def validate(
        self,
        auth_config: dict,
        start_time,
        end_time,
        user_id: int,
        platform: str,
        source_unique_ids: list[str],
    ) -> list[str]:
        """
        Check which work order numbers no longer exist on the platform.
        Returns list of missing ids.
        """
        if not source_unique_ids:
            return []
        self._base_url, _, self._table_name = self._resolve_config(auth_config)
        token = self._ensure_token(auth_config)
        if not token:
            return []

        missing: list[str] = []
        headers = self._build_headers(token)
        url = f"{self._base_url}/api/hyper/table/{self._table_name}"

        for sid in source_unique_ids:
            params = {
                "sysparm_limit": 1,
                "sysparm_query": f"number={sid}",
            }
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30,
                    verify=False,
                )
                if resp.status_code != 200:
                    missing.append(sid)
                    continue
                body = resp.json()
                records = body.get("data", [])
                found = any(
                    r.get("record_data_map", r).get("number") == sid
                    or r.get("number") == sid
                    for r in records
                )
                if not found:
                    missing.append(sid)
            except Exception:
                missing.append(sid)

        if missing:
            logger.info(
                "AfterSalesIncidentProvider.validate: %s missing out of %s",
                len(missing),
                len(source_unique_ids),
            )
        return missing

    def fetch_attachments(
        self,
        auth_config: dict,
        raw_record,
    ) -> list[dict]:
        """After-sales work order records do not have attachments."""
        return []

    def download_attachment_content(
        self,
        auth_config: dict,
        attachment_meta: dict,
    ) -> bytes | None:
        """No attachment download for this platform."""
        return None
