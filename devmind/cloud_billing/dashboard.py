"""Dashboard aggregation helpers for cloud billing overview pages."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import hashlib
import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import BillingData, CloudProvider
from .serializers import get_balance_support_info

LLM_PROVIDER_TYPES = {'zhipu'}
CNY_RATE = Decimal('7.15')
EXCHANGE_RATE_API_URL = 'https://v6.exchangerate-api.com/v6/{api_key}/latest/USD'
EXCHANGE_RATE_SOURCE_URL = 'https://www.exchangerate-api.com/'
EXCHANGE_RATE_CACHE_PREFIX = 'cloud_billing:exchange_rate'
EXCHANGE_RATE_CACHE_TTL = 60 * 60 * 24
RECENT_BURN_WINDOW_DAYS = 30
PROVIDER_PAYMENT_TYPES = {
    'aws': 'postpaid',
    'azure': 'postpaid',
    'huawei-intl': 'postpaid',
}

logger = logging.getLogger(__name__)


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _resolve_dashboard_timezone(timezone_name: str | None):
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            logger.warning(
                'Invalid dashboard timezone %s, falling back to current timezone.',
                timezone_name,
            )
    return timezone.get_current_timezone()


def _cache_get_safely(cache_key: str):
    try:
        return cache.get(cache_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning('Failed to read exchange rate cache: %s', exc)
        return None


def _cache_set_safely(cache_key: str, value: dict[str, object], timeout: int) -> None:
    try:
        cache.set(cache_key, value, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning('Failed to write exchange rate cache: %s', exc)


def _payment_type_for_provider(provider, balance_supported: bool) -> str:
    provider_type = str(getattr(provider, 'provider_type', '') or '').strip().lower()
    if provider_type in PROVIDER_PAYMENT_TYPES:
        return PROVIDER_PAYMENT_TYPES[provider_type]

    config = provider.config or {}
    payment_type = str(config.get('payment_type') or '').strip().lower()
    if payment_type in {'prepaid', 'postpaid'}:
        return payment_type
    return 'prepaid' if balance_supported else 'postpaid'


def _credit_limit_for_provider(provider) -> float | None:
    config = provider.config or {}
    for key in ('credit_limit', 'quota', 'budget'):
        value = config.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_account_funds(provider, billing, payment_type: str) -> dict[str, object]:
    provider_type = str(getattr(provider, 'provider_type', '') or '').strip().lower()
    account_currency = str(
        getattr(provider, 'balance_currency', '')
        or getattr(billing, 'currency', '')
        or 'USD'
    ).upper()
    raw_balance = _to_float(getattr(provider, 'balance', None))
    configured_credit_limit = _credit_limit_for_provider(provider)

    balance = raw_balance
    balance_currency = account_currency if raw_balance > 0 else ''
    credit_limit = configured_credit_limit
    credit_limit_currency = account_currency if configured_credit_limit else ''
    uses_credit_limit_days = False

    if provider_type == 'huawei-intl' and payment_type == 'postpaid':
        credit_limit = raw_balance if raw_balance > 0 else configured_credit_limit
        credit_limit_currency = account_currency if credit_limit else ''
        balance = 0.0
        balance_currency = ''
        uses_credit_limit_days = False

    return {
        'balance': round(balance, 2),
        'balance_currency': balance_currency,
        'credit_limit': round(credit_limit, 2) if credit_limit else None,
        'credit_limit_currency': credit_limit_currency,
        'display_funds': round(credit_limit or balance, 2),
        'display_funds_currency': credit_limit_currency or balance_currency,
        'uses_credit_limit_days': uses_credit_limit_days,
    }


def _hourly_cost_value(billing: BillingData) -> float:
    if billing.hourly_cost is not None:
        return _to_float(billing.hourly_cost)
    return 0.0


def _total_cost_value(billing: BillingData) -> float:
    if getattr(billing, 'total_cost', None) is not None:
        return _to_float(billing.total_cost)
    return 0.0


def _recent_spend_from_snapshots(account_rows, now) -> float:
    if not account_rows:
        return 0.0

    current_period = now.strftime('%Y-%m')
    recent_window_start = (now - timedelta(days=RECENT_BURN_WINDOW_DAYS - 1)).date()
    row_periods = {getattr(row, 'period', None) for row in account_rows if getattr(row, 'period', None)}

    # When the 30-day window starts on the first day of the current month,
    # the latest monthly cumulative snapshot is the best approximation of
    # the recent 30-day spend even if early-hour rows are missing.
    if (
        recent_window_start.day == 1
        and row_periods == {current_period}
    ):
        return max(_total_cost_value(row) for row in account_rows)

    spend = 0.0
    rows_by_period = defaultdict(list)
    for row in account_rows:
        row_period = getattr(row, 'period', None)
        if not row_period:
            continue
        rows_by_period[row_period].append(row)

    for period_rows in rows_by_period.values():
        first_row = period_rows[0]
        last_row = period_rows[-1]
        first_total = _total_cost_value(first_row)
        first_increment = _hourly_cost_value(first_row)
        baseline_total = max(first_total - first_increment, 0.0)
        latest_total = _total_cost_value(last_row)
        spend += max(latest_total - baseline_total, 0.0)

    return spend


def _recent_collected_days_from_snapshots(account_rows, now, local_tz) -> int:
    if not account_rows:
        return 0

    recent_window_start = (now - timedelta(days=RECENT_BURN_WINDOW_DAYS - 1)).date()
    today = now.date()
    collected_days = set()

    for row in account_rows:
        collected_at = getattr(row, 'collected_at', None)
        if collected_at is None:
            continue
        row_day = collected_at.astimezone(local_tz).date()
        if recent_window_start <= row_day <= today:
            collected_days.add(row_day)

    return len(collected_days)


def _daily_rows_for_current_month(local_tz):
    now = timezone.now().astimezone(local_tz)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = BillingData.objects.select_related('provider').filter(
        provider__is_active=True,
        collected_at__gte=month_start.astimezone(dt_timezone.utc),
    ).order_by('provider_id', 'account_id', 'period', 'hour', 'collected_at')
    return now, month_start, list(rows)


def _billing_rows_for_current_year(local_tz):
    now = timezone.now().astimezone(local_tz)
    year_start = now.replace(
        month=1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    rows = BillingData.objects.select_related('provider').filter(
        provider__is_active=True,
        collected_at__gte=year_start.astimezone(dt_timezone.utc),
    ).order_by('provider_id', 'account_id', 'period', 'hour', 'collected_at')
    return now, year_start, list(rows)


def _billing_rows_for_recent_days(local_tz, days: int = 30):
    now = timezone.now().astimezone(local_tz)
    window_start = (now - timedelta(days=max(days - 1, 0))).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    rows = BillingData.objects.select_related('provider').filter(
        provider__is_active=True,
        collected_at__gte=window_start.astimezone(dt_timezone.utc),
    ).order_by('provider_id', 'account_id', 'period', 'hour', 'collected_at')
    return now, window_start, list(rows)


def _latest_billings():
    providers = CloudProvider.objects.filter(is_active=True).order_by(
        'display_name',
        'id',
    )
    billings = BillingData.objects.select_related('provider').order_by(
        'provider_id',
        'account_id',
        '-collected_at',
        '-period',
        '-hour',
    )
    providers = providers.prefetch_related(
        Prefetch('billing_data', queryset=billings, to_attr='ordered_billing_data')
    )

    latest = []
    for provider in providers:
        seen_accounts = set()
        for billing in getattr(provider, 'ordered_billing_data', []):
            account_key = billing.account_id or ''
            if account_key in seen_accounts:
                continue
            latest.append(billing)
            seen_accounts.add(account_key)
    return latest


def _build_summary(latest_billings, daily_rows, local_tz, now, usd_to_cny_rate: float):
    collected_dates = set()

    trend_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    peak_cost = 0.0
    peak_date = now.date().isoformat()
    for row in daily_rows:
        local_collected_at = row.collected_at.astimezone(local_tz)
        if local_collected_at.date() <= now.date():
            collected_dates.add(local_collected_at.date())
        date_key = local_collected_at.strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        trend_map[date_key][currency_key] += _hourly_cost_value(row)

    days_total = monthrange(now.year, now.month)[1]
    consumed_total = 0.0
    trend = []
    for index in range(1, days_total + 1):
        date_key = f'{now.month:02d}-{index:02d}'
        cny_value = round(trend_map[date_key]['cny'], 2)
        usd_value = round(trend_map[date_key]['usd'], 2)
        total = round(cny_value + usd_value * usd_to_cny_rate, 2)
        row_date = now.date().replace(day=index)
        if row_date <= now.date():
            consumed_total += total
        if row_date <= now.date() and total > peak_cost:
            peak_cost = total
            peak_date = f'{now.year}-{date_key}'
        trend.append(
            {
                'date': date_key,
                'cny': cny_value,
                'usd': usd_value,
                'total': total,
            }
        )

    collected_days = len(collected_dates)
    daily_average = consumed_total / collected_days if collected_days else 0.0
    remaining_days = max(days_total - now.day, 0)
    estimated_total = consumed_total + daily_average * remaining_days

    return {
        'estimated_total': round(estimated_total, 2),
        'current_consumed': round(consumed_total, 2),
        'daily_average': round(daily_average, 2),
        'collected_days': collected_days,
        'peak_cost': round(peak_cost, 2),
        'peak_date': peak_date,
        'trend': trend,
    }


def _trend_point(
    label: str, cny_value: float, usd_value: float, usd_to_cny_rate: float
) -> dict[str, object]:
    cny = round(cny_value, 2)
    usd = round(usd_value, 2)
    return {
        'date': label,
        'cny': cny,
        'usd': usd,
        'total': round(cny + usd * usd_to_cny_rate, 2),
    }


def _build_trend_ranges(
    month_rows,
    recent_rows,
    year_rows,
    local_tz,
    now,
    usd_to_cny_rate: float | None = None,
):
    usd_to_cny_rate = float(usd_to_cny_rate or CNY_RATE)

    today_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    for row in month_rows:
        local_collected_at = row.collected_at.astimezone(local_tz)
        if local_collected_at.date() != now.date():
            continue
        label = f'{local_collected_at.hour:02d}:00'
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        today_map[label][currency_key] += _hourly_cost_value(row)

    today = []
    for hour in range(24):
        label = f'{hour:02d}:00'
        today.append(
            _trend_point(
                label,
                today_map[label]['cny'],
                today_map[label]['usd'],
                usd_to_cny_rate,
            )
        )

    week_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    week_start = now.date() - timedelta(days=6)
    for row in month_rows:
        local_collected_at = row.collected_at.astimezone(local_tz)
        row_date = local_collected_at.date()
        if row_date < week_start or row_date > now.date():
            continue
        label = local_collected_at.strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        week_map[label][currency_key] += _hourly_cost_value(row)

    week = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        label = day.strftime('%m-%d')
        week.append(
            _trend_point(
                label,
                week_map[label]['cny'],
                week_map[label]['usd'],
                usd_to_cny_rate,
            )
        )

    recent_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    recent_start = now.date() - timedelta(days=29)
    for row in recent_rows:
        local_collected_at = row.collected_at.astimezone(local_tz)
        row_date = local_collected_at.date()
        if row_date < recent_start or row_date > now.date():
            continue
        label = local_collected_at.strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        recent_map[label][currency_key] += _hourly_cost_value(row)

    thirty_days = []
    for offset in range(30):
        day = recent_start + timedelta(days=offset)
        label = day.strftime('%m-%d')
        thirty_days.append(
            _trend_point(
                label,
                recent_map[label]['cny'],
                recent_map[label]['usd'],
                usd_to_cny_rate,
            )
        )

    month_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    for row in month_rows:
        label = row.collected_at.astimezone(local_tz).strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        month_map[label][currency_key] += _hourly_cost_value(row)

    month = []
    month_days = monthrange(now.year, now.month)[1]
    for index in range(1, month_days + 1):
        label = f'{now.month:02d}-{index:02d}'
        month.append(
            _trend_point(
                label,
                month_map[label]['cny'],
                month_map[label]['usd'],
                usd_to_cny_rate,
            )
        )

    year_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    for row in year_rows:
        label = row.collected_at.astimezone(local_tz).strftime('%Y-%m')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        year_map[label][currency_key] += _hourly_cost_value(row)

    year = []
    for month_index in range(1, 13):
        label = f'{now.year}-{month_index:02d}'
        year.append(
            _trend_point(
                label,
                year_map[label]['cny'],
                year_map[label]['usd'],
                usd_to_cny_rate,
            )
        )

    return {
        'today': today,
        'week': week,
        'thirtyDays': thirty_days,
        'month': month,
        'year': year,
    }


def _build_currency_breakdown(accounts, exchange_rate: float | None = None):
    usd_to_cny_rate = float(exchange_rate or CNY_RATE)
    totals = defaultdict(float)
    original_totals = defaultdict(float)
    seen_providers = set()
    for account in accounts:
        provider_key = account.get('provider_id')
        if provider_key not in (None, ''):
            provider_key = str(provider_key)
            if provider_key in seen_providers:
                continue
            seen_providers.add(provider_key)
        currency = str(account.get('balance_currency') or '').upper()
        amount = _to_float(account.get('balance'))
        if not currency or amount <= 0:
            continue
        original_totals[currency] += amount
        if currency == 'USD':
            totals[currency] += amount * usd_to_cny_rate
        else:
            totals[currency] += amount

    total_value = sum(totals.values()) or 1.0
    colors = {'USD': '#6366f1', 'CNY': '#10b981'}
    labels = {'USD': _('US Dollar'), 'CNY': _('Chinese Yuan')}
    items = []
    for currency in sorted(totals.keys()):
        items.append(
            {
                'name': labels.get(currency, currency),
                'code': currency,
                'value': round(totals[currency], 2),
                'original_value': round(original_totals[currency], 2),
                'percentage': round(totals[currency] / total_value * 100, 1),
                'color': colors.get(currency, '#94a3b8'),
            }
        )
    return items


def _risk_for_days(days_remaining: int) -> str:
    if days_remaining <= 10:
        return 'high'
    if days_remaining <= 30:
        return 'medium'
    return 'low'


def _build_account_detail(
    billing: BillingData,
    monthly_rows,
    recent_rows,
    display_funds: float,
    daily_burn: float,
    days_remaining: int,
    payment_type: str,
    selected_currency: str,
):
    provider_id = getattr(billing, 'provider_id', None) or getattr(
        getattr(billing, 'provider', None),
        'id',
        None,
    )
    account_key = (provider_id, billing.account_id or '')
    relevant_recent_rows = []
    for row in recent_rows:
        row_provider_id = getattr(row, 'provider_id', None) or getattr(
            getattr(row, 'provider', None),
            'id',
            None,
        )
        if (row_provider_id, row.account_id or '') == account_key:
            relevant_recent_rows.append(row)

    baseline_service_costs_by_period = {}
    first_recent_row_by_period = {}
    for row in relevant_recent_rows:
        row_period = getattr(row, 'period', None)
        if row_period and row_period not in first_recent_row_by_period:
            first_recent_row_by_period[row_period] = row

    for row in monthly_rows:
        row_provider_id = getattr(row, 'provider_id', None) or getattr(
            getattr(row, 'provider', None),
            'id',
            None,
        )
        row_period = getattr(row, 'period', None)
        if (row_provider_id, row.account_id or '') != account_key or not row_period:
            continue

        first_recent_row = first_recent_row_by_period.get(row_period)
        if first_recent_row is None:
            continue

        if (
            getattr(row, 'hour', -1),
            getattr(row, 'collected_at', None),
        ) >= (
            getattr(first_recent_row, 'hour', -1),
            getattr(first_recent_row, 'collected_at', None),
        ):
            continue

        baseline_service_costs_by_period[row_period] = {
            str(service_name): _to_float(service_value)
            for service_name, service_value in (
                (getattr(row, 'service_costs', {}) or {}).items()
            )
        }

    daily_totals = defaultdict(float)
    daily_service_totals = defaultdict(lambda: defaultdict(float))
    total_service_totals = defaultdict(float)
    previous_service_costs = None
    previous_period = None
    has_recent_service_rows = False
    for index, row in enumerate(relevant_recent_rows):
        collected_at = getattr(row, 'collected_at', None)
        label = (
            collected_at.strftime('%m-%d')
            if collected_at is not None
            else f'{index + 1:02d}'
        )
        row_total = _hourly_cost_value(row)
        daily_totals[label] += row_total

        row_service_costs = getattr(row, 'service_costs', {}) or {}
        current_period = getattr(row, 'period', None)
        service_delta_map = {}
        if row_service_costs:
            has_recent_service_rows = True
            if previous_period != current_period:
                previous_service_costs = baseline_service_costs_by_period.get(
                    current_period
                )
            if previous_service_costs is None:
                for service_name, service_value in row_service_costs.items():
                    numeric_value = _to_float(service_value)
                    if numeric_value > 0:
                        service_delta_map[str(service_name)] = numeric_value
            else:
                all_service_names = set(previous_service_costs) | set(row_service_costs)
                for service_name in all_service_names:
                    current_value = _to_float(row_service_costs.get(service_name))
                    previous_value = _to_float(previous_service_costs.get(service_name))
                    delta_value = current_value - previous_value
                    if delta_value > 0:
                        service_delta_map[str(service_name)] = delta_value

            for service_name, service_value in service_delta_map.items():
                daily_service_totals[label][service_name] += round(service_value, 2)
                total_service_totals[service_name] += round(service_value, 2)

            previous_service_costs = {
                str(service_name): _to_float(service_value)
                for service_name, service_value in row_service_costs.items()
            }
            previous_period = current_period

    ordered_dates = []
    if recent_rows:
        if all(getattr(row, 'collected_at', None) is not None for row in recent_rows):
            first_day = recent_rows[0].collected_at.date()
            last_day = recent_rows[-1].collected_at.date()
            cursor = first_day
            while cursor <= last_day:
                ordered_dates.append(cursor.strftime('%m-%d'))
                cursor += timedelta(days=1)
        else:
            ordered_dates = sorted(daily_totals.keys())
    recent_trend = [
        {'date': label, 'value': round(daily_totals.get(label, 0.0), 2)}
        for label in ordered_dates[-30:]
    ]

    fallback_service_costs = getattr(billing, 'service_costs', {}) or {}
    service_breakdown_source = 'recent_rows'
    if not total_service_totals:
        service_breakdown_source = 'latest_billing'
        for service_name, service_value in fallback_service_costs.items():
            numeric_value = _to_float(service_value)
            if numeric_value > 0:
                total_service_totals[str(service_name)] = numeric_value

    sorted_services = sorted(
        (
            {
                'name': str(name),
                'value': round(_to_float(value), 2),
            }
            for name, value in total_service_totals.items()
            if _to_float(value) > 0
        ),
        key=lambda item: item['value'],
        reverse=True,
    )
    total_service_cost = sum(item['value'] for item in sorted_services) or 0.0
    comparison_total = (
        sum(item['value'] for item in recent_trend)
        if service_breakdown_source == 'recent_rows'
        else _to_float(getattr(billing, 'total_cost', 0))
    )
    service_coverage = (
        round(total_service_cost / comparison_total * 100, 1)
        if comparison_total > 0 and total_service_cost > 0
        else 0.0
    )
    primary_service = (
        sorted_services[0]
        if sorted_services
        else {'name': _('Core services'), 'value': 0.0}
    )
    primary_share = (
        round(primary_service['value'] / total_service_cost * 100, 1)
        if total_service_cost
        else 0.0
    )
    detailed_services = [
        {
            'name': item['name'],
            'value': item['value'],
            'percentage': (
                round(item['value'] / total_service_cost * 100, 1)
                if total_service_cost
                else 0.0
            ),
        }
        for item in sorted_services
    ]

    major_services = []
    other_service_total = 0.0
    for item in detailed_services:
        if item['percentage'] < 5:
            other_service_total += item['value']
        else:
            major_services.append(item)
    other_share = (
        round(other_service_total / total_service_cost * 100, 1)
        if total_service_cost and other_service_total > 0
        else 0.0
    )
    if other_service_total > 0:
        major_services.append(
            {
                'name': '__other__',
                'value': round(other_service_total, 2),
                'percentage': other_share,
            }
        )

    detail_trend = []
    trend_series = []
    recent_labels = [item['date'] for item in recent_trend]
    for service in major_services:
        service_name = service['name']
        values = []
        for label in recent_labels:
            if service_name == '__other__':
                major_names = {
                    item['name']
                    for item in major_services
                    if item['name'] != '__other__'
                }
                other_value = sum(
                    value
                    for name, value in daily_service_totals.get(label, {}).items()
                    if name not in major_names
                )
                values.append(round(other_value, 2))
            else:
                values.append(
                    round(
                        daily_service_totals.get(label, {}).get(
                            service_name, 0.0
                        ),
                        2,
                    )
                )
        trend_series.append(
            {
                'name': service_name,
                'percentage': service['percentage'],
                'values': values,
            }
        )

    for index, item in enumerate(recent_trend):
        services_map = {
            series['name']: series['values'][index]
            for series in trend_series
        }
        detail_trend.append(
            {
                'date': item['date'],
                'total': round(item['value'], 2),
                'services': services_map,
            }
        )

    peak_daily_cost = max((item['value'] for item in recent_trend), default=0.0)
    recommended_recharge = round(max(daily_burn * 30 - display_funds, 0), 2)
    if payment_type == 'postpaid':
        recommendation_status = 'healthy' if days_remaining > 14 else 'attention'
    else:
        recommendation_status = 'healthy' if days_remaining > 21 else 'attention'

    return {
        'recommendation_status': recommendation_status,
        'daily_average': round(daily_burn, 2),
        'daily_peak': round(peak_daily_cost, 2),
        'recommended_recharge': recommended_recharge,
        'recommended_window_days': 30,
        'service_count': len(sorted_services),
        'primary_service_name': primary_service['name'],
        'primary_service_share': primary_share,
        'other_service_share': other_share,
        'service_breakdown_currency': str(
            getattr(billing, 'currency', '') or selected_currency or 'CNY'
        ).upper(),
        'service_breakdown_source': service_breakdown_source,
        'service_breakdown_has_recent_rows': has_recent_service_rows,
        'service_breakdown_coverage': service_coverage,
        'service_breakdown_complete': abs(service_coverage - 100.0) < 0.1,
        'service_breakdown': detailed_services,
        'trend_series': trend_series,
        'trend_30d': detail_trend,
    }


def _build_accounts(
    latest_billings,
    daily_rows,
    recent_rows=None,
    local_tz=None,
    now=None,
):
    if local_tz is None:
        local_tz = timezone.get_current_timezone()
    if now is None:
        now = timezone.now().astimezone(local_tz)
    if recent_rows is None:
        recent_rows = daily_rows
    monthly_burn = defaultdict(float)
    recent_rows_by_account = defaultdict(list)
    for row in daily_rows:
        account_key = (row.provider_id, row.account_id or '')
        monthly_burn[account_key] += _hourly_cost_value(row)
    for row in recent_rows:
        account_key = (row.provider_id, row.account_id or '')
        recent_rows_by_account[account_key].append(row)

    total_cost = sum(_to_float(item.total_cost) for item in latest_billings) or 1.0
    accounts = []
    for billing in latest_billings:
        provider = billing.provider
        account_key = (provider.id, billing.account_id or '')
        burn = monthly_burn[account_key]
        recent_spend = _recent_spend_from_snapshots(
            recent_rows_by_account[account_key],
            now,
        )
        recent_collected_days = _recent_collected_days_from_snapshots(
            recent_rows_by_account[account_key],
            now,
            local_tz,
        )
        daily_burn = (
            recent_spend / recent_collected_days
            if recent_spend and recent_collected_days > 0
            else 0.0
        )
        balance_info = get_balance_support_info(provider)
        payment_type = _payment_type_for_provider(
            provider,
            balance_info['supported'],
        )
        funds = _normalize_account_funds(provider, billing, payment_type)
        display_funds = float(funds['display_funds'])
        if funds['uses_credit_limit_days'] and display_funds > 0 and daily_burn > 0:
            days_remaining = max(int(display_funds / daily_burn), 1)
        elif float(funds['balance']) > 0 and daily_burn > 0:
            days_remaining = max(int(float(funds['balance']) / daily_burn), 1)
        elif payment_type == 'postpaid':
            days_remaining = 45
        else:
            days_remaining = 120

        account_trend = []
        for index in range(10):
            date_key = (now - timedelta(days=9 - index)).strftime('%m-%d')
            account_trend.append(
                {
                    'date': date_key,
                    # Back-cast from today's available funds:
                    # older points should be higher when daily burn is positive.
                    'value': round(max(display_funds + daily_burn * (9 - index), 0), 2),
                }
            )

        accounts.append(
            {
                'id': f'{provider.id}-{billing.account_id or "default"}',
                'provider_id': provider.id,
                'name': provider.display_name,
                'provider': provider.display_name,
                'provider_type': provider.provider_type,
                'notes': (getattr(provider, 'notes', '') or '').strip(),
                'tags': list(getattr(provider, 'tags', []) or []),
                'category': (
                    'LLM'
                    if provider.provider_type in LLM_PROVIDER_TYPES
                    else 'Cloud'
                ),
                'cost': round(_to_float(billing.total_cost), 2),
                'cost_currency': str(getattr(billing, 'currency', '') or 'CNY').upper(),
                'percentage': round(_to_float(billing.total_cost) / total_cost * 100, 1),
                'change': round(daily_burn, 1),
                'risk': _risk_for_days(days_remaining),
                'balance': funds['balance'],
                'balance_currency': funds['balance_currency'],
                'credit_limit': funds['credit_limit'],
                'credit_limit_currency': funds['credit_limit_currency'],
                'display_funds': funds['display_funds'],
                'display_funds_currency': funds['display_funds_currency'],
                'days_remaining': days_remaining,
                'type': payment_type,
                'usage_rate': None,
                'account_id': billing.account_id or '',
                'trend': account_trend,
                'detail': _build_account_detail(
                    billing,
                    daily_rows,
                    recent_rows,
                    display_funds=display_funds,
                    daily_burn=daily_burn,
                    days_remaining=days_remaining,
                    payment_type=payment_type,
                    selected_currency=str(
                        funds['display_funds_currency']
                        or billing.currency
                        or 'CNY'
                    ).upper(),
                ),
            }
        )

    accounts.sort(key=lambda item: (item['days_remaining'], -item['cost']))
    return accounts


def _build_financial_health(accounts):
    provider_balances = {}
    for item in accounts:
        provider_key = item.get('provider_id')
        if provider_key in (None, ''):
            provider_key = item.get('id')
        if provider_key in (None, '') or provider_key in provider_balances:
            continue
        provider_balances[provider_key] = _to_float(item.get('balance'))

    total_funds = round(sum(provider_balances.values()), 2)
    total_days = min((item['days_remaining'] for item in accounts), default=0)
    bottleneck = next(
        (item['name'] for item in accounts if item['days_remaining'] == total_days),
        '',
    )
    recharge_alerts = [
        {
            'name': item['name'],
            'category': item['category'],
            'account_id': item['account_id'],
            'notes': item['notes'],
            'tags': item.get('tags', []),
            'days_remaining': item['days_remaining'],
        }
        for item in accounts
    ]
    return {
        'total_funds': total_funds,
        'total_days': total_days,
        'bottleneck': bottleneck,
        'recharge_alerts': recharge_alerts,
    }


def _build_fallback_exchange_rate_info() -> dict[str, object]:
    return {
        'exchange_rate': float(CNY_RATE),
        'rate_source_label': 'Internal baseline rate',
        'rate_source_url': '',
        'rate_collected_at': '',
    }


def _build_exchange_rate_info() -> dict[str, object]:
    api_key = os.getenv('EXCHANGE_RATE_API_KEY', '').strip()
    if not api_key:
        return _build_fallback_exchange_rate_info()

    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:12]
    cache_key = f'{EXCHANGE_RATE_CACHE_PREFIX}:{key_hash}'
    cached_value = _cache_get_safely(cache_key)
    if cached_value:
        return cached_value

    request_url = EXCHANGE_RATE_API_URL.format(api_key=api_key)
    timeout = int(os.getenv('EXCHANGE_RATE_API_TIMEOUT', '10'))

    try:
        response = requests.get(request_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json() or {}
        conversion_rates = payload.get('conversion_rates') or {}
        cny_rate = conversion_rates.get('CNY')
        if cny_rate is None:
            raise ValueError('CNY conversion rate missing from exchange response')

        collected_at = timezone.now()
        last_update_unix = payload.get('time_last_update_unix')
        if last_update_unix:
            collected_at = datetime.fromtimestamp(
                int(last_update_unix),
                tz=dt_timezone.utc,
            )

        exchange_rate_info = {
            'exchange_rate': float(cny_rate),
            'rate_source_label': 'ExchangeRate API',
            'rate_source_url': EXCHANGE_RATE_SOURCE_URL,
            'rate_collected_at': collected_at.isoformat(),
        }
        _cache_set_safely(
            cache_key,
            exchange_rate_info,
            timeout=EXCHANGE_RATE_CACHE_TTL,
        )
        return exchange_rate_info
    except Exception as exc:  # noqa: BLE001
        logger.warning('Failed to fetch exchange rate from ExchangeRate API: %s', exc)
        return _build_fallback_exchange_rate_info()


def build_dashboard_overview(timezone_name: str | None = None) -> dict[str, object]:
    """Build a dashboard payload for the operations overview page."""
    local_tz = _resolve_dashboard_timezone(timezone_name)
    exchange_rate_info = _build_exchange_rate_info()
    latest_billings = _latest_billings()
    now, _, daily_rows = _daily_rows_for_current_month(local_tz)
    _, _, recent_rows = _billing_rows_for_recent_days(local_tz, days=30)
    _, _, year_rows = _billing_rows_for_current_year(local_tz)
    accounts = _build_accounts(
        latest_billings,
        daily_rows,
        recent_rows=recent_rows,
        local_tz=local_tz,
        now=now,
    )
    summary = _build_summary(
        latest_billings,
        daily_rows,
        local_tz,
        now,
        float(exchange_rate_info.get('exchange_rate') or CNY_RATE),
    )
    summary['trend_ranges'] = _build_trend_ranges(
        daily_rows,
        recent_rows,
        year_rows,
        local_tz,
        now,
        float(exchange_rate_info.get('exchange_rate') or CNY_RATE),
    )
    overview = {
        'summary': summary,
        'currency_breakdown': _build_currency_breakdown(
            accounts,
            exchange_rate=exchange_rate_info.get('exchange_rate'),
        ),
        'financial_health': _build_financial_health(accounts),
        'accounts': accounts,
        'timezone': str(local_tz),
    }
    overview.update(exchange_rate_info)
    return overview
