from decimal import Decimal

import pytest

from data_ops.models import Contract, DomesticLedger, SourceRecordChange
from data_ops.services.ai_tools import (
    DATA_OPS_TOOL_SCHEMAS,
    aggregate_data_ops_records,
    execute_data_ops_tool,
    get_data_ops_schema,
    get_data_ops_tool_profile,
    query_data_ops_records,
)


@pytest.mark.django_db
def test_query_records_filters_active_records_only():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="active",
        customer_name="Acme",
        sales_person="Alice",
        total_amount=Decimal("100.00"),
    )
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="inactive",
        customer_name="Acme",
        sales_person="Bob",
        total_amount=Decimal("900.00"),
        is_active=False,
    )

    result = query_data_ops_records(
        {
            "table": "contracts",
            "columns": ["customer_name", "sales_person", "total_amount"],
            "filters": [
                {"field": "customer_name", "op": "eq", "value": "Acme"},
            ],
        },
    )

    assert result["row_count"] == 1
    assert result["rows"][0]["sales_person"] == "Alice"
    assert result["rows"][0]["total_amount"] == 100.0


def test_tool_profile_does_not_expose_raw_sql():
    tool_names = [
        item["function"]["name"] for item in DATA_OPS_TOOL_SCHEMAS
    ]
    profile = get_data_ops_tool_profile()

    assert "data_ops_run_sql" not in tool_names
    assert "data_ops_run_sql" not in profile["tools"]
    assert "sql_rules" not in profile
    assert profile["query_rules"]
    assert any(
        "record_changes" in rule for rule in profile["query_rules"]
    )


def test_raw_sql_tool_call_returns_unknown_tool():
    result = execute_data_ops_tool(
        "data_ops_run_sql",
        {"sql": "SELECT customer_name FROM data_ops_contract"},
    )

    assert result["ok"] is False
    assert "unknown tool" in result["error"]


@pytest.mark.django_db
def test_aggregate_handles_custom_calculation_without_raw_sql():
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger-1",
        ledger_type="收入",
        customer_name="Acme",
        currency="CNY",
        outstanding=Decimal("60.00"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger-2",
        ledger_type="收入",
        customer_name="Beta",
        currency="CNY",
        outstanding=Decimal("90.00"),
    )

    result = aggregate_data_ops_records(
        {
            "table": "domestic_ledgers",
            "group_by": ["customer_name"],
            "metrics": [
                {
                    "op": "sum",
                    "field": "outstanding",
                    "alias": "outstanding",
                },
            ],
            "order_by": ["-outstanding"],
        },
    )

    assert result["row_count"] == 2
    assert result["rows"][0]["customer_name"] == "Beta"
    assert result["rows"][0]["outstanding"] == 90


def test_schema_exposes_only_safe_fields():
    schema = get_data_ops_schema("contracts")["tables"][0]
    field_names = {field["name"] for field in schema["fields"]}

    assert "customer_name" in field_names
    assert "raw_data" not in field_names
    assert "source_app_token" not in field_names
    assert schema["db_table"] == "data_ops_contract"


@pytest.mark.django_db
def test_record_changes_are_available_as_an_ai_data_source():
    SourceRecordChange.objects.create(
        source_key="domestic",
        table_key="contracts",
        model_name="contract",
        source_record_id="rec-test",
        change_type="updated",
        changed_fields=["customer_name"],
        before_values={"customer_name": "Example Customer Alpha"},
        after_values={"customer_name": "Example Customer Beta"},
    )

    result = query_data_ops_records(
        {
            "table": "record_changes",
            "columns": [
                "table_key",
                "change_type",
                "changed_fields",
                "before_values",
                "after_values",
            ],
        }
    )

    assert result["row_count"] == 1
    assert result["rows"][0]["change_type"] == "updated"
    assert result["rows"][0]["changed_fields"] == ["customer_name"]


def test_unknown_tool_returns_structured_error():
    result = execute_data_ops_tool("missing_tool", {})

    assert result["ok"] is False
    assert "unknown tool" in result["error"]
