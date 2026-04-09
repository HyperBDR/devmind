import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _build_key():
    raw_key = os.getenv("HYPERBDR_MONITOR_SECRET_KEY") or os.getenv("SECRET_KEY", "devmind-hyperbdr-monitor")
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class EncryptionService:
    def __init__(self):
        self.cipher = Fernet(_build_key())

    def encrypt(self, value):
        if not value:
            return value
        if isinstance(value, str):
            value = value.encode("utf-8")
        return self.cipher.encrypt(value).decode("utf-8")

    def decrypt(self, value):
        if not value:
            return value
        if isinstance(value, bytes):
            raw = value
        else:
            raw = value.encode("utf-8")
        try:
            return self.cipher.decrypt(raw).decode("utf-8")
        except InvalidToken:
            # Attempt fallback: if the stored value looks like a Fernet token
            # but failed to decrypt, the encryption key may have changed.
            # Return the value as-is for backward compatibility (e.g. plaintext passwords).
            return value if isinstance(value, str) else raw.decode("utf-8")


encryption_service = EncryptionService()
