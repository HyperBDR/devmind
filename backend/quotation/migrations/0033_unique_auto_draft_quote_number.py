import re

from django.db import migrations, models


AUTO_NUMBER_PATTERN = re.compile(
    r"^(.+\d{6})(?:\.(\d+))?(?:_R\d+)?$",
    re.IGNORECASE,
)


def _record_sequence(used_sequences, quote_no):
    """Record an automatic number in its root sequence."""
    match = AUTO_NUMBER_PATTERN.match(str(quote_no or "").strip())
    if not match:
        return
    root = match.group(1).lower()
    used_sequences.setdefault(root, set()).add(int(match.group(2) or 0))


def deduplicate_auto_draft_numbers(apps, schema_editor):
    """Renumber duplicate automatic drafts before adding the constraint."""
    quotation_model = apps.get_model("quotation", "Quotation")
    version_model = apps.get_model("quotation", "QuotationVersion")
    used_sequences = {}

    for quote_no in quotation_model.objects.exclude(
        quote_no__isnull=True,
    ).exclude(quote_no="").values_list("quote_no", flat=True):
        _record_sequence(used_sequences, quote_no)
    for snapshot in version_model.objects.values_list(
        "snapshot_json",
        flat=True,
    ):
        if isinstance(snapshot, dict):
            _record_sequence(used_sequences, snapshot.get("quote_no"))

    drafts = quotation_model.objects.filter(
        status="draft",
        numbering_mode="auto",
    ).exclude(draft_quote_no="").order_by("created_at", "id")
    for draft_quote_no in drafts.values_list("draft_quote_no", flat=True):
        _record_sequence(used_sequences, draft_quote_no)

    seen = set()
    for quotation in drafts.iterator():
        current = quotation.draft_quote_no.strip()
        normalized = current.lower()
        if normalized not in seen:
            seen.add(normalized)
            continue

        match = AUTO_NUMBER_PATTERN.match(current)
        if match:
            root = match.group(1)
            root_key = root.lower()
            used = used_sequences.setdefault(root_key, set())
            suffix = 1
            while suffix in used:
                suffix += 1
            replacement = f"{root}.{suffix}"
            used.add(suffix)
        else:
            suffix = 1
            while True:
                ending = f".{suffix}"
                replacement = f"{current[:120 - len(ending)]}{ending}"
                if replacement.lower() not in seen:
                    break
                suffix += 1

        quotation.draft_quote_no = replacement
        quotation.save(update_fields=["draft_quote_no"])
        seen.add(replacement.lower())


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0032_quotationnote"),
    ]

    operations = [
        migrations.RunPython(
            deduplicate_auto_draft_numbers,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="quotation",
            constraint=models.UniqueConstraint(
                fields=("draft_quote_no",),
                condition=(
                    models.Q(status="draft")
                    & models.Q(numbering_mode="auto")
                    & ~models.Q(draft_quote_no="")
                ),
                name="quote_draft_auto_no_uniq",
            ),
        ),
    ]
