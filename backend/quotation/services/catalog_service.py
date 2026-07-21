from __future__ import annotations

from django.db import transaction

from quotation.models import UserQuotationCatalog

CATALOG_FIELDS = (
    "products",
    "services",
    "discounts",
    "product_lines",
    "payment_terms",
)
CATALOG_ITEM_TYPES = {
    "products": "software_product",
    "services": "service_item",
    "discounts": "discount",
    "product_lines": "product_line",
    "payment_terms": "payment_term",
}


def _catalog_item_key(field: str, item: dict) -> str:
    """Return a stable key for one catalog item."""
    candidates = (
        ("value", "id", "code", "name")
        if field in {"product_lines", "payment_terms"}
        else ("id", "code", "name", "value")
    )
    for key in candidates:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _catalog_item_label(item: dict, fallback: str) -> str:
    """Return the clearest user-facing catalog item label."""
    for key in ("name", "label", "code", "value", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return fallback


def _is_automatic_catalog_create(field: str, item: dict) -> bool:
    """Return whether a catalog item came from quote description sync."""
    prefixes = {
        "products": "prod-auto-",
        "services": "serv-auto-",
    }
    prefix = prefixes.get(field)
    item_id = str(item.get("id") or "")
    return bool(prefix and item_id.startswith(prefix))


def catalog_snapshot(catalog: UserQuotationCatalog | None) -> dict:
    """Return catalog lists used for semantic audit comparison."""
    return {
        field: list(getattr(catalog, field, []) or []) if catalog else []
        for field in CATALOG_FIELDS
    }


def catalog_item_changes(before: dict, after: dict) -> list[dict]:
    """Return semantic item-level changes between catalog snapshots."""
    changes = []
    for field in CATALOG_FIELDS:
        before_items = {
            _catalog_item_key(field, item): item
            for item in before.get(field, [])
            if isinstance(item, dict) and _catalog_item_key(field, item)
        }
        after_items = {
            _catalog_item_key(field, item): item
            for item in after.get(field, [])
            if isinstance(item, dict) and _catalog_item_key(field, item)
        }
        for key in sorted(before_items.keys() - after_items.keys()):
            item = before_items[key]
            changes.append(
                {
                    "action": "delete",
                    "target_type": CATALOG_ITEM_TYPES[field],
                    "target_id": key,
                    "target_label": _catalog_item_label(item, key),
                    "fields": [],
                }
            )
        for key in sorted(after_items.keys() - before_items.keys()):
            item = after_items[key]
            if _is_automatic_catalog_create(field, item):
                continue
            changes.append(
                {
                    "action": "create",
                    "target_type": CATALOG_ITEM_TYPES[field],
                    "target_id": key,
                    "target_label": _catalog_item_label(item, key),
                    "fields": [],
                }
            )
        for key in sorted(before_items.keys() & after_items.keys()):
            old_item = before_items[key]
            new_item = after_items[key]
            changed_fields = sorted(
                field_name
                for field_name in set(old_item) | set(new_item)
                if old_item.get(field_name) != new_item.get(field_name)
            )
            if changed_fields:
                changes.append(
                    {
                        "action": "update",
                        "target_type": CATALOG_ITEM_TYPES[field],
                        "target_id": key,
                        "target_label": _catalog_item_label(new_item, key),
                        "fields": changed_fields,
                    }
                )
    return changes


def empty_catalog_data() -> dict:
    return {
        "version": "",
        "initialized": False,
        **{field: [] for field in CATALOG_FIELDS},
        "updated_at": None,
    }


def catalog_values(validated_data: dict) -> dict:
    return {
        "catalog_version": validated_data.get("version", ""),
        "initialized": True,
        **{field: validated_data.get(field, []) for field in CATALOG_FIELDS},
    }


@transaction.atomic
def replace_catalog(user, validated_data: dict) -> UserQuotationCatalog:
    (
        catalog,
        _created,
    ) = UserQuotationCatalog.objects.select_for_update().get_or_create(
        user=user
    )
    for field, value in catalog_values(validated_data).items():
        setattr(catalog, field, value)
    catalog.save()
    return catalog


@transaction.atomic
def initialize_catalog(
    user,
    validated_data: dict,
) -> tuple[UserQuotationCatalog, bool]:
    (
        catalog,
        _created,
    ) = UserQuotationCatalog.objects.select_for_update().get_or_create(
        user=user
    )
    has_server_data = catalog.initialized or any(
        getattr(catalog, field) for field in CATALOG_FIELDS
    )
    if has_server_data:
        return catalog, False
    for field, value in catalog_values(validated_data).items():
        setattr(catalog, field, value)
    catalog.save()
    return catalog, True
