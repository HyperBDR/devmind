"""Mock-only verification of DevMind's native upstream transport."""

import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest

from agione_ops.client import AgioneOpsError
from agione_ops.native_client import NativeClient, encrypt_password

HOST = "upstream.agione.example"
INFO = {
    "sysUser": {
        "tenantId": "123",
        "username": "provider-user",
        "email": "PRIVATE-EMAIL",
    },
    "roles": ["ROLE_PROVIDER"],
    "permissions": [],
}


@pytest.fixture(autouse=True)
def native_settings(settings):
    settings.AGIONE_OPS_NATIVE_ENABLED = True
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = [HOST]


def connection(**values):
    credentials = values.pop(
        "credentials",
        {
            "access_key": "PRIVATE-AK",
            "secret_key": "PRIVATE-SK",
            "username": "provider-user",
        },
    )
    result = SimpleNamespace(
        endpoint=f"https://{HOST}",
        source_kind="native",
        expected_tenant_id="123",
        platform="pro",
        principal_kind="provider",
        get_credentials=lambda: dict(credentials),
    )
    for key, value in values.items():
        setattr(result, key, value)
    return result


def response(data=INFO, status=200, **kwargs):
    return httpx.Response(
        status, json={"status": 200, "result": data}, **kwargs
    )


def client(handler=lambda request: response(), **kwargs):
    return NativeClient(
        connection(), transport=httpx.MockTransport(handler), **kwargs
    )


def test_aksk_signs_decoded_sorted_wire_values_and_has_no_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid-private-proxy:99")
    seen = []

    def handler(request):
        seen.append(request)
        return response()

    with client(handler, clock=lambda: 1234.567) as source:
        source.get("/admin/user/info", {"z": "a b", "a": "中+文"})
        assert source._http._trust_env is False
        assert source._http.follow_redirects is False
        assert source.fetched_at is not None
    request = seen[0]
    expected = (
        hashlib.md5("GETa=中+文z=a b1234567PRIVATE-AKPRIVATE-SK".encode())
        .hexdigest()
        .upper()
    )
    assert request.headers["x-request-sign"] == expected
    assert request.headers["x-request-verify-type"] == "Md5"
    assert "authorization" not in request.headers
    assert request.url.path == "/hyperone/admin/user/info"
    assert request.url.host == HOST


def test_identity_checks_tenant_username_and_observed_role_without_pii():
    with client() as source:
        result = source.identity()
    assert result["tenant_id"] == "123"
    assert result["role_verified"] is True
    assert result["principal_kind"] == "provider"
    assert "PRIVATE" not in str(result)
    assert "username" not in result


@pytest.mark.parametrize(
    "info",
    [
        {**INFO, "sysUser": {"tenantId": "999", "username": "provider-user"}},
        {**INFO, "sysUser": {"tenantId": "123", "username": "different"}},
        {**INFO, "sysUser": {"tenantId": True, "username": "provider-user"}},
        {**INFO, "roles": ["ROLE_OPERATOR"]},
    ],
)
def test_identity_mismatch_fails_before_business_reads(info):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return response(info)

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.get("/xapi/observability/call-logs")
    assert error.value.code == "SOURCE_IDENTITY_MISMATCH"
    assert seen == ["/hyperone/admin/user/info"]


def test_unknown_role_is_not_fabricated_as_verified():
    with client(lambda request: response({**INFO, "roles": []})) as source:
        result = source.identity()
    assert result["role_state"] == "not_verified"
    assert result["role_verified"] is False


@pytest.mark.parametrize(
    "path",
    [
        "http://127.0.0.1:8011/api/v1/local/snapshot",
        "//elsewhere/admin/user/info",
        "/admin/user/info?token=private",
        "/admin/../user/info",
        "/financial/api/finance/v1/admin/account-transactions/1/context",
        "/financial/account/recharge/pageQuery",
        "/auth/oauth2/token",
        "/financial/api/finance/v1/admin/customers/../accounts",
    ],
)
def test_unlisted_paths_have_no_requests(path):
    seen = []
    with client(lambda request: seen.append(request)) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.get(path)
    assert error.value.code == "READ_ONLY_ROUTE_BLOCKED"
    assert seen == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://upstream.agione.example",
        "https://user:secret@" + HOST,
        "https://" + HOST + ":8443",
        "https://" + HOST + "/other",
        "https://" + HOST + "?q=x",
        "https://" + HOST + "#x",
        "https://other.example",
        "https://127.0.0.1",
        "https://localhost",
    ],
)
def test_bad_origins_never_construct_transport(endpoint, settings):
    settings.AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS = [
        HOST,
        "127.0.0.1",
        "localhost",
    ]
    with pytest.raises(AgioneOpsError) as error:
        NativeClient(
            connection(endpoint=endpoint),
            transport=httpx.MockTransport(lambda request: response()),
        )
    assert error.value.code == "SOURCE_ENDPOINT_FORBIDDEN"


def test_mixed_public_private_dns_is_rejected_before_io():
    seen = []
    with client(
        lambda request: seen.append(request),
        resolver=lambda host: ["8.8.8.8", "10.0.0.3"],
    ) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.code == "SOURCE_ENDPOINT_FORBIDDEN"
    assert seen == []


@pytest.mark.parametrize(
    "status,body,code",
    [
        (302, {}, "SOURCE_REDIRECT_BLOCKED"),
        (401, {"PRIVATE": "PRIVATE"}, "SOURCE_AUTH_FAILED"),
        (403, {"PRIVATE": "PRIVATE"}, "SOURCE_FORBIDDEN"),
        (429, {}, "SOURCE_RATE_LIMITED"),
        (500, {"status": 500, "msg": "PRIVATE"}, "SOURCE_REJECTED"),
        (200, {"status": True}, "SOURCE_SHAPE_CHANGED"),
        (200, {"status": "401", "msg": "PRIVATE"}, "SOURCE_AUTH_FAILED"),
        (200, {"status": 200, "result": None}, "SOURCE_NO_RESULT"),
        (200, [], "SOURCE_SHAPE_CHANGED"),
    ],
)
def test_safe_error_codes_never_include_body_or_headers(status, body, code):
    def handler(request):
        return httpx.Response(
            status, json=body, headers={"location": "http://127.0.0.1"}
        )

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.identity()
    assert error.value.code == code
    assert "PRIVATE" not in str(error.value)


def test_non_json_body_is_not_emitted():
    with client(lambda request: httpx.Response(200, text="PRIVATE")) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.code == "SOURCE_NON_JSON"
    assert "PRIVATE" not in str(error.value)


def test_stream_limit_applies_without_content_length(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_BYTES", 32)

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * 20
            yield b"b" * 20

    with client(
        lambda request: httpx.Response(200, stream=Stream())
    ) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.code == "SOURCE_RESPONSE_TOO_LARGE"


def test_large_declared_response_is_rejected_without_reading():
    with client(
        lambda request: httpx.Response(
            200, content=b"{}", headers={"content-length": "999999999"}
        )
    ) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.code == "SOURCE_RESPONSE_TOO_LARGE"


@pytest.mark.parametrize(
    "failure,code",
    [
        (httpx.ReadTimeout("PRIVATE"), "SOURCE_TIMEOUT"),
        (httpx.ConnectError("PRIVATE"), "SOURCE_UNREACHABLE"),
    ],
)
def test_httpx_errors_are_sanitized(failure, code):
    def handler(request):
        raise failure

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.identity()
    assert error.value.code == code
    assert "PRIVATE" not in str(error.value)


def test_feature_disabled_and_missing_credentials(settings):
    settings.AGIONE_OPS_NATIVE_ENABLED = False
    with pytest.raises(AgioneOpsError, match="NATIVE_DISABLED"):
        NativeClient(connection())
    settings.AGIONE_OPS_NATIVE_ENABLED = True
    with pytest.raises(AgioneOpsError, match="SOURCE_NOT_CONFIGURED"):
        NativeClient(connection(credentials={}))


def test_customer_directory_contract_and_full_paging():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/info"):
            return response()
        page = int(request.url.params["pageIndex"])
        return response(
            {"data": [{"customerTenantId": str(page)}], "total": 2}
        )

    with client(handler) as source:
        result = source.page(
            "/coperation/tenant/provider-customers",
            page_size=1,
            page_field="pageIndex",
            size_field="pageSize",
            rows_field="data",
            key_field="customerTenantId",
        )
    assert result["complete"] is True
    assert result["pages_read"] == 2
    assert result["items"] == [
        {"customerTenantId": "1"},
        {"customerTenantId": "2"},
    ]


@pytest.mark.parametrize(
    "mode,code",
    [
        ("duplicate", "SOURCE_DUPLICATE_PAGE"),
        ("changing", "SOURCE_CHANGED_DURING_PAGING"),
        ("empty", "SOURCE_INCOMPLETE_PAGING"),
        ("limit", "SOURCE_PAGE_LIMIT"),
    ],
)
def test_full_pagination_never_silently_returns_partial_data(mode, code):
    count = 0

    def handler(request):
        nonlocal count
        if request.url.path.endswith("/info"):
            return response()
        count += 1
        rows = [] if mode == "empty" else [{"id": "same"}]
        total = 101 if mode == "limit" else 2
        if mode == "changing" and count > 1:
            total = 3
        return response({"records": rows, "total": total})

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.page("/xapi/observability/call-logs", page_size=1)
    assert error.value.code == code
    assert count <= 2


def test_password_login_encrypts_form_and_uses_basic_then_bearer():
    seen = []
    credentials = {
        "auth_mode": "password",
        "username": "provider-user",
        "password": "PRIVATE-PASSWORD",
        "client_id": "metis",
        "client_secret": "PRIVATE-CLIENT",
        "password_aes_key": "1234567890123456",
    }

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/auth/oauth2/token"):
            form = parse_qs(request.content.decode())
            assert form["password"] == [
                encrypt_password("PRIVATE-PASSWORD", "1234567890123456")
            ]
            assert form["grant_type"] == ["password"]
            assert request.headers["authorization"] == "Basic " + (
                base64.b64encode(b"metis:PRIVATE-CLIENT").decode()
            )
            return httpx.Response(
                200, json={"access_token": "PRIVATE-TOKEN", "expires_in": 300}
            )
        assert request.headers["authorization"] == "Bearer PRIVATE-TOKEN"
        return response()

    with NativeClient(
        connection(credentials=credentials),
        transport=httpx.MockTransport(handler),
    ) as source:
        identity = source.identity()
    assert len(seen) == 2
    assert "PRIVATE" not in str(identity)


def test_concurrent_finance_reads_share_password_login():
    credentials = {
        "auth_mode": "password",
        "username": "provider-user",
        "password": "PRIVATE-PASSWORD",
        "client_id": "metis",
        "client_secret": "PRIVATE-CLIENT",
        "password_aes_key": "1234567890123456",
    }
    counts = {"login": 0, "finance": 0}
    lock = Lock()

    def handler(request):
        if request.url.path.endswith("/auth/oauth2/token"):
            with lock:
                counts["login"] += 1
            return httpx.Response(200, json={
                "access_token": "PRIVATE-TOKEN", "expires_in": 300,
            })
        if request.url.path.endswith("/admin/user/info"):
            return response()
        assert request.headers["authorization"] == "Bearer PRIVATE-TOKEN"
        with lock:
            counts["finance"] += 1
        return response([])

    with NativeClient(
        connection(credentials=credentials),
        transport=httpx.MockTransport(handler),
    ) as source:
        source.identity()
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(
                lambda customer: source.get(
                    f"/financial/api/finance/v1/admin/customers/"
                    f"{customer}/accounts"
                ),
                range(1, 21),
            ))

    assert results == [[]] * 20
    assert counts == {"login": 1, "finance": 20}


def test_io_guard_runs_before_and_finally_and_can_block_or_revoke():
    for failure in (False, True):
        events = []

        def handler(request):
            events.append("http")
            if failure:
                raise httpx.ReadTimeout("PRIVATE")
            return response()

        with client(handler) as source:
            source.io_guard = lambda: events.append("guard")
            if failure:
                with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
                    source.identity()
            else:
                source.identity()
        assert events == ["guard", "http", "guard"]

    for deny_at, expected in ((1, ["guard"]), (2, ["guard", "http", "guard"])):
        events = []

        def guard():
            events.append("guard")
            if events.count("guard") == deny_at:
                raise AgioneOpsError("ACCESS_REVOKED", status_code=403)

        def handler(request):
            events.append("http")
            return response()

        with client(handler) as source:
            source.io_guard = guard
            with pytest.raises(AgioneOpsError, match="ACCESS_REVOKED"):
                source.identity()
            assert source._identity_cache is None
        assert events == expected


def test_password_auth_http_has_its_own_before_and_finally_guards():
    credentials = {
        "auth_mode": "password",
        "username": "provider-user",
        "password": "PRIVATE-PASSWORD",
        "client_id": "metis",
        "client_secret": "PRIVATE-CLIENT",
        "password_aes_key": "1234567890123456",
    }
    for revoked in (False, True):
        events = []

        def guard():
            events.append("guard")
            if revoked and events.count("guard") == 2:
                raise AgioneOpsError("ACCESS_REVOKED", status_code=403)

        def handler(request):
            if request.url.path.endswith("/auth/oauth2/token"):
                events.append("auth")
                return httpx.Response(
                    200,
                    json={
                        "access_token": "PRIVATE-TOKEN",
                        "expires_in": 300,
                    },
                )
            events.append("info")
            return response()

        with NativeClient(
            connection(credentials=credentials),
            transport=httpx.MockTransport(handler),
        ) as source:
            source.io_guard = guard
            if revoked:
                with pytest.raises(AgioneOpsError, match="ACCESS_REVOKED"):
                    source.identity()
                assert events == ["guard", "auth", "guard"]
            else:
                source.identity()
                assert events == [
                    "guard",
                    "auth",
                    "guard",
                    "guard",
                    "info",
                    "guard",
                ]


def test_optional_header_and_prefix_configuration_rejects_injection():
    for extra in [
        {"api_prefix": "/../other"},
        {"api_prefix": "//evil"},
        {"shost": "host\r\nAuthorization: private"},
    ]:
        config = {"access_key": "a", "secret_key": "b", **extra}
        with pytest.raises(AgioneOpsError, match="SOURCE_NOT_CONFIGURED"):
            NativeClient(
                connection(credentials=config),
                transport=httpx.MockTransport(lambda req: response()),
            )
