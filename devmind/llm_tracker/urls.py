"""
URL configuration for llm_tracker admin API.

Include under an admin prefix, e.g.:
    path('api/v1/admin/', include('llm_tracker.urls')),
"""
from django.urls import path

from .views import AdminLLMUsageListView, AdminTokenStatsView

app_name = "llm_tracker"

urlpatterns = [
    path("token-stats/", AdminTokenStatsView.as_view(), name="token-stats"),
    path("llm-usage/", AdminLLMUsageListView.as_view(), name="llm-usage"),
]
