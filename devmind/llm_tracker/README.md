# llm_tracker

统一 LLM 调用与用量记录，供统计与成本分析。

---

## 配置（settings）

- `LLM_PROVIDER`: `"openai"` | `"azure_openai"` | `"gemini"`
- **OpenAI**: `OPENAI_CONFIG` 需含 `api_key`，可选 `model`、`max_tokens`、`temperature`
- **Azure OpenAI**: `AZURE_OPENAI_CONFIG` 需含 `api_key`、`api_base`
- **Gemini**: `GEMINI_CONFIG` 需含 `api_key`

缺省时从各 config 读 `max_tokens`/`temperature`。

---

## 发起调用并记录用量

```python
from llm_tracker.llm_tracker import LLMTracker

content, usage = LLMTracker.call_and_track(
    messages=[{"role": "user", "content": "你好"}],
    node_name="interpret",
    state={"user_id": user.id, "source_type": "task", "source_task_id": "celery-uuid"},
)
```

### 参数（LLM 相关在前，元数据在后）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| messages | list | 是 | 消息列表，每项含 `role`、`content` |
| json_mode | bool | 否 | 是否按 JSON 返回，默认 False |
| max_tokens | int | 否 | 不传则用配置默认值 |
| temperature | float | 否 | 同上 |
| response_format | dict | 否 | 传给底层 chat 的 response_format |
| node_name | str | 否 | 调用节点名，默认 `"unknown"`，写入 `LLMUsage.metadata["node_name"]` |
| state | dict | 否 | 可选：`user_id`、`source_type`、`source_task_id`、`source_path`、`metadata`（合并进记录） |

### 返回

- `content`: str，模型回复正文
- `usage`: dict，如 `{"model", "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"}`

### 异常

- `ValueError("Messages cannot be empty")`：messages 为空
- `ValueError("LLM returned empty response")`：模型返回空内容
- 其他：底层 LLM 异常会原样抛出；失败时仍会写入一条 `LLMUsage`（success=False，error 有信息）

---

## 仅获取 LLM 客户端（不记录）

```python
from llm_tracker.llm_service import get_llm_service

svc = get_llm_service()
# svc.chat(messages=..., max_tokens=..., temperature=..., raw_response=True, ...)
```

配置不完整时抛出 `ValueError`。

---

## 用量统计（供管理端）

```python
from llm_tracker.llm_usage_stats import (
    get_summary_stats,
    get_stats_by_model,
    get_stats_by_day,
)
```

### get_summary_stats(start_date=None, end_date=None)

- **返回**:
  `total_prompt_tokens`, `total_completion_tokens`, `total_tokens`,
  `total_calls`, `successful_calls`, `failed_calls`

### get_stats_by_model(start_date=None, end_date=None)

- **返回**: list[dict]，每项含 `model`, `total_calls`, `total_prompt_tokens`, `total_completion_tokens`, `total_tokens`，按 `total_tokens` 降序

### get_stats_by_day(start_date=None, end_date=None)

- **返回**: list[dict]，每项含 `date`（日期字符串）, `total_calls`, `total_tokens`，按日期升序

日期可为 `datetime` 或可被 `parse_datetime`/isoformat 解析的字符串。

---

## 数据表

- **LLMUsage**（表名 `llm_tracker_usage`）
  字段：id(UUID), user_id, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens, success, error, metadata(JSON), created_at。
  `metadata` 中会写入：`node_name`、`source_type`、`source_task_id`、`source_path` 及 state 里传入的 `metadata` 内容。
