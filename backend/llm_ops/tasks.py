"""Celery tasks for llm_ops background work.

Exposes periodic-friendly tasks for model price collection. The global
price sync task runs the service-runtime DeepAgent, which delegates
fetching, parsing, validation, and persistence to platform collectors.

The task is intentionally thin: it converts any exception into a
logged failure and re-raises so Celery records the task as
``FAILURE``. Operators should rely on the ``PriceCollectionRun`` rows
that platform collectors write for the authoritative per-source
history.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="llm_ops.tasks.run_model_price_sync_agent",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def run_model_price_sync_agent(
    self,
    *,
    source_ids: list[int] | None = None,
    verify_source: bool = True,
) -> dict:
    """Run the runtime Agent that syncs configured model price sources."""
    from .agents.model_price_sync import execute_model_price_sync_agent

    normalized_source_ids = (
        None if source_ids is None else list(source_ids)
    )
    log_extra = {
        "source_ids": normalized_source_ids,
        "verify_source": verify_source,
    }
    logger.info("llm_ops.run_model_price_sync_agent start", extra=log_extra)
    try:
        result = execute_model_price_sync_agent(
            source_ids=normalized_source_ids,
            verify_source=verify_source,
            source_task_id=getattr(self.request, "id", None),
        )
    except Exception as exc:
        logger.exception(
            "llm_ops.run_model_price_sync_agent failed",
            extra=log_extra,
        )
        if verify_source and self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise
    logger.info(
        "llm_ops.run_model_price_sync_agent done: %s",
        result,
        extra=log_extra,
    )
    return result


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
        Explicit iterable of provider codes to collect. When ``None``,
        this compatibility task uses the configured default provider
        set; fresh deployments keep that set empty so the task does
        no work instead of rebuilding the price catalogue.
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
    name="llm_ops.tasks.collect_price_source_prices",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def collect_price_source_prices(
    self,
    *,
    source_id: int,
    verify_source: bool = True,
) -> dict[str, int | list[str]]:
    """Run price collection for one configured price source."""
    from .models import PriceCollectionSource
    from .source_collectors import collect_price_source

    source = PriceCollectionSource.objects.select_related("provider").get(
        id=source_id,
    )
    log_extra = {
        "source_id": source_id,
        "source_slug": source.slug,
        "verify_source": verify_source,
    }
    logger.info("llm_ops.collect_price_source_prices start", extra=log_extra)

    try:
        results = collect_price_source(
            source,
            verify_source=verify_source,
        )
    except Exception as exc:
        logger.exception(
            "llm_ops.collect_price_source_prices failed",
            extra=log_extra,
        )
        if verify_source and self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        raise

    logger.info(
        "llm_ops.collect_price_source_prices done: %s",
        source.slug,
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
def sync_meta_models_from_models_dev_task(
    self,
    *,
    source_url: str | None = None,
) -> dict[str, object]:
    """Refresh canonical meta models from models.dev."""
    from .catalog_maintenance import (
        normalize_meta_model_catalog,
        resolve_orphan_meta_models,
    )
    from .collection_services import sync_meta_models_from_models_dev

    logger.info("llm_ops.sync_meta_models_from_models_dev start")
    try:
        kwargs = {"source_url": source_url} if source_url else {}
        results = sync_meta_models_from_models_dev(**kwargs)
        results["meta_model_normalization"] = normalize_meta_model_catalog()
        results["meta_model_orphan_resolution"] = resolve_orphan_meta_models()
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
