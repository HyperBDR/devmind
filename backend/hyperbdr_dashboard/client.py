import logging
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from requests.exceptions import HTTPError


logger = logging.getLogger(__name__)


def _response_detail(response):
    if response is None:
        return ""
    try:
        payload = response.json()
        return payload.get("title") or payload.get("message") or payload.get("detail") or ""
    except Exception:
        return (response.text or "").strip()[:500]


class HyperBDRClient:
    def __init__(
        self,
        api_url,
        username,
        password,
        timeout=30,
        retry_count=3,
        retry_delay=2,
    ):
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.token = None
        self.token_expires_at = 0
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-LANG": "zh",
                "X-SCENE": "system",
            }
        )

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _request(self, method, url, raise_on_error=True, **kwargs):
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                if raise_on_error:
                    response.raise_for_status()
                return response
            except HTTPError as exc:  # pragma: no cover - network failure
                detail = _response_detail(exc.response)
                message = str(exc)
                if detail:
                    message = f"{message} | detail: {detail}"
                last_error = HTTPError(message, response=exc.response)
                logger.warning(
                    "HyperBDR request failed %s/%s for %s: status=%s detail=%s",
                    attempt,
                    self.retry_count,
                    url,
                    getattr(exc.response, "status_code", "unknown"),
                    detail or "n/a",
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
            except Exception as exc:  # pragma: no cover - network failure
                last_error = exc
                logger.warning(
                    "HyperBDR request failed %s/%s for %s: %s",
                    attempt,
                    self.retry_count,
                    url,
                    exc,
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
        raise last_error

    def login(self):
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                login_url = f"{self.api_url}/admin/api/v2/admin-login-np"
                response = self.session.post(
                    login_url,
                    timeout=self.timeout,
                    json={
                        "username": self.username,
                        "password": self.password,
                    },
                )
                payload = response.json()

                # HyperBDR API: body.code == "00000000" means success.
                # The HTTP status may not reliably indicate success, so always
                # check the body code first.
                logger.warning(
                    "HyperBDR login request: url=%s, username=%s, password=%s",
                    login_url,
                    self.username,
                    self.password,
                )
                if payload.get("code") == "00000000":
                    token = (payload.get("data") or {}).get("token")
                    if not token:
                        raise ValueError(
                            f"HyperBDR login succeeded (code=00000000) but token is missing "
                            f"in response data for user '{self.username}'. "
                            f"Response data keys: {list((payload.get('data') or {}).keys())}"
                        )
                    self.token = token
                    self.token_expires_at = time.time() + 3600
                    self.session.headers["X-AUTH-TOKEN"] = token
                    return token

                # Body code indicates failure — build a helpful error message
                status = response.status_code
                detail = (
                    payload.get("title")
                    or payload.get("message")
                    or payload.get("detail")
                    or payload.get("error", {}).get("message")
                    or response.text.strip()[:500]
                )
                error_msg = (
                    f"HyperBDR login failed (status={status}, code={payload.get('code')}) "
                    f"for user '{self.username}' at {login_url}. "
                    f"Detail: {detail or '(no detail)'}, {self.username}, {self.password}, {self.api_url}, {payload}"
                )
                raise HTTPError(error_msg, response=response)

            except (HTTPError, ValueError) as exc:  # pragma: no cover - dependent on external service
                last_error = exc
                logger.warning(
                    "HyperBDR login failed %s/%s: %s",
                    attempt,
                    self.retry_count,
                    exc,
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
            except Exception as exc:  # pragma: no cover - network failure
                last_error = exc
                logger.warning(
                    "HyperBDR login failed %s/%s: %s",
                    attempt,
                    self.retry_count,
                    exc,
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)
        raise last_error

    def ensure_authenticated(self):
        if not self.token or time.time() >= self.token_expires_at:
            self.login()

    def _fetch(self, path, params=None):
        self.ensure_authenticated()
        # Use session.request directly (no raise_for_status) so we can check
        # the body code regardless of HTTP status. HyperBDR may return 4xx
        # with code=00000000 in the body.
        response = self._request(
            "GET",
            f"{self.api_url}{path}",
            params=params,
            raise_on_error=False,
        )
        payload = response.json()
        if payload.get("code") != "00000000":
            raise ValueError(
                f"HyperBDR request failed for {path}: "
                f"code={payload.get('code')}, "
                f"title={payload.get('title') or '(no title)'}, "
                f"detail={payload.get('detail') or '(no detail)'}"
            )
        return payload

    def get_tenants(self, page=1, page_size=1000):
        return self._fetch(
            "/admin/api/v2/admin-getTenants",
            params={"page": page, "page_size": page_size},
        )

    def get_tenant_detail(self, enterprise_id):
        return self._fetch(
            "/admin/api/v2/admin-getTenantDetail",
            params={"enterprise_id": enterprise_id},
        )

    def get_tenant_licenses_statistics(self, enterprise_id, scene="dr", page=1, page_size=100):
        return self._fetch(
            "/admin/api/v2/admin-getTenantsLicensesStatistics",
            params={
                "enterprise_id": enterprise_id,
                "scene": scene,
                "page": page,
                "page_size": page_size,
            },
        )

    def get_tenant_licenses_details(self, enterprise_id, scene="dr", page=1, page_size=100):
        try:
            return self._fetch(
                "/admin/api/v2/admin-getLicenses",
                params={
                    "enterprise_id": enterprise_id,
                    "scene": scene,
                    "page": page,
                    "page_size": page_size,
                },
            )
        except Exception:
            return self.get_tenant_licenses_statistics(
                enterprise_id=enterprise_id,
                scene=scene,
                page=page,
                page_size=page_size,
            )

    def get_tenant_hosts(self, project_id, user_id, scene="dr", page=1, page_size=100):
        return self._fetch(
            "/admin/api/v2/admin-getTenantHosts",
            params={
                "project_id": project_id,
                "user_id": user_id,
                "scene": scene,
                "page": page,
                "page_size": page_size,
            },
        )


def parse_remote_datetime(value):
    if not value:
        return None
    dt_str = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(dt_str)
    except Exception:
        return None
    if dt.tzinfo is None:
        # No timezone info: assume CST (UTC+8) from HyperBDR API
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    else:
        dt = dt.astimezone(timezone.utc)
    return dt
