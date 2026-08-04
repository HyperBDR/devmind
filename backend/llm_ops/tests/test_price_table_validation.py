from decimal import Decimal
from unittest import TestCase

from llm_ops.price_table_validation import (
    AGGREGATION_PERIOD_REQUEST,
    ERROR_DUPLICATE_RANGE,
    ERROR_GAP,
    ERROR_INCONSISTENT_CURRENCY,
    ERROR_INCONSISTENT_DIMENSION,
    ERROR_INCONSISTENT_METRIC,
    ERROR_INCONSISTENT_TIER_TYPE,
    ERROR_INCONSISTENT_UNIT,
    ERROR_INVALID_BOUNDARY,
    ERROR_MIXED_FLAT_AND_TIERED,
    ERROR_TIER_MUST_START_AT_ZERO,
    ERROR_UNBOUNDED_TIER_NOT_LAST,
    ERROR_VOLUME_UNSUPPORTED,
    TIER_CHARGE_MODE_MATCHED_TIER,
    TIER_METRIC_REQUEST_INPUT_TOKENS,
    PriceTableValidationError,
    match_usage_range_tier,
    usage_range_spec,
    validate_price_table,
)


def price_row(
    start,
    end,
    *,
    dimension="text_input",
    currency="USD",
    billing_unit="per_1m_tokens",
    tier_type="usage_range",
    spec=None,
):
    """Build one normalized price row for contract tests."""
    return {
        "dimension": dimension,
        "currency": currency,
        "billing_unit": billing_unit,
        "tier_type": tier_type,
        "tier_start": None if start is None else Decimal(str(start)),
        "tier_end": None if end is None else Decimal(str(end)),
        "spec": usage_range_spec() if spec is None else spec,
    }


class PriceTableValidationTests(TestCase):
    def assert_error_code(self, expected_code, rows):
        """Assert deterministic validation failure codes."""
        with self.assertRaises(PriceTableValidationError) as raised:
            validate_price_table(rows)
        self.assertEqual(raised.exception.code, expected_code)

    def test_usage_range_contract_is_explicit(self):
        self.assertEqual(
            usage_range_spec(),
            {
                "tier_metric": TIER_METRIC_REQUEST_INPUT_TOKENS,
                "tier_charge_mode": TIER_CHARGE_MODE_MATCHED_TIER,
                "aggregation_period": AGGREGATION_PERIOD_REQUEST,
            },
        )

    def test_matches_zero_exact_boundary_and_unbounded_last_tier(self):
        rows = [
            price_row("0", "1000000"),
            price_row("1000000", None),
        ]

        first = match_usage_range_tier(rows, Decimal("0"))
        boundary = match_usage_range_tier(rows, Decimal("1000000"))
        unbounded = match_usage_range_tier(rows, Decimal("9000000"))

        self.assertEqual(first["tier_start"], Decimal("0"))
        self.assertEqual(boundary["tier_start"], Decimal("1000000"))
        self.assertEqual(unbounded["tier_start"], Decimal("1000000"))

    def test_same_validator_accepts_all_price_surfaces(self):
        tables = (
            [
                {
                    **price_row("0", None),
                    "provider": "openai",
                    "source": "official",
                }
            ],
            [
                {
                    **price_row("0", None),
                    "channel": "supplier-a",
                }
            ],
            [
                {
                    **price_row("0", None),
                    "platform": "agione",
                    "listing": "gpt-5",
                }
            ],
        )

        for table in tables:
            with self.subTest(table=table):
                validate_price_table(table)

    def test_rejects_mixed_flat_and_tiered_rows(self):
        rows = [
            price_row(None, None, tier_type="flat", spec={}),
            price_row("0", None),
        ]

        self.assert_error_code(ERROR_MIXED_FLAT_AND_TIERED, rows)

    def test_rejects_first_tier_that_does_not_start_at_zero(self):
        self.assert_error_code(
            ERROR_TIER_MUST_START_AT_ZERO,
            [price_row("1", None)],
        )

    def test_rejects_inverted_range(self):
        self.assert_error_code(
            ERROR_INVALID_BOUNDARY,
            [price_row("0", "0")],
        )

    def test_rejects_duplicate_range(self):
        rows = [price_row("0", "10"), price_row("0", "10")]

        self.assert_error_code(ERROR_DUPLICATE_RANGE, rows)

    def test_rejects_overlapping_range(self):
        rows = [price_row("0", "10"), price_row("9", None)]

        self.assert_error_code(ERROR_INVALID_BOUNDARY, rows)

    def test_rejects_gap_between_ranges(self):
        rows = [price_row("0", "10"), price_row("11", None)]

        self.assert_error_code(ERROR_GAP, rows)

    def test_rejects_unbounded_tier_before_last_tier(self):
        rows = [price_row("0", None), price_row("10", None)]

        self.assert_error_code(ERROR_UNBOUNDED_TIER_NOT_LAST, rows)

    def test_rejects_inconsistent_dimension(self):
        rows = [
            price_row("0", "10"),
            price_row("10", None, dimension="text_output"),
        ]

        self.assert_error_code(ERROR_INCONSISTENT_DIMENSION, rows)

    def test_rejects_inconsistent_currency(self):
        rows = [
            price_row("0", "10"),
            price_row("10", None, currency="CNY"),
        ]

        self.assert_error_code(ERROR_INCONSISTENT_CURRENCY, rows)

    def test_rejects_inconsistent_billing_unit(self):
        rows = [
            price_row("0", "10"),
            price_row("10", None, billing_unit="per_generation"),
        ]

        self.assert_error_code(ERROR_INCONSISTENT_UNIT, rows)

    def test_rejects_inconsistent_tier_type(self):
        rows = [
            price_row("0", "10"),
            price_row("10", None, tier_type="volume"),
        ]

        self.assert_error_code(ERROR_INCONSISTENT_TIER_TYPE, rows)

    def test_rejects_inconsistent_metric(self):
        other_spec = usage_range_spec()
        other_spec["tier_metric"] = "monthly_tokens"
        rows = [
            price_row("0", "10"),
            price_row("10", None, spec=other_spec),
        ]

        self.assert_error_code(ERROR_INCONSISTENT_METRIC, rows)

    def test_rejects_volume_until_business_contract_is_defined(self):
        rows = [price_row("0", None, tier_type="volume")]

        self.assert_error_code(ERROR_VOLUME_UNSUPPORTED, rows)
