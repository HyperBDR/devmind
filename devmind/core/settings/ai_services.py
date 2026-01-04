"""
AI Services configuration for LLM.

This module configures:
- OpenAI for LLM text generation
- Azure OpenAI for LLM text generation (alternative)
- LLM output language preferences
"""

import os

# ============================
# OpenAI Configuration
# ============================

# OPENAI_CONFIG: OpenAI service configuration
# - Use Case: LLM text generation for article processing
# - Security: Store API_KEY in environment variables only
# - Documentation: https://platform.openai.com/docs/api-reference
OPENAI_CONFIG = {
    # API base URL for OpenAI
    # Default: https://api.openai.com/v1/
    # For custom endpoints or proxies, change this value
    'api_base': os.getenv(
        'OPENAI_API_BASE',
        'https://api.openai.com/v1/'
    ),

    # API key for authentication
    # Security: Never commit this to version control
    # How to get: OpenAI Platform → API Keys
    'api_key': os.getenv('OPENAI_API_KEY'),

    # Model name to use
    # Examples: 'gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-4o', 'gpt-4o-mini', 'gpt-5-nano'
    # Default: gpt-5-nano (cost-effective)
    'model': os.getenv('OPENAI_MODEL', 'gpt-5-nano'),

    # Maximum tokens for LLM response
    # - Use Case: Control response length and cost
    # - Range: 1-128000 (varies by model, e.g., gpt-5-nano supports up to 128k)
    # - Default: 60000 (increased for reasoning models)
    # - Note: Reasoning models need extra tokens for reasoning + output
    #   Reasoning tokens (8k-20k) + Output tokens (4k-10k) = ~20k-30k minimum
    #   60000 provides comfortable buffer for complex articles
    'max_tokens': int(os.getenv('OPENAI_MAX_TOKENS', '60000')),

    # Temperature for response randomness
    # - Use Case: Control creativity vs consistency
    # - Range: 0.0-2.0
    # - Default: 0.7 (balanced)
    # - 0.0: Deterministic, consistent responses
    # - 2.0: Creative, varied responses
    'temperature': float(os.getenv('OPENAI_TEMPERATURE', '1')),
}

# ============================
# Azure OpenAI Configuration (Alternative)
# ============================

# AZURE_OPENAI_CONFIG: Azure OpenAI service configuration
# - Use Case: LLM text generation using Azure OpenAI
# - Security: Store API_KEY in environment variables only
# - Documentation: https://learn.microsoft.com/en-us/azure/ai-services/openai/
AZURE_OPENAI_CONFIG = {
    # API base URL from Azure OpenAI resource
    # Format: https://{your-resource-name}.openai.azure.com/
    'api_base': os.getenv('AZURE_OPENAI_API_BASE'),

    # API key for authentication
    # Security: Never commit this to version control
    # How to get: Azure Portal → OpenAI Resource → Keys and Endpoint
    'api_key': os.getenv('AZURE_OPENAI_API_KEY'),

    # Deployment name created in Azure OpenAI Studio
    # Example: 'gpt-4', 'gpt-35-turbo', 'gpt-4o', 'gpt-4o-mini', 'gpt-5-nano'
    # Default: gpt-5-nano
    'deployment': os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5-nano'),

    # API version for Azure OpenAI service
    # Format: YYYY-MM-DD (e.g., '2024-10-01-preview')
    # Latest versions: https://learn.microsoft.com/en-us/azure/ai-services/openai/reference
    'api_version': os.getenv(
        'AZURE_OPENAI_API_VERSION',
        '2024-10-01-preview'
    ),

    # Maximum tokens for LLM response
    # - Use Case: Control response length and cost
    # - Range: 1-128000 (for gpt-5-nano reasoning model)
    # - Default: 60000 (increased for reasoning models)
    # - Note: Reasoning models need extra tokens for reasoning + output
    #   Reasoning tokens (8k-20k) + Output tokens (4k-10k) = ~20k-30k minimum
    #   60000 provides comfortable buffer for complex articles
    'max_tokens': int(os.getenv('AZURE_OPENAI_MAX_TOKENS', '60000')),

    # Temperature for response randomness
    # - Use Case: Control creativity vs consistency
    # - Range: 0.0-2.0 (for most models)
    # - Default: 0.7 (balanced)
    # - 0.0: Deterministic, consistent responses
    # - 2.0: Creative, varied responses
    'temperature': float(os.getenv('AZURE_OPENAI_TEMPERATURE', '1')),
}

# ============================
# LLM Provider Selection
# ============================

# LLM_PROVIDER: Which LLM provider to use
# - Options: 'openai' or 'azure_openai' (default: 'azure_openai')
# - When 'azure_openai' is selected, AZURE_OPENAI_CONFIG is used
# - When 'openai' is selected, OPENAI_CONFIG is used
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'azure_openai').lower()

# ============================
# LLM Output Configuration
# ============================

# LLM_OUTPUT_LANGUAGE: Preferred language for LLM responses
# - Use Case: Control the language of generated summaries and content
# - Default: 'English'
# - Supported: Any language supported by the model
# - Examples: 'English', 'Chinese', 'Spanish', 'French'
# - Note: This is a preference; actual output depends on prompt
LLM_OUTPUT_LANGUAGE = os.getenv('LLM_OUTPUT_LANGUAGE', 'English')
