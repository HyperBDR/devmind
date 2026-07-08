import pytest
from django.core.cache import cache

from data_ops.models import SyncJob, SyncStatus
from data_ops.services.feishu import sync


@pytest.mark.django_db
def test_run_full_sync_skips_when_global_lock_exists():
    cache.set(sync.SYNC_LOCK_KEY, "existing", timeout=60)
    job = SyncJob.objects.create(status=SyncStatus.PENDING)

    result = sync.run_full_sync(job_id=str(job.id))

    job.refresh_from_db()
    assert result["skipped"] is True
    assert result["status"] == SyncStatus.WARNING
    assert job.status == SyncStatus.WARNING
    assert "正在执行" in job.error_message
    cache.delete(sync.SYNC_LOCK_KEY)


@pytest.mark.django_db
def test_run_full_sync_releases_lock_after_success(monkeypatch):
    cache.delete(sync.SYNC_LOCK_KEY)
    monkeypatch.setattr(sync, "iter_bitable_tables", lambda **kwargs: [])

    result = sync.run_full_sync()

    assert result["status"] == SyncStatus.OK
    assert cache.get(sync.SYNC_LOCK_KEY) is None


def test_refresh_sync_lock_only_extends_current_token(monkeypatch):
    calls = []
    token = "job:token"

    monkeypatch.setattr(sync.cache, "get", lambda key: token)
    monkeypatch.setattr(
        sync.cache,
        "set",
        lambda key, value, timeout: calls.append((key, value, timeout)),
    )

    sync._refresh_sync_lock(token)

    assert calls == [(sync.SYNC_LOCK_KEY, token, sync.SYNC_LOCK_TIMEOUT)]


def test_refresh_sync_lock_does_not_overwrite_other_token(monkeypatch):
    calls = []

    monkeypatch.setattr(sync.cache, "get", lambda key: "other-token")
    monkeypatch.setattr(
        sync.cache,
        "set",
        lambda key, value, timeout: calls.append((key, value, timeout)),
    )

    sync._refresh_sync_lock("job:token")

    assert calls == []
