"""
Feishu (Lark) approval provider.

Design notes (aligned with JiraProvider):
- Authentication: use app_id / app_secret to obtain tenant_access_token.
- Step 2 "project list": reuse the fetch-projects endpoint to return approval
  definitions as selectable items.
- collect: for the configured approval definitions (project_keys) and time
  range, pull approval instances and build the RawDataRecord payload shape.
- validate: check each instance id via detail API; treat failures as deleted.
- Attachments: extract file fields from the instance form, return attachment
  metadata; download_attachment_content performs the actual download.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .base import BaseProvider

logger = logging.getLogger(__name__)

FEISHU_BASE_URL = "https://open.feishu.cn"
TENANT_TOKEN_URL = f"{FEISHU_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
APPROVAL_LIST_URL = f"{FEISHU_BASE_URL}/open-apis/approval/v4/approvals"
# Use the newer instances query API to fetch approval instances
INSTANCE_LIST_URL = f"{FEISHU_BASE_URL}/open-apis/approval/v4/instances/query"
# Base path for approval instance detail API; final URL:
#   {INSTANCE_DETAIL_URL}/{instance_code}
INSTANCE_DETAIL_URL = f"{FEISHU_BASE_URL}/open-apis/approval/v4/instances"
FILE_DOWNLOAD_URL_TEMPLATE = (
    FEISHU_BASE_URL + "/open-apis/drive/v1/files/{file_token}/download"
)
# Contact API: get user name for approval timeline display
CONTACT_USER_URL = f"{FEISHU_BASE_URL}/open-apis/contact/v3/users"


def _to_unix_ms(dt: Any) -> int:
    """
    Convert datetime / ISO8601 string / timestamp to Feishu unix ms timestamp.
    """
    if isinstance(dt, (int, float)):
        return int(dt * 1000)
    if isinstance(dt, str):
        try:
            # 允许直接传 ISO8601 字符串
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            dt = parsed
        except Exception:
            return 0
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return 0


def _from_unix_ms(value: Any) -> datetime | None:
    """
    Convert Feishu millisecond timestamp (str/int) to timezone-aware datetime.
    Returns None if value is falsy or cannot be parsed.
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        ms = int(value)
    except (TypeError, ValueError):
        return None
    # Feishu uses epoch milliseconds
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


class FeishuProvider(BaseProvider):
    """
    Feishu approval data collection provider.

    Expected auth_config:
    {
        "app_id": "...",
        "app_secret": "...",
        # Optional: future extensions like tenant_key, user mapping, etc.
    }
    """

    def __init__(self) -> None:
        self._tenant_access_token: str | None = None
        self._tenant_token_expire_at: float | None = None

    # ---------- Internal HTTP / token helpers ----------

    def _get_tenant_access_token(self, auth_config: dict) -> str:
        app_id = (auth_config.get("app_id") or "").strip()
        app_secret = (auth_config.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            raise ValueError("Feishu app_id and app_secret are required")

        now = time.time()
        if (
            self._tenant_access_token
            and self._tenant_token_expire_at
            and now < self._tenant_token_expire_at - 60
        ):
            return self._tenant_access_token

        resp = requests.post(
            TENANT_TOKEN_URL,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code", data.get("code", -1))
        if code != 0:
            msg = data.get("msg") or data.get("message") or "Feishu auth failed"
            raise ValueError(f"Feishu authentication failed: {msg}")
        token = data.get("tenant_access_token") or data.get("tenant_accessToken")
        if not token:
            raise ValueError("Feishu auth response missing tenant_access_token")
        expire = data.get("expire") or data.get("expire_in") or 3600
        self._tenant_access_token = token
        self._tenant_token_expire_at = now + int(expire)
        return token

    def _auth_headers(self, auth_config: dict) -> dict:
        token = self._get_tenant_access_token(auth_config)
        return {"Authorization": f"Bearer {token}"}

    # ---------- Public API: auth / definitions / collect / validate ----------

    def authenticate(self, auth_config: dict) -> bool:
        """
        Verify Feishu application credentials (app_id, app_secret).
        """
        if not auth_config:
            return False
        try:
            logger.info(
                "FeishuProvider.authenticate: validating app_id=%s",
                (auth_config.get("app_id") or "").strip(),
            )
            self._get_tenant_access_token(auth_config)
            logger.info("FeishuProvider.authenticate: success")
            return True
        except Exception as e:
            logger.warning(f"FeishuProvider.authenticate failed: {e}")
            return False

    def list_projects(self, auth_config: dict) -> list[dict]:
        """
        Used by frontend step 2: return approval definition list.

        To reuse the existing fetch-projects endpoint, we return:
        [{\"key\": approval_code, \"id\": approval_code, \"name\": approval_name}, ...]
        """
        headers = self._auth_headers(auth_config)
        logger.info("FeishuProvider.list_projects: fetching approval definitions")
        try:
            resp = requests.get(APPROVAL_LIST_URL, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json() or {}
            items = (
                (data.get("data") or {}).get("approvals")
                or (data.get("data") or {}).get("items")
                or []
            )
            out: list[dict] = []
            for item in items:
                code = item.get("approval_code") or item.get("code")
                name = item.get("name") or item.get("approval_name") or code
                if not code:
                    continue
                out.append({"key": code, "id": str(code), "name": name})
            logger.info(
                "FeishuProvider.list_projects: fetched %d approval definitions",
                len(out),
            )
            return out
        except Exception as e:
            logger.warning(f"FeishuProvider.list_projects failed: {e}")
            raise

    def _list_instances_for_approval(
        self,
        auth_config: dict,
        approval_code: str,
        start_time,
        end_time,
    ) -> list[dict]:
        """
        Call Feishu approval instances query API and return raw instances.
        """
        headers = self._auth_headers(auth_config)
        start_ms = _to_unix_ms(start_time)
        end_ms = _to_unix_ms(end_time)
        if not start_ms or not end_ms:
            return []

        page_token = None
        instances: list[dict] = []
        while True:
            payload: dict[str, Any] = {
                "approval_code": approval_code,
                # Per Feishu docs, use instance_start_time_* fields for time range
                "instance_start_time_from": start_ms,
                "instance_start_time_to": end_ms,
                # Per Feishu docs, page_size max is 200
                "page_size": 200,
            }
            if page_token:
                payload["page_token"] = page_token
            resp = requests.post(
                INSTANCE_LIST_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json() or {}
            if data.get("code", 0) != 0:
                msg = data.get("msg") or data.get("message") or "Feishu list instances failed"
                raise ValueError(msg)
            d = data.get("data") or {}
            items = d.get("instance_list") or d.get("items") or []
            instances.extend(items)
            logger.info(
                "FeishuProvider._list_instances_for_approval: approval_code=%s "
                "fetched=%d, total_so_far=%d, page_token=%s",
                approval_code,
                len(items),
                len(instances),
                (d.get("page_token") or "")[:32],
            )
            page_token = d.get("page_token")
            if not page_token:
                break
        return instances

    def _get_instance_detail(
        self,
        auth_config: dict,
        instance_code: str,
    ) -> dict | None:
        """
        Fetch single approval instance detail (for validate or enrichment).
        """
        headers = self._auth_headers(auth_config)
        url = f"{INSTANCE_DETAIL_URL}/{instance_code}"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
        if data.get("code", 0) != 0:
            msg = data.get("msg") or data.get("message") or "Feishu get instance failed"
            logger.warning(
                "FeishuProvider._get_instance_detail: instance_code=%s error=%s",
                instance_code,
                msg,
            )
            return None
        # Detail may be nested under data.instance or just data
        d = data.get("data") or {}
        detail = d.get("instance") or d
        if not isinstance(detail, dict):
            return None
        return detail

    def _collect_timeline_user_ids(self, instance: dict) -> list[str]:
        """
        Collect all unique user IDs from instance timeline (and CC ext.user_id_list).
        Used to fetch display names via contact API.
        """
        timeline = (
            instance.get("timeline")
            or instance.get("time_line")
            or instance.get("approval_timeline")
            or []
        )
        if not isinstance(timeline, list):
            return []
        ids: set[str] = set()
        for node in timeline:
            if not isinstance(node, dict):
                continue
            for key in ("user_id", "userId", "operator_id", "operatorId"):
                val = node.get(key)
                if val is not None and str(val).strip():
                    ids.add(str(val).strip())
            user = node.get("user")
            if isinstance(user, dict) and user.get("user_id"):
                ids.add(str(user["user_id"]))
            operator = node.get("operator")
            if isinstance(operator, dict) and operator.get("user_id"):
                ids.add(str(operator["user_id"]))
            # CC node: ext.user_id_list or ext.user_id (ext may be dict or JSON string)
            raw_type = node.get("type") or node.get("result") or ""
            if str(raw_type).upper() == "CC":
                ext = node.get("ext")
                if not isinstance(ext, dict):
                    ext = {}
                id_list = ext.get("user_id_list") or node.get("user_id_list")
                if id_list is None and ext.get("user_id") is not None:
                    id_list = [ext["user_id"]]
                if id_list is not None:
                    for uid in id_list if isinstance(id_list, list) else [id_list]:
                        if uid is not None and str(uid).strip():
                            ids.add(str(uid).strip())
        return list(ids)

    def _fetch_user_name(self, auth_config: dict, user_id: str) -> str | None:
        """
        Fetch user display name from Feishu contact API.
        Requires app scope contact:user.base (or similar). Returns None on failure.
        """
        if not user_id or not str(user_id).strip():
            return None
        user_id = str(user_id).strip()
        headers = self._auth_headers(auth_config)
        url = f"{CONTACT_USER_URL}/{user_id}"
        params = {"user_id_type": "user_id"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception as e:
            logger.warning(
                "FeishuProvider._fetch_user_name failed user_id=%s: %s",
                user_id,
                e,
            )
            return None
        if data.get("code", 0) != 0:
            return None
        user = (data.get("data") or {}).get("user")
        if not isinstance(user, dict):
            return None
        name = user.get("name") or user.get("en_name") or user.get("nickname")
        if name is not None and str(name).strip():
            return str(name).strip()
        return None

    def _instance_to_item(
        self,
        approval_code: str,
        approval: dict,
        group: dict,
        instance: dict,
        attachments: list[dict],
    ) -> dict | None:
        """
        Convert a Feishu approval instance into the RawDataRecord item shape.
        """
        if not isinstance(instance, dict):
            return None
        instance_code = (
            instance.get("instance_code")
            or instance.get("instance_id")
            or instance.get("id")
        )
        if not instance_code:
            return None
        status = instance.get("status") or instance.get("approval_status")
        start_raw = (
            instance.get("start_time")
            or instance.get("create_time")
            or instance.get("create_timestamp")
        )
        end_raw = (
            instance.get("end_time")
            or instance.get("update_time")
            or instance.get("update_timestamp")
        )
        start_time = _from_unix_ms(start_raw)
        end_time = _from_unix_ms(end_raw)

        raw_data = {
            "approval": approval,
            "group": group,
            "instance": instance,
            "approval_code": approval_code,
            "attachments": attachments or [],
        }
        payload = json.dumps(raw_data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(payload.encode()).hexdigest()
        approval_name = (approval or {}).get("name")
        filter_metadata = {
            "approval_code": approval_code,
            "approval_name": approval_name,
            "status": status,
        }
        return {
            "source_unique_id": str(instance_code),
            "raw_data": raw_data,
            "filter_metadata": filter_metadata,
            "data_hash": data_hash,
            "source_created_at": start_time,
            "source_updated_at": end_time,
        }

    def _extract_attachments(self, instance: dict) -> list[dict]:
        """
        Extract file-type fields from the instance form and build attachment
        metadata.

        Typical (simplified) structure:
        form = [
            {"type": "file", "name": "Attachment", "value": [{"file_token": "..."}]},
            ...
        ]
        """
        form = instance.get("form") or instance.get("form_content") or []
        if not isinstance(form, list):
            return []
        attachments: list[dict] = []
        for field in form:
            if not isinstance(field, dict):
                continue
            f_type = field.get("type")
            if f_type not in ("file", "attachment"):
                continue
            values = field.get("value") or []
            if not isinstance(values, list):
                values = [values]
            for v in values:
                if not isinstance(v, dict):
                    continue
                file_token = v.get("file_token") or v.get("fileKey") or v.get("token")
                if not file_token:
                    continue
                file_name = v.get("name") or v.get("file_name") or file_token
                file_type = v.get("mime_type") or v.get("type") or ""
                file_size = v.get("size") or 0
                created_raw = instance.get("start_time") or instance.get("create_time")
                updated_raw = instance.get("end_time") or instance.get("update_time")
                attachments.append(
                    {
                        "source_file_id": str(file_token),
                        "file_name": str(file_name),
                        "file_url": FILE_DOWNLOAD_URL_TEMPLATE.format(
                            file_token=file_token
                        ),
                        "file_type": str(file_type),
                        "file_size": int(file_size) if file_size else 0,
                        "source_created_at": _from_unix_ms(created_raw),
                        "source_updated_at": _from_unix_ms(updated_raw),
                    }
                )
        return attachments

    def _extract_attachments_from_detail(self, detail: dict) -> list[dict]:
        """
        Extract attachments from instance detail response.

        Detail may be either:
        - the instance object itself (with form/form_content), or
        - a wrapper containing an "instance" key.
        """
        if not isinstance(detail, dict):
            return []
        # If detail has an "instance" key that is a dict, drill into it
        inst = detail.get("instance")
        if isinstance(inst, dict):
            return self._extract_attachments(inst)
        # Otherwise treat detail as the instance object
        return self._extract_attachments(detail)

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
        Collect approval instances within the given time window.

        kwargs:
        - project_keys: List[str], approval definition codes selected in step 2.
        """
        if not auth_config:
            return []
        approval_codes: list[str] = kwargs.get("project_keys") or []
        if not approval_codes:
            # If not explicitly configured, default to all approval definitions.
            try:
                defs = self.list_projects(auth_config)
                approval_codes = [d["key"] for d in defs if d.get("key")]
            except Exception as e:
                logger.warning(
                    f"FeishuProvider.collect list_projects failed: {e}"
                )
                return []

        logger.info(
            "FeishuProvider.collect: start, approval_codes=%s, "
            "start_time=%s, end_time=%s, user_id=%s",
            approval_codes,
            start_time,
            end_time,
            user_id,
        )
        items: list[dict] = []
        user_name_cache: dict[str, str | None] = {}
        for code in approval_codes:
            try:
                instances = self._list_instances_for_approval(
                    auth_config, code, start_time, end_time
                )
            except Exception as e:
                logger.warning(
                    f"FeishuProvider.collect list instances failed "
                    f"approval_code={code}: {e}"
                )
                continue
            for wrapper in instances:
                if not isinstance(wrapper, dict):
                    continue
                approval = wrapper.get("approval") or {}
                group = wrapper.get("group") or {}
                inst_meta = wrapper.get("instance") or {}
                instance_code = inst_meta.get("code")
                if not instance_code:
                    continue
                # Fetch full instance detail to enrich data and extract attachments
                detail = self._get_instance_detail(auth_config, instance_code)
                full_instance = inst_meta
                if isinstance(detail, dict):
                    # Prefer detail.instance if present, else detail itself
                    inst_from_detail = detail.get("instance")
                    if isinstance(inst_from_detail, dict):
                        full_instance = inst_from_detail
                    else:
                        full_instance = detail
                attachments = self._extract_attachments_from_detail(full_instance)
                # Enrich instance with user_map (user_id -> name) for approval flow display
                user_ids = self._collect_timeline_user_ids(full_instance)
                user_map: dict[str, str] = {}
                for uid in user_ids:
                    if uid not in user_name_cache:
                        user_name_cache[uid] = self._fetch_user_name(auth_config, uid)
                    if user_name_cache.get(uid):
                        user_map[uid] = user_name_cache[uid]
                full_instance["user_map"] = user_map
                item = self._instance_to_item(
                    code,
                    approval,
                    group,
                    full_instance,
                    attachments,
                )
                if item:
                    items.append(item)
        logger.info(
            "FeishuProvider.collect: done, approval_codes=%s, items=%d",
            approval_codes,
            len(items),
        )
        return items

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
        Check whether the given instance ids still exist on Feishu.

        Simple implementation: query each instance detail; if the API errors or
        returns nothing, treat the instance as deleted.
        """
        if not auth_config or not source_unique_ids:
            return []
        missing: list[str] = []
        for sid in source_unique_ids:
            try:
                inst = self._get_instance_detail(auth_config, sid)
            except Exception:
                inst = None
            if not inst:
                missing.append(sid)
        return missing

    def fetch_attachments(self, auth_config: dict, raw_record) -> list[dict]:
        """
        Return attachment metadata list from RawDataRecord.raw_data.

        RawDataRecord.raw_data structure:
        {
            "instance": {...},
            "approval_code": "...",
            "attachments": [...]
        }
        """
        raw_data = getattr(raw_record, "raw_data", None) or {}
        if not isinstance(raw_data, dict):
            return []
        attachments = raw_data.get("attachments") or []
        if not isinstance(attachments, list):
            return []
        return attachments

    def download_attachment_content(
        self,
        auth_config: dict,
        attachment_meta: dict,
    ) -> bytes | None:
        """
        Download Feishu attachment file content using file_url.
        """
        if not attachment_meta:
            return None
        url = attachment_meta.get("file_url")
        if not url:
            return None
        headers = self._auth_headers(auth_config)
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.warning(
                "FeishuProvider.download_attachment_content failed "
                f"url={url[:80]}: {e}"
            )
            return None
