import pytest

from data_ops.models import SyncCursor, SyncTableStatus
from data_ops.serializers import (
    SyncCursorSerializer,
    SyncTableStatusSerializer,
)


@pytest.mark.django_db
def test_sync_table_status_serializer_does_not_expose_feishu_ids():
    status = SyncTableStatus.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="secret_app_token",
        table_id="secret_table_id",
        table_name="Contracts",
    )

    data = SyncTableStatusSerializer(status).data

    assert "app_token" not in data
    assert "table_id" not in data


@pytest.mark.django_db
def test_sync_cursor_serializer_does_not_expose_feishu_ids():
    cursor = SyncCursor.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="secret_app_token",
        table_id="secret_table_id",
        table_name="Contracts",
    )

    data = SyncCursorSerializer(cursor).data

    assert "app_token" not in data
    assert "table_id" not in data
