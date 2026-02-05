"""
LLM service utility for DevMind.

Provides unified interface for initializing LLM services based on
core.settings.ai_services configuration.
"""
import logging

from django.conf import settings
from devtoolbox.llm.azure_openai_provider import AzureOpenAIConfig
from devtoolbox.llm.openai_provider import OpenAIConfig
from devtoolbox.llm.gemini_provider import GeminiConfig
from devtoolbox.llm.service import LLMService

logger = logging.getLogger(__name__)


def get_llm_service() -> LLMService:
    """
    Get LLM service instance based on configuration.

    Returns:
        LLMService: Configured LLM service instance

    Raises:
        ValueError: If configuration is invalid
    """
    provider = getattr(settings, "LLM_PROVIDER", "openai").lower()

    if provider == "azure_openai":
        azure_config = getattr(settings, "AZURE_OPENAI_CONFIG", {})
        if not azure_config.get("api_key") or not azure_config.get("api_base"):
            raise ValueError(
                "Azure OpenAI configuration is incomplete. "
                "Please set AZURE_OPENAI_API_KEY and "
                "AZURE_OPENAI_API_BASE in environment variables."
            )
        llm_config = AzureOpenAIConfig(**azure_config)
        logger.debug(
            f"Azure OpenAI service: {azure_config.get('deployment')}"
        )
    elif provider == "gemini":
        gemini_config = getattr(settings, "GEMINI_CONFIG", {})
        if not gemini_config.get("api_key"):
            raise ValueError(
                "Google Gemini configuration is incomplete. "
                "Please set GOOGLE_API_KEY or GEMINI_API_KEY in "
                "environment variables."
            )
        llm_config = GeminiConfig(**gemini_config)
        logger.debug(
            f"Google Gemini service: {gemini_config.get('model', 'default')}"
        )
    else:
        openai_config = getattr(settings, "OPENAI_CONFIG", {})
        if not openai_config.get("api_key"):
            raise ValueError(
                "OpenAI configuration is incomplete. "
                "Please set OPENAI_API_KEY in environment variables."
            )
        llm_config = OpenAIConfig(**openai_config)
        logger.debug(
            f"OpenAI service: {openai_config.get('model', 'default')}"
        )

    return LLMService(llm_config)
