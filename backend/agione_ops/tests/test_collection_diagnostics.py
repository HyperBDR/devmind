"""Check actionable diagnostics without exposing upstream response data."""

import pytest

from agione_ops.collection_diagnostics import (
    describe_failure,
    possible_cause,
    safe_diagnostic,
)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_http_errors_display_actual_status(status):
    diagnostic = {"http_status": status, "stage": "calls"}
    message, suggestion = describe_failure("SOURCE_NON_JSON", diagnostic)
    assert f"HTTP {status}" in message
    assert suggestion
    assert possible_cause("SOURCE_NON_JSON", diagnostic)


def test_network_errors_do_not_claim_to_know_responsibility():
    diagnostic = {"network": "dns", "stage": "identity"}
    message, suggestion = describe_failure("SOURCE_UNREACHABLE", diagnostic)
    assert "域名解析失败" in message
    assert "管理员" in suggestion
    assert "可能" in possible_cause("SOURCE_UNREACHABLE", diagnostic)


def test_invalid_diagnostic_is_discarded():
    assert safe_diagnostic({
        "http_status": True, "stage": [], "network": {}, "body": "PRIVATE",
    }) == {}
