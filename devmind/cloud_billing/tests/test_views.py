"""
Tests for cloud billing API views.
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User

from cloud_billing.models import (
    CloudProvider,
    BillingData,
    AlertRule,
    AlertRecord,
)


@pytest.mark.django_db
class TestCloudProviderViewSet:
    """
    Tests for CloudProviderViewSet.
    """

    def test_list_providers(
        self,
        api_client,
        cloud_provider,
        cloud_provider_inactive
    ):
        """
        Test listing cloud providers.
        """
        url = '/api/v1/cloud-billing/providers/'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) == 2

    def test_list_filter_active(
        self,
        api_client,
        cloud_provider,
        cloud_provider_inactive
    ):
        """
        Test filtering providers by is_active.
        """
        url = '/api/v1/cloud-billing/providers/?is_active=true'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'test_aws'

    def test_list_filter_provider_type(
        self,
        api_client,
        cloud_provider,
        huawei_provider
    ):
        """
        Test filtering providers by provider_type.
        """
        url = '/api/v1/cloud-billing/providers/?provider_type=aws'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['provider_type'] == 'aws'

    def test_create_provider(self, api_client, user):
        """
        Test creating a cloud provider.
        """
        url = '/api/v1/cloud-billing/providers/'
        data = {
            'name': 'new_provider',
            'provider_type': 'aws',
            'display_name': 'New Provider',
            'config': {'access_key': 'test', 'secret_key': 'test'},
            'is_active': True
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == 201
        assert response.data['name'] == 'new_provider'
        assert response.data['created_by'] == user.id

    def test_retrieve_provider(self, api_client, cloud_provider):
        """
        Test retrieving a specific provider.
        """
        url = f'/api/v1/cloud-billing/providers/{cloud_provider.id}/'
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['name'] == 'test_aws'

    def test_update_provider(self, api_client, cloud_provider, user):
        """
        Test updating a provider.
        """
        url = f'/api/v1/cloud-billing/providers/{cloud_provider.id}/'
        data = {
            'name': 'test_aws',
            'provider_type': 'aws',
            'display_name': 'Updated Display Name',
            'config': cloud_provider.config,
            'is_active': True
        }
        response = api_client.put(url, data, format='json')
        assert response.status_code == 200
        assert response.data['display_name'] == 'Updated Display Name'
        assert response.data['updated_by'] == user.id

    def test_delete_provider(self, api_client, cloud_provider):
        """
        Test deleting a provider.
        """
        url = f'/api/v1/cloud-billing/providers/{cloud_provider.id}/'
        response = api_client.delete(url)
        assert response.status_code == 204
        assert not CloudProvider.objects.filter(id=cloud_provider.id).exists()

    def test_validate_credentials(self, api_client, cloud_provider, mocker):
        """
        Test validating provider credentials.
        """
        url = (
            f'/api/v1/cloud-billing/providers/'
            f'{cloud_provider.id}/validate/'
        )

        mock_result = {
            'valid': True,
            'message': 'Credentials are valid',
            'account_id': '123456789012'
        }
        mocker.patch(
            'cloud_billing.services.provider_service.ProviderService.'
            'validate_credentials',
            return_value=mock_result
        )

        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data['valid'] is True
        assert response.data['account_id'] == '123456789012'


@pytest.mark.django_db
class TestBillingDataViewSet:
    """
    Tests for BillingDataViewSet.
    """

    def test_list_billing_data(
        self,
        api_client,
        billing_data
    ):
        """
        Test listing billing data.
        """
        url = '/api/v1/cloud-billing/billing-data/'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_list_filter_by_provider(
        self,
        api_client,
        billing_data,
        cloud_provider
    ):
        """
        Test filtering billing data by provider_id.
        """
        url = (
            f'/api/v1/cloud-billing/billing-data/'
            f'?provider_id={cloud_provider.id}'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item['provider'] == cloud_provider.id
            for item in response.data['results']
        )

    def test_list_filter_by_period(
        self,
        api_client,
        billing_data
    ):
        """
        Test filtering billing data by period.
        """
        period = billing_data.period
        url = f'/api/v1/cloud-billing/billing-data/?period={period}'
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item['period'] == period
            for item in response.data['results']
        )

    def test_retrieve_billing_data(
        self,
        api_client,
        billing_data
    ):
        """
        Test retrieving specific billing data.
        """
        url = (
            f'/api/v1/cloud-billing/billing-data/'
            f'{billing_data.id}/'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['id'] == billing_data.id
        assert 'provider_name' in response.data

    def test_stats_endpoint(
        self,
        api_client,
        billing_data,
        cloud_provider
    ):
        """
        Test billing statistics endpoint.
        """
        url = (
            f'/api/v1/cloud-billing/billing-data/stats/'
            f'?provider_id={cloud_provider.id}'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert 'total_cost' in response.data
        assert 'average_cost' in response.data
        assert 'count' in response.data
        assert 'cost_by_period' in response.data


@pytest.mark.django_db
class TestAlertRuleViewSet:
    """
    Tests for AlertRuleViewSet.
    """

    def test_list_alert_rules(
        self,
        api_client,
        alert_rule
    ):
        """
        Test listing alert rules.
        """
        url = '/api/v1/cloud-billing/alert-rules/'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_create_alert_rule(
        self,
        api_client,
        cloud_provider,
        user
    ):
        """
        Test creating an alert rule.
        """
        url = '/api/v1/cloud-billing/alert-rules/'
        data = {
            'provider': cloud_provider.id,
            'cost_threshold': '20.00',
            'growth_threshold': '10.00',
            'is_active': True
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == 201
        assert response.data['provider'] == cloud_provider.id
        assert response.data['created_by'] == user.id

    def test_update_alert_rule(
        self,
        api_client,
        alert_rule,
        user
    ):
        """
        Test updating an alert rule.
        """
        url = f'/api/v1/cloud-billing/alert-rules/{alert_rule.id}/'
        data = {
            'provider': alert_rule.provider.id,
            'cost_threshold': '30.00',
            'growth_threshold': '15.00',
            'is_active': True
        }
        response = api_client.put(url, data, format='json')
        assert response.status_code == 200
        assert response.data['cost_threshold'] == '30.00'
        assert response.data['updated_by'] == user.id


@pytest.mark.django_db
class TestAlertRecordViewSet:
    """
    Tests for AlertRecordViewSet.
    """

    def test_list_alert_records(
        self,
        api_client,
        alert_record
    ):
        """
        Test listing alert records.
        """
        url = '/api/v1/cloud-billing/alert-records/'
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) >= 1

    def test_list_filter_by_provider(
        self,
        api_client,
        alert_record,
        cloud_provider
    ):
        """
        Test filtering alert records by provider_id.
        """
        url = (
            f'/api/v1/cloud-billing/alert-records/'
            f'?provider_id={cloud_provider.id}'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item['provider'] == cloud_provider.id
            for item in response.data['results']
        )

    def test_list_filter_by_webhook_status(
        self,
        api_client,
        alert_record
    ):
        """
        Test filtering alert records by webhook_status.
        """
        url = (
            '/api/v1/cloud-billing/alert-records/'
            '?webhook_status=pending'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert all(
            item['webhook_status'] == 'pending'
            for item in response.data['results']
        )

    def test_retrieve_alert_record(
        self,
        api_client,
        alert_record
    ):
        """
        Test retrieving specific alert record.
        """
        url = (
            f'/api/v1/cloud-billing/alert-records/'
            f'{alert_record.id}/'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['id'] == alert_record.id
        assert 'provider_name' in response.data


@pytest.mark.django_db
class TestBillingTaskViewSet:
    """
    Tests for BillingTaskViewSet.
    """

    def test_trigger_collect_task(
        self,
        api_client,
        cloud_provider,
        mocker
    ):
        """
        Test manually triggering billing collection task.
        """
        url = '/api/v1/cloud-billing/tasks/collect/'

        mock_task = mocker.Mock()
        mock_task.id = 'test-task-id'
        mocker.patch(
            'cloud_billing.tasks.collect_billing_data.delay',
            return_value=mock_task
        )

        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'task_id' in response.data

    def test_get_task_status(self, api_client, user):
        """
        Test getting task status via TaskTracker (no Celery sync).
        """
        from agentcore_task.adapters.django.models import TaskExecution
        from agentcore_task.constants import TaskStatus

        task_id = 'test-task-id'
        TaskExecution.objects.create(
            task_id=task_id,
            task_name='cloud_billing.tasks.collect_billing_data',
            module='cloud_billing',
            status=TaskStatus.SUCCESS,
            result={'success': True},
        )
        url = (
            f'/api/v1/cloud-billing/tasks/status/?task_id={task_id}&sync=false'
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['task_id'] == task_id
        assert response.data['status'] == 'SUCCESS'

    def test_get_task_status_missing_task_id(self, api_client):
        """
        Test getting task status without task_id parameter.
        """
        url = '/api/v1/cloud-billing/tasks/status/'
        response = api_client.get(url)
        assert response.status_code == 400
