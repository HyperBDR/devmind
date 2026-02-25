# Ray Code Standards — agentcore-notifier 审查记录

**审查范围**: agentcore-notifier 本次会话全部改动  
**规则**: ray-code-standards  
**日期**: 2025-02-25

---

## 涉及文件

| 文件 | 改动概要 |
|------|----------|
| `agentcore_notifier/adapters/django/services/notification_stats.py` | 新增 `get_notification_user_list()`，供统计/记录用户范围下拉使用 |
| `agentcore_notifier/adapters/django/views/stats.py` | 新增 `AdminNotificationUserListView`，GET 返回有通知记录的用户列表 |
| `agentcore_notifier/adapters/django/views/__init__.py` | 导出 `AdminNotificationUserListView` |
| `agentcore_notifier/adapters/django/urls.py` | 注册 `GET users/` 路由 |
| `agentcore_notifier/adapters/django/views/channels.py` | 渠道校验（Webhook/Email）创建记录时写入操作人 `user_id` |

---

## 审查结果与修改

### 1. notification_stats.py

- **Mid-file import（已修复）**  
  - 规范：所有 import 在文件顶部，三组（标准库 / 第三方 / 本地），组内按字母序。  
  - 原状：`get_notification_user_list()` 内存在 `from django.contrib.auth import get_user_model`。  
  - 处理：将 `get_user_model` 移至文件顶部第三方 import 区，与现有 `django.*` 一起按字母序排列；删除函数内 import。

- **其余**  
  - 行宽、注释与 docstring（英文）、命名、f-string 使用均符合规范；无需 NOTE/TODO/FIXME。

### 2. views/channels.py

- **行宽超过 79 字符（已修复）**  
  - 规范：每行最多 79 字符。  
  - 原状：  
    `user_id = getattr(request.user, "pk", None) if getattr(request.user, "is_authenticated", True) else None`  
    超过 79 字符。  
  - 处理：改为多行条件赋值，每行不超过 79 字符：

    ```python
    if getattr(request.user, "is_authenticated", True):
        user_id = getattr(request.user, "pk", None)
    else:
        user_id = None
    ```

- **其余**  
  - 注释、docstring（含 `user_id: optional operator` 说明）、日志使用 f-string、命名均符合规范。  
  - 已有 `# NOTE(Ray): get_user_model at top for channel user; no circular deps.` 保留。

### 3. views/stats.py

- **符合项**  
  - 仅顶部 import；行宽、docstring（英文）、命名均符合。  
  - `AdminNotificationUserListView` docstring 说明返回 `[{"user_id": int, "display": str}]` 清晰。

- **无需修改。**

### 4. urls.py、views/__init__.py

- **符合项**  
  - 仅新增路由与导出，结构简单，符合规范。

- **无需修改。**

---

## Checklist 结论

| 项 | 结果 |
|----|------|
| 行宽 ≤79 | 已满足（channels 长行已拆） |
| Import 仅顶部、三组、组内字母序 | 已满足（notification_stats 已移出 mid-file import） |
| 注释英文、注释在上、无行内注释 | 已满足 |
| 公开类/函数有英文 docstring | 已满足 |
| 命名简短准确 | 已满足 |
| 含变量的 print/日志使用 f-string | 已满足 |
| 函数长度与可读性 | 已满足 |
| 逻辑分块与空行 | 已满足 |
| 日志带上下文 | 已满足 |

---

## 总结

- **已修复**：`notification_stats.py` 的 mid-file import；`channels.py` 的超长行。  
- **其余改动**：符合 Ray Code Standards，无需进一步修改。
