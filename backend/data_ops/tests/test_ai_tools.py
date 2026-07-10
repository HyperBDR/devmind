from decimal import Decimal

import pytest

from data_ops.models import Contract, DomesticLedger
from data_ops.services.ai_tools import (
    execute_data_ops_tool,
    get_data_ops_schema,
    query_data_ops_records,
    run_data_ops_sql,
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


@pytest.mark.django_db
def test_run_sql_allows_read_only_custom_calculation():
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger-1",
        ledger_type="收入",
        customer_name="Acme",
        currency="CNY",
        outstanding=Decimal("60.00"),
    )

    result = run_data_ops_sql(
        {
            "sql": (
                "SELECT customer_name, SUM(outstanding) AS outstanding "
                "FROM data_ops_domesticledger "
                "GROUP BY customer_name"
            ),
        },
    )

    assert result["row_count"] == 1
    assert result["rows"][0]["customer_name"] == "Acme"
    assert result["rows"][0]["outstanding"] == 60
    assert result["sql"].endswith("LIMIT 30")


@pytest.mark.django_db
def test_run_sql_rejects_mutation_and_sensitive_fields():
    with pytest.raises(ValueError, match="only SELECT"):
        run_data_ops_sql({"sql": "DELETE FROM data_ops_contract"})

    with pytest.raises(ValueError, match="forbidden sensitive"):
        run_data_ops_sql(
            {
                "sql": (
                    "SELECT source_app_token "
                    "FROM data_ops_contract"
                ),
            },
        )

    with pytest.raises(ValueError, match="SELECT \\*"):
        run_data_ops_sql({"sql": "SELECT * FROM data_ops_contract"})


@pytest.mark.django_db
def test_run_sql_reports_missing_column_with_allowed_fields():
    with pytest.raises(ValueError) as exc_info:
        run_data_ops_sql(
            {
                "sql": (
                    "SELECT currency, SUM(total_amount_usd) "
                    "AS total_sales_usd FROM data_ops_salesrecord "
                    "GROUP BY currency"
                ),
            },
        )
    message = str(exc_info.value)

    assert "column does not exist" in message
    assert "data_ops_salesrecord" in message
    assert "total_amount_usd" in message


def test_schema_exposes_only_safe_fields():
    schema = get_data_ops_schema("contracts")["tables"][0]
    field_names = {field["name"] for field in schema["fields"]}

    assert "customer_name" in field_names
    assert "raw_data" not in field_names
    assert "source_app_token" not in field_names
    assert schema["db_table"] == "data_ops_contract"


def test_unknown_tool_returns_structured_error():
    result = execute_data_ops_tool("missing_tool", {})

    assert result["ok"] is False
    assert "unknown tool" in result["error"]
