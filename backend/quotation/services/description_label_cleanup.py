import copy
from dataclasses import dataclass, field

from django.db.models import Q

from quotation.services.line_item_text import strip_description_label

VERSION_NOTE = "Removed legacy description labels"


@dataclass
class CleanupPlan:
    """Pending label cleanup for one quotation."""

    number: str
    quotation: object
    items: list = field(default_factory=list)
    latest: object = None
    snapshot: dict | None = None


def clean_snapshot(snapshot):
    """Return a copy of the snapshot with only item labels stripped."""
    if not isinstance(snapshot, dict):
        return None
    items = snapshot.get("items")
    if not isinstance(items, list):
        return None
    cleaned = copy.deepcopy(snapshot)
    changed = False
    for entry in cleaned["items"]:
        if not isinstance(entry, dict):
            continue
        original = entry.get("description")
        if not isinstance(original, str):
            continue
        stripped = strip_description_label(original)
        if stripped != original:
            entry["description"] = stripped
            changed = True
    return cleaned if changed else None


def build_cleanup_plans(quotation_model, numbers, log=print):
    """
    Collect label cleanup plans for the given quote numbers.

    Model classes are passed in so data migrations can use historical
    models. Unknown or ambiguous numbers are logged and skipped.
    """
    plans = []
    for number in dict.fromkeys(numbers):
        matches = list(
            quotation_model.objects.filter(
                Q(source_quote_no=number)
                | Q(quote_no=number)
                | Q(draft_quote_no=number)
            )
        )
        if not matches:
            log(f"NOT FOUND {number}")
            continue
        if len(matches) > 1:
            ids = ", ".join(str(item.pk) for item in matches)
            log(f"AMBIGUOUS {number}: {ids}; skipped")
            continue
        plan = CleanupPlan(number=number, quotation=matches[0])
        for item in plan.quotation.items.order_by("line_no"):
            cleaned = strip_description_label(item.description)
            if cleaned == item.description:
                continue
            log(
                f"{number} line {item.line_no}: "
                f"{item.description!r} -> {cleaned!r}"
            )
            plan.items.append((item, cleaned))
        plan.latest = plan.quotation.versions.order_by(
            "-version_no"
        ).first()
        if plan.latest is not None:
            plan.snapshot = clean_snapshot(plan.latest.snapshot_json)
        if plan.snapshot is not None:
            log(
                f"{number}: add version {plan.latest.version_no + 1} "
                f"as a cleaned copy of version {plan.latest.version_no}"
            )
        if plan.items or plan.snapshot is not None:
            plans.append(plan)
        else:
            log(f"{number}: nothing to clean")
    return plans


def apply_cleanup_plans(quotation_model, item_model, version_model, plans):
    """
    Write the plans: strip item descriptions and append cleaned versions.

    Existing versions and every other field stay untouched. Callers own
    the surrounding transaction.
    """
    for plan in plans:
        locked = quotation_model.objects.select_for_update().get(
            pk=plan.quotation.pk
        )
        if plan.items:
            for item, cleaned in plan.items:
                item.description = cleaned
            item_model.objects.bulk_update(
                [item for item, _cleaned in plan.items],
                ["description"],
            )
        if plan.snapshot is None:
            continue
        next_version_no = plan.latest.version_no + 1
        if "version_no" in plan.snapshot:
            plan.snapshot["version_no"] = next_version_no
        version_model.objects.create(
            quotation=locked,
            version_no=next_version_no,
            status=plan.latest.status,
            notes=VERSION_NOTE,
            snapshot_json=plan.snapshot,
            operator_email=None,
        )
        if locked.version_current == plan.latest.version_no:
            quotation_model.objects.filter(pk=locked.pk).update(
                version_current=next_version_no
            )


def summarize(plans):
    """Return a one-line summary of the plans."""
    item_count = sum(len(plan.items) for plan in plans)
    version_count = sum(1 for plan in plans if plan.snapshot is not None)
    return (
        f"quotations={len(plans)} "
        f"items={item_count} "
        f"new_versions={version_count}"
    )
