from django.urls import path

from .views import MonthlyTrendsAPIView, OverviewAPIView, TenantsAPIView, TrendsAPIView

urlpatterns = [
    path("overview/", OverviewAPIView.as_view(), name="hyperbdr-dashboard-overview"),
    path("trends/", TrendsAPIView.as_view(), name="hyperbdr-dashboard-trends"),
    path("trends/monthly/", MonthlyTrendsAPIView.as_view(), name="hyperbdr-dashboard-monthly-trends"),
    path("tenants/", TenantsAPIView.as_view(), name="hyperbdr-dashboard-tenants"),
]
