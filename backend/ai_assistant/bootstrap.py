"""Process-local startup for assistant capabilities and skills."""

from threading import Lock

from ai_assistant.discovery import autodiscover_capabilities
from ai_assistant.registry import capability_registry
from ai_assistant.skills import skill_catalog


_bootstrap_lock = Lock()
_bootstrapped = False


def bootstrap_assistant() -> None:
    """Discover capabilities and preload local skills once."""

    global _bootstrapped

    if _bootstrapped:
        return
    with _bootstrap_lock:
        if _bootstrapped:
            return
        autodiscover_capabilities()
        skill_catalog.initialize(capability_registry.all())
        _bootstrapped = True
