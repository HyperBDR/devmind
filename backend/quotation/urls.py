from django.urls import path

from quotation.views.audit import (
    AuditEventExportView,
    AuditEventListView,
    SecurityAlertDetailView,
    SecurityAlertListView,
)
from quotation.views.catalog import (
    CatalogBootstrapView,
    LegacyCatalogImportView,
    UserQuotationCatalogView,
)
from quotation.views.documents import (
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListView,
    QuotationDocumentListCreateView,
)
from quotation.views.feishu import (
    FeishuDriveTreeView,
    FeishuFileAccessBatchView,
    FeishuFileAccessView,
    FeishuFileContentView,
    FeishuFolderSyncView,
    FeishuFolderView,
    FeishuHealthView,
    FeishuImportView,
    FeishuOAuthCallbackView,
    FeishuOAuthStartView,
    FeishuPreferredFolderView,
    FeishuSearchView,
    FeishuStatusView,
    FeishuUploadView,
)
from quotation.views.health import StorageMetricsView
from quotation.views.pdf import PdfFromHtmlView, PdfHealthView
from quotation.views.quotations import (
    QuotationDetailView,
    QuotationGenerateView,
    QuotationListCreateView,
)

urlpatterns = [
    path("metrics/storage", StorageMetricsView.as_view()),
    path("audit-events", AuditEventListView.as_view()),
    path("audit-events/export", AuditEventExportView.as_view()),
    path("security-alerts", SecurityAlertListView.as_view()),
    path(
        "security-alerts/<int:alert_id>",
        SecurityAlertDetailView.as_view(),
    ),
    path("catalog", UserQuotationCatalogView.as_view()),
    path("catalog/import-legacy", LegacyCatalogImportView.as_view()),
    path("catalog/bootstrap", CatalogBootstrapView.as_view()),
    path("quotations", QuotationListCreateView.as_view()),
    path("quotations/<str:quotation_id>", QuotationDetailView.as_view()),
    path(
        "quotations/<str:quotation_id>/generate",
        QuotationGenerateView.as_view(),
    ),
    path(
        "quotations/<str:quotation_id>/documents",
        QuotationDocumentListCreateView.as_view(),
    ),
    path("documents", DocumentListView.as_view()),
    path(
        "documents/<str:document_id>/download", DocumentDownloadView.as_view()
    ),
    path("documents/<str:document_id>", DocumentDetailView.as_view()),
    path("feishu/status", FeishuStatusView.as_view()),
    path("feishu/oauth/start", FeishuOAuthStartView.as_view()),
    path("feishu/oauth/callback", FeishuOAuthCallbackView.as_view()),
    path("feishu/preferred-folder", FeishuPreferredFolderView.as_view()),
    path("feishu/folder", FeishuFolderView.as_view()),
    path("feishu/drive-tree", FeishuDriveTreeView.as_view()),
    path("feishu/search", FeishuSearchView.as_view()),
    path("feishu/sync-folder", FeishuFolderSyncView.as_view()),
    path("feishu/import/<str:file_token>", FeishuImportView.as_view()),
    path("feishu/files/access/batch", FeishuFileAccessBatchView.as_view()),
    path(
        "feishu/documents/<str:document_id>/access",
        FeishuFileAccessView.as_view(),
    ),
    path(
        "feishu/documents/<str:document_id>/content",
        FeishuFileContentView.as_view(),
    ),
    path("feishu/upload", FeishuUploadView.as_view()),
    path("feishu/health", FeishuHealthView.as_view()),
    path("pdf/health", PdfHealthView.as_view()),
    path("pdf/from-html", PdfFromHtmlView.as_view()),
]
