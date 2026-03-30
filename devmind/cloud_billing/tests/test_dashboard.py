from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from decimal import Decimal
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from cloud_billing.dashboard import (
    _build_account_detail,
    _build_accounts,
    _build_currency_breakdown,
    _build_exchange_rate_info,
    _build_financial_health,
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
        self.assertEqual(mock_cache_set.call_args.kwargs['timeout'], 60 * 60 * 24)
        mock_get.assert_called_once_with(
            'https://v6.exchangerate-api.com/v6/cached-api-key/latest/USD',
            timeout=9,
        )

    def test_currency_breakdown_uses_account_balance(self):
        accounts = [
            {
                'provider_id': 1,
                'balance_currency': 'USD',
                'balance': Decimal('10.00'),
                'display_funds_currency': 'USD',
                'display_funds': Decimal('999.00'),
            },
            {
                'provider_id': 1,
                'balance_currency': 'USD',
                'balance': Decimal('10.00'),
            },
            {'provider_id': 2, 'balance_currency': 'CNY', 'balance': Decimal('100.00')},
            {'display_funds_currency': 'USD', 'display_funds': Decimal('500.00')},
        ]

        items = _build_currency_breakdown(accounts, exchange_rate=8.0)
        breakdown = {item['code']: item for item in items}

        self.assertEqual(breakdown['USD']['value'], 80.0)
        self.assertEqual(breakdown['USD']['original_value'], 10.0)
        self.assertEqual(breakdown['CNY']['value'], 100.0)

    def test_financial_health_total_funds_deduplicates_provider_balance(self):
        accounts = [
            {
                'provider_id': 1,
                'id': '1-acct-a',
                'balance': Decimal('200.00'),
                'days_remaining': 8,
                'name': 'AWS Main',
                'category': 'Cloud',
                'account_id': 'acct-a',
                'notes': '',
                'tags': [],
            },
            {
                'provider_id': 1,
                'id': '1-acct-b',
                'balance': Decimal('200.00'),
                'days_remaining': 12,
                'name': 'AWS Main',
                'category': 'Cloud',
                'account_id': 'acct-b',
                'notes': '',
                'tags': [],
            },
            {
                'provider_id': 2,
                'id': '2-default',
                'balance': Decimal('50.00'),
                'days_remaining': 5,
                'name': 'Baidu',
                'category': 'Cloud',
                'account_id': '',
                'notes': '',
                'tags': [],
            },
        ]

        financial_health = _build_financial_health(accounts)

        self.assertEqual(financial_health['total_funds'], 250.0)


class AccountFundsTests(SimpleTestCase):
    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_huawei_intl_postpaid_uses_credit_limit_instead_of_balance(self, mock_balance_support):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=11,
            provider_type='huawei-intl',
            display_name='华为云（国际）',
            config={},
            balance=Decimal('200.00'),
            balance_currency='USD',
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

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_account_tags_are_exposed_to_dashboard(self, mock_balance_support):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=22,
            provider_type='baidu',
            display_name='百度智能云',
            tags=['生产', '核心'],
            notes='VIP',
            config={},
            balance=Decimal('500.00'),
            balance_currency='CNY',
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-2',
                total_cost=Decimal('88.00'),
                currency='CNY',
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=22,
                account_id='acct-2',
                hourly_cost=Decimal('10.00'),
            )
        ]

        accounts = _build_accounts(latest_billings, daily_rows)
        financial_health = _build_financial_health(accounts)

        self.assertEqual(accounts[0]['tags'], ['生产', '核心'])
        self.assertEqual(
            financial_health['recharge_alerts'][0]['tags'],
            ['生产', '核心'],
        )

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_account_detail_contains_service_breakdown_and_trend(self, mock_balance_support):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=23,
            provider_type='alibaba',
            display_name='阿里云',
            tags=[],
            notes='',
            config={},
            balance=Decimal('900.00'),
            balance_currency='CNY',
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-3',
                total_cost=Decimal('300.00'),
                currency='CNY',
                service_costs={'ECS': Decimal('210.00'), 'OSS': Decimal('90.00')},
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=23,
                account_id='acct-3',
                hourly_cost=Decimal('30.00'),
                collected_at=datetime(2026, 3, 25, 0, 0, tzinfo=dt_timezone.utc),
                period='2026-03',
                service_costs={'ECS': Decimal('21.00'), 'OSS': Decimal('9.00')},
            ),
            SimpleNamespace(
                provider_id=23,
                account_id='acct-3',
                hourly_cost=Decimal('45.00'),
                collected_at=datetime(2026, 3, 26, 0, 0, tzinfo=dt_timezone.utc),
                period='2026-03',
                service_costs={'ECS': Decimal('52.50'), 'OSS': Decimal('22.50')},
            ),
        ]

        accounts = _build_accounts(
            latest_billings,
            daily_rows,
            recent_rows=daily_rows,
        )

        detail = accounts[0]['detail']
        self.assertEqual(detail['service_count'], 2)
        self.assertEqual(detail['primary_service_name'], 'ECS')
        self.assertGreater(detail['primary_service_share'], 60)
        self.assertEqual(len(detail['trend_30d']), 2)
        self.assertEqual(detail['service_breakdown_currency'], 'CNY')
        self.assertEqual(detail['service_breakdown_source'], 'recent_rows')
        self.assertTrue(detail['service_breakdown_complete'])
        self.assertEqual(detail['service_breakdown_coverage'], 100.0)
        self.assertEqual(len(detail['trend_series']), 2)
        self.assertIn('recommended_recharge', detail)
        self.assertEqual(detail['recommended_window_days'], 30)

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_small_services_are_grouped_into_other_series(self, mock_balance_support):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=24,
            provider_type='alibaba',
            display_name='阿里云',
            tags=[],
            notes='',
            config={},
            balance=Decimal('1200.00'),
            balance_currency='CNY',
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-4',
                total_cost=Decimal('300.00'),
                currency='CNY',
                service_costs={
                    'ECS': Decimal('240.00'),
                    'OSS': Decimal('45.00'),
                    'CDN': Decimal('9.00'),
                    'DNS': Decimal('6.00'),
                },
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=24,
                account_id='acct-4',
                hourly_cost=Decimal('30.00'),
                collected_at=datetime(2026, 3, 25, 0, 0, tzinfo=dt_timezone.utc),
                period='2026-03',
                service_costs={
                    'ECS': Decimal('24.00'),
                    'OSS': Decimal('4.50'),
                    'CDN': Decimal('0.90'),
                    'DNS': Decimal('0.60'),
                },
            ),
        ]

        accounts = _build_accounts(
            latest_billings,
            daily_rows,
            recent_rows=daily_rows,
        )

        detail = accounts[0]['detail']
        series_names = [item['name'] for item in detail['trend_series']]
        self.assertIn('__other__', series_names)
        self.assertNotIn('CDN', series_names)
        self.assertNotIn('DNS', series_names)

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_account_detail_marks_latest_billing_fallback_service_breakdown(
        self,
        mock_balance_support,
    ):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=25,
            provider_type='aws',
            display_name='AWS',
            tags=[],
            notes='',
            config={},
            balance=Decimal('0'),
            balance_currency='USD',
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-5',
                total_cost=Decimal('200.00'),
                currency='USD',
                service_costs={
                    'EC2': Decimal('120.00'),
                    'S3': Decimal('40.00'),
                },
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=25,
                account_id='acct-5',
                hourly_cost=Decimal('20.00'),
                collected_at=datetime(2026, 3, 25, 0, 0, tzinfo=dt_timezone.utc),
                service_costs={},
            ),
        ]

        accounts = _build_accounts(
            latest_billings,
            daily_rows,
            recent_rows=daily_rows,
        )

        detail = accounts[0]['detail']
        self.assertEqual(detail['service_breakdown_currency'], 'USD')
        self.assertEqual(detail['service_breakdown_source'], 'latest_billing')
        self.assertFalse(detail['service_breakdown_complete'])
        self.assertFalse(detail['service_breakdown_has_recent_rows'])
        self.assertEqual(detail['service_breakdown_coverage'], 80.0)

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_account_detail_uses_previous_monthly_snapshot_as_service_baseline(
        self,
        mock_balance_support,
    ):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=26,
            provider_type='alibaba',
            display_name='阿里云',
            tags=[],
            notes='',
            config={},
            balance=Decimal('1000.00'),
            balance_currency='CNY',
        )
        latest_billing = SimpleNamespace(
            provider=provider,
            account_id='acct-6',
            total_cost=Decimal('500.00'),
            currency='CNY',
            service_costs={'SLB': Decimal('220.00'), 'ECS': Decimal('280.00')},
        )
        monthly_rows = [
            SimpleNamespace(
                provider_id=26,
                account_id='acct-6',
                period='2026-03',
                hour=7,
                collected_at=datetime(2026, 3, 20, 7, 0, tzinfo=dt_timezone.utc),
                service_costs={'SLB': Decimal('100.00'), 'ECS': Decimal('140.00')},
            ),
            SimpleNamespace(
                provider_id=26,
                account_id='acct-6',
                period='2026-03',
                hour=8,
                collected_at=datetime(2026, 3, 20, 8, 0, tzinfo=dt_timezone.utc),
                hourly_cost=Decimal('30.00'),
                service_costs={'SLB': Decimal('120.00'), 'ECS': Decimal('150.00')},
            ),
            SimpleNamespace(
                provider_id=26,
                account_id='acct-6',
                period='2026-03',
                hour=9,
                collected_at=datetime(2026, 3, 21, 9, 0, tzinfo=dt_timezone.utc),
                hourly_cost=Decimal('40.00'),
                service_costs={'SLB': Decimal('150.00'), 'ECS': Decimal('160.00')},
            ),
        ]

        detail = _build_account_detail(
            latest_billing,
            monthly_rows,
            recent_rows=monthly_rows[1:],
            display_funds=1000.0,
            daily_burn=35.0,
            days_remaining=20,
            payment_type='prepaid',
            selected_currency='CNY',
        )

        breakdown = {
            item['name']: item['value'] for item in detail['service_breakdown']
        }
        self.assertEqual(breakdown['SLB'], 50.0)
        self.assertEqual(breakdown['ECS'], 20.0)
        self.assertEqual(detail['service_breakdown_coverage'], 100.0)

    @patch('cloud_billing.dashboard.get_balance_support_info')
    def test_daily_average_uses_active_billing_days_for_account(
        self,
        mock_balance_support,
    ):
        mock_balance_support.return_value = {'supported': True}

        provider = SimpleNamespace(
            id=27,
            provider_type='alibaba',
            display_name='阿里云',
            tags=[],
            notes='',
            config={},
            balance=Decimal('300.00'),
            balance_currency='CNY',
        )
        latest_billings = [
            SimpleNamespace(
                provider=provider,
                account_id='acct-7',
                total_cost=Decimal('90.00'),
                currency='CNY',
                service_costs={'ECS': Decimal('90.00')},
            )
        ]
        daily_rows = [
            SimpleNamespace(
                provider_id=27,
                account_id='acct-7',
                hourly_cost=Decimal('30.00'),
                collected_at=datetime(2026, 3, 2, 8, 0, tzinfo=dt_timezone.utc),
                period='2026-03',
                hour=8,
                service_costs={'ECS': Decimal('30.00')},
            ),
            SimpleNamespace(
                provider_id=27,
                account_id='acct-7',
                hourly_cost=Decimal('60.00'),
                collected_at=datetime(2026, 3, 5, 8, 0, tzinfo=dt_timezone.utc),
                period='2026-03',
                hour=8,
                service_costs={'ECS': Decimal('90.00')},
            ),
        ]

        accounts = _build_accounts(
            latest_billings,
            daily_rows,
            recent_rows=daily_rows,
            local_tz=dt_timezone.utc,
            now=datetime(2026, 3, 20, 0, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(accounts[0]['detail']['daily_average'], 45.0)
        self.assertEqual(accounts[0]['change'], 45.0)


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
