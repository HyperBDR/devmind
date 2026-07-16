import csv
import io
from datetime import timedelta

import pytest
from django.utils import timezone

from data_ops.models import Contract
from data_ops.services.metrics.operations import (
    _safe_int,
    _upcoming_renewals,
    list_contracts_data,
)
from data_ops.views import _csv_response


def test_safe_int_uses_default_for_invalid_values():
    assert _safe_int("bad", 20) == 20
    assert _safe_int(None, 20) == 20
    assert _safe_int("5", 20) == 5


@pytest.mark.django_db
def test_contract_customer_filter_supports_partial_name():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="contract-1",
        customer_name="Example Customer",
    )

    rows = list_contracts_data({"customer_name": "Example"})

    assert [item["customer_name"] for item in rows] == [
        "Example Customer",
    ]


@pytest.mark.django_db
def test_upcoming_renewals_excludes_expired_contracts():
    today = timezone.localdate()
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="expired",
        contract_number="EXPIRED",
        service_end=today - timedelta(days=1),
    )
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="upcoming",
        contract_number="UPCOMING",
        service_end=today + timedelta(days=10),
    )

    rows = _upcoming_renewals(today, 90)

    assert [item["contract_number"] for item in rows] == ["UPCOMING"]


@pytest.mark.django_db
def test_upcoming_renewals_uses_customer_name_contract():
    today = timezone.localdate()
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="contracts",
        source_record_id="customer-contract",
        contract_number="CUSTOMER-CONTRACT",
        customer_name="Example Customer",
        service_end=today + timedelta(days=10),
    )

    rows = _upcoming_renewals(today, 90)

    assert rows[0]["customer_name"] == "Example Customer"


def test_csv_response_uses_stable_columns_and_escapes_formulas():
    response = _csv_response(
        [
            {"name": "No owner", "amount": 1},
            {
                "name": '=HYPERLINK("https://example.test")',
                "amount": 2,
                "owner": "Test Owner",
            },
        ],
        "test.csv",
    )

    content = response.content.decode("utf-8").lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(content)))
    assert rows[0]["owner"] == ""
    assert rows[1]["owner"] == "Test Owner"
    assert rows[1]["name"].startswith("'=")
