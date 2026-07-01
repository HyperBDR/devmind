"""Resale workflow configuration helpers."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from .models import ResalePlatform


CONFIG_VERSION = 1

DEFAULT_POLICIES = {
    "auto_approve_enabled": True,
    "manual_confirm_required": True,
    "feishu_approval_enabled": False,
    "auto_apply_after_approval": True,
    "offline_approval_enabled": False,
}

DEFAULT_NODES = [
    {
        "id": "select_scope",
        "lane": "pricing",
        "label": "选择模型与采购渠道",
        "description": "来自模型主数据、采购渠道和渠道价格。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "compose_price",
        "lane": "pricing",
        "label": "生成上架价格",
        "description": "按统一利润率生成输入、输出和缓存价格。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "margin_gate",
        "lane": "approval",
        "label": "是否启用免审",
        "description": "按平台 auto_approve_max_margin_rate 判断是否跳过审核。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "auto_confirm",
        "lane": "approval",
        "label": "免审通过",
        "description": "命中阈值后跳过内部或外部审核。",
        "status": "configurable",
        "enabled": True,
    },
    {
        "id": "manual_review",
        "lane": "approval",
        "label": "内部人工审核",
        "description": "未命中免审时进入内部人工确认。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "feishu_approval",
        "lane": "approval",
        "label": "飞书审批",
        "description": "未命中免审时提交外部飞书审批。",
        "status": "planned",
        "enabled": False,
    },
    {
        "id": "publish_online",
        "lane": "publishing",
        "label": "通过后处理",
        "description": "免审或审核通过后再决定自动上线或待确认上线。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "offline_request",
        "lane": "publishing",
        "label": "申请下架",
        "description": "从 online 进入 pending_offline。",
        "status": "implemented",
        "enabled": True,
    },
    {
        "id": "offline_confirm",
        "lane": "publishing",
        "label": "确认下架或异常处理",
        "description": "支持确认、驳回和标记下架异常。",
        "status": "implemented",
        "enabled": True,
    },
]

DEFAULT_EDGES = [
    {
        "id": "select_to_price",
        "from": "select_scope",
        "to": "compose_price",
        "label": "配置价格",
        "condition": "always",
        "enabled": True,
    },
    {
        "id": "price_to_gate",
        "from": "compose_price",
        "to": "margin_gate",
        "label": "提交上架",
        "condition": "submit",
        "enabled": True,
    },
    {
        "id": "gate_to_auto",
        "from": "margin_gate",
        "to": "auto_confirm",
        "label": "利润率 <= 免审阈值",
        "condition": "within_auto_approve_margin",
        "enabled": True,
    },
    {
        "id": "gate_to_manual",
        "from": "margin_gate",
        "to": "manual_review",
        "label": "未命中免审",
        "condition": "manual_confirm_required",
        "enabled": True,
    },
    {
        "id": "gate_to_feishu",
        "from": "margin_gate",
        "to": "feishu_approval",
        "label": "利润率 > 免审阈值",
        "condition": "above_auto_approve_margin",
        "enabled": False,
    },
    {
        "id": "auto_to_online",
        "from": "auto_confirm",
        "to": "publish_online",
        "label": "免审通过后处理",
        "condition": "auto_approve_passed",
        "enabled": True,
    },
    {
        "id": "manual_to_online",
        "from": "manual_review",
        "to": "publish_online",
        "label": "审核通过后处理",
        "condition": "manual_review_approved",
        "enabled": True,
    },
    {
        "id": "feishu_to_online",
        "from": "feishu_approval",
        "to": "publish_online",
        "label": "审批通过后处理",
        "condition": "approval_approved",
        "enabled": False,
    },
    {
        "id": "online_to_offline_request",
        "from": "publish_online",
        "to": "offline_request",
        "label": "申请下架",
        "condition": "request_offline",
        "enabled": True,
    },
    {
        "id": "offline_request_to_confirm",
        "from": "offline_request",
        "to": "offline_confirm",
        "label": "处理下架",
        "condition": "confirm_or_reject_offline",
        "enabled": True,
    },
]

TRANSITION_ACTIONS = [
    "submit",
    "withdraw",
    "confirm_publish",
    "start_edit",
    "abandon_update",
    "confirm_update",
    "request_offline",
    "confirm_offline",
    "reject_offline",
    "mark_offline_exception",
    "republish",
    "delete",
]


def decimal_to_float(value: Decimal | None) -> float:
    """Return a JSON-safe number for decimal fields."""
    return float(value or Decimal("0"))


def default_resale_workflow_config(platform: ResalePlatform) -> dict[str, Any]:
    """Build the default workflow from the current platform settings."""
    config = {
        "version": CONFIG_VERSION,
        "policies": deepcopy(DEFAULT_POLICIES),
        "nodes": deepcopy(DEFAULT_NODES),
        "edges": deepcopy(DEFAULT_EDGES),
    }
    config["runtime"] = {
        "platform_id": platform.id,
        "platform_name": platform.name,
        "auto_approve_max_margin_rate": decimal_to_float(
            platform.auto_approve_max_margin_rate
        ),
        "transition_actions": TRANSITION_ACTIONS,
    }
    return config


def merge_resale_workflow_config(
    platform: ResalePlatform,
    saved_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge saved configuration with current runtime platform values."""
    config = default_resale_workflow_config(platform)
    if not saved_config:
        return config

    policies = saved_config.get("policies")
    if isinstance(policies, dict):
        config["policies"].update(
            {
                key: value
                for key, value in policies.items()
                if key in DEFAULT_POLICIES
            }
        )

    for key in ("nodes", "edges"):
        if isinstance(saved_config.get(key), list):
            config[key] = deepcopy(saved_config[key])

    config["version"] = CONFIG_VERSION
    return config


def validate_resale_workflow_config(value: Any) -> dict[str, Any]:
    """Validate the editable workflow config payload."""
    if not isinstance(value, dict):
        raise serializers.ValidationError("config must be an object.")

    nodes = value.get("nodes")
    edges = value.get("edges")
    policies = value.get("policies", {})

    if not isinstance(nodes, list) or not nodes:
        raise serializers.ValidationError("config.nodes must be a list.")
    if not isinstance(edges, list):
        raise serializers.ValidationError("config.edges must be a list.")
    if not isinstance(policies, dict):
        raise serializers.ValidationError("config.policies must be an object.")
    merged_policies = deepcopy(DEFAULT_POLICIES)
    merged_policies.update(
        {
            key: value
            for key, value in policies.items()
            if key in DEFAULT_POLICIES
        }
    )
    has_publish_path = any(
        bool(merged_policies[key])
        for key in (
            "auto_approve_enabled",
            "manual_confirm_required",
            "feishu_approval_enabled",
        )
    )
    if not has_publish_path:
        raise serializers.ValidationError(
            "At least one publishing path must be enabled."
        )

    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise serializers.ValidationError("Each node must be an object.")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise serializers.ValidationError("Each node requires id.")
        if node_id in node_ids:
            raise serializers.ValidationError(f"Duplicate node id: {node_id}.")
        node_ids.add(node_id)
        if not str(node.get("label") or "").strip():
            raise serializers.ValidationError(
                f"Node {node_id} requires label."
            )

    edge_ids: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise serializers.ValidationError("Each edge must be an object.")
        edge_id = str(edge.get("id") or "").strip()
        source = str(edge.get("from") or "").strip()
        target = str(edge.get("to") or "").strip()
        if not edge_id:
            raise serializers.ValidationError("Each edge requires id.")
        if edge_id in edge_ids:
            raise serializers.ValidationError(f"Duplicate edge id: {edge_id}.")
        edge_ids.add(edge_id)
        if source not in node_ids or target not in node_ids:
            raise serializers.ValidationError(
                f"Edge {edge_id} references an unknown node."
            )

    return value
