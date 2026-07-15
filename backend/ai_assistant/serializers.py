"""DRF serializers for global assistant API boundaries."""

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

    message = serializers.CharField(allow_blank=False, trim_whitespace=True)
    page_context = serializers.JSONField(required=False, default=dict)
    llm_config_uuid = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )


class MessageSerializer(serializers.ModelSerializer):
    """Serialize stored conversation messages."""

    class Meta:
        model = AssistantMessage
        fields = ("id", "role", "content", "metadata", "created_at")
