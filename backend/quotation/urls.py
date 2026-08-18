from django.urls import path

from quotation.views.access_requests import (
    QuotationAccessRequestDecisionView,
    QuotationAccessRequestView,
)
from quotation.views.audit import AuditEventExportView, AuditEventListView
from quotation.views.catalog import (
    CatalogBootstrapView,
    LegacyCatalogImportView,
    UserQuotationCatalogView,
)
from quotation.views.dashboard import (
    DashboardAnalyticsView,
    DashboardRecentView,
    DashboardSummaryView,
)
from quotation.views.documents import (
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListView,
    DocumentParseConfirmView,
    DocumentParseView,
    DocumentRestoreView,
    QuotationDocumentListCreateView,
)
from quotation.views.exports import (
    ExportJobDetailView,
    ExportJobRetryUploadView,
    QuotationExportCreateView,
    QuotationTemplateListCreateView,
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
    FeishuLoginSyncView,
    FeishuOAuthCallbackView,
    FeishuOAuthStartView,
    FeishuPreferredFolderView,
    FeishuSearchView,
    FeishuStatusView,
    FeishuSyncDifferenceResolveView,
    FeishuSyncJobDetailView,
    FeishuSyncStatusView,
    FeishuUploadView,
)
from quotation.views.health import ExportMetricsView, StorageMetricsView
from quotation.views.memberships import (
    QuotationMembershipDetailView,
    QuotationMembershipView,
)
from quotation.views.quotations import (
    QuotationDetailView,
    QuotationFormContextView,
    QuotationGenerateView,
    QuotationListCreateView,
)
from quotation.views.upload_permissions import (
    QuotationUploadPermissionDetailView,
    QuotationUploadPermissionView,
)
from quotation.views.view_permissions import (
    QuotationViewPermissionRevokeView,
    QuotationViewPermissionView,
)

urlpatterns = [
    path("dashboard/summary", DashboardSummaryView.as_view()),
    path("dashboard/analytics", DashboardAnalyticsView.as_view()),
    path("dashboard/recent", DashboardRecentView.as_view()),
    path("metrics/exports", ExportMetricsView.as_view()),
    path("metrics/storage", StorageMetricsView.as_view()),
    path("templates", QuotationTemplateListCreateView.as_view()),
    path("audit-events", AuditEventListView.as_view()),
    path("audit-events/export", AuditEventExportView.as_view()),
    path("memberships", QuotationMembershipView.as_view()),
    path(
        "memberships/<int:membership_id>",
        QuotationMembershipDetailView.as_view(),
    ),
    path("access-requests", QuotationAccessRequestView.as_view()),
    path(
        "access-requests/<int:request_id>/decision",
        QuotationAccessRequestDecisionView.as_view(),
    ),
    path("view-permissions", QuotationViewPermissionView.as_view()),
    path(
        "view-permissions/<int:permission_id>",
        QuotationViewPermissionRevokeView.as_view(),
    ),
    path(
        "upload-permissions",
        QuotationUploadPermissionView.as_view(),
    ),
    path(
        "upload-permissions/<int:permission_id>",
        QuotationUploadPermissionDetailView.as_view(),
    ),
    path("catalog", UserQuotationCatalogView.as_view()),
    path("catalog/import-legacy", LegacyCatalogImportView.as_view()),
    path("catalog/bootstrap", CatalogBootstrapView.as_view()),
    path("quotations", QuotationListCreateView.as_view()),
    path("quotations/form-context", QuotationFormContextView.as_view()),
    path("quotations/<str:quotation_id>", QuotationDetailView.as_view()),
    path(
        "quotations/<str:quotation_id>/generate",
        QuotationGenerateView.as_view(),
    ),
    path(
        "quotations/<str:quotation_id>/documents",
        QuotationDocumentListCreateView.as_view(),
    ),
    path(
        "quotations/<str:quotation_id>/exports",
        QuotationExportCreateView.as_view(),
    ),
    path("exports/<str:job_id>", ExportJobDetailView.as_view()),
    path(
        "exports/<str:job_id>/retry-upload",
        ExportJobRetryUploadView.as_view(),
    ),
    path("documents", DocumentListView.as_view()),
    path("documents/<str:document_id>", DocumentDetailView.as_view()),
    path(
        "documents/<str:document_id>/download",
        DocumentDownloadView.as_view(),
    ),
    path(
        "documents/<str:document_id>/restore",
        DocumentRestoreView.as_view(),
    ),
    path(
        "documents/<str:document_id>/parse",
        DocumentParseView.as_view(),
    ),
    path(
        "document-parse-results/<str:parse_result_id>/confirm",
        DocumentParseConfirmView.as_view(),
    ),
    path("feishu/status", FeishuStatusView.as_view()),
    path("feishu/oauth/start", FeishuOAuthStartView.as_view()),
    path("feishu/oauth/callback", FeishuOAuthCallbackView.as_view()),
    path("feishu/preferred-folder", FeishuPreferredFolderView.as_view()),
    path("feishu/folder", FeishuFolderView.as_view()),
    path("feishu/drive-tree", FeishuDriveTreeView.as_view()),
    path("feishu/search", FeishuSearchView.as_view()),
    path("feishu/sync-folder", FeishuFolderSyncView.as_view()),
    path("feishu/sync-on-login", FeishuLoginSyncView.as_view()),
    path("feishu/sync-status", FeishuSyncStatusView.as_view()),
    path(
        "feishu/sync-differences/<str:difference_id>/resolve",
        FeishuSyncDifferenceResolveView.as_view(),
    ),
    path(
        "feishu/sync-jobs/<str:job_id>",
        FeishuSyncJobDetailView.as_view(),
    ),
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
]
