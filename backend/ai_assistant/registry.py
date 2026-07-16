"""In-process registry for app-owned assistant capabilities."""

from __future__ import annotations

from ai_assistant.contracts import AssistantCapability


class CapabilityNotFound(LookupError):
    """Raised when an app has no enabled assistant capability."""


class CapabilityRegistry:
    """Store immutable capabilities without request-specific state."""

    def __init__(self) -> None:
        self._capabilities: dict[str, AssistantCapability] = {}

    def register(self, capability: AssistantCapability) -> None:
        """Validate and register one capability."""

        if capability.app_key in self._capabilities:
            raise ValueError(
                "Duplicate assistant capability: "
                f"{capability.app_key}"
            )
        tool_names = [tool.name for tool in capability.tools]
        duplicates = {
            name for name in tool_names if tool_names.count(name) > 1
        }
        if duplicates:
            duplicate_names = ", ".join(sorted(duplicates))
            raise ValueError(
                f"Duplicate assistant tool: {duplicate_names}"
            )
        self._capabilities[capability.app_key] = capability

    def get(self, app_key: str) -> AssistantCapability | None:
        """Return an enabled capability when it exists."""

        capability = self._capabilities.get(app_key)
        if capability is None or not capability.is_enabled:
            return None
        return capability

    def require(self, app_key: str) -> AssistantCapability:
        """Return a capability or raise a stable lookup exception."""

        capability = self.get(app_key)
        if capability is None:
            raise CapabilityNotFound(app_key)
        return capability

    def all(self) -> tuple[AssistantCapability, ...]:
        """Return enabled capabilities in stable app-key order."""

        return tuple(
            capability
            for app_key, capability in sorted(self._capabilities.items())
            if capability.is_enabled
        )

    def reset(self) -> None:
        """Clear the registry for isolated tests."""

        self._capabilities.clear()


capability_registry = CapabilityRegistry()
