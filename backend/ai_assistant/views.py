"""Thin HTTP views for the global assistant API."""

from __future__ import annotations

import json
import logging

from django.http import StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.models import AssistantConversation, AssistantMessage
from ai_assistant.policies import (
    build_operations_only_reply,
    finalize_operations_answer,
    is_technical_implementation_request,
    sanitize_operations_history,
)
from ai_assistant.registry import CapabilityNotFound, capability_registry
from ai_assistant.runtime import stream_assistant_response
from ai_assistant.serializers import (
    ConversationCreateSerializer,
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from ai_assistant.services import (
    authorized_app_keys,
    list_capabilities_for_user,
    user_can_access_capability,
)

logger = logging.getLogger(__name__)


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
            app_key__in=authorized_app_keys(request.user),
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


class ConversationDetailAPIView(APIView):
    """Delete one conversation owned by the current user."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, conversation_uuid):
        conversation = AssistantConversation.objects.filter(
            uuid=conversation_uuid,
            user=request.user,
        ).first()
        if conversation is None:
            return _error(
                "CONVERSATION_NOT_FOUND",
                "Conversation not found.",
                404,
            )
        capability = capability_registry.get(conversation.app_key)
        if capability is None or not user_can_access_capability(
            request.user,
            capability,
        ):
            return _error(
                "CAPABILITY_FORBIDDEN",
                "You cannot use this app assistant.",
                403,
            )
        conversation.delete()
        return Response(status=204)


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
        capability = capability_registry.get(conversation.app_key)
        if capability is None or not user_can_access_capability(
            request.user,
            capability,
        ):
            return _error(
                "CAPABILITY_FORBIDDEN",
                "You cannot use this app assistant.",
                403,
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
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        history = list(
            conversation.messages.order_by("created_at", "id").values(
                "role",
                "content",
            )
        )[-8:]
        operational_history = sanitize_operations_history(history)
        if not conversation.title:
            conversation.title = message[:80]
            conversation.save(update_fields=["title", "updated_at"])
        AssistantMessage.objects.create(
            conversation=conversation,
            role=AssistantMessage.Role.USER,
            content=message,
        )

        def event_stream():
            chunks = []
            final_reply = ""
            try:
                if is_technical_implementation_request(message):
                    content = finalize_operations_answer(
                        build_operations_only_reply(message),
                        message=message,
                        history=operational_history,
                    )
                    events = iter(
                        [
                            {"type": "chunk", "content": content},
                            {
                                "type": "done",
                                "ok": True,
                                "reply": content,
                                "usage": {"total_tokens": 0},
                            },
                        ]
                    )
                elif capability.stream_handler is not None:
                    stream_handler = capability.stream_handler
                    events = stream_handler(
                        message=message,
                        history=operational_history,
                        preferred_config_uuid=serializer.validated_data.get(
                            "llm_config_uuid",
                            "",
                        ),
                        user_id=request.user.id,
                    )
                else:
                    events = stream_assistant_response(
                        capability=capability,
                        message=message,
                        history=operational_history,
                        preferred_config_uuid=serializer.validated_data.get(
                            "llm_config_uuid",
                            "",
                        ),
                        user_id=request.user.id,
                        conversation_id=str(conversation.uuid),
                        page_context=serializer.validated_data.get(
                            "page_context",
                            {},
                        ),
                    )
                for event in events:
                    if event.get("type") == "chunk":
                        chunks.append(str(event.get("content") or ""))
                    if event.get("type") == "done":
                        raw_reply = str(event.get("reply") or "".join(chunks))
                        final_reply = finalize_operations_answer(
                            raw_reply,
                            message=message,
                            history=operational_history,
                        )
                        event = {**event, "reply": final_reply}
                    if event.get("type") == "error":
                        event = {
                            "type": "error",
                            "detail": "Assistant response failed.",
                        }
                    yield "data: " + json.dumps(
                        event,
                        ensure_ascii=False,
                        default=str,
                    ) + "\n\n"
            except Exception:
                logger.exception(
                    "Assistant stream failed for app %s",
                    conversation.app_key,
                )
                yield "data: " + json.dumps(
                    {
                        "type": "error",
                        "detail": "Assistant response failed.",
                    },
                    ensure_ascii=False,
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
