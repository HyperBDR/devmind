import pytest

from data_ops.models import (
    Contract,
    SourceRecordChange,
    SyncCursor,
    SyncStatus,
    SyncTableStatus,
)
from data_ops.services.feishu import sync
from data_ops.services.feishu.sync import _map_record, _upsert_records


@pytest.mark.django_db
def test_sync_table_rejects_missing_expected_fields_without_overwriting_data():
    existing = Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="contract-1",
        contract_number="C-001",
        customer_name="Existing Customer",
    )

    class Client:
        def list_fields(self, app_token, table_id):
            return ["合同编号"]

        def list_records(self, app_token, table_id):
            return (
                [{"record_id": "contract-1", "fields": {"合同编号": "C-001"}}],
                False,
                1,
            )

    result = sync._sync_one_table(
        client=Client(),
        source_key="domestic",
        source={"app_token": "app"},
        table_key="contracts",
        table={
            "table_id": "table",
            "name": "Contracts",
            "model": "contract",
            "expected_fields": ["合同编号", "签约对方全称"],
            "field_map": {
                "合同编号": "contract_number",
                "签约对方全称": "customer_name",
            },
        },
    )

    existing.refresh_from_db()
    assert result["status"] == SyncStatus.FAILED
    assert result["issue_code"] == "field_missing"
    assert existing.customer_name == "Existing Customer"


@pytest.mark.django_db
def test_sync_table_allows_complete_snapshot_to_remove_existing_record():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="active",
        contract_number="C-001",
    )
    removed = Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="removed",
        contract_number="C-002",
    )
    SyncTableStatus.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        table_name="Contracts",
        status=SyncStatus.OK,
        record_count=2,
        expected_record_floor=2,
    )

    class Client:
        def list_fields(self, app_token, table_id):
            return ["合同编号"]

        def list_records(self, app_token, table_id):
            return (
                [{"record_id": "active", "fields": {"合同编号": "C-001"}}],
                False,
                1,
            )

    result = sync._sync_one_table(
        client=Client(),
        source_key="domestic",
        source={"app_token": "app"},
        table_key="contracts",
        table={
            "table_id": "table",
            "name": "Contracts",
            "model": "contract",
            "expected_fields": ["合同编号"],
            "expected_min_records": 1,
            "field_map": {"合同编号": "contract_number"},
        },
    )

    removed.refresh_from_db()
    assert result["status"] == SyncStatus.OK
    assert result["deleted"] == 1
    assert removed.is_active is False


@pytest.mark.django_db
def test_upsert_records_marks_missing_source_records_inactive():
    stale = Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="stale",
        customer_name="Old Customer",
    )

    stats = _upsert_records(
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
        source_key="domestic",
        table_key="contracts",
    )

    assert stats["source_records"] == 1
    assert stats["created"] == 1
    assert stats["deleted"] == 1
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
        source_key="domestic",
        table_key="contracts",
    )

    record = Contract.objects.get(source_record_id="reactivated")
    assert record.is_active is True
    assert record.customer_name == "New Name"


@pytest.mark.django_db
def test_upsert_records_skips_unchanged_business_data():
    raw_data = {
        "合同编号": "TEST-001",
        "签约对方全称": "Example Customer Alpha",
    }
    record = Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="unchanged",
        raw_data=raw_data,
        source_content_hash=sync._build_record_content_hash(raw_data),
        source_modified_time=100,
        contract_number="TEST-001",
        customer_name="Example Customer Alpha",
    )
    previous_synced_at = record.synced_at

    stats = _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "unchanged",
                "last_modified_time": 100,
                "fields": raw_data,
            }
        ],
        field_map={
            "合同编号": "contract_number",
            "签约对方全称": "customer_name",
        },
        app_token="app",
        table_id="table",
        source_key="domestic",
        table_key="contracts",
    )

    record.refresh_from_db()
    assert stats == {
        "source_records": 1,
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "restored": 0,
        "unchanged": 1,
        "change_events": 0,
    }
    assert record.synced_at == previous_synced_at
    assert SourceRecordChange.objects.count() == 0


@pytest.mark.django_db
def test_upsert_records_logs_only_normalized_business_differences():
    old_raw_data = {
        "合同编号": "TEST-002",
        "签约对方全称": "Example Customer Alpha",
    }
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="changed",
        raw_data=old_raw_data,
        source_content_hash=sync._build_record_content_hash(old_raw_data),
        source_modified_time=100,
        contract_number="TEST-002",
        customer_name="Example Customer Alpha",
    )

    stats = _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "changed",
                "last_modified_time": 200,
                "fields": {
                    "合同编号": "TEST-002",
                    "签约对方全称": "Example Customer Beta",
                },
            }
        ],
        field_map={
            "合同编号": "contract_number",
            "签约对方全称": "customer_name",
        },
        app_token="app",
        table_id="table",
        source_key="domestic",
        table_key="contracts",
    )

    change = SourceRecordChange.objects.get()
    assert stats["updated"] == 1
    assert stats["change_events"] == 1
    assert change.change_type == "updated"
    assert change.changed_fields == ["customer_name"]
    assert change.before_values == {
        "customer_name": "Example Customer Alpha",
    }
    assert change.after_values == {
        "customer_name": "Example Customer Beta",
    }
    assert "raw_data" not in str(change.before_values)
    assert "raw_data" not in str(change.after_values)


@pytest.mark.django_db
def test_upsert_records_does_not_log_unmapped_source_only_changes():
    old_raw_data = {
        "合同编号": "TEST-005",
        "未映射字段": "old",
    }
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="source-only-change",
        raw_data=old_raw_data,
        source_content_hash=sync._build_record_content_hash(old_raw_data),
        contract_number="TEST-005",
    )

    stats = _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "source-only-change",
                "fields": {
                    "合同编号": "TEST-005",
                    "未映射字段": "new",
                },
            }
        ],
        field_map={"合同编号": "contract_number"},
        app_token="app",
        table_id="table",
        source_key="domestic",
        table_key="contracts",
    )

    record = Contract.objects.get(
        source_record_id="source-only-change",
    )
    assert stats["updated"] == 1
    assert stats["change_events"] == 0
    assert record.raw_data["未映射字段"] == "new"
    assert SourceRecordChange.objects.count() == 0


@pytest.mark.django_db
def test_initial_snapshot_does_not_create_business_change_events():
    stats = _upsert_records(
        model_name="contract",
        records=[
            {
                "record_id": "baseline",
                "last_modified_time": 100,
                "fields": {
                    "合同编号": "TEST-003",
                    "签约对方全称": "Example Customer Gamma",
                },
            }
        ],
        field_map={
            "合同编号": "contract_number",
            "签约对方全称": "customer_name",
        },
        app_token="app",
        table_id="table",
        source_key="domestic",
        table_key="contracts",
    )

    assert stats["created"] == 1
    assert stats["change_events"] == 0
    assert SourceRecordChange.objects.count() == 0


@pytest.mark.django_db
def test_sync_does_not_call_unsupported_record_history_api():
    class Client:
        def check_table_access(self, **kwargs):
            return type(
                "Check",
                (),
                {
                    "status": "ok",
                    "issue_code": "",
                    "message": "",
                    "resolution_hint": "",
                    "record_count": 1,
                    "expected_fields": [],
                    "missing_fields": [],
                    "expected_min_records": 1,
                },
            )()

        def list_records(self, app_token, table_id):
            return (
                [
                    {
                        "record_id": "rec-test",
                        "last_modified_time": 100,
                        "fields": {"合同编号": "TEST-004"},
                    }
                ],
                False,
                1,
            )

        def list_record_history(self, *args, **kwargs):
            raise AssertionError("record history API must not be called")

    result = sync._sync_one_table(
        client=Client(),
        source_key="domestic",
        source={"app_token": "app"},
        table_key="contracts",
        table={
            "table_id": "table",
            "name": "Contracts",
            "model": "contract",
            "field_map": {"合同编号": "contract_number"},
            "expected_fields": [],
            "expected_min_records": 1,
        },
    )

    assert result["status"] == "ok"


def test_map_record_preserves_feishu_owner_identity():
    values = _map_record(
        {
            "record_id": "contract-1",
            "fields": {
                "万博签约人": [
                    {
                        "id": "ou_test_alpha",
                        "name": "Test User Alpha",
                        "en_name": "Test User Alpha",
                        "email": "alpha@example.test",
                    }
                ]
            },
        },
        {"万博签约人": "sales_person"},
        "app",
        "table",
    )

    assert values["sales_person"] == "Test User Alpha"
    assert values["owner_identities"] == {
        "sales_person": [
            {
                "open_id": "ou_test_alpha",
                "name": "Test User Alpha",
                "en_name": "Test User Alpha",
            }
        ]
    }
    assert "email" not in str(values["owner_identities"])


def test_record_revision_is_stable_across_record_order():
    records = [
        {"record_id": "rec-2", "last_modified_time": 200},
        {"record_id": "rec-1", "last_modified_time": 100},
    ]

    revision = sync._build_record_revision(records)

    assert revision == sync._build_record_revision(list(reversed(records)))
    assert len(revision) == 64


def test_record_revision_falls_back_to_record_content():
    records = [{"record_id": "rec-1", "fields": {"状态": "执行中"}}]

    revision = sync._build_record_revision(records)

    assert len(revision) == 64
    records[0]["fields"]["状态"] = "已完成"
    assert sync._build_record_revision(records) != revision


def test_record_revision_detects_content_change_with_same_modified_time():
    records = [
        {
            "record_id": "rec-1",
            "last_modified_time": 100,
            "fields": {"状态": "执行中"},
        }
    ]
    revision = sync._build_record_revision(records)

    records[0]["fields"]["状态"] = "已完成"

    assert sync._build_record_revision(records) != revision


@pytest.mark.django_db
def test_conditional_sync_skips_unchanged_table(monkeypatch):
    records = [
        {
            "record_id": "rec-1",
            "last_modified_time": 100,
            "fields": {"合同编号": "C-001"},
        }
    ]
    revision = sync._build_record_revision(records)
    SyncCursor.objects.create(
        app_token="app",
        table_id="table",
        source_key="domestic",
        table_key="contracts",
        record_count=1,
        source_revision=revision,
    )

    class Client:
        def list_records(self, app_token, table_id):
            return records, False, 1

    monkeypatch.setattr(
        sync,
        "_upsert_records",
        lambda **kwargs: pytest.fail("unchanged table should not be written"),
    )

    result = sync._sync_one_table(
        client=Client(),
        source_key="domestic",
        source={"app_token": "app"},
        table_key="contracts",
        table={
            "table_id": "table",
            "name": "Contracts",
            "model": "contract",
            "field_map": {},
        },
        skip_unchanged=True,
    )

    assert result["status"] == "ok"
    assert result["records"] == 0
    assert result["source_records"] == 1
    assert result["skipped"] is True
