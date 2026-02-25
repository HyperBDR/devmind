"""
Celery tasks for cloud billing collection and alert checking.
"""
import logging
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from celery import shared_task
from celery import current_task
from django.db import transaction
from django.utils import translation
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from agentcore_notifier.adapters.django.services.webhook_service import (
    get_default_webhook_channel,
)
from agentcore_task.adapters.django import (
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
from agentcore_task.adapters.django import prevent_duplicate_task

logger = logging.getLogger(__name__)


@shared_task(name='cloud_billing.tasks.collect_billing_data')
@prevent_duplicate_task(
    "collect_billing_data", lock_param="user_id", timeout=3600
)
def collect_billing_data(
    provider_id: Optional[int] = None,
    user_id: Optional[int] = None
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
            task_name='cloud_billing.tasks.collect_billing_data',
            module='cloud_billing',
            task_kwargs={'provider_id': provider_id, 'user_id': user_id},
            metadata={'provider_id': provider_id, 'user_id': user_id}
        )
        TaskTracker.update_task_status(
            task_id=task_id,
            status=TaskStatus.STARTED
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
        'success': [],
        'failed': [],
        'total': 0,
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
            logger.warning(warning_msg)
            return results

        provider_service = ProviderService()
        current_period = datetime.now().strftime("%Y-%m")
        current_hour = datetime.now().hour

        for provider in providers:
            try:
                info_msg = (
                    f"Task collect_billing_data: Processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, "
                    f"display_name={provider.display_name})"
                )
                log_collector.info(info_msg)
                logger.info(info_msg)

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
                    logger.warning(warning_msg)
                    results['failed'].append({
                        'provider': provider.name,
                        'error': (
                            'No configuration found. '
                            'Please configure the provider first.'
                        )
                    })
                    continue

                # get_billing_info will normalize the config internally
                billing_info = provider_service.get_billing_info(
                    provider.provider_type,
                    config_dict,
                    period=current_period
                )

                if billing_info.get('status') != 'success':
                    error_msg = billing_info.get('error', 'Unknown error')
                    error_log = (
                        f"Task collect_billing_data: Failed to get billing "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type}, "
                        f"period={current_period}, error={error_msg})"
                    )
                    log_collector.error(error_log)
                    logger.error(error_log)
                    results['failed'].append({
                        'provider': provider.name,
                        'error': error_msg
                    })
                    continue

                billing_data = billing_info.get('data', {})
                total_cost = Decimal(str(billing_data.get('total_cost', 0)))
                currency = billing_data.get('currency', 'USD')
                service_costs = billing_data.get('service_costs', {})
                account_id = billing_data.get('account_id', '')

                # Calculate hourly incremental cost
                # Rule: If this month has no data yet, hourly_cost = total_cost
                # Otherwise, calculate increment from previous hour
                has_data_this_period = BillingData.objects.filter(
                    provider=provider,
                    period=current_period
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
                        prev_date = datetime.now() - timedelta(days=1)
                        previous_period = prev_date.strftime("%Y-%m")

                    try:
                        previous_billing = BillingData.objects.get(
                            provider=provider,
                            account_id=account_id,
                            period=previous_period,
                            hour=previous_hour
                        )
                        # Calculate incremental cost: current - previous
                        hourly_cost = total_cost - previous_billing.total_cost
                        # Ensure hourly_cost is not negative (safety check)
                        if hourly_cost < 0:
                            hourly_cost = Decimal('0')
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
                                'total_cost': total_cost,
                                'hourly_cost': hourly_cost,
                                'currency': currency,
                                'service_costs': service_costs,
                            }
                        )
                    )

                    if not created:
                        # Update existing billing record with latest data
                        billing_record.total_cost = total_cost
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
                                'total_cost', 'hourly_cost', 'currency',
                                'service_costs', 'account_id',
                                'collected_at'
                            ]
                        )
                        info_msg = (
                            f"Task collect_billing_data: Updated existing "
                            f"billing data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"hourly_cost={hourly_cost}, currency={currency}, "
                            f"account_id={account_id})"
                        )
                        log_collector.info(info_msg)
                        logger.info(info_msg)
                    else:
                        info_msg = (
                            f"Task collect_billing_data: Created new billing "
                            f"data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"hourly_cost={hourly_cost}, currency={currency}, "
                            f"account_id={account_id})"
                        )
                        log_collector.info(info_msg)
                        logger.info(info_msg)

                results['success'].append({
                    'provider': provider.name,
                    'total_cost': float(total_cost),
                    'currency': currency,
                })

                check_alert_for_provider.delay(provider.id)

            except Exception as e:
                error_traceback = traceback.format_exc()
                error_msg = (
                    f"Task collect_billing_data: Error processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, error={str(e)})"
                )
                log_collector.error(error_msg, exception=error_traceback)
                logger.error(error_msg, exc_info=True)
                results['failed'].append({
                    'provider': provider.name,
                    'error': str(e)
                })

        results['total'] = len(results['success']) + len(results['failed'])
        info_msg = (
            f"Task collect_billing_data: Billing collection completed "
            f"(provider_id={provider_id}, total={results['total']}, "
            f"success={len(results['success'])}, "
            f"failed={len(results['failed'])})"
        )
        log_collector.info(info_msg)
        logger.info(info_msg)

        # Save logs to task metadata
        if task_id:
            all_logs = log_collector.get_logs()
            warnings_and_errors = log_collector.get_warnings_and_errors()
            log_summary = log_collector.get_summary()

            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                result=results,
                metadata={
                    'logs': all_logs,
                    'warnings_and_errors': warnings_and_errors,
                    'log_summary': log_summary
                }
            )

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        error_log = (
            f"Task collect_billing_data: Error in billing collection "
            f"(provider_id={provider_id}, error={error_msg})"
        )
        log_collector.error(error_log, exception=error_traceback)
        logger.error(error_log, exc_info=True)
        results['error'] = error_msg

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
                        'logs': all_logs,
                        'warnings_and_errors': warnings_and_errors,
                        'log_summary': log_summary
                    }
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
                    traceback=error_traceback
                )

    return results


@shared_task(name='cloud_billing.tasks.check_alert_for_provider')
def check_alert_for_provider(provider_id: int):
    """
    Check alert rules for a specific provider.

    Args:
        provider_id: Provider ID to check alerts for

    Returns:
        Dictionary with alert check results
    """
    task_id = current_task.request.id if current_task else None

    # Register task in agentcore_task if not already registered
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name='cloud_billing.tasks.check_alert_for_provider',
            module='cloud_billing',
            task_kwargs={'provider_id': provider_id},
            metadata={'provider_id': provider_id}
        )
        TaskTracker.update_task_status(
            task_id=task_id,
            status=TaskStatus.STARTED
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
            return {'checked': False, 'reason': 'No active alert rule'}

        current_period = datetime.now().strftime("%Y-%m")
        current_hour = datetime.now().hour

        # Get all current billing records for this provider
        # (may have multiple accounts)
        current_billings = BillingData.objects.filter(
            provider=provider,
            period=current_period,
            hour=current_hour
        )

        if not current_billings.exists():
            logger.warning(
                f"Task check_alert_for_provider: No current billing data "
                f"found (provider_id={provider.id}, name={provider.name}, "
                f"period={current_period}, hour={current_hour})"
            )
            return {'checked': False, 'reason': 'No current billing data'}

        previous_hour = current_hour - 1
        previous_period = current_period

        if previous_hour < 0:
            previous_hour = 23
            prev_date = datetime.now() - timedelta(days=1)
            previous_period = prev_date.strftime("%Y-%m")

        # Check alerts for each account_id separately
        alerts_created = []
        for current_billing in current_billings:
            account_id = current_billing.account_id or ''
            
            try:
                previous_billing = BillingData.objects.get(
                    provider=provider,
                    account_id=account_id,
                    period=previous_period,
                    hour=previous_hour
                )
            except BillingData.DoesNotExist:
                logger.info(
                    f"Task check_alert_for_provider: "
                    f"No previous billing data found "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"account_id={account_id}, period={previous_period}, "
                    f"hour={previous_hour})"
                )
                continue

            current_cost = Decimal(str(current_billing.total_cost))
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
                continue

            increase_cost = current_cost - previous_cost
            increase_percent = (increase_cost / previous_cost) * 100

            should_alert = False
            alert_reason = []

            # Check cost threshold (absolute current cost)
            if alert_rule.cost_threshold is not None:
                cost_threshold_decimal = Decimal(
                    str(alert_rule.cost_threshold)
                )
                if current_cost > cost_threshold_decimal:
                    should_alert = True
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

            # Check growth threshold
            if alert_rule.growth_threshold is not None:
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
            if alert_rule.growth_amount_threshold is not None:
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

            language = "zh-hans"
            try:
                channel, _ = get_default_webhook_channel()
                if channel and isinstance(channel.config, dict):
                    language = channel.config.get("language", "zh-hans")
            except Exception:
                pass

            # Generate alert message based on trigger reason
            cost_threshold_triggered = any(
                'Current cost' in reason for reason in alert_reason
            )
            
            # Map language code to Django translation code
            lang_code = 'zh_Hans' if language == 'zh-hans' else 'en'
            with translation.override(lang_code):
                if account_id:
                    account_display = str(
                        _(" (Account: {account_id})").format(
                            account_id=account_id
                        )
                    )
                else:
                    account_display = ""
                
                if cost_threshold_triggered:
                    alert_message = str(_(
                        "{provider_name}{account_display} "
                        "current total cost {current_cost:.2f} "
                        "{currency} exceeds threshold "
                        "{threshold:.2f} {currency}"
                    ).format(
                        provider_name=provider.display_name,
                        account_display=account_display,
                        current_cost=current_cost,
                        currency=current_billing.currency,
                        threshold=alert_rule.cost_threshold,
                    ))
                else:
                    alert_message = str(_(
                        "{provider_name}{account_display} "
                        "billing increased by {increase_cost:.2f} "
                        "{currency} in the last hour, "
                        "growth rate: {increase_percent:.2f}%"
                    ).format(
                        provider_name=provider.display_name,
                        account_display=account_display,
                        increase_cost=increase_cost,
                        currency=current_billing.currency,
                        increase_percent=increase_percent,
                    ))

            # Always create alert record, even if webhook is not configured
            alert_record = AlertRecord.objects.create(
                provider=provider,
                alert_rule=alert_rule,
                current_cost=current_cost,
                previous_cost=previous_cost,
                increase_cost=increase_cost,
                increase_percent=increase_percent,
                currency=current_billing.currency,
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
                f"currency={current_billing.currency}, "
                f"reasons={', '.join(alert_reason)})"
            )

            alerts_created.append({
                'alert_record_id': alert_record.id,
                'account_id': account_id,
                'reasons': alert_reason,
            })

        # Return result
        if alerts_created:
            result = {
                'checked': True,
                'alerted': True,
                'alerts_created': alerts_created,
            }
        else:
            result = {
                'checked': True,
                'alerted': False,
            }

        # Update task status to success in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                result=result
            )

        return result

    except CloudProvider.DoesNotExist:
        error_msg = 'Provider not found'
        logger.error(
            f"Task check_alert_for_provider: Provider not found "
            f"(provider_id={provider_id})"
        )
        result = {'checked': False, 'reason': error_msg}

        # Update task status to failure in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg
            )

        return result
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(
            f"Task check_alert_for_provider: Error checking alerts "
            f"(provider_id={provider_id}, error={error_msg})",
            exc_info=True
        )
        result = {'checked': False, 'reason': error_msg}

        # Update task status to failure in task tracker
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
                traceback=error_traceback
            )

        return result


@shared_task(name='cloud_billing.tasks.send_alert_notification')
def send_alert_notification(alert_record_id: int):
    """
    Send alert notification via webhook.

    Args:
        alert_record_id: AlertRecord ID to send notification for

    Returns:
        Dictionary with notification result
    """
    task_id = current_task.request.id if current_task else None

    # Register task in agentcore_task if not already registered
    if task_id:
        TaskTracker.register_task(
            task_id=task_id,
            task_name='cloud_billing.tasks.send_alert_notification',
            module='cloud_billing',
            task_kwargs={'alert_record_id': alert_record_id},
            metadata={'alert_record_id': alert_record_id}
        )
        TaskTracker.update_task_status(
            task_id=task_id,
            status=TaskStatus.STARTED
        )

    logger.info(
        f"Task send_alert_notification: Sending alert notification "
        f"(alert_record_id={alert_record_id}, task_id={task_id})"
    )

    try:
        alert_record = AlertRecord.objects.get(id=alert_record_id)

        notification_service = CloudBillingNotificationService()
        result = notification_service.send_alert(alert_record)

        alert_record.webhook_status = (
            WEBHOOK_STATUS_SUCCESS
            if result['success'] else WEBHOOK_STATUS_FAILED
        )
        alert_record.webhook_response = result.get('response')
        alert_record.webhook_error = result.get('error', '')
        alert_record.save()

        if result['success']:
            logger.info(
                f"Task send_alert_notification: Alert notification sent "
                f"successfully (alert_record_id={alert_record_id}, "
                f"provider_id={alert_record.provider.id}, "
                f"provider_name={alert_record.provider.name}, "
                f"webhook_status=success)"
            )
        else:
            error_msg = result.get('error')
            logger.error(
                f"Task send_alert_notification: Failed to send alert "
                f"notification (alert_record_id={alert_record_id}, "
                f"provider_id={alert_record.provider.id}, "
                f"provider_name={alert_record.provider.name}, "
                f"error={error_msg})"
            )

        task_result = {
            'success': result['success'],
            'alert_record_id': alert_record_id,
            'error': result.get('error'),
        }

        # Update task status in task tracker
        if task_id:
            if result['success']:
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.SUCCESS,
                    result=task_result
                )
            else:
                TaskTracker.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILURE,
                    result=task_result,
                    error=result.get('error', '')
                )

        return task_result

    except AlertRecord.DoesNotExist:
        error_msg = 'AlertRecord not found'
        logger.error(
            f"Task send_alert_notification: AlertRecord not found "
            f"(alert_record_id={alert_record_id})"
        )
        result = {'success': False, 'error': error_msg}

        # Update task status to failure
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg
            )

        return result
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(
            f"Task send_alert_notification: Error sending alert notification "
            f"(alert_record_id={alert_record_id}, error={error_msg})",
            exc_info=True
        )

        try:
            alert_record = AlertRecord.objects.get(id=alert_record_id)
            alert_record.webhook_status = WEBHOOK_STATUS_FAILED
            alert_record.webhook_error = error_msg
            alert_record.save()
        except Exception:
            pass

        result = {'success': False, 'error': error_msg}

        # Update task status to failure
        if task_id:
            TaskTracker.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                result=result,
                error=error_msg,
                traceback=error_traceback
            )

        return result
