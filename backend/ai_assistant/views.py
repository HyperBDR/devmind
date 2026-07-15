"""Thin HTTP views for the global assistant API."""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.models import AssistantConversation, AssistantMessage
from ai_assistant.registry import CapabilityNotFound, capability_registry
from ai_assistant.serializers import (
    ConversationCreateSerializer,
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from ai_assistant.services import (
    list_capabilities_for_user,
    user_can_access_capability,
)


def _error(code: str, message: str, status: int) -> Response:
    return Response(
        {"error": {"code": code, "message": message}},
        status=status,
    )


class CapabilityListAPIView(APIView):
    """List enabled assistant capabilities authorized for the user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"data": list_capabilities_for_user(request.user)})


class ConversationListCreateAPIView(APIView):
    """List or create conversations owned by the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = AssistantConversation.objects.filter(
            user=request.user,
        )
        app_key = str(request.query_params.get("app_key") or "").strip()
        if app_key:
            conversations = conversations.filter(app_key=app_key)
        rows = conversations[:50]
        return Response(
            {
                "data": ConversationSerializer(rows, many=True).data,
                "pagination": {"limit": 50},
            }
        )

    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app_key = serializer.validated_data["app_key"]
        try:
            capability = capability_registry.require(app_key)
        except CapabilityNotFound:
            return _error(
                "CAPABILITY_NOT_FOUND",
                "The requested app does not provide AI support.",
                404,
            )
        if not user_can_access_capability(request.user, capability):
            return _error(
                "CAPABILITY_FORBIDDEN",
                "You cannot use this app assistant.",
                403,
            )
        conversation = AssistantConversation.objects.create(
            user=request.user,
            app_key=capability.app_key,
            capability_version=capability.version,
        )
        return Response(
            {"data": ConversationSerializer(conversation).data},
            status=201,
        )


class ConversationMessageListCreateAPIView(APIView):
    """List messages or stream a response from the bound app Agent."""

    permission_classes = [IsAuthenticated]

    def _conversation(self, request, conversation_uuid):
        return AssistantConversation.objects.filter(
            uuid=conversation_uuid,
            user=request.user,
        ).first()

    def get(self, request, conversation_uuid):
        conversation = self._conversation(request, conversation_uuid)
        if conversation is None:
            return _error(
                "CONVERSATION_NOT_FOUND",
                "Conversation not found.",
                404,
            )
        return Response(
            {
                "data": MessageSerializer(
                    conversation.messages.all(),
                    many=True,
                ).data
            }
        )

    def post(self, request, conversation_uuid):
        conversation = self._conversation(request, conversation_uuid)
        if conversation is None:
            return _error(
                "CONVERSATION_NOT_FOUND",
                "Conversation not found.",
                404,
            )
        capability = capability_registry.require(conversation.app_key)
        if not user_can_access_capability(request.user, capability):
            return _error(
                "CAPABILITY_FORBIDDEN",
                "You cannot use this app assistant.",
                403,
            )
        if capability.stream_handler is None:
            return _error(
                "CAPABILITY_UNAVAILABLE",
                "This app assistant cannot process messages.",
                503,
            )
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        history = list(
            conversation.messages.order_by("created_at", "id").values(
                "role",
                "content",
            )
        )[-8:]
        AssistantMessage.objects.create(
            conversation=conversation,
            role=AssistantMessage.Role.USER,
            content=message,
        )

        def event_stream():
            chunks = []
            final_reply = ""
            events = capability.stream_handler(
                message=message,
                history=history,
                preferred_config_uuid=serializer.validated_data.get(
                    "llm_config_uuid",
                    "",
                ),
                user_id=request.user.id,
            )
            for event in events:
                if event.get("type") == "chunk":
                    chunks.append(str(event.get("content") or ""))
                if event.get("type") == "done":
                    final_reply = str(event.get("reply") or "")
                yield "data: " + json.dumps(
                    event,
                    ensure_ascii=False,
                    default=str,
                ) + "\n\n"
            content = final_reply or "".join(chunks)
            if content:
                AssistantMessage.objects.create(
                    conversation=conversation,
                    role=AssistantMessage.Role.ASSISTANT,
                    content=content,
                )

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
