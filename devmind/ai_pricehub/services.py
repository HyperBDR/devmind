import re
from typing import Any

import requests
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .config_loader import config_loader
from .models import PriceSourceConfig, PricingRecord
from .skill_runner import run_vendor_skill
from .vendors.baidu import sync_vendor_catalog as sync_baidu_catalog
from .vendors.deepseek import sync_vendor_catalog as sync_deepseek_catalog
from .vendors.volcengine import sync_vendor_catalog as sync_volcengine_catalog
from .vendors.zhipu import sync_vendor_catalog as sync_zhipu_catalog

VENDOR_SYNC_FALLBACK_HANDLERS = {
    "aliyun": lambda: run_vendor_skill("aliyun"),
    "baidu": sync_baidu_catalog,
    "deepseek": sync_deepseek_catalog,
    "volcengine": sync_volcengine_catalog,
    "zhipu": sync_zhipu_catalog,
}


class AIPriceHubService:
    """Pricing sync and comparison service."""

    def get_overview(self, platform_slug: str | None = None) -> dict[str, Any]:
        primary_sources = self._primary_sources()
        selected_platform_slug = self._resolve_primary_platform_slug(
            primary_sources,
            platform_slug,
        )
        records = self._latest_records()
        vendor_index = self._build_vendor_index(records)
        serialized_models = [
            self._serialize_model(record, vendor_index=vendor_index)
            for record in records
        ]
        return {
            "primary_sources": [
                self._serialize_primary_source(source, serialized_models)
                for source in primary_sources
            ],
            "selected_platform_slug": selected_platform_slug,
            "vendors": [
                {"id": vendor_id, "slug": slug, "name": name}
                for slug, (vendor_id, name) in sorted(
                    vendor_index.items(),
                    key=lambda item: item[1][1].lower(),
                )
            ],
            "primary_models": [
                item
                for item in serialized_models
                if item["role"] == "primary" and item["vendor_slug"] == selected_platform_slug
            ],
            "models": serialized_models,
        }

    def compare_models(
        self,
        primary_model_id: int | None = None,
        platform_slug: str | None = None,
    ) -> dict[str, Any] | None:
        primary_sources = self._primary_sources()
        primary_vendor_slug = self._resolve_primary_platform_slug(
            primary_sources,
            platform_slug,
        )
        records = self._latest_records()
        if not records:
            return None

        vendor_index = self._build_vendor_index(records)
        primary_candidates = [
            record
            for record in records
            if record.role == "primary" and record.vendor_slug == primary_vendor_slug
        ]
        primary = self._resolve_primary_model(primary_candidates, primary_model_id)
        if primary is None:
            return None

        primary_key = self._canonical_key(primary.model_name)
        allowed_vendor_keys = self._source_vendor_keys(primary)
        comparisons_by_vendor: dict[str, PricingRecord] = {}
        preferred_market_scope = self._preferred_market_scope_for_primary(primary)
        for record in records:
            if record.id == primary.id or record.vendor_slug == primary.vendor_slug:
                continue
            if self._canonical_key(record.model_name) != primary_key:
                continue
            if record.currency != primary.currency:
                continue
            if allowed_vendor_keys:
                vendor_key = self._canonical_vendor_key(record.vendor_slug, record.vendor_name)
                if vendor_key not in allowed_vendor_keys:
                    continue
            if (
                record.input_price_per_million is None
                and record.output_price_per_million is None
            ):
                continue
            vendor_key = self._canonical_vendor_key(record.vendor_slug, record.vendor_name)
            existing = comparisons_by_vendor.get(vendor_key)
            comparisons_by_vendor[vendor_key] = self._select_comparison_record(
                existing=existing,
                candidate=record,
                preferred_market_scope=preferred_market_scope,
            )

        comparisons = [
            self._serialize_comparison(record, primary, vendor_index=vendor_index)
            for record in comparisons_by_vendor.values()
        ]
        comparisons.sort(
            key=lambda item: (
                item["input_price_per_million"] is None,
                item["input_price_per_million"] or 0,
                item["output_price_per_million"] is None,
                item["output_price_per_million"] or 0,
            )
        )
        return {
            "selected_platform_slug": primary_vendor_slug,
            "primary_model": self._serialize_model(primary, vendor_index=vendor_index),
            "comparisons": comparisons,
        }

    @transaction.atomic
    def sync_configured_sources(self, platform_slug: str | None = None) -> dict[str, Any]:
        primary_vendors = [
            vendor
            for vendor in config_loader.get_primary_vendor_configs()
            if vendor.get("is_enabled", True)
        ]
        if platform_slug:
            primary_vendors = [
                vendor for vendor in primary_vendors if vendor.get("platform_slug") == platform_slug
            ]
        comparison_vendors = config_loader.get_comparison_vendors()
        collected_hour = timezone.now().replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        snapshot_count = 0
        failure_count = 0
        errors: list[str] = []
        synced_vendor_slugs: set[str] = set()

        if not primary_vendors:
            return {
                "vendors": 0,
                "models": 0,
                "snapshots": 0,
                "failures": 0,
                "errors": [],
                "accepted": True,
                "message": "No enabled primary source is configured.",
            }

        for primary_vendor in primary_vendors:
            try:
                primary_catalog = self._fetch_primary_vendor_models(primary_vendor)
            except Exception as exc:
                primary_catalog = {
                    "models": [],
                    "source_type": "agione_model_list",
                    "raw_payload": {"error": str(exc)},
                }
                failure_count += 1
                errors.append(f"{primary_vendor['name']}: {exc}")

            synced_count, synced_failures = self._sync_vendor_models(
                vendor_data=primary_vendor,
                catalog=primary_catalog,
                role="primary",
                collected_hour=collected_hour,
            )
            snapshot_count += synced_count
            failure_count += synced_failures
            synced_vendor_slugs.add(primary_vendor["slug"])

        for vendor_data in comparison_vendors:
            if vendor_data["slug"] in synced_vendor_slugs:
                continue
            synced_vendor_slugs.add(vendor_data["slug"])
            try:
                catalog = self._fetch_comparison_vendor_catalog(vendor_data)
            except Exception as exc:
                catalog = {
                    "models": [],
                    "source_type": "vendor_agent_skill",
                    "raw_payload": {"error": str(exc)},
                }
                failure_count += 1
                errors.append(f"{vendor_data['name']}: {exc}")
            synced_count, synced_failures = self._sync_vendor_models(
                vendor_data=vendor_data,
                catalog=catalog,
                role="comparison",
                collected_hour=collected_hour,
            )
            snapshot_count += synced_count
            failure_count += synced_failures

        all_records = list(PricingRecord.objects.all())
        vendor_total = len({record.vendor_slug for record in all_records})
        model_total = len(all_records)
        return {
            "vendors": vendor_total,
            "models": model_total,
            "snapshots": snapshot_count,
            "failures": failure_count,
            "errors": errors,
            "accepted": True,
            "message": "Sync completed.",
        }

    def _fetch_primary_vendor_models(self, vendor: dict[str, Any]) -> dict[str, Any]:
        url = vendor.get("models_source", {}).get("url") or vendor.get("pricing_url")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("result", {}).get("records", [])
        models = []
        for record in records:
            model_name = self._derive_agione_model_name(record)
            if not model_name:
                continue
            models.append(
                {
                    "model_name": model_name,
                    "aliases": self._build_agione_aliases(record, model_name),
                    "family": self._derive_agione_family(record),
                    "input_price_per_million": self._convert_agione_points(
                        record.get("promptPoints"),
                        vendor,
                    ),
                    "output_price_per_million": self._convert_agione_points(
                        record.get("completionPoints"),
                        vendor,
                    ),
                    "currency": vendor.get("currency", "CNY"),
                    "notes": self._build_agione_notes(record, vendor),
                    "source_vendors": self._extract_source_vendors(record),
                    "is_aggregate": bool(record.get("isAggregate")),
                }
            )
        return {
            "models": models,
            "raw_payload": {"url": url, "record_count": len(records)},
            "source_type": "agione_model_list",
        }

    def _fetch_comparison_vendor_catalog(self, vendor_data: dict[str, Any]) -> dict[str, Any]:
        try:
            from .parser_agent import parser_agent_service
        except ImportError as exc:
            fallback_handler = VENDOR_SYNC_FALLBACK_HANDLERS.get(vendor_data["slug"])
            if fallback_handler is None:
                raise ValueError(
                    f"Deepagent dependencies are unavailable and no fallback sync handler exists for {vendor_data['slug']}."
                ) from exc
            catalog = fallback_handler()
            catalog.setdefault("raw_payload", {})
            catalog["raw_payload"]["fallback_reason"] = (
                "deepagent_dependencies_unavailable"
            )
            catalog["raw_payload"]["fallback_detail"] = str(exc)
            return catalog

        try:
            return parser_agent_service.discover_vendor_catalog(vendor=vendor_data)
        except Exception as exc:
            fallback_handler = VENDOR_SYNC_FALLBACK_HANDLERS.get(vendor_data["slug"])
            if fallback_handler is None:
                raise
            catalog = fallback_handler()
            catalog.setdefault("raw_payload", {})
            catalog["raw_payload"]["fallback_reason"] = "deepagent_sync_failed"
            catalog["raw_payload"]["fallback_detail"] = str(exc)
            return catalog

    def _sync_vendor_models(
        self,
        *,
        vendor_data: dict[str, Any],
        catalog: dict[str, Any],
        role: str,
        collected_hour,
    ) -> tuple[int, int]:
        snapshot_count = 0
        failure_count = 0
        prepared_records: dict[tuple[str, str], dict[str, Any]] = {}
        source_type = catalog.get("source_type", "unknown")
        raw_payload = catalog.get("raw_payload")

        for item in catalog.get("models", []):
            normalized = self._normalize_catalog_item(
                item,
                vendor_data=vendor_data,
                role=role,
                source_type=source_type,
            )
            key = (normalized["vendor_slug"], normalized["model_slug"])
            record_data = {
                **normalized,
                "collected_hour": collected_hour,
                "raw_payload": {"catalog": raw_payload, "item": item},
            }
            existing = prepared_records.get(key)
            prepared_records[key] = self._merge_record_data(existing, record_data)

        for record_data in prepared_records.values():
            PricingRecord.objects.update_or_create(
                vendor_slug=record_data["vendor_slug"],
                model_slug=record_data["model_slug"],
                collected_hour=record_data["collected_hour"],
                defaults=record_data,
            )
            snapshot_count += 1
            if (
                record_data.get("input_price_per_million") is None
                and record_data.get("output_price_per_million") is None
            ):
                failure_count += 1

        return snapshot_count, failure_count

    def _normalize_catalog_item(
        self,
        item: dict[str, Any],
        *,
        vendor_data: dict[str, Any],
        role: str,
        source_type: str,
    ) -> dict[str, Any]:
        canonical_name = self._normalize_model_name(item.get("model_name") or "")
        market_scope = str(item.get("market_scope") or "").strip().lower()
        model_slug = self._canonical_key(canonical_name)
        if role == "comparison" and market_scope in {"domestic", "international"}:
            model_slug = f"{model_slug}-{market_scope}"
        return {
            "vendor_slug": vendor_data["slug"],
            "vendor_name": vendor_data["name"],
            "vendor_pricing_url": vendor_data.get("pricing_url"),
            "model_slug": model_slug,
            "model_name": canonical_name,
            "family": item.get("family"),
            "role": role,
            "description": self._build_description(item),
            "source_url": vendor_data.get("models_source", {}).get("url") or vendor_data.get("pricing_url"),
            "currency": item.get("currency") or vendor_data.get("currency", "USD"),
            "input_price_per_million": item.get("input_price_per_million"),
            "output_price_per_million": item.get("output_price_per_million"),
            "source_type": source_type,
        }

    @staticmethod
    def _merge_record_data(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
        if existing is None:
            return candidate
        return candidate if AIPriceHubService._record_score(candidate) > AIPriceHubService._record_score(existing) else existing

    @staticmethod
    def _record_score(item: dict[str, Any]) -> tuple[int, int]:
        priced_fields = int(item.get("input_price_per_million") is not None) + int(
            item.get("output_price_per_million") is not None
        )
        note_length = len(str(item.get("description") or ""))
        return priced_fields, note_length

    @staticmethod
    def _build_vendor_index(records: list[PricingRecord]) -> dict[str, tuple[int, str]]:
        vendor_index: dict[str, tuple[int, str]] = {}
        next_id = 1
        for record in records:
            if record.vendor_slug in vendor_index:
                continue
            vendor_index[record.vendor_slug] = (next_id, record.vendor_name)
            next_id += 1
        return vendor_index

    @staticmethod
    def _latest_records() -> list[PricingRecord]:
        records = list(
            PricingRecord.objects.all().order_by(
                "vendor_slug",
                "model_slug",
                "-collected_hour",
                "-id",
            )
        )
        latest: dict[tuple[str, str], PricingRecord] = {}
        for record in records:
            key = (record.vendor_slug, record.model_slug)
            latest.setdefault(key, record)
        return list(latest.values())

    def _serialize_model(
        self,
        record: PricingRecord,
        *,
        vendor_index: dict[str, tuple[int, str]],
    ) -> dict[str, Any]:
        vendor_id, _ = vendor_index[record.vendor_slug]
        raw_item = record.raw_payload.get("item") if isinstance(record.raw_payload, dict) else {}
        primary_source = self._primary_source_map().get(record.vendor_slug)
        return {
            "id": record.id,
            "vendor_id": vendor_id,
            "vendor_slug": record.vendor_slug,
            "vendor_name": record.vendor_name,
            "platform_slug": primary_source.get("platform_slug") if primary_source else None,
            "platform_name": primary_source.get("name") if primary_source else None,
            "platform_region": primary_source.get("region") if primary_source else None,
            "slug": record.model_slug,
            "name": record.model_name,
            "family": record.family,
            "role": record.role,
            "source_url": record.source_url,
            "input_price_per_million": record.input_price_per_million,
            "output_price_per_million": record.output_price_per_million,
            "currency": record.currency,
            "source_vendors": raw_item.get("source_vendors", []),
            "is_aggregate": bool(raw_item.get("is_aggregate", False)),
        }

    def _serialize_comparison(
        self,
        record: PricingRecord,
        primary: PricingRecord,
        *,
        vendor_index: dict[str, tuple[int, str]],
    ) -> dict[str, Any]:
        vendor_id, _ = vendor_index[record.vendor_slug]
        input_advantage = self._compute_advantage(
            primary.input_price_per_million,
            record.input_price_per_million,
        )
        output_advantage = self._compute_advantage(
            primary.output_price_per_million,
            record.output_price_per_million,
        )
        return {
            "model_id": record.id,
            "vendor_id": vendor_id,
            "vendor_slug": record.vendor_slug,
            "vendor_name": record.vendor_name,
            "platform_slug": None,
            "platform_name": None,
            "platform_region": None,
            "model_name": record.model_name,
            "family": record.family,
            "role": record.role,
            "input_price_per_million": record.input_price_per_million,
            "output_price_per_million": record.output_price_per_million,
            "currency": record.currency,
            "input_advantage": input_advantage,
            "output_advantage": output_advantage,
            "input_advantage_ratio": self._compute_advantage_ratio(
                record.input_price_per_million,
                input_advantage,
            ),
            "output_advantage_ratio": self._compute_advantage_ratio(
                record.output_price_per_million,
                output_advantage,
            ),
        }

    def _preferred_market_scope_for_primary(self, primary: PricingRecord) -> str | None:
        source = self._primary_source_map().get(primary.vendor_slug) or {}
        region = str(source.get("region") or "").strip().lower()
        if any(token in region for token in ["中国", "china", "cn", "大陆", "国内"]):
            return "domestic"
        if region:
            return "international"
        return None

    def _select_comparison_record(
        self,
        *,
        existing: PricingRecord | None,
        candidate: PricingRecord,
        preferred_market_scope: str | None,
    ) -> PricingRecord:
        if existing is None:
            return candidate
        candidate_scope = self._comparison_market_scope(candidate)
        existing_scope = self._comparison_market_scope(existing)
        if preferred_market_scope:
            if candidate_scope == preferred_market_scope and existing_scope != preferred_market_scope:
                return candidate
            if existing_scope == preferred_market_scope and candidate_scope != preferred_market_scope:
                return existing
        candidate_score = self._comparison_record_score(candidate)
        existing_score = self._comparison_record_score(existing)
        return candidate if candidate_score > existing_score else existing

    @staticmethod
    def _comparison_market_scope(record: PricingRecord) -> str:
        if not isinstance(record.raw_payload, dict):
            return "unknown"
        item = record.raw_payload.get("item") or {}
        return str(item.get("market_scope") or "unknown").strip().lower()

    @staticmethod
    def _comparison_record_score(record: PricingRecord) -> tuple[int, float, float, int]:
        priced_fields = int(record.input_price_per_million is not None) + int(
            record.output_price_per_million is not None
        )
        total = float(record.input_price_per_million or 0) + float(record.output_price_per_million or 0)
        description_length = len(record.description or "")
        return priced_fields, total, float(record.id), description_length

    @staticmethod
    def _compute_advantage(primary: float | None, candidate: float | None) -> float | None:
        if primary is None or candidate is None:
            return None
        return candidate - primary

    @staticmethod
    def _compute_advantage_ratio(
        candidate: float | None,
        advantage: float | None,
    ) -> float | None:
        if candidate in (None, 0) or advantage is None:
            return None
        return advantage / candidate

    @staticmethod
    def _resolve_primary_model(
        candidates: list[PricingRecord],
        primary_model_id: int | None,
    ) -> PricingRecord | None:
        if not candidates:
            return None
        if primary_model_id is None:
            return candidates[0]
        return next((item for item in candidates if item.id == primary_model_id), None)

    @staticmethod
    def _source_vendor_keys(record: PricingRecord) -> set[str]:
        if not isinstance(record.raw_payload, dict):
            return set()
        item = record.raw_payload.get("item") or {}
        return {
            AIPriceHubService._canonical_vendor_key(name, name)
            for name in item.get("source_vendors", [])
            if name
        }

    @staticmethod
    def _canonical_vendor_key(slug: str | None, name: str | None) -> str:
        base = slug or name or ""
        return re.sub(r"[^a-z0-9]+", "", base.lower())

    @staticmethod
    def _canonical_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")

    @staticmethod
    def _canonical_name(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize_model_name(value: str) -> str:
        canonical_name = AIPriceHubService._canonical_name(value)
        canonical_name = AIPriceHubService._clean_agione_model_name(canonical_name)
        lowered = canonical_name.lower()
        aliases = {
            "moonshot-kimi-k2-instruct": "Kimi-K2-Instruct",
            "kimi-k2-instruct": "Kimi-K2-Instruct",
            "deepseek r1": "DeepSeek-R1",
            "deepseek-r1": "DeepSeek-R1",
            "deepseek v3.2": "DeepSeek-V3.2",
            "deepseek-v3.2": "DeepSeek-V3.2",
        }
        return aliases.get(lowered, canonical_name)

    @staticmethod
    def _build_description(item: dict[str, Any]) -> str | None:
        notes = [item.get("notes"), item.get("description")]
        parts = [part.strip() for part in notes if isinstance(part, str) and part.strip()]
        return " ".join(parts) if parts else None

    @staticmethod
    def _derive_agione_model_name(record: dict[str, Any]) -> str:
        for candidate in AIPriceHubService._agione_text_candidates(record):
            extracted = AIPriceHubService._extract_model_name_from_text(candidate)
            if extracted:
                return extracted

        name = AIPriceHubService._clean_agione_model_name((record.get("name") or "").strip())
        if AIPriceHubService._looks_like_clean_model_name(name):
            return name
        return ""

    @staticmethod
    def _agione_text_candidates(record: dict[str, Any]) -> list[str]:
        candidates = []
        for key in ["info", "information", "description", "remark", "summary"]:
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        return candidates

    @staticmethod
    def _extract_model_name_from_text(text: str) -> str:
        patterns = [
            r"Model\s+(.+?)\s+aggregated",
            r"Model\s+(.+?)\s+from\s+[A-Za-z0-9 _-]+(?:$|,|\s)",
            r"^(.+?)\s+aggregated\s+from\b",
            r"^(.+?)\s+from\s+[A-Za-z0-9 _-]+(?:$|,|\s)",
            r"模型[名称名]*[:：\s]+(.+?)(?:\s+聚合|\s+来自|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                cleaned = AIPriceHubService._clean_agione_model_name(match.group(1))
                if cleaned:
                    return cleaned

        cleaned = AIPriceHubService._clean_agione_model_name(text)
        signature = AIPriceHubService._extract_model_signature(cleaned)
        if signature:
            return signature
        if AIPriceHubService._looks_like_clean_model_name(cleaned):
            return cleaned
        return ""

    @staticmethod
    def _clean_agione_model_name(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        replacements = [
            (r"^\[Aggregate\]\s*", ""),
            (r"^(?:quicker|smarter|faster|cheaper|premium)\s+model\s+", ""),
            (r"^Model\s+", ""),
            (r"\s+aggregated\s+from.+$", ""),
            (r"\s+aggregated.+$", ""),
            (r"\s+from\s+[A-Za-z0-9._/-]+$", ""),
            (r"\s+from\s+[A-Za-z0-9._/-]+(?=,)", ""),
            (r"\s+for\s+LB.+$", ""),
            (r"\s+聚合自.+$", ""),
            (r"\s+来自.+$", ""),
            (r"[\],]\s*which\b.*$", ""),
            (r"\s+which\b.*$", ""),
            (r"\s+that\b.*$", ""),
            (r"\s*[\[(].*$", ""),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDeepSeek\s+R1\b", "DeepSeek-R1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDeepSeek\s+V3(?:\.2)?\b", lambda match: match.group(0).replace(" ", "-"), cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" -:：,.;[]()")

    @staticmethod
    def _extract_model_signature(value: str) -> str:
        patterns = [
            r"\b(GLM-[A-Za-z0-9.:-]+)\b",
            r"\b(DeepSeek-[A-Za-z0-9.:-]+)\b",
            r"\b(DeepSeek\s+[A-Za-z0-9.:-]+)\b",
            r"\b(Qwen[A-Za-z0-9._:-]*)\b",
            r"\b(gpt-[A-Za-z0-9.:-]+)\b",
            r"\b(gemini-[A-Za-z0-9.:-]+)\b",
            r"\b(claude-[A-Za-z0-9.:-]+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, value, flags=re.IGNORECASE)
            if match:
                return AIPriceHubService._clean_agione_model_name(match.group(1).strip())
        return ""

    @staticmethod
    def _looks_like_clean_model_name(value: str) -> bool:
        if not value:
            return False
        lowered = value.lower()
        noise_tokens = [
            "aggregated",
            "aggregate",
            "source vendor",
            "input_points",
            "output_points",
            "promptpoints",
            "completionpoints",
        ]
        if any(token in lowered for token in noise_tokens):
            return False
        return len(value) <= 120

    @staticmethod
    def _build_agione_aliases(record: dict[str, Any], model_name: str) -> list[str]:
        aliases = [model_name]
        raw_name = (record.get("name") or "").strip()
        description = record.get("description") or ""
        for value in [raw_name, description]:
            if value and value not in aliases:
                aliases.append(value)
        return aliases

    @staticmethod
    def _extract_source_vendors(record: dict[str, Any]) -> list[str]:
        description = AIPriceHubService._build_description(record) or ""
        match = re.search(
            r"aggregated\s+from\s+(.+?)(?:,|\s+for\s+LB|$)",
            description,
            flags=re.IGNORECASE,
        )
        if match:
            vendor_text = match.group(1)
        else:
            fallback_match = re.search(
                r"\s+from\s+([A-Za-z0-9._/-]+?)(?:$|,|\s+for\s+LB)",
                description,
                flags=re.IGNORECASE,
            )
            if not fallback_match:
                return []
            vendor_text = fallback_match.group(1)
        vendors = []
        for item in re.split(r"/|,|&", vendor_text):
            cleaned = item.strip()
            if cleaned and cleaned not in vendors:
                vendors.append(cleaned)
        return vendors

    @staticmethod
    def _derive_agione_family(record: dict[str, Any]) -> str | None:
        tag_list = record.get("tagList") or []
        if tag_list:
            name = tag_list[0].get("translations", {}).get("en-US", {}).get("name")
            if name:
                return name.lower().replace(" ", "-")
        return None

    @staticmethod
    def _convert_agione_points(value: Any, vendor: dict[str, Any]) -> float | None:
        try:
            if value is None:
                return None
            points_per_currency_unit = float(
                vendor.get("points_per_currency_unit") or 10.0
            )
            if points_per_currency_unit <= 0:
                points_per_currency_unit = 10.0
            return float(value) / points_per_currency_unit
        except (TypeError, ValueError):
            return None

    def _build_agione_notes(self, record: dict[str, Any], vendor: dict[str, Any]) -> str | None:
        description = (record.get("description") or "").strip()
        prompt_points = record.get("promptPoints")
        completion_points = record.get("completionPoints")
        points_per_currency_unit = float(
            vendor.get("points_per_currency_unit") or 10.0
        )
        notes = []
        if description:
            notes.append(description)
        if prompt_points is not None or completion_points is not None:
            notes.append(
                "AGIOne pricing converted from points using "
                f"{points_per_currency_unit:g} points = 1 "
                f"{vendor.get('currency', 'CNY')}"
                f" (input_points={prompt_points}, output_points={completion_points})."
            )
        return " ".join(notes) if notes else None

    @staticmethod
    def _resolve_primary_platform_slug(
        primary_sources: list[dict[str, Any]],
        platform_slug: str | None,
    ) -> str:
        if platform_slug and any(
            item["platform_slug"] == platform_slug for item in primary_sources
        ):
            return platform_slug
        return primary_sources[0]["platform_slug"] if primary_sources else ""

    @staticmethod
    def _serialize_primary_source(
        source: dict[str, Any],
        serialized_models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        model_count = sum(
            1
            for item in serialized_models
            if item["role"] == "primary" and item["vendor_slug"] == source["platform_slug"]
        )
        return {
            "platform_slug": source["platform_slug"],
            "vendor_slug": source.get("vendor_slug", "agione"),
            "name": source["name"],
            "region": source.get("region", ""),
            "currency": source.get("currency", "CNY"),
            "endpoint_url": source.get("models_source", {}).get("url", ""),
            "points_per_currency_unit": source.get("points_per_currency_unit", 10.0),
            "is_enabled": source.get("is_enabled", True),
            "model_count": model_count,
        }

    @staticmethod
    def _primary_sources() -> list[dict[str, Any]]:
        return config_loader.get_primary_vendor_configs()

    @staticmethod
    def _primary_source_map() -> dict[str, dict[str, Any]]:
        return {
            item["platform_slug"]: item
            for item in config_loader.get_primary_vendor_configs()
        }


ai_pricehub_service = AIPriceHubService()


def list_primary_source_configs() -> list[PriceSourceConfig]:
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
        return configs

    default = config_loader.load()["primary_vendor"]
    defaults = {
        "platform_slug": default["slug"],
        "vendor_name": default["name"],
        "region": default.get("region", ""),
        "endpoint_url": (
            default.get("models_source", {}).get("url")
            or default.get("pricing_url")
        ),
        "currency": default.get("currency", "CNY"),
        "points_per_currency_unit": default.get(
            "points_per_currency_unit",
            10.0,
        ),
        "is_enabled": True,
        "notes": "",
    }
    return [PriceSourceConfig(vendor_slug="agione", **defaults)]


def get_primary_source_config(config_id: int) -> PriceSourceConfig | None:
    try:
        return PriceSourceConfig.objects.filter(
            vendor_slug="agione",
            id=config_id,
        ).first()
    except (OperationalError, ProgrammingError):
        for item in list_primary_source_configs():
            if item.id == config_id:
                return item
        return None


def create_primary_source_config(data: dict[str, Any]) -> PriceSourceConfig:
    payload = dict(data)
    payload["vendor_slug"] = "agione"
    return PriceSourceConfig.objects.create(**payload)
