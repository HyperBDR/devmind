from django.urls import path

from .views import (
    CollectionTaskDetailAPIView,
    CollectionTaskListAPIView,
    DashboardAPIView,
    DataSourceCollectAPIView,
    DataSourceDetailAPIView,
    DataSourceListCreateAPIView,
    HealthAPIView,
    LicenseListAPIView,
    LicenseUsageAPIView,
    MonthlyTrendsAPIView,
    OverviewAPIView,
    TaskExecutionAPIView,
    TenantDetailAPIView,
    TenantListAPIView,
    TenantStatusAPIView,
    TenantsAPIView,
    TrendsAPIView,
    TriggerCollectionAPIView,
)

urlpatterns = [
    # Dashboard product-facing endpoints
    path("overview/", OverviewAPIView.as_view(), name="hyperbdr-dashboard-overview"),
    path("trends/", TrendsAPIView.as_view(), name="hyperbdr-dashboard-trends"),
    path("trends/monthly/", MonthlyTrendsAPIView.as_view(), name="hyperbdr-dashboard-monthly-trends"),
    path("tenants/", TenantsAPIView.as_view(), name="hyperbdr-dashboard-tenants"),
    # Analyzer / monitor CRUD endpoints
    path("data-sources/", DataSourceListCreateAPIView.as_view(), name="data-source-list"),
    path("data-sources/<int:data_source_id>/", DataSourceDetailAPIView.as_view(), name="data-source-detail"),
    path("data-sources/<int:data_source_id>/collect/", DataSourceCollectAPIView.as_view(), name="data-source-collect"),
    path("tenants/admin/", TenantListAPIView.as_view(), name="tenant-list"),
    path("tenants/<str:tenant_id>/", TenantDetailAPIView.as_view(), name="tenant-detail"),
    path("licenses/", LicenseListAPIView.as_view(), name="license-list"),
    path("tasks/", CollectionTaskListAPIView.as_view(), name="task-list"),
    path("tasks/collect/", TriggerCollectionAPIView.as_view(), name="task-collect"),
    path("tasks/<int:task_id>/", CollectionTaskDetailAPIView.as_view(), name="task-detail"),
    path("analyzer/dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("analyzer/tenant-status/", TenantStatusAPIView.as_view(), name="tenant-status"),
    path("analyzer/license-usage/", LicenseUsageAPIView.as_view(), name="license-usage"),
    path("analyzer/task-execution/", TaskExecutionAPIView.as_view(), name="task-execution"),
    path("health/", HealthAPIView.as_view(), name="health"),
]
