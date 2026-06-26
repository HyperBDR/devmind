"""URLs for accounts tests."""
from django.urls import path

from accounts.views import CustomPasswordChangeView
from accounts.views.management import (
    ManagementGroupListView,
    ManagementUserListView,
)


urlpatterns = [
    path(
        "api/v1/auth/password/change",
        CustomPasswordChangeView.as_view(),
    ),
    path(
        "api/v1/management/users/",
        ManagementUserListView.as_view(),
    ),
    path(
        "api/v1/management/groups/",
        ManagementGroupListView.as_view(),
    ),
]
