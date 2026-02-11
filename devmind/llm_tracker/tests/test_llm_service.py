"""
Tests for get_llm_service: config resolution and ValueError when incomplete.

Mocks Django settings to avoid real API keys.
"""
import pytest
from unittest.mock import patch

from llm_tracker.llm_service import get_llm_service


@pytest.mark.unit
class TestGetLlmServiceOpenAI:
    """
    get_llm_service with LLM_PROVIDER=openai.
    """

    @patch("llm_tracker.llm_service.settings")
    @patch("llm_tracker.llm_service.LLMService")
    @patch("llm_tracker.llm_service.OpenAIConfig")
    def test_returns_llm_service_when_openai_configured(
        self, mock_config_cls, mock_llm_svc_cls, mock_settings
    ):
        """
        With api_key set, returns LLMService(OpenAIConfig(...)).
        """
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_CONFIG = {"api_key": "sk-x", "model": "gpt-4"}

        get_llm_service()

        mock_config_cls.assert_called_once_with(
            api_key="sk-x", model="gpt-4"
        )
        mock_llm_svc_cls.assert_called_once()

    @patch("llm_tracker.llm_service.settings")
    def test_raises_when_openai_api_key_missing(self, mock_settings):
        """
        ValueError when OPENAI_CONFIG has no api_key.
        """
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_CONFIG = {}

        with pytest.raises(
            ValueError, match="OpenAI configuration is incomplete"
        ):
            get_llm_service()


@pytest.mark.unit
class TestGetLlmServiceAzure:
    """
    get_llm_service with LLM_PROVIDER=azure_openai.
    """

    @patch("llm_tracker.llm_service.settings")
    @patch("llm_tracker.llm_service.LLMService")
    @patch("llm_tracker.llm_service.AzureOpenAIConfig")
    def test_returns_llm_service_when_azure_configured(
        self, mock_config_cls, mock_llm_svc_cls, mock_settings
    ):
        """
        With api_key and api_base set, returns LLMService(AzureOpenAIConfig).
        """
        mock_settings.LLM_PROVIDER = "azure_openai"
        mock_settings.AZURE_OPENAI_CONFIG = {
            "api_key": "k",
            "api_base": "https://azure.example.com",
        }

        get_llm_service()

        mock_config_cls.assert_called_once()
        mock_llm_svc_cls.assert_called_once()

    @patch("llm_tracker.llm_service.settings")
    def test_raises_when_azure_api_key_missing(self, mock_settings):
        """
        ValueError when AZURE_OPENAI_CONFIG missing api_key or api_base.
        """
        mock_settings.LLM_PROVIDER = "azure_openai"
        mock_settings.AZURE_OPENAI_CONFIG = {"api_base": "https://x.com"}

        with pytest.raises(ValueError, match="Azure OpenAI configuration"):
            get_llm_service()

    @patch("llm_tracker.llm_service.settings")
    def test_raises_when_azure_api_base_missing(self, mock_settings):
        """
        ValueError when api_key set but api_base missing.
        """
        mock_settings.LLM_PROVIDER = "azure_openai"
        mock_settings.AZURE_OPENAI_CONFIG = {"api_key": "k"}

        with pytest.raises(ValueError, match="Azure OpenAI configuration"):
            get_llm_service()


@pytest.mark.unit
class TestGetLlmServiceGemini:
    """
    get_llm_service with LLM_PROVIDER=gemini.
    """

    @patch("llm_tracker.llm_service.settings")
    @patch("llm_tracker.llm_service.LLMService")
    @patch("llm_tracker.llm_service.GeminiConfig")
    def test_returns_llm_service_when_gemini_configured(
        self, mock_config_cls, mock_llm_svc_cls, mock_settings
    ):
        """
        With api_key set, returns LLMService(GeminiConfig(...)).
        """
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GEMINI_CONFIG = {"api_key": "gkey"}

        get_llm_service()

        mock_config_cls.assert_called_once_with(api_key="gkey")
        mock_llm_svc_cls.assert_called_once()

    @patch("llm_tracker.llm_service.settings")
    def test_raises_when_gemini_api_key_missing(self, mock_settings):
        """
        ValueError when GEMINI_CONFIG has no api_key.
        """
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GEMINI_CONFIG = {}

        with pytest.raises(ValueError, match="Google Gemini configuration"):
            get_llm_service()
