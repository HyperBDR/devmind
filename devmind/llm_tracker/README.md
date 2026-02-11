# llm_tracker

统一 LLM 调用与用量记录，供统计与成本分析。

---

## 模块说明

| 模块 | 用途 |
|------|------|
| **llm_tracker.py** | 发起 LLM 调用并自动落库（`LLMTracker.call_and_track`） |
| **llm_service.py** | 获取 LLM 客户端（`get_llm_service`），不写库 |
| **llm_usage_stats.py** | 用量**统计**：汇总、按模型、时序，供图表与成本分析 |
| **llm_usage.py** | 用量**明细**：分页列表与筛选，供管理端表格 |
| **views.py / urls.py** | Admin 只读 REST 接口（token-stats、llm-usage） |

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

推荐直接按 query 取完整统计（含图表时序）：

```python
from llm_tracker.llm_usage_stats import get_token_stats_from_query

data = get_token_stats_from_query(request.query_params)
# data: summary, by_model, series（仅当传入 granularity 时有值，否则为 None）
# 不支持的 granularity 会 raise ValueError
```

或按需调用底层函数：

```python
from llm_tracker.llm_usage_stats import (
    get_summary_stats,
    get_stats_by_model,
    get_time_series_stats,
)
```

### get_summary_stats(start_date=None, end_date=None, user_id=None)

- **返回**: `total_prompt_tokens`, `total_completion_tokens`, `total_tokens`,
  `total_cached_tokens`, `total_reasoning_tokens`, `total_calls`,
  `successful_calls`, `failed_calls`

### get_stats_by_model(start_date=None, end_date=None, user_id=None)

- **返回**: list[dict]，每项含 `model`, `total_calls`, `total_prompt_tokens`,
  `total_completion_tokens`, `total_tokens`, `total_cached_tokens`,
  `total_reasoning_tokens`，按 `total_tokens` 降序

### get_time_series_stats(granularity, start_date=None, end_date=None, user_id=None)

- **granularity**: `"day"`（按小时）| `"month"`（按日）| `"year"`（按月）
- **返回**: list[dict]，每项含 `bucket`, `total_calls`, `total_prompt_tokens`,
  `total_completion_tokens`, `total_tokens`, `total_cached_tokens`,
  `total_reasoning_tokens`
- 不支持的 granularity 会 **raise ValueError**

日期可为 `datetime` 或可被 `parse_datetime`/isoformat 解析的字符串。

---

## 用量明细（分页列表，供管理端表格）

需要逐条、分页的用量记录时，用 `llm_usage`：

```python
from llm_tracker.llm_usage import get_llm_usage_list, get_llm_usage_list_from_query

# 从 query 解析并返回分页结果
data = get_llm_usage_list_from_query(request.query_params)
# data: results (list), total, page, page_size
```

或直接调用（`start_date`、`end_date` 可选，为 datetime 或可解析字符串）：

```python
data = get_llm_usage_list(
    page=1,
    page_size=20,
    user_id=user_id,
    model_filter="gpt",
    success_filter="true",
    start_date=start_date,   # 可选
    end_date=end_date,       # 可选
)
```

- **筛选**: `user_id`、`model`（icontains）、`success`（true/false）、`start_date`、`end_date`
- **返回**: `results`（每条含 id、user_id、username、model、prompt_tokens/completion_tokens/total_tokens、success、error、created_at、metadata）、`total`、`page`、`page_size`
- `llm_usage` 内部复用 `llm_usage_stats` 的 `_parse_date`、`_parse_end_date` 做日期解析

---

## Admin API（仅管理员）

llm_tracker 提供只读的 REST 接口，需 **IsAdminUser**（staff 或 superuser）。

### 挂载方式

在项目根 URL 下 include 即可，例如：

```python
# core/urls.py 或项目主 urls.py
from django.urls import path, include

urlpatterns = [
    path('api/v1/admin/', include('llm_tracker.urls')),
]
```

则接口为：

- `GET /api/v1/admin/token-stats/` — 用量统计（summary、by_model、series）
  - query: `start_date`, `end_date`, `user_id`, `granularity`（day|month|year）
- `GET /api/v1/admin/llm-usage/` — 分页用量列表
  - query: `page`, `page_size`, `user_id`, `model`, `success`, `start_date`, `end_date`

依赖：`rest_framework`，且认证用户需 `is_staff=True` 或为 superuser。

---

## 数据表

- **LLMUsage**（表名 `llm_tracker_usage`）  
  字段：id(UUID), user_id, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens, success, error, metadata(JSON), created_at。  
  `metadata` 中会写入：`node_name`、`source_type`、`source_task_id`、`source_path` 及 state 里传入的 `metadata` 内容。  
  在 Django Admin（`admin.py` 已注册）中可只读查看。
