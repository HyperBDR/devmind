import pytest
from django.contrib.auth import get_user_model

from data_collector.models import CollectorConfig

from ai_pricehub.source_config_store import (
    AI_PRICEHUB_CONFIG_KEY,
    AI_PRICEHUB_PLATFORM,
    create_primary_source_config,
    get_primary_source_config,
    get_primary_vendor_configs,
    list_primary_source_configs,
    sync_primary_sources_to_collector,
    update_primary_source_config,
)


@pytest.mark.django_db
def test_create_primary_source_config_persists_to_data_collector():
    User = get_user_model()
    user = User.objects.create_user(username="admin-pricehub")
    CollectorConfig.objects.filter(platform=AI_PRICEHUB_PLATFORM).delete()

    created = create_primary_source_config(
        {
            "platform_slug": "cn-main",
            "vendor_name": "AGIOne CN",
            "endpoint_url": "https://example.com/models",
            "currency": "CNY",
            "points_per_currency_unit": 10.0,
            "is_enabled": True,
            "notes": "seed",
        },
        owner_user=user,
    )

    assert created["id"] > 0
    row = CollectorConfig.objects.get(
        platform=AI_PRICEHUB_PLATFORM,
        key=AI_PRICEHUB_CONFIG_KEY,
    )
    assert row.user_id == user.id
    assert len((row.value or {}).get("primary_sources") or []) >= 1


@pytest.mark.django_db
def test_update_primary_source_config_updates_collector_payload():
    User = get_user_model()
    user = User.objects.create_user(username="admin-pricehub-update")
    CollectorConfig.objects.filter(platform=AI_PRICEHUB_PLATFORM).delete()

    created = create_primary_source_config(
        {
            "platform_slug": "cn-main",
            "vendor_name": "AGIOne CN",
            "endpoint_url": "https://example.com/models",
            "currency": "CNY",
            "points_per_currency_unit": 10.0,
            "is_enabled": True,
            "notes": "",
        },
        owner_user=user,
    )
    updated = update_primary_source_config(
        created["id"],
        {
            "vendor_name": "AGIOne Mainland",
            "endpoint_url": "https://example.com/new-models",
        },
        owner_user=user,
    )

    assert updated is not None
    assert updated["vendor_name"] == "AGIOne Mainland"
    assert updated["endpoint_url"] == "https://example.com/new-models"
    fetched = get_primary_source_config(created["id"])
    assert fetched is not None
    assert fetched["vendor_name"] == "AGIOne Mainland"


@pytest.mark.django_db
def test_get_primary_vendor_configs_transforms_primary_sources():
    User = get_user_model()
    user = User.objects.create_user(username="admin-pricehub-vendor-config")
    CollectorConfig.objects.filter(platform=AI_PRICEHUB_PLATFORM).delete()

    create_primary_source_config(
        {
            "platform_slug": "cn-main",
            "vendor_name": "AGIOne CN",
            "endpoint_url": "https://example.com/models",
            "parser_llm_config_uuid": "",
            "currency": "CNY",
            "points_per_currency_unit": 8.0,
            "is_enabled": True,
            "notes": "n",
        },
        owner_user=user,
    )

    sources = list_primary_source_configs()
    assert len(sources) >= 1
    vendors = get_primary_vendor_configs()
    assert vendors[0]["platform_slug"] == sources[0]["platform_slug"]
    assert vendors[0]["models_source"]["url"] == sources[0]["endpoint_url"]


@pytest.mark.django_db
def test_sync_primary_sources_to_collector_writes_collector_config():
    User = get_user_model()
    user = User.objects.create_user(username="admin-pricehub-sync")
    CollectorConfig.objects.filter(platform=AI_PRICEHUB_PLATFORM).delete()

    sources = sync_primary_sources_to_collector(owner_user=user)

    assert len(sources) >= 1
    row = CollectorConfig.objects.get(
        platform=AI_PRICEHUB_PLATFORM,
        key=AI_PRICEHUB_CONFIG_KEY,
    )
    assert isinstance((row.value or {}).get("primary_sources"), list)
    assert len((row.value or {}).get("primary_sources") or []) >= 1
