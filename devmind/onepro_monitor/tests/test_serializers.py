import pytest

from onepro_monitor.encryption import encryption_service
from onepro_monitor.serializers import DataSourceSerializer


@pytest.mark.django_db
def test_data_source_serializer_encrypts_password():
    serializer = DataSourceSerializer(
        data={
            "name": "Primary OnePro",
            "api_url": "https://onepro.example.com",
            "username": "collector",
            "password": "plain-secret",
            "is_active": True,
            "api_timeout": 30,
            "api_retry_count": 3,
            "api_retry_delay": 2,
            "collect_interval": 3600,
        }
    )

    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.password != "plain-secret"
    assert encryption_service.decrypt(instance.password) == "plain-secret"


@pytest.mark.django_db
def test_data_source_serializer_preserves_password_on_blank_update(data_source):
    original_password = encryption_service.encrypt("kept-secret")
    data_source.password = original_password
    data_source.save(update_fields=["password"])

    serializer = DataSourceSerializer(
        data_source,
        data={
            "name": data_source.name,
            "api_url": data_source.api_url,
            "username": data_source.username,
            "password": "",
            "is_active": False,
            "api_timeout": data_source.api_timeout,
            "api_retry_count": data_source.api_retry_count,
            "api_retry_delay": data_source.api_retry_delay,
            "collect_interval": data_source.collect_interval,
        },
    )

    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert encryption_service.decrypt(instance.password) == "kept-secret"
    assert instance.is_active is False
