"""Data Ops capability registered with the global assistant runtime."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from ai_assistant.contracts import (
    AssistantCapability,
    AssistantTool,
    MemoryPolicy,
)
from data_ops.services.ai import (
    SYSTEM_PROMPT,
    get_data_ops_ai_assistant_profile,
    stream_chat_with_data_ops_assistant,
)
from data_ops.services.ai_tools import (
    DATA_OPS_TOOL_SCHEMAS,
    execute_data_ops_tool,
)


SKILL_ROOT = Path(__file__).resolve().parent / "skills"


def _build_tools() -> tuple[AssistantTool, ...]:
    tools = []
    for item in DATA_OPS_TOOL_SCHEMAS:
        function = item["function"]
        name = function["name"]
        tools.append(
            AssistantTool(
                name=name,
                description=function.get("description", ""),
                schema=function.get("parameters", {}),
                handler=partial(execute_data_ops_tool, name),
            )
        )
    return tuple(tools)


def build_capability() -> AssistantCapability:
    """Build the immutable Data Ops assistant capability."""

    return AssistantCapability(
        app_key="data_ops",
        display_name="Data Ops 助手",
        required_feature="data_ops",
        description="分析合同、回款、Pipeline 和数据质量。",
        instructions=SYSTEM_PROMPT.strip(),
        tools=_build_tools(),
        skill_dirs=(SKILL_ROOT,),
        memory_policy=MemoryPolicy(
            enable_conversation_summary=True,
            enable_user_preferences=False,
            retention_days=90,
        ),
        profile_loader=get_data_ops_ai_assistant_profile,
        stream_handler=stream_chat_with_data_ops_assistant,
    )
