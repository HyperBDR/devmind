from datetime import datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from llm_ops.models import ModelPriceItem
from llm_ops.price_table_validation import (
    PriceTableValidationError,
    validate_price_table_groups,
    usage_range_spec,
)
from llm_ops.services import (
    _merge_flat_fallback_tiers,
    derive_resale_pricing_format,
)
from llm_ops.tier_pricing import (
    PriceSchedule,
    PriceTier,
    PriceTierNotFoundError,
    RevenuePolicy,
    UsageContext,
    analyze_tier_profit,
    calculate_price_schedule_usage_cost,
    resolve_price_tier,
    resolve_usage_unit_prices,
)


class TieredPricingKernelTests(SimpleTestCase):
    def test_flat_fallback_becomes_valid_usage_range_tail(self):
        tiers = _merge_flat_fallback_tiers(
            [
                self._tier("1", "0", "128000"),
                self._tier(
                    "2",
                    None,
                    None,
                    tier_type=ModelPriceItem.TIER_FLAT,
                ),
            ]
        )

        validate_price_table_groups(tiers)

        self.assertEqual(
            [
                (tier.tier_type, tier.tier_start, tier.tier_end)
                for tier in tiers
            ],
            [
                (
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("0"),
                    Decimal("128000"),
                ),
                (
                    ModelPriceItem.TIER_USAGE_RANGE,
                    Decimal("128000"),
                    None,
                ),
            ],
        )
        self.assertEqual(
            [tier.spec for tier in tiers],
            [usage_range_spec(), usage_range_spec()],
        )

    def test_resolve_price_tier_uses_half_open_boundaries(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier("1", "0", "100"),
                self._tier("2", "100", None),
            )
        )

        self.assertEqual(
            resolve_price_tier(
                schedule,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                usage=Decimal("99.999999"),
            ).unit_price,
            Decimal("1"),
        )
        self.assertEqual(
            resolve_price_tier(
                schedule,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                usage=Decimal("100"),
            ).unit_price,
            Decimal("2"),
        )

    def test_usage_context_selects_all_tiers_by_request_input_tokens(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier(
                    "1",
                    "0",
                    "100",
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                ),
                self._tier(
                    "2",
                    "100",
                    None,
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                ),
            )
        )

        prices = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=100, output_tokens=1),
        )

        self.assertEqual(prices.output_per_million, Decimal("2"))

    def test_calculate_schedule_cost_supports_flat_and_cached_tiers(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier(
                    "2",
                    None,
                    None,
                    dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                    tier_type=ModelPriceItem.TIER_FLAT,
                ),
                self._tier(
                    "0.5",
                    "0",
                    "1000",
                    dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
                ),
                self._tier(
                    "1",
                    "1000",
                    None,
                    dimension=ModelPriceItem.DIMENSION_CACHE_INPUT,
                ),
            )
        )

        cost = calculate_price_schedule_usage_cost(
            schedule,
            UsageContext(
                input_tokens=1_000_000,
                cache_input_tokens=1000,
            ),
        )

        self.assertEqual(cost, Decimal("2.001000"))

    def test_profit_analysis_aligns_all_boundaries_and_flags_risk(self):
        cost_schedule = PriceSchedule(
            tiers=(
                self._tier("2", "0", "100"),
                self._tier("4", "100", None),
            )
        )
        retail_schedule = PriceSchedule(
            tiers=(
                self._tier("10", "0", "50"),
                self._tier("8", "50", "200"),
                self._tier("5", "200", None),
            )
        )
        policy = RevenuePolicy(
            target_currency="CNY",
            cost_exchange_rate=Decimal("2"),
            retail_exchange_rate=Decimal("1"),
            platform_fee_rate=Decimal("0.10"),
            service_fee_rate=Decimal("0.05"),
            tax_rate=Decimal("0.05"),
            settlement_rate=Decimal("0.90"),
            risk_net_yield_rate=Decimal("0"),
        )

        analysis = analyze_tier_profit(
            cost_schedule,
            retail_schedule,
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            policy=policy,
        )

        self.assertEqual(
            [(row.tier_start, row.tier_end) for row in analysis.intervals],
            [
                (Decimal("0"), Decimal("50")),
                (Decimal("50"), Decimal("100")),
                (Decimal("100"), Decimal("200")),
                (Decimal("200"), None),
            ],
        )
        first = analysis.intervals[0]
        self.assertEqual(first.converted_cost_unit_price, Decimal("4.000000"))
        self.assertEqual(first.cost, Decimal("3.600000"))
        self.assertEqual(first.net_revenue, Decimal("8.000000"))
        self.assertEqual(first.gross_profit, Decimal("4.400000"))
        self.assertEqual(first.gross_margin_rate, Decimal("0.550000"))
        self.assertEqual(
            analysis.minimum_gross_margin_rate,
            Decimal("-0.800000"),
        )
        self.assertEqual(
            analysis.minimum_net_yield_rate,
            Decimal("-0.640000"),
        )
        self.assertEqual(
            [
                (row.tier_start, row.tier_end)
                for row in analysis.risk_intervals
            ],
            [
                (Decimal("100"), Decimal("200")),
                (Decimal("200"), None),
            ],
        )

    def test_profit_analysis_does_not_hide_invalid_price_tables(self):
        invalid_cost = PriceSchedule(
            tiers=(
                self._tier("1", "0", "10"),
                self._tier("2", "20", None),
            )
        )
        retail = PriceSchedule(tiers=(self._tier("3", "0", None),))

        with self.assertRaises(PriceTableValidationError):
            analyze_tier_profit(
                invalid_cost,
                retail,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                policy=RevenuePolicy(target_currency="USD"),
            )

    def test_profit_risk_uses_unrounded_net_yield(self):
        analysis = analyze_tier_profit(
            PriceSchedule(tiers=(self._tier("9.000004", "0", None),)),
            PriceSchedule(tiers=(self._tier("10", "0", None),)),
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            policy=RevenuePolicy(
                target_currency="USD",
                risk_net_yield_rate=Decimal("0.1"),
            ),
        )

        interval = analysis.intervals[0]
        self.assertEqual(interval.net_yield_rate, Decimal("0.100000"))
        self.assertTrue(interval.is_risk)

    def test_usage_above_top_tier_bills_at_top_tier_rate(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier("1", "0", "1000"),
                self._tier("2", "1000", "5000"),
                self._tier("4", "5000", None),
            )
        )

        prices = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=10_000_000, output_tokens=1),
        )

        self.assertEqual(prices.input_per_million, Decimal("4"))

    def test_usage_above_bounded_top_tier_bills_at_top_tier_rate(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier("1", "0", "1000"),
                self._tier("2", "1000", "5000"),
                self._tier("4", "5000", "10000"),
            )
        )

        prices = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=10_000_000, output_tokens=1),
        )

        self.assertEqual(prices.input_per_million, Decimal("4"))
        with self.assertRaises(PriceTierNotFoundError):
            resolve_price_tier(
                schedule,
                dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
                usage=Decimal("10_000_000"),
            )

    def test_resolves_multi_metric_glm_price_conditions(self):
        def tier(dimension, price, start, end, conditions):
            return PriceTier(
                dimension=dimension,
                billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
                currency="CNY",
                unit_price=Decimal(price),
                tier_type=ModelPriceItem.TIER_USAGE_RANGE,
                tier_start=Decimal(start),
                tier_end=Decimal(end) if end is not None else None,
                spec={
                    **usage_range_spec(),
                    "usage_conditions": conditions,
                },
            )

        rules = (
            (
                "2",
                "8",
                "0",
                "32000",
                {
                    "input_tokens": {"start": "0", "end": "32000"},
                    "output_tokens": {"start": "0", "end": "200"},
                },
            ),
            (
                "3",
                "14",
                "0",
                "32000",
                {
                    "input_tokens": {"start": "0", "end": "32000"},
                    "output_tokens": {"start": "200", "end": None},
                },
            ),
            (
                "4",
                "16",
                "32000",
                "200000",
                {
                    "input_tokens": {"start": "32000", "end": "200000"},
                },
            ),
        )
        tiers = []
        for input_price, output_price, start, end, conditions in rules:
            tiers.extend(
                [
                    tier(
                        ModelPriceItem.DIMENSION_TEXT_INPUT,
                        input_price,
                        start,
                        end,
                        conditions,
                    ),
                    tier(
                        ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                        output_price,
                        start,
                        end,
                        conditions,
                    ),
                ]
            )
        schedule = PriceSchedule(tiers=tuple(tiers))

        short_output = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=10_000, output_tokens=100),
        )
        long_output = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=10_000, output_tokens=300),
        )
        long_input = resolve_usage_unit_prices(
            schedule,
            UsageContext(input_tokens=50_000, output_tokens=100),
        )

        self.assertEqual(short_output.input_per_million, Decimal("2"))
        self.assertEqual(short_output.output_per_million, Decimal("8"))
        self.assertEqual(long_output.input_per_million, Decimal("3"))
        self.assertEqual(long_output.output_per_million, Decimal("14"))
        self.assertEqual(long_input.input_per_million, Decimal("4"))
        self.assertEqual(long_input.output_per_million, Decimal("16"))

    def test_derive_resale_pricing_format_classifies_flat_schedule(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier(
                    "1",
                    None,
                    None,
                    tier_type=ModelPriceItem.TIER_FLAT,
                ),
                self._tier(
                    "2",
                    None,
                    None,
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                    tier_type=ModelPriceItem.TIER_FLAT,
                ),
            )
        )

        self.assertEqual(derive_resale_pricing_format(schedule), "flat")

    def test_derive_resale_pricing_format_classifies_usage_range_schedule(
        self,
    ):
        schedule = PriceSchedule(
            tiers=(
                self._tier("1", "0", None),
                self._tier(
                    "2",
                    "0",
                    None,
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                ),
            )
        )

        self.assertEqual(
            derive_resale_pricing_format(schedule),
            "usage_range",
        )

    def test_derive_resale_pricing_format_classifies_mixed_schedule(self):
        schedule = PriceSchedule(
            tiers=(
                self._tier("1", "0", None),
                self._tier(
                    "2",
                    None,
                    None,
                    dimension=ModelPriceItem.DIMENSION_TEXT_OUTPUT,
                    tier_type=ModelPriceItem.TIER_FLAT,
                ),
            )
        )

        self.assertEqual(derive_resale_pricing_format(schedule), "mixed")

    def test_conditional_fallback_considers_unconditional_highest_price(self):
        schedule = PriceSchedule(
            tiers=(
                self._flat_tier(
                    "2",
                    {
                        "time_windows": [
                            {
                                "weekdays": list(range(7)),
                                "start": "08:00",
                                "end": "20:00",
                            }
                        ]
                    },
                ),
                self._flat_tier("5", {}),
            )
        )

        with self.assertLogs("llm_ops.tier_pricing", level="WARNING"):
            prices = resolve_usage_unit_prices(schedule, UsageContext())

        self.assertEqual(prices.input_per_million, Decimal("5"))

    def test_overlapping_time_rules_warn_and_choose_highest_price(self):
        window = {
            "time_windows": [
                {
                    "weekdays": list(range(7)),
                    "start": "08:00",
                    "end": "20:00",
                }
            ],
            "timezone": "UTC",
        }
        schedule = PriceSchedule(
            tiers=(
                self._flat_tier("1", window),
                self._flat_tier("3", window),
            )
        )
        usage = UsageContext(
            input_tokens=1_000_000,
            occurred_at=datetime(
                2026,
                8,
                18,
                12,
                tzinfo=timezone.utc,
            ),
        )

        with self.assertLogs("llm_ops.tier_pricing", level="WARNING"):
            prices = resolve_usage_unit_prices(schedule, usage)

        self.assertEqual(prices.input_per_million, Decimal("3"))

    @staticmethod
    def _flat_tier(unit_price, spec):
        return PriceTier(
            dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal(unit_price),
            tier_type=ModelPriceItem.TIER_FLAT,
            tier_start=None,
            tier_end=None,
            spec=spec,
        )

    @staticmethod
    def _tier(
        unit_price,
        tier_start,
        tier_end,
        *,
        dimension=ModelPriceItem.DIMENSION_TEXT_INPUT,
        tier_type=ModelPriceItem.TIER_USAGE_RANGE,
    ):
        return PriceTier(
            dimension=dimension,
            billing_unit=ModelPriceItem.UNIT_PER_1M_TOKENS,
            currency="USD",
            unit_price=Decimal(unit_price),
            tier_type=tier_type,
            tier_start=(
                Decimal(tier_start) if tier_start is not None else None
            ),
            tier_end=Decimal(tier_end) if tier_end is not None else None,
            spec=(
                usage_range_spec()
                if tier_type == ModelPriceItem.TIER_USAGE_RANGE
                else {}
            ),
        )
