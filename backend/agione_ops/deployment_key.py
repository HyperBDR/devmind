"""Create a persistent deployment key without replacing existing keys."""

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from django.core.management.base import CommandError


def ensure_deployment_key(path, *, has_credentials):
    """Provision one key atomically or fail closed when old data exists."""
    path = Path(path)
    if path.exists():
        key = path.read_bytes().strip()
        try:
            Fernet(key)
        except (TypeError, ValueError):
            raise CommandError("AGIOne deployment key is invalid.") from None
        return key
    if has_credentials:
        raise CommandError(
            "AGIOne deployment key is missing while credentials exist."
        )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".agione-key-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(Fernet.generate_key())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)
    return ensure_deployment_key(path, has_credentials=False)
