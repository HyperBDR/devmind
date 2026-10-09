from django.urls import path

from mcp_server.robot_views import (
    McpRobotCredentialDetailView,
    McpRobotCredentialListView,
)

urlpatterns = [
    path("", McpRobotCredentialListView.as_view(), name="mcp-robots"),
    path(
        "<uuid:credential_id>/",
        McpRobotCredentialDetailView.as_view(),
        name="mcp-robot-detail",
    ),
]
