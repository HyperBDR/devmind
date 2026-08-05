"""Tier-aware price resolution, usage costing, and profit analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import ModelPriceItem
from .price_table_validation import (
    match_usage_range_tier,
    validate_price_table,
)

ZERO = Decimal("0")
ONE = Decimal("1")
SIX_PLACES = Decimal("0.000001")


class TieredPriceNotSupportedError(ValueError):
    """Raised when a flat-only compatibility API receives tiered prices."""


class PriceTierNotFoundError(ValueError):
    """Raised when a valid finite schedule does not cover a metric."""


@dataclass(frozen=True)
class UnitPrices:
    """Resolved unit prices for every supported billing dimension."""

    input_per_million: Decimal
    output_per_million: Decimal
    cache_input_per_million: Decimal
    image_output_per_image: Decimal
    audio_input_per_second: Decimal
    audio_output_per_second: Decimal
    video_input_per_second: Decimal
    video_output_per_second: Decimal


@dataclass(frozen=True)
class PriceTier:
    """One normalized price interval using ``[start, end)`` boundaries."""

    dimension: str
    billing_unit: str
    currency: str
    unit_price: Decimal
    tier_type: str
    tier_start: Decimal | None
    tier_end: Decimal | None
    spec: dict


@dataclass(frozen=True)
class PriceSchedule:
    """Complete normalized price schedule for all billing dimensions."""

    tiers: tuple[PriceTier, ...]

    def for_dimension(self, dimension: str) -> tuple[PriceTier, ...]:
        """Return one dimension ordered by its lower boundary."""
        return tuple(
            sorted(
                (tier for tier in self.tiers if tier.dimension == dimension),
                key=lambda tier: (
                    tier.tier_start if tier.tier_start is not None else ZERO,
                    tier.tier_end is None,
                    tier.tier_end or ZERO,
                ),
            )
        )


@dataclass(frozen=True)
class UsageContext:
    """Actual request usage used for tier selection and billing."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_input_tokens: int = 0
    image_output_count: int = 0
    audio_input_seconds: Decimal | int | str = ZERO
    audio_output_seconds: Decimal | int | str = ZERO
    video_input_seconds: Decimal | int | str = ZERO
    video_output_seconds: Decimal | int | str = ZERO


@dataclass(frozen=True)
class RevenuePolicy:
    """Currency conversion, fee, settlement, and risk inputs.

    Exchange rates express target-currency units per source-currency unit.
    The settlement rate applies to converted cost. Platform, service, and
    tax rates are deducted from converted retail revenue. Risk follows the
    canonical #192 net-yield definition: profit divided by gross revenue.
    """

    target_currency: str
    cost_exchange_rate: Decimal = ONE
    retail_exchange_rate: Decimal = ONE
    platform_fee_rate: Decimal = ZERO
    service_fee_rate: Decimal = ZERO
    tax_rate: Decimal = ZERO
    settlement_rate: Decimal = ONE
    risk_net_yield_rate: Decimal | None = None

    def __post_init__(self) -> None:
        """Reject fee and conversion inputs that cannot produce revenue."""
        if not str(self.target_currency or "").strip():
            raise ValueError("target_currency is required.")
        if self.cost_exchange_rate <= ZERO:
            raise ValueError("cost_exchange_rate must be > 0.")
        if self.retail_exchange_rate <= ZERO:
            raise ValueError("retail_exchange_rate must be > 0.")
        if self.settlement_rate <= ZERO:
            raise ValueError("settlement_rate must be > 0.")
        fee_rates = (
            self.platform_fee_rate,
            self.service_fee_rate,
            self.tax_rate,
        )
        if any(rate < ZERO for rate in fee_rates):
            raise ValueError("fee rates must be >= 0.")
        if sum(fee_rates, ZERO) >= ONE:
            raise ValueError("combined fee rates must be < 1.")


@dataclass(frozen=True)
class TierProfitInterval:
    """Cost and profit metrics for one aligned tier interval."""

    dimension: str
    billing_unit: str
    currency: str
    tier_start: Decimal
    tier_end: Decimal | None
    cost_currency: str
    retail_currency: str
    cost_unit_price: Decimal
    retail_unit_price: Decimal
    converted_cost_unit_price: Decimal
    converted_retail_unit_price: Decimal
    cost: Decimal
    gross_revenue: Decimal
    net_revenue: Decimal
    gross_profit: Decimal
    gross_margin_rate: Decimal
    net_yield_rate: Decimal
    is_risk: bool


@dataclass(frozen=True)
class TierProfitAnalysis:
    """Aligned interval results and lowest-margin risk summary."""

    dimension: str
    currency: str
    billing_unit: str
    intervals: tuple[TierProfitInterval, ...]
    minimum_gross_margin_rate: Decimal | None
    minimum_net_yield_rate: Decimal | None
    minimum_interval: TierProfitInterval | None
    risk_intervals: tuple[TierProfitInterval, ...]


def resolve_price_tier(
    schedule: PriceSchedule,
    *,
    dimension: str,
    usage: Decimal | int | str,
) -> PriceTier:
    """Resolve the tier containing a metric under ``[start, end)`` rules."""
    metric_value = _decimal_or_zero(usage)
    if metric_value < ZERO:
        raise ValueError("usage must be >= 0.")

    tiers = schedule.for_dimension(dimension)
    if not tiers:
        raise ValueError(f"No price tier exists for {dimension}.")
    validate_price_table(tiers)
    flat_tiers = tuple(
        tier for tier in tiers if tier.tier_type == ModelPriceItem.TIER_FLAT
    )
    if flat_tiers:
        if len(flat_tiers) != 1:
            raise ValueError(f"Invalid flat price schedule for {dimension}.")
        return flat_tiers[0]

    tier = match_usage_range_tier(tiers, metric_value)
    if tier is not None:
        return tier
    raise PriceTierNotFoundError(
        f"No {dimension} price tier contains usage {metric_value}."
    )


def resolve_usage_price_tier(
    schedule: PriceSchedule,
    *,
    dimension: str,
    usage: UsageContext,
) -> PriceTier:
    """Resolve a dimension using the request-level tier metric."""
    tiers = schedule.for_dimension(dimension)
    if not tiers:
        raise ValueError(f"No price tier exists for {dimension}.")
    metric_value = ZERO
    if any(tier.tier_type != ModelPriceItem.TIER_FLAT for tier in tiers):
        metric_value = _decimal_or_zero(usage.input_tokens)
    return resolve_price_tier(
        schedule,
        dimension=dimension,
        usage=metric_value,
    )


def resolve_usage_unit_prices(
    schedule: PriceSchedule,
    usage: UsageContext,
) -> UnitPrices:
    """Resolve scalar unit prices for one explicit usage context."""

    def unit_price(dimension: str) -> Decimal:
        if not schedule.for_dimension(dimension):
            return ZERO
        tier = resolve_usage_price_tier(
            schedule,
            dimension=dimension,
            usage=usage,
        )
        return tier.unit_price

    return UnitPrices(
        input_per_million=unit_price(ModelPriceItem.DIMENSION_TEXT_INPUT),
        output_per_million=unit_price(ModelPriceItem.DIMENSION_TEXT_OUTPUT),
        cache_input_per_million=unit_price(
            ModelPriceItem.DIMENSION_CACHE_INPUT
        ),
        image_output_per_image=unit_price(
            ModelPriceItem.DIMENSION_IMAGE_OUTPUT
        ),
        audio_input_per_second=unit_price(
            ModelPriceItem.DIMENSION_AUDIO_INPUT
        ),
        audio_output_per_second=unit_price(
            ModelPriceItem.DIMENSION_AUDIO_OUTPUT
        ),
        video_input_per_second=unit_price(
            ModelPriceItem.DIMENSION_VIDEO_INPUT
        ),
        video_output_per_second=unit_price(
            ModelPriceItem.DIMENSION_VIDEO_OUTPUT
        ),
    )


def calculate_price_schedule_usage_cost(
    schedule: PriceSchedule,
    usage: UsageContext,
) -> Decimal:
    """Calculate actual usage cost from a complete price schedule."""
    total = ZERO
    for dimension, amount in _usage_amounts(usage).items():
        if amount == ZERO or not schedule.for_dimension(dimension):
            continue
        tier = resolve_usage_price_tier(
            schedule,
            dimension=dimension,
            usage=usage,
        )
        total += _billing_quantity(amount, tier.billing_unit) * tier.unit_price
    return total.quantize(SIX_PLACES)


def analyze_tier_profit(
    cost_schedule: PriceSchedule,
    retail_schedule: PriceSchedule,
    *,
    dimension: str,
    policy: RevenuePolicy,
) -> TierProfitAnalysis:
    """Align cost and retail boundaries and calculate interval profits."""
    cost_tiers = cost_schedule.for_dimension(dimension)
    retail_tiers = retail_schedule.for_dimension(dimension)
    if not cost_tiers or not retail_tiers:
        raise ValueError(f"Both schedules require {dimension} prices.")

    intervals = []
    boundaries = _aligned_tier_boundaries(cost_tiers, retail_tiers)
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] if index + 1 < len(boundaries) else None
        if not _both_schedules_cover_usage(
            cost_schedule,
            retail_schedule,
            dimension=dimension,
            usage=start,
        ):
            continue
        cost_tier = resolve_price_tier(
            cost_schedule,
            dimension=dimension,
            usage=start,
        )
        retail_tier = resolve_price_tier(
            retail_schedule,
            dimension=dimension,
            usage=start,
        )
        if cost_tier.billing_unit != retail_tier.billing_unit:
            raise ValueError("Cost and retail billing units must match.")
        intervals.append(
            _tier_profit_interval(
                dimension=dimension,
                start=start,
                end=end,
                cost_tier=cost_tier,
                retail_tier=retail_tier,
                policy=policy,
            )
        )

    interval_rows = tuple(intervals)
    minimum = min(
        interval_rows,
        key=lambda row: row.gross_margin_rate,
        default=None,
    )
    minimum_yield = min(
        (row.net_yield_rate for row in interval_rows),
        default=None,
    )
    return TierProfitAnalysis(
        dimension=dimension,
        currency=_normalize_currency(policy.target_currency),
        billing_unit=(interval_rows[0].billing_unit if interval_rows else ""),
        intervals=interval_rows,
        minimum_gross_margin_rate=(
            minimum.gross_margin_rate if minimum is not None else None
        ),
        minimum_net_yield_rate=minimum_yield,
        minimum_interval=minimum,
        risk_intervals=tuple(row for row in interval_rows if row.is_risk),
    )


def _usage_amounts(usage: UsageContext) -> dict[str, Decimal]:
    """Map and validate actual usage by pricing dimension."""
    amounts = {
        ModelPriceItem.DIMENSION_TEXT_INPUT: _decimal_or_zero(
            usage.input_tokens
        ),
        ModelPriceItem.DIMENSION_TEXT_OUTPUT: _decimal_or_zero(
            usage.output_tokens
        ),
        ModelPriceItem.DIMENSION_CACHE_INPUT: _decimal_or_zero(
            usage.cache_input_tokens
        ),
        ModelPriceItem.DIMENSION_IMAGE_OUTPUT: _decimal_or_zero(
            usage.image_output_count
        ),
        ModelPriceItem.DIMENSION_AUDIO_INPUT: _decimal_or_zero(
            usage.audio_input_seconds
        ),
        ModelPriceItem.DIMENSION_AUDIO_OUTPUT: _decimal_or_zero(
            usage.audio_output_seconds
        ),
        ModelPriceItem.DIMENSION_VIDEO_INPUT: _decimal_or_zero(
            usage.video_input_seconds
        ),
        ModelPriceItem.DIMENSION_VIDEO_OUTPUT: _decimal_or_zero(
            usage.video_output_seconds
        ),
    }
    if any(amount < ZERO for amount in amounts.values()):
        raise ValueError("usage values must be >= 0.")
    return amounts


def _billing_quantity(amount: Decimal, billing_unit: str) -> Decimal:
    """Convert raw usage to the quantity represented by one unit price."""
    if billing_unit == ModelPriceItem.UNIT_PER_1M_TOKENS:
        return amount / Decimal("1000000")
    if billing_unit in {
        ModelPriceItem.UNIT_PER_IMAGE,
        ModelPriceItem.UNIT_PER_SECOND,
        ModelPriceItem.UNIT_PER_GENERATION,
    }:
        return amount
    raise ValueError(f"Unsupported billing unit: {billing_unit}.")


def _aligned_tier_boundaries(
    cost_tiers: tuple[PriceTier, ...],
    retail_tiers: tuple[PriceTier, ...],
) -> tuple[Decimal, ...]:
    """Return the sorted union of every finite schedule boundary."""
    boundaries = {ZERO}
    for tier in cost_tiers + retail_tiers:
        if tier.tier_start is not None:
            boundaries.add(tier.tier_start)
        if tier.tier_end is not None:
            boundaries.add(tier.tier_end)
    return tuple(sorted(boundaries))


def _both_schedules_cover_usage(
    cost_schedule: PriceSchedule,
    retail_schedule: PriceSchedule,
    *,
    dimension: str,
    usage: Decimal,
) -> bool:
    """Return whether both schedules cover an aligned boundary."""
    try:
        resolve_price_tier(
            cost_schedule,
            dimension=dimension,
            usage=usage,
        )
        resolve_price_tier(
            retail_schedule,
            dimension=dimension,
            usage=usage,
        )
    except PriceTierNotFoundError:
        return False
    return True


def _tier_profit_interval(
    *,
    dimension: str,
    start: Decimal,
    end: Decimal | None,
    cost_tier: PriceTier,
    retail_tier: PriceTier,
    policy: RevenuePolicy,
) -> TierProfitInterval:
    """Calculate canonical resale metrics for one aligned interval."""
    converted_cost = cost_tier.unit_price * policy.cost_exchange_rate
    converted_retail = retail_tier.unit_price * policy.retail_exchange_rate
    cost = converted_cost * policy.settlement_rate
    net_factor = (
        ONE
        - policy.platform_fee_rate
        - policy.service_fee_rate
        - policy.tax_rate
    )
    net_revenue = converted_retail * net_factor
    gross_profit = net_revenue - cost
    gross_margin_rate = _safe_ratio(gross_profit, net_revenue)
    net_yield_rate = _safe_ratio(gross_profit, converted_retail)
    margin_rate = gross_margin_rate.quantize(SIX_PLACES)
    yield_rate = net_yield_rate.quantize(SIX_PLACES)
    risk_threshold = policy.risk_net_yield_rate
    return TierProfitInterval(
        dimension=dimension,
        billing_unit=cost_tier.billing_unit,
        currency=_normalize_currency(policy.target_currency),
        tier_start=start,
        tier_end=end,
        cost_currency=_normalize_currency(cost_tier.currency),
        retail_currency=_normalize_currency(retail_tier.currency),
        cost_unit_price=cost_tier.unit_price,
        retail_unit_price=retail_tier.unit_price,
        converted_cost_unit_price=converted_cost.quantize(SIX_PLACES),
        converted_retail_unit_price=converted_retail.quantize(SIX_PLACES),
        cost=cost.quantize(SIX_PLACES),
        gross_revenue=converted_retail.quantize(SIX_PLACES),
        net_revenue=net_revenue.quantize(SIX_PLACES),
        gross_profit=gross_profit.quantize(SIX_PLACES),
        gross_margin_rate=margin_rate,
        net_yield_rate=yield_rate,
        is_risk=(
            risk_threshold is not None and net_yield_rate < risk_threshold
        ),
    )


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return a deterministic ratio for a zero denominator."""
    if denominator:
        return numerator / denominator
    if numerator < ZERO:
        return Decimal("-1")
    return ZERO


def _decimal_or_zero(value) -> Decimal:
    """Return a Decimal value, falling back to zero."""
    if value is None:
        return ZERO
    return Decimal(str(value))


def _normalize_currency(value: str | None) -> str:
    """Normalize currency codes in analysis output."""
    return str(value or "").strip().upper()
