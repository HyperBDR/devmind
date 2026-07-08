import pytest

from data_ops.models import Contract
from data_ops.services.feishu.sync import _upsert_records


@pytest.mark.django_db
def test_upsert_records_marks_missing_source_records_inactive():
    stale = Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="stale",
        customer_name="Old Customer",
    )

    count = _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "active",
                "fields": {
                    "合同编号": "C-001",
                    "签约对方全称": "New Customer",
                },
            }
        ],
        field_map={
            "合同编号": "contract_number",
            "签约对方全称": "customer_name",
        },
        app_token="app",
        table_id="table",
    )

    assert count == 1
    stale.refresh_from_db()
    assert stale.is_active is False
    assert Contract.objects.count() == 1
    assert Contract.objects.get().source_record_id == "active"


@pytest.mark.django_db
def test_upsert_records_reactivates_previously_inactive_record():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="reactivated",
        customer_name="Old Name",
        is_active=False,
    )

    _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "reactivated",
                "fields": {"签约对方全称": "New Name"},
            }
        ],
        field_map={"签约对方全称": "customer_name"},
        app_token="app",
        table_id="table",
    )

    record = Contract.objects.get(source_record_id="reactivated")
    assert record.is_active is True
    assert record.customer_name == "New Name"
