import copy
import re

from django.db import migrations
from django.db.models import Q

QUOTE_NUMBERS = (
    "BDR111126",
    "BDR101126",
    "BDR061126",
    "BDR051126.1_R1",
    "BDR051126_R1",
    "BDR031126.1",
    "BDR031126_R1",
)
VERSION_NOTE = "Removed legacy description labels"
LABEL_PATTERN = re.compile(
    r"^\s*(?:license\s+type|description)\s*[:：]\s*",
    re.IGNORECASE,
)


def _strip(value):
    """Drop one leading label; keep text that would become empty."""
    if not isinstance(value, str) or not value:
        return value
    stripped = LABEL_PATTERN.sub("", value, count=1)
    return stripped if stripped.strip() else value


def _clean_snapshot(snapshot):
    """Return a copy of the snapshot with only item labels stripped."""
    if not isinstance(snapshot, dict):
        return None
    if not isinstance(snapshot.get("items"), list):
        return None
    cleaned = copy.deepcopy(snapshot)
    changed = False
    for entry in cleaned["items"]:
        if not isinstance(entry, dict):
            continue
        original = entry.get("description")
        stripped = _strip(original)
        if stripped != original:
            entry["description"] = stripped
            changed = True
    return cleaned if changed else None


def strip_labels(apps, schema_editor):
    """Strip legacy description labels from the listed quotations only."""
    Quotation = apps.get_model("quotation", "Quotation")
    QuotationItem = apps.get_model("quotation", "QuotationItem")
    QuotationVersion = apps.get_model("quotation", "QuotationVersion")
    for number in QUOTE_NUMBERS:
        matches = list(
            Quotation.objects.select_for_update().filter(
                Q(source_quote_no=number)
                | Q(quote_no=number)
                | Q(draft_quote_no=number)
            )
        )
        if len(matches) != 1:
            state = "not found" if not matches else "ambiguous"
            print(f"\n  description labels {number}: {state}, skipped")
            continue
        quotation = matches[0]
        items = []
        for item in quotation.items.order_by("line_no"):
            cleaned = _strip(item.description)
            if cleaned != item.description:
                item.description = cleaned
                items.append(item)
        if items:
            QuotationItem.objects.bulk_update(items, ["description"])
        latest = quotation.versions.order_by("-version_no").first()
        snapshot = _clean_snapshot(latest.snapshot_json) if latest else None
        if snapshot is not None:
            next_version_no = latest.version_no + 1
            if "version_no" in snapshot:
                snapshot["version_no"] = next_version_no
            QuotationVersion.objects.create(
                quotation=quotation,
                version_no=next_version_no,
                status=latest.status,
                notes=VERSION_NOTE,
                snapshot_json=snapshot,
                operator_email=None,
            )
            if quotation.version_current == latest.version_no:
                Quotation.objects.filter(pk=quotation.pk).update(
                    version_current=next_version_no
                )
        print(
            f"\n  description labels {number}: items={len(items)} "
            f"new_version={'yes' if snapshot is not None else 'no'}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("quotation", "0037_imported_quote_dates_nullable"),
    ]

    operations = [
        migrations.RunPython(strip_labels, migrations.RunPython.noop),
    ]
