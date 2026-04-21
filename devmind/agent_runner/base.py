"""
Generic dynamic Agent Runner.

Architectural principles:
- The runner is a generic execution engine. It assembles an agent from:
    (1) system prompt fragments  — provided by subclasses
    (2) skill subagents         — registered via SubAgentMiddleware; each skill
                                  is a self-contained sub-agent with its own tools
                                  and system prompt
    (3) extra tools             — provided by subclasses
- The main agent communicates with skill subagents exclusively through the
  `task` tool injected by SubAgentMiddleware.
- All execution traces (LLM runs, events, timing) are recorded uniformly so
  that any subclass inherits full observability without additional code.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Any, ClassVar, Dict, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from deepagents.backends.state import StateBackend
from deepagents.middleware.subagents import SubAgentMiddleware, SubAgent

from .observability.langfuse import (
    LangfuseAgentCallbackHandler,
    LangfuseRuntime,
    build_langfuse_runtime,
    extract_message_text,
)
from .spec import SkillSpec, _iter_skill_files

logger = logging.getLogger(__name__)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if not candidate:
        return None

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.IGNORECASE | re.DOTALL)
    candidates = [fence_match.group(1).strip()] if fence_match else []
    candidates.append(candidate)

    for item in candidates:
        try:
            parsed = json.loads(item)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# ---------------------------------------------------------------------------
# Base runner
# ---------------------------------------------------------------------------

class AgentRunner(ABC):
    """
    Generic dynamic agent runner.

    Subclasses must implement:
        build_system_prompt_fragments()  — returns ordered prompt fragments
        build_skill_specs()             — returns SkillSpec list for subagents
        build_tools()                   — returns extra tools for the main agent
        build_user_context()            — returns the initial user message content
        get_llm_model()                 — returns the chat model for the main agent

    The runner automatically:
        - Loads skill SKILL.md frontmatter as sub-agent specs
        - Registers skill sub-agents via SubAgentMiddleware (task tool)
        - Executes the agent with full tracing (LLM runs, events, timing)
    """

    # Subclasses override these to point at their skill directories
    SKILL_dirs: ClassVar[List[Path]] = []

    def __init__(
        self,
        *,
        record: Any,
        user_id: int | None = None,
        source_task_id: str | None = None,
        max_llm_run_records: int = 500,
        workspace_root: Path | None = None,
    ) -> None:
        self.record = record
        self.user_id = user_id
        self.source_task_id = source_task_id
        self.max_llm_run_records = max_llm_run_records
        # Resolve workspace root: env var takes precedence, otherwise infer from file location
        if workspace_root:
            self._workspace_root = workspace_root
        else:
            env_root = os.environ.get("WORKSPACE_ROOT", "").strip()
            if env_root:
                self._workspace_root = Path(env_root)
            else:
                # parents[2] of agent_runner/base.py → project root (e.g. /opt/devmind/)
                self._workspace_root = Path(__file__).resolve().parents[2]

        # Runtime state populated by execute()
        self._trace_started_at: Any = None
        self._trace_finished_at: Any = None

    # -------------------------------------------------------------------------
    # Abstract methods — implemented by subclasses
    # -------------------------------------------------------------------------

    @abstractmethod
    def build_system_prompt_fragments(self) -> List[str]:
        """Return ordered system prompt fragments. Joined with ``\\n\\n``."""

    @abstractmethod
    def build_skill_specs(self) -> List[SkillSpec]:
        """Return SkillSpec definitions for all skill sub-agents."""

    @abstractmethod
    def build_tools(self) -> List[BaseTool]:
        """Return extra tools for the main agent (besides skill task tools)."""

    @abstractmethod
    def build_user_context(self) -> str:
        """Return the initial user message content passed to the agent."""

    @abstractmethod
    def get_llm_model(self) -> BaseChatModel | str:
        """Return the chat model (model name str or BaseChatModel instance)."""

    @abstractmethod
    def record_llm_run(
        self,
        runner_type: str,
        provider: str,
        model: str,
        input_snapshot: str,
        output_snapshot: str,
        usage_payload: Dict[str, Any],
        stdout: str,
        stderr: str,
        started_at: Any,
        finished_at: Any,
        success: bool,
        **kwargs: Any,
    ) -> None:
        """
        Record one LLM run for observability.

        Subclasses typically call their own ``create_*_llm_run()`` helper here.
        """

    @abstractmethod
    def record_event(
        self,
        event_type: str,
        stage: str,
        source: str,
        message: str,
        payload: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record one execution event for observability.

        Subclasses typically call their own ``create_*_event()`` helper here.
        """

    # -------------------------------------------------------------------------
    # Execute — generic pipeline
    # -------------------------------------------------------------------------

    def execute(self) -> Dict[str, Any]:
        """
        Build and run the agent, recording full execution traces.

        Returns the agent's structured_response as a dict.
        """
        from django.utils import timezone

        self._trace_started_at = timezone.now()
        self.record_event(
            event_type="agent_started",
            stage="agent_execute",
            source="agent_runner",
            message=f"{self.__class__.__name__} execution started.",
            payload={"source_task_id": self.source_task_id or ""},
        )

        # 1. Build the system prompt from fragments
        fragments = self.build_system_prompt_fragments()
        system_prompt = "\n\n".join(f for f in fragments if f)
        logger.info(
            "AgentRunner system prompt (%d fragments):\n%s",
            len(fragments),
            system_prompt[:500],
        )

        # 2. Build extra tools + skill execution tools
        extra_tools = self.build_tools()
        skill_tools = self.build_skill_tools()
        all_tools = [*skill_tools, *extra_tools]
        logger.info(
            "AgentRunner tools: skill=%s extra=%s",
            [t.name for t in skill_tools],
            [t.name for t in extra_tools],
        )

        # 3. Register skill sub-agents via SubAgentMiddleware
        subagent_middleware, skill_subagents = self._build_skill_subagents()

        # 4. Build the agent
        model = self.get_llm_model()
        from . import create_deep_agent as package_create_deep_agent

        agent = package_create_deep_agent(
            model=model,
            tools=all_tools,
            backend=StateBackend,
            response_format=self.get_response_format(),
            system_prompt=system_prompt,
            name=self.__class__.__name__,
            middleware=[subagent_middleware] if subagent_middleware else [],
        )

        langfuse_runtime = self.get_langfuse_runtime()
        # 5. Build callbacks — merge existing handler with optional Langfuse handler
        callbacks = [handler for handler in [self._build_callback_handler()] if handler is not None]
        if langfuse_runtime is not None:
            callbacks.append(langfuse_runtime.callback_handler)

        # 5. Invoke
        user_context = self.build_user_context()
        logger.info("AgentRunner user context:\n%s", user_context[:500])
        invoke_payload = {
            "messages": [HumanMessage(content=user_context)],
            "files": self.build_skill_state_files(),
        }

        try:
            if langfuse_runtime is not None:
                langfuse_runtime.set_root_input(invoke_payload)
                with langfuse_runtime:
                    result = agent.invoke(
                        invoke_payload,
                        config={"callbacks": callbacks},
                    )
            else:
                result = agent.invoke(
                    invoke_payload,
                    config={"callbacks": callbacks},
                )
        except Exception as exc:
            self.record_event(
                event_type="agent_error",
                stage="agent_execute",
                source="agent_runner",
                message=f"Agent execution failed: {exc}",
                payload={"error": str(exc)},
            )
            raise

        self._trace_finished_at = timezone.now()

        # 6. Extract structured_response, or recover JSON from the final message.
        structured = result.get("structured_response")
        if structured is None:
            for key in ("output", "final", "response"):
                candidate = result.get(key)
                if isinstance(candidate, dict):
                    structured = candidate
                    break
                if isinstance(candidate, str):
                    parsed = _parse_json_object(candidate)
                    if parsed is not None:
                        structured = parsed
                        break
            if structured is None:
                parsed = _parse_json_object(extract_message_text(result.get("messages")))
                if parsed is not None:
                    structured = parsed
        if structured is None:
            structured = self.recover_structured_response(result)
        if structured is None:
            raw_result_text = extract_message_text(result)
            try:
                raw_result_dump = json.dumps(result, default=str, ensure_ascii=False, indent=2)
            except TypeError:
                raw_result_dump = str(result)
            logger.error(
                "Agent final output could not be parsed as structured_response.\n"
                "Raw final text:\n%s\n"
                "Raw result dump:\n%s",
                raw_result_text or "(empty)",
                raw_result_dump,
            )
            # Also print directly so it shows up in task logs / Celery worker output
            import sys
            print(
                f"\n===== AGENT RAW RESPONSE (unstructured) =====\n"
                f"Raw final text:\n{raw_result_text or '(empty)'}\n\n"
                f"Raw result dump:\n{raw_result_dump}\n"
                f"==============================================\n",
                file=sys.stderr,
            )
            self.record_event(
                event_type="agent_error",
                stage="agent_execute",
                source="agent_runner",
                message=(
                    "Agent did not return structured_response and no JSON payload "
                    "could be recovered from the final message."
                ),
                payload={
                    "raw_final_text": raw_result_text,
                    "raw_result_preview": raw_result_dump[:4000],
                },
            )
            raise RuntimeError(
                "Agent did not return structured_response and no JSON payload "
                "could be recovered from the final message.\n"
                f"Raw final text:\n{raw_result_text or '(empty)'}\n"
                f"Raw agent result:\n{raw_result_dump[:12000]}"
            )

        payload: Dict[str, Any]
        if isinstance(structured, dict):
            payload = structured
        else:
            payload = (
                structured.model_dump()
                if hasattr(structured, "model_dump")
                else dict(structured)
            )

        self.record_event(
            event_type="agent_completed",
            stage="agent_execute",
            source="agent_runner",
            message="Agent execution completed.",
            payload=payload,
        )
        return payload

    def recover_structured_response(self, result: Dict[str, Any]) -> Dict[str, Any] | None:
        """Subclass hook for recovering a result when an agent omits final JSON."""
        return None

    # -------------------------------------------------------------------------
    # Skill sub-agents
    # -------------------------------------------------------------------------

    def _build_skill_subagents(
        self,
    ) -> tuple[SubAgentMiddleware | None, List[SubAgent]]:
        specs = self.build_skill_specs()
        if not specs:
            return None, []

        subagent_configs: List[SubAgent] = []
        for spec in specs:
            tools_for_skill = self._collect_skill_tools(spec)
            subagent_configs.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "model": spec.model,
                    "tools": tools_for_skill,
                    "system_prompt": (
                        spec.system_prompt
                        or f"You are the {spec.name} agent. "
                          f"Use your available tools to complete the assigned task. "
                          f"Return a structured summary of what you did."
                    ),
                }
            )
            logger.info(
                "Registered skill sub-agent: name=%s model=%s tools=%s",
                spec.name,
                spec.model,
                [t.name for t in tools_for_skill],
            )

        middleware = SubAgentMiddleware(
            backend=StateBackend,
            subagents=subagent_configs,
            general_purpose_agent=False,
        )
        return middleware, subagent_configs

    def _collect_skill_tools(self, spec: SkillSpec) -> List[BaseTool]:
        """
        Return the tools to attach to a skill sub-agent.

        Default implementation:
        - Calls `get_skill_tools(skill_name)` if overridden.
        - Falls back to `spec._extra_tools`.
        Subclasses can override this method or set `spec._extra_tools` directly.
        """
        tools = self.get_skill_tools(spec.name)
        if tools is not NotImplemented:
            return tools
        return spec._extra_tools

    def get_skill_tools(self, skill_name: str) -> List[BaseTool] | type[NotImplemented]:
        """
        Hook for subclasses to provide tools for a specific skill sub-agent.

        Return ``NotImplemented`` (the singleton, not a list) to fall through
        to the skill spec's ``_extra_tools``.
        """
        return NotImplemented  # type: ignore[return-value]

    def prepare_skill_script_environment(
        self,
        full_env: Dict[str, str],
        tool_env: Dict[str, str],
    ) -> Dict[str, str]:
        """Hook for subclasses to adjust script execution environment."""
        return full_env

    def prepare_skill_script_invocation(
        self,
        script_path: Path,
        script_args: list[str],
    ) -> Dict[str, Any] | None:
        """Hook for subclasses to prepare files or metadata before script execution."""
        return None

    def resolve_skill_script_path(self, script: str) -> Path:
        """
        Resolve a script argument from agents into an executable file path.

        Agents sometimes pass the exact SKILL.md path, a workspace-relative path,
        a leading-slash injected skill path, or just a script filename. The last
        form is resolved against each registered skill directory's scripts/
        folder to avoid accidentally looking in the workspace root.
        """
        raw_script = Path(script)
        if raw_script.is_absolute():
            script_path = raw_script
            try:
                script_path.relative_to(self._workspace_root)
            except ValueError:
                script_path = self._workspace_root / str(raw_script).lstrip("/")
        else:
            script_path = self._workspace_root / raw_script
        if script_path.exists():
            return script_path

        candidates: list[Path] = []
        for skill_dir in self.SKILL_dirs:
            candidates.extend(
                [
                    skill_dir / raw_script,
                    skill_dir / "scripts" / raw_script.name,
                ]
            )
            candidates.extend(skill_dir.glob(f"*/scripts/{raw_script.name}"))
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return script_path

    # -------------------------------------------------------------------------
    # Generic script execution tool — used by agents following skill instructions
    # -------------------------------------------------------------------------

    def build_skill_tools(self) -> List[BaseTool]:
        """
        Return the generic skill execution tools.

        Subclasses can override to add more tools or filter the list.
        The default set includes:
          - run_skill_script: executes a Python script with env vars, captures output
        """
        import json
        import hashlib
        import os
        import shlex
        import subprocess
        import sys
        import time
        from pathlib import Path
        from django.utils import timezone

        workspace = self._workspace_root

        def _mask_env(env: Dict[str, str]) -> Dict[str, str]:
            return {
                k: ("***REDACTED***" if any(x in k.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "KEY")) else v)
                for k, v in env.items()
            }

        def _redact_text(value: Any) -> str:
            text = str(value or "")
            if not text:
                return ""
            text = re.sub(
                r"(?i)(secret|token|password|authorization|app_secret)(['\"\s:=]+)([^,'\"\s}]+)",
                r"\1\2***REDACTED***",
                text,
            )
            text = re.sub(r"\b\d{12,}\b", lambda m: f"***{m.group(0)[-4:]}", text)
            return text

        def _redact_payload(value: Any) -> Any:
            if isinstance(value, dict):
                result: dict[str, Any] = {}
                for key, item in value.items():
                    if any(seg in str(key).upper() for seg in ("SECRET", "TOKEN", "PASSWORD", "KEY", "AUTHORIZATION")):
                        result[key] = "***REDACTED***"
                    else:
                        result[key] = _redact_payload(item)
                return result
            if isinstance(value, list):
                return [_redact_payload(item) for item in value]
            if isinstance(value, str):
                return _redact_text(value)
            return value

        def _preview_text(value: Any, limit: int = 2000) -> str:
            return _redact_text(value)[:limit]

        def _request_file_arg(args: list[str]) -> Path | None:
            for index, token in enumerate(args):
                if token == "--request-file" and index + 1 < len(args):
                    return Path(args[index + 1])
                if token.startswith("--request-file="):
                    return Path(token.split("=", 1)[1])
            return None

        def _request_file_sha256(path: Path | None) -> str:
            if path is None:
                return ""
            target = path if path.is_absolute() else workspace / path
            try:
                return hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError:
                return ""

        def _script_trace_payload(
            *,
            script_path: Path,
            args: list[str],
            env: Dict[str, str],
            attempt: int,
            max_attempts: int,
            cmd_display: str,
            exit_code: Any,
            success: bool,
            latency_ms: int,
            stdout: str,
            stderr: str,
        ) -> dict[str, Any]:
            request_file = _request_file_arg(args)
            request_file_str = ""
            if request_file is not None:
                request_file_str = str(request_file if request_file.is_absolute() else workspace / request_file)
            try:
                relative_script = str(script_path.relative_to(workspace))
            except ValueError:
                relative_script = str(script_path)
            return {
                "script_path": relative_script,
                "script_name": script_path.name,
                "args": _redact_payload(args),
                "cwd": str(workspace),
                "python_executable": sys.executable,
                "env": _mask_env(env),
                "env_keys": sorted(env.keys()),
                "request_file": request_file_str,
                "request_file_sha256": _request_file_sha256(request_file),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "command": _preview_text(cmd_display, 2000),
                "exit_code": exit_code,
                "success": success,
                "latency_ms": latency_ms,
                "stdout_preview": _preview_text(stdout, 2000),
                "stderr_preview": _preview_text(stderr, 2000),
            }

        def _record_script_run(trace: dict[str, Any], stdout: str, stderr: str, started_at: Any, finished_at: Any) -> None:
            self.record_llm_run(
                runner_type="script",
                provider="subprocess",
                model=str(trace.get("script_name") or ""),
                input_snapshot=json.dumps(trace, ensure_ascii=False, indent=2),
                output_snapshot=json.dumps(
                    {
                        "stdout_preview": trace.get("stdout_preview", ""),
                        "stderr_preview": trace.get("stderr_preview", ""),
                        "exit_code": trace.get("exit_code"),
                        "success": trace.get("success"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                parsed_payload=trace,
                usage_payload={},
                stdout=_preview_text(stdout, 8000),
                stderr=_preview_text(stderr, 8000),
                started_at=started_at,
                finished_at=finished_at,
                success=bool(trace.get("success")),
                error_message="" if trace.get("success") else str(trace.get("stderr_preview") or "Script failed."),
            )

        def _record_http_traces(stdout: str, parent_trace: dict[str, Any]) -> None:
            try:
                parsed = json.loads(stdout or "{}")
            except json.JSONDecodeError:
                return
            traces = parsed.get("http_traces")
            if not isinstance(traces, list):
                return
            for item in traces:
                if not isinstance(item, dict):
                    continue
                sanitized = _redact_payload(item)
                endpoint_name = str(sanitized.get("endpoint_name") or sanitized.get("url") or "http")
                success = bool(sanitized.get("success"))
                self.record_llm_run(
                    runner_type="skill_http",
                    provider="urllib.request",
                    model=endpoint_name,
                    input_snapshot=json.dumps(sanitized.get("request_preview", {}), ensure_ascii=False, indent=2),
                    output_snapshot=json.dumps(sanitized.get("response_preview", {}), ensure_ascii=False, indent=2),
                    parsed_payload={
                        **sanitized,
                        "parent_script": parent_trace.get("script_path", ""),
                        "parent_attempt": parent_trace.get("attempt"),
                    },
                    usage_payload={},
                    stdout=json.dumps(sanitized.get("response_preview", {}), ensure_ascii=False)[:8000],
                    stderr=str(sanitized.get("error") or ""),
                    started_at=timezone.now(),
                    finished_at=timezone.now(),
                    success=success,
                    error_message=str(sanitized.get("error") or ""),
                )

        def _format_cmd(cmd: list[str]) -> str:
            return " ".join(shlex.quote(part) for part in cmd)

        def _split_script_args(script_args: str) -> list[str]:
            if not script_args.strip():
                return []
            return shlex.split(script_args)

        def _is_retryable_failure(exc: BaseException | None, result: subprocess.CompletedProcess[str] | None) -> bool:
            if exc is not None:
                return True
            if result is None or result.returncode == 0:
                return False
            stderr = (result.stderr or "").lower()
            stdout = (result.stdout or "").lower()
            text = f"{stderr}\n{stdout}"
            retry_markers = (
                "timeout",
                "timed out",
                "network error",
                "connection reset",
                "temporarily unavailable",
                "service unavailable",
                "503",
                "502",
                "504",
                "too many requests",
                "rate limit",
                "temporary failure",
            )
            return any(marker in text for marker in retry_markers)

        def _adjust_command_for_retry(cmd: list[str], stderr: str) -> tuple[list[str], str | None]:
            lowered = stderr.lower()
            if "unrecognized arguments" in lowered and any(
                token == "--output" or token.startswith("--output=") for token in cmd
            ):
                adjusted = list(cmd)
                for index, token in enumerate(list(adjusted)):
                    if token == "--output":
                        del adjusted[index : min(index + 2, len(adjusted))]
                        break
                    if token.startswith("--output="):
                        del adjusted[index]
                        break
                return adjusted, "dropped --output after argparse rejection"
            return cmd, None

        @tool
        def run_skill_script(
            script: Annotated[str, "Path to the Python script to run, relative to workspace root."],
            script_args: Annotated[str, "Command-line arguments, e.g. 'submit --request-file /tmp/req.json'."] = "",
            env_vars: Annotated[str, "JSON object of environment variables to set before running."] = "{}",
        ) -> str:
            """
            Execute a Python skill script and return its stdout as a JSON string.

            The agent reads the skill's SKILL.md to determine which script to call
            and what arguments to pass. Environment variables (e.g. API credentials)
            must be passed explicitly via ``env_vars`` — never hard-code secrets.
            """
            env = json.loads(env_vars) if env_vars and env_vars != "{}" else {}
            full_env = {**os.environ, **env}
            full_env = self.prepare_skill_script_environment(full_env, env)
            trace_env = {
                key: value
                for key, value in full_env.items()
                if key in env or key.startswith("FEISHU_")
            }

            script_path = self.resolve_skill_script_path(script)
            if not script_path.exists():
                raise RuntimeError(f"Script not found: {script_path}")
            masked = _mask_env(full_env)
            base_args = _split_script_args(script_args)
            attempts: list[dict[str, Any]] = []
            max_attempts = 3
            current_script_path = script_path
            current_args = list(base_args)
            prepared = self.prepare_skill_script_invocation(
                current_script_path,
                current_args,
            )
            if prepared:
                logger.info(
                    "run_skill_script prepared invocation: %s",
                    prepared,
                )
                self.record_event(
                    event_type=str(prepared.get("event_type") or "skill_script_invocation_prepared"),
                    stage="skill_execute",
                    source="run_skill_script",
                    message=str(prepared.get("message") or "Skill script invocation prepared."),
                    payload={
                        "script": str(current_script_path.relative_to(workspace)),
                        **{k: v for k, v in prepared.items() if k not in {"event_type", "message"}},
                    },
                )

            for attempt in range(1, max_attempts + 1):
                cmd = [sys.executable, str(current_script_path), *current_args]
                cmd_display = _format_cmd(cmd)
                logger.info(
                    "run_skill_script attempt %d/%d:\n"
                    "  Script: %s\n"
                    "  Command: %s\n"
                    "  Environment Variables (masked):\n%s",
                    attempt,
                    max_attempts,
                    str(current_script_path),
                    cmd_display,
                    json.dumps(masked, ensure_ascii=False, indent=2),
                )
                self.record_event(
                    event_type="skill_script_attempt_started",
                    stage="skill_execute",
                    source="run_skill_script",
                    message=f"Skill script attempt {attempt} started.",
                    payload={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "script": str(current_script_path.relative_to(workspace)),
                        "command": cmd_display,
                    },
                )

                start = time.monotonic()
                started_at = timezone.now()
                result = None
                timeout_exc: subprocess.TimeoutExpired | None = None
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        env=full_env,
                        cwd=str(workspace),
                        timeout=120,
                    )
                except subprocess.TimeoutExpired as exc:
                    timeout_exc = exc
                latency_ms = int((time.monotonic() - start) * 1000)
                finished_at = timezone.now()

                if timeout_exc is None and result is not None and result.returncode == 0:
                    stdout = (result.stdout or "").strip()
                    stderr = (result.stderr or "").strip()
                    trace = _script_trace_payload(
                        script_path=current_script_path,
                        args=current_args,
                        env=trace_env,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        cmd_display=cmd_display,
                        exit_code=result.returncode,
                        success=True,
                        latency_ms=latency_ms,
                        stdout=stdout,
                        stderr=stderr,
                    )
                    _record_script_run(trace, stdout, stderr, started_at, finished_at)
                    _record_http_traces(stdout, trace)
                    logger.info(
                        "run_skill_script succeeded on attempt %d/%d: latency=%dms\n"
                        "Stdout (%d bytes):\n%s",
                        attempt,
                        max_attempts,
                        latency_ms,
                        len(stdout),
                        stdout[:1000],
                    )
                    self.record_event(
                        event_type="skill_script_attempt_completed",
                        stage="skill_execute",
                        source="run_skill_script",
                        message="Skill script attempt completed successfully.",
                        payload={
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "latency_ms": latency_ms,
                            "script": str(current_script_path.relative_to(workspace)),
                            "command": cmd_display,
                            "stdout_preview": stdout[:1000],
                        },
                    )
                    return stdout

                stderr_text = ""
                stdout_text = ""
                if timeout_exc is not None:
                    stderr_text = f"TimeoutExpired after {timeout_exc.timeout}s"
                    stdout_text = timeout_exc.stdout or ""
                elif result is not None:
                    stderr_text = (result.stderr or "").strip()
                    stdout_text = (result.stdout or "").strip()

                if attempt < max_attempts:
                    adjusted_cmd, adjustment_reason = _adjust_command_for_retry(cmd, stderr_text)
                    retryable = _is_retryable_failure(timeout_exc, result)
                    next_script_path = current_script_path
                    next_args = current_args
                    if adjusted_cmd != cmd:
                        next_script_path = Path(adjusted_cmd[1])
                        next_args = adjusted_cmd[2:]
                        retryable = True
                    if retryable:
                        sleep_seconds = min(0.5 * (2 ** (attempt - 1)), 3.0)
                        logger.warning(
                            "run_skill_script attempt %d/%d failed and will retry after %.1fs:\n"
                            "  reason=%s\n"
                            "  stderr=%s\n"
                            "  stdout=%s",
                            attempt,
                            max_attempts,
                            sleep_seconds,
                            adjustment_reason or (stderr_text or "retryable failure"),
                            stderr_text[:1000] or "(empty)",
                            stdout_text[:500] or "(empty)",
                        )
                        self.record_event(
                            event_type="skill_script_attempt_retry",
                            stage="skill_execute",
                            source="run_skill_script",
                            message="Skill script attempt failed; retrying.",
                            payload={
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "latency_ms": latency_ms,
                                "script": str(current_script_path.relative_to(workspace)),
                                "command": cmd_display,
                                "adjustment_reason": adjustment_reason or "",
                                "stderr_preview": stderr_text[:1000],
                                "stdout_preview": stdout_text[:500],
                            },
                        )
                        time.sleep(sleep_seconds)
                        current_script_path = next_script_path
                        current_args = next_args
                        attempts.append(
                            {
                                "attempt": attempt,
                                "command": cmd_display,
                                "stderr": stderr_text,
                                "stdout": stdout_text,
                                "reason": adjustment_reason or stderr_text,
                            }
                        )
                        continue

                logger.error(
                    "run_skill_script failed after %d attempt(s):\n"
                    "  exit=%s  latency=%dms\n"
                    "  Script: %s\n"
                    "  Command: %s\n"
                    "  Stderr:\n%s\n"
                    "  Stdout:\n%s",
                    attempt,
                    timeout_exc.__class__.__name__ if timeout_exc is not None else (
                        result.returncode if result is not None else "unknown"
                    ),
                    latency_ms,
                    str(current_script_path),
                    cmd_display,
                    stderr_text[:2000] or "(empty)",
                    stdout_text[:1000] or "(empty)",
                )
                trace = _script_trace_payload(
                    script_path=current_script_path,
                    args=current_args,
                    env=trace_env,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    cmd_display=cmd_display,
                    exit_code=timeout_exc.__class__.__name__ if timeout_exc is not None else (
                        result.returncode if result is not None else "unknown"
                    ),
                    success=False,
                    latency_ms=latency_ms,
                    stdout=stdout_text,
                    stderr=stderr_text,
                )
                _record_script_run(trace, stdout_text, stderr_text, started_at, finished_at)
                _record_http_traces(stdout_text, trace)
                self.record_event(
                    event_type="skill_script_attempt_failed",
                    stage="skill_execute",
                    source="run_skill_script",
                    message="Skill script failed.",
                    payload={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "latency_ms": latency_ms,
                        "script": str(current_script_path.relative_to(workspace)),
                        "command": cmd_display,
                        "stderr_preview": stderr_text[:2000],
                        "stdout_preview": stdout_text[:1000],
                        "retries": attempts,
                    },
                )
                if timeout_exc is not None:
                    raise RuntimeError(
                        f"Script timed out after {timeout_exc.timeout} seconds.\n"
                        f"Command: {cmd_display}\n"
                        f"Stderr: {stderr_text or '(empty)'}\n"
                        f"Stdout: {stdout_text or '(empty)'}"
                    )
                raise RuntimeError(
                    f"Script exited with code {timeout_exc.__class__.__name__ if timeout_exc is not None else (result.returncode if result is not None else 'unknown')}.\n"
                    f"Command: {cmd_display}\n"
                    f"Stderr: {stderr_text or '(empty)'}\n"
                    f"Stdout: {stdout_text or '(empty)'}"
                )

        return [run_skill_script]

    # -------------------------------------------------------------------------
    # Skill state files — make skill markdown/references available to the agent
    # -------------------------------------------------------------------------

    def build_skill_state_files(self) -> Dict[str, Any]:
        """
        Scan ``SKILL_dirs`` and load every skill's SKILL.md and reference files
        into agent state so the agent can read them at runtime.
        """
        from deepagents.backends.utils import create_file_data

        files: Dict[str, Any] = {}
        workspace = self._workspace_root
        for skill_dir in self.SKILL_dirs:
            if not skill_dir.is_dir():
                continue
            for ref_file in _iter_skill_files(skill_dir):
                rel = ref_file.relative_to(workspace).as_posix()
                file_data = create_file_data(ref_file.read_text(encoding="utf-8"))
                files[f"/{rel}"] = file_data
                try:
                    skill_rel = ref_file.relative_to(skill_dir).as_posix()
                except ValueError:
                    continue
                files[f"/{skill_rel}"] = file_data
                skill_parts = Path(skill_rel).parts
                if len(skill_parts) > 1:
                    files[f"/{'/'.join(skill_parts[1:])}"] = file_data
        return files

    # -------------------------------------------------------------------------
    # Callback hook — subclasses can override to inject additional callbacks
    # -------------------------------------------------------------------------

    def _build_callback_handler(
        self,
        *,
        langfuse_runtime: LangfuseRuntime | None = None,
    ) -> Any:
        """Return a callback handler for the agent invocation. Override as needed."""
        return None

    def get_langfuse_callback_handler(self) -> Any:
        """
        Build and return a Langfuse callback handler if Langfuse is configured.

        Returns None when langfuse is unavailable or LANGFUSE_ENABLED is false,
        so subclasses that don't care about observability stay unaffected.
        """
        try:
            runtime = self.get_langfuse_runtime()
        except Exception as exc:
            logger.warning("Langfuse tracing disabled: %s", exc)
            return None
        return runtime.callback_handler if runtime is not None else None

    def get_langfuse_runtime(self) -> LangfuseRuntime | None:
        """Build and return a Langfuse runtime if Langfuse is configured."""
        try:
            return build_langfuse_runtime(
                runner_name=self.__class__.__name__,
                record=self.record,
                user_id=self.user_id,
                source_task_id=self.source_task_id,
            )
        except Exception as exc:
            logger.warning("Langfuse tracing disabled: %s", exc)
            return None

    # -------------------------------------------------------------------------
    # Response format — subclasses override to provide their Pydantic model
    # -------------------------------------------------------------------------

    def get_response_format(self) -> Any:
        """Return the response_format for create_deep_agent. Defaults to None."""
        return None

    # -------------------------------------------------------------------------
    # Helper — record an execution summary after execute() returns
    # -------------------------------------------------------------------------

    def record_execution_summary(
        self,
        runner_type: str,
        provider: str,
        model: str,
        input_snapshot: str,
        output_snapshot: str,
        latency_ms: int,
        stdout: str,
        stderr: str,
        success: bool,
    ) -> None:
        """Convenience wrapper that calls record_llm_run with timing."""
        from django.utils import timezone

        now = timezone.now()
        started = now - timezone.timedelta(milliseconds=latency_ms)
        self.record_llm_run(
            runner_type=runner_type,
            provider=provider,
            model=model,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            usage_payload={"latency_ms": latency_ms},
            stdout=stdout,
            stderr=stderr,
            started_at=started,
            finished_at=now,
            success=success,
        )
