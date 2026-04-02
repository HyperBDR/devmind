import pytest
from rest_framework.test import APIClient

from hyperbdr_monitor.models import Host, Tenant


@pytest.mark.django_db
def test_list_data_sources(api_client, data_source):
    response = api_client.get("/api/v1/hyperbdr-monitor/data-sources/")

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert response.data["items"][0]["name"] == data_source.name
    assert response.data["items"][0]["password"] == ""


@pytest.mark.django_db
def test_dashboard_endpoint_returns_summary(api_client):
    response = api_client.get("/api/v1/hyperbdr-monitor/analyzer/dashboard/")

    assert response.status_code == 200
    assert "tenant" in response.data
    assert "license" in response.data
    assert "host" in response.data
    assert "task" in response.data


@pytest.mark.django_db
def test_export_hosts_requires_auth():
    client = APIClient()

    response = client.get("/api/v1/hyperbdr-monitor/hosts/export/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_export_hosts_filtered_scope_applies_filters(api_client, data_source):
    tenant = Tenant.objects.create(
        data_source=data_source,
        source_tenant_id="tenant-1",
        name="Tenant A",
    )
    Host.objects.create(
        data_source=data_source,
        tenant=tenant,
        source_host_id="host-healthy",
        name="Healthy Host",
        status="host_register_done",
        boot_status="stopped",
        health_status="healthy",
        os_type="Linux",
        host_type="physical",
        cpu_num=4,
        ram_size="8.00",
        license_valid=True,
        error_message="",
    )
    Host.objects.create(
        data_source=data_source,
        tenant=tenant,
        source_host_id="host-risk",
        name="Risk Host",
        status="sync_failed",
        boot_status="boot_failed",
        health_status="warning",
        os_type="Windows",
        host_type="vmware",
        cpu_num=2,
        ram_size="4.00",
        license_valid=False,
        error_message="sync failed",
    )

    response = api_client.get(
        "/api/v1/hyperbdr-monitor/hosts/export/",
        {"data_source_id": data_source.id, "health_scope": "healthy", "scope": "filtered"},
    )

    content = response.content.decode("utf-8-sig")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment;" in response["Content-Disposition"]
    assert "主机名称,主机ID,数据源,租户" in content
    assert "Healthy Host" in content
    assert "健康" in content
    assert "Risk Host" not in content


@pytest.mark.django_db
def test_export_hosts_data_source_all_ignores_local_filters(api_client, data_source):
    tenant = Tenant.objects.create(
        data_source=data_source,
        source_tenant_id="tenant-2",
        name="Tenant B",
    )
    Host.objects.create(
        data_source=data_source,
        tenant=tenant,
        source_host_id="host-one",
        name="Alpha Host",
        status="host_register_done",
        boot_status="stopped",
        health_status="healthy",
        os_type="Linux",
        host_type="physical",
        cpu_num=4,
        ram_size="8.00",
        license_valid=True,
        error_message="",
    )
    Host.objects.create(
        data_source=data_source,
        tenant=tenant,
        source_host_id="host-two",
        name="Beta Host",
        status="sync_failed",
        boot_status="boot_failed",
        health_status="warning",
        os_type="Linux",
        host_type="vmware",
        cpu_num=8,
        ram_size="16.00",
        license_valid=False,
        error_message="host error details",
    )

    response = api_client.get(
        "/api/v1/hyperbdr-monitor/hosts/export/",
        {
            "data_source_id": data_source.id,
            "name": "Alpha",
            "license_valid": "true",
            "scope": "data_source_all",
        },
    )

    content = response.content.decode("utf-8-sig")
    assert response.status_code == 200
    assert "Alpha Host" in content
    assert "Beta Host" in content
    assert "无效" in content
    assert "host error details" in content
