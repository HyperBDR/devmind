from decimal import Decimal

import pytest

from data_ops.models import Contract, DomesticLedger, SalesRecord
from data_ops.services.ai import (
    REASONING_ARCHITECTURE_SKILL_KEY,
    SYSTEM_PROMPT,
    _build_final_answer_messages,
    _build_messages,
    _configured_max_tokens,
    _prepare_messages_with_data_ops_tools,
    _recognize_intent,
    _select_analysis_skill,
    get_data_ops_ai_assistant_profile,
    get_ai_context_metrics,
    stream_chat_with_data_ops_assistant,
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
        "reasoning_architecture_diagnosis",
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
    assert "图表不是默认输出" in prompt_text
    assert "只有图表能比文字或表格更清楚" in prompt_text
    assert '"type": "bar | line | pie | doughnut"' in prompt_text
    assert "不同币种未统一换算" in prompt_text
    assert "最多 1 至 2 张" in prompt_text
    assert "放在建议追问之前" in prompt_text
    assert "Do not provide source code" in prompt_text
    assert "operational findings" in prompt_text


def test_ai_messages_exclude_duplicate_ui_only_assistant_context():
    messages = _build_messages(
        message="分析 Pipeline 风险",
        history=[],
        context={
            "assistant": get_data_ops_ai_assistant_profile(),
            "contract": {"contract_count": 2},
        },
    )
    prompt_text = "\n".join(item["content"] for item in messages)

    assert prompt_text.count('"capabilities"') == 1
    assert '"question_groups"' not in prompt_text
    assert '"query_tools"' not in prompt_text
    assert '"contract_count": 2' in prompt_text


def test_answer_limit_uses_the_selected_model_configuration():
    assert _configured_max_tokens({"config": {"max_tokens": 60000}}) == 60000
    assert _configured_max_tokens({"config": {}}) == 1600


def test_analysis_skill_router_only_selects_complex_diagnosis():
    assert (
        _select_analysis_skill("为什么回款风险持续集中在这些客户？")
        == REASONING_ARCHITECTURE_SKILL_KEY
    )
    assert (
        _select_analysis_skill("从经营架构看 Pipeline 卡在哪里？")
        == REASONING_ARCHITECTURE_SKILL_KEY
    )
    assert _select_analysis_skill("列出未来 30 天到期合同") is None


def test_conversation_router_uses_only_the_latest_user_question():
    intent = _recognize_intent(
        "再按负责人分组呢？",
        history=[
            {"role": "user", "content": "哪些客户需要优先催收？"},
            {"role": "assistant", "content": "这里是回款分析结果。"},
        ],
    )

    assert intent.key == "cash_collection"
    assert intent.skill_key == "cash_collection_risk"


def test_conversation_router_drops_root_cause_mode_on_topic_switch():
    intent = _recognize_intent(
        "未来 60 天有哪些 License 到期？",
        history=[
            {
                "role": "user",
                "content": "为什么回款风险持续集中在这些客户？",
            },
        ],
    )

    assert intent.key == "renewal_expiry"
    assert intent.analysis_skill_key is None


def test_final_answer_injects_selected_reasoning_framework():
    messages = _build_final_answer_messages(
        [{"role": "user", "content": "为什么回款持续下降？"}],
        analysis_skill_key=REASONING_ARCHITECTURE_SKILL_KEY,
    )
    system_text = "\n".join(
        item["content"] for item in messages if item["role"] == "system"
    )

    assert "经营根因诊断" in system_text
    assert "根因假设" in system_text
    assert "证据不足" in system_text
    assert "不要输出内部思维链" in system_text

    plain_messages = _build_final_answer_messages(
        [{"role": "user", "content": "列出未来 30 天到期合同"}],
    )
    plain_system_text = "\n".join(
        item["content"] for item in plain_messages if item["role"] == "system"
    )
    assert "经营根因诊断" not in plain_system_text


@pytest.mark.django_db
def test_ai_tool_loop_rejects_raw_sql_tool_call(
    monkeypatch,
):
    Contract.all_objects.create(
        source_app_token="app",
        source_table_id="table",
        source_record_id="contract",
        customer_name="Example Customer",
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
        analysis_skill_key=REASONING_ARCHITECTURE_SKILL_KEY,
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
    assert any(
        "经营根因诊断" in item["content"]
        for item in messages
        if item["role"] == "system"
    )
    roles = [item["role"] for item in messages]
    first_non_system = next(
        index for index, role in enumerate(roles) if role != "system"
    )
    assert "system" not in roles[first_non_system:]


def test_stream_chat_exposes_selected_reasoning_skill(monkeypatch):
    captured = {}

    def fake_context(data_sources=None):
        captured["data_sources"] = data_sources
        return {
            "contract": {"contract_count": 2},
            "ledger": {"outstanding_by_currency": []},
            "oversea_project": {"project_count": 0},
        }

    monkeypatch.setattr(
        "data_ops.services.ai.get_ai_context_metrics",
        fake_context,
    )

    def fake_prepare_messages(**kwargs):
        captured.update(kwargs)
        return (
            [{"role": "user", "content": "分析"}],
            "",
            {},
            {"source": "test"},
            [],
        )

    monkeypatch.setattr(
        "data_ops.services.ai._prepare_messages_with_data_ops_tools",
        fake_prepare_messages,
    )
    monkeypatch.setattr(
        "data_ops.services.ai._stream_litellm",
        lambda **kwargs: iter([{"type": "done", "ok": True}]),
    )

    events = list(
        stream_chat_with_data_ops_assistant(
            message="为什么回款风险持续集中在这些客户？",
        )
    )

    reasoning_event = next(
        item for item in events if item.get("stage") == "reasoning"
    )
    assert reasoning_event["metadata"]["skill"] == (
        REASONING_ARCHITECTURE_SKILL_KEY
    )
    assert captured["analysis_skill_key"] == (REASONING_ARCHITECTURE_SKILL_KEY)
    assert captured["data_sources"] == (
        "contracts",
        "domestic_ledgers",
    )
