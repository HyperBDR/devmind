import json
from pathlib import Path
from typing import Any

from .source_config_store import get_primary_vendor_configs


class ConfigLoader:
    """Load app-local pricing source configuration."""

    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parent / "config" / "pricing_sources.json"

    def load(self) -> dict[str, Any]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def get_primary_vendor_configs(self) -> list[dict[str, Any]]:
        return get_primary_vendor_configs()

    def get_primary_vendor(self) -> dict[str, Any]:
        return self.get_primary_vendor_configs()[0]

    def get_comparison_vendors(self) -> list[dict[str, Any]]:
        return self.load().get("comparison_vendors", [])


config_loader = ConfigLoader()
