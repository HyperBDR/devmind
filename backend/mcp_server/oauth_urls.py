from django.urls import path

from mcp_server.oauth_views import McpOAuthConsentView

urlpatterns = [
    path(
        "transactions/<uuid:transaction_id>",
        McpOAuthConsentView.as_view(),
        name="mcp-oauth-consent",
    ),
]
