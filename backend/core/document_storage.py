"""Safe local-file storage shared by document-oriented Django apps."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO


class LocalDocumentStorage:
    """Persist files below one configured root with atomic writes."""

    def __init__(self, root: str | Path, chunk_size: int = 1024 * 1024):
        self.root = Path(root).absolute()
        self.chunk_size = chunk_size

    def resolve(self, storage_key: str) -> Path:
        path = (self.root / str(storage_key)).absolute()
        resolved_root = self.root.resolve()
        resolved_path = path.resolve()
        if (
            resolved_path != resolved_root
            and resolved_root not in resolved_path.parents
        ):
            raise ValueError("document path is outside storage root")
        return path

    def write(self, content: bytes, storage_key: str) -> Path:
        path = self.resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def write_stream(
        self,
        stream: BinaryIO,
        storage_key: str,
    ) -> tuple[Path, int]:
        """Atomically persist a seekable stream without a full copy."""
        path = self.resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        original_position = stream.tell()
        written_bytes = 0
        try:
            stream.seek(0)
            with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                chunks = getattr(stream, "chunks", None)
                iterator = (
                    chunks(chunk_size=self.chunk_size)
                    if callable(chunks)
                    else iter(
                        lambda: stream.read(self.chunk_size),
                        b"",
                    )
                )
                for chunk in iterator:
                    temporary.write(chunk)
                    written_bytes += len(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
        finally:
            stream.seek(original_position)
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return path, written_bytes

    def write_atomic(self, content: bytes, storage_key: str) -> Path:
        """Atomically replace one storage object."""
        path = self.resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return path

    def delete(self, storage_key: str) -> bool:
        path = self.resolve(storage_key)
        if not path.is_file():
            return False
        path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass
        return True
