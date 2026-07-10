from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, connection, models
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
    SyncJob,
    SyncTableStatus,
)
from data_ops.services.metrics.overview import _number


MAX_TOOL_ROWS = 100
DEFAULT_TOOL_ROWS = 30
SQL_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|"
    r"detach|pragma|vacuum|grant|revoke|copy|execute|call)\b",
    re.IGNORECASE,
)
SQL_COMMENT_PATTERN = re.compile(r"(--|/\*|\*/)")
SQL_TABLE_PATTERN = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
SQL_LIMIT_PATTERN = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)
SQL_SENSITIVE_PATTERN = re.compile(
    r"\b(raw_data|feishu_app_secret|source_app_token|source_table_id|"
    r"app_token|table_id|celery_task_id|locked_by)\b",
    re.IGNORECASE,
)
SQL_COUNT_STAR_PATTERN = re.compile(r"count\s*\(\s*\*\s*\)", re.IGNORECASE)
SQL_MISSING_COLUMN_PATTERNS = (
    re.compile(
        r'column "(?P<column>[^"]+)" does not exist',
        re.IGNORECASE,
    ),
    re.compile(
        r"no such column: (?P<column>[a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    ),
)


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
                        "description": "可选表名，不传则返回所有表。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "data_ops_query_records",
            "description": "按字段筛选 Data Ops 记录，适合明细查询。",
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
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "data_ops_run_sql",
            "description": (
                "当内置工具无法表达时执行只读 SQL。只允许 SELECT，"
                "必须使用白名单表和显式字段，禁止 SELECT *。"
            ),
            "parameters": {
                "type": "object",
                "required": ["sql"],
                "properties": {
                    "sql": {"type": "string"},
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
        "sql_rules": [
            "只允许单条 SELECT 查询。",
            "只能查询 Data Ops 白名单表。",
            "禁止 SELECT *，必须显式选择字段或 count(*) 聚合。",
            "禁止读取 raw_data、token、secret、celery_task_id 等字段。",
            f"默认最多返回 {DEFAULT_TOOL_ROWS} 行，最多 {MAX_TOOL_ROWS} 行。",
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
        "data_ops_run_sql": run_data_ops_sql,
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
        rows = (
            queryset.values(*group_by)
            .annotate(**metrics)
            .order_by(*group_by)
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


def run_data_ops_sql(arguments: dict[str, Any]) -> dict[str, Any]:
    sql = str(arguments.get("sql") or "").strip()
    limit = _normalize_limit(arguments.get("limit"))
    safe_sql = _validate_data_ops_sql(sql, limit)
    try:
        with connection.cursor() as cursor:
            cursor.execute(safe_sql)
            columns = [item[0] for item in cursor.description or []]
            if any(_is_sensitive_column(item) for item in columns):
                raise ValueError(
                    "SQL result contains forbidden sensitive columns"
                )
            rows = [
                dict(zip(columns, row))
                for row in cursor.fetchmany(limit)
            ]
    except DatabaseError as exc:
        raise ValueError(_format_sql_execution_error(safe_sql, exc)) from exc
    return {
        "sql": safe_sql,
        "columns": columns,
        "rows": [_json_safe_row(row) for row in rows],
        "row_count": len(rows),
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


def _normalize_limit(value: Any) -> int:
    try:
        limit = int(value or DEFAULT_TOOL_ROWS)
    except (TypeError, ValueError):
        limit = DEFAULT_TOOL_ROWS
    return max(1, min(limit, MAX_TOOL_ROWS))


def _validate_data_ops_sql(sql: str, limit: int) -> str:
    if not sql:
        raise ValueError("sql is required")
    if ";" in sql or SQL_COMMENT_PATTERN.search(sql):
        raise ValueError("SQL must be a single statement without comments")
    if not re.match(r"^\s*select\b", sql, re.IGNORECASE):
        raise ValueError("only SELECT SQL is allowed")
    if SQL_FORBIDDEN_PATTERN.search(sql):
        raise ValueError("SQL contains forbidden operation")
    if SQL_SENSITIVE_PATTERN.search(sql):
        raise ValueError("SQL references forbidden sensitive fields")
    selected = re.split(r"\bfrom\b", sql, maxsplit=1, flags=re.IGNORECASE)[0]
    selected_without_count = SQL_COUNT_STAR_PATTERN.sub("", selected)
    if "*" in selected_without_count:
        raise ValueError("SELECT * is not allowed")
    _validate_sql_tables(sql)
    if SQL_LIMIT_PATTERN.search(sql):
        return sql
    return f"{sql} LIMIT {limit}"


def _validate_sql_tables(sql: str) -> None:
    allowed_db_tables = {
        model._meta.db_table for model in DATA_OPS_QUERY_TABLES.values()
    }
    table_names = SQL_TABLE_PATTERN.findall(sql)
    if not table_names:
        raise ValueError("SQL must reference at least one allowed table")
    disallowed = [
        table for table in table_names if table not in allowed_db_tables
    ]
    if disallowed:
        raise ValueError(f"SQL references forbidden table: {disallowed[0]}")


def _format_sql_execution_error(sql: str, error: Exception) -> str:
    missing_column = _extract_missing_column(str(error))
    if not missing_column:
        return f"SQL execution failed: {error}"
    table_schemas = _referenced_table_schemas(sql)
    if not table_schemas:
        return f"SQL column does not exist: {missing_column}"
    return (
        f"SQL column does not exist: {missing_column}. "
        f"Allowed fields by table: {'; '.join(table_schemas)}"
    )


def _extract_missing_column(message: str) -> str:
    for pattern in SQL_MISSING_COLUMN_PATTERNS:
        match = pattern.search(message)
        if match:
            return str(match.group("column"))
    return ""


def _referenced_table_schemas(sql: str) -> list[str]:
    schema_lines = []
    seen_tables = set()
    db_tables = SQL_TABLE_PATTERN.findall(sql)
    model_map = {
        model._meta.db_table: model
        for model in DATA_OPS_QUERY_TABLES.values()
    }
    for db_table in db_tables:
        if db_table in seen_tables:
            continue
        seen_tables.add(db_table)
        model = model_map.get(db_table)
        if model is None:
            continue
        allowed_fields = ", ".join(
            field.name
            for field in model._meta.fields
            if _field_allowed(field.name)
        )
        schema_lines.append(f"{db_table}({allowed_fields})")
    return schema_lines


def _is_sensitive_column(column: str) -> bool:
    return column.lower() in {
        "raw_data",
        "feishu_app_secret",
        "source_app_token",
        "source_table_id",
        "app_token",
        "table_id",
        "celery_task_id",
        "locked_by",
    }


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
