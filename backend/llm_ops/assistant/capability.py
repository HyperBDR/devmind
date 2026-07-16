"""LLM Ops capability registered with the global assistant runtime."""

from functools import partial

from ai_assistant.contracts import (
    AssistantTool,
    MemoryPolicy,
)
from ai_assistant.provider import AssistantCapabilityProvider
from llm_ops.assistant_tools import (
    LLM_OPS_TOOL_SCHEMAS,
    execute_llm_ops_tool,
    get_llm_ops_assistant_profile,
)

INSTRUCTIONS = """
你是大模型运营助手。
回答必须先区分运营模型和市场参考模型：
- operational 表示已有渠道配置或当前平台挂售意图，
  可以进入运营待办。
- market_reference 只用于市场价格比较，
  不得描述为缺渠道、待挂售或低收益。

查询运营待办时使用 llm_ops_query_decisions；查询市场价时使用
llm_ops_query_market_prices；
价格变化和采集健康分别使用对应工具。
需要用户配置渠道、调价或挂售时，调用
llm_ops_get_operation_entry，在回答中给出其返回的控制台链接。
控制台链接必须原样使用工具返回的相对路径，
不得补充协议、域名或当前页面 origin。
工具只提供查询和操作入口，
不能声称已经修改价格、渠道、
平台配置或挂售状态。回答要注明数据范围和更新时间。

每次回答末尾必须推荐 2 至 3 个下一轮问题。
推荐必须根据本轮用户问题和回答中的结论、数据范围及异常生成，
不得从预设问题目录照搬，也不得重复用户已经问过的问题。
推荐问题应当能够独立提问，并帮助用户继续下钻当前分析。
中文回答使用“建议追问：”，英文回答使用
“Suggested follow-up questions:”，每个问题单独列出。
建议追问之后不要再输出其他内容。
"""


def _execute_tool(name, _context, arguments):
    return execute_llm_ops_tool(name, arguments)


def _build_tools() -> tuple[AssistantTool, ...]:
    tools = []
    for item in LLM_OPS_TOOL_SCHEMAS:
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


class LLMOpsAssistantProvider(AssistantCapabilityProvider):
    """Declare the LLM Ops assistant through the shared template."""

    app_key = "llm_ops"
    display_name = "大模型运营助手"
    required_feature = "llm_ops"
    description = "查询运营待办、市场价格、挂售收益和采集异常。"

    def get_instructions(self):
        return INSTRUCTIONS

    def get_tools(self):
        return _build_tools()

    def get_memory_policy(self):
        return MemoryPolicy(
            enable_conversation_summary=True,
            enable_user_preferences=False,
            retention_days=90,
        )

    def get_profile_loader(self):
        return get_llm_ops_assistant_profile


def build_capability():
    """Build the LLM Ops capability for compatibility callers."""

    return LLMOpsAssistantProvider().build_capability()
