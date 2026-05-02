"""
SALS URL routing: /api/v1/sals/
"""
from django.urls import path

from . import views

urlpatterns = [
    # Health
    path("ping/", views.PingAPIView.as_view(), name="sals-ping"),

    # Init / sync
    path("init-db/", views.InitDbAPIView.as_view(), name="sals-init-db"),
    path("sync/status/", views.SyncStatusAPIView.as_view(), name="sals-sync-status"),

    # Stats
    path("stats/kpi/", views.KpiStatAPIView.as_view(), name="sals-stats-kpi"),
    path("stats/priority-dist/", views.PriorityDistAPIView.as_view(), name="sals-stats-priority-dist"),
    path("stats/state-dist/", views.StateDistAPIView.as_view(), name="sals-stats-state-dist"),
    path("stats/monthly-trend/", views.MonthlyTrendAPIView.as_view(), name="sals-stats-monthly-trend"),
    path("stats/group-stats/", views.GroupStatsAPIView.as_view(), name="sals-stats-group-stats"),
    path("stats/assignee-stats/", views.AssigneeStatsAPIView.as_view(), name="sals-stats-assignee-stats"),
    path("stats/customer-stats/", views.CustomerStatsAPIView.as_view(), name="sals-stats-customer-stats"),
    path("stats/product-stats/", views.ProductStatsAPIView.as_view(), name="sals-stats-product-stats"),
    path("stats/sla-stats/", views.SlaStatsAPIView.as_view(), name="sals-stats-sla-stats"),
    path("stats/keywords/", views.KeywordStatsAPIView.as_view(), name="sals-stats-keywords"),
    path("stats/product-state-matrix/", views.ProductStateMatrixAPIView.as_view(), name="sals-stats-product-state-matrix"),
    path("stats/daily-breakdown/", views.DailyBreakdownAPIView.as_view(), name="sals-stats-daily-breakdown"),

    # Incidents
    path("incidents/", views.IncidentListAPIView.as_view(), name="sals-incidents"),
    path("incidents/count/", views.IncidentCountAPIView.as_view(), name="sals-incidents-count"),
    path("incidents/recent/", views.RecentIncidentsAPIView.as_view(), name="sals-incidents-recent"),

    # Companies
    path("companies/", views.CompanyListAPIView.as_view(), name="sals-companies"),
    path("companies/count/", views.CompanyCountAPIView.as_view(), name="sals-company-count"),
    path("companies/sync/", views.SyncCompaniesAPIView.as_view(), name="sals-companies-sync"),

    # Users
    path("users/", views.UserListAPIView.as_view(), name="sals-users"),
    path("users/count/", views.UserCountAPIView.as_view(), name="sals-users-count"),
    path("users/sync/", views.SyncUsersAPIView.as_view(), name="sals-users-sync"),

    # Dashboard
    path("dashboard/", views.DashboardAPIView.as_view(), name="sals-dashboard"),
]
