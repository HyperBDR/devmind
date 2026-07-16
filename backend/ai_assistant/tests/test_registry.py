from pathlib import Path

import pytest

from ai_assistant.contracts import AssistantCapability, AssistantTool
from ai_assistant.registry import CapabilityRegistry


def _capability(app_key: str = "data_ops") -> AssistantCapability:
    return AssistantCapability(
        app_key=app_key,
        display_name="Data Ops Assistant",
        required_feature="data_ops",
        instructions="Use Data Ops tools only.",
        tools=(
            AssistantTool(
                name="data_ops_query_records",
                description="Query Data Ops records.",
                schema={},
                handler=lambda context, arguments: arguments,
            ),
        ),
        skill_dirs=(Path("/tmp/data-ops-skills"),),
    )


def test_registry_resolves_registered_capability():
    registry = CapabilityRegistry()

    registry.register(_capability())

    assert registry.require("data_ops").display_name == "Data Ops Assistant"


def test_registry_rejects_duplicate_app_key():
    registry = CapabilityRegistry()
    registry.register(_capability())

    with pytest.raises(ValueError, match="Duplicate assistant capability"):
        registry.register(_capability())


def test_registry_rejects_duplicate_tool_names():
    registry = CapabilityRegistry()
    duplicate_tool = AssistantTool(
        name="data_ops_query_records",
        description="Duplicate tool.",
        schema={},
        handler=lambda context, arguments: arguments,
    )
    capability = _capability()
    capability = AssistantCapability(
        app_key=capability.app_key,
        display_name=capability.display_name,
        required_feature=capability.required_feature,
        instructions=capability.instructions,
        tools=(*capability.tools, duplicate_tool),
    )

    with pytest.raises(ValueError, match="Duplicate assistant tool"):
        registry.register(capability)
