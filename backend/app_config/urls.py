"""
URL configuration for global configuration API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    GlobalConfigViewSet,
    GlobalConfigByKeyView,
    GlobalConfigByCategoryView,
)

router = DefaultRouter()
router.register(r'config', GlobalConfigViewSet, basename='global-config')
# Register settings as an alias for config
router.register(r'settings', GlobalConfigViewSet, basename='settings')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path(
        'api/v1/config/key/<str:key>/',
        GlobalConfigByKeyView.as_view(),
        name='config-by-key'
    ),
    path(
        'api/v1/config/category/<str:category>/',
        GlobalConfigByCategoryView.as_view(),
        name='config-by-category'
    ),
]
