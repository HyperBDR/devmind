"""Bounded, read-only AGIOne HTTPS transport owned by DevMind."""

import base64
import hashlib
import ipaddress
import json
import math
import re
import socket
import time
from datetime import datetime, timezone
from threading import RLock
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings

from agione_ops.client import AgioneOpsError
from agione_ops.observability import add_counter

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 100
READ_PATHS = re.compile(
    r"^(?:/admin/user/info"
    r"|/coperation/tenant/(?:op-customers|provider-customers|"
    r"op-customer-overviews)"
    r"|/xapi/observability/(?:call-logs|models/options|inventory/users)"
    r"|/financial/api/finance/v1/provider/revenue/overview"
    r"|/financial/api/finance/v1/admin/customers/[0-9]{1,40}/"
    r"(?:accounts|overview))$"
)


def _error(code, status=502):
    return AgioneOpsError(code, status_code=status)


def _text(value, limit=4096, required=True):
    if not isinstance(value, str) or len(value) > limit:
        raise _error("SOURCE_NOT_CONFIGURED", 503)
    if required and not value:
        raise _error("SOURCE_NOT_CONFIGURED", 503)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise _error("SOURCE_NOT_CONFIGURED", 503)
    return value


def encrypt_password(password, key):
    """Use the observed AES-CFB128 protocol, not local storage encryption."""
    raw = _text(key, 64).encode("utf-8")
    if len(raw) != 16:
        raise _error("SOURCE_NOT_CONFIGURED", 503)
    encryptor = Cipher(algorithms.AES(raw), modes.CFB(raw)).encryptor()
    data = encryptor.update(password.encode("utf-8")) + encryptor.finalize()
    return base64.b64encode(data).decode("ascii")


class NativeClient:
    """One connection, one principal, no process proxy or Demo dependency."""

    def __init__(
        self, connection, *, transport=None, resolver=None, clock=None
    ):
        if getattr(settings, "AGIONE_OPS_NATIVE_ENABLED", False) is not True:
            raise _error("NATIVE_DISABLED", 503)
        if connection.source_kind not in {"native", "agione_api"}:
            raise _error("SOURCE_KIND_FORBIDDEN", 403)
        self.connection = connection
        self._resolver = resolver
        self._mock = isinstance(transport, httpx.MockTransport)
        self._clock = clock or time.time
        self._lock = RLock()
        self._token = ""
        self._token_until = 0
        self._identity_cache = None
        self.fetched_at = None
        self._closed = False
        self._origin, self._host = self._validate_origin(connection.endpoint)
        credentials = connection.get_credentials()
        if not isinstance(credentials, dict):
            raise _error("SOURCE_NOT_CONFIGURED", 503)
        self._credentials = dict(credentials)
        self.auth_mode = credentials.get("auth_mode", "aksk")
        if self.auth_mode not in {"aksk", "password"}:
            raise _error("SOURCE_NOT_CONFIGURED", 503)
        self.api_prefix = credentials.get("api_prefix", "/hyperone")
        if not isinstance(self.api_prefix, str) or not re.fullmatch(
            r"(?:/[A-Za-z0-9_-]{1,64}){1,4}", self.api_prefix
        ):
            raise _error("SOURCE_NOT_CONFIGURED", 503)
        self._headers = {
            "Accept": "application/json",
            "accept-language": "zh-CN",
        }
        for key in ("shost", "static_route"):
            value = credentials.get(key, "")
            if value:
                if not isinstance(value, str) or not re.fullmatch(
                    r"[A-Za-z0-9.*:_-]{1,120}", value
                ):
                    raise _error("SOURCE_NOT_CONFIGURED", 503)
                self._headers[key] = value
        required = (
            ("access_key", "secret_key")
            if self.auth_mode == "aksk"
            else (
                "username",
                "password",
                "client_id",
                "client_secret",
                "password_aes_key",
            )
        )
        for key in required:
            _text(credentials.get(key))
        self._expected_tenant = _text(connection.expected_tenant_id, 160)
        if connection.principal_kind not in {"provider", "operator"}:
            raise _error("SOURCE_IDENTITY_MISMATCH", 403)
        self._http = httpx.Client(
            base_url=self._origin,
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            limits=httpx.Limits(
                max_connections=3, max_keepalive_connections=3
            ),
        )

    def _validate_origin(self, endpoint):
        try:
            parsed = urlsplit(endpoint)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except (TypeError, ValueError):
            raise _error("SOURCE_ENDPOINT_FORBIDDEN", 400) from None
        allowed = {
            str(value).lower().rstrip(".")
            for value in getattr(
                settings, "AGIONE_OPS_ALLOWED_ENDPOINT_HOSTS", ()
            )
        }
        if (
            parsed.scheme != "https"
            or not host
            or host not in allowed
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or port not in {None, 443}
            or not host.isascii()
            or host == "localhost"
            or host.endswith(".localhost")
        ):
            raise _error("SOURCE_ENDPOINT_FORBIDDEN", 400)
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise _error("SOURCE_ENDPOINT_FORBIDDEN", 400)
        return "https://" + parsed.netloc.rstrip("/"), host

    def _check_dns(self):
        """Reject any nonpublic address, including mixed public/private DNS."""
        if self._mock and self._resolver is None:
            return
        try:
            if self._resolver is None:
                addresses = [
                    item[4][0]
                    for item in socket.getaddrinfo(
                        self._host, 443, type=socket.SOCK_STREAM
                    )
                ]
            else:
                addresses = self._resolver(self._host)
            trusted = getattr(
                settings, "AGIONE_OPS_NATIVE_DNS_NETWORKS", {}
            ).get(self._host, ())
            networks = [ipaddress.ip_network(value) for value in trusted]
            if not addresses or any(
                not ipaddress.ip_address(address).is_global and not any(
                    ipaddress.ip_address(address) in network
                    for network in networks
                )
                for address in addresses
            ):
                raise _error("SOURCE_ENDPOINT_FORBIDDEN", 400)
        except (OSError, ValueError, TypeError):
            raise _error("SOURCE_ENDPOINT_FORBIDDEN", 400) from None

    def _params(self, params):
        if params is None:
            return httpx.QueryParams()
        if not isinstance(params, (dict, httpx.QueryParams)):
            raise _error("SOURCE_QUERY_INVALID", 400)
        try:
            query = httpx.QueryParams(params)
        except (TypeError, ValueError):
            raise _error("SOURCE_QUERY_INVALID", 400) from None
        if len(query.multi_items()) > 100 or len(str(query)) > 32768:
            raise _error("SOURCE_QUERY_INVALID", 400)
        for key, value in query.multi_items():
            if (
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key)
                or len(value) > 4096
                or any(ord(c) < 32 for c in value)
                or re.search(
                    r"password|secret|authorization|access_?key|" r"token",
                    key,
                    re.I,
                )
            ):
                raise _error("SOURCE_QUERY_INVALID", 400)
        return query

    def _signed_headers(self, params):
        add_counter("upstream_authentications", 1)
        access = self._credentials["access_key"]
        secret = self._credentials["secret_key"]
        timestamp = str(int(self._clock() * 1000))
        values = "".join(
            f"{key}={value}"
            for key, value in sorted(
                params.multi_items(), key=lambda item: item[0]
            )
        )
        signature = (
            hashlib.md5(
                ("GET" + values + timestamp + access + secret).encode("utf-8")
            )
            .hexdigest()
            .upper()
        )
        return {
            "x-request-access-key": access,
            "x-request-timestamp": timestamp,
            "x-request-verify-type": "Md5",
            "x-request-sign": signature,
        }

    def _request(self, method, path, *, params=None, data=None, auth=None):
        if self._closed:
            raise _error("SOURCE_CLIENT_CLOSED", 503)
        login = (
            method == "POST"
            and path == "/auth/oauth2/token"
            and self.auth_mode == "password"
        )
        if not login and not (
            method == "GET"
            and isinstance(path, str)
            and READ_PATHS.fullmatch(path)
        ):
            raise _error("READ_ONLY_ROUTE_BLOCKED", 400)
        query = self._params(params)
        headers = dict(self._headers)
        if method == "GET":
            if self.auth_mode == "aksk":
                headers.update(self._signed_headers(query))
            else:
                self._login()
                headers["Authorization"] = "Bearer " + self._token
        guard = getattr(self, "io_guard", None)
        if guard is not None:
            guard()
        try:
            self._check_dns()
            add_counter("internal_http_requests", 1)
            with self._http.stream(
                method,
                self.api_prefix + path,
                params=query,
                headers=headers,
                data=data,
                auth=auth,
            ) as response:
                if 300 <= response.status_code < 400:
                    raise _error("SOURCE_REDIRECT_BLOCKED")
                length = response.headers.get("content-length")
                if length is not None:
                    try:
                        if int(length) > MAX_BYTES:
                            raise _error("SOURCE_RESPONSE_TOO_LARGE")
                    except ValueError:
                        raise _error("SOURCE_SHAPE_CHANGED") from None
                body = bytearray()
                for chunk in response.iter_bytes():
                    add_counter("internal_download_bytes", len(chunk))
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise _error("SOURCE_RESPONSE_TOO_LARGE")
                result = self._decode(response.status_code, body)
                self.fetched_at = datetime.now(timezone.utc).isoformat()
                return result
        except httpx.TimeoutException:
            raise _error("SOURCE_TIMEOUT", 504) from None
        except httpx.RequestError:
            raise _error("SOURCE_UNREACHABLE") from None
        finally:
            if guard is not None:
                guard()

    def _decode(self, status, content):
        if status == 429:
            raise _error("SOURCE_RATE_LIMITED", 429)
        if status in {401, 403}:
            raise _error(
                "SOURCE_FORBIDDEN" if status == 403 else "SOURCE_AUTH_FAILED",
                403 if status == 403 else 502,
            )
        try:
            body = json.loads(content)
        except (ValueError, UnicodeError):
            raise _error("SOURCE_NON_JSON") from None
        if not isinstance(body, dict):
            raise _error("SOURCE_SHAPE_CHANGED")
        business = body.get("status", body.get("code"))
        if isinstance(business, str) and business.isdecimal():
            business = int(business)
        if business is not None and type(business) is not int:
            raise _error("SOURCE_SHAPE_CHANGED")
        if business == 429:
            raise _error("SOURCE_RATE_LIMITED", 429)
        if business in {401, 403}:
            raise _error(
                (
                    "SOURCE_FORBIDDEN"
                    if business == 403
                    else "SOURCE_AUTH_FAILED"
                ),
                403 if business == 403 else 502,
            )
        if status == 424 and business == 1:
            raise _error("SOURCE_AUTH_FAILED")
        if not 200 <= status < 300 or business not in {None, 200}:
            raise _error("SOURCE_REJECTED")
        return body

    def _login(self):
        """Share one login/token across concurrent read-only requests."""
        with self._lock:
            return self._login_locked()

    def _login_locked(self):
        """Keep OAuth tokens only for this task-owned client instance."""
        if self._token and time.monotonic() < self._token_until:
            return
        credentials = self._credentials
        add_counter("upstream_authentications", 1)
        body = self._request(
            "POST",
            "/auth/oauth2/token",
            auth=httpx.BasicAuth(
                credentials["client_id"], credentials["client_secret"]
            ),
            data={
                "username": credentials["username"],
                "password": encrypt_password(
                    credentials["password"], credentials["password_aes_key"]
                ),
                "grant_type": "password",
            },
        )
        token = body.get("access_token")
        if not isinstance(token, str) or not token or len(token) > 16384:
            raise _error("SOURCE_AUTH_FAILED")
        try:
            expires = float(body.get("expires_in", 300))
        except (TypeError, ValueError):
            expires = 300
        if not math.isfinite(expires) or expires <= 0:
            expires = 300
        self._token = token
        self._token_until = time.monotonic() + max(1, min(expires, 86400) - 30)

    def _result(self, path, params=None):
        for attempt in range(2):
            try:
                body = self._request("GET", path, params=params)
            except AgioneOpsError as exc:
                if (
                    self.auth_mode != "password"
                    or attempt
                    or exc.code != "SOURCE_AUTH_FAILED"
                ):
                    raise
                self._token = ""
                self._token_until = 0
                continue
            if "result" not in body or body["result"] is None:
                raise _error("SOURCE_NO_RESULT")
            return body["result"]
        raise _error("SOURCE_AUTH_FAILED")

    def _validate_identity(self, info):
        if not isinstance(info, dict) or not isinstance(
            info.get("sysUser"), dict
        ):
            raise _error("SOURCE_SHAPE_CHANGED")
        user = info["sysUser"]
        tenant = user.get("tenantId")
        if (
            isinstance(tenant, bool)
            or not isinstance(tenant, (str, int))
            or str(tenant) != self._expected_tenant
            or (
                self._credentials.get("username") is not None
                and user.get("username") != self._credentials["username"]
            )
        ):
            raise _error("SOURCE_IDENTITY_MISMATCH", 403)
        roles = info.get("roles", [])
        permissions = info.get("permissions", [])
        if not isinstance(roles, list) or not isinstance(permissions, list):
            raise _error("SOURCE_SHAPE_CHANGED")
        declared = self.connection.principal_kind
        role_values = set()
        for role in roles:
            value = role if isinstance(role, str) else None
            if isinstance(role, dict):
                value = role.get("roleCode", role.get("code"))
            if isinstance(value, str):
                role_values.add(value.lower().removeprefix("role_"))
        observed = role_values.intersection({"provider", "operator"})
        if observed and declared not in observed:
            raise _error("SOURCE_IDENTITY_MISMATCH", 403)
        return {
            "tenant_id": str(tenant),
            "platform": self.connection.platform,
            "principal_kind": declared,
            "role_verified": declared in observed,
            "role_state": (
                "verified" if declared in observed else "not_verified"
            ),
            "fetchedAt": self.fetched_at,
        }

    def identity(self):
        """Check actual tenant, optional username and explicit role evidence."""
        with self._lock:
            try:
                identity = self._validate_identity(
                    self._result("/admin/user/info")
                )
            except AgioneOpsError:
                self._identity_cache = None
                self._token = ""
                raise
            self._identity_cache = identity
            return dict(identity)

    def get(self, path, params=None):
        """Return the named read result; no arbitrary methods or paths exist."""
        if not isinstance(path, str) or not READ_PATHS.fullmatch(path):
            raise _error("READ_ONLY_ROUTE_BLOCKED", 400)
        if path == "/admin/user/info":
            with self._lock:
                info = self._result(path, params)
                self._identity_cache = self._validate_identity(info)
                return info
        if self._identity_cache is None:
            with self._lock:
                if self._identity_cache is None:
                    self.identity()
        return self._result(path, params)

    def page(
        self,
        path,
        params=None,
        *,
        page=1,
        page_size=100,
        all_pages=True,
        page_field="current",
        size_field="size",
        rows_field="records",
        key_field="id",
    ):
        """Reject truncation, moving totals and repeated upstream page IDs."""
        if (
            type(page) is not int
            or not 1 <= page <= MAX_PAGES
            or type(page_size) is not int
            or not 1 <= page_size <= 200
            or type(all_pages) is not bool
            or (all_pages and page != 1)
        ):
            raise _error("SOURCE_QUERY_INVALID", 400)
        for field in (page_field, size_field, rows_field, key_field):
            if not isinstance(field, str) or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]{0,63}", field
            ):
                raise _error("SOURCE_QUERY_INVALID", 400)
        collected, keys, expected = [], set(), None
        for count, current in enumerate(range(page, MAX_PAGES + 1), 1):
            result = self.get(
                path,
                {**(params or {}), page_field: current, size_field: page_size},
            )
            if not isinstance(result, dict):
                raise _error("SOURCE_SHAPE_CHANGED")
            rows, total = result.get(rows_field), result.get("total")
            if (
                not isinstance(rows, list)
                or len(rows) > page_size
                or type(total) is not int
                or total < 0
            ):
                raise _error("SOURCE_SHAPE_CHANGED")
            if expected is None:
                expected = total
                if all_pages and total > MAX_PAGES * page_size:
                    raise _error("SOURCE_PAGE_LIMIT", 409)
            elif expected != total:
                raise _error("SOURCE_CHANGED_DURING_PAGING", 409)
            for row in rows:
                key = row.get(key_field) if isinstance(row, dict) else None
                if (
                    isinstance(key, bool)
                    or not isinstance(key, (str, int))
                    or not str(key).strip()
                ):
                    raise _error("SOURCE_RECORD_ID_MISSING")
                if str(key) in keys:
                    raise _error("SOURCE_DUPLICATE_PAGE", 409)
                keys.add(str(key))
                collected.append(row)
            if len(collected) > expected or (
                not rows and collected != [] and len(collected) != expected
            ):
                raise _error("SOURCE_INCOMPLETE_PAGING", 409)
            if not all_pages or len(collected) == expected:
                return {
                    "items": collected,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "pages_read": count,
                    "complete": page == 1 and len(collected) == total,
                    "fetchedAt": self.fetched_at,
                }
            if not rows:
                raise _error("SOURCE_INCOMPLETE_PAGING", 409)
        raise _error("SOURCE_PAGE_LIMIT", 409)

    def customers(self):
        """Use the principal-specific authorized directory contract."""
        provider = self.connection.principal_kind == "provider"
        path = "/coperation/tenant/" + (
            "provider-customers" if provider else "op-customers"
        )
        return self.page(
            path,
            {} if provider else {"identityCode": "EU"},
            page_field="pageIndex",
            size_field="pageSize",
            rows_field="data",
            key_field="customerTenantId" if provider else "tenantId",
        )

    def call_logs(self, start_time, end_time, **kwargs):
        return self.page(
            "/xapi/observability/call-logs",
            {"startTime": start_time, "endTime": end_time},
            **kwargs,
        )

    def close(self):
        self._http.close()
        self._closed = True
        self._token = ""
        self._credentials.clear()
        self._identity_cache = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
