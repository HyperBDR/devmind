from __future__ import annotations

import json
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from .extraction import ExtractedPricingCatalog
from .tracked_llm import build_tracking_state, invoke_tracked_structured_llm

logger = logging.getLogger(__name__)

RESOURCE_TEXT_CHAR_LIMIT = 18000
RESOURCE_URL_LIMIT = 5


class ParserAgentService:
    def __init__(self) -> None:
        self.root_dir = Path(__file__).resolve().parent
        self.runtime_dir = self.root_dir / "runtime" / "parse_jobs"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def discover_vendor_catalog(
        self,
        *,
        vendor: dict[str, Any],
        parser_llm_config_uuid: str | None = None,
    ) -> dict[str, Any]:
        job_dir = self.runtime_dir / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=True)

        evidence = self._collect_vendor_evidence(vendor=vendor, job_dir=job_dir)
        state = build_tracking_state(
            vendor=vendor,
            node_name="ai_pricehub_vendor_parser_agent",
            source_path="ai_pricehub.parser_agent",
            metadata={
                "job_dir": str(job_dir),
                "pricing_url": vendor.get("pricing_url") or "",
            },
        )
        result, usage, llm_settings = invoke_tracked_structured_llm(
            schema=ExtractedPricingCatalog,
            messages=self._build_vendor_discovery_messages(
                evidence=evidence,
            ),
            preferred_config_uuid=parser_llm_config_uuid,
            node_name="ai_pricehub_vendor_parser_agent",
            state=state,
            max_tokens=5000,
            temperature=0,
        )
        payload = result.model_dump()
        return {
            "models": payload.get("models", []),
            "notes": payload.get("notes"),
            "raw_payload": {
                "vendor": vendor.get("name"),
                "job_dir": str(job_dir),
                "pricing_url": vendor.get("pricing_url"),
                "evidence": evidence,
                "usage": usage,
                "parser_llm": {
                    "config_uuid": llm_settings.get("config_uuid"),
                    "label": llm_settings.get("label"),
                    "source": llm_settings.get("source"),
                },
            },
            "source_type": "vendor_tracked_parser",
        }

    def _collect_vendor_evidence(
        self,
        *,
        vendor: dict[str, Any],
        job_dir: Path,
    ) -> dict[str, Any]:
        pricing_url = str(vendor.get("pricing_url") or "").strip()
        evidence: dict[str, Any] = {
            "pricing_url": pricing_url,
            "vendor_context": {
                "slug": vendor.get("slug"),
                "name": vendor.get("name"),
                "currency": vendor.get("currency"),
                "acquisition": vendor.get("acquisition") or {},
            },
            "resources": [],
        }

        deterministic_result = None
        deterministic_raw = (vendor.get("_deterministic_catalog") or {}).get("raw_payload")
        if deterministic_raw:
            deterministic_result = deterministic_raw
        if deterministic_result:
            evidence["deterministic_attempt"] = deterministic_result

        if not pricing_url:
            return evidence

        primary_resource = self._fetch_resource(pricing_url, job_dir=job_dir)
        evidence["resources"].append(primary_resource)

        candidate_urls = self._extract_candidate_urls(
            pricing_url=pricing_url,
            text=primary_resource.get("content") or "",
        )
        for candidate_url in candidate_urls[:RESOURCE_URL_LIMIT]:
            try:
                evidence["resources"].append(
                    self._fetch_resource(candidate_url, job_dir=job_dir),
                )
            except Exception as exc:
                logger.info(
                    "ai_pricehub parser skipped candidate resource url=%s error=%s",
                    candidate_url,
                    exc,
                )
        return evidence

    def _fetch_resource(self, url: str, *, job_dir: Path) -> dict[str, Any]:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        text = response.text
        suffix = self._guess_suffix(url=url, content_type=content_type)
        target = job_dir / f"resource-{uuid.uuid4().hex}{suffix}"
        target.write_text(text, encoding="utf-8")
        return {
            "url": url,
            "content_type": content_type,
            "file_path": f"/{target.relative_to(self.root_dir).as_posix()}",
            "content": text[:RESOURCE_TEXT_CHAR_LIMIT],
        }

    @staticmethod
    def _extract_candidate_urls(*, pricing_url: str, text: str) -> list[str]:
        parsed = urlparse(pricing_url)
        base_host = parsed.netloc
        seen: set[str] = set()
        scored: list[tuple[int, str]] = []
        for raw in re.findall(r'https?://[^"\'\s)]+|/[^"\'\s)]+', text):
            candidate = urljoin(pricing_url, raw)
            normalized = candidate.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidate_parsed = urlparse(normalized)
            if candidate_parsed.netloc and candidate_parsed.netloc != base_host:
                continue
            score = 0
            lowered = normalized.lower()
            if any(token in lowered for token in ("pricing", "price", "billing", "token", "model")):
                score += 3
            if lowered.endswith(".json"):
                score += 4
            if lowered.endswith(".js"):
                score += 2
            if score <= 0:
                continue
            scored.append((score, normalized))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [url for _, url in scored]

    def _build_vendor_discovery_messages(
        self,
        *,
        evidence: dict[str, Any],
    ) -> list[dict[str, str]]:
        prompt = (
            "Analyze the vendor pricing evidence below and extract a complete AI model pricing catalog.\n"
            f"Vendor metadata:\n{json.dumps(evidence.get('vendor_context') or {}, ensure_ascii=False, indent=2)}\n\n"
            f"Evidence bundle:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
            "Requirements:\n"
            "- Return only standard model pricing, one item per model per market scope when applicable.\n"
            "- Normalize prices to the vendor currency per 1M tokens.\n"
            "- Preserve region distinctions using market_scope values domestic, international, global, or null.\n"
            "- When the evidence shows tiered or range pricing, keep the highest standard range price.\n"
            "- Ignore cache, batch, promotional, training, discount, or free-tier pricing.\n"
            "- Keep model names concise and canonical.\n"
            "- Omit models you cannot substantiate from the evidence.\n"
        )
        return [
            {
                "role": "system",
                "content": (
                    "Extract vendor AI model token pricing into structured JSON. "
                    "Return a valid JSON object only."
                ),
            },
            {"role": "user", "content": prompt},
        ]

    @staticmethod
    def _guess_suffix(*, url: str, content_type: str) -> str:
        if "json" in content_type:
            return ".json"
        if "html" in content_type:
            return ".html"
        if "javascript" in content_type or url.endswith(".js"):
            return ".js"
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
        return guessed or ".txt"


parser_agent_service = ParserAgentService()
