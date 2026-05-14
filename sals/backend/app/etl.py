"""
ETL: 从远程 OneProCloud API 加载工单数据，清洗后写入 SQLite
API 为默认主数据源，Excel 仅作为无 API 凭证时的备用。
"""
import base64
import json
import logging
import os
import pandas as pd
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Incident, Company, User
from app.database import engine, Base, SessionLocal

logger = logging.getLogger(__name__)

# ── SLA 配置 ──────────────────────────────────────
SLA_MAP = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}

# ── 文件路径（仅 Excel 备用模式使用）───────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.getenv("EXCEL_PATH", os.path.join(BASE_DIR, "..", "Incident(2026-04-13+09_31_35).xlsx"))

# ── API 配置（从环境变量读取）──────────────────────
API_BASE_URL = os.getenv("ONEPRO_API_BASE_URL", "https://support.oneprocloud.com")
API_USERNAME = os.getenv("ONEPRO_USERNAME", "")
API_PASSWORD = os.getenv("ONEPRO_PASSWORD", "")
API_SYNC_LIMIT = int(os.getenv("API_SYNC_LIMIT", "500"))  # 每次同步拉取上限

# ── Token 缓存 ─────────────────────────────────────
_token_cache: Dict[str, Any] = {"token": None, "exp": None}  # exp: unix timestamp


def _jwt_exp(token: str) -> Optional[int]:
    """从 JWT 中解析 exp 字段（unix 秒），解析失败返回 None"""
    try:
        payload_b64 = token.split(".")[1]
        # PKCS7 padding
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += "=" * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("exp")
    except Exception:
        return None


def _is_token_valid(token: str) -> bool:
    """检查 token 是否有效（未过期，提前 5 分钟视为过期）"""
    exp = _jwt_exp(token)
    if exp is None:
        return True  # 无法解析时保守返回有效，依赖 401 触发刷新
    now = datetime.now(timezone.utc).timestamp()
    return now < (exp - 300)  # 提前 5 分钟刷新


def _do_login() -> Optional[str]:
    """执行登录请求，返回 token"""
    if not API_USERNAME or not API_PASSWORD:
        print("⚠️  未配置认证信息（ONEPRO_USERNAME/PASSWORD）")
        return None
    url = f"{API_BASE_URL}/api/hyper/auth/login"
    payload = {
        "user_name": API_USERNAME,
        "user_password": API_PASSWORD,
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
                logger.info("[Login] 登录成功，token 已缓存")
                return token
            resp_text = resp.text
            token_in_body = "token" in resp_text
            logger.warning(
                "[Login] 登录成功但无 JWT (token in body: %s): %s",
                token_in_body,
                resp_text[:500],
            )
            return None
        logger.warning("[Login] 登录失败: %s %s", resp.status_code, resp.text[:500])
        return None
    except Exception as e:
        logger.warning("[Login] 登录异常: %s", e)
        return None


def _get_token(force_refresh: bool = False) -> Optional[str]:
    """获取有效 token，force_refresh=True 时强制重新登录"""
    if not force_refresh:
        cached = _token_cache["token"]
        if cached and _is_token_valid(cached):
            return cached
    token = _do_login()
    if token:
        _token_cache["token"] = token
        _token_cache["exp"] = _jwt_exp(token)
    return token


def login_api() -> Optional[str]:
    """
    获取认证 token。
    优先使用环境变量 ONEPRO_BEARER_TOKEN（预置 token），其次通过登录接口获取并缓存。
    缓存的 token 提前 5 分钟自动刷新，401 时强制重新登录。
    """
    bearer = os.getenv("ONEPRO_BEARER_TOKEN", "").strip()
    if bearer:
        print("   ✅ 使用预置 Bearer token")
        return bearer
    return _get_token()


# ── 格式化辅助 ────────────────────────────────────
_STATE_MAP = {1: "New", 2: "In Progress", 3: "On Hold", 4: "Resolved", 5: "Closed", 6: "Canceled", 7: "Pending"}

def _fmt_priority(v: Any) -> str:
    """将 priority 数字或字符串格式化为 P1-P4"""
    try:
        n = int(v)
        return {1: "P1", 2: "P2", 3: "P3", 4: "P4"}.get(n, "P3")
    except (TypeError, ValueError):
        s = str(v).strip().upper()
        if s.startswith("P") and len(s) <= 3:
            return s
        return "P3"

def _fmt_state(v: Any) -> str:
    """将 state 数字映射为文字"""
    if v is None:
        return "Unknown"
    try:
        return _STATE_MAP.get(int(v), "Unknown")
    except (TypeError, ValueError):
        return str(v)


# ── API 认证 & 数据拉取 ────────────────────────────

def _parse_httped_raw(raw: str) -> Dict[str, Any]:
    """解析 curl -d '...' 格式的原始 JSON（key 包含 \\u 转义）"""
    try:
        return json.loads(raw)
    except Exception:
        text = raw.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
        return json.loads(text)


def fetch_incidents_from_api(token: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    从 OneProCloud API 分页拉取最多 limit 条 incident 记录。
    遇到 401 时自动重新登录并重试一次。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    }

    all_records: List[Dict[str, Any]] = []
    batch_size = min(200, limit)
    offset = 0
    refreshed = False  # 防止无限重试

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
            print(f"   ❌ 请求异常 at offset {offset}: {e}")
            break

        if resp.status_code == 401 and not refreshed:
            logger.warning("[Fetch] 收到 401，Token 可能已过期，尝试重新登录...")
            new_token = _get_token(force_refresh=True)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                refreshed = True
                continue
            logger.warning("[Fetch] Token 刷新失败，停止拉取")
            break
        if resp.status_code != 200:
            print(f"   ❌ API 请求失败 [{resp.status_code}]: {resp.text[:300]}")
            break

        body = resp.json()
        records = body.get("data", [])
        if not records:
            break

        for raw in records:
            if not isinstance(raw, dict):
                continue
            data_map = raw.get("record_data_map", raw)
            # 优先取 *_special_name（可读名称），fallback 到 sys_id
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
                "caller": data_map.get("caller_id_special_name") or data_map.get("u_caller_special_name"),
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

        print(f"   已拉取 {len(all_records)} 条（offset={offset}）")
        offset += batch_size

        if len(records) < batch_size:
            break

    return all_records[:limit]


def fetch_companies_from_api(token: str) -> List[Dict[str, Any]]:
    """
    从 OneProCloud API 拉取 core_company 表中的所有公司记录。
    API 响应格式: { "msg": "OK", "total": N, "code": 200, "data": [...] }
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    }

    url = f"{API_BASE_URL}/api/hyper/table/core_company"
    params = {
        "sysparm_limit": 500,
        "sysparm_offset": 0,
        "sysparm_display_value": "true",
    }

    all_records: List[Dict[str, Any]] = []
    batch_size = 200
    offset = 0
    refreshed = False

    while True:
        params["sysparm_offset"] = offset
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
        except Exception as e:
            print(f"   ❌ 公司 API 请求异常 at offset {offset}: {e}")
            break

        if resp.status_code == 401:
            logger.warning("[Fetch] 公司 API 收到 401，尝试重新登录...")
            new_token = _get_token(force_refresh=True)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                refreshed = True
                continue
            print(f"   ❌ Token 刷新失败")
            break
        if resp.status_code != 200:
            print(f"   ❌ 公司 API 请求失败 [{resp.status_code}]: {resp.text[:300]}")
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

        print(f"   已拉取 {len(all_records)} 条公司记录（offset={offset}）")
        offset += batch_size

        if len(records) < batch_size:
            break

    return all_records


def sync_companies_from_api() -> Dict[str, Any]:
    """
    从 OneProCloud API 同步 company 数据到数据库（按需/增量）。
    仅当数据库中不存在该 sys_id 的公司时才写入。
    """
    token = login_api()
    if not token:
        return {"status": "error", "message": "API 认证失败"}

    records = fetch_companies_from_api(token)
    if not records:
        return {"status": "error", "message": "API 未返回任何公司记录"}

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        added = 0
        skipped = 0
        for row in records:
            sys_id = str(row.get("sys_id", "")).strip()
            if not sys_id:
                skipped += 1
                continue
            existing = db.query(Company).filter(Company.sys_id == sys_id).first()
            if existing:
                skipped += 1
            else:
                db.add(Company(
                    sys_id=sys_id,
                    name=str(row.get("name", "") or "") or None,
                ))
                added += 1

        db.commit()
        total = db.query(Company).count()
        logger.info(f"   ✅ Company 同步完成: 新增 {added} 条，跳过 {skipped} 条，当前共 {total} 条")
        return {
            "status": "ok",
            "added": added,
            "skipped": skipped,
            "total": total,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"   ❌ Company 同步失败: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def fetch_users_from_api(token: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    从 OneProCloud API 分页拉取最多 limit 条 sys_user 记录。
    API 端点: GET /api/hyper/table/sys_user/{tableId}?viewSysId=Default view
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
    }

    # 使用任务描述中的 API 端点
    url = "https://support.oneprocloud.com/api/hyper/table/sys_user"
    params = {
    }

    all_records: List[Dict[str, Any]] = []
    batch_size = 200
    offset = 0
    refreshed = False

    while len(all_records) < limit:
        params["sysparm_offset"] = offset
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60, verify=False)
        except Exception as e:
            print(f"   ❌ User API 请求异常 at offset {offset}: {e}")
            break

        if resp.status_code == 401:
            logger.warning("[Fetch] User API 收到 401，尝试重新登录...")
            new_token = _get_token(force_refresh=True)
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                refreshed = True
                continue
            print(f"   ❌ Token 刷新失败")
            break
        if resp.status_code != 200:
            print(f"   ❌ User API 请求失败 [{resp.status_code}]: {resp.text[:300]}")
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

        print(f"   已拉取 {len(all_records)} 条用户记录（offset={offset}）")
        offset += batch_size

        if len(records) < batch_size:
            break

        if len(all_records) >= limit:
            break

    return all_records[:limit]


def sync_users_from_api() -> Dict[str, Any]:
    """
    从 OneProCloud API 同步 user 数据到数据库（按需/增量）。
    仅当数据库中不存在该 sys_id 的用户时才写入。
    """
    token = login_api()
    if not token:
        return {"status": "error", "message": "API 认证失败"}

    records = fetch_users_from_api(token)
    if not records:
        return {"status": "error", "message": "API 未返回任何用户记录"}

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        added = 0
        skipped = 0
        seen_sys_ids: set = set()
        for row in records:
            sys_id = str(row.get("sys_id", "")).strip()
            if not sys_id:
                skipped += 1
                continue
            # 批次级去重：同一次 API 响应中可能有重复 sys_id
            if sys_id in seen_sys_ids:
                skipped += 1
                continue
            seen_sys_ids.add(sys_id)
            existing = db.query(User).filter(User.sys_id == sys_id).first()
            if existing:
                skipped += 1
            else:
                db.add(User(
                    sys_id=sys_id,
                    name=str(row.get("name", "") or "") or None,
                    email=str(row.get("email", "") or "") or None,
                    user_name=str(row.get("user_name", "") or "") or None,
                    department=str(row.get("department", "") or "") or None,
                    phone=str(row.get("phone", "") or "") or None,
                    mobile_phone=str(row.get("mobile_phone", "") or "") or None,
                    title=str(row.get("title", "") or "") or None,
                    active=str(row.get("active", "") or "") or None,
                ))
                added += 1

        db.commit()
        total = db.query(User).count()
        logger.info(f"   ✅ User 同步完成: 新增 {added} 条，跳过 {skipped} 条，当前共 {total} 条")
        return {
            "status": "ok",
            "added": added,
            "skipped": skipped,
            "total": total,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"   ❌ User 同步失败: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据清洗（Excel 格式）"""
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    df["Updated"] = pd.to_datetime(df["Updated"], errors="coerce")
    df["resolve_hours"] = ((df["Updated"] - df["Created"]).dt.total_seconds() / 3600).fillna(0)
    df["sla_limit"] = df["Priority"].map(SLA_MAP)
    df["is_sla_met"] = ((df["resolve_hours"] <= df["sla_limit"]) & df["Priority"].notna()).astype(int)
    df["month"] = df["Created"].dt.to_period("M").astype(str)
    df["weekday"] = df["Created"].dt.day_name()
    df["hour"] = df["Created"].dt.hour
    df["company"] = df["Company"].fillna("未知")
    df["caller"] = df["Caller"].fillna("未知")
    df["priority"] = df["Priority"].fillna("P3")
    df["state"] = df["State"].fillna("Unknown")
    df["category"] = df["Category"].fillna("未知")
    df["assignment_group"] = df["Assignment group"].fillna("未分配")
    return df


def _parse_api_datetime(value: Any) -> datetime:
    """解析 API 返回的日期时间字符串（兼容多种格式）"""
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
    """从 API 行数据派生 resolve_hours / sla_limit / is_sla_met 等字段"""
    created = _parse_api_datetime(row.get("sys_created_on"))
    updated = _parse_api_datetime(row.get("sys_updated_on"))
    resolve_hours = max(0, (updated - created).total_seconds() / 3600)
    priority = _fmt_priority(row.get("priority"))
    sla_limit = SLA_MAP.get(priority, 24)
    is_sla_met = 1 if resolve_hours <= sla_limit else 0
    return {
        "resolve_hours": round(resolve_hours, 2),
        "sla_limit": sla_limit,
        "is_sla_met": is_sla_met,
        "month": created.strftime("%Y-%m"),
        "weekday": created.strftime("%A"),
        "hour": created.hour,
    }


def _record_to_dict(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 API 行数据转换为 Incident 写入字典"""
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
        "created_at": _parse_api_datetime(raw.get("sys_created_on")),
        "updated_at": _parse_api_datetime(raw.get("sys_updated_on")),
        **derived,
    }


def sync_from_api(full_sync: bool = True) -> Dict[str, Any]:
    """
    从 OneProCloud API 同步工单数据到数据库。
    - full_sync=True：先清空再全量写入（初始加载）
    - full_sync=False：增量更新（只插入/覆盖 sys_updated_on 更新的记录）

    返回同步结果统计。
    """
    token = login_api()
    if not token:
        return {"status": "error", "message": "API 认证失败，请检查 ONEPRO_BEARER_TOKEN 或 ONEPRO_USERNAME/PASSWORD 环境变量"}

    limit = API_SYNC_LIMIT
    records = fetch_incidents_from_api(token, limit=limit)
    if not records:
        return {"status": "error", "message": "API 未返回任何记录"}

    Base.metadata.create_all(bind=engine)

    # 先同步公司映射表（用于将 company sys_id → 名称）
    sync_companies_from_api()

    # 构建 sys_id -> name 映射
    _db_tmp = SessionLocal()
    company_map: Dict[str, str] = {}
    try:
        for row in _db_tmp.query(Company).all():
            if row.sys_id:
                company_map[row.sys_id] = row.name or row.sys_id
    finally:
        _db_tmp.close()

    db: Session = SessionLocal()
    try:
        if full_sync:
            db.query(Incident).delete()
            db.commit()
            logger.info("   旧数据已清理（全量同步）")

        mapped = []
        for raw in records:
            # 将 company sys_id 替换为可读名称
            co_sys_id = raw.get("company") or ""
            raw["company"] = company_map.get(co_sys_id, co_sys_id)
            m = _record_to_dict(raw)
            if m:
                mapped.append(m)

        # 增量模式：按 number 覆盖已有记录
        for row in mapped:
            existing = db.query(Incident).filter(Incident.number == row["number"]).first()
            if existing:
                for key, val in row.items():
                    setattr(existing, key, val)
            else:
                db.add(Incident(**row))

        db.commit()
        total = db.query(Incident).count()
        logger.info(f"   ✅ Incident 同步完成: {len(mapped)} 条已处理，当前库中共 {total} 条")

        # 同步 user（按需增量）
        user_result = sync_users_from_api()

        return {
            "status": "ok",
            "synced": len(mapped),
            "total": total,
            "mode": "full" if full_sync else "incremental",
            "users": user_result,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"   ❌ 同步失败: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def load_excel_to_db(excel_path: str):
    """
    Excel 备用 ETL：仅在无 API 凭证时使用。
    会清空数据库再全量写入。
    """
    print(f"📥 [Excel 备用] 读取: {excel_path}")
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel 文件不存在: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name="data")
    print(f"   原始记录: {len(df)} 条")
    df = clean_data(df)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        db.query(Incident).delete()
        db.commit()
        print("   旧数据已清理")

        batch = []
        for _, row in df.iterrows():
            batch.append(Incident(
                number=row["Number"],
                parent_incident=row.get("Parent Incident"),
                short_description=row.get("Short description"),
                company=row["company"],
                caller=row["caller"],
                created_by=row.get("Created by"),
                priority=row["priority"],
                assigned_to=row.get("Assigned to"),
                state=row["state"],
                resolution_code=row.get("Resolution code"),
                category=row["category"],
                assignment_group=row["assignment_group"],
                updated_by=row.get("Updated by"),
                created_at=row["Created"].to_pydatetime() if pd.notna(row["Created"]) else datetime.utcnow(),
                updated_at=row["Updated"].to_pydatetime() if pd.notna(row["Updated"]) else datetime.utcnow(),
                resolve_hours=round(row["resolve_hours"], 2),
                sla_limit=row.get("sla_limit"),
                is_sla_met=int(row.get("is_sla_met", 0)),
                month=row.get("month"),
                weekday=row.get("weekday"),
                hour=int(row.get("hour", 0)) if pd.notna(row.get("hour")) else 0,
            ))
            if len(batch) >= 500:
                db.add_all(batch)
                db.commit()
                batch = []

        if batch:
            db.add_all(batch)
            db.commit()

        total = db.query(Incident).count()
        print(f"   ✅ 写入完成: {total} 条")
        return {"status": "ok", "total": total}

    finally:
        db.close()


if __name__ == "__main__":
    # 默认尝试 API 同步，无凭证才 fallback 到 Excel
    result = sync_from_api(full_sync=True)
    if result["status"] == "error":
        print(f"   尝试 Excel 备用: {result['message']}")
        if os.path.exists(EXCEL_PATH):
            load_excel_to_db(EXCEL_PATH)
        else:
            print(f"❌ Excel 文件也不存在: {EXCEL_PATH}")
