"""
Minimal URLconf for cloud_billing tests (no agentcore_metering).
Mounts cloud_billing API at same path as main project.
"""
from django.urls import path, include

urlpatterns = [
    path('api/v1/cloud-billing/', include('cloud_billing.urls')),
]
