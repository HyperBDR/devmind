"""Dedicated fail-closed credential encryption using configured keys only."""

import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialConfigurationError(ValueError):
    """A dedicated encryption key is unavailable or malformed."""


class CredentialDecryptionError(ValueError):
    """A credential cannot be authenticated or decoded safely."""


def _cipher(key_id):
    """Never fall back to SECRET_KEY, an environment file, or plaintext."""

    keys = getattr(settings, "AGIONE_OPS_ENCRYPTION_KEYS", {})
    key = keys.get(key_id) if isinstance(keys, dict) else None
    if not key:
        raise CredentialConfigurationError("Credential key unavailable.")
    try:
        return Fernet(key.encode("ascii") if isinstance(key, str) else key)
    except (TypeError, ValueError, UnicodeError):
        raise CredentialConfigurationError("Credential key invalid.") from None


def encrypt_credentials(payload, key_id=None):
    """Return ciphertext and its key identifier without retaining plaintext."""

    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        raise ValueError("Credentials must be a string mapping.")
    resolved = key_id or getattr(settings, "AGIONE_OPS_ACTIVE_KEY_ID", "")
    cipher = _cipher(resolved)
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return cipher.encrypt(encoded).decode("ascii"), resolved


def decrypt_credentials(ciphertext, key_id):
    """Authenticate ciphertext; invalid input never becomes a usable secret."""

    cipher = _cipher(key_id)
    try:
        decoded = cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        result = json.loads(decoded)
        if not isinstance(result, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in result.items()
        ):
            raise ValueError
        return result
    except (InvalidToken, TypeError, ValueError, UnicodeError, AttributeError):
        raise CredentialDecryptionError(
            "Credential decryption failed."
        ) from None
