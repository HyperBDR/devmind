# ArticleHub Prompts Configuration

## Overview

This directory contains the prompt configuration system for ArticleHub article processing workflow. All LLM prompts are centrally managed in YAML files for better maintainability and extensibility.

## File Structure

```
conf/articlehub/
├── prompts/
│   └── default.yaml    # Default prompts for article processing
└── README.md           # This file
```

## Configuration Files

### prompts/default.yaml

Contains all prompt templates used in the article processing workflow.

**Available Prompts:**

- `rewrite_prompt`: Content optimization and rewriting prompt
- `translate_prompt`: Translation prompt for markdown content
- `translate_optimize_prompt`: Translation optimization prompt
- `summary_prompt`: Article summary generation prompt
- `title_prompt`: Title translation/localization prompt

**Prompt Variables:**

Prompts use `{variable_name}` for dynamic content replacement:

- `{region}`: Target region (e.g., "US", "CN")
- `{publish_date}`: Article publication date
- `{original_content}`: Original article content
- `{target_language}`: Target language for translation
- `{rewrite_content}`: Rewritten/optimized content
- `{translated_content}`: Translated content
- `{content}`: Content to summarize
- `{original_title}`: Original article title

## Usage

### In Code

```python
from articlehub.utils import get_prompt_manager

# Get prompt manager instance
prompt_manager = get_prompt_manager()

# Get and render a prompt
rewrite_prompt = prompt_manager.get_prompt(
    'rewrite_prompt',
    region='US',
    publish_date='2025-01-01',
    original_content=article_content
)
```

### Customizing Prompts

1. Edit `conf/articlehub/prompts/default.yaml`
2. Modify the prompt templates as needed
3. Restart the application to load changes

### Configuration Path

By default, the system looks for prompts in:
- `devmind/conf/articlehub/prompts/default.yaml`

You can customize the path by setting `ARTICLEHUB_CONFIG_PATH` in Django settings:

```python
# settings.py
ARTICLEHUB_CONFIG_PATH = '/path/to/your/config'
```

## Prompt Structure

All prompts are defined under the `common` section in the YAML file:

```yaml
common:
  rewrite_prompt: |
    Your prompt template here...
    Use {variable} for dynamic content.
```

## Best Practices

1. **Keep prompts focused**: Each prompt should have a single, clear purpose
2. **Use variables**: Make prompts reusable with variable substitution
3. **Document variables**: Add comments explaining what each variable does
4. **Test changes**: Test prompt changes before deploying to production
5. **Version control**: Keep prompt changes in version control for tracking

## Examples

### Rewrite Prompt

```yaml
common:
  rewrite_prompt: |
    Rewrite the following content for {region}:
    {original_content}
```

### Summary Prompt

```yaml
common:
  summary_prompt: |
    Summarize this content in {target_language}:
    {content}
```
