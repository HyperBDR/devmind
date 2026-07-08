import pytest
from django.urls import reverse

from data_ops.models import (
    CollectionFrequency,
    DataOpsGlobalConfig,
    FeishuBitableCollectionConfig,
    SyncJob,
    SyncStatus,
)


@pytest.mark.django_db
def test_sync_status_allows_read_only_data_ops_user(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "accounts.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("data-ops-status"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_sync_configs_allows_data_ops_role(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("data-ops-sync-configs"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_sync_configs_allows_staff_data_ops_admin(
    api_client,
    data_ops_admin,
    monkeypatch,
):
    monkeypatch.setattr(
        "data_ops.services.feishu.config.ensure_bitable_collection_configs",
        lambda: [],
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.get(reverse("data-ops-sync-configs"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_config_trigger_marks_job_failed_when_dispatch_fails(
    api_client,
    data_ops_admin,
    monkeypatch,
):
    config = FeishuBitableCollectionConfig.objects.create(
        source_key="domestic",
        table_key="contracts",
        app_token="app",
        table_id="table",
        sync_frequency=CollectionFrequency.HOURLY,
    )
    monkeypatch.setattr(
        "data_ops.tasks.run_table_sync_task.delay",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("broker down")),
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-sync-config-trigger", args=[config.id]),
    )

    job = SyncJob.objects.get(
        source_key=config.source_key,
        table_key=config.table_key,
    )
    assert response.status_code == 503
    assert job.status == SyncStatus.FAILED
    assert "投递失败" in job.error_message


@pytest.mark.django_db
def test_global_config_allows_data_ops_role(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("data-ops-global-config"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_global_config_rejects_without_data_ops_role(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "data_ops.permissions.get_effective_feature_keys",
        lambda user: ["admin_console"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("data-ops-global-config"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_global_config_allows_staff_update(api_client, data_ops_admin):
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.patch(
        reverse("data-ops-global-config"),
        {
            "feishu_app_id": "cli_app",
            "feishu_app_secret": "cli_secret",
            "feishu_date_timezone": "Asia/Shanghai",
            "active_sync_job_timeout_hours": 5,
        },
        format="json",
    )

    config = DataOpsGlobalConfig.get_solo()
    assert response.status_code == 200
    assert response.data["feishu_app_id"] == "cli_app"
    assert response.data["has_feishu_app_secret"] is True
    assert "feishu_app_secret" not in response.data
    assert config.feishu_app_secret != "cli_secret"
    assert config.feishu_app_secret.startswith(
        DataOpsGlobalConfig.ENCRYPTED_SECRET_PREFIX,
    )
    assert config.get_feishu_app_secret() == "cli_secret"


@pytest.mark.django_db
def test_global_config_rejects_invalid_runtime_settings(
    api_client,
    data_ops_admin,
):
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.patch(
        reverse("data-ops-global-config"),
        {
            "feishu_date_timezone": "Mars/Base",
            "active_sync_job_timeout_hours": 0,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "feishu_date_timezone" in response.data
    assert "active_sync_job_timeout_hours" in response.data


@pytest.mark.django_db
def test_llm_chat_stream_returns_sse_chunks(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "accounts.permissions.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )

    def fake_stream_chat(**kwargs):
        yield {"type": "chunk", "content": "## 经营分析"}
        yield {"type": "chunk", "content": "\n| 指标 | 值 |"}
        yield {"type": "done", "ok": True, "usage": {}}

    monkeypatch.setattr(
        "data_ops.views.stream_chat_with_data_ops_assistant",
        fake_stream_chat,
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.post(
        reverse("data-ops-llm-chat-stream"),
        {"message": "看一下经营健康度"},
        format="json",
    )
    body = b"".join(response.streaming_content).decode("utf-8")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert 'data: {"type": "chunk", "content": "## 经营分析"}' in body
    assert '"type": "done"' in body
