"""
License platform provider.

- Auth: base_url + username + password; POST /v1/auth/login to get api_key.
- Step 2 exposes order collection only; step 3 config shape follows Jira
  (project_keys, initial_range, etc.).
- Collect: GET /v1/order/list with is_paginate=false,
  filter_update_start_time/filter_update_end_time as UTC strings "YYYY-MM-DD HH:MM:SS";
  source_unique_id uses the response field "code".
"""

import hashlib
import json
import logging
from typing import Any

import requests

from data_collector.utils import to_utc_datetime_str
from .base import BaseProvider

logger = logging.getLogger(__name__)


def _get_base_url(auth_config: dict) -> str:
    base_url = (auth_config.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("base_url (auth URL) is required")
    return base_url


class LicenseProvider(BaseProvider):
    """
    License platform data collection: order collection only.

    Expected auth_config:
    {
        "base_url": "https://auth.example.com",
        "username": "...",
        "password": "...",
    }
    """

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._api_key_base_url: str | None = None

    def _get_api_key(self, auth_config: dict) -> str:
        base_url = _get_base_url(auth_config)
        username = (auth_config.get("username") or "").strip()
        password = (auth_config.get("password") or "").strip()
        if not username or not password:
            raise ValueError("License requires username and password")

        if self._api_key and self._api_key_base_url == base_url:
            return self._api_key

        url = f"{base_url}/v1/auth/login"
        payload = {"username": username, "password": password}
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
        api_key = data.get("api_key")
        if not api_key:
            raise ValueError("Login response missing api_key")
        self._api_key = api_key
        self._api_key_base_url = base_url
        return api_key

    def _auth_headers(self, auth_config: dict) -> dict:
        api_key = self._get_api_key(auth_config)
        return {"Authorization": api_key}

    def authenticate(self, auth_config: dict) -> bool:
        """Verify connection using base_url, username, and password."""
        if not auth_config:
            return False
        try:
            self._get_api_key(auth_config)
            logger.info("LicenseProvider.authenticate: success")
            return True
        except Exception as e:
            logger.warning(f"LicenseProvider.authenticate failed: {e}")
            return False

    def list_projects(self, auth_config: dict) -> list[dict]:
        """
        Step 2: order collection only; return a single option for the frontend.
        Shape aligned with Jira/Feishu: key, id, name.
        """
        return [
            {"key": "order", "id": "order", "name": "Order collection"},
        ]

    def _order_raw_to_item(self, order: dict) -> dict | None:
        """Convert raw order dict to collection item; source_unique_id=code."""
        code = order.get("code")
        if not code:
            return None
        raw_data = {"order": order}
        payload = json.dumps(raw_data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(payload.encode()).hexdigest()
        created_at = order.get("created_at")
        updated_at = order.get("approval_at") or order.get("created_at")
        category = order.get("category") or {}
        category_id = (
            category.get("id")
            if isinstance(category, dict) and category.get("id") is not None
            else order.get("category_id")
        )
        third_id = order.get("third_id")
        filter_metadata = {}
        if category_id is not None:
            filter_metadata["category"] = category_id
        if third_id is not None:
            filter_metadata["third_id"] = third_id
        return {
            "source_unique_id": code,
            "raw_data": raw_data,
            "filter_metadata": filter_metadata,
            "data_hash": data_hash,
            "source_created_at": created_at,
            "source_updated_at": updated_at,
        }

    def collect(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        **kwargs: Any,
    ) -> list[dict]:
        """
        Fetch order list: GET /v1/order/list with is_paginate=false,
        filter_update_start_time and filter_update_end_time as strings.
        """
        if not auth_config:
            return []
        project_keys = kwargs.get("project_keys") or []
        if project_keys and "order" not in project_keys:
            logger.info(
                f"LicenseProvider.collect: project_keys={project_keys} "
                f"does not include order, skip",
            )
            return []

        base_url = _get_base_url(auth_config)
        url = f"{base_url}/v1/order/list"
        filter_update_start_time = to_utc_datetime_str(start_time)
        filter_update_end_time = to_utc_datetime_str(end_time)
        params = {
            "is_paginate": "false",
            "filter_update_start_time": filter_update_start_time,
            "filter_update_end_time": filter_update_end_time,
        }
        headers = self._auth_headers(auth_config)
        logger.info(
            f"LicenseProvider.collect: GET {url} params={params}",
        )
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json() or {}
        items_raw = (
            data.get("items") or data.get("data", {}).get("items") or []
        )
        out: list[dict] = []
        for order in items_raw:
            if not isinstance(order, dict):
                continue
            item = self._order_raw_to_item(order)
            if item:
                out.append(item)
        logger.info(
            f"LicenseProvider.collect: done, returning {len(out)} orders",
        )
        return out

    def validate(
        self,
        auth_config: dict,
        start_time: Any,
        end_time: Any,
        user_id: int,
        platform: str,
        source_unique_ids: list[str],
    ) -> list[str]:
        """
        Check which orders still exist. Re-fetches list and compares codes
        when no single-order detail API exists.
        """
        if not auth_config or not source_unique_ids:
            return []
        try:
            base_url = _get_base_url(auth_config)
            url = f"{base_url}/v1/order/list"
            params = {
                "is_paginate": "false",
                "filter_update_start_time": to_utc_datetime_str(start_time),
                "filter_update_end_time": to_utc_datetime_str(end_time),
            }
            headers = self._auth_headers(auth_config)
            resp = requests.get(
                url, headers=headers, params=params, timeout=60
            )
            resp.raise_for_status()
            data = resp.json() or {}
            items_raw = (
                data.get("items")
                or data.get("data", {}).get("items")
                or []
            )
            existing_codes = {
                str(o.get("code", ""))
                for o in items_raw
                if isinstance(o, dict) and o.get("code")
            }
            missing = [
                sid for sid in source_unique_ids if sid not in existing_codes
            ]
            return missing
        except Exception as e:
            logger.warning(f"LicenseProvider.validate failed: {e}")
            return []

    def fetch_attachments(
        self, auth_config: dict, raw_record: Any
    ) -> list[dict]:
        """Order collection has no attachments; return empty list."""
        return []
