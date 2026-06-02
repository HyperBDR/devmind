"""
External site token management service.

Handles fetching and caching tokens from external services.
"""
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx

from .encrypted_fields import _encrypt
from .models import ExternalSite

logger = logging.getLogger(__name__)


class ExternalSiteTokenService:
    """Service for managing external site tokens."""

    def __init__(self, site: ExternalSite):
        self.site = site

    def get_auth_header(self, request_path: str = "") -> dict:
        """Return auth headers for a proxied request."""
        auth_type = self.site.auth_type

        if auth_type == ExternalSite.AUTH_TYPE_NONE:
            return {}

        if auth_type == ExternalSite.AUTH_TYPE_STATIC_TOKEN:
            return {"Authorization": f"Bearer {self.site.static_token}"}

        if auth_type == ExternalSite.AUTH_TYPE_TOKEN_FETCH:
            token = self._get_or_refresh_token()
            if token:
                return {"Authorization": f"Bearer {token}"}
            return {}

        if auth_type == ExternalSite.AUTH_TYPE_HMAC:
            return self._generate_hmac_headers(request_path)

        return {}

    def _get_or_refresh_token(self) -> str | None:
        """Return a cached token or fetch a new one."""
        if not self.site.is_token_expired():
            return self.site.cached_token

        if not self.site.token_fetch_url:
            logger.warning(
                f"ExternalSite {self.site.name} requires token but no "
                "fetch URL configured"
            )
            return None

        return self._fetch_token()

    def _fetch_token(self) -> str | None:
        """Fetch a new token from the external service."""
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            headers.update(self.site.token_fetch_headers or {})

            body = self.site.token_fetch_body or {}
            method = self.site.token_fetch_method.upper()

            with httpx.Client(timeout=30.0) as client:
                if method == "GET":
                    response = client.get(
                        self.site.token_fetch_url,
                        headers=headers,
                    )
                else:
                    response = client.post(
                        self.site.token_fetch_url,
                        headers=headers,
                        json=body,
                    )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch token for {self.site.name}: "
                    f"status={response.status_code}, "
                    f"body={response.text[:200]}"
                )
                return None

            data = response.json()
            token = (
                data.get("token")
                or data.get("access_token")
                or data.get("data", {}).get("token")
            )

            if not token:
                logger.error(
                    f"No token found in response for {self.site.name}: "
                    f"{data}"
                )
                return None

            self._update_token_cache(token, data)
            return token

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching token for {self.site.name}")
            return None
        except Exception as e:
            logger.error(f"Error fetching token for {self.site.name}: {e}")
            return None

    def _update_token_cache(self, token: str, response_data: dict):
        """Persist the refreshed token and expiry time."""
        expires_in = response_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # .update() bypasses the field's get_prep_value, so encrypt here
        # explicitly to keep the on-disk value consistent with normal writes.
        ExternalSite.objects.filter(pk=self.site.pk).update(
            cached_token=_encrypt(token),
            cached_token_expires_at=expires_at,
        )

    def _generate_hmac_headers(self, request_path: str) -> dict:
        """Generate HMAC signature headers."""
        if not self.site.hmac_secret:
            return {}

        timestamp = int(time.time())
        nonce = f"{timestamp}-{secrets.token_hex(8)}"

        message = f"{self.site.pk}|{request_path}|{nonce}"
        signature = hmac.new(
            self.site.hmac_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-External-Site-ID": str(self.site.pk),
            "X-Request-Path": request_path,
            "X-Timestamp": str(timestamp),
            "X-Nonce": nonce,
            "X-Signature": signature,
        }


def get_site_for_path(path: str) -> ExternalSite | None:
    """Return the active external site matching a proxy path."""
    if not path.startswith("/proxy/"):
        return None

    sites = ExternalSite.objects.filter(
        is_active=True,
    ).order_by("-order", "-slug")
    for site in sites:
        if path.startswith(site.path_prefix):
            return site
    return None


def get_proxy_headers(site: ExternalSite, request_path: str = "") -> dict:
    """Return auth headers needed by the proxy."""
    service = ExternalSiteTokenService(site)
    return service.get_auth_header(request_path)
