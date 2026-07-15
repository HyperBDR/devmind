"""URL routes for the global assistant API."""

from django.urls import path

from ai_assistant.views import (
    CapabilityListAPIView,
    ConversationListCreateAPIView,
    ConversationMessageListCreateAPIView,
)


urlpatterns = [
    path(
        "capabilities/",
        CapabilityListAPIView.as_view(),
        name="assistant-capability-list",
    ),
    path(
        "conversations/",
        ConversationListCreateAPIView.as_view(),
        name="assistant-conversation-list",
    ),
    path(
        "conversations/<uuid:conversation_uuid>/messages/",
        ConversationMessageListCreateAPIView.as_view(),
        name="assistant-conversation-message-list",
    ),
]
