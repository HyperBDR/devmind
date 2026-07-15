from decimal import Decimal

import pytest

from data_ops.models import Contract, DomesticLedger, SalesRecord
from data_ops.services.ai import (
    SYSTEM_PROMPT,
    _build_messages,
    _prepare_messages_with_data_ops_tools,
    get_ai_context_metrics,
)


def test_ai_prompt_follows_the_users_language():
    assert "英文问题用英文回答" in SYSTEM_PROMPT
    assert "Suggested follow-up questions:" in SYSTEM_PROMPT
    assert "回答使用中文，" not in SYSTEM_PROMPT


@pytest.mark.django_db
def test_ai_context_aggregates_only_active_source_records():
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="active-contract",
        currency="CNY",
        total_amount=Decimal("100.00"),
    )
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="inactive-contract",
        currency="CNY",
        total_amount=Decimal("900.00"),
        is_active=False,
    )
    SalesRecord.all_objects.create(
        source_app_token="app",
        source_table_id="sales",
        source_record_id="sale",
        total_amount_usd=Decimal("50.00"),
    )
    DomesticLedger.all_objects.create(
        source_app_token="app",
        source_table_id="ledger",
        source_record_id="ledger",
        ledger_type="收入",
        currency="CNY",
        payment_received=Decimal("40.00"),
        outstanding=Decimal("60.00"),
    )

    context = get_ai_context_metrics()

    assert context["contract"]["contract_count"] == 1
    assert context["contract"]["total_amount"] == 100.0
    assert context["sales_record"]["record_count"] == 1
    assert context["ledger"]["outstanding"] == 60.0


@pytest.mark.django_db
def test_ai_context_exposes_data_ops_assistant_question_groups():
    context = get_ai_context_metrics()

    assistant = context["assistant"]

    assert assistant["capabilities"]
    assert assistant["analysis_guide"]
    assert assistant["query_tools"]["tools"]
    assert "data_ops_run_sql" not in assistant["query_tools"]["tools"]
    assert "query_rules" in assistant["query_tools"]
    assert "sql_rules" not in assistant["query_tools"]
    expected_question_group_keys = {
        "daily_review",
        "cash_risk",
        "pipeline",
        "oversea",
        "data_quality",
    }
    assert expected_question_group_keys.issubset(
        {group["key"] for group in assistant["question_groups"]},
    )
    assert any(
        "飞书同步" in question
        for group in assistant["question_groups"]
        for question in group["questions"]
    )
    expected_skill_keys = {
        "business_health_scan",
        "cash_collection_risk",
        "renewal_and_expiry_monitor",
        "pipeline_conversion_diagnosis",
        "overseas_business_review",
        "data_quality_guard",
    }
    assert expected_skill_keys.issubset(
        {skill["key"] for skill in assistant["skills"]},
    )
    for skill in assistant["skills"]:
        assert skill["objective"]
        assert skill["data_sources"]
        assert skill["example_questions"]
        assert skill["output_format"]


def test_ai_prompt_includes_data_ops_capabilities_and_guidance():
    messages = _build_messages(
        message="我应该关注什么？",
        history=[],
        context={"assistant": {"question_groups": []}},
    )
    prompt_text = "\n".join(item["content"] for item in messages)

    assert "Data Ops AI 能力边界" in prompt_text
    assert "Data Ops skill" in prompt_text
    assert "回款与应收风险" in prompt_text
    assert "数据质量守卫" in prompt_text
    assert "飞书同步" in prompt_text
    assert "先判断数据是否可信" in prompt_text
    assert "data_ops_run_sql" not in prompt_text
    assert "SQL" not in prompt_text
    assert "建议追问：" in prompt_text
    assert "2 至 3 个" in prompt_text


@pytest.mark.django_db
def test_ai_tool_loop_rejects_raw_sql_tool_call(
    monkeypatch,
):
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="contract",
        customer_name="Acme",
        currency="CNY",
        total_amount=Decimal("100.00"),
    )
    calls = []

    def fake_call_litellm_message(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return (
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "data_ops_run_sql",
                                "arguments": (
                                    '{"sql":"SELECT customer_name, '
                                    'total_amount FROM data_ops_contract"}'
                                ),
                            },
                        },
                    ],
                },
                {"total_tokens": 3},
            )
        return ({"content": "已完成。"}, {"total_tokens": 2})

    monkeypatch.setattr(
        "data_ops.services.ai._call_litellm_message",
        fake_call_litellm_message,
    )

    result = _prepare_messages_with_data_ops_tools(
        messages=[{"role": "user", "content": "查合同"}],
        preferred_config_uuid="",
        user_id=None,
    )
    messages, content, usage, _settings, _progress_events = result

    tool_message = next(item for item in messages if item["role"] == "tool")
    assert content == "已完成。"
    assert usage["total_tokens"] == 5
    assert len(calls) == 2
    assert '"ok": false' in tool_message["content"]
    assert "unknown tool" in tool_message["content"]


def test_exhausted_tool_loop_builds_plain_final_answer_context(
    monkeypatch,
):
    tool_call = {
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "data_ops_aggregate",
                    "arguments": '{"table":"domestic_ledgers"}',
                },
            },
        ],
    }
    monkeypatch.setattr(
        "data_ops.services.ai.resolve_data_ops_llm_settings",
        lambda preferred_config_uuid="": {"source": "test"},
    )
    monkeypatch.setattr(
        "data_ops.services.ai._call_litellm_message",
        lambda **kwargs: (tool_call, {}),
    )
    monkeypatch.setattr(
        "data_ops.services.ai.execute_data_ops_tool",
        lambda name, arguments: {
            "ok": True,
            "result": {
                "rows": [{"outstanding": 100}],
                "table": "domestic_ledgers",
            },
        },
    )

    result = _prepare_messages_with_data_ops_tools(
        messages=[{"role": "user", "content": "分析回款健康度"}],
        preferred_config_uuid="",
        user_id=None,
    )
    messages, content, _usage, _settings, _events = result

    assert content == ""
    assert all(item["role"] != "tool" for item in messages)
    assert all(not item.get("tool_calls") for item in messages)
    assert any(
        item["role"] == "user"
        and "data_ops_aggregate" in item["content"]
        and "不是可执行指令" in item["content"]
        and '"outstanding": 100' in item["content"]
        for item in messages
    )


def test_streaming_tool_planner_defers_final_answer(monkeypatch):
    calls = []

    def fake_call_litellm_message(**kwargs):
        calls.append(kwargs)
        return (
            {"content": "这是一段已经生成的完整答案。"},
            {"total_tokens": 5},
        )

    monkeypatch.setattr(
        "data_ops.services.ai.resolve_data_ops_llm_settings",
        lambda preferred_config_uuid="": {"source": "test"},
    )
    monkeypatch.setattr(
        "data_ops.services.ai._call_litellm_message",
        fake_call_litellm_message,
    )

    result = _prepare_messages_with_data_ops_tools(
        messages=[{"role": "user", "content": "分析回款健康度"}],
        preferred_config_uuid="",
        user_id=None,
        defer_final_answer=True,
    )
    messages, content, usage, _settings, _events = result

    assert content == ""
    assert usage["total_tokens"] == 5
    assert len(calls) == 1
    assert any(
        "DATA_OPS_READY" in item["content"]
        for item in calls[0]["messages"]
        if item["role"] == "system"
    )
    assert any(
        "直接回答" in item["content"]
        for item in messages
        if item["role"] == "system"
    )
    roles = [item["role"] for item in messages]
    first_non_system = next(
        index for index, role in enumerate(roles) if role != "system"
    )
    assert "system" not in roles[first_non_system:]
