from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.audit import record_audit_event
from quotation.models import AuditEvent, UserQuotationCatalog
from quotation.serializers import (
    UserQuotationCatalogSerializer,
    UserQuotationCatalogWriteSerializer,
)
from quotation.services.catalog_service import (
    catalog_item_changes,
    catalog_snapshot,
    empty_catalog_data,
    initialize_catalog,
    replace_catalog,
)


def serialize_catalog(catalog: UserQuotationCatalog | None) -> dict:
    if not catalog:
        return empty_catalog_data()
    return UserQuotationCatalogSerializer(catalog).data


class UserQuotationCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        catalog = UserQuotationCatalog.objects.filter(
            user=request.user
        ).first()
        return Response(serialize_catalog(catalog))

    def put(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            existing = UserQuotationCatalog.objects.select_for_update().filter(
                user=request.user
            ).first()
            before = catalog_snapshot(existing)
            catalog = replace_catalog(request.user, serializer.validated_data)
            after = catalog_snapshot(catalog)
            for change in catalog_item_changes(before, after):
                record_audit_event(
                    request=request,
                    module="catalog",
                    action=change["action"],
                    result=AuditEvent.RESULT_SUCCEEDED,
                    target_type=change["target_type"],
                    target_id=change["target_id"],
                    target_label=change["target_label"],
                    changes={"fields": change["fields"]}
                    if change["fields"]
                    else {},
                )
        response = Response(serialize_catalog(catalog))
        response._quotation_audit_handled = True
        return response


class LegacyCatalogImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog, imported = initialize_catalog(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {
                "imported": imported,
                "catalog": serialize_catalog(catalog),
            }
        )


class CatalogBootstrapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserQuotationCatalogWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog, created = initialize_catalog(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {
                "created": created,
                "catalog": serialize_catalog(catalog),
            }
        )
