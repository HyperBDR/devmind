"""Discover optional assistant capability modules from Django apps."""

from importlib import import_module

from django.apps import apps

from ai_assistant.registry import capability_registry


def autodiscover_capabilities() -> None:
    """Load ``get_assistant_capability`` from installed apps."""

    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.assistant"
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise
        loader = getattr(module, "get_assistant_capability", None)
        if loader is None:
            continue
        capability_registry.register(loader())
