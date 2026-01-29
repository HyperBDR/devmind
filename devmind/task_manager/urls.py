"""
URL configuration for task management API.
"""
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import TaskExecutionViewSet

router = DefaultRouter()
router.register(
    r'executions', TaskExecutionViewSet, basename='task-execution'
)

urlpatterns = [
    path('', include(router.urls)),
]
