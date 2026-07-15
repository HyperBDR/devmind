from ai_assistant import runtime
from ai_assistant.contracts import AssistantCapability, AssistantTool


def test_generic_runtime_executes_registered_app_tool(monkeypatch):
    executed = []
    contexts = []
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
                "choices": [
                    {"message": {"content": "Three records found."}}
                ],
                "usage": {"total_tokens": 12},
            },
        ]
    )
    monkeypatch.setattr(
        runtime,
        "_completion_params",
        lambda **kwargs: {"model": "test-model"},
    )
    monkeypatch.setattr(
        runtime,
        "_completion",
        lambda **kwargs: next(responses),
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
                    or
                    executed.append(arguments)
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
    assert events[-1]["reply"] == "Three records found."
