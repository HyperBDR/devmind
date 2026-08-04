"""Shared executable contract for normalized tiered price tables.

A table represents one model, source/platform variant, billing dimension,
currency, and billing unit. Usage-range tiers use ``[tier_start, tier_end)``;
``tier_end=None`` means that the final tier is unbounded. The first-phase
metric is the input token count of one request, and the matched tier prices
the whole request. Volume tiers remain disabled until cumulative periods and
graduated-versus-matched charging are defined.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import json
from typing import Any


TIER_FLAT = "flat"
TIER_USAGE_RANGE = "usage_range"
TIER_VOLUME = "volume"

TIER_METRIC_REQUEST_INPUT_TOKENS = "request_input_tokens"
TIER_CHARGE_MODE_MATCHED_TIER = "matched_tier"
AGGREGATION_PERIOD_REQUEST = "request"

TIER_CONTRACT_SPEC_KEYS = frozenset(
    {
        "tier_metric",
        "tier_charge_mode",
        "aggregation_period",
    }
)
SUPPORTED_TIER_DIMENSIONS = frozenset(
    {
        "text_input",
        "text_output",
        "cache_input",
    }
)

ERROR_MIXED_FLAT_AND_TIERED = "price_table_mixed_flat_and_tiered"
ERROR_INCONSISTENT_DIMENSION = "price_table_inconsistent_dimension"
ERROR_INCONSISTENT_CURRENCY = "price_table_inconsistent_currency"
ERROR_INCONSISTENT_UNIT = "price_table_inconsistent_billing_unit"
ERROR_INCONSISTENT_TIER_TYPE = "price_table_inconsistent_tier_type"
ERROR_INCONSISTENT_METRIC = "price_table_inconsistent_tier_metric"
ERROR_INCONSISTENT_CHARGE_MODE = (
    "price_table_inconsistent_tier_charge_mode"
)
ERROR_INCONSISTENT_AGGREGATION_PERIOD = (
    "price_table_inconsistent_aggregation_period"
)
ERROR_UNSUPPORTED_DIMENSION = "price_table_unsupported_tier_dimension"
ERROR_INVALID_USAGE_RANGE_SPEC = "price_table_invalid_usage_range_spec"
ERROR_TIER_MUST_START_AT_ZERO = "price_table_first_tier_must_start_at_zero"
ERROR_INVALID_BOUNDARY = "price_table_invalid_boundary"
ERROR_DUPLICATE_RANGE = "price_table_duplicate_range"
ERROR_GAP = "price_table_gap"
ERROR_UNBOUNDED_TIER_NOT_LAST = "price_table_unbounded_tier_not_last"
ERROR_VOLUME_UNSUPPORTED = "price_table_volume_unsupported"


class PriceTableValidationError(ValueError):
    """Machine-readable price table contract violation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def usage_range_spec() -> dict[str, str]:
    """Return the first-phase executable usage-range contract."""
    return {
        "tier_metric": TIER_METRIC_REQUEST_INPUT_TOKENS,
        "tier_charge_mode": TIER_CHARGE_MODE_MATCHED_TIER,
        "aggregation_period": AGGREGATION_PERIOD_REQUEST,
    }


def with_usage_range_spec(spec: Mapping[str, Any] | None) -> dict:
    """Add the canonical usage-range contract to display metadata."""
    if spec is not None and not isinstance(spec, Mapping):
        _raise(
            ERROR_INVALID_USAGE_RANGE_SPEC,
            "Tier spec must be a JSON object.",
        )
    return {**dict(spec or {}), **usage_range_spec()}


def validate_price_table(rows: Sequence[Any]) -> None:
    """Validate one flat or tiered table using the shared contract."""
    if not rows:
        return

    tier_types = {_value(row, "tier_type") or TIER_FLAT for row in rows}
    if TIER_FLAT in tier_types and len(tier_types) > 1:
        _raise(
            ERROR_MIXED_FLAT_AND_TIERED,
            "A price table cannot mix flat and tiered rows.",
        )

    _require_consistent(
        rows,
        "dimension",
        ERROR_INCONSISTENT_DIMENSION,
        "All rows must use the same dimension.",
    )
    _require_consistent(
        rows,
        "currency",
        ERROR_INCONSISTENT_CURRENCY,
        "All rows must use the same currency.",
    )
    _require_consistent(
        rows,
        "billing_unit",
        ERROR_INCONSISTENT_UNIT,
        "All rows must use the same billing unit.",
    )
    if len(tier_types) > 1:
        _raise(
            ERROR_INCONSISTENT_TIER_TYPE,
            "All rows must use the same tier type.",
        )

    tier_type = next(iter(tier_types))
    if tier_type == TIER_FLAT:
        _validate_flat_table(rows)
        return
    if tier_type == TIER_VOLUME:
        _raise(
            ERROR_VOLUME_UNSUPPORTED,
            "Volume tiers are disabled until their billing contract is set.",
        )
    if tier_type != TIER_USAGE_RANGE:
        _raise(
            ERROR_INVALID_BOUNDARY,
            f"Unsupported tier type: {tier_type}.",
        )

    _validate_usage_range_table(rows)


def validate_price_table_groups(rows: Sequence[Any]) -> None:
    """Validate independent dimension and variant tables in one catalog."""
    tables: dict[tuple[str, str], list[Any]] = {}
    for row in rows:
        key = (
            str(_value(row, "dimension") or ""),
            price_table_variant_key(row),
        )
        tables.setdefault(key, []).append(row)
    for table in tables.values():
        validate_price_table(table)


def match_usage_range_tier(rows: Sequence[Any], metric_value: Any) -> Any:
    """Return the row containing a request metric under ``[start, end)``."""
    validate_price_table(rows)
    value = _decimal(metric_value)
    if value is None or value < Decimal("0"):
        _raise(
            ERROR_INVALID_BOUNDARY,
            "The tier metric value must be a non-negative number.",
        )

    for row in _sorted_tiers(rows):
        start = _decimal(_value(row, "tier_start"))
        end = _decimal(_value(row, "tier_end"))
        if start is not None and start <= value:
            if end is None or value < end:
                return row
    return None


def price_table_variant_key(row: Any) -> str:
    """Return display metadata that identifies an independent table."""
    return _variant_spec_key(_value(row, "spec"))


def _validate_flat_table(rows: Sequence[Any]) -> None:
    for row in rows:
        if (
            _value(row, "tier_start") is not None
            or _value(row, "tier_end") is not None
        ):
            _raise(
                ERROR_INVALID_BOUNDARY,
                "Flat price rows cannot define tier boundaries.",
            )


def _validate_usage_range_table(rows: Sequence[Any]) -> None:
    dimension = str(_value(rows[0], "dimension") or "")
    if dimension not in SUPPORTED_TIER_DIMENSIONS:
        _raise(
            ERROR_UNSUPPORTED_DIMENSION,
            "Usage-range tiers only support text and cached input prices.",
        )

    specs = [_price_spec(row) for row in rows]
    _require_spec_consistent(
        specs,
        "tier_metric",
        ERROR_INCONSISTENT_METRIC,
        "All rows must use the same tier metric.",
    )
    _require_spec_consistent(
        specs,
        "tier_charge_mode",
        ERROR_INCONSISTENT_CHARGE_MODE,
        "All rows must use the same tier charge mode.",
    )
    _require_spec_consistent(
        specs,
        "aggregation_period",
        ERROR_INCONSISTENT_AGGREGATION_PERIOD,
        "All rows must use the same aggregation period.",
    )
    expected = usage_range_spec()
    if any(
        any(spec.get(key) != value for key, value in expected.items())
        for spec in specs
    ):
        _raise(
            ERROR_INVALID_USAGE_RANGE_SPEC,
            "Usage-range rows must use the request input token contract.",
        )

    tiers = _sorted_tiers(rows)
    first_start = _decimal(_value(tiers[0], "tier_start"))
    if first_start != Decimal("0"):
        _raise(
            ERROR_TIER_MUST_START_AT_ZERO,
            "The first tier must start at zero.",
        )

    seen_ranges = set()
    previous_end = None
    for index, row in enumerate(tiers):
        start = _decimal(_value(row, "tier_start"))
        end = _decimal(_value(row, "tier_end"))
        range_key = (start, end)
        if range_key in seen_ranges:
            _raise(ERROR_DUPLICATE_RANGE, "Tier ranges must be unique.")
        seen_ranges.add(range_key)

        if start is None or start < Decimal("0"):
            _raise(
                ERROR_INVALID_BOUNDARY,
                "Tier boundaries must be non-negative numbers.",
            )
        if end is not None and end <= start:
            _raise(
                ERROR_INVALID_BOUNDARY,
                "A tier end must be greater than its start.",
            )
        if end is None and index != len(tiers) - 1:
            _raise(
                ERROR_UNBOUNDED_TIER_NOT_LAST,
                "Only the final tier may have no upper bound.",
            )
        if index:
            if previous_end is None:
                _raise(
                    ERROR_UNBOUNDED_TIER_NOT_LAST,
                    "Only the final tier may have no upper bound.",
                )
            if start < previous_end:
                _raise(ERROR_INVALID_BOUNDARY, "Tier ranges overlap.")
            if start > previous_end:
                _raise(ERROR_GAP, "Tier ranges must not contain gaps.")
        previous_end = end


def _require_consistent(
    rows: Sequence[Any],
    field: str,
    code: str,
    message: str,
) -> None:
    values = {_value(row, field) for row in rows}
    if len(values) > 1:
        _raise(code, message)


def _require_spec_consistent(
    specs: Sequence[Mapping[str, Any]],
    field: str,
    code: str,
    message: str,
) -> None:
    values = {spec.get(field) for spec in specs}
    if len(values) > 1:
        _raise(code, message)


def _sorted_tiers(rows: Sequence[Any]) -> list[Any]:
    try:
        return sorted(
            rows,
            key=lambda row: (
                _decimal(_value(row, "tier_start")) is None,
                _decimal(_value(row, "tier_start")) or Decimal("0"),
            ),
        )
    except (InvalidOperation, TypeError, ValueError):
        _raise(ERROR_INVALID_BOUNDARY, "Tier boundaries must be numbers.")


def _variant_spec_key(spec: Any) -> str:
    if spec is not None and not isinstance(spec, Mapping):
        return json.dumps(
            {"invalid_spec": spec},
            default=str,
            sort_keys=True,
        )
    values = dict(spec or {})
    for key in TIER_CONTRACT_SPEC_KEYS:
        values.pop(key, None)
    return json.dumps(values, default=str, sort_keys=True)


def _price_spec(row: Any) -> dict:
    value = _value(row, "spec")
    if value is not None and not isinstance(value, Mapping):
        _raise(
            ERROR_INVALID_USAGE_RANGE_SPEC,
            "Tier spec must be a JSON object.",
        )
    return dict(value or {})


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _raise(ERROR_INVALID_BOUNDARY, "Tier boundaries must be numbers.")
    if not result.is_finite():
        _raise(ERROR_INVALID_BOUNDARY, "Tier boundaries must be finite.")
    return result


def _value(row: Any, field: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(field)
    return getattr(row, field, None)


def _raise(code: str, message: str) -> None:
    raise PriceTableValidationError(code, message)
