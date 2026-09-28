from django.urls import include, path

urlpatterns = [
    path("api/v1/hyperbdr-dashboard/", include("hyperbdr_dashboard.urls")),
]
