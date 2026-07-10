from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Iterator

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from data_ops.llm_config import resolve_data_ops_llm_settings
from data_ops.models import (
    Contract,
    DomesticLedger,
    OverseaProject,
    OverseaSettlement,
    ProjectInit,
    SalesRecord,
)
from data_ops.services.ai_tools import (
    DATA_OPS_TOOL_SCHEMAS,
    execute_data_ops_tool,
    get_data_ops_tool_profile,
)
from data_ops.services.metrics.overview import _number


ZERO_DECIMAL = Decimal("0")

SYSTEM_PROMPT = """
你是数据运营控制台的经营数据助手。
你只能基于提供的业务上下文回答。
如果上下文不足，请明确说明需要先同步数据或补充维度。
不要编造不存在的客户、合同、金额或工具结果。
回答使用中文，简洁、可执行。
优先指出风险、机会和下一步动作。
你需要主动围绕合同、回款、海外销售、Pipeline、同步质量、
风险和机会给出运营洞察，而不是只复述指标。
当用户问题较宽泛时，先总结异常、变化和优先级，再给出建议追问。
回答前先判断最匹配的 Data Ops skill，并按该 skill 的输出形态组织答案。
当用户需要明细、排行、分组、趋势、计算或任意数据查询时，
优先使用 Data Ops tools 获取真实数据，不要只依赖上下文摘要。
明细查询使用 data_ops_query_records。
分组、排行、统计、Top 项和多指标计算使用
data_ops_aggregate。
只能使用工具 schema 中公开的表、字段、过滤、
聚合和排序能力。
使用 Markdown 输出。适合对比和排行的数据用 GFM Markdown 表格。
适合趋势、分布、Top 项的数据，可追加 dataops-chart 代码块：
```dataops-chart
{
  "type": "bar",
  "title": "标题",
  "labels": ["A", "B"],
  "series": [{"name": "指标", "data": [1, 2]}]
}
```
"""

DATA_OPS_AI_CAPABILITIES = [
    {
        "key": "executive_health",
        "title": "经营健康度",
        "description": (
            "综合合同金额、签约趋势、回款、待回款和客户分布，"
            "判断当前经营状态。"
        ),
    },
    {
        "key": "cash_collection",
        "title": "回款与应收风险",
        "description": (
            "分析收入台账、待回款、账期和合同到期，定位需要跟进的"
            "客户、负责人和项目。"
        ),
    },
    {
        "key": "oversea_sales",
        "title": "海外销售与 License",
        "description": (
            "分析海外订单、国家地区、产品类型、License 到期和成本利润。"
        ),
    },
    {
        "key": "pipeline_conversion",
        "title": "Pipeline 转化",
        "description": (
            "基于立项、国内/海外项目、预估金额和状态分布，识别高潜"
            "项目和转化阻塞。"
        ),
    },
    {
        "key": "sync_quality",
        "title": "数据同步质量",
        "description": (
            "结合飞书同步状态、字段缺失、权限异常和记录数波动，判断"
            "数据是否可信。"
        ),
    },
]

DATA_OPS_AI_SKILLS = [
    {
        "key": "business_health_scan",
        "title": "经营健康扫描",
        "objective": (
            "快速判断合同规模、签约结构、回款、海外项目和立项是否"
            "出现异常。"
        ),
        "data_sources": [
            "contracts",
            "domestic_ledgers",
            "sales_records",
            "oversea_projects",
            "project_inits",
        ],
        "example_questions": [
            "当前经营健康度怎么样？",
            "这周经营会我应该先讲哪些异常？",
            "合同、回款、海外项目之间有什么值得关注的变化？",
        ],
        "output_format": [
            "总体判断",
            "关键指标",
            "异常信号",
            "建议动作",
        ],
    },
    {
        "key": "cash_collection_risk",
        "title": "回款风险定位",
        "objective": (
            "从收入台账、待回款和合同状态中识别高金额、临近到期、"
            "负责人明确的回款风险。"
        ),
        "data_sources": [
            "contracts",
            "domestic_ledgers",
        ],
        "example_questions": [
            "待回款风险主要集中在哪里？",
            "哪些客户需要优先催收？",
            "请给我一个回款跟进优先级清单。",
        ],
        "output_format": [
            "风险分层",
            "客户/项目/负责人",
            "影响金额",
            "跟进建议",
        ],
    },
    {
        "key": "renewal_and_expiry_monitor",
        "title": "续约与到期监控",
        "objective": (
            "识别服务到期、License 到期和续约窗口，帮助提前安排客户"
            "沟通和交付动作。"
        ),
        "data_sources": [
            "contracts",
            "sales_records",
            "oversea_projects",
        ],
        "example_questions": [
            "未来 60 天有哪些续约风险？",
            "有哪些 License 快到期？",
            "哪些合同到期但还没有明确下一步？",
        ],
        "output_format": [
            "到期批次",
            "风险等级",
            "负责人",
            "建议触达时间",
        ],
    },
    {
        "key": "pipeline_conversion_diagnosis",
        "title": "Pipeline 转化诊断",
        "objective": (
            "分析立项、项目状态和预估金额，识别高潜项目、停滞项目和"
            "转化阻塞。"
        ),
        "data_sources": [
            "project_inits",
            "projects",
            "contracts",
        ],
        "example_questions": [
            "哪些立项最值得重点推进？",
            "Pipeline 转化卡在哪里？",
            "国内和海外 Pipeline 的机会有什么不同？",
        ],
        "output_format": [
            "机会分组",
            "转化阻塞",
            "优先级",
            "下一步动作",
        ],
    },
    {
        "key": "overseas_business_review",
        "title": "海外业务复盘",
        "objective": (
            "分析海外订单、国家地区、产品类型、成本、利润和结算状态，"
            "定位海外增长机会。"
        ),
        "data_sources": [
            "sales_records",
            "oversea_projects",
            "oversea_settlements",
        ],
        "example_questions": [
            "海外业务哪些国家表现最好？",
            "海外项目收入和成本有什么异常？",
            "哪些海外结算项目需要跟进？",
        ],
        "output_format": [
            "国家/产品表现",
            "利润异常",
            "结算风险",
            "销售建议",
        ],
    },
    {
        "key": "data_quality_guard",
        "title": "数据质量守卫",
        "objective": (
            "检查飞书同步、字段缺失、权限不足、分页不完整和记录数波动，"
            "先判断数据是否适合用于经营分析。"
        ),
        "data_sources": [
            "sync_table_status",
            "sync_jobs",
            "feishu_collection_configs",
        ],
        "example_questions": [
            "当前数据能不能支撑经营分析？",
            "哪些飞书表抓取不完整？",
            "本周经营会前需要先修复哪些数据？",
        ],
        "output_format": [
            "可信度判断",
            "问题表",
            "影响范围",
            "修复建议",
        ],
    },
]

DATA_OPS_AI_QUESTION_GROUPS = [
    {
        "key": "daily_review",
        "title": "每日经营复盘",
        "questions": [
            "今天我应该优先关注哪些经营风险？",
            "当前合同、回款和待回款的整体健康度怎么样？",
            "哪些客户或负责人需要优先跟进？",
        ],
    },
    {
        "key": "cash_risk",
        "title": "回款与风险",
        "questions": [
            "待回款风险主要集中在哪些客户、项目或负责人？",
            "哪些合同临近到期但回款或续约状态需要关注？",
            "请按影响金额给我排一个回款跟进优先级。",
        ],
    },
    {
        "key": "pipeline",
        "title": "Pipeline 洞察",
        "questions": [
            "国内和海外 Pipeline 的转化风险在哪里？",
            "哪些立项项目最值得销售重点推进？",
            "Pipeline 里有哪些高潜金额但状态停滞的项目？",
        ],
    },
    {
        "key": "oversea",
        "title": "海外业务",
        "questions": [
            "海外销售记录里哪些国家或产品类型表现最好？",
            "有哪些 License 即将到期，需要提前续约或交付跟进？",
            "海外项目的收入、成本和利润结构有什么异常？",
        ],
    },
    {
        "key": "data_quality",
        "title": "数据质量",
        "questions": [
            "当前飞书同步结果是否足以支撑经营分析？",
            "哪些数据表存在权限、字段缺失或抓取不完整风险？",
            "如果我要做本周经营会，哪些数据需要先修复？",
        ],
    },
]

DATA_OPS_ANALYSIS_GUIDE = [
    "先判断数据是否可信，再解读业务指标。",
    "优先识别金额大、临近到期、负责人明确的风险项。",
    "对机会项给出下一步动作，而不是只列出名称。",
    "涉及多币种时按币种分别说明，避免混算。",
]


def get_ai_context_metrics() -> dict[str, Any]:
    contract_amounts = _sum_by_currency(Contract.objects.all(), "total_amount")
    contract_by_platform = _count_by(Contract, "order_platform")
    contract_by_status = _count_by(Contract, "status")

    sales_amount = SalesRecord.objects.aggregate(
        value=Coalesce(Sum("total_amount_usd"), ZERO_DECIMAL),
    )["value"]

    income_rows = DomesticLedger.objects.filter(ledger_type="收入")
    expense_rows = DomesticLedger.objects.filter(ledger_type="支出")
    ledger_income_amounts = _sum_by_currency(income_rows, "payment_received")
    ledger_expense_amounts = _sum_by_currency(expense_rows, "payment_amount")
    outstanding_amounts = _sum_by_currency(income_rows, "outstanding")

    oversea_amount = OverseaProject.objects.aggregate(
        value=Coalesce(Sum("stat_amount_usd"), ZERO_DECIMAL),
    )["value"]
    oversea_cost = OverseaProject.objects.aggregate(
        value=Coalesce(Sum("cost_usd"), ZERO_DECIMAL),
    )["value"]
    settlement_receivable_amounts = _sum_by_currency(
        OverseaSettlement.objects.all(),
        "receivable_amount",
    )
    settlement_received_amounts = _sum_by_currency(
        OverseaSettlement.objects.all(),
        "received_amount",
    )

    return {
        "contract": {
            "contract_count": Contract.objects.count(),
            "total_amount": _single_currency_amount(contract_amounts),
            "total_amount_by_currency": contract_amounts,
            "by_platform": contract_by_platform,
            "by_status": contract_by_status,
        },
        "sales_record": {
            "record_count": SalesRecord.objects.count(),
            "total_amount_usd": _number(sales_amount),
        },
        "ledger": {
            "income": _single_currency_amount(ledger_income_amounts),
            "income_by_currency": ledger_income_amounts,
            "expense": _single_currency_amount(ledger_expense_amounts),
            "expense_by_currency": ledger_expense_amounts,
            "outstanding": _single_currency_amount(outstanding_amounts),
            "outstanding_by_currency": outstanding_amounts,
        },
        "oversea_project": {
            "project_count": OverseaProject.objects.count(),
            "total_stat_amount_usd": _number(oversea_amount),
            "total_cost_usd": _number(oversea_cost),
            "profit_usd": _number(oversea_amount) - _number(oversea_cost),
            "by_status": _count_by(OverseaProject, "status"),
        },
        "oversea_settlement": {
            "total_receivable": _single_currency_amount(
                settlement_receivable_amounts,
            ),
            "total_receivable_by_currency": settlement_receivable_amounts,
            "total_received": _single_currency_amount(
                settlement_received_amounts,
            ),
            "total_received_by_currency": settlement_received_amounts,
            "pending_by_currency": _subtract_currency_amounts(
                settlement_receivable_amounts,
                settlement_received_amounts,
            ),
        },
        "project_init": {
            "total_count": ProjectInit.objects.count(),
            "by_domestic_intl": _count_by(
                ProjectInit,
                "domestic_international",
            ),
        },
        "assistant": get_data_ops_ai_assistant_profile(),
        "updated_at": timezone.now().isoformat(),
    }


def get_data_ops_ai_assistant_profile() -> dict[str, Any]:
    return {
        "capabilities": DATA_OPS_AI_CAPABILITIES,
        "skills": DATA_OPS_AI_SKILLS,
        "question_groups": DATA_OPS_AI_QUESTION_GROUPS,
        "analysis_guide": DATA_OPS_ANALYSIS_GUIDE,
        "query_tools": get_data_ops_tool_profile(),
    }


def chat_with_data_ops_assistant(
    *,
    message: str,
    history: list[dict[str, str]] | None = None,
    preferred_config_uuid: str = "",
    user_id: int | None = None,
) -> dict[str, Any]:
    context = get_ai_context_metrics()
    messages = _build_messages(
        message=message,
        history=history or [],
        context=context,
    )
    content, usage, settings = _call_litellm(
        messages=messages,
        preferred_config_uuid=preferred_config_uuid,
        user_id=user_id,
    )
    return {
        "reply": content,
        "answer": content,
        "usage": usage,
        "llm": {
            "source": settings.get("source", ""),
            "label": settings.get("label", ""),
            "config_uuid": settings.get("config_uuid", ""),
        },
        "context": context,
    }


def stream_chat_with_data_ops_assistant(
    *,
    message: str,
    history: list[dict[str, str]] | None = None,
    preferred_config_uuid: str = "",
    user_id: int | None = None,
) -> Iterator[dict[str, Any]]:
    context = get_ai_context_metrics()
    messages = _build_messages(
        message=message,
        history=history or [],
        context=context,
    )
    try:
        (
            final_messages,
            precomputed_content,
            usage,
            settings,
        ) = _prepare_messages_with_data_ops_tools(
            messages=messages,
            preferred_config_uuid=preferred_config_uuid,
            user_id=user_id,
        )
        if precomputed_content:
            yield from _stream_precomputed_content(
                content=precomputed_content,
                usage=usage,
                settings=settings,
            )
            return
        yield from _stream_litellm(
            messages=final_messages,
            preferred_config_uuid=preferred_config_uuid,
            user_id=user_id,
        )
    except Exception as exc:
        yield {"type": "error", "detail": str(exc)}


def _count_by(model, field_name: str) -> dict[str, int]:
    rows = model.objects.values(field_name).annotate(count=Count("id"))
    return {
        str(item[field_name] or "未知"): int(item["count"] or 0)
        for item in rows
    }


def _sum_by_currency(queryset, amount_field: str) -> list[dict[str, float]]:
    rows = (
        queryset.values("currency")
        .annotate(value=Coalesce(Sum(amount_field), ZERO_DECIMAL))
        .order_by("currency")
    )
    return [
        {
            "currency": item["currency"] or "未知",
            "amount": _number(item["value"]),
        }
        for item in rows
    ]


def _single_currency_amount(items: list[dict[str, float]]) -> float | None:
    if len(items) != 1:
        return None
    return items[0]["amount"]


def _subtract_currency_amounts(
    left: list[dict[str, float]],
    right: list[dict[str, float]],
) -> list[dict[str, float]]:
    amounts = {item["currency"]: item["amount"] for item in left}
    for item in right:
        currency = item["currency"]
        amounts[currency] = amounts.get(currency, 0.0) - item["amount"]
    return [
        {"currency": currency, "amount": amount}
        for currency, amount in sorted(amounts.items())
    ]


def _build_messages(
    *,
    message: str,
    history: list[dict[str, str]],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    payload = json.dumps(context, ensure_ascii=False, default=str)
    profile = json.dumps(
        get_data_ops_ai_assistant_profile(),
        ensure_ascii=False,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {
            "role": "system",
            "content": f"Data Ops AI 能力边界与建议问题：\n{profile}",
        },
        {
            "role": "system",
            "content": f"当前业务上下文 JSON：\n{payload}",
        },
    ]
    for item in history[-8:]:
        role = item.get("role") if isinstance(item, dict) else ""
        content = item.get("content") if isinstance(item, dict) else ""
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": message})
    return messages


def _call_litellm(
    *,
    messages: list[dict[str, str]],
    preferred_config_uuid: str,
    user_id: int | None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    (
        final_messages,
        precomputed_content,
        usage,
        settings,
    ) = _prepare_messages_with_data_ops_tools(
        messages=messages,
        preferred_config_uuid=preferred_config_uuid,
        user_id=user_id,
    )
    if precomputed_content:
        return precomputed_content, usage, settings
    state = _build_litellm_state(user_id)
    message_payload, final_usage = _call_litellm_message(
        messages=final_messages,
        llm_settings=settings,
        state=state,
    )
    usage = _merge_usage(usage, final_usage)
    return str(message_payload.get("content") or ""), usage, settings


def _prepare_messages_with_data_ops_tools(
    *,
    messages: list[dict[str, str]],
    preferred_config_uuid: str,
    user_id: int | None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any], dict[str, Any]]:
    llm_settings = resolve_data_ops_llm_settings(preferred_config_uuid)
    state = _build_litellm_state(user_id)
    working_messages: list[dict[str, Any]] = list(messages)
    usage: dict[str, Any] = {}
    used_tools = False
    for _index in range(4):
        message_payload, step_usage = _call_litellm_message(
            messages=working_messages,
            llm_settings=llm_settings,
            state=state,
            tools=DATA_OPS_TOOL_SCHEMAS,
            tool_choice="auto",
        )
        usage = _merge_usage(usage, step_usage)
        tool_calls = _normalize_tool_calls(
            message_payload.get("tool_calls") or [],
        )
        if not tool_calls:
            if used_tools:
                break
            return (
                working_messages,
                str(message_payload.get("content") or ""),
                usage,
                llm_settings,
            )
        used_tools = True
        working_messages.append(
            _assistant_tool_call_message(message_payload, tool_calls),
        )
        working_messages.extend(_tool_result_messages(tool_calls))

    working_messages.append(
        {
            "role": "system",
            "content": (
                "Data Ops tools 已返回查询结果。请基于这些结果直接回答，"
                "不要继续调用工具。"
            ),
        },
    )
    return working_messages, "", usage, llm_settings


def _build_litellm_state(user_id: int | None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "node_name": "data_ops_ai_assistant",
        "source_type": "data_ops",
    }
    if user_id is not None:
        state["user_id"] = user_id
    return state


def _call_litellm_message(
    *,
    messages: list[dict[str, Any]],
    llm_settings: dict[str, Any],
    state: dict[str, Any],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from agentcore_metering.adapters.django.trackers.llm import LLMTracker

    config_uuid = str(llm_settings.get("config_uuid") or "").strip()
    if config_uuid:
        message_payload, usage = LLMTracker.call_and_track(
            messages=messages,
            max_tokens=1600,
            temperature=0.2,
            node_name="data_ops_ai_assistant",
            state=state,
            model_uuid=config_uuid,
            tools=tools,
            tool_choice=tool_choice,
            return_message=True,
        )
        return _normalize_message_payload(message_payload), usage

    params = _build_litellm_completion_params(llm_settings)
    params["messages"] = messages
    params["temperature"] = 0.2
    params["max_tokens"] = 1600
    if tools:
        params["tools"] = tools
    if tool_choice:
        params["tool_choice"] = tool_choice
    message_payload, usage = LLMTracker._call_and_track_non_stream_once(
        params=params,
        effective_state=state,
        node_name="data_ops_ai_assistant",
        state=state,
        model=str(params.get("model") or "unknown"),
        return_message=True,
    )
    return _normalize_message_payload(message_payload), usage


def _normalize_message_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"content": str(value or "")}


def _normalize_tool_calls(items: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(items):
        function = _chunk_get(item, "function") or {}
        name = _chunk_get(function, "name")
        arguments = _chunk_get(function, "arguments") or "{}"
        call_id = _chunk_get(item, "id") or f"data_ops_tool_{index}"
        if not name:
            continue
        normalized.append(
            {
                "id": str(call_id),
                "type": "function",
                "function": {
                    "name": str(name),
                    "arguments": str(arguments),
                },
            },
        )
    return normalized


def _assistant_tool_call_message(
    message_payload: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": str(message_payload.get("content") or ""),
        "tool_calls": tool_calls,
    }


def _tool_result_messages(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages = []
    for item in tool_calls:
        name = item["function"]["name"]
        arguments = _parse_tool_arguments(item["function"]["arguments"])
        result = execute_data_ops_tool(name, arguments)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": item["id"],
                "name": name,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                ),
            },
        )
    return messages


def _parse_tool_arguments(value: str) -> dict[str, Any]:
    try:
        arguments = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(arguments, dict):
        return arguments
    return {}


def _merge_usage(
    left: dict[str, Any],
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if key in {
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        }:
            merged[key] = int(merged.get(key) or 0) + int(value or 0)
        elif key not in merged:
            merged[key] = value
    return merged


def _stream_precomputed_content(
    *,
    content: str,
    usage: dict[str, Any],
    settings: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    for index in range(0, len(content), 80):
        yield {"type": "chunk", "content": content[index:index + 80]}
    yield {
        "type": "done",
        "ok": True,
        "reply": content,
        "usage": usage,
        "llm": {
            "source": settings.get("source", ""),
            "label": settings.get("label", ""),
            "config_uuid": settings.get("config_uuid", ""),
        },
    }


def _stream_litellm(
    *,
    messages: list[dict[str, str]],
    preferred_config_uuid: str,
    user_id: int | None,
) -> Iterator[dict[str, Any]]:
    from litellm import completion

    llm_settings = resolve_data_ops_llm_settings(preferred_config_uuid)
    params = _build_litellm_completion_params(llm_settings)
    params["messages"] = messages
    params["temperature"] = 0.2
    params["max_tokens"] = 1600
    params["stream"] = True

    if user_id is not None:
        params.setdefault("metadata", {})
        params["metadata"]["user_id"] = user_id
    params.setdefault("metadata", {})
    params["metadata"]["source_type"] = "data_ops"
    params["metadata"]["node_name"] = "data_ops_ai_assistant"

    full_content = []
    usage: dict[str, Any] = {}
    for chunk in completion(**params):
        content = _extract_litellm_chunk_content(chunk)
        if content:
            full_content.append(content)
            yield {"type": "chunk", "content": content}
        chunk_usage = _extract_litellm_chunk_usage(chunk)
        if chunk_usage:
            usage = chunk_usage

    yield {
        "type": "done",
        "ok": True,
        "reply": "".join(full_content),
        "usage": usage,
        "llm": {
            "source": llm_settings.get("source", ""),
            "label": llm_settings.get("label", ""),
            "config_uuid": llm_settings.get("config_uuid", ""),
        },
    }


def _build_litellm_completion_params(
    llm_settings: dict[str, Any],
) -> dict[str, Any]:
    from agentcore_metering.adapters.django.services import litellm_params

    provider = str(
        llm_settings.get("provider") or "openai_compatible"
    ).strip().lower()
    config = dict(llm_settings.get("config") or {})
    config.update(
        {
            "model": llm_settings.get("model") or config.get("model") or "",
            "api_key": llm_settings.get("api_key") or config.get("api_key"),
            "api_base": llm_settings.get("api_base") or config.get("api_base"),
        }
    )
    if provider == "azure_openai":
        config.setdefault(
            "deployment",
            config.get("deployment") or config.get("model"),
        )
        config.setdefault("api_version", config.get("api_version"))

    return litellm_params.build_litellm_params_from_config(provider, config)


def _extract_litellm_chunk_content(chunk: Any) -> str:
    choices = _chunk_get(chunk, "choices") or []
    if not choices:
        return ""
    choice = choices[0]
    delta = _chunk_get(choice, "delta") or {}
    content = _chunk_get(delta, "content")
    if content is None:
        content = _chunk_get(choice, "text")
    return str(content or "")


def _extract_litellm_chunk_usage(chunk: Any) -> dict[str, Any]:
    usage = _chunk_get(chunk, "usage") or {}
    if not usage:
        return {}
    if isinstance(usage, dict):
        return usage
    return {
        key: getattr(usage, key)
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )
        if getattr(usage, key, None) is not None
    }


def _chunk_get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
