from types import SimpleNamespace

from data_ops.services.metrics.owner_identities import (
    owner_payload,
    owner_payload_from_record,
)


def test_owner_payload_uses_feishu_open_id_as_stable_identity():
    payload = owner_payload(
        "Test User Alpha",
        [
            {
                "open_id": "ou_test_alpha",
                "name": "Test User Alpha",
                "en_name": "Test User Alpha",
            }
        ],
    )

    assert payload["owner_open_ids"] == ["ou_test_alpha"]
    assert payload["owner_display"] == "Test User Alpha"
    assert payload["owner_aliases"] == ["Test User Alpha"]


def test_owner_payload_from_record_uses_field_specific_identity():
    record = SimpleNamespace(
        sales_person="Test User Alpha",
        owner_identities={
            "sales_person": [
                {"open_id": "ou_test_alpha", "name": "Test User Alpha"}
            ]
        },
    )

    payload = owner_payload_from_record(record, "sales_person")

    assert payload["owner_open_ids"] == ["ou_test_alpha"]


def test_owner_payload_returns_empty_dict_for_blank_value():
    assert owner_payload("") == {}
