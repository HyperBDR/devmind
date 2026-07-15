"""DRF serializers for global assistant API boundaries."""

import json

from rest_framework import serializers

from ai_assistant.models import AssistantConversation, AssistantMessage


class ConversationCreateSerializer(serializers.Serializer):
    """Validate a new app-scoped conversation."""

    app_key = serializers.CharField(max_length=64)


class ConversationSerializer(serializers.ModelSerializer):
    """Serialize conversation metadata without leaking messages."""

    class Meta:
        model = AssistantConversation
        fields = (
            "uuid",
            "app_key",
            "title",
            "summary",
            "created_at",
            "updated_at",
        )


class MessageCreateSerializer(serializers.Serializer):
    """Validate one user message."""

    message = serializers.CharField(
        allow_blank=False,
        max_length=8000,
        trim_whitespace=True,
    )
    page_context = serializers.JSONField(required=False, default=dict)
    llm_config_uuid = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )

    def validate_page_context(self, value):
        """Keep optional route context bounded before runtime use."""

        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if len(serialized) > 16000:
            raise serializers.ValidationError("Page context is too large.")
        return value


class MessageSerializer(serializers.ModelSerializer):
    """Serialize stored conversation messages."""

    class Meta:
        model = AssistantMessage
        fields = ("id", "role", "content", "metadata", "created_at")
