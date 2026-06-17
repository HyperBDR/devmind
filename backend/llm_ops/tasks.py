"""Celery tasks for llm_ops background work.

Exposes a single periodic-friendly task that wraps
:func:`llm_ops.collection_services.sync_configured_official_model_prices`
(the same routine used by the ``collect_llm_ops_official_prices``
management command) so it can be scheduled by django_celery_beat.

The task is intentionally thin: it converts any exception into a
logged failure and re-raises so Celery records the task as
``FAILURE``. Operators should rely on the ``PriceCollectionRun`` rows
that ``sync_configured_official_model_prices`` writes for the
authoritative per-source history.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="llm_ops.tasks.collect_official_model_prices",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def collect_official_model_prices(
    self,
    *,
    provider_codes: list[str] | None = None,
    verify_source: bool = True,
) -> dict[str, dict[str, int | list[str]]]:
    """Run the official price collection across configured providers.

    Parameters
    ----------
    provider_codes:
        Optional iterable of provider codes to limit the run to. When
        ``None`` (the periodic default), every provider listed in
        ``OFFICIAL_PROVIDER_CONFIGS`` is collected. Limiting the list
        is useful for re-running a single provider after a transient
        upstream failure.
    verify_source:
        When ``True`` (the default) the collector fetches the
        provider's pricing page before extracting prices. Set to
        ``False`` from ad-hoc runs to skip the network round-trip.

    Returns
    -------
    dict
        Mapping of ``provider_code`` to its per-run stats. Empty when
        no active supported providers are configured.
    """
    # Imported lazily so that the worker process can finish
    # autodiscover before resolving the symbol.
    from .collection_services import (
        sync_configured_official_model_prices,
    )

    log_extra = {
        "provider_codes": list(provider_codes) if provider_codes else None,
        "verify_source": verify_source,
    }
    logger.info("llm_ops.collect_official_model_prices start", extra=log_extra)
    try:
        results = sync_configured_official_model_prices(
            provider_codes=list(provider_codes) if provider_codes else None,
            verify_source=verify_source,
        )
    except Exception as exc:
        logger.exception(
            "llm_ops.collect_official_model_prices failed",
            extra=log_extra,
        )
        # Retry transient failures (network, 5xx) but let config
        # errors propagate immediately.
        if verify_source and self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info(
        "llm_ops.collect_official_model_prices done: %d provider(s)",
        len(results),
        extra=log_extra,
    )
    return results


@shared_task(
    name="llm_ops.tasks.sync_meta_models_from_models_dev",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def sync_meta_models_from_models_dev_task(self) -> dict[str, int]:
    """Refresh canonical meta models from models.dev."""
    from .collection_services import sync_meta_models_from_models_dev

    logger.info("llm_ops.sync_meta_models_from_models_dev start")
    try:
        results = sync_meta_models_from_models_dev()
    except Exception as exc:
        logger.exception("llm_ops.sync_meta_models_from_models_dev failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info(
        "llm_ops.sync_meta_models_from_models_dev done: %d model(s)",
        results.get("models", 0),
    )
    return results
