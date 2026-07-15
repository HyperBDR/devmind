"""Data Ops assistant capability entry point."""

from data_ops.assistant.capability import build_capability


def get_assistant_capability():
    """Return the Data Ops capability for global discovery."""

    return build_capability()
