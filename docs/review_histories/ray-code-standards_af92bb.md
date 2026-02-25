# Ray Code Standards – Review: agentcore-notifier

**Base commit:** af92bb  
**Scope:** All hand-written Python in `devmind/agentcore/agentcore-notifier/` (excluding migrations and minimal `__init__.py` re-exports). Includes tests.  
**Date:** 2026-02-25 (full re-review)

## Summary

- **Line length:** All files brought to ≤ 79 characters. Long lines broken by expression; docstrings shortened where needed.
- **Logging:** logger.exception in channels.py uses f-string with exception context; SMTP validation failure log includes `{e}`.
- **Imports:** All at top; three groups; alphabetical within group. get_user_model at top in channels.py with NOTE(Ray). Lazy imports in conf.py, merge_and_silence.py, send.py, registry.py already have NOTE(Ray).
- **Import order:** stats.py: adapters before constants. channels.py: get_default_registry import wrapped.
- **Comments / docstrings:** All in English; comments above code; no inline comments.
- **NOTE(Ray):** Used for get_user_model (channels), lazy imports (conf, merge_and_silence, send, registry), and cleanup/task (cleanup.py).

## Checklist (after fixes)

| Item | Status |
|------|--------|
| No line over 79 characters | Done |
| Imports at top; three groups; alphabetical; NOTE where needed | Done |
| Comments in English; above code; no inline | Done |
| Docstrings (English) on public classes/functions | Done |
| NOTE(Ray) where needed | Done |
| Short, precise names | Done |
| F-strings for print/logging with variables | Done |
| Logical blocks with single blank line | Done |
| Logs with context | Done |
| Long-running tasks: Starting/Finished paired logs | N/A (no long-running task in notifier) |

## Files changed (this pass)

**Adapter / app code**

- `agentcore_notifier/__init__.py` – Shorten module docstring.
- `agentcore_notifier/adapters/django/admin.py` – Break list_display.
- `agentcore_notifier/adapters/django/models.py` – Break docstrings, help_text, __str__; scope CharField kwargs.
- `agentcore_notifier/adapters/django/views/channels.py` – Module and function docstrings; get_user_model at top with NOTE(Ray); break Response, filter, ordering, sent_at, _get_channel; logger.exception f-string and SMTP log with context.
- `agentcore_notifier/adapters/django/views/stats.py` – Import order: adapters before constants.
- `agentcore_notifier/adapters/django/services/merge_and_silence.py` – Module and function docstrings; break _filter_active_silence_rules signature and list-comp; _get_silence_rules import and docstring; should_silence, should_skip_due_to_merge docstrings; merge_key docstring.
- `agentcore_notifier/adapters/django/services/notification_stats.py` – Break function signature, result dict, day_start, year, month bucket line.
- `agentcore_notifier/adapters/django/services/webhook_service.py` – Module and method docstrings; message_prefix; logger.warning message.
- `agentcore_notifier/adapters/django/services/webhook/base.py` – Class and method docstrings; send() signature.
- `agentcore_notifier/adapters/django/services/webhook/feishu.py` – Module docstring; _apply_message_prefix signature; send() signature and docstring.
- `agentcore_notifier/adapters/django/services/webhook/wechat.py` – send() signature.
- `agentcore_notifier/adapters/django/services/webhook/registry.py` – NOTE(Ray) line.
- `agentcore_notifier/adapters/django/tasks/send.py` – Module docstring.
- `agentcore_notifier/adapters/django/tasks/cleanup.py` – NOTE(Ray) line length.

**Tests**

- `tests/test_channels.py` – Break test_list_channels_filter_by_type, patch path, assert with response.json().
- `tests/test_email_service.py` – Break test_returns_none_when_channel_has_no_smtp_host, test_send_returns_error_when_no_valid_recipients, test_send_success_and_record; break assert for "not found"/"not active"; break patch path.
- `tests/test_cleanup.py` – Break cleanup import; break assert .filter().exists().
- `tests/test_feishu_driver.py` – Break patch paths (requests.post, time.time).
- `tests/test_webhook_service.py` – Break patch path.
- `tests/test_merge_and_silence.py` – Shorten test_merge_per_user_dimension docstring.
- `tests/test_tasks_send.py` – Break patch path (feishu.requests.post, email_service.smtplib.SMTP).

## Excluded from strict review (per skill)

- `agentcore_notifier/adapters/django/migrations/*` – auto-generated.
- Minimal re-export `__init__.py` files (left as-is unless line length violated).
