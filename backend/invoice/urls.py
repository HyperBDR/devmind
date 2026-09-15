from django.urls import path

from invoice.views import (
    InvoiceDetailView,
    InvoiceFeishuUploadView,
    InvoiceFeishuSyncView,
    InvoiceFormContextView,
    InvoiceListCreateView,
    InvoicePdfView,
    InvoiceSalesDashboardView,
)
from invoice.views_permissions import (
    InvoiceAccessGrantDetailView,
    InvoiceAccessGrantView,
)


urlpatterns = [
    path("access-permissions", InvoiceAccessGrantView.as_view()),
    path(
        "access-permissions/<int:permission_id>",
        InvoiceAccessGrantDetailView.as_view(),
    ),
    path("invoices", InvoiceListCreateView.as_view()),
    path("invoices/form-context", InvoiceFormContextView.as_view()),
    path("invoices/<str:invoice_id>", InvoiceDetailView.as_view()),
    path(
        "invoices/<str:invoice_id>/feishu",
        InvoiceFeishuUploadView.as_view(),
    ),
    path("invoices/<str:invoice_id>/pdf", InvoicePdfView.as_view()),
    path("feishu/sync", InvoiceFeishuSyncView.as_view()),
    path("dashboard/analytics", InvoiceSalesDashboardView.as_view()),
]
