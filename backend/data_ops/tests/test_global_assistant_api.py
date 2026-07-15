import json

import pytest
from django.urls import reverse

from ai_assistant.contracts import AssistantCapability
from ai_assistant.models import AssistantConversation, AssistantMessage
from ai_assistant.registry import capability_registry


@pytest.fixture
def restore_capabilities():
    original = capability_registry.all()
    yield
    capability_registry.reset()
    for capability in original:
        capability_registry.register(capability)


@pytest.mark.django_db
def test_capabilities_lists_registered_apps_allowed_for_user(
    api_client,
    data_ops_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("assistant-capability-list"))

    assert response.status_code == 200
    assert [item["app_key"] for item in response.data["data"]] == [
        "data_ops"
    ]
    assert response.data["data"][0]["skill_count"] >= 3


@pytest.mark.django_db
def test_conversation_rejects_app_without_registered_capability(
    api_client,
    data_ops_user,
):
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.post(
        reverse("assistant-conversation-list"),
        {"app_key": "missing_app"},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "CAPABILITY_NOT_FOUND"


@pytest.mark.django_db
def test_user_can_delete_own_conversation(
    api_client,
    data_ops_user,
    monkeypatch,
):
    conversation = AssistantConversation.objects.create(
        user=data_ops_user,
        app_key="data_ops",
    )
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.delete(
        reverse(
            "assistant-conversation-detail",
            kwargs={"conversation_uuid": conversation.uuid},
        )
    )

    assert response.status_code == 204
    assert not AssistantConversation.objects.filter(
        uuid=conversation.uuid,
    ).exists()


@pytest.mark.django_db
def test_conversations_are_hidden_after_app_access_is_removed(
    api_client,
    data_ops_user,
    monkeypatch,
):
    AssistantConversation.objects.create(
        user=data_ops_user,
        app_key="data_ops",
        title="Sensitive prior analysis",
    )
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: [],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.get(reverse("assistant-conversation-list"))

    assert response.status_code == 200
    assert response.data["data"] == []


@pytest.mark.django_db
def test_message_rejects_oversized_input(
    api_client,
    data_ops_user,
    monkeypatch,
):
    conversation = AssistantConversation.objects.create(
        user=data_ops_user,
        app_key="data_ops",
    )
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)

    response = api_client.post(
        reverse(
            "assistant-conversation-message-list",
            kwargs={"conversation_uuid": conversation.uuid},
        ),
        {"message": "x" * 8001},
        format="json",
    )

    assert response.status_code == 400
    assert not AssistantMessage.objects.filter(
        conversation=conversation,
    ).exists()


@pytest.mark.django_db
def test_message_stream_uses_conversation_app_and_persists_messages(
    api_client,
    data_ops_user,
    monkeypatch,
    restore_capabilities,
):
    def fake_stream(**kwargs):
        assert kwargs["message"] == "hello"
        yield {"type": "chunk", "content": "world"}
        yield {"type": "done", "reply": "world", "usage": {}}

    capability_registry.reset()
    capability_registry.register(
        AssistantCapability(
            app_key="data_ops",
            display_name="Data Ops Assistant",
            required_feature="data_ops",
            instructions="Test.",
            tools=(),
            stream_handler=fake_stream,
        )
    )
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)
    conversation_response = api_client.post(
        reverse("assistant-conversation-list"),
        {"app_key": "data_ops"},
        format="json",
    )
    conversation_uuid = conversation_response.data["data"]["uuid"]

    response = api_client.post(
        reverse(
            "assistant-conversation-message-list",
            kwargs={"conversation_uuid": conversation_uuid},
        ),
        {"message": "hello", "app_key": "cloud_billing"},
        format="json",
    )
    body = b"".join(response.streaming_content).decode("utf-8")
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert response.status_code == 200
    assert payloads[-1]["type"] == "done"
    conversation = AssistantConversation.objects.get(
        uuid=conversation_uuid,
    )
    assert conversation.app_key == "data_ops"
    assert conversation.title == "hello"
    assert list(
        AssistantMessage.objects.filter(
            conversation=conversation,
        ).values_list("role", "content")
    ) == [("user", "hello"), ("assistant", "world")]


@pytest.mark.django_db
def test_stream_failure_returns_a_safe_error_event(
    api_client,
    data_ops_user,
    monkeypatch,
    restore_capabilities,
):
    def failing_stream(**kwargs):
        raise RuntimeError("internal provider secret")
        yield

    capability_registry.reset()
    capability_registry.register(
        AssistantCapability(
            app_key="data_ops",
            display_name="Data Ops Assistant",
            required_feature="data_ops",
            instructions="Test.",
            tools=(),
            stream_handler=failing_stream,
        )
    )
    monkeypatch.setattr(
        "ai_assistant.services.get_effective_feature_keys",
        lambda user: ["data_ops"],
    )
    api_client.force_authenticate(user=data_ops_user)
    conversation = AssistantConversation.objects.create(
        user=data_ops_user,
        app_key="data_ops",
    )

    response = api_client.post(
        reverse(
            "assistant-conversation-message-list",
            kwargs={"conversation_uuid": conversation.uuid},
        ),
        {"message": "hello"},
        format="json",
    )
    body = b"".join(response.streaming_content).decode("utf-8")

    assert '"type": "error"' in body
    assert "internal provider secret" not in body
