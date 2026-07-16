"""LLM Ops assistant capability entry point."""

from llm_ops.assistant.capability import LLMOpsAssistantProvider

assistant_provider = LLMOpsAssistantProvider()


def get_assistant_capability():
    """Return the LLM Ops capability for global discovery."""

    return assistant_provider.build_capability()
