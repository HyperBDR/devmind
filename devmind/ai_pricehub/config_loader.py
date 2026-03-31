import json
from pathlib import Path
from typing import Any

from django.db.utils import OperationalError, ProgrammingError

from .models import PriceSourceConfig


class ConfigLoader:
    """Load app-local pricing source configuration."""

    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parent / "config" / "pricing_sources.json"

    def load(self) -> dict[str, Any]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _serialize_config(self, config: PriceSourceConfig) -> dict[str, Any]:
        return {
            "slug": config.platform_slug,
            "vendor_slug": config.vendor_slug,
            "platform_slug": config.platform_slug,
            "name": config.vendor_name,
            "region": config.region,
            "parser_llm_config_uuid": (
                str(config.parser_llm_config_uuid)
                if config.parser_llm_config_uuid
                else ""
            ),
            "currency": config.currency,
            "points_per_currency_unit": config.points_per_currency_unit,
            "is_enabled": config.is_enabled,
            "models_source": {
                "type": "agione_model_list",
                "url": config.endpoint_url,
            },
            "notes": config.notes,
        }

    def get_primary_vendor_configs(self) -> list[dict[str, Any]]:
        try:
            configs = list(
                PriceSourceConfig.objects.filter(vendor_slug="agione").order_by(
                    "region",
                    "vendor_name",
                    "id",
                )
            )
        except (OperationalError, ProgrammingError):
            configs = []
        if configs:
            return [self._serialize_config(config) for config in configs]
        default = self.load()["primary_vendor"]
        return [
            {
                "slug": default["slug"],
                "vendor_slug": default["slug"],
                "platform_slug": default["slug"],
                "name": default["name"],
                "region": default.get("region", ""),
                "parser_llm_config_uuid": "",
                "currency": default.get("currency", "CNY"),
                "points_per_currency_unit": default.get(
                    "points_per_currency_unit",
                    10.0,
                ),
                "is_enabled": default.get("is_enabled", True),
                "models_source": default.get("models_source", {}),
                "notes": default.get("notes", ""),
            }
        ]

    def get_primary_vendor(self) -> dict[str, Any]:
        return self.get_primary_vendor_configs()[0]

    def get_comparison_vendors(self) -> list[dict[str, Any]]:
        return self.load().get("comparison_vendors", [])


config_loader = ConfigLoader()
