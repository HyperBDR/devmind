from uuid import uuid4

from django.test import SimpleTestCase

from quotation.services.storage import (
    delete_document,
    document_storage_key,
    resolve_document_path,
    write_document,
)


class QuotationStorageTests(SimpleTestCase):
    def test_document_storage_key_uses_record_and_document_uuids_only(self):
        quotation_id = str(uuid4())
        document_id = str(uuid4())
        self.assertEqual(
            document_storage_key(document_id, quotation_id),
            f"documents/{quotation_id}/{document_id}",
        )

    def test_unassigned_document_uses_document_uuid_as_record_directory(self):
        document_id = str(uuid4())
        self.assertEqual(
            document_storage_key(document_id),
            f"documents/{document_id}/{document_id}",
        )

    def test_document_storage_key_rejects_non_uuid_segments(self):
        with self.assertRaises(ValueError):
            document_storage_key("../quote.xlsx")

    def test_write_resolve_and_delete_document(self):
        with self.settings(QUOTATION_STORAGE=self.temp_dir):
            document_id = str(uuid4())
            key = document_storage_key(document_id)
            path = write_document(b"quotation", key)

            self.assertEqual(path, self.temp_path / key)
            self.assertEqual(path.read_bytes(), b"quotation")
            self.assertEqual(resolve_document_path(key), path)
            self.assertTrue(delete_document(key))
            self.assertFalse(path.exists())
            self.assertFalse(delete_document(key))

    def test_resolve_supports_legacy_relative_keys(self):
        with self.settings(QUOTATION_STORAGE=self.temp_dir):
            legacy = self.temp_path / "imports" / "old_quote.xlsx"
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"legacy")
            self.assertEqual(
                resolve_document_path("imports/old_quote.xlsx"), legacy
            )

    def test_resolve_rejects_paths_outside_storage_root(self):
        with self.settings(QUOTATION_STORAGE=self.temp_dir):
            with self.assertRaises(ValueError):
                resolve_document_path("../outside.txt")

    def setUp(self):
        import tempfile
        from pathlib import Path

        self._temp = tempfile.TemporaryDirectory()
        self.temp_dir = self._temp.name
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        self._temp.cleanup()
