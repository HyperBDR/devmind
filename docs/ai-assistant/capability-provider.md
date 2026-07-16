# App Assistant Capability Provider

每个业务 app 通过继承
`ai_assistant.provider.AssistantCapabilityProvider` 声明自己的 AI 能力。
基类负责组装稳定的 `AssistantCapability`，业务 app 只提供自身元数据、
instructions、tools，以及按需覆盖 profile、skills、memory 和 stream
handler。

```python
from ai_assistant.provider import AssistantCapabilityProvider


class ExampleAssistantProvider(AssistantCapabilityProvider):
    app_key = "example"
    display_name = "Example 助手"
    required_feature = "example"
    description = "查询 Example 业务数据。"

    def get_instructions(self):
        return "只能使用 Example app 注册的工具。"

    def get_tools(self):
        return (...,)


assistant_provider = ExampleAssistantProvider()
```

app 的 `assistant/__init__.py` 必须导出 `assistant_provider`。全局发现器会
优先加载该对象；旧的 `get_assistant_capability()` 函数仍可保留作为兼容
入口。

可覆盖的方法：

- `get_skill_dirs()`：app 自管的本地 skill 目录。
- `get_memory_policy()`：会话摘要和偏好记忆策略。
- `get_profile_loader()`：控制台问题目录和能力说明。
- `get_stream_handler()`：迁移期保留的 app 专用流式实现；新 app 默认使用
  全局 tool-calling runtime。

约束：

- `app_key`、`display_name`、`required_feature` 和 instructions 必填。
- tools 必须只访问当前 app 授权的数据边界。
- 查询工具默认只读；业务修改应优先返回受控操作入口。
- tool schema 是前后端与模型共同依赖的公开契约，新增字段优先采用兼容的
  additive change。
