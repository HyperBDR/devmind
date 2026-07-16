"""Template contract for app-owned assistant capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ai_assistant.contracts import (
    AssistantCapability,
    AssistantTool,
    ContextLoader,
    MemoryPolicy,
    StreamHandler,
)


class AssistantCapabilityProvider(ABC):
    """Build one app capability through a stable template contract."""

    app_key = ""
    display_name = ""
    required_feature = ""
    description = ""
    icon = ""
    version = "1"
    is_enabled = True

    @abstractmethod
    def get_instructions(self) -> str:
        """Return the app-specific system instructions."""

    @abstractmethod
    def get_tools(self) -> tuple[AssistantTool, ...]:
        """Return tools owned by this app capability."""

    def get_skill_dirs(self) -> tuple[Path, ...]:
        """Return local skill roots owned by this app."""

        return ()

    def get_memory_policy(self) -> MemoryPolicy:
        """Return the app-specific long-term memory policy."""

        return MemoryPolicy()

    def get_profile_loader(self) -> ContextLoader | None:
        """Return optional UI profile loader."""

        return None

    def get_stream_handler(self) -> StreamHandler | None:
        """Return an optional legacy streaming handler."""

        return None

    def build_capability(self) -> AssistantCapability:
        """Build the immutable runtime contract after validation."""

        metadata = (
            str(self.app_key).strip(),
            str(self.display_name).strip(),
            str(self.required_feature).strip(),
        )
        if not all(metadata):
            raise ValueError(
                "app_key, display_name and required_feature are required"
            )
        instructions = str(self.get_instructions() or "").strip()
        if not instructions:
            raise ValueError("assistant instructions are required")
        return AssistantCapability(
            app_key=metadata[0],
            display_name=metadata[1],
            required_feature=metadata[2],
            description=str(self.description or "").strip(),
            icon=str(self.icon or "").strip(),
            version=str(self.version or "1").strip(),
            is_enabled=bool(self.is_enabled),
            instructions=instructions,
            tools=tuple(self.get_tools()),
            skill_dirs=tuple(self.get_skill_dirs()),
            memory_policy=self.get_memory_policy(),
            profile_loader=self.get_profile_loader(),
            stream_handler=self.get_stream_handler(),
        )
