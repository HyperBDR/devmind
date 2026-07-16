"""Data Ops assistant capability entry point."""

from data_ops.assistant.capability import DataOpsAssistantProvider

assistant_provider = DataOpsAssistantProvider()


def get_assistant_capability():
    """Return the Data Ops capability for global discovery."""

    return assistant_provider.build_capability()
