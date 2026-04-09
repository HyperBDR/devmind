import pytest

from hyperbdr_monitor.encryption import encryption_service
from hyperbdr_monitor.serializers import DataSourceSerializer


@pytest.mark.django_db
def test_data_source_serializer_stores_plaintext_password():
    """HyperBDR DataSource passwords are stored as plaintext (no encryption).

    The password is written directly from CollectorConfig.value.auth.password,
    not via the DataSourceSerializer in the collection flow.
    """
    serializer = DataSourceSerializer(
        data={
            "name": "Primary HyperBDR",
            "api_url": "https://hyperbdr.example.com",
            "username": "collector",
            "password": "Onepro2024@P@ssw0rd",
            "is_active": True,
            "api_timeout": 30,
            "api_retry_count": 3,
            "api_retry_delay": 2,
            "collect_interval": 3600,
        }
    )

    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    # Password stored as plaintext (no encryption)
    assert instance.password == "Onepro2024@P@ssw0rd"


@pytest.mark.django_db
def test_data_source_serializer_preserves_password_on_blank_update(data_source):
    """Blank password in update should preserve the existing plaintext password."""
    data_source.password = "existing-password"
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

    # Blank password preserves existing plaintext password
    assert instance.password == "existing-password"
    assert instance.is_active is False


def test_decrypt_returns_plaintext_on_invalid_token():
    """decrypt() falls back to plaintext when the value is not a valid Fernet token."""
    # A string that is not a valid Fernet token should be returned as-is
    result = encryption_service.decrypt("not-a-fernet-token")
    assert result == "not-a-fernet-token"

    # An empty value should be returned as-is
    assert encryption_service.decrypt("") == ""
    assert encryption_service.decrypt(None) is None

    # A Fernet token encrypted with a DIFFERENT key should fall back to the raw value
    # (since it can't be decrypted with the current key)
    different_key_cipher = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet(
        __import__("base64", fromlist=["urlsafe_b64encode"]).urlsafe_b64encode(
            __import__("hashlib").sha256(b"different-key").digest()
        )
    )
    wrong_key_token = different_key_cipher.encrypt(b"my-secret")
    result = encryption_service.decrypt(wrong_key_token.decode())
    assert result == wrong_key_token.decode()
