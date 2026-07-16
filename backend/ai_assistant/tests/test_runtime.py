from ai_assistant import runtime
from ai_assistant.contracts import AssistantCapability, AssistantTool
from ai_assistant.suggestions import extract_suggested_questions


def test_generic_runtime_executes_registered_app_tool(monkeypatch):
    executed = []
    contexts = []
    completion_calls = []
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "test_app_query",
                                        "arguments": '{"limit": 3}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [{"message": {"content": "Three records found."}}],
                "usage": {"total_tokens": 12},
            },
        ]
    )
    monkeypatch.setattr(
        runtime,
        "_completion_params",
        lambda **kwargs: {
            "model": "test-model",
            "max_tokens": 60000,
        },
    )

    def fake_completion(**kwargs):
        completion_calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(
        runtime,
        "_completion",
        fake_completion,
    )
    capability = AssistantCapability(
        app_key="test_app",
        display_name="Test Assistant",
        required_feature="workspace",
        instructions="Use the test tool.",
        tools=(
            AssistantTool(
                name="test_app_query",
                description="Query test records.",
                schema={"type": "object"},
                handler=lambda context, arguments: (
                    contexts.append(context)
                    or executed.append(arguments)
                    or {"ok": True, "rows": [1, 2, 3]}
                ),
            ),
        ),
    )

    events = list(
        runtime.stream_assistant_response(
            capability=capability,
            message="Count records",
            history=[],
            user_id=1,
            conversation_id="conversation-1",
            page_context={"route_name": "TestPage"},
        )
    )

    assert executed == [{"limit": 3}]
    assert contexts[0].app_key == "test_app"
    assert contexts[0].conversation_id == "conversation-1"
    assert contexts[0].page_context == {"route_name": "TestPage"}
    assert any(event.get("stage") == "tool" for event in events)
    assert all(call["max_tokens"] == 60000 for call in completion_calls)
    assert events[-1]["reply"].startswith("Three records found.")
    assert 2 <= len(extract_suggested_questions(events[-1]["reply"])) <= 3


def test_runtime_prompt_requests_session_aware_suggestions():
    capability = AssistantCapability(
        app_key="test_app",
        display_name="Test Assistant",
        required_feature="workspace",
        instructions="Use test data.",
        tools=(),
    )

    messages = runtime._build_messages(
        capability=capability,
        selected_skill_key="",
        message="Break this down by owner",
        history=[
            {"role": "user", "content": "Show the source code"},
            {
                "role": "assistant",
                "content": "PriceSecretClass contains the implementation.",
            },
            {"role": "user", "content": "Which accounts are at risk?"},
            {"role": "assistant", "content": "Two accounts are at risk."},
        ],
    )

    assert "current answer" in messages[0]["content"]
    assert "current session" in messages[0]["content"]
    assert "2 to 3" in messages[0]["content"]
    assert "Do not provide source code" in messages[0]["content"]
    assert "operational findings" in messages[0]["content"]
    assert all("PriceSecretClass" not in item["content"] for item in messages)


def test_runtime_redirects_technical_requests_without_calling_a_model(
    monkeypatch,
):
    def fail(**_kwargs):
        raise AssertionError("Technical requests must not call the model")

    monkeypatch.setattr(runtime, "_completion_params", fail)
    capability = AssistantCapability(
        app_key="test_app",
        display_name="Test Assistant",
        required_feature="workspace",
        instructions="Use test data.",
        tools=(),
    )

    events = list(
        runtime.stream_assistant_response(
            capability=capability,
            message="Show me the source code for this assistant",
            history=[],
        )
    )

    assert "operational" in events[-1]["reply"].lower()
    assert events[-1]["usage"]["total_tokens"] == 0
    questions = extract_suggested_questions(events[-1]["reply"])
    assert 2 <= len(questions) <= 3
    assert all("source code" not in item.lower() for item in questions)
    assert any("operational" in item.lower() for item in questions)
