"""
URL configuration for cloud billing API.
"""
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (
    AlertRecordViewSet,
    AlertRuleViewSet,
    BillingDataViewSet,
    BillingTaskViewSet,
    CloudProviderViewSet,
)

router = DefaultRouter()
router.register(
    r'providers', CloudProviderViewSet, basename='provider'
)
router.register(
    r'billing-data', BillingDataViewSet, basename='billing-data'
)
router.register(
    r'alert-rules', AlertRuleViewSet, basename='alert-rule'
)
router.register(
    r'alert-records', AlertRecordViewSet, basename='alert-record'
)
router.register(r'tasks', BillingTaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
]
