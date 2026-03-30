import json
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

import requests
from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from django.conf import settings

from .extraction import ExtractedPricingCatalog
from .skill_runner import run_vendor_skill


class DeepAgentLLMLogHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self.logger = logging.getLogger("devmind.ai_pricehub.deepagent")

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> Any:
        for batch in messages:
            payload = [
                {
                    "type": getattr(message, "type", None),
                    "content": message.content,
                }
                for message in batch
            ]
            self.logger.info(
                "deepagent_llm_start model=%s messages=%s",
                serialized.get("name") or serialized.get("id"),
                json.dumps(payload, ensure_ascii=False),
            )


class ParserAgentService:
    def __init__(self) -> None:
        self.root_dir = Path(__file__).resolve().parent
        self.runtime_dir = self.root_dir / "runtime" / "parse_jobs"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.callback_handler = DeepAgentLLMLogHandler()

    def discover_vendor_catalog(self, *, vendor: dict[str, Any]) -> dict[str, Any]:
        self._validate_llm_config()
        job_dir = self.runtime_dir / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=True)

        prompt = self._build_vendor_discovery_prompt(vendor=vendor)
        tools = self._build_vendor_tools(job_dir=job_dir, vendor=vendor)
        result = self._invoke_agent(
            prompt=prompt,
            tools=tools,
            response_format=ExtractedPricingCatalog,
            skill_name="pricing-vendor-agent",
        )
        payload = result.model_dump() if isinstance(result, ExtractedPricingCatalog) else ExtractedPricingCatalog.model_validate(result).model_dump()
        return {
            "models": payload.get("models", []),
            "notes": payload.get("notes"),
            "raw_payload": {
                "vendor": vendor.get("name"),
                "job_dir": str(job_dir),
                "pricing_url": vendor.get("pricing_url"),
                "notes": payload.get("notes"),
            },
            "source_type": "vendor_agent_skill",
        }

    def _invoke_agent(
        self,
        *,
        prompt: str,
        tools: list[Any],
        response_format: type,
        skill_name: str,
    ) -> Any:
        llm = ChatOpenAI(
            model=settings.AI_PRICEHUB_PARSER_LLM_MODEL,
            api_key=settings.AI_PRICEHUB_PARSER_LLM_API_KEY,
            base_url=settings.AI_PRICEHUB_PARSER_LLM_BASE_URL,
            temperature=0,
            callbacks=[self.callback_handler],
        )
        backend = FilesystemBackend(root_dir=str(self.root_dir))
        agent = create_deep_agent(
            model=llm,
            backend=backend,
            tools=tools,
            skills=[f"/skills/{skill_name}"],
            response_format=response_format,
            system_prompt=(
                "You extract AI model token pricing from vendor-owned pricing pages. "
                "Always fetch the vendor page, inspect the contents, and return structured JSON only."
            ),
        )
        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        structured = result.get("structured_response")
        if structured is None:
            raise ValueError("Deep agent did not return structured pricing output.")
        return structured

    def _build_vendor_tools(self, *, job_dir: Path, vendor: dict[str, Any]) -> list[Any]:
        @tool
        def get_vendor_context() -> str:
            """Return the configured vendor context, including vendor name, slug, pricing URL, currency, and aliases."""
            return json.dumps(vendor, ensure_ascii=False, indent=2)

        @tool
        def run_vendor_skill_python() -> str:
            """Run the vendor-specific deterministic pricing Python script and return its standard JSON result."""
            try:
                result = run_vendor_skill(vendor.get("slug", ""))
            except Exception as exc:
                return json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2)
            return json.dumps(result, ensure_ascii=False, indent=2)

        @tool
        def fetch_url_to_file(url: str) -> str:
            """Fetch a URL and save the response to the current job directory."""
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            suffix = self._guess_suffix(url=url, content_type=content_type)
            target = job_dir / f"resource-{uuid.uuid4().hex}{suffix}"
            target.write_text(response.text, encoding="utf-8")
            return json.dumps(
                {
                    "url": url,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "file_path": f"/{target.relative_to(self.root_dir).as_posix()}",
                },
                ensure_ascii=False,
                indent=2,
            )

        @tool
        def extract_urls_from_file(file_path: str, pattern: str = "") -> str:
            """Extract URLs or asset paths from a saved HTML or JS file."""
            resolved = self.root_dir / file_path.lstrip("/")
            text = resolved.read_text(encoding="utf-8")
            matches = re.findall(r'https?://[^"\'\\s)]+|/[^"\'\\s)]+', text)
            if pattern:
                regex = re.compile(pattern)
                matches = [item for item in matches if regex.search(item)]
            unique: list[str] = []
            for item in matches:
                if item not in unique:
                    unique.append(item)
            return json.dumps(unique[:200], ensure_ascii=False, indent=2)

        @tool
        def read_file_chunk(file_path: str, start: int = 0, length: int = 8000) -> str:
            """Read a chunk from a saved file so large HTML or JS resources can be inspected incrementally."""
            resolved = self.root_dir / file_path.lstrip("/")
            text = resolved.read_text(encoding="utf-8")
            return json.dumps(
                {
                    "file_path": file_path,
                    "start": start,
                    "length": length,
                    "content": text[start:start + length],
                },
                ensure_ascii=False,
                indent=2,
            )

        return [get_vendor_context, run_vendor_skill_python, fetch_url_to_file, extract_urls_from_file, read_file_chunk]

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

    @staticmethod
    def _build_vendor_discovery_prompt(*, vendor: dict[str, Any]) -> str:
        return (
            "Use the vendor metadata below as your starting context, then discover the vendor pricing resources and extract the full priced model catalog.\n"
            f"Vendor metadata:\n{json.dumps(vendor, ensure_ascii=False, indent=2)}\n"
            "Requirements:\n"
            "- Start from the vendor-owned pricing URL when available.\n"
            "- You may inspect HTML pages, JS bundles, JSON endpoints, or vendor assets as needed.\n"
            "- Return one item per supported priced model when you can substantiate it from fetched resources.\n"
            "- Normalize prices to the vendor currency per 1M tokens.\n"
            "- Distinguish market scope when the source provides different prices for China mainland versus international regions.\n"
            "- Set market_scope to domestic, international, or leave it null if the page does not distinguish regions.\n"
            "- Ignore batch, cache, training, discount, or promotional prices unless clearly marked as standard pricing.\n"
            "- Keep model names canonical and concise.\n"
        )

    @staticmethod
    def _validate_llm_config() -> None:
        if not getattr(settings, "AI_PRICEHUB_PARSER_LLM_API_KEY", ""):
            raise ValueError("AIPRICEHUB_PARSER_LLM_API_KEY is required for deepagent parsing.")
        if not getattr(settings, "AI_PRICEHUB_PARSER_LLM_MODEL", ""):
            raise ValueError("AIPRICEHUB_PARSER_LLM_MODEL is required for deepagent parsing.")
        if not getattr(settings, "AI_PRICEHUB_PARSER_LLM_BASE_URL", ""):
            raise ValueError("AIPRICEHUB_PARSER_LLM_BASE_URL is required for deepagent parsing.")


parser_agent_service = ParserAgentService()
