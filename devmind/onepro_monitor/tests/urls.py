from django.urls import include, path


urlpatterns = [
    path("api/v1/onepro-monitor/", include("onepro_monitor.urls")),
]

