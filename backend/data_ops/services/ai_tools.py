from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import Avg, Count, Max, Min, Sum

from data_ops.models import (
    Contract,
    DomesticLedger,
    FeishuBitableCollectionConfig,
    OverseaProject,
    OverseaSettlement,
    Project,
    ProjectInit,
    SalesRecord,
    SourceRecordChange,
    SyncJob,
    SyncTableStatus,
)
from data_ops.services.metrics.overview import _number


MAX_TOOL_ROWS = 100
DEFAULT_TOOL_ROWS = 30


DATA_OPS_QUERY_TABLES: dict[str, type[models.Model]] = {
    "contracts": Contract,
    "sales_records": SalesRecord,
    "domestic_ledgers": DomesticLedger,
    "project_inits": ProjectInit,
    "projects": Project,
    "oversea_projects": OverseaProject,
    "oversea_settlements": OverseaSettlement,
    "sync_table_status": SyncTableStatus,
    "sync_jobs": SyncJob,
    "feishu_collection_configs": FeishuBitableCollectionConfig,
    "record_changes": SourceRecordChange,
}

SENSITIVE_FIELDS = {
    "raw_data",
    "source_app_token",
    "source_table_id",
    "app_token",
    "table_id",
    "celery_task_id",
    "locked_by",
}

LOOKUP_MAP = {
    "eq": "",
    "exact": "",
    "contains": "__icontains",
    "gte": "__gte",
    "lte": "__lte",
    "gt": "__gt",
    "lt": "__lt",
    "in": "__in",
    "isnull": "__isnull",
}

AGGREGATE_MAP = {
    "count": Count,
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


DATA_OPS_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "data_ops_get_schema",
            "description": "查看 Data Ops 可查询表和字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": (
                            "可选表名，不传则返回所有表。"
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "data_ops_query_records",
            "description": (
                "按字段筛选 Data Ops 记录，适合明细查询。"
            ),
            "parameters": {
                "type": "object",
                "required": ["table"],
                "properties": {
                    "table": {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["field", "op", "value"],
                            "properties": {
                                "field": {"type": "string"},
                                "op": {"type": "string"},
                                "value": {},
                            },
                        },
                    },
                    "order_by": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "data_ops_aggregate",
            "description": "对 Data Ops 表做分组和聚合计算。",
            "parameters": {
                "type": "object",
                "required": ["table", "metrics"],
                "properties": {
                    "table": {"type": "string"},
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["op"],
                            "properties": {
                                "op": {"type": "string"},
                                "field": {"type": "string"},
                                "alias": {"type": "string"},
                            },
                        },
                    },
                    "filters": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "order_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "可按分组字段或指标 alias 排序，"
                            "降序加 -。"
                        ),
                    },
                    "limit": {"type": "integer"},
                },
            },
        },
    },
]


def get_data_ops_tool_profile() -> dict[str, Any]:
    return {
        "tools": [
            item["function"]["name"] for item in DATA_OPS_TOOL_SCHEMAS
        ],
        "tables": get_data_ops_schema()["tables"],
        "query_rules": [
            "只能使用 Data Ops 工具 schema 中公开的表和字段。",
            "明细查询使用 data_ops_query_records。",
            "分组、排行、统计和 Top 项使用 data_ops_aggregate。",
            (
                "分析同步后的新增、修改、删除或"
                "恢复数据时，查询 record_changes。"
            ),
            (
                "禁止读取 raw_data、token、secret、"
                "celery_task_id 等字段。"
            ),
            (
                f"默认最多返回 {DEFAULT_TOOL_ROWS} 行，"
                f"最多 {MAX_TOOL_ROWS} 行。"
            ),
        ],
    }


def get_data_ops_schema(table: str | None = None) -> dict[str, Any]:
    if table:
        return {"tables": [_table_schema(table)]}
    return {
        "tables": [
            _table_schema(item)
            for item in sorted(DATA_OPS_QUERY_TABLES.keys())
        ],
    }


def execute_data_ops_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    handlers = {
        "data_ops_get_schema": lambda value: get_data_ops_schema(
            value.get("table"),
        ),
        "data_ops_query_records": query_data_ops_records,
        "data_ops_aggregate": aggregate_data_ops_records,
    }
    if name not in handlers:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        result = handlers[name](arguments or {})
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "result": result}


def query_data_ops_records(arguments: dict[str, Any]) -> dict[str, Any]:
    table = _require_table(arguments.get("table"))
    model = DATA_OPS_QUERY_TABLES[table]
    columns = _normalize_columns(model, arguments.get("columns"))
    queryset = _filtered_queryset(model, arguments.get("filters") or [])
    order_by = str(arguments.get("order_by") or "").strip()
    if order_by:
        queryset = queryset.order_by(_normalize_order_by(model, order_by))
    rows = list(
        queryset.values(*columns)[: _normalize_limit(arguments.get("limit"))],
    )
    return {
        "table": table,
        "columns": columns,
        "rows": [_json_safe_row(row) for row in rows],
        "row_count": len(rows),
    }


def aggregate_data_ops_records(arguments: dict[str, Any]) -> dict[str, Any]:
    table = _require_table(arguments.get("table"))
    model = DATA_OPS_QUERY_TABLES[table]
    queryset = _filtered_queryset(model, arguments.get("filters") or [])
    group_by = [
        _require_field(model, field)
        for field in arguments.get("group_by") or []
    ]
    metrics = _build_metrics(model, arguments.get("metrics") or [])
    if not metrics:
        raise ValueError("metrics is required")
    if group_by:
        order_by = _normalize_aggregate_order_by(
            arguments.get("order_by"),
            group_by,
            list(metrics.keys()),
        )
        rows = (
            queryset.values(*group_by)
            .annotate(**metrics)
            .order_by(*(order_by or group_by))
        )
        result_rows = list(rows[: _normalize_limit(arguments.get("limit"))])
        return {
            "table": table,
            "group_by": group_by,
            "rows": [_json_safe_row(row) for row in result_rows],
            "row_count": len(result_rows),
        }
    return {
        "table": table,
        "metrics": _json_safe_row(queryset.aggregate(**metrics)),
    }


def _table_schema(table: str) -> dict[str, Any]:
    model = DATA_OPS_QUERY_TABLES[_require_table(table)]
    return {
        "name": table,
        "db_table": model._meta.db_table,
        "fields": [
            {
                "name": field.name,
                "type": field.get_internal_type(),
            }
            for field in model._meta.fields
            if _field_allowed(field.name)
        ],
    }


def _require_table(value: Any) -> str:
    table = str(value or "").strip()
    if table not in DATA_OPS_QUERY_TABLES:
        raise ValueError(f"table is not allowed: {table}")
    return table


def _field_allowed(field_name: str) -> bool:
    return field_name not in SENSITIVE_FIELDS


def _require_field(model: type[models.Model], value: Any) -> str:
    field_name = str(value or "").strip()
    allowed = {
        field.name
        for field in model._meta.fields
        if _field_allowed(field.name)
    }
    if field_name not in allowed:
        raise ValueError(f"field is not allowed: {field_name}")
    return field_name


def _normalize_columns(
    model: type[models.Model],
    columns: list[str] | None,
) -> list[str]:
    if not columns:
        return [
            field.name
            for field in model._meta.fields
            if _field_allowed(field.name)
        ][:12]
    return [_require_field(model, item) for item in columns]


def _filtered_queryset(
    model: type[models.Model],
    filters: list[dict[str, Any]],
):
    queryset = model.objects.all()
    for item in filters:
        if not isinstance(item, dict):
            raise ValueError("filter must be an object")
        field = _require_field(model, item.get("field"))
        op = str(item.get("op") or "eq").strip().lower()
        if op not in LOOKUP_MAP:
            raise ValueError(f"filter op is not allowed: {op}")
        queryset = queryset.filter(
            **{f"{field}{LOOKUP_MAP[op]}": item.get("value")},
        )
    return queryset


def _normalize_order_by(model: type[models.Model], value: str) -> str:
    descending = value.startswith("-")
    field_name = value[1:] if descending else value
    field_name = _require_field(model, field_name)
    return f"-{field_name}" if descending else field_name


def _build_metrics(
    model: type[models.Model],
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    output = {}
    for index, item in enumerate(metrics):
        if not isinstance(item, dict):
            raise ValueError("metric must be an object")
        op = str(item.get("op") or "").strip().lower()
        if op not in AGGREGATE_MAP:
            raise ValueError(f"metric op is not allowed: {op}")
        field = item.get("field") or "id"
        field_name = _require_field(model, field)
        alias = str(item.get("alias") or f"{op}_{field_name}_{index}")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$", alias):
            raise ValueError(f"metric alias is not allowed: {alias}")
        output[alias] = AGGREGATE_MAP[op](field_name)
    return output


def _normalize_aggregate_order_by(
    value: Any,
    group_by: list[str],
    metric_aliases: list[str],
) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    allowed = set(group_by) | set(metric_aliases)
    order_by = []
    for item in items:
        raw = str(item or "").strip()
        descending = raw.startswith("-")
        field_name = raw[1:] if descending else raw
        if field_name not in allowed:
            raise ValueError(f"order_by is not allowed: {raw}")
        order_by.append(f"-{field_name}" if descending else field_name)
    return order_by


def _normalize_limit(value: Any) -> int:
    try:
        limit = int(value or DEFAULT_TOOL_ROWS)
    except (TypeError, ValueError):
        limit = DEFAULT_TOOL_ROWS
    return max(1, min(limit, MAX_TOOL_ROWS))


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe_value(value) for key, value in row.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _number(value)
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except TypeError:
        return str(value)
