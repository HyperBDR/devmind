from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from llm_ops.models import (
    ChannelOffering,
    ChannelPriceItem,
    ChannelPriceVersion,
    LLMModel,
    LLMProvider,
    MetaModel,
    ModelPriceItem,
    ProcurementChannel,
    UsageReconciliationRecord,
)
from llm_ops.services import calculate_channel_model_cost


class ChannelPriceContractTests(TestCase):
    """Exercise version, time, discount, exchange, and snapshot contracts."""

    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username="contract-ops",
            password="secret",
            is_staff=True,
        )
        self.client.force_authenticate(user)
        provider = LLMProvider.objects.create(
            name="OpenAI",
            code="openai-contract-tests",
        )
        meta_model = MetaModel.objects.create(
            name="GPT-5 Contract",
            code="gpt-5-contract-tests",
        )
        self.model = LLMModel.objects.create(
            provider=provider,
            meta_model=meta_model,
            name="GPT-5 Contract",
            code="gpt-5-contract-tests",
        )
        self.channel = ProcurementChannel.objects.create(
            name="Contract Supplier",
            code="contract-supplier-tests",
        )
        self.offering = ChannelOffering.objects.create(
            channel=self.channel,
            meta_model=meta_model,
            model=self.model,
            offering_key="contract-sku",
            display_name="Contract SKU",
        )

    def test_future_version_resolves_only_after_effective_time(self):
        now = timezone.now().replace(microsecond=0)
        current = self._create_version(
            version=1,
            effective_from=now - timedelta(days=1),
            effective_to=now + timedelta(hours=1),
            unit_price="1",
        )
        future = self._create_version(
            version=2,
            status=ChannelPriceVersion.STATUS_SCHEDULED,
            effective_from=now + timedelta(hours=1),
            unit_price="2",
        )

        before = calculate_channel_model_cost(
            self.channel,
            self.model,
            offering=self.offering,
            occurred_at=now,
            input_tokens=1_000_000,
        )
        after = calculate_channel_model_cost(
            self.channel,
            self.model,
            offering=self.offering,
            occurred_at=now + timedelta(hours=2),
            input_tokens=1_000_000,
        )

        self.assertEqual(before, Decimal("1.000000"))
        self.assertEqual(after, Decimal("2.000000"))
        self.assertEqual(current.price_items.count(), 1)
        self.assertEqual(future.price_items.count(), 1)

    def test_time_windows_support_timezone_and_cross_midnight(self):
        occurred_at = datetime(
            2026,
            8,
            18,
            13,
            0,
            tzinfo=dt_timezone.utc,
        )
        self._create_version(
            version=1,
            effective_from=occurred_at - timedelta(days=1),
            unit_price="1",
            timezone_name="Asia/Shanghai",
            price_items=[
                self._price_item(
                    "1",
                    start="08:00",
                    end="20:00",
                ),
                self._price_item(
                    "3",
                    start="20:00",
                    end="08:00",
                ),
            ],
        )

        night_cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            offering=self.offering,
            occurred_at=occurred_at,
            input_tokens=1_000_000,
        )
        day_cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            offering=self.offering,
            occurred_at=occurred_at - timedelta(hours=12),
            input_tokens=1_000_000,
        )
        with self.assertLogs("llm_ops.tier_pricing", level="WARNING"):
            missing_time_cost = calculate_channel_model_cost(
                self.channel,
                self.model,
                offering=self.offering,
                input_tokens=1_000_000,
            )

        self.assertEqual(night_cost, Decimal("3.000000"))
        self.assertEqual(day_cost, Decimal("1.000000"))
        self.assertEqual(missing_time_cost, Decimal("3.000000"))

    def test_discount_and_contract_exchange_rate_are_applied(self):
        now = timezone.now()
        self._create_version(
            version=1,
            effective_from=now - timedelta(hours=1),
            unit_price="10",
            discount_type=ChannelPriceVersion.DISCOUNT_RATIO,
            discount_value="0.8",
            contract_currency="CNY",
            contract_exchange_rate="7",
            exchange_rate_effective_from=now - timedelta(days=1),
            exchange_rate_effective_to=now + timedelta(days=1),
        )

        cost = calculate_channel_model_cost(
            self.channel,
            self.model,
            offering=self.offering,
            occurred_at=now,
            input_tokens=1_000_000,
        )

        self.assertEqual(cost, Decimal("56.000000"))

    def test_overlapping_versions_fall_back_to_highest_cost_with_warning(self):
        now = timezone.now()
        self._create_version(
            version=1,
            effective_from=now - timedelta(hours=1),
            unit_price="1",
        )
        self._create_version(
            version=2,
            effective_from=now - timedelta(minutes=30),
            unit_price="3",
        )

        with self.assertLogs("llm_ops.services", level="WARNING"):
            cost = calculate_channel_model_cost(
                self.channel,
                self.model,
                offering=self.offering,
                occurred_at=now,
                input_tokens=1_000_000,
            )

        self.assertEqual(cost, Decimal("3.000000"))

    def test_reconciliation_persists_resolution_snapshot(self):
        now = timezone.now()
        version = self._create_version(
            version=1,
            effective_from=now - timedelta(hours=1),
            unit_price="2",
            contract_exchange_rate="7",
            contract_currency="CNY",
        )

        response = self.client.post(
            reverse("reconciliation-record-list"),
            {
                "date": now.date().isoformat(),
                "business_occurred_at": now.isoformat(),
                "business_timezone": "Asia/Shanghai",
                "channel": self.channel.id,
                "model": self.model.id,
                "offering": self.offering.id,
                "input_tokens": 1_000_000,
                "charged_amount": "14",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        record = UsageReconciliationRecord.objects.get()
        self.assertEqual(record.price_version, version)
        self.assertEqual(record.exchange_rate_snapshot, Decimal("7"))
        self.assertEqual(record.exchange_rate_source, "contract")
        self.assertEqual(record.final_price_snapshot, Decimal("14"))
        self.assertEqual(
            record.unit_price_snapshot["text_input"],
            "14.000000",
        )

        item = ChannelPriceItem.objects.get(price_version=version)
        item.unit_price = Decimal("99")
        item.save(update_fields=["unit_price"])
        record.refresh_from_db()
        self.assertEqual(record.final_price_snapshot, Decimal("14"))

    def _create_version(
        self,
        *,
        version,
        effective_from,
        unit_price=None,
        price_items=None,
        status=ChannelPriceVersion.STATUS_ACTIVE,
        effective_to=None,
        timezone_name="UTC",
        **extra,
    ):
        items = price_items or [self._price_item(unit_price)]
        payload = {
            "offering": self.offering.id,
            "model": self.model.id,
            "version": version,
            "status": status,
            "effective_from": effective_from.isoformat(),
            "effective_to": (
                effective_to.isoformat() if effective_to else None
            ),
            "timezone": timezone_name,
            "price_items": items,
            **extra,
        }
        response = self.client.post(
            reverse("channel-price-version-list"),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return ChannelPriceVersion.objects.get(pk=response.data["id"])

    def _price_item(self, unit_price, *, start=None, end=None):
        spec = {}
        if start and end:
            spec["time_windows"] = [
                {
                    "weekdays": list(range(7)),
                    "start": start,
                    "end": end,
                }
            ]
        return {
            "dimension": ModelPriceItem.DIMENSION_TEXT_INPUT,
            "billing_unit": ModelPriceItem.UNIT_PER_1M_TOKENS,
            "currency": "USD",
            "unit_price": unit_price,
            "tier_type": ModelPriceItem.TIER_FLAT,
            "spec": spec,
        }
