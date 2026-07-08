from __future__ import annotations

from dataclasses import dataclass

import httpx
from django.utils import timezone

from data_ops.models import SyncIssueCode, SyncStatus, SyncTableStatus

from .global_config import get_feishu_credentials
from .mappings import iter_bitable_tables


FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


@dataclass
class FeishuCheckResult:
    status: str
    issue_code: str = ""
    message: str = ""
    resolution_hint: str = ""
    record_count: int = 0
    expected_fields: list[str] | None = None
    missing_fields: list[str] | None = None
    expected_min_records: int | None = None


def _settings_missing_result() -> FeishuCheckResult:
    return FeishuCheckResult(
        status=SyncStatus.FAILED,
        issue_code=SyncIssueCode.CONFIG_MISSING,
        message="飞书应用配置缺失，无法检查多维表格权限。",
        resolution_hint=(
            "请配置 DATA_OPS_FEISHU_APP_ID 和 "
            "DATA_OPS_FEISHU_APP_SECRET。"
        ),
    )


def _classify_feishu_error(
    *,
    table_name: str,
    stage: str,
    response: httpx.Response | None = None,
    exc: Exception | None = None,
) -> FeishuCheckResult:
    if exc is not None:
        if "pagination incomplete" in str(exc).lower():
            return FeishuCheckResult(
                status=SyncStatus.FAILED,
                issue_code=SyncIssueCode.PAGINATION_INCOMPLETE,
                message=(
                    f"飞书多维表格「{table_name}」"
                    f"{stage}分页读取不完整。"
                ),
                resolution_hint=(
                    "请重试同步；若持续失败，"
                    "请检查飞书 API 返回和应用权限。"
                ),
            )
        if isinstance(exc, ValueError) and "credentials" in str(exc):
            return _settings_missing_result()
        return FeishuCheckResult(
            status=SyncStatus.FAILED,
            issue_code=SyncIssueCode.NETWORK_ERROR,
            message=(
                f"飞书多维表格「{table_name}」"
                f"{stage}失败：{exc}"
            ),
            resolution_hint=(
                "请检查网络连通性、飞书开放平台服务"
                "和代理配置。"
            ),
        )

    payload = {}
    if response is not None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}

    code = payload.get("code")
    msg = payload.get("msg") or payload.get("message") or ""
    status_code = response.status_code if response is not None else 0
    text = f"{code} {msg}".lower()
    permission_markers = (
        "permission",
        "scope",
        "forbidden",
        "access denied",
        "no permission",
        "125403",
        "403",
        "权限",
        "无权",
    )

    if status_code in {401, 403} or any(
        marker in text for marker in permission_markers
    ):
        issue_code = (
            SyncIssueCode.FIELD_ACCESS_DENIED
            if stage == "字段读取"
            else SyncIssueCode.TABLE_ACCESS_DENIED
        )
        return FeishuCheckResult(
            status=SyncStatus.FAILED,
            issue_code=issue_code,
            message=(
                f"飞书多维表格「{table_name}」{stage}权限不足。"
                f"飞书返回：{msg or status_code}"
            ),
            resolution_hint=(
                "请确认飞书应用已添加到该多维表格，并授予"
                "多维表格、数据表记录和字段读取权限。"
            ),
        )

    if stage == "tenant token 获取":
        return FeishuCheckResult(
            status=SyncStatus.FAILED,
            issue_code=SyncIssueCode.TOKEN_ERROR,
            message=(
                "飞书 tenant access token 获取失败："
                f"{msg or status_code}"
            ),
            resolution_hint=(
                "请检查飞书应用 ID、Secret 和应用启用状态。"
            ),
        )

    return FeishuCheckResult(
        status=SyncStatus.FAILED,
        issue_code=SyncIssueCode.UNKNOWN,
        message=(
            f"飞书多维表格「{table_name}」{stage}失败。"
            f"飞书返回：{msg or status_code}"
        ),
        resolution_hint=(
            "请检查飞书应用权限、表格 ID 和服务状态。"
        ),
    )


class FeishuBitableClient:
    def __init__(self, *, app_id: str = "", app_secret: str = ""):
        if app_id or app_secret:
            self.app_id = app_id
            self.app_secret = app_secret
        else:
            self.app_id, self.app_secret = get_feishu_credentials()
        self._tenant_token = ""

    def get_tenant_access_token(self) -> str:
        if not self.app_id or not self.app_secret:
            raise ValueError("Missing Feishu app credentials")

        response = httpx.post(
            f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            },
            timeout=15,
        )
        payload = response.json()
        if response.status_code >= 400 or payload.get("code") != 0:
            raise httpx.HTTPStatusError(
                "Feishu tenant token request failed",
                request=response.request,
                response=response,
            )
        self._tenant_token = payload["tenant_access_token"]
        return self._tenant_token

    @property
    def headers(self) -> dict[str, str]:
        token = self._tenant_token or self.get_tenant_access_token()
        return {"Authorization": f"Bearer {token}"}

    def list_fields(self, app_token: str, table_id: str) -> list[str]:
        fields = []
        page_token = ""

        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            response = httpx.get(
                (
                    f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
                    f"/tables/{table_id}/fields"
                ),
                headers=self.headers,
                params=params,
                timeout=20,
            )
            payload = response.json()
            if response.status_code >= 400 or payload.get("code") != 0:
                raise httpx.HTTPStatusError(
                    "Feishu field list request failed",
                    request=response.request,
                    response=response,
                )

            data = payload.get("data", {})
            items = data.get("items", [])
            fields.extend(
                item.get("field_name", "")
                for item in items
                if item.get("field_name")
            )
            if not data.get("has_more"):
                break
            next_page_token = data.get("page_token")
            if not next_page_token:
                raise httpx.HTTPError(
                    "Feishu field list pagination incomplete"
                )
            page_token = next_page_token

        return fields

    def count_records_probe(self, app_token: str, table_id: str) -> int:
        response = httpx.get(
            (
                f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
                f"/tables/{table_id}/records"
            ),
            headers=self.headers,
            params={"page_size": 1},
            timeout=20,
        )
        payload = response.json()
        if response.status_code >= 400 or payload.get("code") != 0:
            raise httpx.HTTPStatusError(
                "Feishu record probe request failed",
                request=response.request,
                response=response,
            )
        data = payload.get("data", {})
        total = data.get("total")
        if isinstance(total, int):
            return total
        return len(data.get("items", []))

    def list_records(
        self,
        app_token: str,
        table_id: str,
        *,
        page_size: int = 500,
    ) -> tuple[list[dict], bool, int | None]:
        records = []
        page_token = ""
        total = None
        incomplete = False

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            response = httpx.get(
                (
                    f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
                    f"/tables/{table_id}/records"
                ),
                headers=self.headers,
                params=params,
                timeout=30,
            )
            payload = response.json()
            if response.status_code >= 400 or payload.get("code") != 0:
                raise httpx.HTTPStatusError(
                    "Feishu record list request failed",
                    request=response.request,
                    response=response,
                )

            data = payload.get("data", {})
            if isinstance(data.get("total"), int):
                total = data["total"]
            records.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            next_page_token = data.get("page_token")
            if not next_page_token:
                incomplete = True
                break
            page_token = next_page_token

        if total is not None and len(records) < total:
            incomplete = True
        return records, incomplete, total

    def list_record_history(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> list[dict]:
        history = []
        page_token = ""

        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            response = httpx.get(
                (
                    f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
                    f"/tables/{table_id}/records/{record_id}/record_history"
                ),
                headers=self.headers,
                params=params,
                timeout=20,
            )
            payload = response.json()
            if response.status_code >= 400 or payload.get("code") != 0:
                raise httpx.HTTPStatusError(
                    "Feishu record history request failed",
                    request=response.request,
                    response=response,
                )

            data = payload.get("data", {})
            for item in data.get("items", []):
                history.extend(item.get("fields_history", []) or [])
            if not data.get("has_more"):
                break
            next_page_token = data.get("page_token")
            if not next_page_token:
                raise httpx.HTTPError(
                    "Feishu record history pagination incomplete"
                )
            page_token = next_page_token

        return history

    def check_table_access(
        self,
        *,
        app_token: str,
        table_id: str,
        table_name: str,
        expected_fields: list[str],
    ) -> FeishuCheckResult:
        try:
            fields = self.list_fields(app_token, table_id)
        except httpx.HTTPStatusError as exc:
            return _classify_feishu_error(
                table_name=table_name,
                stage="字段读取",
                response=exc.response,
            )
        except Exception as exc:
            return _classify_feishu_error(
                table_name=table_name,
                stage="字段读取",
                exc=exc,
            )

        missing_fields = [
            field for field in expected_fields if field not in set(fields)
        ]
        if missing_fields:
            return FeishuCheckResult(
                status=SyncStatus.FAILED,
                issue_code=SyncIssueCode.FIELD_MISSING,
                message=(
                    f"飞书多维表格「{table_name}」"
                    f"缺少必要字段：{', '.join(missing_fields)}。"
                ),
                resolution_hint=(
                    "请确认表格字段未被重命名、删除，"
                    "或更新 Data Ops 字段映射配置。"
                ),
                expected_fields=expected_fields,
                missing_fields=missing_fields,
            )

        try:
            record_count = self.count_records_probe(app_token, table_id)
        except httpx.HTTPStatusError as exc:
            return _classify_feishu_error(
                table_name=table_name,
                stage="记录读取",
                response=exc.response,
            )
        except Exception as exc:
            return _classify_feishu_error(
                table_name=table_name,
                stage="记录读取",
                exc=exc,
            )

        return FeishuCheckResult(
            status=SyncStatus.OK,
            record_count=record_count,
            expected_fields=expected_fields,
            missing_fields=[],
        )


def run_bitable_access_check(
    *,
    source_key: str | None = None,
    table_key: str | None = None,
) -> list[SyncTableStatus]:
    client = FeishuBitableClient()
    now = timezone.now()
    statuses = []
    tables = list(
        iter_bitable_tables(
            include_disabled=bool(source_key and table_key),
            source_filter=source_key,
            table_filter=table_key,
        )
    )

    if not client.app_id or not client.app_secret:
        result = _settings_missing_result()
        for source_key, source, table_key, table in tables:
            statuses.append(
                _upsert_table_status(
                    source_key=source_key,
                    table_key=table_key,
                    app_token=source["app_token"],
                    table_id=table["table_id"],
                    table_name=table["name"],
                    result=result,
                    checked_at=now,
                )
            )
        return statuses

    try:
        client.get_tenant_access_token()
    except httpx.HTTPStatusError as exc:
        result = _classify_feishu_error(
            table_name="全部数据源",
            stage="tenant token 获取",
            response=exc.response,
        )
        for source_key, source, table_key, table in tables:
            statuses.append(
                _upsert_table_status(
                    source_key=source_key,
                    table_key=table_key,
                    app_token=source["app_token"],
                    table_id=table["table_id"],
                    table_name=table["name"],
                    result=result,
                    checked_at=now,
                )
            )
        return statuses
    except Exception as exc:
        result = _classify_feishu_error(
            table_name="全部数据源",
            stage="tenant token 获取",
            exc=exc,
        )
        for source_key, source, table_key, table in tables:
            statuses.append(
                _upsert_table_status(
                    source_key=source_key,
                    table_key=table_key,
                    app_token=source["app_token"],
                    table_id=table["table_id"],
                    table_name=table["name"],
                    result=result,
                    checked_at=now,
                )
            )
        return statuses

    for source_key, source, table_key, table in tables:
        result = client.check_table_access(
            app_token=source["app_token"],
            table_id=table["table_id"],
            table_name=table["name"],
            expected_fields=table.get("expected_fields", []),
        )
        result.expected_min_records = table.get("expected_min_records")
        statuses.append(
            _upsert_table_status(
                source_key=source_key,
                table_key=table_key,
                app_token=source["app_token"],
                table_id=table["table_id"],
                table_name=table["name"],
                result=result,
                checked_at=now,
            )
        )

    return statuses


def _upsert_table_status(
    *,
    source_key: str,
    table_key: str,
    app_token: str,
    table_id: str,
    table_name: str,
    result: FeishuCheckResult,
    checked_at,
) -> SyncTableStatus:
    previous = SyncTableStatus.objects.filter(
        source_key=source_key,
        table_key=table_key,
    ).first()
    expected_floor = _resolve_record_floor(previous, result)
    defaults = {
        "app_token": app_token,
        "table_id": table_id,
        "table_name": table_name,
        "status": result.status,
        "issue_code": result.issue_code,
        "message": result.message,
        "resolution_hint": result.resolution_hint,
        "expected_fields": result.expected_fields or [],
        "missing_fields": result.missing_fields or [],
        "expected_min_records": result.expected_min_records,
        "expected_record_floor": expected_floor,
        "record_count": result.record_count,
        "last_checked_at": checked_at,
    }

    if result.status == SyncStatus.OK and result.record_count < expected_floor:
        defaults.update(
            {
                "status": SyncStatus.WARNING,
                "issue_code": SyncIssueCode.ZERO_RECORDS_UNEXPECTED,
                "message": (
                    f"飞书多维表格「{table_name}」本次仅检测到 "
                    f"{result.record_count} 条记录，低于历史或"
                    f"最低预期 {expected_floor} 条。"
                ),
                "resolution_hint": (
                    "请确认飞书应用的数据表记录读取权限、"
                    "视图过滤、表格共享范围和源表数据"
                    "是否完整。"
                ),
            }
        )

    if defaults["status"] == SyncStatus.OK:
        defaults["last_success_at"] = checked_at

    status, _ = SyncTableStatus.objects.update_or_create(
        source_key=source_key,
        table_key=table_key,
        defaults=defaults,
    )
    return status


def _resolve_record_floor(
    previous: SyncTableStatus | None,
    result: FeishuCheckResult,
) -> int:
    previous_floor = previous.expected_record_floor if previous else 0
    previous_count = previous.record_count if previous else 0
    configured_floor = result.expected_min_records or 0
    floor = max(configured_floor, previous_floor, previous_count)
    if result.status == SyncStatus.OK and result.record_count >= floor:
        return max(floor, result.record_count)
    return floor
