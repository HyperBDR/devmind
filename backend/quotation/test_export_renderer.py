import base64
import io
import subprocess
from datetime import datetime
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.test import TestCase, override_settings
from openpyxl import load_workbook
from quotation.services.export_renderer import (
    TemplateValidationError,
    _signature_image,
    build_default_template_bytes,
    convert_xlsx_to_pdf,
    ensure_default_template,
    render_quotation_xlsx,
    validate_template_bytes,
)


def named_value(workbook, name):
    definition = workbook.defined_names.get(name)
    sheet_name, coordinate = next(definition.destinations)
    return workbook[sheet_name][coordinate.replace("$", "")].value


class QuotationTemplateRendererTests(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.settings_override = override_settings(QUOTATION_STORAGE=self.storage.name)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.storage.cleanup()

    def test_default_template_renders_snapshot_and_dynamic_rows(self):
        template = ensure_default_template()
        snapshot = {
            "quote_no": "PINNED-001",
            "quote_date": "2026-07-24",
            "expire_date": "2026-08-24",
            "client_company": "Snapshot Client",
            "contact_person": "Buyer",
            "email": "buyer@example.com",
            "billing_company": "Billing Client",
            "billing_contact": "Billing",
            "billing_email": "billing@example.com",
            "project_name": "Pinned project",
            "payment_terms": "NET 30",
            "currency": "USD",
            "remarks_disclaimer": "Immutable snapshot",
            "issuer_company_name": "OnePro Cloud Limited",
            "issuer_contact_name": "Owner",
            "issuer_contact_email": "owner@example.com",
            "subtotal_before_vat": "300.00",
            "vat_amount": "30.00",
            "grand_total": "330.00",
            "items": [
                {
                    "line_no": 1,
                    "description": "Software",
                    "qty": "1.00",
                    "list_price": "100.00",
                    "discount_percent": "0.00",
                    "net_unit_price": "100.00",
                    "extended_price": "100.00",
                },
                {
                    "line_no": 2,
                    "description": "Service",
                    "qty": "2.00",
                    "list_price": "100.00",
                    "discount_percent": "0.00",
                    "net_unit_price": "100.00",
                    "extended_price": "200.00",
                },
            ],
        }

        content = render_quotation_xlsx(template, snapshot)

        workbook = load_workbook(io.BytesIO(content), data_only=False)
        sheet = workbook["Quotation"]
        self.assertEqual(named_value(workbook, "quote_no"), "PINNED-001")
        self.assertEqual(sheet["B11"].value, "Software")
        self.assertEqual(sheet["B12"].value, "Service")
        self.assertEqual(sheet["G13"].value, "300.00")
        self.assertEqual(sheet["G15"].value, "330.00")
        self.assertEqual(sheet.print_area, "'Quotation'!$A$1:$G$23")

    def test_default_template_embeds_snapshot_signature_image(self):
        template = ensure_default_template()
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
            "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        snapshot = {
            "issuer_signature": (
                "data:image/png;base64,"
                f"{base64.b64encode(png_bytes).decode('ascii')}"
            )
        }

        content = render_quotation_xlsx(template, snapshot)

        workbook = load_workbook(io.BytesIO(content), data_only=False)
        sheet = workbook["Quotation"]
        self.assertIn("issuer_signature", workbook.defined_names)
        self.assertEqual(len(sheet._images), 1)

    def test_same_template_and_snapshot_produce_identical_xlsx(self):
        template = ensure_default_template()
        snapshot = {"quote_no": "DETERMINISTIC-001"}

        class FirstSaveTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 24, 8, 0, 0, tzinfo=tz)

        class SecondSaveTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 24, 9, 0, 0, tzinfo=tz)

        with patch(
            "openpyxl.writer.excel.datetime.datetime",
            FirstSaveTime,
        ):
            first = render_quotation_xlsx(template, snapshot)
        with patch(
            "openpyxl.writer.excel.datetime.datetime",
            SecondSaveTime,
        ):
            second = render_quotation_xlsx(template, snapshot)

        self.assertEqual(first, second)

    def test_template_validation_rejects_macros(self):
        template = ensure_default_template()
        from quotation.services.storage import resolve_document_path

        original = resolve_document_path(template.storage_key).read_bytes()
        modified = io.BytesIO(original)
        with ZipFile(modified, mode="a", compression=ZIP_DEFLATED) as archive:
            archive.writestr("xl/vbaProject.bin", b"macro")

        with self.assertRaises(TemplateValidationError) as raised:
            validate_template_bytes(modified.getvalue())

        self.assertEqual(raised.exception.code, "template_macros_forbidden")

    @override_settings(QUOTATION_MAX_TEMPLATE_EXPANDED_BYTES=1)
    def test_template_validation_rejects_excessive_expanded_size(self):
        with self.assertRaises(TemplateValidationError) as raised:
            validate_template_bytes(build_default_template_bytes())

        self.assertEqual(raised.exception.code, "template_expanded_too_large")

    @override_settings(QUOTATION_MAX_SIGNATURE_BYTES=3)
    @patch("quotation.services.export_renderer.base64.b64decode")
    def test_signature_size_is_rejected_before_base64_decode(self, decode):
        with self.assertRaises(TemplateValidationError) as raised:
            _signature_image("data:image/png;base64,AAAAAAAA")

        self.assertEqual(raised.exception.code, "signature_too_large")
        decode.assert_not_called()


class FakeLibreOfficeProcess:
    pid = 1234
    returncode = 0

    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs

    def communicate(self, timeout):
        output_dir = self.command[self.command.index("--outdir") + 1]
        input_path = self.command[-1]
        pdf_name = input_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        with open(f"{output_dir}/{pdf_name}.pdf", "wb") as output:
            output.write(b"%PDF-rendered")
        return b"converted", b""


class TimeoutLibreOfficeProcess(FakeLibreOfficeProcess):
    returncode = None

    def communicate(self, timeout):
        raise subprocess.TimeoutExpired(self.command, timeout)

    def wait(self, timeout=None):
        self.returncode = -15
        return self.returncode


class LibreOfficeConversionTests(TestCase):
    @patch(
        "quotation.services.export_renderer.subprocess.Popen",
        side_effect=FakeLibreOfficeProcess,
    )
    def test_conversion_uses_isolated_profile_and_validates_pdf(self, popen):
        result = convert_xlsx_to_pdf(b"PK\x03\x04xlsx", job_id="job-1")

        self.assertEqual(result, b"%PDF-rendered")
        command = popen.call_args.args[0]
        self.assertTrue(
            any(
                argument.startswith("-env:UserInstallation=file://")
                for argument in command
            )
        )
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    @patch("quotation.services.export_renderer.os.killpg")
    @patch(
        "quotation.services.export_renderer.subprocess.Popen",
        side_effect=TimeoutLibreOfficeProcess,
    )
    def test_timeout_terminates_the_process_group(self, _popen, killpg):
        with self.assertRaises(TimeoutError):
            convert_xlsx_to_pdf(b"PK\x03\x04xlsx", job_id="job-2")

        killpg.assert_called_once()
