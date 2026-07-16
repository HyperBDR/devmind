from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import UserQuotationCatalog
from quotation.serializers import (
    UserQuotationCatalogSerializer,
    UserQuotationCatalogWriteSerializer,
)
from quotation.services.catalog_service import (
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
        catalog = replace_catalog(request.user, serializer.validated_data)
        return Response(serialize_catalog(catalog))


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
