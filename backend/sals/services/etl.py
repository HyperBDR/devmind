"""
ETL: 从远程 OneProCloud API 加载工单数据，清洗后写入 Django 数据库。
API 为默认主数据源，Excel 仅作为无 API 凭证时的备用。
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.db import transaction

from ..models import Company, Incident, User

logger = logging.getLogger(__name__)

SLA_MAP = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}

EXCEL_PATH = os.getenv("EXCEL_PATH", "")

# Companies excluded from API query (not synced to DB)
# 逗号分隔的公司名称列表，如 "BOG,测试公司"
EXCLUDED_COMPANY_NAMES = [
    name.strip()
    for name in os.getenv("SUPPORT_EXCLUDED_COMPANIES", "").split(",")
    if name.strip()
]

API_BASE_URL = os.getenv("ONEPRO_API_BASE_URL", "https://support.oneprocloud.com")
API_USERNAME = os.getenv("ONEPRO_USERNAME", "")
API_PASSWORD = os.getenv("ONEPRO_PASSWORD", "")
API_SYNC_LIMIT = int(os.getenv("API_SYNC_LIMIT", "500"))

_STATE_MAP = {
    1: "New",
    2: "In Progress",
    3: "On Hold",
    4: "Closed",
    5: "Closed",
    6: "Resolved",
    7: "Pending",
    8: "Canceled",
}

# Reverse lookup: display values (any locale) → state code
_STATE_DISPLAY_TO_CODE: Dict[str, int] = {}
for _code, _name in _STATE_MAP.items():
    _STATE_DISPLAY_TO_CODE[_name.lower()] = _code
# Common Chinese display values
_STATE_DISPLAY_TO_CODE.update({
    "新建": 1, "待处理": 1, "新": 1,
    "处理中": 2, "进行中": 2,
    "暂停": 3, "挂起": 3,
    "已关闭": 4, "关闭": 4, "已结束": 5,
    "已解决": 6, "解决": 6,
    "待定": 7, "等待": 7, "挂起中": 7,
    "已取消": 8, "取消": 8,
})


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
    # Numeric code
    try:
        return _STATE_MAP.get(int(v), "Unknown")
    except (TypeError, ValueError):
        pass
    # String: try reverse lookup (handles any locale display value)
    s = str(v).strip().lower()
    code = _STATE_DISPLAY_TO_CODE.get(s)
    if code is not None:
        return _STATE_MAP[code]
    return "Unknown"


def _do_login_with_creds(username: str, password: str, base_url: str) -> Optional[str]:
    url = f"{base_url}/api/hyper/auth/login"
    payload = {
        "user_name": username,
        "user_password": password,
        "auth_type": "glide.local.authentication",
        "preferred_language": "zh",
    }
    try:
        resp = requests.post(url, json=payload, timeout=30, verify=False)
        if resp.status_code == 200:
            body = resp.json()
            token = resp.headers.get("X-Subject-Token") or body.get("token")
            if token:
                logger.info("API login successful")
                return token
            user_sys_id = body.get("data", {}).get("user_info", {}).get("user_sys_id")
            if user_sys_id:
                logger.warning("Login succeeded but no JWT, using user_sys_id: %s", user_sys_id)
                return user_sys_id
            logger.error("Login succeeded but no token found")
            return None
        else:
            logger.error("API login failed: %s %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("API login exception: %s", e)
        return None


def _login_from_collector_config() -> Optional[str]:
    """
    从 data_collector 的 CollectorConfig 读取凭证并登录。
    尝试 after_sales_incident 和 incident 两个平台，取第一个启用且有有效凭证的配置。
    直接复用各 provider 的 _do_login 以确保认证行为一致。
    """
    try:
        from data_collector.models import CollectorConfig
    except ImportError:
        return None

    for platform in ("after_sales_incident", "incident"):
        configs = CollectorConfig.objects.filter(
            platform=platform,
            is_enabled=True,
        ).order_by("id")[:1]
        for config in configs:
            value = config.value or {}
            auth = value.get("auth") or {}
            # 构建与 provider 相同的 auth_config 格式
            auth_config = {**value, **auth}
            # bearer_token 直接优先使用
            bearer_token = (auth.get("bearer_token") or "").strip()
            if bearer_token:
                logger.info(
                    "Using bearer_token from CollectorConfig (platform=%s)",
                    platform,
                )
                return bearer_token
            # 使用 provider 的 _do_login（已验证可用）
            try:
                if platform == "after_sales_incident":
                    from data_collector.services.providers.after_sales_incident import (
                        AfterSalesIncidentProvider,
                    )
                    provider = AfterSalesIncidentProvider()
                    token = provider._do_login(auth_config)
                    if token:
                        logger.info(
                            "Login from CollectorConfig successful (platform=%s)",
                            platform,
                        )
                        return token
            except Exception as exc:
                logger.warning(
                    "Provider login failed for platform=%s: %s",
                    platform,
                    exc,
                )
    return None


def login_api() -> Optional[str]:
    bearer = os.getenv("ONEPRO_BEARER_TOKEN", "").strip()
    if bearer:
        logger.info("Using pre-configured Bearer token")
        return bearer

    if API_USERNAME and API_PASSWORD:
        token = _do_login_with_creds(API_USERNAME, API_PASSWORD, API_BASE_URL)
        if token:
            return token

    token = _login_from_collector_config()
    if token:
        return token

    logger.warning("No API credentials available")
    return None


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    }


def _parse_raw_incident(raw: dict) -> Optional[dict]:
    """Extract structured fields from a single API record."""
    if not isinstance(raw, dict):
        return None
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
        "company": (
            data_map.get("company_special_name")
            or data_map.get("company")
        ),
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
    return mapped if mapped.get("number") else None


def fetch_incidents_from_api(
    token: str,
    limit: Optional[int] = 200,
) -> List[Dict[str, Any]]:
    headers = _build_headers(token)
    all_records: List[Dict[str, Any]] = []
    batch_size = 200
    offset = 0

    # 获取要排除的公司 sys_ids（需要先同步 company）
    excluded_sys_ids = _get_excluded_company_sys_ids()

    def _build_query_param() -> str:
        """Build sysparm_query to exclude specified companies."""
        if not excluded_sys_ids:
            return ""
        query_parts = []
        for sys_id in excluded_sys_ids:
            if sys_id:
                query_parts.append(f"companyNOT LIKE{sys_id}")
        if query_parts:
            return "^".join(query_parts) + "^ORDERBYDESCsys_created_on"
        return ""

    while limit is None or len(all_records) < limit:
        remaining = (
            (limit - len(all_records))
            if limit is not None
            else batch_size
        )
        params = {
            "sysparm_limit": min(batch_size, remaining),
            "sysparm_offset": offset,
            "sysparm_display_value": "true",
        }
        # 添加排除公司的查询条件
        query = _build_query_param()
        if query:
            params["sysparm_query"] = query
        url = f"{API_BASE_URL}/api/hyper/table/incident"
        try:
            resp = requests.get(
                url, headers=headers, params=params,
                timeout=60, verify=False,
            )
        except Exception as e:
            logger.error(
                "Request exception at offset %s: %s", offset, e,
            )
            break

        if resp.status_code != 200:
            logger.error(
                "API request failed [%s]: %s",
                resp.status_code, resp.text[:300],
            )
            break

        body = resp.json()
        records = body.get("data", [])
        if not records:
            break

        for raw in records:
            parsed = _parse_raw_incident(raw)
            if parsed:
                all_records.append(parsed)

        logger.info(
            "Fetched %s records (offset=%s)",
            len(all_records), offset,
        )
        offset += batch_size
        if len(records) < batch_size:
            break

    if limit is not None:
        return all_records[:limit]
    return all_records


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


def sync_companies_from_api(
    token: Optional[str] = None,
) -> Dict[str, Any]:
    if not token:
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


def _get_excluded_company_sys_ids() -> List[str]:
    """Get sys_ids of companies to exclude from sync.
    Reads from EXCLUDED_COMPANY_NAMES (env var) and queries Company table.
    """
    if not EXCLUDED_COMPANY_NAMES:
        return []
    sys_ids = list(
        Company.objects.filter(
            name__in=EXCLUDED_COMPANY_NAMES
        ).values_list("sys_id", flat=True)
    )
    if sys_ids:
        logger.info(
            "Excluding companies from sync: %s (sys_ids: %s)",
            EXCLUDED_COMPANY_NAMES,
            sys_ids,
        )
    else:
        logger.warning(
            "No companies found for exclusion names: %s",
            EXCLUDED_COMPANY_NAMES,
        )
    return sys_ids


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
            "message": (
                "API 认证失败，请检查 "
                "ONEPRO_BEARER_TOKEN 或 "
                "ONEPRO_USERNAME/PASSWORD 环境变量"
            ),
        }

    # 1. 同步公司映射表（写入前需要 company name）
    sync_companies_result = sync_companies_from_api(token)
    logger.info("Company sync result: %s", sync_companies_result)

    company_map: Dict[str, str] = {
        c.sys_id: c.name or c.sys_id
        for c in Company.objects.all()
        if c.sys_id
    }

    # 2. 获取要排除的公司 sys_ids
    excluded_sys_ids = _get_excluded_company_sys_ids()

    # 3. 并发分页拉取 → 清洗 → 写入
    headers = _build_headers(token)
    url = f"{API_BASE_URL}/api/hyper/table/incident"
    batch_size = 200
    concurrency = 4
    total_synced = 0
    limit = None if full_sync else API_SYNC_LIMIT
    offset = 0

    def _build_query_param() -> str:
        """Build sysparm_query to exclude specified companies."""
        if not excluded_sys_ids:
            return ""
        query_parts = []
        for sys_id in excluded_sys_ids:
            if sys_id:
                query_parts.append(f"companyNOT LIKE{sys_id}")
        if query_parts:
            return "^".join(query_parts) + "^ORDERBYDESCsys_created_on"
        return ""

    def _fetch_page(off: int) -> tuple[int, list]:
        """Fetch a single page; returns (offset, records)."""
        try:
            params = {
                "sysparm_limit": batch_size,
                "sysparm_offset": off,
                "sysparm_display_value": "true",
            }
            # 添加排除公司的查询条件
            query = _build_query_param()
            if query:
                params["sysparm_query"] = query
            resp = requests.get(
                url, headers=headers, params=params,
                timeout=60, verify=False,
            )
        except Exception as e:
            logger.error(
                "Request exception offset=%s: %s", off, e,
            )
            return off, []
        if resp.status_code != 200:
            logger.error(
                "API request failed [%s] offset=%s: %s",
                resp.status_code, off, resp.text[:200],
            )
            return off, []
        return off, resp.json().get("data", []) or []

    def _write_batch(records: list) -> tuple[int, set]:
        """Transform and persist one batch.
        Returns (count_written, set_of_numbers)."""
        written = 0
        numbers: set = set()
        with transaction.atomic():
            for raw in records:
                parsed = _parse_raw_incident(raw)
                if not parsed:
                    continue
                co_sys_id = parsed.get("company") or ""
                company_name = company_map.get(co_sys_id, co_sys_id)
                parsed["company"] = company_name
                row = _record_to_dict(parsed)
                if not row:
                    continue
                numbers.add(row["number"])
                defaults = {
                    k: v for k, v in row.items()
                    if k != "number"
                }
                Incident.objects.update_or_create(
                    number=row["number"],
                    defaults=defaults,
                )
                written += 1
        return written, numbers

    # 全量模式：先写新数据，成功后再删旧数据
    # 记录同步前的旧 number 集合
    old_numbers: set = set()
    if full_sync:
        old_numbers = set(
            Incident.objects.values_list("number", flat=True)
        )

    synced_numbers: set = set()
    done = False
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while not done:
            wave_offsets = [
                offset + i * batch_size
                for i in range(concurrency)
            ]
            if not wave_offsets:
                break

            futures = {
                pool.submit(_fetch_page, off): off
                for off in wave_offsets
            }

            results: dict[int, list] = {}
            for future in as_completed(futures):
                off, records = future.result()
                results[off] = records

            for off in sorted(results):
                records = results[off]
                if not records:
                    done = True
                    break
                written, numbers = _write_batch(records)
                total_synced += written
                synced_numbers |= numbers
                logger.info(
                    "Batch done: offset=%s "
                    "written=%s total=%s",
                    off, written, total_synced,
                )
                if len(records) < batch_size:
                    done = True
                    break

                # 增量模式到达 limit 时停止
                if limit is not None and total_synced >= limit:
                    done = True
                    break

            offset += concurrency * batch_size

    # 全量模式：删除本次同步未覆盖的旧记录
    if full_sync and synced_numbers:
        stale = old_numbers - synced_numbers
        if stale:
            deleted, _ = Incident.objects.filter(
                number__in=stale,
            ).delete()
            logger.info(
                "Removed %s stale incidents", deleted,
            )

    total = Incident.objects.count()
    logger.info(
        "Incident sync done: synced=%s, total=%s",
        total_synced, total,
    )

    user_result = sync_users_from_api()
    return {
        "status": "ok",
        "synced": total_synced,
        "total": total,
        "mode": "full" if full_sync else "incremental",
        "users": user_result,
    }
