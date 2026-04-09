import pytest

from data_collector.services.providers.ai_pricehub import AIPriceHubProvider


@pytest.mark.unit
def test_ai_pricehub_provider_collect_reuses_existing_sync(monkeypatch):
    captured = {}

    def fake_sync_configured_sources(
        *,
        platform_slug=None,
        task_id=None,
        strict_api_failure_raises=True,
    ):
        captured["platform_slug"] = platform_slug
        captured["task_id"] = task_id
        captured["strict_api_failure_raises"] = strict_api_failure_raises
        return {"accepted": True, "vendors": 3, "models": 10}

    monkeypatch.setattr(
        "ai_pricehub.services.ai_pricehub_service.sync_configured_sources",
        fake_sync_configured_sources,
    )

    provider = AIPriceHubProvider()
    items = provider.collect(
        auth_config={},
        start_time=None,
        end_time=None,
        user_id=1,
        platform="ai_pricehub",
        project_keys=["cn-main"],
    )

    assert captured["platform_slug"] == "cn-main"
    assert captured["task_id"] is None
    assert captured["strict_api_failure_raises"] is False
    assert len(items) == 1
    assert items[0]["filter_metadata"]["task_type"] == "ai_pricehub_sync"


@pytest.mark.unit
def test_ai_pricehub_provider_collect_passes_task_id(monkeypatch):
    captured = {}

    def fake_sync_configured_sources(
        *,
        platform_slug=None,
        task_id=None,
        strict_api_failure_raises=True,
    ):
        captured["platform_slug"] = platform_slug
        captured["task_id"] = task_id
        captured["strict_api_failure_raises"] = strict_api_failure_raises
        return {"accepted": True}

    monkeypatch.setattr(
        "ai_pricehub.services.ai_pricehub_service.sync_configured_sources",
        fake_sync_configured_sources,
    )

    provider = AIPriceHubProvider()
    provider.collect(
        auth_config={},
        start_time=None,
        end_time=None,
        user_id=1,
        platform="ai_pricehub",
        project_keys=["sync"],
        task_id="dc-task-001",
    )

    assert captured["platform_slug"] is None
    assert captured["task_id"] == "dc-task-001"
    assert captured["strict_api_failure_raises"] is False
