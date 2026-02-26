# Ray Code Standards – devmind 审查记录

**规则**: ray-code-standards  
**范围**: devmind 下手写 Python 代码（不含 migrations、minimal `__init__.py`），含 agentcore-notifier 与 cloud_billing 等本次改动涉及模块  
**基准**: 000000

---

## 审查范围

**agentcore-notifier**

- `agentcore_notifier/adapters/django/views/channels.py`
- `agentcore_notifier/adapters/django/services/email_service.py`
- `agentcore_notifier/adapters/django/services/webhook_service.py`
- `agentcore_notifier/adapters/django/tasks/send.py`
- `agentcore_notifier/constants.py`
- 其他 hand-written 模块（merge_and_silence、conf、models 等）未逐行审查，仅对本次改动涉及文件做修复与记录。

**devmind / cloud_billing**

- `cloud_billing/services/notification_service.py`
- `cloud_billing/serializers.py`、`cloud_billing/models.py`、`cloud_billing/tasks.py` 仅做抽查（长行等）；未改动的逻辑未动。

---

## 已修复项

### 1. send.py

- **Mid-file import**  
  - 原：`_user_from_id` 内 `from django.contrib.auth import get_user_model`。  
  - 改：在文件顶部 third-party 组增加 `from django.contrib.auth import get_user_model`，删除函数内 import；为 `_user_from_id` 补简短英文 docstring。
- **行宽 > 79**  
  - `merge_enabled = (raw_channel_config.get("merge_enabled") if ...)` 拆成多行。  
  - Webhook/Email 的 `"Webhook config not found or invalid"` / `"Email channel not found or invalid"` 提成变量 `err_msg` 再使用，避免单行过长。  
  - `_validate_send_notification_params` 中 `notification_type must be one of ...` 的 f-string 拆成多行并赋给 `err` 再写入返回 dict。

### 2. email_service.py

- **行宽 > 79**  
  - `get_email_channel_by_uuid` 内 `UUID(str(channel_uuid)) if isinstance(...) else channel_uuid` 拆成多行。

### 3. webhook_service.py

- **行宽 > 79**  
  - `build_webhook_config_from_dict` 签名拆成多行。  
  - `"provider": cfg.get("provider_type") or ...` 拆成多行。  
  - `get_webhook_channel_by_uuid` 内 `uuid_val = UUID(...) if ... else ...` 拆成多行。

### 4. channels.py

- 未发现行宽违规；import 分组与 NOTE(Ray) 位置符合规范，未改动。

### 5. cloud_billing/services/notification_service.py

- **Imports**  
  - 将 `from ..constants`、`from ..models` 改为绝对导入 `from cloud_billing.constants`、`from cloud_billing.models`。  
  - 第三组内按字母序排列：agentcore_notifier 的 email_service、webhook_service、tasks.send、constants，再 cloud_billing。
- **行宽**  
  - `notification = (alert_record.provider.config or {}).get("notification") or {}` 拆成 `provider_config = ...` 与 `notification = provider_config.get("notification") or {}`。  
  - 两处 `to_addresses = [a.strip() for a in ... if ...]` 拆成多行 list comprehension，保证每行 ≤ 79 字符。

---

## 未改动的例外

- **merge_and_silence.py**  
  - 存在 mid-file 的 `from agentcore_notifier.adapters.django.services import notification_config`，并有 `# NOTE(Ray): Lazy import to avoid circular import.`  
  - 保留：为避免循环依赖的 lazy import，符合 skill 中 “relative/lazy import when necessary (e.g. circular imports)” 的例外。
- **Migrations**  
  - 按 skill 的 Review Scope 不纳入严格风格审查。
- **测试文件**  
  - 仅对与 send/channels 相关的改动做必要修正；长行等在测试中适当放宽。
- **cloud_billing/serializers.py, models.py, tasks.py**  
  - 抽查未发现需强制修改的违规（长行在 help_text/docstring 内已合理换行）。

---

## Checklist 结论

| 项 | 状态 |
|----|------|
| 行宽 ≤ 79 | 已修复上述文件中的超长行 |
| 仅顶部 import；三组；字母序 | 已满足；send.py 已去掉 mid-file import；notification_service 已改为绝对导入并字母序 |
| 注释英文、注释在上方、无行内注释 | 已满足 |
| 公开类/函数有 docstring（英文） | 已满足；_user_from_id 已补 |
| NOTE/TODO/FIXME(Ray) | channels 已有；send 中 lazy import 已移除故 NOTE 已删 |
| 命名简短准确 | 已满足 |
| 打印/日志含变量用 f-string | 已满足 |
| 函数简洁、逻辑分块、适当空行与注释 | 已满足 |
| 日志有层级与上下文 | 已满足 |

---

*审查完成；后续同规则、同基准重新运行时可更新本文件。*
