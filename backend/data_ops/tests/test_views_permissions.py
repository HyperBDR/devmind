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
def test_preflight_returns_additive_discovery_metadata(
    api_client,
    data_ops_admin,
    monkeypatch,
):
    discovery = {
        "app_tokens": 1,
        "tables_seen": 14,
        "matched": 6,
        "updated": 6,
        "unmatched": [],
        "ambiguous": [],
        "errors": [],
        "message": "已发现并匹配飞书表。",
    }
    monkeypatch.setattr(
        "data_ops.views.discover_bitable_table_ids",
        lambda **kwargs: discovery,
    )
    monkeypatch.setattr(
        "data_ops.views.run_bitable_access_check",
        lambda **kwargs: [],
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(reverse("data-ops-preflight"))

    assert response.status_code == 200
    assert response.data["overall_status"] == "ok"
    assert response.data["discovery"] == discovery
    assert response.data["tables"] == []


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
def test_refresh_sync_dispatches_conditional_full_sync(
    api_client,
    data_ops_admin,
    monkeypatch,
):
    dispatched = {}

    def fake_delay(**kwargs):
        dispatched.update(kwargs)
        return type("Result", (), {"id": "task-id"})()

    monkeypatch.setattr(
        "data_ops.tasks.run_full_sync_task.delay",
        fake_delay,
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-sync"),
        {"force": False},
        format="json",
    )

    assert response.status_code == 202
    assert dispatched["force"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "active_status",
    [SyncStatus.PENDING, SyncStatus.RUNNING],
)
def test_full_sync_reuses_active_job(
    api_client,
    data_ops_admin,
    monkeypatch,
    active_status,
):
    active_job = SyncJob.objects.create(
        source_key="",
        table_key="",
        status=active_status,
    )
    dispatched = []
    monkeypatch.setattr(
        "data_ops.tasks.run_full_sync_task.delay",
        lambda **kwargs: dispatched.append(kwargs),
    )
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-sync"),
        {"force": True},
        format="json",
    )

    assert response.status_code == 202
    assert str(response.data["id"]) == str(active_job.id)
    assert response.data["deduplicated"] is True
    assert SyncJob.objects.count() == 1
    assert dispatched == []


@pytest.mark.django_db
def test_incremental_sync_rejects_inactive_source(api_client, data_ops_admin):
    api_client.force_authenticate(user=data_ops_admin)

    response = api_client.post(
        reverse("data-ops-sync-incremental"),
        {"source_key": "oversea"},
        format="json",
    )

    assert response.status_code == 400
    assert SyncJob.objects.count() == 0


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


def test_stream_chat_emits_progress_for_dsml_tool_calls(monkeypatch):
    from data_ops.services import ai

    monkeypatch.setattr(
        ai,
        "get_ai_context_metrics",
        lambda: {
            "contract": {"contract_count": 2},
            "ledger": {"outstanding_by_currency": [{"currency": "CNY"}]},
            "oversea_project": {"project_count": 1},
        },
    )
    monkeypatch.setattr(
        ai,
        "resolve_data_ops_llm_settings",
        lambda preferred_config_uuid="": {
            "config_uuid": "",
            "label": "test",
            "model": "test-model",
            "provider": "openai_compatible",
            "source": "test",
        },
    )
    monkeypatch.setattr(
        ai,
        "execute_data_ops_tool",
        lambda name, arguments: {
            "ok": True,
            "result": {
                "rows": [{"total_outstanding": 100}],
                "table": "domestic_ledgers",
            },
        },
    )

    calls = {"count": 0}

    def fake_call_litellm_message(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return (
                {
                    "content": (
                        '<｜｜DSML｜｜tool_calls>'
                        '<｜｜DSML｜｜invoke name="data_ops_aggregate">'
                        '<｜｜DSML｜｜parameter name="table" string="true">'
                        'domestic_ledgers'
                        '</｜｜DSML｜｜parameter>'
                        '<｜｜DSML｜｜parameter name="metrics" string="false">'
                        "[{\"op\":\"sum\",\"field\":\"outstanding\","
                        "\"alias\":\"total_outstanding\"}]"
                        '</｜｜DSML｜｜parameter>'
                        '</｜｜DSML｜｜invoke>'
                        '</｜｜DSML｜｜tool_calls>'
                    ),
                },
                {},
            )
        return ({"content": "工具结果已读取。"}, {})

    monkeypatch.setattr(
        ai,
        "_call_litellm_message",
        fake_call_litellm_message,
    )

    events = list(ai.stream_chat_with_data_ops_assistant(message="回款风险"))

    assert any(
        item.get("type") == "progress" and item.get("stage") == "tool"
        for item in events
    )
    assert {"type": "chunk", "content": "工具结果已读取。"} in events
    assert not any(
        "DSML" in str(item.get("content", ""))
        for item in events
    )
