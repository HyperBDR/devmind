"""Application-level encryption for ExternalSite secrets.

Stores `static_token`, `hmac_secret`, `token_fetch_headers`,
`token_fetch_body`, and `cached_token` encrypted at rest using
Fernet (AES-128-CBC + HMAC-SHA256).

Key resolution:
- `EXTERNAL_PROXY_FERNET_KEY` env var (a base64-encoded 32-byte
  key, as produced by `cryptography.fernet.Fernet.generate_key`)
  is the preferred source.
- If not set, the key is derived from `SECRET_KEY` via HKDF-SHA256
  with a fixed salt. That keeps dev installs working out of the
  box but means rotating `SECRET_KEY` will invalidate all stored
  secrets (they would need to be re-entered).
"""
import base64
import json
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_SALT = b"external_proxy_v1"
_INFO = b"external_proxy_fernet"


def _build_fernet() -> Fernet:
    explicit = os.environ.get("EXTERNAL_PROXY_FERNET_KEY")
    if explicit:
        return Fernet(explicit.encode())
    secret = settings.SECRET_KEY.encode()
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=_INFO,
    ).derive(secret)
    return Fernet(base64.urlsafe_b64encode(derived))


_FERNET = _build_fernet()


def _encrypt(value: str) -> str:
    if value is None or value == "":
        return value
    return _FERNET.encrypt(str(value).encode()).decode()


def _decrypt(value):
    if value is None or value == "":
        return value
    if isinstance(value, bytes):
        raw = value
    else:
        raw = value.encode()
    try:
        return _FERNET.decrypt(raw).decode()
    except (InvalidToken, ValueError):
        # Not encrypted (e.g. legacy plaintext row) — return as-is so
        # admin actions can fix the row instead of erroring out.
        if isinstance(value, str):
            return value
        return raw.decode(errors="replace")


class EncryptedTextField(models.TextField):
    """TextField that encrypts at rest, decrypts on read."""

    description = "TextField encrypted with Fernet"

    def from_db_value(self, value, expression, connection):
        return _decrypt(value)

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        return _decrypt(value)

    def get_prep_value(self, value):
        return _encrypt(value)


class EncryptedCharField(models.CharField):
    """CharField that encrypts at rest, decrypts on read."""

    description = "CharField encrypted with Fernet"

    def from_db_value(self, value, expression, connection):
        return _decrypt(value)

    def to_python(self, value):
        if value is None:
            return value
        return _decrypt(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return _encrypt(value)


class EncryptedJSONField(models.TextField):
    """JSON value encrypted as text with transparent read/write."""

    description = "JSONField encrypted with Fernet"

    def from_db_value(self, value, expression, connection):
        raw = _decrypt(value)
        if raw in (None, ""):
            return {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("EncryptedJSONField got non-JSON plaintext")
            return {}

    def to_python(self, value):
        if value is None:
            return {}
        if isinstance(value, (dict, list)):
            return value
        raw = _decrypt(value)
        if raw in (None, ""):
            return {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    def get_prep_value(self, value):
        if value in (None, ""):
            return _encrypt("")
        return _encrypt(json.dumps(value, ensure_ascii=False))
