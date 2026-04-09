import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _build_key():
    raw_key = os.getenv("ONEPRO_MONITOR_SECRET_KEY") or os.getenv("SECRET_KEY", "devmind-onepro-monitor")
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
        if isinstance(value, str):
            value = value.encode("utf-8")
        try:
            return self.cipher.decrypt(value).decode("utf-8")
        except Exception:
            return value.decode("utf-8") if isinstance(value, bytes) else value


encryption_service = EncryptionService()
