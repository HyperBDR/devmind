from io import BytesIO
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from core.document_storage import LocalDocumentStorage


class LocalDocumentStorageTests(SimpleTestCase):
    def test_storage_isolated_from_root_traversal(self):
        with TemporaryDirectory() as root:
            storage = LocalDocumentStorage(root)

            with self.assertRaises(ValueError):
                storage.resolve("../outside.txt")

    def test_atomic_and_stream_writes_round_trip(self):
        with TemporaryDirectory() as root:
            storage = LocalDocumentStorage(root, chunk_size=3)
            storage.write_atomic(b"first", "documents/a/file")
            path, size = storage.write_stream(
                BytesIO(b"streamed content"),
                "documents/a/file",
            )

            self.assertEqual(path.read_bytes(), b"streamed content")
            self.assertEqual(size, len(b"streamed content"))
            self.assertTrue(storage.delete("documents/a/file"))
            self.assertFalse(storage.delete("documents/a/file"))
