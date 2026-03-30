from __future__ import annotations

from typing import Any, Callable

from .skill_runner import run_vendor_skill


CatalogFetcher = Callable[[dict[str, Any]], dict[str, Any]]


class PricingHarnessAgent:
    """Orchestrate vendor pricing acquisition into one standard catalog shape."""

    def __init__(
        self,
        *,
        deterministic_fetcher: CatalogFetcher | None = None,
        agent_fetcher: CatalogFetcher | None = None,
    ) -> None:
        self._deterministic_fetcher = deterministic_fetcher or self._run_vendor_skill
        self._agent_fetcher = agent_fetcher or self._run_parser_agent

    def fetch_vendor_catalog(self, vendor: dict[str, Any]) -> dict[str, Any]:
        acquisition = vendor.get("acquisition") or {}
        strategy = str(acquisition.get("method") or "page").strip().lower()

        deterministic_catalog = self._attempt_deterministic_fetch(
            vendor=vendor,
            strategy=strategy,
        )
        if self._catalog_has_models(deterministic_catalog):
            return deterministic_catalog

        agent_catalog = self._attempt_agent_fetch(
            vendor=vendor,
            strategy=strategy,
            deterministic_catalog=deterministic_catalog,
        )
        if self._catalog_has_models(agent_catalog):
            return agent_catalog

        if deterministic_catalog is not None:
            return deterministic_catalog
        if agent_catalog is not None:
            return agent_catalog
        raise ValueError(
            f"PricingHarnessAgent could not fetch catalog for vendor '{vendor.get('slug')}'."
        )

    def _attempt_deterministic_fetch(
        self,
        *,
        vendor: dict[str, Any],
        strategy: str,
    ) -> dict[str, Any] | None:
        try:
            catalog = self._deterministic_fetcher(vendor)
        except Exception as exc:
            return self._build_error_catalog(
                vendor=vendor,
                source_type="vendor_skill",
                strategy=strategy,
                error=exc,
            )
        return self._annotate_catalog(
            vendor=vendor,
            catalog=catalog,
            strategy=strategy,
            source_stage="deterministic_skill",
        )

    def _attempt_agent_fetch(
        self,
        *,
        vendor: dict[str, Any],
        strategy: str,
        deterministic_catalog: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        try:
            catalog = self._agent_fetcher(vendor)
        except Exception as exc:
            catalog = self._build_error_catalog(
                vendor=vendor,
                source_type="vendor_agent_skill",
                strategy=strategy,
                error=exc,
            )
        catalog = self._annotate_catalog(
            vendor=vendor,
            catalog=catalog,
            strategy=strategy,
            source_stage="deepagent",
        )
        if deterministic_catalog is not None:
            catalog.setdefault("raw_payload", {})
            catalog["raw_payload"]["deterministic_attempt"] = (
                deterministic_catalog.get("raw_payload")
            )
        return catalog

    @staticmethod
    def _catalog_has_models(catalog: dict[str, Any] | None) -> bool:
        return bool(catalog and catalog.get("models"))

    @staticmethod
    def _annotate_catalog(
        *,
        vendor: dict[str, Any],
        catalog: dict[str, Any],
        strategy: str,
        source_stage: str,
    ) -> dict[str, Any]:
        payload = dict(catalog or {})
        payload.setdefault("models", [])
        payload.setdefault("raw_payload", {})
        payload["raw_payload"]["vendor_slug"] = vendor.get("slug")
        payload["raw_payload"]["acquisition_strategy"] = strategy
        payload["raw_payload"]["source_stage"] = source_stage
        payload["raw_payload"]["vendor_config"] = {
            "slug": vendor.get("slug"),
            "name": vendor.get("name"),
            "pricing_url": vendor.get("pricing_url"),
            "currency": vendor.get("currency"),
            "acquisition": vendor.get("acquisition") or {},
        }
        return payload

    @staticmethod
    def _build_error_catalog(
        *,
        vendor: dict[str, Any],
        source_type: str,
        strategy: str,
        error: Exception,
    ) -> dict[str, Any]:
        return {
            "models": [],
            "source_type": source_type,
            "raw_payload": {
                "vendor_slug": vendor.get("slug"),
                "acquisition_strategy": strategy,
                "error": str(error),
            },
        }

    @staticmethod
    def _run_vendor_skill(vendor: dict[str, Any]) -> dict[str, Any]:
        return run_vendor_skill(vendor.get("slug", ""), vendor)

    @staticmethod
    def _run_parser_agent(vendor: dict[str, Any]) -> dict[str, Any]:
        from .parser_agent import parser_agent_service

        return parser_agent_service.discover_vendor_catalog(vendor=vendor)


pricing_harness_agent = PricingHarnessAgent()
