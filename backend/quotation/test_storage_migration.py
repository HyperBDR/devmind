import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from quotation.models import DocumentAsset, DocumentType
from quotation.services.storage import document_storage_key


class QuotationStorageMigrationTests(TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.override = self.settings(QUOTATION_STORAGE=str(self.root))
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self._temp.cleanup()

    def create_asset(self, storage_key="imports/legacy.xlsx"):
        return DocumentAsset.objects.create(
            doc_type=DocumentType.EXCEL,
            file_name="Original Name.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            storage_key=storage_key,
            size_bytes=7,
            source="feishu",
        )

    def test_dry_run_reports_without_moving_or_updating(self):
        asset = self.create_asset()
        source = self.root / asset.storage_key
        source.parent.mkdir(parents=True)
        source.write_bytes(b"content")
        output = StringIO()

        call_command("migrate_quotation_storage", "--dry-run", stdout=output)

        asset.refresh_from_db()
        self.assertEqual(asset.storage_key, "imports/legacy.xlsx")
        self.assertTrue(source.exists())
        self.assertIn("DRY RUN: migrated=1", output.getvalue())

    def test_migrates_file_and_is_idempotent(self):
        asset = self.create_asset()
        source = self.root / asset.storage_key
        source.parent.mkdir(parents=True)
        source.write_bytes(b"content")

        call_command("migrate_quotation_storage", stdout=StringIO())

        asset.refresh_from_db()
        expected_key = document_storage_key(asset.id)
        self.assertEqual(asset.storage_key, expected_key)
        self.assertEqual((self.root / expected_key).read_bytes(), b"content")
        self.assertFalse(source.exists())

        output = StringIO()
        call_command("migrate_quotation_storage", stdout=output)
        self.assertIn(
            "migrated=0 already_aligned=1 missing=0", output.getvalue()
        )

    def test_missing_source_is_reported_without_database_change(self):
        asset = self.create_asset("feishu_uploads/does-not-exist.xlsx")
        output = StringIO()

        call_command("migrate_quotation_storage", stdout=output)

        asset.refresh_from_db()
        self.assertEqual(
            asset.storage_key, "feishu_uploads/does-not-exist.xlsx"
        )
        self.assertIn(
            "migrated=0 already_aligned=0 missing=1", output.getvalue()
        )
