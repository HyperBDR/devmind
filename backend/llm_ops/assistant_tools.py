"""Read-only assistant tools and controlled LLM Ops operation entries."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from llm_ops.models import (
    ChannelModelPrice,
    ChannelModelPriceHistory,
    LLMModel,
    ModelPriceItem,
    PriceCollectionRun,
    PriceCollectionSource,
    ResaleListing,
    ResaleListingExclusion,
    ResalePlatform,
)
from llm_ops.services import (
    OPERATION_SCOPE_OPERATIONAL,
    build_currency_conversion_context,
    calculate_usage_cost,
    compute_model_decision,
    convert_currency_amount,
    resolve_channel_model_currency,
    resolve_channel_model_price,
    resolve_resale_listing_currency,
    selected_price_item_group,
)

DEFAULT_LIMIT = 30
MAX_LIMIT = 100
DEFAULT_INPUT_TOKENS = 10_000_000
DEFAULT_OUTPUT_TOKENS = 15_000_000

DECISION_STATUSES = {
    "all",
    "priority",
    "no_supply",
    "currency_unresolved",
    "platform_fee_unresolved",
    "low_yield",
    "not_lowest_channel",
    "unlisted",
    "single_channel",
    "ready",
}
PRIORITY_STATUSES = {
    "no_supply",
    "currency_unresolved",
    "platform_fee_unresolved",
    "low_yield",
    "not_lowest_channel",
    "unlisted",
    "single_channel",
}

LLM_OPS_QUESTION_GROUPS = [
    {
        "key": "operations",
        "title": "运营待办",
        "questions": [
            "当前需要处理的运营模型有哪些？",
            "哪些运营模型缺少渠道价格？",
        ],
    },
    {
        "key": "listing",
        "title": "挂售与收益",
        "questions": [
            "哪些运营模型还没有挂售？",
            "哪些模型收益率低于预警线？",
            "当前挂售没有使用最低采购渠道的模型有哪些？",
        ],
    },
    {
        "key": "market",
        "title": "市场价格",
        "questions": [
            "查询某个元模型的全部市场参考价。",
            "最近采购渠道价格变化最大的模型有哪些？",
        ],
    },
    {
        "key": "quality",
        "title": "数据质量",
        "questions": [
            "最近采集失败或数据异常的价格源有哪些？",
        ],
    },
]


def _tool(name, description, properties=None, required=None):
    parameters = {
        "type": "object",
        "properties": properties or {},
    }
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


LLM_OPS_TOOL_SCHEMAS = [
    _tool(
        "llm_ops_get_overview",
        "查询运营模型、市场参考模型和运营待办数量。",
        {
            "platform_id": {"type": "integer"},
        },
    ),
    _tool(
        "llm_ops_query_decisions",
        ("查询运营模型决策队列；" "不会把市场参考模型算作运营问题。"),
        {
            "status": {
                "type": "string",
                "enum": sorted(DECISION_STATUSES),
            },
            "query": {"type": "string"},
            "platform_id": {"type": "integer"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    ),
    _tool(
        "llm_ops_query_market_prices",
        "按元模型名称或编码查询全部当前市场参考价格。",
        {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        ["query"],
    ),
    _tool(
        "llm_ops_query_price_changes",
        "查询近期采购渠道价格变化并按变化幅度排序。",
        {
            "days": {"type": "integer", "minimum": 1, "maximum": 365},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    ),
    _tool(
        "llm_ops_query_source_health",
        ("查询价格源启停、最近采集结果、" "失败原因和陈旧状态。"),
        {
            "status": {
                "type": "string",
                "enum": ["all", "disabled", "failed", "healthy", "stale"],
            },
            "stale_hours": {
                "type": "integer",
                "minimum": 1,
                "maximum": 8760,
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    ),
    _tool(
        "llm_ops_get_operation_entry",
        ("返回安全的控制台操作入口；" "本工具不会执行任何数据修改。"),
        {
            "action": {
                "type": "string",
                "enum": [
                    "configure_channel",
                    "configure_exchange_rate",
                    "configure_platform_fee",
                    "inspect_price_changes",
                    "inspect_price_source",
                    "inspect_reconciliation",
                    "publish_listing",
                    "review_margin",
                    "switch_procurement_channel",
                    "view_market_price",
                ],
            },
            "model_id": {"type": "integer"},
            "platform_id": {"type": "integer"},
            "source_id": {"type": "integer"},
        },
        ["action"],
    ),
]


def get_llm_ops_assistant_profile() -> dict[str, Any]:
    """Return questions and safety boundaries for the assistant UI."""

    return {
        "question_groups": LLM_OPS_QUESTION_GROUPS,
        "quick_question_limit": 4,
        "ui_i18n": {
            "description_key": "llmOps.assistant.description",
            "drawer_label_key": "llmOps.assistant.drawerLabel",
            "open_label_key": "llmOps.assistant.openLabel",
            "question_groups_key": "llmOps.assistant.questionGroups",
            "title_key": "llmOps.assistant.title",
        },
        "query_tools": {
            "tools": [
                item["function"]["name"] for item in LLM_OPS_TOOL_SCHEMAS
            ],
            "rules": [
                "运营动作查询只允许 operation_scope=operational。",
                "market_reference 只用于价格比较和采购决策。",
                ("操作工具只返回控制台入口，" "不直接修改业务数据。"),
                f"单次查询最多返回 {MAX_LIMIT} 行。",
            ],
        },
    }


def execute_llm_ops_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Validate and execute one registered LLM Ops assistant tool."""

    handlers = {
        "llm_ops_get_overview": get_llm_ops_overview,
        "llm_ops_query_decisions": query_llm_ops_decisions,
        "llm_ops_query_market_prices": query_market_prices,
        "llm_ops_query_price_changes": query_price_changes,
        "llm_ops_query_source_health": query_source_health,
        "llm_ops_get_operation_entry": get_operation_entry,
    }
    handler = handlers.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        result = handler(arguments or {})
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "result": result}


def _limit(value) -> int:
    try:
        normalized = int(value or DEFAULT_LIMIT)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    return max(1, min(normalized, MAX_LIMIT))


def _selected_platform(value):
    queryset = ResalePlatform.objects.filter(is_active=True).order_by(
        "name",
        "id",
    )
    if value:
        selected = queryset.filter(id=value).first()
        if selected is not None:
            return selected
    return queryset.filter(code="agione").first() or queryset.first()


def _operation_model_ids(platform) -> set[int]:
    channel_model_ids = set(
        ChannelModelPrice.objects.values_list("model_id", flat=True)
    )
    if platform is None:
        return channel_model_ids
    listing_ids = set(
        ResaleListing.objects.filter(platform=platform).values_list(
            "model_id",
            flat=True,
        )
    )
    excluded_ids = set(
        ResaleListingExclusion.objects.filter(platform=platform).values_list(
            "model_id",
            flat=True,
        )
    )
    return (channel_model_ids | listing_ids) - (excluded_ids - listing_ids)


def get_llm_ops_overview(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return scope counts and operational decision counts."""

    platform = _selected_platform(arguments.get("platform_id"))
    active_ids = set(
        LLMModel.objects.filter(is_active=True).values_list("id", flat=True)
    )
    operational_ids = active_ids & _operation_model_ids(platform)
    rows = _decision_rows(platform=platform, model_ids=operational_ids)
    decision_counts = defaultdict(int)
    for row in rows:
        decision_counts[row["decision_status"]] += 1
    for status in DECISION_STATUSES - {"all", "priority"}:
        decision_counts[status] += 0
    return {
        "active_models": len(active_ids),
        "operational_models": len(operational_ids),
        "market_reference_models": len(active_ids - operational_ids),
        "decision_counts": dict(decision_counts),
        "platform": _platform_payload(platform),
        "scope_rule": (
            "Only models with channel configuration or platform listing "
            "intent are operational; all others are market references."
        ),
        "updated_at": timezone.now().isoformat(),
    }


def query_llm_ops_decisions(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return filtered operational decision rows."""

    status = str(arguments.get("status") or "priority").strip()
    if status not in DECISION_STATUSES:
        raise ValueError("invalid decision status")
    platform = _selected_platform(arguments.get("platform_id"))
    model_ids = _operation_model_ids(platform)
    rows = _decision_rows(platform=platform, model_ids=model_ids)
    query = str(arguments.get("query") or "").strip().lower()
    if query:
        rows = [
            row
            for row in rows
            if query
            in " ".join(
                [
                    row["model_name"],
                    row["model_code"],
                    row["provider_name"],
                ]
            ).lower()
        ]
    if status == "priority":
        rows = [
            row for row in rows if row["decision_status"] in PRIORITY_STATUSES
        ]
    elif status != "all":
        rows = [row for row in rows if row["decision_status"] == status]
    rows.sort(
        key=lambda row: (
            row["decision_priority"],
            row["provider_name"],
            row["model_name"],
        )
    )
    limit = _limit(arguments.get("limit"))
    return {
        "status": status,
        "operation_scope": OPERATION_SCOPE_OPERATIONAL,
        "platform": _platform_payload(platform),
        "rows": rows[:limit],
        "row_count": min(len(rows), limit),
        "total_matches": len(rows),
    }


def _decision_rows(*, platform, model_ids) -> list[dict[str, Any]]:
    models = list(
        LLMModel.objects.filter(is_active=True, id__in=model_ids)
        .select_related("provider", "meta_model")
        .order_by("provider__name", "name", "id")
    )
    overrides = list(
        ChannelModelPrice.objects.filter(
            model_id__in=model_ids,
            is_listed=True,
            channel__is_active=True,
        ).select_related("channel", "model", "price_source")
    )
    overrides_by_model = defaultdict(list)
    for override in overrides:
        overrides_by_model[override.model_id].append(override)
    price_items_by_override = _current_price_items_by_channel_price(overrides)
    listings_by_model = defaultdict(list)
    if platform is not None:
        listings = ResaleListing.objects.filter(
            platform=platform,
            is_active=True,
        ).select_related("channel", "model", "platform")
        for listing in listings:
            listings_by_model[listing.model_id].append(listing)

    currency_context = build_currency_conversion_context("CNY")
    rows = []
    for model in models:
        options = _channel_options(
            model,
            overrides_by_model.get(model.id, []),
            currency_context,
            price_items_by_override,
        )
        best = options[0] if options else None
        listing = _select_listing(
            listings_by_model.get(model.id, []),
            best,
        )
        listing_payload = _listing_payload(
            listing,
            options,
            best,
            currency_context,
        )
        decision = compute_model_decision(
            procurement_row={
                "best_channel": best,
                "options": options,
                "requires_currency_conversion": any(
                    option["requires_currency_conversion"]
                    for option in options
                ),
            },
            current_listing=listing_payload,
            platform=platform,
            operation_scope=OPERATION_SCOPE_OPERATIONAL,
            last_data_event_at=model.updated_at,
        )
        action = decision["decision_action"]
        rows.append(
            {
                "model_id": model.id,
                "model_name": model.name,
                "model_code": model.code,
                "meta_model_id": model.meta_model_id,
                "provider_name": model.provider.name,
                "operation_scope": OPERATION_SCOPE_OPERATIONAL,
                "coverage_count": len(options),
                "recommended_channel": _channel_payload(best),
                "current_listing": _current_listing_payload(listing_payload),
                "input_yield": _decimal_text(decision.get("input_yield")),
                "output_yield": _decimal_text(decision.get("output_yield")),
                "decision_status": decision["decision_status"],
                "decision_action": action,
                "decision_priority": decision["decision_priority"],
                "operation_entry": get_operation_entry(
                    {
                        "action": _entry_action(action),
                        "model_id": model.id,
                        "platform_id": platform.id if platform else None,
                    }
                ),
                "updated_at": decision["last_data_event_at"],
            }
        )
    return rows


def _current_price_items_by_channel_price(overrides):
    """Bulk-load current price items for channel price configurations."""

    if not overrides:
        return {}
    model_ids = {override.model_id for override in overrides}
    meta_model_ids = {
        override.model.meta_model_id
        for override in overrides
        if override.model.meta_model_id
    }
    candidates = list(
        ModelPriceItem.objects.filter(is_current=True)
        .filter(
            Q(model_id__in=model_ids) | Q(meta_model_id__in=meta_model_ids)
        )
        .select_related(
            "meta_model",
            "model",
            "model__meta_model",
            "offering",
            "sku",
            "source",
            "source__provider",
        )
        .order_by("dimension", "tier_start", "id")
    )
    direct_by_model = defaultdict(list)
    fallback_by_meta_model = defaultdict(list)
    for item in candidates:
        if item.model_id in model_ids:
            direct_by_model[item.model_id].append(item)
        if item.meta_model_id in meta_model_ids and item.unit_price > 0:
            fallback_by_meta_model[item.meta_model_id].append(item)

    selected = {}
    for override in overrides:
        direct = direct_by_model.get(override.model_id, [])
        fallback = fallback_by_meta_model.get(
            override.model.meta_model_id,
            [],
        )
        if override.price_source_id:
            direct = [
                item
                for item in direct
                if item.source_id == override.price_source_id
            ]
            fallback = [
                item
                for item in fallback
                if item.source_id == override.price_source_id
            ]
        rows = direct or fallback
        selected[override.id] = (
            selected_price_item_group(rows, model=override.model)
            if rows
            else []
        )
    return selected


def _channel_options(
    model,
    overrides,
    currency_context,
    price_items_by_override,
):
    options = []
    for override in overrides:
        unit_prices = resolve_channel_model_price(
            override.channel,
            model,
            override=override,
            source_items=price_items_by_override.get(override.id, []),
        )
        input_price = Decimal(str(unit_prices.input_per_million or "0"))
        output_price = Decimal(str(unit_prices.output_per_million or "0"))
        if input_price <= 0 or output_price <= 0:
            continue
        currency = resolve_channel_model_currency(
            override.channel,
            model,
            override=override,
        )
        converted_input = convert_currency_amount(
            input_price,
            currency,
            currency_context,
        )
        converted_output = convert_currency_amount(
            output_price,
            currency,
            currency_context,
        )
        estimated_cost = calculate_usage_cost(
            unit_prices,
            input_tokens=DEFAULT_INPUT_TOKENS,
            output_tokens=DEFAULT_OUTPUT_TOKENS,
        )
        converted_cost = convert_currency_amount(
            estimated_cost,
            currency,
            currency_context,
        )
        requires_conversion = any(
            value is None
            for value in (
                converted_input,
                converted_output,
                converted_cost,
            )
        )
        options.append(
            {
                "channel_id": override.channel_id,
                "channel_name": override.channel.name,
                "price_source_id": override.price_source_id,
                "currency": (
                    currency
                    if requires_conversion
                    else currency_context.display_currency
                ),
                "original_currency": currency,
                "input_price_per_million": _decimal_value(
                    converted_input or input_price
                ),
                "output_price_per_million": _decimal_value(
                    converted_output or output_price
                ),
                "estimated_cost": _decimal_value(
                    converted_cost or estimated_cost
                ),
                "requires_currency_conversion": requires_conversion,
                "updated_at": override.updated_at.isoformat(),
            }
        )
    options.sort(
        key=lambda item: (
            item["requires_currency_conversion"],
            Decimal(str(item["estimated_cost"])),
            item["channel_id"],
        )
    )
    return options


def _select_listing(listings, best):
    if not listings:
        return None
    if best is not None:
        best_channel_id = best["channel_id"]
        for listing in listings:
            if listing.channel_id in {None, best_channel_id}:
                return listing
    return listings[0]


def _listing_payload(listing, options, best, currency_context):
    if listing is None:
        return None
    option = best
    if listing.channel_id is not None:
        option = next(
            (
                row
                for row in options
                if row["channel_id"] == listing.channel_id
            ),
            None,
        )
    retail_currency = resolve_resale_listing_currency(listing)
    retail_input = convert_currency_amount(
        listing.retail_input_price_per_million,
        retail_currency,
        currency_context,
    )
    retail_output = convert_currency_amount(
        listing.retail_output_price_per_million,
        retail_currency,
        currency_context,
    )
    requires_conversion = any(
        value is None for value in (retail_input, retail_output)
    ) or bool(option and option["requires_currency_conversion"])
    return {
        "channel_id": listing.channel_id,
        "channel_name": (listing.channel.name if listing.channel_id else None),
        "channel_type": (
            "fixed_channel" if listing.channel_id else "auto_best"
        ),
        "currency": (
            retail_currency
            if requires_conversion
            else currency_context.display_currency
        ),
        "retail_input_price_per_million": _decimal_value(
            retail_input or listing.retail_input_price_per_million
        ),
        "retail_output_price_per_million": _decimal_value(
            retail_output or listing.retail_output_price_per_million
        ),
        "cost_input_price_per_million": (
            option.get("input_price_per_million") if option else None
        ),
        "cost_output_price_per_million": (
            option.get("output_price_per_million") if option else None
        ),
        "requires_currency_conversion": requires_conversion,
        "is_listed": True,
        "updated_at": listing.updated_at.isoformat(),
    }


def _channel_payload(option):
    if option is None:
        return None
    return {
        "channel_id": option["channel_id"],
        "channel_name": option["channel_name"],
        "currency": option["currency"],
        "input_price_per_million": option["input_price_per_million"],
        "output_price_per_million": option["output_price_per_million"],
    }


def _current_listing_payload(listing):
    if listing is None:
        return {"is_listed": False}
    return {
        "is_listed": True,
        "channel_id": listing["channel_id"],
        "channel_name": listing["channel_name"],
        "channel_type": listing["channel_type"],
        "currency": listing["currency"],
        "retail_input_price_per_million": listing[
            "retail_input_price_per_million"
        ],
        "retail_output_price_per_million": listing[
            "retail_output_price_per_million"
        ],
    }


def _entry_action(decision_action):
    return {
        "add_channel_coverage": "configure_channel",
        "configure_channel": "configure_channel",
        "configure_exchange_rate": "configure_exchange_rate",
        "configure_platform_fee": "configure_platform_fee",
        "keep": "view_market_price",
        "publish_listing": "publish_listing",
        "review_pricing_or_channel": "review_margin",
        "switch_lowest_channel": "switch_procurement_channel",
        "view_market_price": "view_market_price",
    }.get(decision_action, "view_market_price")


def query_market_prices(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return current normalized prices matching a canonical model."""

    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    matches = Q(meta_model__name__icontains=query) | Q(
        meta_model__code__icontains=query
    )
    matches |= Q(model__name__icontains=query) | Q(
        model__code__icontains=query
    )
    items = list(
        ModelPriceItem.objects.filter(is_current=True)
        .filter(matches)
        .select_related("meta_model", "model", "provider", "source")
        .order_by(
            "meta_model__name",
            "source__name",
            "provider__name",
            "dimension",
            "id",
        )[: _limit(arguments.get("limit"))]
    )
    rows = [_market_price_payload(item) for item in items]
    if not rows:
        rows = _legacy_market_price_rows(
            query,
            _limit(arguments.get("limit")),
        )
    return {
        "query": query,
        "rows": rows,
        "row_count": len(rows),
        "usage_rule": (
            "Prices are market references unless a separate channel or "
            "platform configuration places the model in operational scope."
        ),
    }


def _market_price_payload(item):
    return {
        "meta_model_id": item.meta_model_id,
        "meta_model_name": item.meta_model.name,
        "meta_model_code": item.meta_model.code,
        "model_id": item.model_id,
        "model_name": item.model.name if item.model_id else "",
        "provider_name": item.provider.name,
        "source_id": item.source_id,
        "source_name": item.source.name if item.source_id else "",
        "source_category": (
            item.source.source_category if item.source_id else "unknown"
        ),
        "price_role": item.price_role,
        "dimension": item.dimension,
        "billing_unit": item.billing_unit,
        "currency": item.currency,
        "unit_price": str(item.unit_price),
        "effective_from": item.effective_from.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _legacy_market_price_rows(query, limit):
    matches = Q(meta_model__name__icontains=query) | Q(
        meta_model__code__icontains=query
    )
    matches |= Q(name__icontains=query) | Q(code__icontains=query)
    models = (
        LLMModel.objects.filter(is_active=True)
        .filter(matches)
        .select_related("meta_model", "provider", "source")
        .order_by("meta_model__name", "provider__name", "name", "id")
    )
    rows = []
    for model in models:
        for dimension, value in (
            ("text_input", model.input_price_per_million),
            ("text_output", model.output_price_per_million),
        ):
            rows.append(
                {
                    "meta_model_id": model.meta_model_id,
                    "meta_model_name": model.meta_model.name,
                    "meta_model_code": model.meta_model.code,
                    "model_id": model.id,
                    "model_name": model.name,
                    "provider_name": model.provider.name,
                    "source_id": model.source_id,
                    "source_name": (
                        model.source.name if model.source_id else ""
                    ),
                    "source_category": (
                        model.source.source_category
                        if model.source_id
                        else "unknown"
                    ),
                    "price_role": model.price_role,
                    "dimension": dimension,
                    "billing_unit": "per_1m_tokens",
                    "currency": model.currency,
                    "unit_price": str(value),
                    "effective_from": (
                        model.last_price_updated_at or model.updated_at
                    ).isoformat(),
                    "updated_at": model.updated_at.isoformat(),
                }
            )
            if len(rows) == limit:
                return rows
    return rows


def query_price_changes(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compare consecutive procurement price versions."""

    days = _bounded_int(arguments.get("days"), 30, 1, 365, "days")
    cutoff = timezone.now() - timedelta(days=days)
    previous_version = (
        ChannelModelPriceHistory.objects.filter(
            channel_id=OuterRef("channel_id"),
            model_id=OuterRef("model_id"),
            effective_from__lt=cutoff,
        )
        .order_by("-effective_from", "-id")
        .values("id")[:1]
    )
    baseline_ids = list(
        ChannelModelPriceHistory.objects.filter(
            effective_from__gte=cutoff,
        )
        .values("channel_id", "model_id")
        .distinct()
        .annotate(baseline_id=Subquery(previous_version))
        .values_list("baseline_id", flat=True)
    )
    history = list(
        ChannelModelPriceHistory.objects.filter(
            Q(effective_from__gte=cutoff) | Q(id__in=baseline_ids)
        )
        .select_related("channel", "model", "model__provider")
        .order_by(
            "channel_id",
            "model_id",
            "-effective_from",
            "-id",
        )
    )
    grouped = defaultdict(list)
    for item in history:
        grouped[(item.channel_id, item.model_id)].append(item)
    rows = []
    for versions in grouped.values():
        if len(versions) < 2:
            continue
        latest, previous = versions[:2]
        input_change = _percent_change(
            latest.input_price_per_million,
            previous.input_price_per_million,
        )
        output_change = _percent_change(
            latest.output_price_per_million,
            previous.output_price_per_million,
        )
        magnitude = max(
            abs(input_change or Decimal("0")),
            abs(output_change or Decimal("0")),
        )
        rows.append(
            {
                "model_id": latest.model_id,
                "model_name": latest.model.name,
                "provider_name": latest.model.provider.name,
                "channel_id": latest.channel_id,
                "channel_name": latest.channel.name,
                "currency": latest.currency,
                "input_price_before": str(previous.input_price_per_million),
                "input_price_after": str(latest.input_price_per_million),
                "input_change_percent": _percent_text(input_change),
                "output_price_before": str(previous.output_price_per_million),
                "output_price_after": str(latest.output_price_per_million),
                "output_change_percent": _percent_text(output_change),
                "changed_at": latest.effective_from.isoformat(),
                "magnitude": magnitude,
                "operation_entry": get_operation_entry(
                    {
                        "action": "inspect_price_changes",
                        "model_id": latest.model_id,
                    }
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            -row["magnitude"],
            row["model_name"],
            row["channel_name"],
        )
    )
    for row in rows:
        row.pop("magnitude", None)
    limit = _limit(arguments.get("limit"))
    return {
        "days": days,
        "rows": rows[:limit],
        "row_count": min(len(rows), limit),
        "total_matches": len(rows),
    }


def query_source_health(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return latest collection state for price sources."""

    status = str(arguments.get("status") or "all").strip()
    allowed_statuses = {"all", "disabled", "failed", "healthy", "stale"}
    if status not in allowed_statuses:
        raise ValueError("invalid source health status")
    stale_hours = _bounded_int(
        arguments.get("stale_hours"),
        48,
        1,
        8760,
        "stale_hours",
    )
    cutoff = timezone.now() - timedelta(hours=stale_hours)
    latest_runs = PriceCollectionRun.objects.filter(
        source_id=OuterRef("pk")
    ).order_by("-started_at", "-id")
    sources = PriceCollectionSource.objects.annotate(
        latest_run_status=Subquery(latest_runs.values("status")[:1]),
        latest_run_started_at=Subquery(latest_runs.values("started_at")[:1]),
        latest_run_finished_at=Subquery(latest_runs.values("finished_at")[:1]),
        latest_run_error=Subquery(latest_runs.values("error_message")[:1]),
    ).order_by("name", "id")
    rows = []
    for source in sources:
        health_status = _source_health_status(source, cutoff)
        if status != "all" and health_status != status:
            continue
        rows.append(
            {
                "source_id": source.id,
                "source_name": source.name,
                "source_category": source.source_category,
                "collection_method": source.collection_method,
                "is_enabled": source.is_enabled,
                "health_status": health_status,
                "last_collected_at": _iso(source.last_collected_at),
                "latest_run_status": source.latest_run_status,
                "latest_run_started_at": _iso(source.latest_run_started_at),
                "latest_run_finished_at": _iso(source.latest_run_finished_at),
                "latest_error": source.latest_run_error or "",
                "operation_entry": get_operation_entry(
                    {
                        "action": "inspect_price_source",
                        "source_id": source.id,
                    }
                ),
            }
        )
    limit = _limit(arguments.get("limit"))
    return {
        "status": status,
        "stale_hours": stale_hours,
        "rows": rows[:limit],
        "row_count": min(len(rows), limit),
        "total_matches": len(rows),
        "updated_at": timezone.now().isoformat(),
    }


def _source_health_status(source, cutoff):
    if not source.is_enabled:
        return "disabled"
    if source.latest_run_status == PriceCollectionRun.STATUS_FAILED:
        return "failed"
    latest_at = (
        source.last_collected_at
        or source.latest_run_finished_at
        or source.latest_run_started_at
    )
    if latest_at is None or latest_at < cutoff:
        return "stale"
    return "healthy"


OPERATION_ENTRIES = {
    "configure_channel": {
        "label": "配置采购渠道",
        "section": "channels",
    },
    "configure_exchange_rate": {
        "label": "查看汇率状态",
        "path": "/cloud-billing/billing",
        "section": "",
    },
    "configure_platform_fee": {
        "label": "配置平台费用",
        "open_platform_config": True,
        "section": "monitor",
    },
    "inspect_price_changes": {
        "label": "查看价格变化",
        "section": "priceChanges",
    },
    "inspect_price_source": {
        "label": "查看价格源",
        "section": "providers",
    },
    "inspect_reconciliation": {
        "label": "查看对账异常",
        "section": "reconciler",
    },
    "publish_listing": {
        "label": "进入挂售工作台",
        "section": "reseller",
    },
    "review_margin": {
        "label": "复核挂售价与收益",
        "section": "reseller",
    },
    "switch_procurement_channel": {
        "label": "切换采购渠道",
        "section": "reseller",
    },
    "view_market_price": {
        "label": "查看市场价格",
        "section": "modelWorkbench",
    },
}


def get_operation_entry(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return one allow-listed console navigation target."""

    action = str(arguments.get("action") or "").strip()
    entry = OPERATION_ENTRIES.get(action)
    if entry is None:
        raise ValueError("invalid operation action")
    label = entry["label"]
    section = entry["section"]
    params = {"section": section} if section else {}
    model_id = _optional_positive_int(arguments.get("model_id"), "model_id")
    platform_id = _optional_positive_int(
        arguments.get("platform_id"),
        "platform_id",
    )
    source_id = _optional_positive_int(
        arguments.get("source_id"),
        "source_id",
    )
    if model_id is not None:
        params["model_id"] = model_id
    if source_id is not None:
        params["source_id"] = source_id
    if entry.get("open_platform_config"):
        params["open_platform_config"] = 1
        if platform_id is not None:
            params["platform_id"] = platform_id
    path = entry.get("path") or f"/llm-ops?{urlencode(params)}"
    return {
        "action": action,
        "label": label,
        "section": section,
        "path": path,
        "executes_mutation": False,
    }


def _platform_payload(platform):
    if platform is None:
        return None
    return {
        "platform_id": platform.id,
        "platform_name": platform.name,
        "currency": platform.currency,
    }


def _decimal_value(value):
    return float(Decimal(str(value)))


def _decimal_text(value):
    return str(value) if value is not None else None


def _percent_change(current, previous):
    old = Decimal(str(previous))
    if old == 0:
        return None
    return (Decimal(str(current)) - old) / old * Decimal("100")


def _percent_text(value):
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))


def _bounded_int(value, default, minimum, maximum, field_name):
    try:
        normalized = int(value if value is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if normalized < minimum or normalized > maximum:
        raise ValueError(
            f"{field_name} must be between {minimum} and {maximum}"
        )
    return normalized


def _optional_positive_int(value, field_name):
    if value in (None, ""):
        return None
    return _bounded_int(value, 1, 1, 2_147_483_647, field_name)


def _iso(value):
    return value.isoformat() if value is not None else None
