"""First local AGIOne API surface; no raw upstream proxy endpoints."""

from django.urls import path

from agione_ops import views

urlpatterns = [
    path(
        "connections/<uuid:connection_id>/live/query/",
        views.LiveOperationAPIView.as_view(),
        name="agione-ops-live-query",
    ),
    path(
        "connections/<uuid:connection_id>/snapshot/query/",
        views.SnapshotOperationAPIView.as_view(),
        name="agione-ops-snapshot-query",
    ),
    path(
        "connections/",
        views.ConnectionListCreateAPIView.as_view(),
        name="agione-ops-connections",
    ),
    path(
        "connections/<uuid:connection_id>/",
        views.ConnectionDetailAPIView.as_view(),
        name="agione-ops-connection-detail",
    ),
    path(
        "connections/<uuid:connection_id>/grants/<int:user_id>/",
        views.ConnectionGrantAPIView.as_view(),
        name="agione-ops-connection-grant",
    ),
    path(
        "connections/<uuid:connection_id>/finance/refresh/",
        views.FinanceRefreshAPIView.as_view(),
        name="agione-ops-finance-refresh",
    ),
    path(
        "connections/<uuid:connection_id>/verify/",
        views.ConnectionVerifyAPIView.as_view(),
        name="agione-ops-verify",
    ),
    path(
        "connections/<uuid:connection_id>/sync-runs/",
        views.SyncRunCreateAPIView.as_view(),
        name="agione-ops-sync-runs",
    ),
    path(
        "connections/<uuid:connection_id>/sync-runs/<uuid:run_id>/",
        views.SyncRunDetailAPIView.as_view(),
        name="agione-ops-sync-run-detail",
    ),
    path(
        "connections/<uuid:connection_id>/dashboard/query/",
        views.DashboardQueryAPIView.as_view(),
        name="agione-ops-dashboard-query",
    ),
]
