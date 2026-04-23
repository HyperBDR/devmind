import pytest
from requests.exceptions import HTTPError

from hyperbdr_dashboard.client import HyperBDRClient


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.django_db
def test_login_uses_no_captcha_endpoint_and_sets_auth_token(monkeypatch):
    client = HyperBDRClient(
        api_url="https://admin-preprod.hyperbdr.com",
        username="collector",
        password="secret",
    )
    captured = {}

    def fake_post(url, timeout, json):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["json"] = json
        return DummyResponse(
            payload={
                "code": "00000000",
                "data": {"token": "token-123"},
            }
        )

    monkeypatch.setattr(client.session, "post", fake_post)

    token = client.login()

    assert token == "token-123"
    assert captured["url"] == "https://admin-preprod.hyperbdr.com/admin/api/v2/admin-login-np"
    assert captured["timeout"] == client.timeout
    assert captured["json"] == {
        "username": "collector",
        "password": "secret",
    }
    assert client.session.headers["X-AUTH-TOKEN"] == "token-123"


@pytest.mark.django_db
def test_login_succeeds_even_with_400_status_if_code_is_00000000(monkeypatch):
    """HyperBDR may return HTTP 400 but body code=00000000 with a valid token."""
    client = HyperBDRClient(
        api_url="https://admin-preprod.hyperbdr.com",
        username="collector",
        password="secret",
    )

    def fake_post(url, timeout, json):
        return DummyResponse(
            status_code=400,
            payload={
                "code": "00000000",
                "data": {
                    "enterprise_id": "b07cbda130ac400a808d639bda670413",
                    "token": "QjZDRjFGRkFDNEM4NjcwOWV5SmhiR2NpT2lKSVV6VXhNaUlzSW1WNGNDSTZNVGMzTlRBd01UUTFOaXdpYVdGMElqb3hOemMwT1RrM09EVTJmUS4uLi4=",
                },
            },
        )

    monkeypatch.setattr(client.session, "post", fake_post)

    token = client.login()

    assert token.startswith("QjZDRjFGRk")
    assert client.session.headers["X-AUTH-TOKEN"] == token


@pytest.mark.django_db
def test_login_fails_with_clear_error_when_code_is_not_00000000(monkeypatch):
    """Non-00000000 code should raise HTTPError with detail from body."""
    client = HyperBDRClient(
        api_url="https://admin-preprod.hyperbdr.com",
        username="collector",
        password="wrong-password",
    )

    def fake_post(url, timeout, json):
        return DummyResponse(
            status_code=400,
            payload={
                "code": "10000001",
                "error": {"message": "invalid credentials"},
                "title": "Unauthorized",
            },
        )

    monkeypatch.setattr(client.session, "post", fake_post)

    with pytest.raises(HTTPError) as exc_info:
        client.login()

    assert "10000001" in str(exc_info.value)
    assert "collector" in str(exc_info.value)
    assert "invalid credentials" in str(exc_info.value) or "Unauthorized" in str(exc_info.value)


@pytest.mark.django_db
def test_login_fails_with_clear_error_when_token_missing(monkeypatch):
    """Body code=00000000 but missing token should raise ValueError."""
    client = HyperBDRClient(
        api_url="https://admin-preprod.hyperbdr.com",
        username="collector",
        password="secret",
    )

    def fake_post(url, timeout, json):
        return DummyResponse(
            payload={
                "code": "00000000",
                "data": {},  # no token field
            },
        )

    monkeypatch.setattr(client.session, "post", fake_post)

    with pytest.raises(ValueError) as exc_info:
        client.login()

    assert "token is missing" in str(exc_info.value)
    assert "collector" in str(exc_info.value)
