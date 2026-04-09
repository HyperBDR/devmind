"""
HyperBDR platform provider.

Authentication: base_url + username + password;
POST /admin/api/v2/admin-login-np to verify credentials.
"""
import logging

import requests
from requests.exceptions import RequestException

from .base import BaseProvider

logger = logging.getLogger(__name__)


class HyperBDRProvider(BaseProvider):
    """
    HyperBDR platform data collection provider.

    Expected auth_config:
    {
        "base_url": "https://hyperbdr.example.com",
        "username": "admin",
        "password": "...",
    }
    """

    def authenticate(self, auth_config: dict) -> bool:
        """Verify HyperBDR credentials via admin-login-np endpoint."""
        if not auth_config:
            return False

        base_url = (auth_config.get("base_url") or "").rstrip("/")
        username = (auth_config.get("username") or "").strip()
        password = auth_config.get("password") or ""

        if not base_url or not username or not password:
            return False

        try:
            login_url = f"{base_url}/admin/api/v2/admin-login-np"
            logger.info(
                f"HyperBDRProvider.authenticate: validating {login_url} "
                f"for user={username!r}"
            )

            response = requests.post(
                login_url,
                json={"username": username, "password": password},
                timeout=30,
            )
            payload = response.json()
            if payload.get("code") == "00000000":
                logger.info("HyperBDRProvider.authenticate: success")
                return True
            else:
                detail = (
                    payload.get("title")
                    or payload.get("message")
                    or payload.get("detail")
                    or "Authentication failed"
                )
                logger.warning(
                    f"HyperBDRProvider.authenticate failed: code={payload.get('code')}, "
                    f"detail={detail}"
                )
                return False
        except RequestException as e:
            logger.warning(f"HyperBDRProvider.authenticate request failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"HyperBDRProvider.authenticate failed: {e}")
            return False

    def list_projects(self, auth_config: dict):
        """
        HyperBDR uses single config for tenant data collection.
        Return a placeholder project for frontend compatibility.
        """
        return [{"key": "tenants", "id": "tenants", "name": "Tenant collection"}]

    def collect(self, auth_config, start_time, end_time, user_id: int, platform: str, **kwargs):
        """Collect not implemented for this provider."""
        return []

    def validate(self, auth_config, start_time, end_time, user_id: int, platform: str, source_unique_ids):
        """Validate not implemented for this provider."""
        return []

    def fetch_attachments(self, auth_config, raw_record):
        """No attachments for HyperBDR."""
        return []
