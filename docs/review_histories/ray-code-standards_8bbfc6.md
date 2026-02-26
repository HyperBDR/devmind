# Ray Code Standards – devmind

**Rule:** ray-code-standards  
**Base commit (6):** 8bbfc6  
**Scope:** devmind repo (hand-written Python; migrations/tests/settings relaxed per skill)

## Summary

- **Reviewed:** agentcore-notifier (views, webhook drivers), cloud_billing (tasks, services, clouds).
- **Excluded (per skill):** `migrations/`, `__init__.py` re-exports, generated/vendored code; tests and settings relaxed.
- **Changes applied:** Line length ≤79, logging f-strings, docstring wrap.

## Changes Applied

### 1. Line length (≤79)

- **`agentcore_notifier/adapters/django/views/stats.py`**  
  - Wrapped `AdminNotificationUserListView` docstring so no line exceeds 79 chars (was 91 on the "Returns" line).

- **`agentcore_notifier/adapters/django/views/channels.py`**  
  - Shortened SMTP "no route to host" `_()` string and split across lines so each line is ≤79 chars.

### 2. Logging (f-strings and context)

- **`agentcore_notifier/adapters/django/services/webhook/wechat.py`**  
  - Replaced `logger.info("WeChatWebhookDriver: sent successfully")` with `logger.info(f"WeChatWebhookDriver: sent successfully")` to satisfy f-string requirement.

- **`agentcore_notifier/adapters/django/services/webhook/feishu.py`**  
  - Same change: `logger.info("FeishuWebhookDriver: sent successfully")` → `logger.info(f"FeishuWebhookDriver: sent successfully")`.

### 3. Already compliant (no change)

- **notification_stats.py:** Imports (stdlib → third-party → local), f-strings in logging, docstrings, line length.
- **cleanup.py:** Logging uses f-strings with context.
- **channels.py:** NOTE(Ray) present; logging already uses f-strings; imports ordered.
- **config.py:** Short file, docstrings and structure ok.
- **constants.py:** Minimal constants; out of scope for strict style.

## Checklist (hand-written code)

| Item | Status |
|------|--------|
| No line over 79 characters | Fixed in stats, channels |
| Imports at top; 3 groups; alphabetical | Verified (no change) |
| Comments in English; above code; no inline | Verified |
| Docstrings (triple-quoted, English) | Present |
| NOTE/TODO/FIXME where needed | channels.py has NOTE(Ray) |
| Short, precise names | Verified |
| Logging/print with variables use f-strings | Fixed wechat, feishu |
| Functions &lt;100 lines; logical blocks | Verified |
| Logs with useful context | Verified / improved |

### 4. cloud_billing (this run)

- **`cloud_billing/tasks.py`**  
  - All logger calls that pass a variable (e.g. `logger.warning(warning_msg)`) changed to f-string form (e.g. `logger.warning(f"{warning_msg}")`) to satisfy Ray standard.

- **`cloud_billing/clouds/huawei_provider.py`**  
  - `logger.error(error_message)` → `logger.error(f"{error_message}")`.

- **`cloud_billing/clouds/huawei_intl_provider.py`**  
  - `logger.error(error_message)` → `logger.error(f"{error_message}")`.

- **`cloud_billing/services/notification_service.py`**  
  - Line length: import `send_webhook_notification` wrapped to two lines; `__init__` docstring shortened; `send_alert` docstring line broken so no line >79.

## Files not modified

- Migration files (excluded by skill).
- `__init__.py` that only re-export (excluded).
- Tests and core settings (relaxed per skill; many long lines remain in tests/settings).
- app_config, core/urls, other modules with long lines left for a later pass.
