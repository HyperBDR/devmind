from django.urls import path, include

urlpatterns = [
    path("api/v1/hyperbdr-dashboard/", include("hyperbdr_dashboard.urls")),
]
