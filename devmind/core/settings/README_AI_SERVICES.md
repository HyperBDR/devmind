# AI Services Configuration Guide

## Overview

This guide explains how to configure LLM (Large Language Model) services for ArticleHub article processing workflow.

## Supported Providers

ArticleHub supports two LLM providers:

1. **OpenAI** (default) - Standard OpenAI API
2. **Azure OpenAI** - Azure-hosted OpenAI service

## Configuration

### Step 1: Choose Provider

Set the `LLM_PROVIDER` environment variable in your `.env` file:

```bash
# For OpenAI (default)
LLM_PROVIDER=openai

# For Azure OpenAI
LLM_PROVIDER=azure_openai
```

### Step 2: Configure Provider

#### OpenAI Configuration

Add these variables to your `.env` file:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional (with defaults)
OPENAI_API_BASE=https://api.openai.com/v1/  # Default
OPENAI_MODEL=gpt-5-nano                      # Default
OPENAI_MAX_TOKENS=4000                       # Default
OPENAI_TEMPERATURE=0.7                       # Default
```

**How to get API key:**
1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key

**Model Options:**
- `gpt-5-nano` - Cost-effective, fast (recommended, default)
- `gpt-4o-mini` - Cost-effective alternative
- `gpt-4o` - More capable, higher cost
- `gpt-4-turbo` - Balanced performance
- `gpt-3.5-turbo` - Legacy, cheaper

#### Azure OpenAI Configuration

Add these variables to your `.env` file:

```bash
# Required
AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-5-nano  # Default

# Optional (with defaults)
AZURE_OPENAI_API_VERSION=2024-10-01-preview  # Default
AZURE_OPENAI_MAX_TOKENS=12000                 # Default
AZURE_OPENAI_TEMPERATURE=0.7                   # Default
```

**How to get Azure OpenAI credentials:**
1. Go to Azure Portal
2. Create or select an Azure OpenAI resource
3. Navigate to "Keys and Endpoint"
4. Copy the endpoint URL and API key
5. Go to Azure OpenAI Studio
6. Create a deployment and note the deployment name

### Step 3: Configure Output Language (Optional)

Set the preferred language for LLM responses:

```bash
LLM_OUTPUT_LANGUAGE=English  # or Chinese, Spanish, etc.
```

## Configuration Parameters

### max_tokens

- **Purpose**: Controls the maximum length of LLM responses
- **Range**: 1-4096 (varies by model)
- **Default**: 4000
- **Impact**: Higher values = longer responses, higher cost, more latency

### temperature

- **Purpose**: Controls response randomness/creativity
- **Range**: 0.0-2.0 (OpenAI) or 0.0-1.0 (Azure)
- **Default**: 0.7
- **Values**:
  - `0.0`: Deterministic, consistent responses (good for structured tasks)
  - `0.7`: Balanced (good for general use)
  - `1.0+`: Creative, varied responses (good for creative writing)

## Usage in Code

The configuration is automatically loaded from settings. In your code:

```python
from articlehub.utils import get_llm_service

# Get configured LLM service
llm_service = get_llm_service()

# Use the service
response = llm_service.call(
    messages=[{"role": "user", "content": "Your prompt here"}]
)
```

## Verification

To verify your configuration is working:

1. Check that all required environment variables are set
2. Restart your Django application
3. Check logs for "Using OpenAI LLM service" or "Using Azure OpenAI LLM service"
4. Test with a simple workflow execution

## Troubleshooting

### Error: "OpenAI configuration is incomplete"

**Solution**: Make sure `OPENAI_API_KEY` is set in your `.env` file.

### Error: "Azure OpenAI configuration is incomplete"

**Solution**: Make sure both `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_API_BASE` are set.

### Error: "Azure OpenAI provider not available"

**Solution**: The devtoolbox package may not include Azure support. Use `LLM_PROVIDER=openai` instead.

### Model not responding

**Possible causes**:
- Invalid API key
- Insufficient credits/quota
- Network connectivity issues
- Invalid model name

**Solution**: Check your API key, account status, and network connection.

## Cost Optimization Tips

1. **Use `gpt-5-nano`** for most tasks (cost-effective, default)
2. **Lower `max_tokens`** when possible (reduces cost)
3. **Use `temperature=0.3-0.5`** for structured tasks (more consistent)
4. **Monitor usage** through your provider's dashboard

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for all sensitive configuration
3. **Rotate API keys** regularly
4. **Use separate keys** for development and production
5. **Set usage limits** in your provider dashboard
