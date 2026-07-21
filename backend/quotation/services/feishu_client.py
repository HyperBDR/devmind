from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from time import perf_counter
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from django.conf import settings as dj_settings

from quotation.audit import AUDIT_CONTEXT
from quotation.metrics import record_storage_operation


logger = logging.getLogger(__name__)


@contextmanager
def _external_call(operation: str, storage_connection_id: str = ""):
    """Log one sanitized Feishu call with request correlation fields."""
    started = perf_counter()
    context = AUDIT_CONTEXT.get()
    result = "success"
    error_code = ""
    try:
        yield
    except Exception as exc:
        result = "failed"
        code = getattr(exc, "code", None)
        error_code = (
            f"feishu_{code}" if code is not None else "transport_error"
        )
        raise
    finally:
        duration_seconds = perf_counter() - started
        record_storage_operation(
            provider="feishu",
            operation=operation,
            result=result,
            duration_seconds=duration_seconds,
        )
        logger.info(
            "quotation_external_call",
            extra={
                "provider": "feishu",
                "operation": operation,
                "result": result,
                "duration_ms": round(duration_seconds * 1000),
                "error_code": error_code,
                "storage_connection_id": storage_connection_id,
                "request_id": context.get("request_id", ""),
                "trace_id": context.get("trace_id", ""),
            },
        )


def _feishu_settings() -> SimpleNamespace:
    return SimpleNamespace(
        feishu_app_id=dj_settings.FEISHU_APP_ID,
        feishu_app_secret=dj_settings.FEISHU_APP_SECRET,
        feishu_base_url=dj_settings.FEISHU_BASE_URL,
        feishu_oauth_redirect_uri=dj_settings.FEISHU_OAUTH_REDIRECT_URI,
        feishu_oauth_scopes=dj_settings.FEISHU_OAUTH_SCOPES,
    )


class FeishuAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


@dataclass
class FeishuTokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    scope: str = ""


FOLDER_URL_RE = re.compile(
    r"/(?:drive/folder|folder)/(?P<token>[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
FILE_URL_RE = re.compile(
    r"/(?:file|sheets|docx|wiki|drive/file)/(?P<token>[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def extract_feishu_token_from_url(url_or_token: str) -> str:
    value = (url_or_token or "").strip()
    if not value:
        raise FeishuAPIError("empty Feishu URL or token")
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value
    for pattern in (FOLDER_URL_RE, FILE_URL_RE):
        match = pattern.search(value)
        if match:
            return match.group("token")
    raise FeishuAPIError(f"cannot parse Feishu token from: {value}")


class FeishuClient:
    def __init__(self, settings=None, storage_connection_id: str = ""):
        self.settings = settings or _feishu_settings()
        self.base_url = self.settings.feishu_base_url.rstrip("/")
        self.storage_connection_id = storage_connection_id

    def _ensure_app_credentials(self) -> None:
        if (
            not self.settings.feishu_app_id
            or not self.settings.feishu_app_secret
        ):
            raise FeishuAPIError(
                "Feishu App ID / App Secret is not configured"
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        operation = f"{method.upper()} {self._operation_path(path)}"
        with _external_call(operation, self.storage_connection_id):
            headers: dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            url = f"{self.base_url}{path}"
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise FeishuAPIError(
                    f"Feishu non-JSON response ({response.status_code})"
                ) from exc
            if response.status_code >= 400:
                raise FeishuAPIError(
                    "Feishu HTTP "
                    f"{response.status_code}: {payload.get('msg') or payload}",
                    code=payload.get("code"),
                    payload=payload,
                )
            code = payload.get("code")
            if code not in (0, None):
                raise FeishuAPIError(
                    f"Feishu API error {code}: {payload.get('msg')}",
                    code=code,
                    payload=payload,
                )
            return payload

    @staticmethod
    def _operation_path(path: str) -> str:
        """Return a low-cardinality path without remote object tokens."""
        segments = []
        for segment in path.split("?")[0].split("/"):
            if not segment:
                continue
            if segment.isdigit() or len(segment) >= 20:
                segments.append("{id}")
            else:
                segments.append(segment)
        return "/" + "/".join(segments)

    def get_tenant_access_token(self) -> str:
        self._ensure_app_credentials()
        payload = self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json_body={
                "app_id": self.settings.feishu_app_id,
                "app_secret": self.settings.feishu_app_secret,
            },
        )
        token = payload.get("tenant_access_token")
        if not token:
            raise FeishuAPIError(
                "tenant_access_token missing in response", payload=payload
            )
        return token

    def build_user_oauth_url(self, state: str) -> str:
        self._ensure_app_credentials()
        query = urlencode(
            {
                "app_id": self.settings.feishu_app_id,
                "redirect_uri": self.settings.feishu_oauth_redirect_uri,
                "scope": self.settings.feishu_oauth_scopes,
                "state": state,
            }
        )
        return f"{self.base_url}/open-apis/authen/v1/authorize?{query}"

    def exchange_code_for_user_token(self, code: str) -> FeishuTokenBundle:
        app_token = self.get_tenant_access_token()
        payload = self._request(
            "POST",
            "/open-apis/authen/v2/oauth/token",
            token=app_token,
            json_body={
                "grant_type": "authorization_code",
                "client_id": self.settings.feishu_app_id,
                "client_secret": self.settings.feishu_app_secret,
                "code": code,
                "redirect_uri": self.settings.feishu_oauth_redirect_uri,
            },
        )
        data = payload.get("data") or payload
        access_token = data.get("access_token")
        if not access_token:
            # Fallback to older authen/v1/access_token shape
            payload = self._request(
                "POST",
                "/open-apis/authen/v1/access_token",
                token=app_token,
                json_body={"grant_type": "authorization_code", "code": code},
            )
            data = payload.get("data") or {}
            access_token = data.get("access_token")
        if not access_token:
            raise FeishuAPIError(
                "access_token missing after OAuth exchange", payload=payload
            )
        return FeishuTokenBundle(
            access_token=access_token,
            refresh_token=data.get("refresh_token") or "",
            expires_in=int(data.get("expires_in") or 7200),
            token_type=data.get("token_type") or "Bearer",
            scope=data.get("scope") or "",
        )

    def refresh_user_token(self, refresh_token: str) -> FeishuTokenBundle:
        app_token = self.get_tenant_access_token()
        try:
            payload = self._request(
                "POST",
                "/open-apis/authen/v2/oauth/token",
                token=app_token,
                json_body={
                    "grant_type": "refresh_token",
                    "client_id": self.settings.feishu_app_id,
                    "client_secret": self.settings.feishu_app_secret,
                    "refresh_token": refresh_token,
                },
            )
            data = payload.get("data") or payload
        except FeishuAPIError:
            payload = self._request(
                "POST",
                "/open-apis/authen/v1/refresh_access_token",
                token=app_token,
                json_body={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            data = payload.get("data") or {}
        access_token = data.get("access_token")
        if not access_token:
            raise FeishuAPIError(
                "access_token missing after refresh", payload=payload
            )
        return FeishuTokenBundle(
            access_token=access_token,
            refresh_token=data.get("refresh_token") or refresh_token,
            expires_in=int(data.get("expires_in") or 7200),
            token_type=data.get("token_type") or "Bearer",
            scope=data.get("scope") or "",
        )

    def get_user_info(self, user_access_token: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            "/open-apis/authen/v1/user_info",
            token=user_access_token,
        )
        return payload.get("data") or {}

    def get_root_folder_meta(self, user_access_token: str) -> dict[str, Any]:
        """Return the user's My Space root folder metadata."""
        payload = self._request(
            "GET",
            "/open-apis/drive/explorer/v2/root_folder/meta",
            token=user_access_token,
        )
        return payload.get("data") or {}

    def get_folder_meta(
        self,
        user_access_token: str,
        folder_token: str,
    ) -> dict[str, Any]:
        """Return folder metadata for My Space or shared folders."""
        token = quote(folder_token, safe="")
        payload = self._request(
            "GET",
            f"/open-apis/drive/explorer/v2/folder/{token}/meta",
            token=user_access_token,
        )
        return payload.get("data") or {}

    def list_folder_files(
        self,
        user_access_token: str,
        folder_token: str,
        *,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "folder_token": folder_token,
            "page_size": page_size,
        }
        if page_token:
            params["page_token"] = page_token
        payload = self._request(
            "GET",
            "/open-apis/drive/v1/files",
            token=user_access_token,
            params=params,
        )
        return payload.get("data") or {}

    def batch_query_files_meta(
        self,
        user_access_token: str,
        file_tokens: list[str],
        *,
        doc_type: str = "file",
        with_url: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Resolve metadata for multiple drive files via batch_query.
        """
        tokens = [
            str(token or "").strip()
            for token in file_tokens
            if str(token or "").strip()
        ]
        if not tokens:
            return [], []
        payload = self._request(
            "POST",
            "/open-apis/drive/v1/metas/batch_query",
            token=user_access_token,
            json_body={
                "request_docs": [
                    {
                        "doc_token": token,
                        "doc_type": doc_type,
                    }
                    for token in tokens
                ],
                "with_url": with_url,
            },
        )
        data = payload.get("data") or {}
        metas = data.get("metas") or []
        failed_list = data.get("failed_list") or []
        return metas, failed_list

    def batch_query_file_meta(
        self,
        user_access_token: str,
        file_token: str,
        *,
        doc_type: str = "file",
        with_url: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve file metadata via drive batch_query.

        Uploaded pdf/xlsx use doc_type=file.
        """
        metas, failed_list = self.batch_query_files_meta(
            user_access_token,
            [file_token],
            doc_type=doc_type,
            with_url=with_url,
        )
        if metas:
            return metas[0]
        for item in failed_list:
            if str(item.get("token") or "") == file_token:
                raise FeishuAPIError(
                    f"meta query failed code={item.get('code')}",
                    code=item.get("code"),
                    payload=item if isinstance(item, dict) else {},
                )
        raise FeishuAPIError(
            "meta query returned no result",
            payload={},
        )

    def download_file(
        self, user_access_token: str, file_token: str
    ) -> tuple[bytes, str | None]:
        path = f"/open-apis/drive/v1/files/{quote(file_token)}/download"
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {user_access_token}"}
        with _external_call(
            "GET drive.file.download",
            self.storage_connection_id,
        ):
            with httpx.Client(timeout=60.0) as client:
                response = client.get(url, headers=headers)
            if response.status_code >= 400:
                try:
                    payload = response.json()
                except Exception:  # noqa: BLE001
                    payload = {"msg": response.text}
                raise FeishuAPIError(
                    "download failed HTTP "
                    f"{response.status_code}: {payload.get('msg') or payload}",
                    code=(
                        payload.get("code")
                        if isinstance(payload, dict)
                        else None
                    ),
                    payload=payload if isinstance(payload, dict) else {},
                )
            content_type = response.headers.get("content-type")
            return response.content, content_type

    def export_and_download(
        self,
        user_access_token: str,
        *,
        token: str,
        doc_type: str,
        file_extension: str,
    ) -> tuple[bytes, str | None]:
        """Export online docs/sheets then download the exported binary."""
        create_payload = self._request(
            "POST",
            "/open-apis/drive/v1/export_tasks",
            token=user_access_token,
            json_body={
                "file_extension": file_extension,
                "token": token,
                "type": doc_type,
            },
        )
        ticket = (create_payload.get("data") or {}).get("ticket")
        if not ticket:
            raise FeishuAPIError(
                "export ticket missing", payload=create_payload
            )

        export_file_token = None
        for _ in range(20):
            status_payload = self._request(
                "GET",
                f"/open-apis/drive/v1/export_tasks/{quote(ticket)}",
                token=user_access_token,
                params={"token": token},
            )
            result = (status_payload.get("data") or {}).get("result") or {}
            job_status = result.get("job_status")
            # 0 success, 1/2 processing, others failed
            if job_status == 0:
                export_file_token = result.get("file_token")
                break
            if job_status not in (1, 2, None):
                raise FeishuAPIError(
                    f"export failed status={job_status}: "
                    f"{result.get('job_error_msg') or result}",
                    payload=status_payload,
                )
            import time

            time.sleep(0.8)

        if not export_file_token:
            raise FeishuAPIError("export timed out waiting for file_token")

        path = (
            "/open-apis/drive/v1/export_tasks/file/"
            f"{quote(export_file_token)}/download"
        )
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {user_access_token}"}
        with _external_call(
            "GET drive.export.download",
            self.storage_connection_id,
        ):
            with httpx.Client(timeout=120.0) as client:
                response = client.get(url, headers=headers)
            if response.status_code >= 400:
                try:
                    payload = response.json()
                except Exception:  # noqa: BLE001
                    payload = {"msg": response.text}
                raise FeishuAPIError(
                    "export download failed HTTP "
                    f"{response.status_code}: "
                    f"{payload.get('msg') or payload}",
                    code=(
                        payload.get("code")
                        if isinstance(payload, dict)
                        else None
                    ),
                    payload=payload if isinstance(payload, dict) else {},
                )
            return response.content, response.headers.get("content-type")

    def download_drive_item(
        self,
        user_access_token: str,
        *,
        file_token: str,
        file_type: str | None = None,
        file_name: str | None = None,
    ) -> tuple[bytes, str | None, str]:
        """
        Download uploaded files directly; export online sheet/doc first.
        Returns (content, mime_type, resolved_file_name).
        """
        normalized_type = (file_type or "").strip().lower()
        name = file_name or file_token

        if normalized_type in {"sheet", "sheets", "spreadsheet"}:
            content, mime = self.export_and_download(
                user_access_token,
                token=file_token,
                doc_type="sheet",
                file_extension="xlsx",
            )
            if not name.lower().endswith(".xlsx"):
                name = f"{name}.xlsx"
            return (
                content,
                mime
                or (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                name,
            )

        if normalized_type in {"docx", "doc"}:
            content, mime = self.export_and_download(
                user_access_token,
                token=file_token,
                doc_type="docx",
                file_extension="pdf",
            )
            if not name.lower().endswith(".pdf"):
                name = f"{name}.pdf"
            return content, mime or "application/pdf", name

        # Default: binary file in drive (pdf/xlsx uploads, etc.)
        try:
            content, mime = self.download_file(user_access_token, file_token)
            return content, mime, name
        except FeishuAPIError as exc:
            # Fallback: some "file-like" items still need export.
            if (
                normalized_type in {"", "file"}
                and "download failed" in str(exc).lower()
            ):
                # Try sheet export as a last resort for spreadsheet tokens.
                content, mime = self.export_and_download(
                    user_access_token,
                    token=file_token,
                    doc_type="sheet",
                    file_extension="xlsx",
                )
                if not name.lower().endswith(
                    (".xlsx", ".pdf", ".doc", ".docx")
                ):
                    name = f"{name}.xlsx"
                return content, mime, name
            raise

    def upload_file(
        self,
        user_access_token: str,
        *,
        folder_token: str,
        file_name: str,
        content: bytes,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/open-apis/drive/v1/files/upload_all"
        headers = {"Authorization": f"Bearer {user_access_token}"}
        files = {
            "file": (file_name, content, "application/octet-stream"),
        }
        data = {
            "file_name": file_name,
            "parent_type": "explorer",
            "parent_node": folder_token,
            "size": str(len(content)),
        }
        with _external_call(
            "POST drive.file.upload",
            self.storage_connection_id,
        ):
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    url, headers=headers, data=data, files=files
                )
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise FeishuAPIError(
                    f"upload non-JSON response ({response.status_code})"
                ) from exc
            if (
                response.status_code >= 400
                or payload.get("code") not in (0, None)
            ):
                raise FeishuAPIError(
                    f"upload failed: {payload.get('msg') or payload}",
                    code=payload.get("code"),
                    payload=payload,
                )
            return payload.get("data") or {}

    def delete_file(self, user_access_token: str, file_token: str) -> None:
        self._request(
            "DELETE",
            f"/open-apis/drive/v1/files/{quote(file_token)}",
            token=user_access_token,
            params={"type": "file"},
        )

    def search_documents(
        self,
        user_access_token: str,
        *,
        search_key: str,
        count: int = 50,
        offset: int = 0,
        docs_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Search cloud docs visible to the user (includes shared files).

        Uses Feishu suite docs search API.
        """
        body: dict[str, Any] = {
            "search_key": search_key,
            "count": max(1, min(int(count), 50)),
            "offset": max(0, int(offset)),
            "docs_types": docs_types
            or ["doc", "sheet", "bitable", "mindnote", "file", "slides"],
        }
        payload = self._request(
            "POST",
            "/open-apis/suite/docs-api/search/object",
            token=user_access_token,
            json_body=body,
        )
        return payload.get("data") or {}

    def search_folders(
        self,
        user_access_token: str,
        *,
        query: str,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Discover folders visible to the user via Search v2.
        Requires search:docs:read user scope.
        """
        payload = self._request(
            "POST",
            "/open-apis/search/v2/doc_wiki/search",
            token=user_access_token,
            json_body={
                "query": query,
                "page_size": max(1, min(int(page_size), 20)),
                "doc_filter": {"doc_types": ["FOLDER"]},
            },
        )
        data = payload.get("data") or {}
        results = []
        for item in data.get("res_units") or []:
            meta = item.get("result_meta") or {}
            token = str(meta.get("token") or "").strip()
            title = item.get("title_highlighted") or meta.get("title") or token
            doc_type = str(meta.get("doc_types") or "").upper()
            if not token:
                continue
            if doc_type and doc_type != "FOLDER":
                continue
            results.append(
                {
                    "token": token,
                    "name": str(title)
                    .replace("<em>", "")
                    .replace("</em>", "")
                    .replace("<h>", "")
                    .replace("</h>", ""),
                    "type": "folder",
                }
            )
        return results


def token_expires_at(expires_in: int, *, skew_seconds: int = 60) -> datetime:
    return datetime.utcnow() + timedelta(
        seconds=max(expires_in - skew_seconds, 60)
    )
