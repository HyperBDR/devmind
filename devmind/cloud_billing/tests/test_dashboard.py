from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from decimal import Decimal
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from cloud_billing.dashboard import (
    _build_accounts,
    _build_exchange_rate_info,
    _payment_type_for_provider,
    _build_trend_ranges,
)


class ExchangeRateInfoTests(SimpleTestCase):
    def test_uses_fallback_when_api_key_missing(self):
        with patch.dict('os.environ', {}, clear=True):
            result = _build_exchange_rate_info()

        self.assertEqual(result['rate_source_label'], 'Internal baseline rate')
        self.assertEqual(result['exchange_rate'], 7.15)
        self.assertEqual(result['rate_source_url'], '')


class PaymentTypeTests(SimpleTestCase):
    def test_code_defined_postpaid_provider_types_take_priority(self):
        aws_provider = SimpleNamespace(provider_type='aws', config={'payment_type': 'prepaid'})
        azure_provider = SimpleNamespace(provider_type='azure', config={})
        huawei_intl_provider = SimpleNamespace(provider_type='huawei-intl', config={})

        self.assertEqual(_payment_type_for_provider(aws_provider, balance_supported=True), 'postpaid')
        self.assertEqual(_payment_type_for_provider(azure_provider, balance_supported=True), 'postpaid')
        self.assertEqual(
            _payment_type_for_provider(huawei_intl_provider, balance_supported=True),
            'postpaid',
        )

    def test_other_provider_types_can_still_use_config_or_balance_support(self):
        alibaba_provider = SimpleNamespace(provider_type='alibaba', config={'payment_type': 'prepaid'})
        tencent_provider = SimpleNamespace(provider_type='tencentcloud', config={})

        self.assertEqual(
            _payment_type_for_provider(alibaba_provider, balance_supported=False),
            'prepaid',
        )
        self.assertEqual(
            _payment_type_for_provider(tencent_provider, balance_supported=False),
            'postpaid',
        )

    @patch('cloud_billing.dashboard.requests.get')
    @patch('cloud_billing.dashboard._cache_get_safely', return_value=None)
    def test_fetches_exchange_rate_from_remote_api(
        self,
        _mock_cache_get,
        mock_get,
    ):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'conversion_rates': {'CNY': 7.23},
            'time_last_update_unix': 1711411200,
        }
        mock_get.return_value = response

        with patch.dict(
            'os.environ',
            {'EXCHANGE_RATE_API_KEY': 'test-api-key', 'EXCHANGE_RATE_API_TIMEOUT': '12'},
            clear=True,
        ):
            result = _build_exchange_rate_info()

        self.assertEqual(result['exchange_rate'], 7.23)
        self.assertEqual(result['rate_source_label'], 'ExchangeRate API')
        self.assertEqual(result['rate_source_url'], 'https://www.exchangerate-api.com/')
        mock_get.assert_called_once_with(
            'https://v6.exchangerate-api.com/v6/test-api-key/latest/USD',
            timeout=12,
        )

    @patch('cloud_billing.dashboard.requests.get')
    @patch('cloud_billing.dashboard._cache_get_safely', return_value=None)
    def test_falls_back_when_remote_api_fails(
        self,
        _mock_cache_get,
        mock_get,
    ):
        mock_get.side_effect = RuntimeError('network failure')

        with patch.dict(
            'os.environ',
            {'EXCHANGE_RATE_API_KEY': 'test-api-key'},
            clear=True,
        ):
            result = _build_exchange_rate_info()

        self.assertEqual(result['rate_source_label'], 'Internal baseline rate')
        self.assertEqual(result['exchange_rate'], 7.15)

    @patch('cloud_billing.dashboard.requests.get')
    @patch('cloud_billing.dashboard._cache_set_safely')
    @patch('cloud_billing.dashboard._cache_get_safely')
    def test_uses_cached_exchange_rate_within_24_hours(
        self,
        mock_cache_get,
        mock_cache_set,
        mock_get,
    ):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'conversion_rates': {'CNY': 7.31},
            'time_last_update_unix': 1711411200,
        }
        mock_get.return_value = response
        mock_cache_get.side_effect = [
            None,
            {
                'exchange_rate': 7.31,
                'rate_source_label': 'ExchangeRate API',
                'rate_source_url': 'https://www.exchangerate-api.com/',
                'rate_collected_at': '2024-03-26T00:00:00+00:00',
            },
        ]

        with patch.dict(
            'os.environ',
            {'EXCHANGE_RATE_API_KEY': 'cached-api-key', 'EXCHANGE_RATE_API_TIMEOUT': '9'},
            clear=True,
        ):
            first_result = _build_exchange_rate_info()
            second_result = _build_exchange_rate_info()

        self.assertEqual(first_result, second_result)
        mock_cache_set.assert_called_once()
        mock_get.assert_called_once_with(
            'https://v6.exchangerate-api.com/v6/cached-api-key/latest/USD',
            timeout=9,
        )


class AccountFundsTests(SimpleTestCase):
    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_huawei_intl_postpaid_uses_credit_limit_instead_of_balance(self, mock_balance_support):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=11,
            provider_type='huawei-intl',
            display_name='华为云（国际）',
            config={},
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-1',
                total_cost=Decimal('568.90'),
                balance=Decimal('200.00'),
                currency='USD',
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=11,
                account_id='acct-1',
                hourly_cost=Decimal('620.00'),
            )
        ]

        accounts = _build_accounts(latest_billings, daily_rows)

        self.assertEqual(len(accounts), 1)
        account = accounts[0]
        self.assertEqual(account['type'], 'postpaid')
        self.assertEqual(account['balance'], 0.0)
        self.assertEqual(account['balance_currency'], '')
        self.assertEqual(account['credit_limit'], 200.0)
        self.assertEqual(account['credit_limit_currency'], 'USD')
        self.assertEqual(account['days_remaining'], 45)


class DashboardTimezoneTests(SimpleTestCase):
    @patch('cloud_billing.dashboard.timezone.now')
    def test_trend_ranges_align_with_selected_timezone(self, mock_now):
        los_angeles = ZoneInfo('America/Los_Angeles')
        mock_now.return_value = datetime(2026, 3, 26, 1, 0, tzinfo=dt_timezone.utc)

        month_rows = [
            SimpleNamespace(
                collected_at=datetime(2026, 3, 26, 0, 30, tzinfo=dt_timezone.utc),
                currency='USD',
                hourly_cost=Decimal('12.50'),
                hour=0,
            ),
            SimpleNamespace(
                collected_at=datetime(2026, 3, 24, 7, 30, tzinfo=dt_timezone.utc),
                currency='CNY',
                hourly_cost=Decimal('88.00'),
                hour=7,
            ),
        ]

        ranges = _build_trend_ranges(
            month_rows,
            month_rows,
            los_angeles,
            mock_now.return_value.astimezone(los_angeles),
        )

        today_points = {item['date']: item for item in ranges['today']}
        week_points = {item['date']: item for item in ranges['week']}

        self.assertEqual(today_points['17:00']['usd'], 12.5)
        self.assertEqual(today_points['17:00']['cny'], 0.0)
        self.assertEqual(week_points['03-24']['cny'], 88.0)
        self.assertEqual(week_points['03-25']['usd'], 12.5)
