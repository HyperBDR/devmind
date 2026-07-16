"""Low-cost intent routing for the Data Ops assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_assistant.policies import (
    build_operations_only_reply,
    is_technical_implementation_request,
)


@dataclass(frozen=True)
class DataOpsIntent:
    """Describe the work required before any data or model call."""

    key: str
    requires_data: bool
    skill_key: str | None = None
    skill_keys: tuple[str, ...] = ()
    analysis_skill_key: str | None = None
    language: str = "zh-CN"


_CAPABILITY_PATTERN = re.compile(
    r"你能做什么|可以做什么|支持哪些|如何使用|"
    r"what can you do|how can you help|capabilit|help me use",
    re.IGNORECASE,
)
_GREETING_PATTERN = re.compile(
    r"^(你好|您好|嗨|hi|hello|hey)[！!。.\s]*$",
    re.IGNORECASE,
)
_THANKS_PATTERN = re.compile(
    r"^(谢谢|感谢|多谢|thanks|thank you)[！!。.\s]*$",
    re.IGNORECASE,
)
_CONTEXTUAL_FOLLOW_UP_PATTERN = re.compile(
    r"^(?:再|继续|进一步|那|那么|这些|上述|其中|它们|这个|该|也|还|"
    r"what about|how about|and\b|also\b|then\b|those\b|these\b|them\b|"
    r"it\b)",
    re.IGNORECASE,
)
_DATA_ROUTES = (
    (
        "data_quality",
        "data_quality_guard",
        re.compile(
            r"同步|数据质量|权限|字段缺失|抓取|可信|完整性|"
            r"sync|data quality|permission|missing field|reliab",
            re.IGNORECASE,
        ),
    ),
    (
        "renewal_expiry",
        "renewal_and_expiry_monitor",
        re.compile(
            r"到期|续约|license|expiry|expire|renewal",
            re.IGNORECASE,
        ),
    ),
    (
        "cash_collection",
        "cash_collection_risk",
        re.compile(
            r"回款|待回款|催收|应收|账期|"
            r"collection|receivable|outstanding|payment",
            re.IGNORECASE,
        ),
    ),
    (
        "pipeline_conversion",
        "pipeline_conversion_diagnosis",
        re.compile(
            r"pipeline|立项|转化|高潜|停滞|" r"conversion|opportunit|stalled",
            re.IGNORECASE,
        ),
    ),
    (
        "overseas_business",
        "overseas_business_review",
        re.compile(
            r"海外|国家|地区|结算|利润|成本|"
            r"oversea|country|region|settlement|profit|margin",
            re.IGNORECASE,
        ),
    ),
)


def recognize_data_ops_intent(
    message: str,
    *,
    analysis_skill_key: str | None = None,
    context_message: str = "",
) -> DataOpsIntent:
    """Classify a request without a database or LLM call."""

    text = str(message or "").strip()
    language = _message_language(text)
    if is_technical_implementation_request(text):
        return DataOpsIntent(
            key="technical_request",
            requires_data=False,
            language=language,
        )
    if _CAPABILITY_PATTERN.search(text):
        return DataOpsIntent(
            key="capability_help",
            requires_data=False,
            language=language,
        )
    if _GREETING_PATTERN.fullmatch(text):
        return DataOpsIntent(
            key="greeting",
            requires_data=False,
            language=language,
        )
    if _THANKS_PATTERN.fullmatch(text):
        return DataOpsIntent(
            key="acknowledgement",
            requires_data=False,
            language=language,
        )
    matched_routes = _matched_data_routes(text)
    if matched_routes:
        skill_keys = tuple(
            dict.fromkeys(skill_key for _key, skill_key in matched_routes)
        )
        if len(matched_routes) == 1:
            key, skill_key = matched_routes[0]
            return DataOpsIntent(
                key=key,
                requires_data=True,
                skill_key=skill_key,
                skill_keys=skill_keys,
                analysis_skill_key=analysis_skill_key,
                language=language,
            )
        return DataOpsIntent(
            key="multi_domain",
            requires_data=True,
            skill_keys=skill_keys,
            analysis_skill_key=analysis_skill_key,
            language=language,
        )
    context_routes = _matched_data_routes(context_message)
    if context_routes and _is_contextual_follow_up(text):
        context_skill_keys = tuple(
            dict.fromkeys(skill_key for _key, skill_key in context_routes)
        )
        if len(context_routes) == 1:
            key, skill_key = context_routes[0]
            return DataOpsIntent(
                key=key,
                requires_data=True,
                skill_key=skill_key,
                skill_keys=context_skill_keys,
                analysis_skill_key=analysis_skill_key,
                language=language,
            )
        return DataOpsIntent(
            key="multi_domain",
            requires_data=True,
            skill_keys=context_skill_keys,
            analysis_skill_key=analysis_skill_key,
            language=language,
        )
    if analysis_skill_key:
        return DataOpsIntent(
            key="root_cause_diagnosis",
            requires_data=True,
            skill_key=analysis_skill_key,
            skill_keys=(analysis_skill_key,),
            analysis_skill_key=analysis_skill_key,
            language=language,
        )
    return DataOpsIntent(
        key="business_health",
        requires_data=True,
        skill_key="business_health_scan",
        skill_keys=("business_health_scan",),
        language=language,
    )


def has_explicit_data_domain(message: str) -> bool:
    """Return whether a message names at least one known business domain."""

    return bool(_matched_data_routes(str(message or "")))


def _matched_data_routes(message: str) -> list[tuple[str, str]]:
    return [
        (key, skill_key)
        for key, skill_key, pattern in _DATA_ROUTES
        if pattern.search(str(message or ""))
    ]


def _is_contextual_follow_up(message: str) -> bool:
    """Return whether a domain-free message explicitly continues context."""

    text = str(message or "").strip()
    return bool(_CONTEXTUAL_FOLLOW_UP_PATTERN.search(text))


def build_direct_intent_reply(intent: DataOpsIntent) -> str:
    """Return a deterministic response for zero-data intents."""

    if intent.key == "technical_request":
        message = (
            "技术实现" if intent.language == "zh-CN" else "implementation"
        )
        return build_operations_only_reply(message)
    if intent.language == "en":
        if intent.key == "acknowledgement":
            return "You're welcome. Ask me whenever you need Data Ops help."
        return (
            "I can analyze contracts, collections, renewals, Pipeline, "
            "overseas business, and data quality. Data is queried only "
            "after I identify the relevant business intent."
        )
    if intent.key == "acknowledgement":
        return "不客气。需要 Data Ops 分析时可以继续问我。"
    return (
        "我可以分析合同、回款、续约、Pipeline、海外业务和数据质量。"
        "我会先识别业务意图，再按需查询相关数据。"
    )


def _message_language(message: str) -> str:
    if re.search(r"[\u3400-\u9fff]", message):
        return "zh-CN"
    return "en"
