"""Mock-only verification of DevMind's native upstream transport."""

import base64
import errno
import hashlib
import logging
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock
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


def test_identity_has_one_deadline_across_multiple_requests(monkeypatch):
    from agione_ops import native_client

    monkeypatch.setattr(native_client, "IDENTITY_TIMEOUT_SECONDS", 0.05,
                        raising=False)
    credentials = {"auth_mode": "password", "username": "provider-user",
                   "password": "test-password", "client_id": "test",
                   "client_secret": "test", "password_aes_key": "0123456789abcdef"}

    def handler(request):
        time.sleep(0.035)
        if request.url.path.endswith("/auth/oauth2/token"):
            return httpx.Response(200, json={"access_token": "test"})
        return response()

    source = NativeClient(connection(credentials=credentials),
                          transport=httpx.MockTransport(handler))
    with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
        source.identity()
    source.close()


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


def test_discover_identity_uses_the_single_observed_upstream_role():
    candidate = connection(
        expected_tenant_id="pending",
        principal_kind="provider",
        credentials={
            "access_key": "PRIVATE-AK",
            "secret_key": "PRIVATE-SK",
        },
    )
    with NativeClient(
        candidate,
        transport=httpx.MockTransport(lambda request: response()),
    ) as source:
        result = source.discover_identity()
    assert result["tenant_id"] == "123"
    assert result["principal_kind"] == "provider"
    assert result["role_verified"] is True


@pytest.mark.parametrize("role", ["provider", "operator"])
def test_discover_identity_accepts_explicit_role_for_opaque_upstream(role):
    candidate = connection(expected_tenant_id="pending")
    def handler(request):
        if request.url.path.endswith("/admin/user/info"):
            return response({**INFO, "roles": ["opaque-role-id"]})
        expected = (
            "provider-customers" if role == "provider" else "op-customers"
        )
        assert request.url.path.endswith(expected)
        assert request.url.params["pageSize"] == "1"
        return response({"data": [], "total": 0})

    transport = httpx.MockTransport(handler)
    with NativeClient(candidate, transport=transport) as source:
        result = source.discover_identity(role)
    assert result["principal_kind"] == role
    assert result["role_verified"] is False
    assert result["role_state"] == "not_verified"


def test_discover_identity_rejects_conflicting_explicit_role():
    candidate = connection(expected_tenant_id="pending")
    with NativeClient(
        candidate, transport=httpx.MockTransport(lambda request: response())
    ) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.discover_identity("operator")
    assert error.value.code == "SOURCE_IDENTITY_MISMATCH"


def test_opaque_role_rejects_forbidden_selected_customer_directory():
    candidate = connection(expected_tenant_id="pending")

    def handler(request):
        if request.url.path.endswith("/admin/user/info"):
            return response({**INFO, "roles": ["opaque-role-id"]})
        return httpx.Response(403, json={"status": 403})

    with NativeClient(candidate, transport=httpx.MockTransport(handler)) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.discover_identity("operator")
    assert error.value.code == "SOURCE_FORBIDDEN"


@pytest.mark.parametrize("roles", [[], ["ROLE_PROVIDER", "ROLE_OPERATOR"]])
def test_discover_identity_rejects_missing_or_ambiguous_roles(roles):
    candidate = connection(
        expected_tenant_id="pending",
        credentials={
            "access_key": "PRIVATE-AK",
            "secret_key": "PRIVATE-SK",
        },
    )
    transport = httpx.MockTransport(
        lambda request: response({**INFO, "roles": roles})
    )
    with NativeClient(candidate, transport=transport) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.discover_identity()
    assert error.value.code == "SOURCE_ROLE_NOT_VERIFIED"


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


@pytest.mark.parametrize("status", [404, 503])
def test_http_status_survives_even_for_non_json_error(status):
    with client(lambda request: httpx.Response(status, text="PRIVATE")) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.code == "SOURCE_NON_JSON"
    assert error.value.diagnostic == {
        "http_status": status, "stage": "identity",
    }
    assert "PRIVATE" not in str(error.value.diagnostic)


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


def test_slow_stream_has_total_time_limit_and_safe_stage(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .03,
                        raising=False)

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            for chunk in (b'{"status":', b'200,"result":', b'null}'):
                time.sleep(.02)
                yield chunk

    def handler(request):
        if request.url.path.endswith("/admin/user/info"):
            return response()
        return httpx.Response(200, stream=SlowStream())

    with client(handler) as source:
        source.identity()
        with pytest.raises(AgioneOpsError) as error:
            source.get("/xapi/observability/models/options")
    assert error.value.code == "SOURCE_TIMEOUT"
    assert error.value.diagnostic["stage"] == "models"
    assert error.value.diagnostic["network"] == "response_deadline"


@pytest.mark.parametrize("blocked_stage", ["dns", "headers", "body"])
def test_blocked_io_returns_by_deadline_and_invalidates_client(
    monkeypatch, blocked_stage,
):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .04)
    release = Event()
    finished = Event()
    seen = []

    def block():
        try:
            release.wait(.6)
        finally:
            finished.set()

    def resolver(host):
        if blocked_stage == "dns":
            block()
        return ["8.8.8.8"]

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            block()
            yield b'{"status":200,"result":{}}'

    def handler(request):
        seen.append(request)
        if blocked_stage == "headers":
            block()
        if blocked_stage == "body":
            return httpx.Response(200, stream=Stream())
        return response()

    source = client(handler, resolver=resolver)
    cleaned = Event()
    original_close = source._http.close

    def closed():
        original_close()
        cleaned.set()

    monkeypatch.setattr(source._http, "close", closed)
    started = time.monotonic()
    try:
        with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT") as error:
            source.identity()
        assert time.monotonic() - started < .3
        assert error.value.diagnostic["network"] == "response_deadline"
        assert error.value.diagnostic["stage"] == "identity"
        if blocked_stage == "body":
            assert error.value.diagnostic["http_status"] == 200
        assert source.fetched_at is None
        source.close()
        assert time.monotonic() - started < .3
        with pytest.raises(AgioneOpsError, match="SOURCE_CLIENT_CLOSED"):
            source.identity()
    finally:
        release.set()
        assert finished.wait(1)
        assert cleaned.wait(1)
        source.close()
    assert source.fetched_at is None
    assert source._identity_cache is None
    if blocked_stage == "dns":
        assert seen == []


def test_system_getaddrinfo_is_inside_deadline(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .04)
    release = Event()
    cleaned = Event()
    seen = []

    def getaddrinfo(*args, **kwargs):
        release.wait(.6)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    source = client(lambda request: seen.append(request))
    source._mock = False
    monkeypatch.setattr(source._http, "close", cleaned.set)
    try:
        started = time.monotonic()
        with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
            source.identity()
        assert time.monotonic() - started < .3
    finally:
        release.set()
        assert cleaned.wait(1)
        source.close()
    assert seen == []


@pytest.mark.parametrize("blocked_close", ["response", "client"])
def test_transport_cleanup_cannot_block_caller(monkeypatch, blocked_close):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .04)
    release = Event()
    finished = Event()

    def block():
        try:
            release.wait(.6)
        finally:
            finished.set()

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"status":200,"result":{}}'

        def close(self):
            block()

    source = client(lambda request: httpx.Response(200, stream=Stream()))
    if blocked_close == "client":
        monkeypatch.setattr(source._http, "close", block)
    started = time.monotonic()
    try:
        if blocked_close == "response":
            with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
                source.identity()
        source.close()
        assert time.monotonic() - started < .3
    finally:
        release.set()
        assert finished.wait(1)
        source.close()


def test_stuck_io_has_global_capacity_and_no_unbounded_queue(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .03)
    monkeypatch.setattr(
        "agione_ops.native_client._IO_SLOTS", BoundedSemaphore(2),
        raising=False,
    )
    release = Event()
    completed = Event()
    count = 0
    lock = Lock()

    def handler(request):
        nonlocal count
        with lock:
            count += 1
        release.wait(1)
        with lock:
            count -= 1
            if count == 0:
                completed.set()
        return response()

    sources = [client(handler) for _ in range(6)]
    try:
        for source in sources:
            with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
                source.identity()
        assert count == 2
    finally:
        release.set()
        assert completed.wait(1)
        for source in sources:
            source.close()


def test_idle_client_cleanup_survives_exhausted_io_slots(monkeypatch):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr("agione_ops.native_client._IO_SLOTS", slots)
    source = client()
    source.identity()
    cleaned = Event()
    original_close = source._http.close

    def close():
        original_close()
        cleaned.set()

    monkeypatch.setattr(source._http, "close", close)
    assert slots.acquire(blocking=False)
    try:
        source.close()
    finally:
        slots.release()
    # No second close call or new request may be needed to finish cleanup.
    assert cleaned.wait(.5)
    assert source._http.is_closed


def test_blocked_cleanup_has_bounded_ownership_and_eventual_drain(
    monkeypatch,
):
    monkeypatch.setattr(
        "agione_ops.native_client._CLIENT_SLOTS", BoundedSemaphore(2),
    )
    release = Event()
    entered = Event()
    first = client()
    second = client()

    def close():
        entered.set()
        release.wait(1)

    monkeypatch.setattr(first._http, "close", close)
    try:
        first.close(_deadline=time.monotonic())
        assert entered.wait(.5)
        with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
            client()
        second.close(_deadline=time.monotonic())
        second.close(_deadline=time.monotonic())
        assert second._cleanup_done.wait(1)
    finally:
        release.set()
        assert first._cleanup_done.wait(1)
        assert second._cleanup_done.wait(1)
    assert second._http.is_closed
    with client() as replacement:
        assert replacement.identity()["tenant_id"] == "123"


def test_blocked_cleanup_does_not_block_other_clients(monkeypatch):
    monkeypatch.setattr(
        "agione_ops.native_client._CLIENT_SLOTS", BoundedSemaphore(2),
    )
    release, entered = Event(), Event()
    first, second = client(), client()

    def blocked_close():
        entered.set()
        release.wait(3)

    monkeypatch.setattr(first._http, "close", blocked_close)
    try:
        first.close(_deadline=time.monotonic())
        assert entered.wait(1)
        second.close(_deadline=time.monotonic() + 1)
        assert second._cleanup_done.is_set()
        with client() as third:
            assert third.identity()["tenant_id"] == "123"
    finally:
        release.set()
        assert first._cleanup_done.wait(2)


def test_failed_http_construction_releases_client_ownership(monkeypatch):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr("agione_ops.native_client._CLIENT_SLOTS", slots)

    def fail(**kwargs):
        raise RuntimeError("synthetic constructor failure")

    with monkeypatch.context() as local:
        local.setattr("agione_ops.native_client.httpx.Client", fail)
        with pytest.raises(RuntimeError, match="synthetic constructor"):
            client()
    with client() as source:
        assert source.identity()["tenant_id"] == "123"


def test_cleanup_exception_is_sanitized(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="agione_ops.native_client")
    source = client()

    def close():
        raise OSError("PRIVATE-CLEANUP")

    monkeypatch.setattr(source._http, "close", close)
    source.close()
    assert "OSError" in caplog.text
    assert "PRIVATE" not in caplog.text


def test_timed_out_client_does_not_mix_other_client_credentials(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .04)
    release = Event()
    cleaned = Event()
    seen = []

    def handler(request):
        seen.append(request.headers["x-request-access-key"])
        release.wait(.6)
        return response()

    first = client(handler)
    monkeypatch.setattr(first._http, "close", cleaned.set)
    try:
        with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
            first.identity()
        with NativeClient(
            connection(credentials={
                "access_key": "OTHER-AK", "secret_key": "OTHER-SK",
            }),
            transport=httpx.MockTransport(lambda request: (
                seen.append(request.headers["x-request-access-key"])
                or response()
            )),
        ) as second:
            assert second.identity()["tenant_id"] == "123"
            assert first._credentials == {}
    finally:
        release.set()
        assert cleaned.wait(1)
        first.close()
    assert seen == ["PRIVATE-AK", "OTHER-AK"]
    assert first.fetched_at is None


def test_identity_lock_wait_is_bounded(monkeypatch):
    monkeypatch.setattr("agione_ops.native_client.MAX_RESPONSE_SECONDS", .04)
    with client() as source:
        source._lock = Lock()
        source._lock.acquire()
        try:
            started = time.monotonic()
            with pytest.raises(AgioneOpsError, match="SOURCE_TIMEOUT"):
                source.identity()
            assert time.monotonic() - started < .3
        finally:
            source._lock.release()


def test_model_request_stage_logs_are_sanitized(monkeypatch):
    logs = []
    monkeypatch.setattr(
        "agione_ops.native_client.logger.info", lambda *args: logs.append(args),
    )
    with client(lambda request: response(
        INFO if request.url.path.endswith("/admin/user/info") else []
    )) as source:
        source.identity()
        source.get("/xapi/observability/models/options")
    assert any("model request started" in item[0] for item in logs)
    assert any("model DNS checked" in item[0] for item in logs)
    assert any("model response headers" in item[0] for item in logs)
    assert any("model request finished" in item[0] for item in logs)
    assert "PRIVATE" not in str(logs)


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
def test_httpx_errors_are_sanitized(failure, code, monkeypatch):
    logs = []
    monkeypatch.setattr(
        "agione_ops.native_client.logger.warning",
        lambda *args: logs.append(args),
    )
    def handler(request):
        raise failure

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.identity()
    assert error.value.code == code
    assert "PRIVATE" not in str(error.value)
    assert error.value.diagnostic["stage"] == "identity"
    assert error.value.diagnostic["network"] in {"read_timeout", "connection"}
    assert type(failure).__name__ in str(logs)
    assert "PRIVATE" not in str(logs)


def test_dns_lookup_failure_is_retryable_and_sanitized(monkeypatch):
    logs = []
    monkeypatch.setattr(
        "agione_ops.native_client.logger.warning",
        lambda *args: logs.append(args),
    )
    def resolver(host):
        raise OSError("PRIVATE DNS DETAILS")

    with NativeClient(
        connection(), transport=httpx.MockTransport(lambda request: response()),
        resolver=resolver,
    ) as source, pytest.raises(AgioneOpsError) as error:
        source.identity()
    assert error.value.code == "SOURCE_UNREACHABLE"
    assert error.value.diagnostic == {"network": "dns", "stage": "identity"}
    assert "OSError" in str(logs)
    assert "PRIVATE" not in str(logs)


@pytest.mark.parametrize(
    "cause,network",
    [
        (ConnectionRefusedError(errno.ECONNREFUSED, "PRIVATE"),
         "connection_refused"),
        (ConnectionResetError(errno.ECONNRESET, "PRIVATE"),
         "connection_reset"),
        (OSError(errno.ENETUNREACH, "PRIVATE"), "network_unreachable"),
        (OSError(errno.EHOSTUNREACH, "PRIVATE"), "host_unreachable"),
        (ssl.SSLCertVerificationError("PRIVATE"), "tls_certificate"),
        (ssl.SSLError("PRIVATE"), "tls"),
    ],
)
def test_request_failure_classifies_nested_exceptions(cause, network):
    def handler(request):
        try:
            raise cause
        except Exception as inner:
            raise httpx.ConnectError("PRIVATE") from inner

    with client(handler) as source, pytest.raises(AgioneOpsError) as error:
        source.identity()
    assert error.value.diagnostic == {"network": network, "stage": "identity"}
    assert "PRIVATE" not in str(error.value.diagnostic)


@pytest.mark.parametrize(
    "code,network",
    [(socket.EAI_NONAME, "dns_not_found"), (socket.EAI_AGAIN, "dns_temporary")],
)
def test_dns_failure_distinguishes_structured_resolver_errors(code, network):
    def resolver(host):
        raise socket.gaierror(code, "PRIVATE")

    with NativeClient(connection(), resolver=resolver) as source:
        with pytest.raises(AgioneOpsError) as error:
            source.identity()
    assert error.value.diagnostic == {"network": network, "stage": "identity"}


@pytest.mark.parametrize("code,network", [(10, "tls_cert_expired"),
                                         (62, "tls_hostname")])
def test_known_certificate_verification_codes(code, network):
    from agione_ops.native_client import _network_failure

    failure = ssl.SSLCertVerificationError("PRIVATE")
    failure.verify_code = code
    assert _network_failure(failure) == network


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
