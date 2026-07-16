"""Shared session-aware follow-up suggestion policy."""

from __future__ import annotations

import re
from typing import Any

FOLLOW_UP_SYSTEM_INSTRUCTION = """
After composing the current answer, append 2 to 3 suggested follow-up
questions. Generate them from the current user request, factual conclusions
in the current answer, and relevant turns in the current session. At least
one question should deepen the current conclusion or lead to a concrete next
query or action. Do not copy startup prompt examples or repeat a question the
user already asked. Use the answer language. For Chinese, use the heading
“建议追问：”; for English, use “Suggested follow-up questions:”. Put each
question on its own bullet line and output nothing after the suggestions.
""".strip()

_MARKER_PATTERN = re.compile(
    r"(?:建议追问|Suggested follow-up questions?|Follow-up questions?)"
    r"[：:]\s*",
    re.IGNORECASE,
)
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
_LOW_CONTEXT_PATTERN = re.compile(
    r"^(?:你好|您好|嗨|谢谢|感谢|多谢|hi|hello|hey|thanks|thank you)"
    r"[！!。.?？\s]*$",
    re.IGNORECASE,
)


def extract_suggested_questions(content: str) -> list[str]:
    """Extract up to three follow-up questions from one answer."""

    _body, questions = _split_answer(content)
    return questions[:3]


def ensure_contextual_suggestions(
    content: str,
    *,
    message: str,
    history: list[dict[str, Any]] | None,
) -> str:
    """Normalize one answer to two or three session-aware suggestions."""

    answer = str(content or "").strip()
    if not answer:
        return answer
    body, generated = _split_answer(answer)
    asked = {
        _comparison_key(value)
        for value in _user_messages(history) + [str(message or "")]
        if value
    }
    questions = []
    for question in generated:
        if _comparison_key(question) in asked:
            continue
        _append_unique(questions, question)
    is_chinese = bool(_CJK_PATTERN.search(str(message or "") or answer))
    for question in _fallback_questions(
        message=message,
        history=history,
        is_chinese=is_chinese,
    ):
        if len(questions) >= 3:
            break
        if _comparison_key(question) not in asked:
            _append_unique(questions, question)
    questions = questions[:3]
    marker = "建议追问：" if is_chinese else "Suggested follow-up questions:"
    suggestion_block = "\n".join(f"- {item}" for item in questions)
    return f"{body}\n\n{marker}\n{suggestion_block}".strip()


def _split_answer(content: str) -> tuple[str, list[str]]:
    text = str(content or "").strip()
    marker = _MARKER_PATTERN.search(text)
    if marker is None:
        return text, []
    body = text[: marker.start()].strip()
    tail = text[slice(marker.end(), None)]
    questions = []
    for line in tail.splitlines():
        question = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", "", line)
        question = re.sub(r"[`*_]", "", question).strip()
        if len(question) >= 4:
            _append_unique(questions, question)
    return body, questions


def _fallback_questions(
    *,
    message: str,
    history: list[dict[str, Any]] | None,
    is_chinese: bool,
) -> list[str]:
    previous_messages = _user_messages(history)
    topic_message = str(message or "")
    inherited_topic = False
    if previous_messages and _LOW_CONTEXT_PATTERN.fullmatch(
        topic_message.strip()
    ):
        topic_message = previous_messages[-1]
        inherited_topic = True
    topic = _short_topic(
        topic_message,
        "本轮问题" if is_chinese else "this topic",
    )
    previous = (
        _short_topic(previous_messages[-1], "") if previous_messages else ""
    )
    previous_answers = _assistant_messages(history)
    previous_answer = (
        _short_topic(_split_answer(previous_answers[-1])[0], "")
        if previous_answers
        else ""
    )
    if is_chinese:
        questions = [
            f"基于本轮对“{topic}”的回答，下一步最应优先处理什么？",
            "为了验证本轮结论，还需要补充哪些数据或筛选条件？",
            "可以按影响范围和紧急程度继续拆解本轮结果吗？",
        ]
        if previous and not inherited_topic:
            questions[1] = (
                f"结合本轮结论和之前的“{previous}”，"
                "哪些变化最值得继续验证？"
            )
        if previous_answer:
            questions[2] = (
                f"本轮结论与本会话此前的“{previous_answer}”相比，"
                "哪些变化需要重点关注？"
            )
        return questions
    questions = [
        f"Based on the answer about “{topic}”, "
        "what should be prioritized next?",
        "What additional data or filters would validate this conclusion?",
        "Can you break down the result by impact and urgency?",
    ]
    if previous and not inherited_topic:
        questions[1] = (
            f"Compared with the earlier question “{previous}”, "
            "which changes should be validated next?"
        )
    if previous_answer:
        questions[2] = (
            "Compared with the earlier session conclusion "
            f"“{previous_answer}”, "
            "which changes need attention?"
        )
    return questions


def _user_messages(history: list[dict[str, Any]] | None) -> list[str]:
    return [
        str(item.get("content") or "").strip()
        for item in history or []
        if isinstance(item, dict)
        and item.get("role") == "user"
        and item.get("content")
    ]


def _assistant_messages(history: list[dict[str, Any]] | None) -> list[str]:
    return [
        str(item.get("content") or "").strip()
        for item in history or []
        if isinstance(item, dict)
        and item.get("role") == "assistant"
        and item.get("content")
    ]


def _short_topic(value: str, fallback: str) -> str:
    topic = re.sub(r"\s+", " ", str(value or "")).strip(" ？?。.!！")
    if not topic:
        return fallback
    return topic if len(topic) <= 48 else f"{topic[:45]}..."


def _comparison_key(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", str(value or "").casefold())


def _append_unique(items: list[str], value: str) -> None:
    key = _comparison_key(value)
    if key and all(_comparison_key(item) != key for item in items):
        items.append(value)
