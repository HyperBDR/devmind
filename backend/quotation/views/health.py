from quotation.metrics import export_metrics_snapshot, storage_metrics_snapshot
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "quotation-django"})


class StorageMetricsView(APIView):
    """Return low-cardinality Quote Desk provider RED metrics."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(storage_metrics_snapshot())


class ExportMetricsView(APIView):
    """Return low-cardinality quotation export stage metrics."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(export_metrics_snapshot())
