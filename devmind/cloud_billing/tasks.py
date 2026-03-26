"""
Celery tasks for cloud billing collection and alert checking.
"""

import logging
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from celery import shared_task
from celery import current_task
from django.db import transaction
from django.utils import timezone

from agentcore_notifier.adapters.django.services.webhook_service import (
    get_default_webhook_channel,
)
from agentcore_task.adapters.django import (
    prevent_duplicate_task,
    TaskLogCollector,
    TaskStatus,
    TaskTracker,
)

from .constants import (
    WEBHOOK_STATUS_FAILED,
    WEBHOOK_STATUS_PENDING,
    WEBHOOK_STATUS_SUCCESS,
)
from .models import AlertRecord, AlertRule, BillingData, CloudProvider
from .services.notification_service import CloudBillingNotificationService
from .services.provider_service import ProviderService

logger = logging.getLogger(__name__)


def _is_chinese_language(language: str) -> bool:
    return str(language or "").lower().startswith("zh")


def _extract_provider_notes(provider: CloudProvider) -> str:
    direct_notes = (getattr(provider, "notes", "") or "").strip()
    if direct_notes:
        return direct_notes

    config = getattr(provider, "config", {}) or {}
    for key in ("notes", "note", "remark", "remarks", "description"):
        value = (config.get(key) or "").strip() if isinstance(config, dict) else ""
        if value:
            return value
    return ""


def _build_alert_message(
    *,
    provider_name: str,
    provider_notes: str,
    account_id: str,
    current_cost: Decimal,
    previous_cost: Decimal,
    increase_cost: Decimal,
    increase_percent: Decimal,
    current_balance: Decimal | None,
    currency: str,
    alert_rule: AlertRule,
    cost_threshold_triggered: bool,
    balance_threshold_triggered: bool,
    language: str,
) -> str:
    if _is_chinese_language(language):
        lines = [f"云平台：{provider_name}"]
        if account_id:
            lines.append(f"账号：{account_id}")
        if provider_notes:
            lines.append(f"备注：{provider_notes}")

        if balance_threshold_triggered:
            lines.insert(0, "告警类型：余额阈值告警")
            lines.append(f"当前余额：{current_balance:.2f} {currency}")
            lines.append(
                f"告警阈值：{alert_rule.balance_threshold:.2f} {currency}"
            )
            lines.append("告警说明：账户剩余余额低于设定阈值")
            return "\n".join(lines)

        if cost_threshold_triggered:
            lines.insert(0, "告警类型：费用阈值告警")
            lines.append(f"当前总费用：{current_cost:.2f} {currency}")
            lines.append(
                f"告警阈值：{alert_rule.cost_threshold:.2f} {currency}"
            )
            lines.append(f"上一小时费用：{previous_cost:.2f} {currency}")
            lines.append("告警说明：当前总费用已超过设定阈值")
            return "\n".join(lines)

        lines.insert(0, "告警类型：费用增长告警")
        lines.append(f"当前总费用：{current_cost:.2f} {currency}")
        lines.append(f"上一小时费用：{previous_cost:.2f} {currency}")
        lines.append(f"增长金额：{increase_cost:.2f} {currency}")
        lines.append(f"增长比例：{increase_percent:.2f}%")
        if alert_rule.growth_threshold is not None:
            lines.append(f"百分比阈值：{alert_rule.growth_threshold:.2f}%")
        if alert_rule.growth_amount_threshold is not None:
            lines.append(
                f"金额阈值：{alert_rule.growth_amount_threshold:.2f} {currency}"
            )
        lines.append("告警说明：费用增长超过设定阈值")
        return "\n".join(lines)

    account_suffix = f" (Account: {account_id})" if account_id else ""
    notes_suffix = f"\nNotes: {provider_notes}" if provider_notes else ""
    if balance_threshold_triggered:
        return (
            f"{provider_name}{account_suffix} remaining balance "
            f"{current_balance:.2f} {currency} is below threshold "
            f"{alert_rule.balance_threshold:.2f} {currency}"
            f"{notes_suffix}"
        )
    if cost_threshold_triggered:
        return (
            f"{provider_name}{account_suffix} current total cost "
            f"{current_cost:.2f} {currency} exceeds threshold "
            f"{alert_rule.cost_threshold:.2f} {currency}\n"
            f"Previous hour cost: {previous_cost:.2f} {currency}"
            f"{notes_suffix}"
        )
    return (
        f"{provider_name}{account_suffix} account billing increased by "
        f"{increase_cost:.2f} {currency} in the last hour, growth rate: "
        f"{increase_percent:.2f}%\n"
        f"Current cost: {current_cost:.2f} {currency}\n"
        f"Previous hour cost: {previous_cost:.2f} {currency}"
        f"{notes_suffix}"
    )


@shared_task(name="cloud_billing.tasks.collect_billing_data")
@prevent_duplicate_task(
    "collect_billing_data", lock_param="user_id", timeout=3600
)
def collect_billing_data(
    provider_id: Optional[int] = None, user_id: Optional[int] = None
):
    """
    Collect billing data for cloud providers.

    Args:
        provider_id: Optional provider ID to collect for specific provider.
                     If None, collects for all active providers.
        user_id: Optional user ID for per-user task locking.
                 If None, uses system user (0) for scheduled tasks.

    Returns:
        Dictionary with collection results
    """
    task_id = current_task.request.id if current_task else None

    # Use system user (0) for scheduled tasks if user_id is None
    if user_id is None:
        user_id = 0

    # Set up simple log collector for this task
    log_collector = TaskLogCollector(max_records=1000)

    # Register task in agentcore_task if not already registered
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="cloud_billing.tasks.collect_billing_data",
            module="cloud_billing",
            task_kwargs={"provider_id": provider_id, "user_id": user_id},
            metadata={"provider_id": provider_id, "user_id": user_id},
        )
        TaskTracker.update_task_status(
            task_id=task_id, status=TaskStatus.STARTED
        )

    log_collector.info(
        f"Task collect_billing_data: Starting billing data collection "
        f"(provider_id={provider_id}, user_id={user_id}, task_id={task_id})"
    )
    logger.info(
        f"Task collect_billing_data: Starting billing data collection "
        f"(provider_id={provider_id}, user_id={user_id}, task_id={task_id})"
    )

    results = {
        "success": [],
        "failed": [],
        "total": 0,
    }

    try:
        if provider_id:
            providers = CloudProvider.objects.filter(
                id=provider_id, is_active=True
            )
        else:
            providers = CloudProvider.objects.filter(is_active=True)

        if not providers.exists():
            warning_msg = (
                f"Task collect_billing_data: No active providers found "
                f"(provider_id={provider_id})"
            )
            log_collector.warning(warning_msg)
            logger.warning(f"{warning_msg}")
            if task_id:
                all_logs = log_collector.get_logs()
                warnings_and_errors = log_collector.get_warnings_and_errors()
                log_summary = log_collector.get_summary()
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.SUCCESS,
                    result=results,
                    metadata={
                        "logs": all_logs,
                        "warnings_and_errors": warnings_and_errors,
                        "log_summary": log_summary,
                    },
                )
            return results

        provider_service = ProviderService()
        now = timezone.now()
        current_period = now.strftime("%Y-%m")
        current_hour = now.hour

        for provider in providers:
            try:
                info_msg = (
                    f"Task collect_billing_data: Processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, "
                    f"display_name={provider.display_name})"
                )
                log_collector.info(info_msg)
                logger.info(f"{info_msg}")

                config_dict = provider.config

                # Check if config is None, empty dict, or missing required
                # fields
                is_empty_dict = (
                    isinstance(config_dict, dict) and len(config_dict) == 0
                )
                if not config_dict or is_empty_dict:
                    warning_msg = (
                        f"Task collect_billing_data: Provider has no config "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type})"
                    )
                    log_collector.warning(warning_msg)
                    logger.warning(f"{warning_msg}")
                    results["failed"].append(
                        {
                            "provider": provider.name,
                            "error": (
                                "No configuration found. "
                                "Please configure the provider first."
                            ),
                        }
                    )
                    continue

                # get_billing_info will normalize the config internally
                billing_info = provider_service.get_billing_info(
                    provider.provider_type, config_dict, period=current_period
                )

                if billing_info.get("status") not in (
                    "success",
                    "partial_success",
                ):
                    error_msg = billing_info.get("error", "Unknown error")
                    error_log = (
                        f"Task collect_billing_data: Failed to get billing "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type}, "
                        f"period={current_period}, error={error_msg})"
                    )
                    log_collector.error(error_log)
                    logger.error(f"{error_log}")
                    results["failed"].append(
                        {"provider": provider.name, "error": error_msg}
                    )
                    continue

                billing_data = billing_info.get("data", {})
                billing_status = billing_info.get("status")
                cost_status = billing_data.get("cost_status", "success")
                total_cost = Decimal(str(billing_data.get("total_cost", 0)))
                balance_raw = billing_data.get("balance")
                balance = (
                    Decimal(str(balance_raw))
                    if balance_raw is not None
                    else None
                )
                balance_debug = billing_data.get("balance_debug") or {}
                currency = billing_data.get("currency", "USD")
                service_costs = billing_data.get("service_costs", {})
                account_id = billing_data.get("account_id", "")

                if billing_status == "partial_success" or cost_status != "success":
                    previous_total_cost = (
                        BillingData.objects.filter(
                            provider=provider,
                            account_id=account_id,
                            period=current_period,
                        )
                        .order_by("-hour", "-collected_at")
                        .values_list("total_cost", flat=True)
                        .first()
                    )
                    if previous_total_cost is not None:
                        total_cost = previous_total_cost

                    cost_error = billing_data.get("cost_error") or billing_info.get(
                        "error"
                    )
                    log_collector.warning(
                        f"Task collect_billing_data: Cost query partially failed "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type}, period={current_period}, "
                        f"using_total_cost={total_cost}, cost_error={cost_error})"
                    )

                if provider.provider_type in (
                    "alibaba",
                    "aws",
                    "azure",
                    "huawei",
                    "huawei-intl",
                    "tencentcloud",
                    "volcengine",
                    "baidu",
                    "zhipu",
                ):
                    log_collector.warning(
                        f"{provider.provider_type.upper()} balance debug "
                        f"(provider_id={provider.id}, account_id={account_id}, "
                        f"balance={balance}, balance_debug={balance_debug})"
                    )

                # Calculate hourly incremental cost
                # Rule: If this month has no data yet, hourly_cost = total_cost
                # Otherwise, calculate increment from previous hour
                has_data_this_period = BillingData.objects.filter(
                    provider=provider, period=current_period
                ).exists()

                if not has_data_this_period:
                    # First collection for this month,
                    # hourly_cost equals total_cost
                    hourly_cost = total_cost
                else:
                    # This month has data, try to get previous hour's record
                    previous_hour = current_hour - 1
                    previous_period = current_period

                    # Handle cross-month case
                    # (hour 0 -> previous month hour 23)
                    if previous_hour < 0:
                        previous_hour = 23
                        prev_date = timezone.now() - timedelta(days=1)
                        previous_period = prev_date.strftime("%Y-%m")

                    try:
                        previous_billing = BillingData.objects.get(
                            provider=provider,
                            account_id=account_id,
                            period=previous_period,
                            hour=previous_hour,
                        )
                        # Calculate incremental cost: current - previous
                        hourly_cost = total_cost - previous_billing.total_cost
                        # Ensure hourly_cost is not negative (safety check)
                        if hourly_cost < 0:
                            hourly_cost = Decimal("0")
                    except BillingData.DoesNotExist:
                        # Previous hour not found, use total_cost as fallback
                        # This should rarely happen if data collection
                        # is regular
                        hourly_cost = total_cost

                with transaction.atomic():
                    billing_record, created = (
                        BillingData.objects.get_or_create(
                            provider=provider,
                            account_id=account_id,
                            period=current_period,
                            hour=current_hour,
                            defaults={
                                "total_cost": total_cost,
                                "balance": balance,
                                "hourly_cost": hourly_cost,
                                "currency": currency,
                                "service_costs": service_costs,
                            },
                        )
                    )

                    if not created:
                        # Update existing billing record with latest data
                        billing_record.total_cost = total_cost
                        billing_record.balance = balance
                        billing_record.hourly_cost = hourly_cost
                        billing_record.currency = currency
                        billing_record.service_costs = service_costs
                        billing_record.account_id = account_id

                        # Update collected_at to reflect the latest
                        # collection time
                        billing_record.collected_at = timezone.now()

                        # Explicitly specify update_fields to ensure
                        # collected_at is updated
                        billing_record.save(
                            update_fields=[
                                "total_cost",
                                "balance",
                                "hourly_cost",
                                "currency",
                                "service_costs",
                                "account_id",
                                "collected_at",
                            ]
                        )
                        info_msg = (
                            f"Task collect_billing_data: Updated existing "
                            f"billing data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"balance={balance}, "
                            f"hourly_cost={hourly_cost}, currency={currency}, "
                            f"account_id={account_id})"
                        )
                        log_collector.info(info_msg)
                        logger.info(f"{info_msg}")
                    else:
                        info_msg = (
                            f"Task collect_billing_data: Created new billing "
                            f"data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"balance={balance}, "
                            f"hourly_cost={hourly_cost}, currency={currency}, "
                            f"account_id={account_id})"
                        )
                        log_collector.info(info_msg)
                        logger.info(f"{info_msg}")

                results["success"].append(
                    {
                        "provider": provider.name,
                        "total_cost": float(total_cost),
                        "balance": float(balance) if balance is not None else None,
                        "currency": currency,
                    }
                )

                check_alert_for_provider.delay(
                    provider.id,
                    provider.provider_type,
                )

            except Exception as e:
                error_traceback = traceback.format_exc()
                error_msg = (
                    f"Task collect_billing_data: Error processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, error={str(e)})"
                )
                log_collector.error(error_msg, exception=error_traceback)
                logger.error(f"{error_msg}", exc_info=True)
                results["failed"].append(
                    {"provider": provider.name, "error": str(e)}
                )

        results["total"] = len(results["success"]) + len(results["failed"])
        task_status = TaskStatus.SUCCESS
        task_error = None
        if results["success"]:
            if results["failed"]:
                results["warning"] = (
                    f"{len(results['failed'])} provider(s) failed "
                    f"during this collection run"
                )
        elif results["failed"]:
            task_status = TaskStatus.FAILURE
            task_error = (
                "Billing collection failed for all providers "
                f"(failed={len(results['failed'])})"
            )
            results["error"] = task_error

        info_msg = (
            f"Task collect_billing_data: Billing collection completed "
            f"(provider_id={provider_id}, total={results['total']}, "
            f"success={len(results['success'])}, "
            f"failed={len(results['failed'])})"
        )
        log_collector.info(info_msg)
        logger.info(f"{info_msg}")

        # Save logs to task metadata
        if task_id:
            all_logs = log_collector.get_logs()
            warnings_and_errors = log_collector.get_warnings_and_errors()
            log_summary = log_collector.get_summary()

            TaskTracker.update_task_status(
                task_id=task_id,
                status=task_status,
                result=results,
                error=task_error,
                metadata={
                    "logs": all_logs,
                    "warnings_and_errors": warnings_and_errors,
                    "log_summary": log_summary,
                },
            )

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        error_log = (
            f"Task collect_billing_data: Error in billing collection "
            f"(provider_id={provider_id}, error={error_msg})"
        )
        log_collector.error(error_log, exception=error_traceback)
        logger.error(f"{error_log}", exc_info=True)
        results["error"] = error_msg

        # Save logs to task metadata
        if task_id:
            try:
                all_logs = log_collector.get_logs()
                warnings_and_errors = log_collector.get_warnings_and_errors()
                log_summary = log_collector.get_summary()

                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILURE,
                    result=results,
                    error=error_msg,
                    traceback=error_traceback,
                    metadata={
                        "logs": all_logs,
                        "warnings_and_errors": warnings_and_errors,
                        "log_summary": log_summary,
                    },
                )
            except Exception as log_error:
                logger.error(
                    f"Failed to save logs for task {task_id}: {str(log_error)}"
                )
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILURE,
                    result=results,
                    error=error_msg,
                    traceback=error_traceback,
                )

    return results


@shared_task(name="cloud_billing.tasks.check_alert_for_provider")
@prevent_duplicate_task(
    "check_alert_for_provider", lock_param="provider_id", timeout=600
)
def check_alert_for_provider(
    provider_id: int, provider_name: Optional[str] = None
):
    """
    Check alert rules for a specific provider.

    Args:
        provider_id: Provider ID to check alerts for
        provider_name: Optional provider type for task naming

    Returns:
        Dictionary with alert check results
    """
    task_id = current_task.request.id if current_task else None

    # Register task in agentcore_task if not already registered
    if task_id:
        task_display_name = (
            "cloud_billing.tasks.check_alert_for_provider"
            f" ({provider_name})"
            if provider_name
            else (
                "cloud_billing.tasks.check_alert_for_provider "
                f"(provider_id={provider_id})"
            )
        )
        TaskTracker.register_task(
            task_id=task_id,
            task_name=task_display_name,
            module="cloud_billing",
            task_kwargs={
                "provider_id": provider_id,
                "provider_name": provider_name,
            },
            metadata={
                "provider_id": provider_id,
                "provider_name": provider_name,
            },
        )
        TaskTracker.update_task_status(
            task_id=task_id, status=TaskStatus.STARTED
        )

    logger.info(
        f"Task check_alert_for_provider: Checking alerts "
        f"(provider_id={provider_id}, task_id={task_id})"
    )

    try:
        provider = CloudProvider.objects.get(id=provider_id)

        try:
            alert_rule = AlertRule.objects.get(
                provider=provider, is_active=True
            )
        except AlertRule.DoesNotExist:
            logger.info(
                f"Task check_alert_for_provider: No active alert rule found "
                f"(provider_id={provider.id}, name={provider.name}, "
                f"type={provider.provider_type})"
            )
            result = {"checked": False, "reason": "No active alert rule"}
            if task_id:
                TaskTracker.update_task_status(
                    task_id=task_id, status=TaskStatus.SUCCESS, result=result
                )
            return result

        now = timezone.now()
        current_period = now.strftime("%Y-%m")
        current_hour = now.hour

        # Get all current billing records for this provider
        # (may have multiple accounts)
        current_billings = BillingData.objects.filter(
            provider=provider, period=current_period, hour=current_hour
        )

        if not current_billings.exists():
            logger.warning(
                f"Task check_alert_for_provider: No current billing data "
                f"found (provider_id={provider.id}, name={provider.name}, "
                f"period={current_period}, hour={current_hour})"
            )
            result = {"checked": False, "reason": "No current billing data"}
            if task_id:
                TaskTracker.update_task_status(
                    task_id=task_id, status=TaskStatus.SUCCESS, result=result
                )
            return result

        previous_hour = current_hour - 1
        previous_period = current_period

        if previous_hour < 0:
            previous_hour = 23
            prev_date = timezone.now() - timedelta(days=1)
            previous_period = prev_date.strftime("%Y-%m")

        # Check alerts for each account_id separately
        alerts_created = []
        for current_billing in current_billings:
            account_id = current_billing.account_id or ""

            current_cost = Decimal(str(current_billing.total_cost))
            current_balance = (
                Decimal(str(current_billing.balance))
                if current_billing.balance is not None
                else None
            )
            previous_billing = None
            previous_cost = Decimal("0")
            try:
                previous_billing = BillingData.objects.get(
                    provider=provider,
                    account_id=account_id,
                    period=previous_period,
                    hour=previous_hour,
                )
                previous_cost = Decimal(str(previous_billing.total_cost))
            except BillingData.DoesNotExist:
                logger.info(
                    f"Task check_alert_for_provider: "
                    f"No previous billing data found "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"account_id={account_id}, period={previous_period}, "
                    f"hour={previous_hour})"
                )

            if previous_cost <= 0 and current_balance is None:
                logger.info(
                    f"Task check_alert_for_provider: "
                    f"Previous cost is zero or negative "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"account_id={account_id}, "
                    f"previous_cost={previous_cost}, "
                    f"period={previous_period}, hour={previous_hour})"
                )
                continue

            increase_cost = current_cost - previous_cost
            increase_percent = Decimal("0")
            if previous_cost > 0:
                increase_percent = (increase_cost / previous_cost) * 100
            should_alert = False
            alert_reason = []
            cost_threshold_triggered = False

            # Cost threshold is absolute and should not depend on a previous
            # billing record. Growth-based rules still need the previous hour.
            if alert_rule.cost_threshold is not None:
                cost_threshold_decimal = Decimal(
                    str(alert_rule.cost_threshold)
                )
                if current_cost > cost_threshold_decimal:
                    should_alert = True
                    cost_threshold_triggered = True
                    alert_reason.append(
                        f"Current cost {current_cost} exceeds threshold "
                        f"{alert_rule.cost_threshold}"
                    )
                    logger.info(
                        f"Task check_alert_for_provider: "
                        f"Cost threshold exceeded "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"account_id={account_id}, "
                        f"current_cost={current_cost}, "
                        f"cost_threshold={alert_rule.cost_threshold})"
                    )

            needs_previous_billing = (
                alert_rule.growth_threshold is not None
                or alert_rule.growth_amount_threshold is not None
            )
            if needs_previous_billing:
                try:
                    previous_billing = BillingData.objects.get(
                        provider=provider,
                        account_id=account_id,
                        period=previous_period,
                        hour=previous_hour,
                    )
                except BillingData.DoesNotExist:
                    logger.info(
                        f"Task check_alert_for_provider: "
                        f"No previous billing data found "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"account_id={account_id}, period={previous_period}, "
                        f"hour={previous_hour})"
                    )
                    if not should_alert:
                        continue

                if previous_billing is not None:
                    previous_cost = Decimal(str(previous_billing.total_cost))
                    if previous_cost <= 0:
                        logger.info(
                            f"Task check_alert_for_provider: "
                            f"Previous cost is zero or negative "
                            f"(provider_id={provider.id}, name={provider.name}, "
                            f"account_id={account_id}, "
                            f"previous_cost={previous_cost}, "
                            f"period={previous_period}, hour={previous_hour})"
                        )
                        if not cost_threshold_triggered:
                            continue

            if previous_billing is not None and previous_cost > 0:
                increase_cost = current_cost - previous_cost
                increase_percent = (increase_cost / previous_cost) * 100

            # Check growth threshold
            if alert_rule.growth_threshold is not None and previous_billing:
                growth_threshold_decimal = Decimal(
                    str(alert_rule.growth_threshold)
                )
                if increase_percent > growth_threshold_decimal:
                    should_alert = True
                    alert_reason.append(
                        f"Growth {increase_percent:.2f}% exceeds threshold "
                        f"{alert_rule.growth_threshold}%"
                    )
                    logger.info(
                        f"Task check_alert_for_provider: "
                        f"Growth threshold exceeded "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"account_id={account_id}, "
                        f"increase_percent={increase_percent:.2f}, "
                        f"growth_threshold={alert_rule.growth_threshold})"
                    )

            # Check growth amount threshold
            if alert_rule.growth_amount_threshold is not None and previous_billing:
                growth_amount_threshold_decimal = Decimal(
                    str(alert_rule.growth_amount_threshold)
                )
                if increase_cost > growth_amount_threshold_decimal:
                    should_alert = True
                    alert_reason.append(
                        f"Growth amount {increase_cost:.2f} exceeds "
                        f"threshold {alert_rule.growth_amount_threshold}"
                    )
                    logger.info(
                        f"Task check_alert_for_provider: "
                        f"Growth amount threshold exceeded "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"account_id={account_id}, "
                        f"increase_cost={increase_cost:.2f}, "
                        f"growth_amount_threshold="
                        f"{alert_rule.growth_amount_threshold})"
                    )

            if (
                alert_rule.balance_threshold is not None
                and current_balance is not None
            ):
                balance_threshold_decimal = Decimal(
                    str(alert_rule.balance_threshold)
                )
                if current_balance < balance_threshold_decimal:
                    should_alert = True
                    alert_reason.append(
                        f"Current balance {current_balance:.2f} is below "
                        f"threshold {alert_rule.balance_threshold}"
                    )
                    logger.info(
                        f"Task check_alert_for_provider: "
                        f"Balance threshold triggered "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"account_id={account_id}, "
                        f"current_balance={current_balance:.2f}, "
                        f"balance_threshold={alert_rule.balance_threshold})"
                    )

            if not should_alert:
                logger.info(
                    f"Task check_alert_for_provider: No alert triggered "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"account_id={account_id}, current_cost={current_cost}, "
                    f"previous_cost={previous_cost}, "
                    f"increase_cost={increase_cost}, "
                    f"increase_percent={increase_percent:.2f})"
                )
                continue

            language = "en"
            try:
                channel, _config = get_default_webhook_channel()
                if channel and isinstance(channel.config, dict):
                    language = channel.config.get("language", "en")
            except Exception:
                pass

            # Generate alert message based on trigger reason
            cost_threshold_triggered = any(
                "Current cost" in reason for reason in alert_reason
            )
            balance_threshold_triggered = any(
                "Current balance" in reason for reason in alert_reason
            )
            alert_message = _build_alert_message(
                provider_name=provider.display_name,
                provider_notes=_extract_provider_notes(provider),
                account_id=account_id,
                current_cost=current_cost,
                previous_cost=previous_cost,
                increase_cost=increase_cost,
                increase_percent=increase_percent,
                current_balance=current_balance,
                currency=current_billing.currency,
                alert_rule=alert_rule,
                cost_threshold_triggered=cost_threshold_triggered,
                balance_threshold_triggered=balance_threshold_triggered,
                language=language,
            )

            # Always create alert record, even if webhook is not configured
            alert_record = AlertRecord.objects.create(
                provider=provider,
                alert_rule=alert_rule,
                current_cost=current_cost,
                previous_cost=previous_cost,
                increase_cost=increase_cost,
                increase_percent=increase_percent,
                currency=current_billing.currency,
                current_balance=current_balance,
                balance_threshold=alert_rule.balance_threshold,
                alert_message=alert_message,
                webhook_status=WEBHOOK_STATUS_PENDING,
            )

            # Try to send notification (will update webhook_status)
            # Even if webhook is not configured, alert record is still created
            send_alert_notification.delay(alert_record.id)

            logger.info(
                f"Task check_alert_for_provider: Alert created "
                f"(provider_id={provider.id}, name={provider.name}, "
                f"account_id={account_id}, alert_record_id={alert_record.id}, "
                f"current_cost={current_cost}, previous_cost={previous_cost}, "
                f"increase_cost={increase_cost}, "
                f"increase_percent={increase_percent:.2f}, "
                f"current_balance={current_balance}, "
                f"currency={current_billing.currency}, "
                f"reasons={', '.join(alert_reason)})"
            )

            alerts_created.append(
                {
                    "alert_record_id": alert_record.id,
                    "account_id": account_id,
                    "reasons": alert_reason,
                }
            )

        # Return result
        if alerts_created:
            result = {
                "checked": True,
                "alerted": True,
                "alerts_created": alerts_created,
            }
        else:
            result = {
                "checked": True,
                "alerted": False,
            }

        # Update task status to success in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id, status=TaskStatus.SUCCESS, result=result
            )

        return result

    except CloudProvider.DoesNotExist:
        error_msg = "Provider not found"
        logger.error(
            f"Task check_alert_for_provider: Provider not found "
            f"(provider_id={provider_id})"
        )
        result = {"checked": False, "reason": error_msg}

        # Update task status to failure in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
            )

        return result
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(
            f"Task check_alert_for_provider: Error checking alerts "
            f"(provider_id={provider_id}, error={error_msg})",
            exc_info=True,
        )
        result = {"checked": False, "reason": error_msg}

        # Update task status to failure in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
                traceback=error_traceback,
            )

        return result


def _send_alert_notification_metadata(log_collector):
    """Build metadata dict with logs for task detail panel."""
    return {
        "logs": log_collector.get_logs(),
        "warnings_and_errors": log_collector.get_warnings_and_errors(),
        "log_summary": log_collector.get_summary(),
    }


@shared_task(name="cloud_billing.tasks.send_alert_notification")
def send_alert_notification(alert_record_id: int):
    """
    Send alert notification via webhook. Channel from
    provider.config['notification'] (type=webhook, channel_uuid=...) when set;
    else notifier default is used.

    Returns:
        Dictionary with notification result
    """
    task_id = current_task.request.id if current_task else None
    log_collector = TaskLogCollector(max_records=500)

    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name="cloud_billing.tasks.send_alert_notification",
            module="cloud_billing",
            task_kwargs={"alert_record_id": alert_record_id},
            metadata={"alert_record_id": alert_record_id},
        )
        TaskTracker.update_task_status(
            task_id=task_id,
            status=TaskStatus.STARTED,
            metadata=_send_alert_notification_metadata(log_collector),
        )

    log_collector.info(
        f"Sending alert notification (alert_record_id={alert_record_id})"
    )
    logger.info(
        f"Task send_alert_notification: Sending alert notification "
        f"(alert_record_id={alert_record_id}, task_id={task_id})"
    )

    try:
        alert_record = AlertRecord.objects.get(id=alert_record_id)
        provider = alert_record.provider
        channel_uuid = None
        channel_type = None
        notification = (provider.config or {}).get("notification")
        if isinstance(notification, dict):
            ntype = notification.get("type")
            cu = notification.get("channel_uuid")
            if cu:
                channel_uuid = str(cu)
            if ntype in ("webhook", "email"):
                channel_type = ntype

        notification_service = CloudBillingNotificationService()
        result = notification_service.send_alert(
            alert_record,
            channel_uuid=channel_uuid,
            channel_type=channel_type,
        )

        alert_record.webhook_status = (
            WEBHOOK_STATUS_SUCCESS
            if result["success"]
            else WEBHOOK_STATUS_FAILED
        )
        alert_record.webhook_response = result.get("response")
        alert_record.webhook_error = result.get("error") or ""
        alert_record.save()

        if result["success"]:
            log_collector.info(
                f"Alert notification sent successfully "
                f"(provider_id={alert_record.provider.id}, "
                f"provider_name={alert_record.provider.name})"
            )
            logger.info(
                f"Task send_alert_notification: Alert notification sent "
                f"successfully (alert_record_id={alert_record_id}, "
                f"provider_id={alert_record.provider.id}, "
                f"provider_name={alert_record.provider.name}, "
                f"webhook_status=success)"
            )
        else:
            error_msg = result.get("error")
            log_collector.error(
                f"Failed to send alert: {error_msg}",
                exception=result.get("response"),
            )
            logger.error(
                f"Task send_alert_notification: Failed to send alert "
                f"notification (alert_record_id={alert_record_id}, "
                f"provider_id={alert_record.provider.id}, "
                f"provider_name={alert_record.provider.name}, "
                f"error={error_msg})"
            )

        task_result = {
            "success": result["success"],
            "alert_record_id": alert_record_id,
            "error": result.get("error"),
        }

        if task_id:
            meta = _send_alert_notification_metadata(log_collector)
            if result["success"]:
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.SUCCESS,
                    result=task_result,
                    metadata=meta,
                )
            else:
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILURE,
                    result=task_result,
                    error=result.get("error", ""),
                    metadata=meta,
                )

        return task_result

    except AlertRecord.DoesNotExist:
        error_msg = "AlertRecord not found"
        log_collector.error(f"AlertRecord not found (id={alert_record_id})")
        logger.error(
            f"Task send_alert_notification: AlertRecord not found "
            f"(alert_record_id={alert_record_id})"
        )
        result = {"success": False, "error": error_msg}

        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
                metadata=_send_alert_notification_metadata(log_collector),
            )

        return result
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        log_collector.error(
            f"Error sending alert notification: {error_msg}",
            exception=error_traceback,
        )
        logger.error(
            f"Task send_alert_notification: Error sending alert notification "
            f"(alert_record_id={alert_record_id}, error={error_msg})",
            exc_info=True,
        )

        try:
            alert_record = AlertRecord.objects.get(id=alert_record_id)
            alert_record.webhook_status = WEBHOOK_STATUS_FAILED
            alert_record.webhook_error = error_msg or ""
            alert_record.save()
        except Exception:
            pass

        result = {"success": False, "error": error_msg}

        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
                traceback=error_traceback,
                metadata=_send_alert_notification_metadata(log_collector),
            )

        return result
