from data_ops.services.metrics.operations import _safe_int


def test_safe_int_uses_default_for_invalid_values():
    assert _safe_int("bad", 20) == 20
    assert _safe_int(None, 20) == 20
    assert _safe_int("5", 20) == 5
