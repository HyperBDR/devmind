"""Data Ops capability registered with the global assistant runtime."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from ai_assistant.contracts import (
    AssistantTool,
    MemoryPolicy,
)
from ai_assistant.provider import AssistantCapabilityProvider
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


def _execute_tool(name, _context, arguments):
    return execute_data_ops_tool(name, arguments)


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
                handler=partial(_execute_tool, name),
            )
        )
    return tuple(tools)


class DataOpsAssistantProvider(AssistantCapabilityProvider):
    """Declare the Data Ops assistant through the shared template."""

    app_key = "data_ops"
    display_name = "Data Ops 助手"
    required_feature = "data_ops"
    description = "分析合同、回款、Pipeline 和数据质量。"

    def get_instructions(self):
        return SYSTEM_PROMPT

    def get_tools(self):
        return _build_tools()

    def get_skill_dirs(self):
        return (SKILL_ROOT,)

    def get_memory_policy(self):
        return MemoryPolicy(
            enable_conversation_summary=True,
            enable_user_preferences=False,
            retention_days=90,
        )

    def get_profile_loader(self):
        return get_data_ops_ai_assistant_profile

    def get_stream_handler(self):
        return stream_chat_with_data_ops_assistant


def build_capability():
    """Build the Data Ops capability for compatibility callers."""

    return DataOpsAssistantProvider().build_capability()
