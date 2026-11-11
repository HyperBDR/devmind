import importlib
from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from quotation.models import Quotation, QuotationItem, QuotationVersion
from quotation.services.document_parsing.schemas import ParsedQuotationItem
from quotation.services.line_item_text import strip_description_label
from quotation.services.quotation_service import (
    quotation_business_signature,
)

migration = importlib.import_module(
    "quotation.migrations.0038_strip_listed_quote_description_labels"
)

YEARLY = "License Type: HyperBDR Yearly License. VM Quantity: 1. Cost: 420."
SERVICE = (
    "Description: Remote Product Service - Premium 7*24 "
    "(Optional, Yearly).\n29VMs x 2 times"
)


class StripDescriptionLabelTests(SimpleTestCase):
    def test_only_the_leading_label_is_removed(self):
        self.assertEqual(
            strip_description_label(YEARLY),
            "HyperBDR Yearly License. VM Quantity: 1. Cost: 420.",
        )
        self.assertEqual(
            strip_description_label(SERVICE),
            "Remote Product Service - Premium 7*24 "
            "(Optional, Yearly).\n29VMs x 2 times",
        )

    def test_label_variants_are_recognized(self):
        for value in (
            "license type : HyperBDR",
            "LICENSE TYPE:HyperBDR",
            "  Description：HyperBDR",
        ):
            self.assertEqual(strip_description_label(value), "HyperBDR")

    def test_other_text_is_untouched(self):
        for value in (
            None,
            "",
            "HyperBDR Yearly License",
            "Extended Description: kept in the middle",
            "HyperBDR. License Type: kept when not leading",
            "License Type:",
        ):
            self.assertEqual(strip_description_label(value), value)

    def test_migration_uses_the_same_rule(self):
        for value in (
            None,
            "",
            YEARLY,
            SERVICE,
            "license type : HyperBDR",
            "  Description：HyperBDR",
            "Extended Description: kept in the middle",
            "License Type:",
        ):
            self.assertEqual(
                migration._strip(value), strip_description_label(value)
            )

    def test_parsed_items_drop_the_label(self):
        item = ParsedQuotationItem(
            line_no=1,
            type="Software",
            description=YEARLY,
        )
        self.assertEqual(
            item.description,
            "HyperBDR Yearly License. VM Quantity: 1. Cost: 420.",
        )


class StripQuoteDescriptionLabelsCommandTests(TestCase):
    def _quote(self, number: str) -> Quotation:
        quotation = Quotation.objects.create(
            quote_no=number,
            project_name="HW_Globe Telecom_29VMs",
            currency="USD",
            payment_terms="CIA",
            quote_date="2026-11-11",
            expire_date="2026-12-11",
            grand_total=Decimal("21749.20"),
            issuer_contact_name="Natalie Chan",
            issuer_contact_email="natalie@example.com",
            client_company="Huawei",
            contact_person="Huawei",
            email="huawei@example.com",
        )
        QuotationItem.objects.create(
            quotation=quotation,
            line_no=1,
            type="Software",
            name="HyperBDR Yearly License",
            description="License Type: HyperBDR Yearly License.",
            qty=29,
            list_price=420,
            extended_price=12180,
        )
        QuotationItem.objects.create(
            quotation=quotation,
            line_no=2,
            type="Others",
            description="Remote Product Service - Premium 7*24",
            qty=1,
            list_price=2610,
            extended_price=2610,
        )
        QuotationVersion.objects.create(
            quotation=quotation,
            version_no=1,
            status=quotation.status,
            snapshot_json={
                "project_name": quotation.project_name,
                "grand_total": "21749.20",
                "version_no": 1,
                "items": [
                    {
                        "line_no": 1,
                        "name": "License Type: kept in other keys",
                        "description": (
                            "License Type: HyperBDR Yearly License."
                        ),
                        "qty": "29.00",
                    }
                ],
            },
        )
        Quotation.objects.filter(pk=quotation.pk).update(version_current=1)
        quotation.refresh_from_db()
        return quotation

    def test_label_alone_is_not_a_business_change(self):
        quotation = self._quote("BDR111126")
        legacy = quotation_business_signature(quotation)
        items = [
            {
                "line_no": item.line_no,
                "type": item.type,
                "item_id": item.item_id,
                "currency": item.currency,
                "name": item.name,
                "description": strip_description_label(item.description),
                "qty": item.qty,
                "list_price": item.list_price,
                "discount_percent": item.discount_percent,
                "net_unit_price": item.net_unit_price,
                "extended_price": item.extended_price,
            }
            for item in quotation.items.order_by("line_no")
        ]
        self.assertEqual(
            quotation_business_signature(quotation, items=items),
            legacy,
        )
        items[0]["description"] = "HyperBDR Monthly License."
        self.assertNotEqual(
            quotation_business_signature(quotation, items=items),
            legacy,
        )

    def test_dry_run_changes_nothing(self):
        quotation = self._quote("BDR111126")
        out = StringIO()

        call_command(
            "strip_quote_description_labels",
            "BDR111126",
            stdout=out,
        )

        self.assertIn(
            "DRY RUN quotations=1 items=1 new_versions=1",
            out.getvalue(),
        )
        self.assertEqual(
            quotation.items.get(line_no=1).description,
            "License Type: HyperBDR Yearly License.",
        )
        self.assertEqual(quotation.versions.count(), 1)

    def test_apply_only_strips_labels_on_named_quotes(self):
        target = self._quote("BDR111126")
        other = self._quote("BDR999999")
        before = Quotation.objects.get(pk=target.pk)

        call_command(
            "strip_quote_description_labels",
            "BDR111126",
            "--apply",
            stdout=StringIO(),
        )

        first = target.items.get(line_no=1)
        self.assertEqual(first.description, "HyperBDR Yearly License.")
        self.assertEqual(first.name, "HyperBDR Yearly License")
        self.assertEqual(first.qty, Decimal("29"))
        self.assertEqual(first.list_price, Decimal("420"))
        self.assertEqual(first.extended_price, Decimal("12180"))
        self.assertEqual(
            target.items.get(line_no=2).description,
            "Remote Product Service - Premium 7*24",
        )
        original = target.versions.get(version_no=1).snapshot_json
        self.assertEqual(
            original["items"][0]["description"],
            "License Type: HyperBDR Yearly License.",
        )
        cleaned = target.versions.get(version_no=2)
        self.assertEqual(cleaned.status, target.status)
        expected = dict(original)
        expected["version_no"] = 2
        expected["items"] = [
            dict(original["items"][0], description="HyperBDR Yearly License.")
        ]
        self.assertEqual(cleaned.snapshot_json, expected)
        after = Quotation.objects.get(pk=target.pk)
        self.assertEqual(after.version_current, 2)
        self.assertEqual(after.quote_no, before.quote_no)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(after.grand_total, before.grand_total)
        self.assertEqual(other.versions.count(), 1)
        self.assertEqual(
            other.items.get(line_no=1).description,
            "License Type: HyperBDR Yearly License.",
        )

    def test_data_migration_cleans_only_listed_quotes(self):
        listed = self._quote("BDR051126_R1")
        other = self._quote("BDR999999")
        before = Quotation.objects.get(pk=listed.pk)

        with redirect_stdout(StringIO()) as log:
            migration.strip_labels(django_apps, None)
            migration.strip_labels(django_apps, None)

        self.assertIn(
            "BDR051126_R1: items=1 new_version=yes", log.getvalue()
        )
        self.assertIn("BDR111126: not found, skipped", log.getvalue())

        self.assertEqual(
            listed.items.get(line_no=1).description,
            "HyperBDR Yearly License.",
        )
        self.assertEqual(listed.versions.count(), 2)
        self.assertEqual(
            listed.versions.get(version_no=2).snapshot_json["items"][0][
                "description"
            ],
            "HyperBDR Yearly License.",
        )
        after = Quotation.objects.get(pk=listed.pk)
        self.assertEqual(after.version_current, 2)
        self.assertEqual(after.quote_no, before.quote_no)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(other.versions.count(), 1)
        self.assertEqual(
            other.items.get(line_no=1).description,
            "License Type: HyperBDR Yearly License.",
        )
