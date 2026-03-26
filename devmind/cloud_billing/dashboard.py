"""Dashboard aggregation helpers for cloud billing overview pages."""

from __future__ import annotations

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

from .models import BillingData, CloudProvider
from .serializers import get_balance_support_info

LLM_PROVIDER_TYPES = {'zhipu'}
CNY_RATE = Decimal('7.15')
EXCHANGE_RATE_API_URL = 'https://v6.exchangerate-api.com/v6/{api_key}/latest/USD'
EXCHANGE_RATE_SOURCE_URL = 'https://www.exchangerate-api.com/'
EXCHANGE_RATE_CACHE_PREFIX = 'cloud_billing:exchange_rate'
EXCHANGE_RATE_CACHE_TTL = 60 * 60 * 24
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
    account_currency = str(getattr(billing, 'currency', '') or 'USD').upper()
    raw_balance = _to_float(getattr(billing, 'balance', None))
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


def _build_summary(latest_billings, daily_rows, local_tz, now):
    days_in_month = max(now.day, 1)
    days_total = 30
    current_consumed = sum(_to_float(item.total_cost) for item in latest_billings)
    daily_average = current_consumed / days_in_month if days_in_month else 0.0
    estimated_total = daily_average * days_total

    trend_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    peak_cost = 0.0
    peak_date = now.date().isoformat()
    for row in daily_rows:
        local_collected_at = row.collected_at.astimezone(local_tz)
        date_key = local_collected_at.strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        trend_map[date_key][currency_key] += _hourly_cost_value(row)

    trend = []
    for index in range(1, 32):
        date_key = f'{now.month:02d}-{index:02d}'
        cny_value = round(trend_map[date_key]['cny'], 2)
        usd_value = round(trend_map[date_key]['usd'], 2)
        total = round(cny_value + usd_value, 2)
        if total > peak_cost:
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

    return {
        'estimated_total': round(estimated_total, 2),
        'current_consumed': round(current_consumed, 2),
        'daily_average': round(daily_average, 2),
        'peak_cost': round(peak_cost, 2),
        'peak_date': peak_date,
        'trend': trend,
    }


def _trend_point(label: str, cny_value: float, usd_value: float) -> dict[str, object]:
    cny = round(cny_value, 2)
    usd = round(usd_value, 2)
    return {
        'date': label,
        'cny': cny,
        'usd': usd,
        'total': round(cny + usd, 2),
    }


def _build_trend_ranges(month_rows, year_rows, local_tz, now):

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
            _trend_point(label, today_map[label]['cny'], today_map[label]['usd'])
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
        week.append(_trend_point(label, week_map[label]['cny'], week_map[label]['usd']))

    month_map = defaultdict(lambda: {'cny': 0.0, 'usd': 0.0})
    for row in month_rows:
        label = row.collected_at.astimezone(local_tz).strftime('%m-%d')
        currency_key = 'cny' if str(row.currency).upper() == 'CNY' else 'usd'
        month_map[label][currency_key] += _hourly_cost_value(row)

    month = []
    for index in range(1, 32):
        label = f'{now.month:02d}-{index:02d}'
        month.append(
            _trend_point(label, month_map[label]['cny'], month_map[label]['usd'])
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
            _trend_point(label, year_map[label]['cny'], year_map[label]['usd'])
        )

    return {
        'today': today,
        'week': week,
        'month': month,
        'year': year,
    }


def _build_currency_breakdown(latest_billings):
    totals = defaultdict(float)
    original_totals = defaultdict(float)
    for billing in latest_billings:
        currency = str(billing.currency or 'USD').upper()
        amount = _to_float(billing.total_cost)
        original_totals[currency] += amount
        if currency == 'USD':
            totals[currency] += amount * float(CNY_RATE)
        else:
            totals[currency] += amount

    total_value = sum(totals.values()) or 1.0
    colors = {'USD': '#6366f1', 'CNY': '#10b981'}
    labels = {'USD': '美元', 'CNY': '人民币'}
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


def _build_accounts(latest_billings, daily_rows, local_tz=None, now=None):
    if local_tz is None:
        local_tz = timezone.get_current_timezone()
    if now is None:
        now = timezone.now().astimezone(local_tz)
    monthly_burn = defaultdict(float)
    for row in daily_rows:
        account_key = (row.provider_id, row.account_id or '')
        monthly_burn[account_key] += _hourly_cost_value(row)

    total_cost = sum(_to_float(item.total_cost) for item in latest_billings) or 1.0
    accounts = []
    for billing in latest_billings:
        provider = billing.provider
        account_key = (provider.id, billing.account_id or '')
        burn = monthly_burn[account_key]
        daily_burn = burn / max(now.day, 1) if burn else 0.0
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
                    'value': round(max(display_funds - daily_burn * (9 - index), 0), 2),
                }
            )

        accounts.append(
            {
                'id': f'{provider.id}-{billing.account_id or "default"}',
                'name': provider.display_name,
                'provider': provider.display_name,
                'provider_type': provider.provider_type,
                'notes': (getattr(provider, 'notes', '') or '').strip(),
                'category': (
                    'LLM'
                    if provider.provider_type in LLM_PROVIDER_TYPES
                    else 'Cloud'
                ),
                'cost': round(_to_float(billing.total_cost), 2),
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
            }
        )

    accounts.sort(key=lambda item: (item['days_remaining'], -item['cost']))
    return accounts


def _build_financial_health(accounts):
    total_funds = round(sum(item['balance'] for item in accounts), 2)
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
            'days_remaining': item['days_remaining'],
        }
        for item in accounts[:8]
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
        'rate_collected_at': timezone.now().isoformat(),
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
    latest_billings = _latest_billings()
    now, _, daily_rows = _daily_rows_for_current_month(local_tz)
    _, _, year_rows = _billing_rows_for_current_year(local_tz)
    accounts = _build_accounts(latest_billings, daily_rows, local_tz=local_tz, now=now)
    summary = _build_summary(latest_billings, daily_rows, local_tz, now)
    summary['trend_ranges'] = _build_trend_ranges(daily_rows, year_rows, local_tz, now)
    overview = {
        'summary': summary,
        'currency_breakdown': _build_currency_breakdown(latest_billings),
        'financial_health': _build_financial_health(accounts),
        'accounts': accounts,
        'timezone': str(local_tz),
    }
    overview.update(_build_exchange_rate_info())
    return overview
