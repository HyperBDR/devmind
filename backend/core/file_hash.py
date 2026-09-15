"""Streaming file hashing shared by document-oriented applications."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def hash_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest for one local file."""
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
