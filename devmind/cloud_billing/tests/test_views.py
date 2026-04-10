"""
Tests for cloud billing API views.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
    RechargeApprovalRecord,
)
from cloud_billing.serializers import BillingDataListSerializer


@pytest.mark.django_db
class TestCloudProviderViewSet:
    """
    Tests for CloudProviderViewSet.
    """

    def test_list_providers(
        self, api_client, cloud_provider, cloud_provider_inactive
    ):
        """
        Test listing cloud providers.
        """
        url = "/api/v1/cloud-billing/providers/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_list_filter_active(
        self, api_client, cloud_provider, cloud_provider_inactive
    ):
        """
        Test filtering providers by is_active.
        """
        url = "/api/v1/cloud-billing/providers/?is_active=true"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "test_aws"

    def test_list_filter_provider_type(
        self, api_client, cloud_provider, huawei_provider
    ):
        """
        Test filtering providers by provider_type.
        """
        url = "/api/v1/cloud-billing/providers/?provider_type=aws"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["provider_type"] == "aws"

    def test_list_providers_includes_auth_identifier(
        self, api_client, cloud_provider, user
    ):
        """
        Test list view exposes a display-safe auth identifier.
        """
        cloud_provider.config = {
            "AWS_ACCESS_KEY_ID": "AKIA_TEST_123456",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_REGION": "us-east-1",
        }
        cloud_provider.save(update_fields=["config"])

        zhipu_provider = CloudProvider.objects.create(
            name="test_zhipu",
            provider_type="zhipu",
            display_name="Test Zhipu",
            config={
                "ZHIPU_USERNAME": "billing-user@example.com",
                "ZHIPU_PASSWORD": "secret-password",
            },
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        url = "/api/v1/cloud-billing/providers/"
        response = api_client.get(url)
        assert response.status_code == 200

        rows = {item["id"]: item for item in response.data["results"]}
        assert rows[cloud_provider.id]["auth_identifier_kind"] == "access_key_id"
        assert rows[cloud_provider.id]["auth_identifier"] == "AKIA_TEST_123456"
        assert rows[zhipu_provider.id]["auth_identifier_kind"] == "username"
        assert rows[zhipu_provider.id]["auth_identifier"] == "billing-user@example.com"

    def test_create_provider(self, api_client, user):
        """
        Test creating a cloud provider.
        """
        url = "/api/v1/cloud-billing/providers/"
        data = {
            "name": "new_provider",
            "provider_type": "aws",
            "display_name": "New Provider",
            "config": {"access_key": "test", "secret_key": "test"},
            "is_active": True,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "new_provider"
        assert response.data["created_by"] == user.id

    def test_retrieve_provider(self, api_client, cloud_provider):
        """
        Test retrieving a specific provider.
        """
        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["name"] == "test_aws"

    def test_update_provider(self, api_client, cloud_provider, user):
        """
        Test updating a provider.
        """
        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/"
        data = {
            "name": "test_aws",
            "provider_type": "aws",
            "display_name": "Updated Display Name",
            "config": cloud_provider.config,
            "is_active": True,
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == 200
        assert response.data["display_name"] == "Updated Display Name"
        assert response.data["updated_by"] == user.id

    def test_update_provider_recharge_info(self, api_client, cloud_provider, user):
        """
        Test updating provider recharge info snapshot.
        """
        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/"
        data = {
            "name": "test_aws",
            "provider_type": "aws",
            "display_name": "Updated Display Name",
            "recharge_info": '{"amount": 288, "recharge_account": "acct-288"}',
            "config": cloud_provider.config,
            "is_active": True,
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == 200
        assert response.data["recharge_info"] == data["recharge_info"]

    def test_delete_provider(self, api_client, cloud_provider):
        """
        Test deleting a provider.
        """
        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/"
        response = api_client.delete(url)
        assert response.status_code == 204
        assert not CloudProvider.objects.filter(id=cloud_provider.id).exists()

    def test_validate_credentials(self, api_client, cloud_provider, mocker):
        """
        Test validating provider credentials.
        """
        url = (
            f"/api/v1/cloud-billing/providers/"
            f"{cloud_provider.id}/validate/"
        )

        mock_result = {
            "valid": True,
            "message": "Credentials are valid",
            "account_id": "123456789012",
        }
        mocker.patch(
            "cloud_billing.services.provider_service.ProviderService."
            "validate_credentials",
            return_value=mock_result,
        )

        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data["valid"] is True
        assert response.data["account_id"] == "123456789012"

    def test_config_schemas(self, api_client):
        """Test getting provider config schemas for the UI."""
        url = "/api/v1/cloud-billing/providers/config-schemas/"
        response = api_client.get(url)
        assert response.status_code == 200
        provider_types = {
            provider["provider_type"]
            for provider in response.data["providers"]
        }
        assert "volcengine" in provider_types
        assert "baidu" in provider_types
        assert "zhipu" in provider_types

        volcengine = api_client.get(url + "?provider_type=volcengine")
        assert volcengine.status_code == 200
        assert volcengine.data["provider"]["provider_type"] == "volcengine"
        required_names = {
            field["name"]
            for field in volcengine.data["provider"]["required_fields"]
        }
        assert "VOLCENGINE_ACCESS_KEY_ID" in required_names
        assert "VOLCENGINE_SECRET_ACCESS_KEY" in required_names

        tencent = api_client.get(url + "?provider_type=tencentcloud")
        assert tencent.status_code == 200
        tencent_optional = {
            field["name"]
            for field in tencent.data["provider"]["optional_fields"]
        }
        assert "TENCENT_ENDPOINT" in tencent_optional
        assert "TENCENT_TIMEOUT" in tencent_optional
        assert "TENCENT_MAX_RETRIES" in tencent_optional

        baidu = api_client.get(url + "?provider_type=baidu")
        assert baidu.status_code == 200
        baidu_required = {
            field["name"]
            for field in baidu.data["provider"]["required_fields"]
        }
        assert "BAIDU_ACCESS_KEY_ID" in baidu_required
        assert "BAIDU_SECRET_ACCESS_KEY" in baidu_required

        zhipu = api_client.get(url + "?provider_type=zhipu")
        assert zhipu.status_code == 200
        zhipu_required = {
            field["name"]
            for field in zhipu.data["provider"]["required_fields"]
        }
        assert "ZHIPU_USERNAME" in zhipu_required
        assert "ZHIPU_PASSWORD" in zhipu_required
        zhipu_optional = {
            field["name"]
            for field in zhipu.data["provider"]["optional_fields"]
        }
        assert "ZHIPU_USER_TYPE" in zhipu_optional

    def test_provider_tags_returns_unique_sorted_tags(
        self, api_client, cloud_provider, cloud_provider_inactive, user
    ):
        """
        Test provider tags endpoint returns a unique sorted list.
        """
        cloud_provider.tags = ["finance", "prod", "  "]
        cloud_provider.save(update_fields=["tags"])
        cloud_provider_inactive.tags = ["prod", "shared", "ops"]
        cloud_provider_inactive.save(update_fields=["tags"])
        CloudProvider.objects.create(
            name="extra_tags_provider",
            provider_type="aws",
            display_name="Extra Tags Provider",
            config={"access_key": "test", "secret_key": "test"},
            tags=["Finance", "team-a"],
            is_active=True,
            created_by=user,
            updated_by=user,
        )

        url = "/api/v1/cloud-billing/providers/tags/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["tags"] == [
            "Finance",
            "finance",
            "ops",
            "prod",
            "shared",
            "team-a",
        ]


@pytest.mark.django_db
class TestBillingDataViewSet:
    """
    Tests for BillingDataViewSet.
    """

    def test_list_billing_data(self, api_client, billing_data):
        """
        Test listing billing data.
        """
        url = "/api/v1/cloud-billing/billing-data/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_filter_by_provider(
        self, api_client, billing_data, cloud_provider
    ):
        """
        Test filtering billing data by provider_id.
        """
        url = (
            f"/api/v1/cloud-billing/billing-data/"
            f"?provider_id={cloud_provider.id}"
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item["provider"] == cloud_provider.id
            for item in response.data["results"]
        )

    def test_list_filter_by_period(self, api_client, billing_data):
        """
        Test filtering billing data by period.
        """
        period = billing_data.period
        url = f"/api/v1/cloud-billing/billing-data/?period={period}"
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item["period"] == period for item in response.data["results"]
        )

    def test_list_includes_provider_notes(self, api_client, billing_data):
        """
        Billing list should expose provider notes for unified display labels.
        """
        billing_data.provider.notes = "生产账号"
        billing_data.provider.save(update_fields=["notes"])

        response = api_client.get("/api/v1/cloud-billing/billing-data/")

        assert response.status_code == 200
        assert response.data["results"][0]["provider_notes"] == "生产账号"

    def test_retrieve_billing_data(self, api_client, billing_data):
        """
        Test retrieving specific billing data.
        """
        url = f"/api/v1/cloud-billing/billing-data/" f"{billing_data.id}/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == billing_data.id
        assert "provider_name" in response.data
        assert "balance" in response.data

    def test_stats_endpoint(self, api_client, billing_data, cloud_provider):
        """
        Test billing statistics endpoint.
        """
        cloud_provider.balance = Decimal("88.00")
        cloud_provider.balance_currency = "USD"
        cloud_provider.notes = "生产账号"
        cloud_provider.save(
            update_fields=["balance", "balance_currency", "notes"]
        )
        url = (
            f"/api/v1/cloud-billing/billing-data/stats/"
            f"?provider_id={cloud_provider.id}"
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert "total_cost" in response.data
        assert "total_balance" in response.data
        assert "average_cost" in response.data
        assert "count" in response.data
        assert "cost_by_period" in response.data
        by_provider = response.data["by_provider"]
        first_row = next(iter(by_provider.values()))
        assert first_row["provider_notes"] == "生产账号"

    def test_stats_uses_latest_record_per_provider_account_period(
        self, api_client, cloud_provider
    ):
        """
        Stats should use the latest row in each provider/account/period group.
        """
        cloud_provider.balance = Decimal("90.00")
        cloud_provider.balance_currency = "USD"
        cloud_provider.save(update_fields=["balance", "balance_currency"])

        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=9,
            total_cost=Decimal("100.00"),
            balance=Decimal("500.00"),
            currency="USD",
            service_costs={"ec2": "100.00"},
            account_id="acct-1",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=18,
            total_cost=Decimal("130.00"),
            balance=Decimal("480.00"),
            currency="USD",
            service_costs={"ec2": "130.00"},
            account_id="acct-1",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=17,
            total_cost=Decimal("75.00"),
            balance=Decimal("450.00"),
            currency="USD",
            service_costs={"s3": "75.00"},
            account_id="acct-2",
        )

        response = api_client.get(
            "/api/v1/cloud-billing/billing-data/stats/?start_period=2026-04&end_period=2026-04"
        )

        assert response.status_code == 200
        assert response.data["total_cost"] == 205.0
        assert response.data["average_cost"] == 102.5
        assert response.data["cost_by_period"] == {"2026-04": 205.0}

    def test_list_filters_by_search(self, api_client, cloud_provider):
        """
        Billing list should support backend search by provider name and account.
        """
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=10,
            total_cost=Decimal("50.00"),
            balance=Decimal("100.00"),
            currency="USD",
            service_costs={"ec2": "50.00"},
            account_id="team-alpha",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=11,
            total_cost=Decimal("60.00"),
            balance=Decimal("90.00"),
            currency="USD",
            service_costs={"ec2": "60.00"},
            account_id="team-beta",
        )

        response = api_client.get(
            "/api/v1/cloud-billing/billing-data/?search=alpha"
        )

        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["account_id"] == "team-alpha"

    def test_daily_series_endpoint_returns_latest_total_per_day(
        self, api_client, cloud_provider
    ):
        """
        Daily series should return the latest total for each day and account.
        """
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 9).date(),
            hour=8,
            total_cost=Decimal("80.00"),
            balance=Decimal("400.00"),
            currency="USD",
            service_costs={"ec2": "80.00"},
            account_id="acct-1",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 9).date(),
            hour=20,
            total_cost=Decimal("95.00"),
            balance=Decimal("390.00"),
            currency="USD",
            service_costs={"ec2": "95.00"},
            account_id="acct-1",
        )
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=19,
            total_cost=Decimal("120.00"),
            balance=Decimal("370.00"),
            currency="USD",
            service_costs={"ec2": "120.00"},
            account_id="acct-1",
        )

        response = api_client.get(
            "/api/v1/cloud-billing/billing-data/daily-series/?start_date=2026-04-09&end_date=2026-04-10"
        )

        assert response.status_code == 200
        assert response.data["results"] == [
            {
                "provider_id": cloud_provider.id,
                "account_id": "acct-1",
                "day": "2026-04-09",
                "hour": 20,
                "total_cost": 95.0,
                "currency": "USD",
                "collected_at": response.data["results"][0]["collected_at"],
            },
            {
                "provider_id": cloud_provider.id,
                "account_id": "acct-1",
                "day": "2026-04-10",
                "hour": 19,
                "total_cost": 120.0,
                "currency": "USD",
                "collected_at": response.data["results"][1]["collected_at"],
            },
        ]

    def test_list_serializer_includes_change_from_last_hour_from_db(
        self, cloud_provider
    ):
        """
        List serializer should compute hourly change from database history
        instead of relying on the current page rows.
        """
        BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=10,
            total_cost=Decimal("100.00"),
            balance=Decimal("400.00"),
            currency="USD",
            service_costs={"ec2": "100.00"},
            account_id="acct-1",
        )
        current = BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=11,
            total_cost=Decimal("150.00"),
            balance=Decimal("350.00"),
            currency="USD",
            service_costs={"ec2": "150.00"},
            account_id="acct-1",
        )
        for index in range(3):
            BillingData.objects.create(
                provider=cloud_provider,
                period="2026-04",
                day=datetime(2026, 4, 10).date(),
                hour=12 + index,
                total_cost=Decimal(f"{200 + index}.00"),
                balance=Decimal("300.00"),
                currency="USD",
                service_costs={"ec2": f"{200 + index}.00"},
                account_id=f"acct-{index + 2}",
            )

        payload = BillingDataListSerializer(current).data

        assert payload["id"] == current.id
        assert payload["hour"] == 11
        assert payload["change_from_last_hour"] == 50.0

    def test_latest_by_provider_account_includes_entire_end_day(
        self, api_client, cloud_provider
    ):
        """
        Latest-by-provider-account should treat end_date as inclusive for the
        full day.
        """
        billing = BillingData.objects.create(
            provider=cloud_provider,
            period="2026-04",
            day=datetime(2026, 4, 10).date(),
            hour=18,
            total_cost=Decimal("180.00"),
            balance=Decimal("320.00"),
            currency="USD",
            service_costs={"ec2": "180.00"},
            account_id="acct-1",
        )
        BillingData.objects.filter(id=billing.id).update(
            collected_at=timezone.make_aware(datetime(2026, 4, 10, 18, 30, 0))
        )

        response = api_client.get(
            "/api/v1/cloud-billing/billing-data/latest-by-provider-account/?provider_id="
            f"{cloud_provider.id}&start_date=2026-04-10&end_date=2026-04-10"
        )

        assert response.status_code == 200
        assert any(
            item["account_id"] == "acct-1" and item["hour"] == 18
            for item in response.data
        )

    def test_list_excludes_inactive_provider_data(
        self, api_client, cloud_provider_inactive
    ):
        """
        Billing data list should ignore disabled providers by default.
        """
        current_period = datetime.now().strftime("%Y-%m")
        current_hour = datetime.now().hour
        BillingData.objects.create(
            provider=cloud_provider_inactive,
            period=current_period,
            hour=current_hour,
            total_cost=Decimal("88.00"),
            balance=Decimal("66.00"),
            currency="USD",
            service_costs={"ec2": "88.00"},
            account_id="inactive-account",
        )

        url = "/api/v1/cloud-billing/billing-data/"
        response = api_client.get(url)

        assert response.status_code == 200
        assert not any(
            item["provider"] == cloud_provider_inactive.id
            for item in response.data["results"]
        )

    def test_stats_excludes_inactive_provider_data(
        self, api_client, billing_data, cloud_provider_inactive
    ):
        """
        Billing statistics should not include disabled providers.
        """
        billing_data.provider.balance = Decimal("66.00")
        billing_data.provider.balance_currency = "USD"
        billing_data.provider.save(update_fields=["balance", "balance_currency"])
        BillingData.objects.create(
            provider=cloud_provider_inactive,
            period=billing_data.period,
            hour=billing_data.hour,
            total_cost=Decimal("88.00"),
            balance=Decimal("66.00"),
            currency="USD",
            service_costs={"ec2": "88.00"},
            account_id="inactive-account",
        )

        url = "/api/v1/cloud-billing/billing-data/stats/"
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["total_cost"] == float(billing_data.total_cost)
        assert response.data["total_balance"] == float(
            billing_data.provider.balance
        )
        assert all(
            entry["provider_id"] != cloud_provider_inactive.id
            for entry in response.data["by_provider"].values()
        )


@pytest.mark.django_db
class TestAlertRuleViewSet:
    """
    Tests for AlertRuleViewSet.
    """

    def test_list_alert_rules(self, api_client, alert_rule):
        """
        Test listing alert rules.
        """
        url = "/api/v1/cloud-billing/alert-rules/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_create_alert_rule(self, api_client, cloud_provider, user):
        """
        Test creating an alert rule.
        """
        url = "/api/v1/cloud-billing/alert-rules/"
        data = {
            "provider": cloud_provider.id,
            "cost_threshold": "20.00",
            "growth_threshold": "10.00",
            "balance_threshold": "200.00",
            "is_active": True,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["provider"] == cloud_provider.id
        assert response.data["balance_threshold"] == "200.00"
        assert response.data["created_by"] == user.id

    def test_update_alert_rule(self, api_client, alert_rule, user):
        """
        Test updating an alert rule.
        """
        url = f"/api/v1/cloud-billing/alert-rules/{alert_rule.id}/"
        data = {
            "provider": alert_rule.provider.id,
            "cost_threshold": "30.00",
            "growth_threshold": "15.00",
            "balance_threshold": "150.00",
            "is_active": True,
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == 200
        assert response.data["cost_threshold"] == "30.00"
        assert response.data["balance_threshold"] == "150.00"
        assert response.data["updated_by"] == user.id

    def test_update_alert_rule_auto_submit_toggle(self, api_client, alert_rule, user):
        """
        Test updating independent recharge approval SOP toggle.
        """
        url = f"/api/v1/cloud-billing/alert-rules/{alert_rule.id}/"
        data = {
            "provider": alert_rule.provider.id,
            "cost_threshold": "30.00",
            "growth_threshold": "15.00",
            "balance_threshold": "150.00",
            "auto_submit_recharge_approval": True,
            "is_active": True,
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == 200
        assert response.data["auto_submit_recharge_approval"] is True


@pytest.mark.django_db
class TestAlertRecordViewSet:
    """
    Tests for AlertRecordViewSet.
    """

    def test_list_alert_records(self, api_client, alert_record):
        """
        Test listing alert records.
        """
        url = "/api/v1/cloud-billing/alert-records/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_list_filter_by_provider(
        self, api_client, alert_record, cloud_provider
    ):
        """
        Test filtering alert records by provider_id.
        """
        url = (
            f"/api/v1/cloud-billing/alert-records/"
            f"?provider_id={cloud_provider.id}"
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item["provider"] == cloud_provider.id
            for item in response.data["results"]
        )

    def test_list_filter_by_webhook_status(self, api_client, alert_record):
        """
        Test filtering alert records by webhook_status.
        """
        url = "/api/v1/cloud-billing/alert-records/" "?webhook_status=pending"
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item["webhook_status"] == "pending"
            for item in response.data["results"]
        )

    def test_retrieve_alert_record(self, api_client, alert_record):
        """
        Test retrieving specific alert record.
        """
        url = f"/api/v1/cloud-billing/alert-records/" f"{alert_record.id}/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == alert_record.id
        assert "provider_name" in response.data


@pytest.mark.django_db
class TestBillingTaskViewSet:
    """
    Tests for BillingTaskViewSet.
    """

    def test_trigger_collect_task(self, api_client, cloud_provider, mocker):
        """
        Test manually triggering billing collection task.
        """
        url = "/api/v1/cloud-billing/tasks/collect/"

        mock_task = mocker.Mock()
        mock_task.id = "test-task-id"
        mocker.patch(
            "cloud_billing.tasks.collect_billing_data.delay",
            return_value=mock_task,
        )

        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data["success"] is True
        assert "task_id" in response.data

    def test_get_task_status(self, api_client, user):
        """
        Test getting task status via TaskTracker (no Celery sync).
        """
        from agentcore_task.adapters.django.models import TaskExecution
        from agentcore_task.constants import TaskStatus

        task_id = "test-task-id"
        TaskExecution.objects.create(
            task_id=task_id,
            task_name="cloud_billing.tasks.collect_billing_data",
            module="cloud_billing",
            status=TaskStatus.SUCCESS,
            result={"success": True},
        )
        url = (
            f"/api/v1/cloud-billing/tasks/status/?task_id={task_id}&sync=false"
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["task_id"] == task_id
        assert response.data["status"] == "SUCCESS"

    def test_get_task_status_missing_task_id(self, api_client):
        """
        Test getting task status without task_id parameter.
        """
        url = "/api/v1/cloud-billing/tasks/status/"
        response = api_client.get(url)
        assert response.status_code == 400


@pytest.mark.django_db
class TestRechargeApprovalEndpoints:
    """
    Tests for recharge approval APIs.
    """

    def test_submit_recharge_approval_endpoint(self, api_client, cloud_provider, mocker):
        """
        Provider endpoint should trigger a dedicated recharge approval task.
        """
        cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
        cloud_provider.save(update_fields=["recharge_info"])
        mock_task = mocker.Mock()
        mock_task.id = "approval-task-id"
        mocker.patch(
            "cloud_billing.views.provider.submit_recharge_approval.delay",
            return_value=mock_task,
        )

        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/submit-recharge-approval/"
        response = api_client.post(url, {}, format="json")

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["task_id"] == "approval-task-id"

    def test_submit_recharge_approval_requires_recharge_info(
        self, api_client, cloud_provider
    ):
        """
        Provider endpoint should reject manual submission when recharge info is empty.
        """
        url = f"/api/v1/cloud-billing/providers/{cloud_provider.id}/submit-recharge-approval/"
        response = api_client.post(url, {}, format="json")

        assert response.status_code == 400
        assert response.data["success"] is False

    def test_feishu_callback_challenge(self, api_client):
        """
        Callback endpoint should echo the challenge when Feishu verifies the URL.
        """
        url = "/api/v1/cloud-billing/recharge-approvals/feishu-callback/"
        response = api_client.post(
            url,
            {"challenge": "verify-me", "type": "url_verification"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["challenge"] == "verify-me"

    def test_feishu_callback_updates_recharge_record(
        self, api_client, cloud_provider
    ):
        """
        Callback endpoint should update status and timeline for the matched instance.
        """
        record = RechargeApprovalRecord.objects.create(
            provider=cloud_provider,
            trigger_source=RechargeApprovalRecord.TRIGGER_SOURCE_MANUAL,
            raw_recharge_info='{"amount": 188}',
            request_payload={"amount": 188},
            feishu_instance_code="ins_123",
            feishu_approval_code="approval_123",
            status=RechargeApprovalRecord.STATUS_SUBMITTED,
        )

        url = "/api/v1/cloud-billing/recharge-approvals/feishu-callback/"
        response = api_client.post(
            url,
            {
                "event": {
                    "instance_code": "ins_123",
                    "approval_code": "approval_123",
                    "status": "APPROVED",
                    "timeline": [{"type": "APPROVE", "user_id": "u_1"}],
                }
            },
            format="json",
        )

        assert response.status_code == 200
        record.refresh_from_db()
        assert record.status == RechargeApprovalRecord.STATUS_APPROVED
        assert record.approval_timeline == [{"type": "APPROVE", "user_id": "u_1"}]
