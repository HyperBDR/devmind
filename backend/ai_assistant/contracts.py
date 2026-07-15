"""Stable contracts shared by the assistant runtime and business apps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]
StreamHandler = Callable[..., Iterator[dict[str, Any]]]
ContextLoader = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class AssistantTool:
    """One app-owned tool exposed to its assistant only."""

    name: str
    description: str
    schema: dict[str, Any]
    handler: ToolHandler
    is_read_only: bool = True


@dataclass(frozen=True)
class MemoryPolicy:
    """Long-term memory policy for one assistant capability."""

    enable_conversation_summary: bool = True
    enable_user_preferences: bool = False
    retention_days: int = 90
    allowed_memory_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssistantCapability:
    """Complete AI capability registered by one business app."""

    app_key: str
    display_name: str
    required_feature: str
    instructions: str
    tools: tuple[AssistantTool, ...]
    skill_dirs: tuple[Path, ...] = ()
    memory_policy: MemoryPolicy = field(default_factory=MemoryPolicy)
    description: str = ""
    icon: str = ""
    version: str = "1"
    is_enabled: bool = True
    profile_loader: ContextLoader | None = None
    stream_handler: StreamHandler | None = None


@dataclass(frozen=True)
class SkillDescriptor:
    """Immutable skill content loaded from a local SKILL.md file."""

    key: str
    app_key: str
    description: str
    instructions: str
    allowed_tools: tuple[str, ...]
    version: str
    skill_dir: Path
    reference_files: tuple[Path, ...]
    fingerprint: str
