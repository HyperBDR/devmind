from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.services.pdf_renderer import (
    _browser_available,
    render_html_to_pdf,
)


class PdfHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok = _browser_available()
        payload = {"ok": ok, "engine": "playwright-chromium"}
        if not ok:
            payload["detail"] = (
                "Chromium not available; run: playwright install chromium"
            )
        return Response(payload)


class PdfFromHtmlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        html = request.data.get("html") or ""
        file_name = request.data.get("file_name") or "quotation.pdf"
        if not str(file_name).lower().endswith(".pdf"):
            file_name = f"{file_name}.pdf"
        try:
            pdf_bytes = render_html_to_pdf(html)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"detail": f"PDF render failed: {exc}"}, status=500
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response
