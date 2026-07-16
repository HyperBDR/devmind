from ai_assistant.suggestions import (
    ensure_contextual_suggestions,
    extract_suggested_questions,
)


def test_fallback_suggestions_use_current_and_session_context():
    content = "回款风险主要集中在三个大客户。"
    history = [
        {"role": "user", "content": "哪些客户回款风险最高？"},
        {"role": "assistant", "content": "需要先按客户汇总。"},
    ]

    result = ensure_contextual_suggestions(
        content,
        message="再按负责人拆解一下",
        history=history,
    )
    questions = extract_suggested_questions(result)

    assert result.startswith(content)
    assert 2 <= len(questions) <= 3
    assert any("哪些客户回款风险最高" in item for item in questions)
    assert any("需要先按客户汇总" in item for item in questions)


def test_suggestions_remove_asked_questions_and_limit_to_three():
    result = ensure_contextual_suggestions(
        "当前有两项高优先级风险。\n\n"
        "建议追问：\n"
        "- 当前有哪些高优先级风险？\n"
        "- 哪位负责人需要先跟进？\n"
        "- 涉及的合同金额是多少？\n"
        "- 哪些数据需要补充？",
        message="当前有哪些高优先级风险？",
        history=[],
    )
    questions = extract_suggested_questions(result)

    assert len(questions) == 3
    assert "当前有哪些高优先级风险？" not in questions


def test_english_suggestions_use_the_english_marker():
    result = ensure_contextual_suggestions(
        "Collection risk is concentrated in two accounts.",
        message="Show the collection risk",
        history=[],
    )

    assert "Suggested follow-up questions:" in result
    assert 2 <= len(extract_suggested_questions(result)) <= 3


def test_low_context_message_reuses_the_session_topic():
    result = ensure_contextual_suggestions(
        "不客气。",
        message="谢谢",
        history=[
            {"role": "user", "content": "哪些客户回款风险最高？"},
            {"role": "assistant", "content": "风险集中在三个客户。"},
        ],
    )
    questions = extract_suggested_questions(result)

    assert any("哪些客户回款风险最高" in item for item in questions)
    assert all("“谢谢”" not in item for item in questions)
