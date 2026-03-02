"""
JIRA platform provider (jira-python). Issue + comments + attachment metadata.
"""
import hashlib
import json
import logging
import time
from datetime import timedelta, timezone

from jira import JIRA

from .base import BaseProvider

logger = logging.getLogger(__name__)

SEARCH_PAGE_SIZE = 50
COMMENT_PAGE_SIZE = 50
REQUEST_DELAY_SECONDS = 0.05


def _to_utc_date(dt):
    """Get calendar date in UTC from datetime (or as-is if already a date)."""
    if hasattr(dt, "astimezone"):
        return dt.astimezone(timezone.utc).date()
    return dt


def _jql_date_range(start_time, end_time) -> tuple[str, str]:
    """
    Return (start_date_str, end_date_plus_one_str) in UTC for JQL.
    Date-only (YYYY-MM-DD); end uses next day to include full end day.
    JQL: updated >= "start_date" AND updated < "end_date_plus_one".
    """
    start_date = _to_utc_date(start_time)
    end_date = _to_utc_date(end_time)
    end_plus_one = end_date + timedelta(days=1)
    s = start_date.strftime("%Y-%m-%d")
    e = end_plus_one.strftime("%Y-%m-%d")
    return s, e


def _client(auth_config: dict) -> JIRA:
    """Build JIRA client from auth_config (base_url, auth_version, creds)."""
    base_url = (auth_config.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("base_url is required")
    auth_version = auth_config.get("auth_version") or "legacy"
    if auth_version == "cloud":
        email = auth_config.get("email") or ""
        api_token = auth_config.get("api_token") or ""
        if not email or not api_token:
            raise ValueError("email and api_token are required for Jira Cloud")
        return JIRA(server=base_url, basic_auth=(email, api_token))
    username = auth_config.get("username") or ""
    password = auth_config.get("password") or ""
    if not username or not password:
        raise ValueError("username and password are required for legacy Jira")
    return JIRA(server=base_url, basic_auth=(username, password))


def _get_all_comments(jira: JIRA, issue_self: str) -> list[dict]:
    """Fetch all comments for an issue via REST (paginated)."""
    out = []
    start_at = 0
    url = issue_self.rstrip("/") + "/comment"
    while True:
        params = {"startAt": start_at, "maxResults": COMMENT_PAGE_SIZE}
        resp = jira._session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        comments = data.get("comments") or []
        total = int(data.get("total", 0))
        out.extend(comments)
        start_at += len(comments)
        if start_at >= total or not comments:
            break
    return out


def _issue_raw_to_item(issue_raw: dict, comments: list[dict]) -> dict | None:
    """Build collector item from issue raw dict and comments."""
    key = issue_raw.get("key")
    if not key:
        return None
    fields = issue_raw.get("fields") or {}
    attachments = list(fields.get("attachment") or [])
    raw_data = {
        "issue": issue_raw,
        "comments": comments,
        "attachments": attachments,
    }
    payload = json.dumps(raw_data, sort_keys=True, default=str)
    data_hash = hashlib.sha256(payload.encode()).hexdigest()
    created = fields.get("created")
    updated = fields.get("updated")
    project_key = (fields.get("project") or {}).get("key")
    return {
        "source_unique_id": key,
        "raw_data": raw_data,
        "filter_metadata": {"project": project_key},
        "data_hash": data_hash,
        "source_created_at": created,
        "source_updated_at": updated,
    }


class JiraProvider(BaseProvider):
    """JIRA data collection provider (jira-python)."""

    def authenticate(self, auth_config: dict) -> bool:
        """Verify credentials via jira.myself()."""
        if not auth_config:
            return False
        try:
            jira = _client(auth_config)
            jira.myself()
            return True
        except Exception as e:
            logger.warning(f"Jira authenticate failed: {e}")
            return False

    def list_projects(self, auth_config: dict) -> list[dict]:
        """Fetch all projects via jira.projects()."""
        try:
            jira = _client(auth_config)
            projects = jira.projects()
            return [
                {"key": p.key, "id": str(p.id), "name": p.name or p.key}
                for p in projects
            ]
        except Exception as e:
            logger.warning(f"Jira list_projects failed: {e}")
            raise

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
        Fetch issues (with comments and attachment metadata) in time range.
        Uses search_issues() then issue() per page; 50 per page.
        """
        project_keys = kwargs.get("project_keys") or []
        start_str, end_plus_one_str = _jql_date_range(start_time, end_time)
        jql_parts = [
            f'updated >= "{start_str}"',
            f'updated < "{end_plus_one_str}"',
        ]
        if project_keys:
            keys_comma = ", ".join(project_keys)
            jql_parts.append(f"project in ({keys_comma})")
        jql = " AND ".join(jql_parts)
        proj_preview = (
            project_keys[:5] if len(project_keys) > 5 else project_keys
        )
        logger.info(
            f"JiraProvider.collect: jql={jql}, project_keys={proj_preview}, "
            f"page_size={SEARCH_PAGE_SIZE}"
        )
        jira = _client(auth_config)
        out = []
        start_at = 0
        fields = (
            "summary,updated,created,status,project,issuetype,"
            "description,attachment"
        )
        while True:
            data = jira.search_issues(
                jql,
                startAt=start_at,
                maxResults=SEARCH_PAGE_SIZE,
                json_result=True,
            )
            issues = data.get("issues") or []
            total = int(data.get("total", 0))
            total_this_page = len(issues)
            for idx, issue in enumerate(issues):
                key = issue.get("key")
                if not key:
                    continue
                if idx > 0 and REQUEST_DELAY_SECONDS > 0:
                    time.sleep(REQUEST_DELAY_SECONDS)
                try:
                    full = jira.issue(key, fields=fields, expand="attachment")
                    issue_raw = full.raw
                    comments = _get_all_comments(jira, full.self)
                    item = _issue_raw_to_item(issue_raw, comments)
                    if item:
                        out.append(item)
                except Exception as e:
                    logger.warning(
                        f"JiraProvider.collect: issue {key} failed: {e}"
                    )
                    continue
            logger.info(
                f"JiraProvider.collect: page startAt={start_at}, "
                f"got {total_this_page} issues, total so far={len(out)}, "
                f"total={total}"
            )
            start_at += total_this_page
            if start_at >= total or total_this_page == 0:
                break
        logger.info(f"JiraProvider.collect: done, returning {len(out)} issues")
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
        """Return issue keys that no longer exist on the server."""
        if not source_unique_ids:
            return []
        try:
            jira = _client(auth_config)
            missing = []
            for key in source_unique_ids:
                try:
                    jira.issue(key, fields="key")
                except Exception:
                    missing.append(key)
            return missing
        except Exception as e:
            logger.warning(f"Jira validate failed: {e}")
            return []

    def fetch_attachments(self, auth_config: dict, raw_record) -> list[dict]:
        """Return attachment metadata from raw_record.raw_data.attachments."""
        raw_data = getattr(raw_record, "raw_data", None) or {}
        if isinstance(raw_data, dict):
            attachments = raw_data.get("attachments") or []
        else:
            attachments = []
        if not attachments:
            return []
        out = []
        for att in attachments:
            out.append({
                "source_file_id": att.get("id"),
                "file_name": att.get("filename"),
                "file_url": att.get("content"),
                "file_type": att.get("mimeType"),
                "file_size": att.get("size"),
                "source_created_at": att.get("created"),
                "source_updated_at": att.get("updated"),
            })
        return out

    def download_attachment_content(
        self,
        auth_config: dict,
        attachment_meta: dict,
    ) -> bytes | None:
        """Download attachment from Jira URL (authenticated session)."""
        url = attachment_meta.get("file_url") or attachment_meta.get("content")
        if not url:
            return None
        try:
            jira = _client(auth_config)
            resp = jira._session.get(url)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            u = url[:80]
            logger.warning(
                f"Jira download_attachment_content failed url={u}: {e}"
            )
            return None
