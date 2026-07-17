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
