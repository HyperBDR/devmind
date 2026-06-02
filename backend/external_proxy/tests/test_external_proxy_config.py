"""Tests for external proxy configuration behavior."""

import pytest

from external_proxy.encrypted_fields import _decrypt, _encrypt
from external_proxy.models import ExternalSite
from external_proxy.routing import build_routing_table
from external_proxy.serializers import ExternalSiteSerializer
from external_proxy.url_safety import is_blocked_host


@pytest.mark.django_db
def test_routing_table_includes_dynamic_proxy_metadata():
    """Routing table should include fields OpenResty needs."""
    site = ExternalSite.objects.create(
        name="Metrics",
        slug="metrics",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="metrics.internal:8443",
        target_scheme=ExternalSite.TARGET_SCHEME_HTTPS,
        required_feature="metrics_access",
        auth_type=ExternalSite.AUTH_TYPE_HMAC,
        hmac_secret="secret",
    )

    table = build_routing_table()

    assert table == [
        {
            "id": site.id,
            "slug": "metrics",
            "target_host": "metrics.internal:8443",
            "target_scheme": "https",
            "verify_tls": True,
            "access_mode": "proxy",
            "external_url": "",
            "auth_type": "hmac",
            "required_feature": "metrics_access",
            "hmac_secret": "secret",
        }
    ]


@pytest.mark.django_db
def test_serializer_preserves_write_only_auth_fields_on_update():
    """Blank write-only auth fields should not clear existing secrets."""
    site = ExternalSite.objects.create(
        name="Logs",
        slug="logs",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="logs.internal:8080",
        auth_type=ExternalSite.AUTH_TYPE_TOKEN_FETCH,
        static_token="old-static",
        hmac_secret="old-hmac",
        token_fetch_url="http://logs.internal/auth/token",
        token_fetch_headers={"X-API-Key": "old"},
        token_fetch_body={"scope": "logs"},
    )
    serializer = ExternalSiteSerializer(
        site,
        data={
            "name": "Logs Updated",
            "slug": "logs",
            "access_mode": ExternalSite.ACCESS_MODE_PROXY,
            "target_host": "logs.internal:8080",
            "target_scheme": ExternalSite.TARGET_SCHEME_HTTP,
            "required_feature": "admin_console",
            "auth_type": ExternalSite.AUTH_TYPE_TOKEN_FETCH,
            "static_token": "",
            "hmac_secret": "",
            "token_fetch_url": "http://logs.internal/auth/token",
            "token_fetch_method": "POST",
            "token_fetch_headers": {},
            "token_fetch_body": {},
            "is_active": True,
            "order": 0,
        },
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    site.refresh_from_db()

    assert site.name == "Logs Updated"
    assert site.static_token == "old-static"
    assert site.hmac_secret == "old-hmac"
    assert site.token_fetch_headers == {"X-API-Key": "old"}
    assert site.token_fetch_body == {"scope": "logs"}


@pytest.mark.django_db
def test_iframe_site_does_not_require_target_host():
    """Only proxy mode should require target_host."""
    serializer = ExternalSiteSerializer(
        data={
            "name": "BI",
            "slug": "bi",
            "access_mode": ExternalSite.ACCESS_MODE_IFRAME,
            "external_url": "https://bi.example.com",
            "required_feature": "admin_console",
            "auth_type": ExternalSite.AUTH_TYPE_NONE,
            "is_active": True,
            "order": 0,
        }
    )

    assert serializer.is_valid(), serializer.errors
    site = serializer.save()

    assert site.target_host == ""
    assert site.external_url == "https://bi.example.com"


def test_encrypted_field_roundtrip():
    """Encrypt/decrypt helper should be a stable bijection."""
    plaintext = "super-secret-token-123"
    ciphertext = _encrypt(plaintext)
    assert ciphertext != plaintext
    assert _decrypt(ciphertext) == plaintext


def test_encrypted_field_returns_legacy_plaintext_unchanged():
    """Old rows written before encryption was enabled must still load."""
    assert _decrypt("legacy-not-encrypted") == "legacy-not-encrypted"
    assert _decrypt("") == ""
    assert _decrypt(None) is None


@pytest.mark.django_db
def test_secrets_are_encrypted_in_db():
    """Stored DB values for auth secrets must not be plaintext."""
    site = ExternalSite.objects.create(
        name="Logs",
        slug="logs",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="logs.internal:8080",
        auth_type=ExternalSite.AUTH_TYPE_STATIC_TOKEN,
        static_token="plaintext-must-not-leak",
        hmac_secret="hmac-must-not-leak",
        token_fetch_url="https://logs.example.com/auth/token",
        token_fetch_headers={"X-API-Key": "header-must-not-leak"},
        token_fetch_body={"scope": "logs"},
    )

    # .values() still goes through from_db_value, so it would return
    # the *decrypted* value and pass the test even when storage is
    # plaintext. Use raw SQL to inspect the on-disk bytes.
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            "SELECT static_token, hmac_secret, token_fetch_headers, "
            "token_fetch_body FROM external_proxy_site WHERE id = %s",
            [site.pk],
        )
        row = cur.fetchone()

    encrypted_columns = (
        "static_token",
        "hmac_secret",
        "token_fetch_headers",
        "token_fetch_body",
    )
    for col, value in zip(
        encrypted_columns,
        row,
    ):
        assert isinstance(value, str), f"{col} not stored as text"
        assert "must-not-leak" not in value, f"{col} stored as plaintext"

    # Decrypted access still yields the original values.
    site.refresh_from_db()
    assert site.static_token == "plaintext-must-not-leak"
    assert site.hmac_secret == "hmac-must-not-leak"
    assert site.token_fetch_headers == {"X-API-Key": "header-must-not-leak"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_host",
    [
        "127.0.0.1",
        "127.0.0.1:8080",
        "10.0.0.5",
        "10.0.0.5:8080",
        "172.16.5.5",
        "192.168.1.1",
        "169.254.169.254",  # AWS / GCP metadata
        "::1",
        "localhost",
        "metadata.google.internal",
        "kubernetes.default.svc",
    ],
)
def test_is_blocked_host_flags_internal_targets(bad_host):
    assert is_blocked_host(bad_host) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "good_host",
    [
        "bi.example.com",
        "8.8.8.8",
        "1.1.1.1",
    ],
)
def test_is_blocked_host_allows_public_targets(good_host):
    assert is_blocked_host(good_host) is False


def test_is_blocked_host_blocks_rfc_reserved_documentation_ranges():
    """TEST-NET ranges are reserved, not routable, and blocked."""
    assert is_blocked_host("192.0.2.1") is True
    assert is_blocked_host("198.51.100.1") is True
    assert is_blocked_host("203.0.113.1") is True


@pytest.mark.django_db
def test_external_url_rejects_private_ip():
    """An admin that sets a private-IP external_url should be rejected."""
    serializer = ExternalSiteSerializer(
        data={
            "name": "Risky",
            "slug": "risky",
            "access_mode": ExternalSite.ACCESS_MODE_IFRAME,
            "external_url": "http://10.0.0.1/admin",
            "required_feature": "admin_console",
            "auth_type": ExternalSite.AUTH_TYPE_NONE,
            "is_active": True,
            "order": 0,
        }
    )
    assert not serializer.is_valid()
    assert "external_url" in serializer.errors


@pytest.mark.django_db
def test_token_fetch_url_rejects_metadata_endpoint():
    """Cloud metadata token_fetch_url values must be rejected."""
    site = ExternalSite.objects.create(
        name="Logs",
        slug="logs",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="logs.internal:8080",
        auth_type=ExternalSite.AUTH_TYPE_TOKEN_FETCH,
        token_fetch_url="https://logs.example.com/auth/token",
    )
    serializer = ExternalSiteSerializer(
        site,
        data={
            "name": "Logs",
            "slug": "logs",
            "access_mode": ExternalSite.ACCESS_MODE_PROXY,
            "target_host": "logs.internal:8080",
            "target_scheme": ExternalSite.TARGET_SCHEME_HTTPS,
            "required_feature": "admin_console",
            "auth_type": ExternalSite.AUTH_TYPE_TOKEN_FETCH,
            "token_fetch_url": "http://169.254.169.254/latest/meta-data",
            "token_fetch_method": "POST",
            "is_active": True,
            "order": 0,
        },
    )
    assert not serializer.is_valid()
    assert "token_fetch_url" in serializer.errors


@pytest.mark.django_db
def test_verify_tls_field_defaults_to_true():
    """A newly created site must default to verifying TLS."""
    site = ExternalSite.objects.create(
        name="Metrics",
        slug="metrics",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="metrics.internal:8443",
        target_scheme=ExternalSite.TARGET_SCHEME_HTTPS,
    )
    assert site.verify_tls is True


@pytest.mark.django_db
def test_routing_table_honors_verify_tls():
    """The Lua routing table must carry the verify_tls flag per site."""
    ExternalSite.objects.create(
        name="Strict",
        slug="strict",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="strict.example.com:443",
        target_scheme=ExternalSite.TARGET_SCHEME_HTTPS,
        verify_tls=True,
    )
    ExternalSite.objects.create(
        name="SelfSigned",
        slug="selfsigned",
        access_mode=ExternalSite.ACCESS_MODE_PROXY,
        target_host="selfsigned.example.com:443",
        target_scheme=ExternalSite.TARGET_SCHEME_HTTPS,
        verify_tls=False,
    )
    by_slug = {row["slug"]: row for row in build_routing_table()}
    assert by_slug["strict"]["verify_tls"] is True
    assert by_slug["selfsigned"]["verify_tls"] is False
