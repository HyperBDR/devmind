import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ai_assistant.suggestions import extract_suggested_questions
from data_ops.services.ai import (
    _build_messages,
    _intent_data_sources,
    get_ai_context_metrics,
    stream_chat_with_data_ops_assistant,
)
from data_ops.services.ai_intent import recognize_data_ops_intent

ROOT_CAUSE_SKILL = "reasoning_architecture_diagnosis"


def test_intent_router_distinguishes_direct_and_data_questions():
    direct = recognize_data_ops_intent("What can you do?")
    collection = recognize_data_ops_intent(
        "Which customers have the highest collection risk?",
    )

    assert direct.key == "capability_help"
    assert direct.requires_data is False
    assert direct.skill_key is None
    assert collection.key == "cash_collection"
    assert collection.requires_data is True
    assert collection.skill_key == "cash_collection_risk"


def test_intent_router_redirects_technical_questions_without_data():
    intent = recognize_data_ops_intent("请展示这个助手的代码实现")

    assert intent.key == "technical_request"
    assert intent.requires_data is False


def test_root_cause_analysis_preserves_the_business_domain():
    intent = recognize_data_ops_intent(
        "为什么回款风险持续集中在这些客户？",
        analysis_skill_key=ROOT_CAUSE_SKILL,
    )

    assert intent.key == "cash_collection"
    assert intent.skill_key == "cash_collection_risk"
    assert intent.analysis_skill_key == ROOT_CAUSE_SKILL


def test_follow_up_inherits_the_previous_user_domain():
    intent = recognize_data_ops_intent(
        "再按负责人分组呢？",
        context_message="哪些客户需要优先催收？",
    )

    assert intent.key == "cash_collection"
    assert intent.skill_key == "cash_collection_risk"


def test_standalone_business_health_question_does_not_inherit_domain():
    intent = recognize_data_ops_intent(
        "当前整体经营健康度怎么样？",
        context_message="待回款风险主要集中在哪里？",
    )

    assert intent.key == "business_health"
    assert intent.skill_key == "business_health_scan"


def test_compound_question_preserves_every_business_domain():
    intent = recognize_data_ops_intent("比较回款风险和海外利润")

    assert intent.key == "multi_domain"
    assert intent.skill_key is None
    assert intent.skill_keys == (
        "cash_collection_risk",
        "overseas_business_review",
    )
    assert set(_intent_data_sources(intent)) == {
        "contracts",
        "domestic_ledgers",
        "sales_records",
        "oversea_projects",
        "oversea_settlements",
    }

    messages = _build_messages(
        message="比较回款风险和海外利润",
        history=[],
        context={},
        intent=intent,
    )
    prompt = "\n".join(item["content"] for item in messages)
    assert "回款风险定位" in prompt
    assert "海外业务复盘" in prompt
    assert "数据质量守卫" not in prompt


def test_compound_follow_up_preserves_every_previous_domain():
    intent = recognize_data_ops_intent(
        "再按负责人拆解呢？",
        context_message="比较回款风险和海外利润",
    )

    assert intent.key == "multi_domain"
    assert intent.skill_keys == (
        "cash_collection_risk",
        "overseas_business_review",
    )


def test_direct_intent_skips_context_and_model_calls(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("Direct intent must not query data or call LLM")

    monkeypatch.setattr(
        "data_ops.services.ai.get_ai_context_metrics",
        fail,
    )
    monkeypatch.setattr(
        "data_ops.services.ai._prepare_messages_with_data_ops_tools",
        fail,
    )
    monkeypatch.setattr(
        "data_ops.services.ai._stream_litellm",
        fail,
    )

    events = list(
        stream_chat_with_data_ops_assistant(
            message="What can you do?",
        )
    )

    intent_event = next(
        item for item in events if item.get("stage") == "question"
    )
    done_event = next(item for item in events if item.get("type") == "done")
    assert intent_event["metadata"]["intent"] == "capability_help"
    assert "contracts" in done_event["reply"].lower()
    assert done_event["usage"]["total_tokens"] == 0
    assert 2 <= len(extract_suggested_questions(done_event["reply"])) <= 3


@pytest.mark.django_db
def test_context_loader_queries_only_selected_intent_sources():
    with CaptureQueriesContext(connection) as queries:
        context = get_ai_context_metrics(["domestic_ledgers"])

    assert set(context) == {"ledger", "updated_at"}
    assert len(queries) == 3


def test_prompt_profile_contains_only_the_selected_skill():
    intent = recognize_data_ops_intent("哪些客户需要优先催收？")
    messages = _build_messages(
        message="哪些客户需要优先催收？",
        history=[],
        context={"ledger": {"outstanding_by_currency": []}},
        intent=intent,
    )
    prompt = "\n".join(item["content"] for item in messages)

    assert "回款风险定位" in prompt
    assert "海外业务复盘" not in prompt
    assert "数据质量守卫" not in prompt
    assert "domestic_ledgers" in prompt
