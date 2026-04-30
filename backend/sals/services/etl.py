"""
ETL: 从远程 OneProCloud API 加载工单数据，清洗后写入 Django 数据库。
API 为默认主数据源，Excel 仅作为无 API 凭证时的备用。
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.db import transaction

from ..models import Company, Incident, User

logger = logging.getLogger(__name__)

SLA_MAP = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}

EXCEL_PATH = os.getenv("EXCEL_PATH", "")

API_BASE_URL = os.getenv("ONEPRO_API_BASE_URL", "https://support.oneprocloud.com")
API_USERNAME = os.getenv("ONEPRO_USERNAME", "")
API_PASSWORD = os.getenv("ONEPRO_PASSWORD", "")
API_SYNC_LIMIT = int(os.getenv("API_SYNC_LIMIT", "500"))

_STATE_MAP = {
    1: "New",
    2: "In Progress",
    3: "On Hold",
    4: "Resolved",
    5: "Closed",
    6: "Canceled",
    7: "Pending",
}


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
    if v is None:
        return "Unknown"
    try:
        return _STATE_MAP.get(int(v), "Unknown")
    except (TypeError, ValueError):
        return str(v)


def login_api() -> Optional[str]:
    bearer = os.getenv("ONEPRO_BEARER_TOKEN", "").strip()
    if bearer:
        logger.info("Using pre-configured Bearer token")
        return bearer

    if not API_USERNAME or not API_PASSWORD:
        logger.warning("No API credentials configured")
        return None

    url = f"{API_BASE_URL}/api/hyper/auth/login"
    payload = {
        "user_name": API_USERNAME,
        "user_password": API_PASSWORD,
        "auth_type": "glide.local.authentication",
        "preferred_language": "zh",
    }
    try:
        resp = requests.post(url, json=payload, timeout=30, verify=False)
        if resp.status_code == 200:
            body = resp.json()
            token = body.get("token") or resp.headers.get("X-Subject-Token")
            if token:
                logger.info("API login successful")
                return token
            user_sys_id = body.get("data", {}).get("user_info", {}).get("user_sys_id")
            if user_sys_id:
                logger.warning("Login succeeded but no JWT, using user_sys_id")
                return user_sys_id
            logger.error("Login succeeded but no token found")
            return None
        else:
            logger.error("API login failed: %s %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("API login exception: %s", e)
        return None


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    }


def fetch_incidents_from_api(token: str, limit: int = 200) -> List[Dict[str, Any]]:
    headers = _build_headers(token)
    all_records: List[Dict[str, Any]] = []
    batch_size = min(200, limit)
    offset = 0

    while len(all_records) < limit:
        remaining = limit - len(all_records)
        params = {
            "sysparm_limit": min(batch_size, remaining),
            "sysparm_offset": offset,
            "sysparm_display_value": "true",
        }
        url = f"{API_BASE_URL}/api/hyper/table/incident"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
        except Exception as e:
            logger.error("Request exception at offset %s: %s", offset, e)
            break

        if resp.status_code != 200:
            logger.error("API request failed [%s]: %s", resp.status_code, resp.text[:300])
            break

        body = resp.json()
        records = body.get("data", [])
        if not records:
            break

        for raw in records:
            if not isinstance(raw, dict):
                continue
            data_map = raw.get("record_data_map", raw)
            group_name = (
                data_map.get("assignment_group_special_name")
                or data_map.get("assignment_group")
            )
            assignee_name = (
                data_map.get("assigned_to_special_name")
                or data_map.get("assigned_to")
            )
            mapped = {
                "number": data_map.get("number") or raw.get("number"),
                "short_description": data_map.get("short_description"),
                "priority": data_map.get("priority"),
                "state": _fmt_state(data_map.get("state")),
                "category": data_map.get("category"),
                "assignment_group": group_name,
                "assigned_to": assignee_name,
                "company": data_map.get("company_special_name") or data_map.get("company"),
                "caller": (
                    data_map.get("caller_id_special_name")
                    or data_map.get("u_caller_special_name")
                ),
                "sys_created_on": data_map.get("sys_created_on"),
                "sys_updated_on": data_map.get("sys_updated_on"),
                "sys_created_by": data_map.get("sys_created_by"),
                "sys_updated_by": data_map.get("sys_updated_by"),
                "parent_incident": data_map.get("parent"),
                "resolution_code": data_map.get("close_code"),
            }
            mapped = {k: v for k, v in mapped.items() if v is not None}
            if mapped.get("number"):
                all_records.append(mapped)

        logger.info("Fetched %s records (offset=%s)", len(all_records), offset)
        offset += batch_size
        if len(records) < batch_size:
            break

    return all_records[:limit]


def fetch_companies_from_api(token: str) -> List[Dict[str, Any]]:
    headers = _build_headers(token)
    all_records: List[Dict[str, Any]] = []
    batch_size = 200
    offset = 0

    while True:
        params = {
            "sysparm_limit": min(500, batch_size),
            "sysparm_offset": offset,
            "sysparm_display_value": "true",
        }
        url = f"{API_BASE_URL}/api/hyper/table/core_company"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
        except Exception as e:
            logger.error("Company API request exception at offset %s: %s", offset, e)
            break

        if resp.status_code != 200:
            logger.error("Company API request failed [%s]: %s", resp.status_code, resp.text[:300])
            break

        body = resp.json()
        records = body.get("data", [])
        if not records:
            break

        for raw in records:
            data_map = raw.get("record_data_map", raw)
            sys_id = data_map.get("sys_id") or raw.get("sys_id")
            if not sys_id:
                continue
            all_records.append({
                "sys_id": str(sys_id),
                "name": data_map.get("name") or raw.get("name"),
            })

        logger.info("Fetched %s company records (offset=%s)", len(all_records), offset)
        offset += batch_size
        if len(records) < batch_size:
            break

    return all_records


def fetch_users_from_api(token: str, limit: int = 500) -> List[Dict[str, Any]]:
    headers = _build_headers(token)
    all_records: List[Dict[str, Any]] = []
    batch_size = 200
    offset = 0

    while len(all_records) < limit:
        params = {
            "sysparm_limit": min(200, limit - len(all_records)),
            "sysparm_offset": offset,
        }
        url = "https://support.oneprocloud.com/api/hyper/table/sys_user"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
        except Exception as e:
            logger.error("User API request exception at offset %s: %s", offset, e)
            break

        if resp.status_code != 200:
            logger.error("User API request failed [%s]: %s", resp.status_code, resp.text[:300])
            break

        body = resp.json()
        records = body.get("data", [])
        if not records:
            break

        for raw in records:
            if not isinstance(raw, dict):
                continue
            data_map = raw.get("record_data_map", raw)
            sys_id = data_map.get("sys_id") or raw.get("sys_id")
            if not sys_id:
                continue
            all_records.append({
                "sys_id": str(sys_id),
                "name": data_map.get("name") or raw.get("name"),
                "email": data_map.get("email") or raw.get("email"),
                "user_name": data_map.get("user_name") or raw.get("user_name"),
                "department": data_map.get("department") or raw.get("department"),
                "phone": data_map.get("phone") or raw.get("phone"),
                "mobile_phone": data_map.get("mobile_phone") or raw.get("mobile_phone"),
                "title": data_map.get("title") or raw.get("title"),
                "active": data_map.get("active") or raw.get("active"),
            })

        logger.info("Fetched %s user records (offset=%s)", len(all_records), offset)
        offset += batch_size
        if len(records) < batch_size:
            break
        if len(all_records) >= limit:
            break

    return all_records[:limit]


def _parse_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except Exception:
            pass
    try:
        ts = int(str(value)[:10])
        return datetime.utcfromtimestamp(ts)
    except Exception:
        pass
    return datetime.utcnow()


def _derive_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    created = _parse_datetime(row.get("sys_created_on"))
    updated = _parse_datetime(row.get("sys_updated_on"))
    resolve_hours = max(0.0, (updated - created).total_seconds() / 3600)
    priority = _fmt_priority(row.get("priority"))
    sla_limit = SLA_MAP.get(priority, 24)
    is_sla_met = resolve_hours <= sla_limit
    return {
        "resolve_hours": round(resolve_hours, 2),
        "sla_limit": sla_limit,
        "is_sla_met": is_sla_met,
        "month": created.strftime("%Y-%m"),
        "weekday": created.strftime("%A"),
        "hour": created.hour,
    }


def _record_to_dict(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not raw.get("number"):
        return None
    derived = _derive_fields(raw)
    return {
        "number": str(raw.get("number", "")),
        "parent_incident": str(raw.get("parent_incident", "") or "") or None,
        "short_description": str(raw.get("short_description", "") or "") or None,
        "company": str(raw.get("company", "") or "未知"),
        "caller": str(raw.get("caller", "") or "未知"),
        "created_by": str(raw.get("sys_created_by", "") or ""),
        "priority": _fmt_priority(raw.get("priority")),
        "assigned_to": str(raw.get("assigned_to", "") or "") or None,
        "state": _fmt_state(raw.get("state")),
        "resolution_code": str(raw.get("resolution_code", "") or "") or None,
        "category": str(raw.get("category", "") or "未知"),
        "assignment_group": str(raw.get("assignment_group", "") or "未分配"),
        "updated_by": str(raw.get("sys_updated_by", "") or "") or None,
        "created_at": _parse_datetime(raw.get("sys_created_on")),
        "updated_at": _parse_datetime(raw.get("sys_updated_on")),
        **derived,
    }


def sync_companies_from_api() -> Dict[str, Any]:
    token = login_api()
    if not token:
        return {"status": "error", "message": "API 认证失败"}

    records = fetch_companies_from_api(token)
    if not records:
        return {"status": "error", "message": "API 未返回任何公司记录"}

    added = 0
    skipped = 0
    with transaction.atomic():
        for row in records:
            sys_id = str(row.get("sys_id", "")).strip()
            if not sys_id:
                skipped += 1
                continue
            _, created = Company.objects.get_or_create(
                sys_id=sys_id,
                defaults={"name": str(row.get("name", "") or "") or None},
            )
            if created:
                added += 1
            else:
                skipped += 1

    total = Company.objects.count()
    logger.info("Company sync done: added=%s, skipped=%s, total=%s", added, skipped, total)
    return {"status": "ok", "added": added, "skipped": skipped, "total": total}


def sync_users_from_api() -> Dict[str, Any]:
    token = login_api()
    if not token:
        return {"status": "error", "message": "API 认证失败"}

    records = fetch_users_from_api(token)
    if not records:
        return {"status": "error", "message": "API 未返回任何用户记录"}

    added = 0
    skipped = 0
    seen_sys_ids: set = set()
    with transaction.atomic():
        for row in records:
            sys_id = str(row.get("sys_id", "")).strip()
            if not sys_id or sys_id in seen_sys_ids:
                skipped += 1
                continue
            seen_sys_ids.add(sys_id)
            _, created = User.objects.get_or_create(
                sys_id=sys_id,
                defaults={
                    "name": str(row.get("name", "") or "") or None,
                    "email": str(row.get("email", "") or "") or None,
                    "user_name": str(row.get("user_name", "") or "") or None,
                    "department": str(row.get("department", "") or "") or None,
                    "phone": str(row.get("phone", "") or "") or None,
                    "mobile_phone": str(row.get("mobile_phone", "") or "") or None,
                    "title": str(row.get("title", "") or "") or None,
                    "active": str(row.get("active", "") or "") or None,
                },
            )
            if created:
                added += 1
            else:
                skipped += 1

    total = User.objects.count()
    logger.info("User sync done: added=%s, skipped=%s, total=%s", added, skipped, total)
    return {"status": "ok", "added": added, "skipped": skipped, "total": total}


def sync_from_api(full_sync: bool = True) -> Dict[str, Any]:
    token = login_api()
    if not token:
        return {
            "status": "error",
            "message": "API 认证失败，请检查 ONEPRO_BEARER_TOKEN 或 ONEPRO_USERNAME/PASSWORD 环境变量",
        }

    limit = API_SYNC_LIMIT
    records = fetch_incidents_from_api(token, limit=limit)
    if not records:
        return {"status": "error", "message": "API 未返回任何记录"}

    # 先同步公司映射表
    sync_companies_result = sync_companies_from_api()
    logger.info("Company sync result: %s", sync_companies_result)

    # 构建 sys_id -> name 映射
    company_map: Dict[str, str] = {
        c.sys_id: c.name or c.sys_id
        for c in Company.objects.all()
        if c.sys_id
    }

    mapped = []
    for raw in records:
        co_sys_id = raw.get("company") or ""
        raw["company"] = company_map.get(co_sys_id, co_sys_id)
        m = _record_to_dict(raw)
        if m:
            mapped.append(m)

    with transaction.atomic():
        if full_sync:
            Incident.objects.all().delete()
            logger.info("Old incidents deleted (full sync)")

        for row in mapped:
            defaults = {k: v for k, v in row.items() if k != "number"}
            _, created = Incident.objects.update_or_create(
                number=row["number"],
                defaults=defaults,
            )

    total = Incident.objects.count()
    logger.info("Incident sync done: processed=%s, total=%s", len(mapped), total)

    user_result = sync_users_from_api()
    return {
        "status": "ok",
        "synced": len(mapped),
        "total": total,
        "mode": "full" if full_sync else "incremental",
        "users": user_result,
    }
