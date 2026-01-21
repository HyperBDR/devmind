"""
Celery tasks for cloud billing collection and alert checking.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from celery import shared_task
from django.db import transaction

from .models import AlertRecord, AlertRule, BillingData, CloudProvider
from .services.provider_service import ProviderService
from .services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


@shared_task(name='cloud_billing.tasks.collect_billing_data')
def collect_billing_data(provider_id: Optional[int] = None):
    """
    Collect billing data for cloud providers.

    Args:
        provider_id: Optional provider ID to collect for specific provider.
                     If None, collects for all active providers.

    Returns:
        Dictionary with collection results
    """
    logger.info(
        f"Task collect_billing_data: Starting billing data collection "
        f"(provider_id={provider_id})"
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
            logger.warning(
                f"Task collect_billing_data: No active providers found "
                f"(provider_id={provider_id})"
            )
            return results

        provider_service = ProviderService()
        current_period = datetime.now().strftime("%Y-%m")
        current_hour = datetime.now().hour

        for provider in providers:
            try:
                logger.info(
                    f"Task collect_billing_data: Processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, "
                    f"display_name={provider.display_name})"
                )

                config_dict = provider.config
                if not config_dict:
                    logger.warning(
                        f"Task collect_billing_data: Provider has no config "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type})"
                    )
                    results['failed'].append({
                        'provider': provider.name,
                        'error': 'No configuration found'
                    })
                    continue

                billing_info = provider_service.get_billing_info(
                    provider.provider_type,
                    config_dict,
                    period=current_period
                )

                if billing_info.get('status') != 'success':
                    error_msg = billing_info.get('error', 'Unknown error')
                    logger.error(
                        f"Task collect_billing_data: Failed to get billing "
                        f"(provider_id={provider.id}, name={provider.name}, "
                        f"type={provider.provider_type}, period={current_period}, "
                        f"error={error_msg})"
                    )
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

                with transaction.atomic():
                    billing_record, created = BillingData.objects.get_or_create(
                        provider=provider,
                        period=current_period,
                        hour=current_hour,
                        defaults={
                            'total_cost': total_cost,
                            'currency': currency,
                            'service_costs': service_costs,
                            'account_id': account_id,
                        }
                    )

                    if not created:
                        billing_record.total_cost = total_cost
                        billing_record.currency = currency
                        billing_record.service_costs = service_costs
                        billing_record.account_id = account_id
                        billing_record.save()
                        logger.info(
                            f"Task collect_billing_data: Updated existing "
                            f"billing data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"currency={currency}, account_id={account_id})"
                        )
                    else:
                        logger.info(
                            f"Task collect_billing_data: Created new billing "
                            f"data (provider_id={provider.id}, "
                            f"name={provider.name}, period={current_period}, "
                            f"hour={current_hour}, total_cost={total_cost}, "
                            f"currency={currency}, account_id={account_id})"
                        )

                results['success'].append({
                    'provider': provider.name,
                    'total_cost': float(total_cost),
                    'currency': currency,
                })

                check_alert_for_provider.delay(provider.id)

            except Exception as e:
                logger.error(
                    f"Task collect_billing_data: Error processing provider "
                    f"(provider_id={provider.id}, name={provider.name}, "
                    f"type={provider.provider_type}, error={str(e)})",
                    exc_info=True
                )
                results['failed'].append({
                    'provider': provider.name,
                    'error': str(e)
                })

        results['total'] = len(results['success']) + len(results['failed'])
        logger.info(
            f"Task collect_billing_data: Billing collection completed "
            f"(provider_id={provider_id}, total={results['total']}, "
            f"success={len(results['success'])}, "
            f"failed={len(results['failed'])})"
        )

    except Exception as e:
        logger.error(
            f"Task collect_billing_data: Error in billing collection "
            f"(provider_id={provider_id}, error={str(e)})",
            exc_info=True
        )
        results['error'] = str(e)

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
    logger.info(
        f"Task check_alert_for_provider: Checking alerts "
        f"(provider_id={provider_id})"
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

        try:
            current_billing = BillingData.objects.get(
                provider=provider,
                period=current_period,
                hour=current_hour
            )
        except BillingData.DoesNotExist:
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

        try:
            previous_billing = BillingData.objects.get(
                provider=provider,
                period=previous_period,
                hour=previous_hour
            )
        except BillingData.DoesNotExist:
            logger.info(
                f"Task check_alert_for_provider: No previous billing data "
                f"found (provider_id={provider.id}, name={provider.name}, "
                f"period={previous_period}, hour={previous_hour})"
            )
            return {'checked': False, 'reason': 'No previous billing data'}

        current_cost = Decimal(str(current_billing.total_cost))
        previous_cost = Decimal(str(previous_billing.total_cost))

        if previous_cost <= 0:
            logger.info(
                f"Task check_alert_for_provider: Previous cost is zero or "
                f"negative (provider_id={provider.id}, name={provider.name}, "
                f"previous_cost={previous_cost}, period={previous_period}, "
                f"hour={previous_hour})"
            )
            return {
                'checked': False,
                'reason': 'Previous cost is zero or negative'
            }

        increase_cost = current_cost - previous_cost
        increase_percent = (increase_cost / previous_cost) * 100

        should_alert = False
        alert_reason = []

        cost_threshold_decimal = Decimal(str(alert_rule.cost_threshold))
        if alert_rule.cost_threshold and increase_cost > cost_threshold_decimal:
            should_alert = True
            alert_reason.append(
                f"Cost increase {increase_cost} exceeds threshold "
                f"{alert_rule.cost_threshold}"
            )
            logger.info(
                f"Task check_alert_for_provider: Cost threshold exceeded "
                f"(provider_id={provider.id}, name={provider.name}, "
                f"increase_cost={increase_cost}, "
                f"cost_threshold={alert_rule.cost_threshold})"
            )

        growth_threshold_decimal = Decimal(
            str(alert_rule.growth_threshold)
        )
        if alert_rule.growth_threshold and increase_percent > growth_threshold_decimal:
            should_alert = True
            alert_reason.append(
                f"Growth {increase_percent:.2f}% exceeds threshold "
                f"{alert_rule.growth_threshold}%"
            )
            logger.info(
                f"Task check_alert_for_provider: Growth threshold exceeded "
                f"(provider_id={provider.id}, name={provider.name}, "
                f"increase_percent={increase_percent:.2f}, "
                f"growth_threshold={alert_rule.growth_threshold})"
            )

        if not should_alert:
            logger.info(
                f"Task check_alert_for_provider: No alert triggered "
                f"(provider_id={provider.id}, name={provider.name}, "
                f"current_cost={current_cost}, previous_cost={previous_cost}, "
                f"increase_cost={increase_cost}, "
                f"increase_percent={increase_percent:.2f})"
            )
            return {'checked': True, 'alerted': False}

        language = 'zh-hans'
        try:
            from app_config.utils import get_config
            webhook_config = get_config('webhook_config', default={})
            language = webhook_config.get('language', 'zh-hans')
        except Exception:
            pass

        if language == 'zh-hans':
            alert_message = (
                f"{provider.display_name} 账户在过去一小时的消费增长了 "
                f"{increase_cost:.2f} {current_billing.currency}，"
                f"增长率为 {increase_percent:.2f}%"
            )
        else:
            alert_message = (
                f"{provider.display_name} account billing increased by "
                f"{increase_cost:.2f} {current_billing.currency} "
                f"in the last hour, growth rate: {increase_percent:.2f}%"
            )

        alert_record = AlertRecord.objects.create(
            provider=provider,
            alert_rule=alert_rule,
            current_cost=current_cost,
            previous_cost=previous_cost,
            increase_cost=increase_cost,
            increase_percent=increase_percent,
            currency=current_billing.currency,
            alert_message=alert_message,
            webhook_status='pending',
        )

        send_alert_notification.delay(alert_record.id)

        logger.info(
            f"Task check_alert_for_provider: Alert created "
            f"(provider_id={provider.id}, name={provider.name}, "
            f"alert_record_id={alert_record.id}, "
            f"current_cost={current_cost}, previous_cost={previous_cost}, "
            f"increase_cost={increase_cost}, "
            f"increase_percent={increase_percent:.2f}, "
            f"currency={current_billing.currency}, "
            f"reasons={', '.join(alert_reason)})"
        )

        return {
            'checked': True,
            'alerted': True,
            'alert_record_id': alert_record.id,
            'reasons': alert_reason,
        }

    except CloudProvider.DoesNotExist:
        logger.error(
            f"Task check_alert_for_provider: Provider not found "
            f"(provider_id={provider_id})"
        )
        return {'checked': False, 'reason': 'Provider not found'}
    except Exception as e:
        logger.error(
            f"Task check_alert_for_provider: Error checking alerts "
            f"(provider_id={provider_id}, error={str(e)})",
            exc_info=True
        )
        return {'checked': False, 'reason': str(e)}


@shared_task(name='cloud_billing.tasks.send_alert_notification')
def send_alert_notification(alert_record_id: int):
    """
    Send alert notification via webhook.

    Args:
        alert_record_id: AlertRecord ID to send notification for

    Returns:
        Dictionary with notification result
    """
    logger.info(
        f"Task send_alert_notification: Sending alert notification "
        f"(alert_record_id={alert_record_id})"
    )

    try:
        alert_record = AlertRecord.objects.get(id=alert_record_id)

        webhook_service = WebhookService()
        result = webhook_service.send_alert(alert_record)

        alert_record.webhook_status = (
            'success' if result['success'] else 'failed'
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

        return {
            'success': result['success'],
            'alert_record_id': alert_record_id,
            'error': result.get('error'),
        }

    except AlertRecord.DoesNotExist:
        logger.error(
            f"Task send_alert_notification: AlertRecord not found "
            f"(alert_record_id={alert_record_id})"
        )
        return {'success': False, 'error': 'AlertRecord not found'}
    except Exception as e:
        logger.error(
            f"Task send_alert_notification: Error sending alert notification "
            f"(alert_record_id={alert_record_id}, error={str(e)})",
            exc_info=True
        )

        try:
            alert_record = AlertRecord.objects.get(id=alert_record_id)
            alert_record.webhook_status = 'failed'
            alert_record.webhook_error = str(e)
            alert_record.save()
        except Exception:
            pass

        return {'success': False, 'error': str(e)}
