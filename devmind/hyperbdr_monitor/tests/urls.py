from django.urls import include, path


urlpatterns = [
    path("api/v1/hyperbdr-monitor/", include("hyperbdr_monitor.urls")),
]

