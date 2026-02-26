# Ray Code Standards Review Report

**Rule:** ray-code-standards  
**Base commit:** 9241fd  
**Scope:** devmind hand-written Python (excl. migrations, generated, vendored).

## Summary

- **Line length (79):** Fail — many files 80–109 chars (app_config, core, cloud_billing, agentcore, tests).
- **Imports:** Fail — `core/celery.py` has `import time` inside `periodic_reap()`; move to top.
- **Logging f-strings:** Fail — `core/periodic_registry.py`, `register_periodic_tasks.py`, `accounts/serializers.py` use %s or .format(); convert to f-strings.
- **Function length (100):** Fail — `cloud_billing/tasks.py`: `collect_billing_data` and `check_alert_for_provider` far over 100 lines; split.
- **Start/Finish logs:** Partial — add "Starting/Finished task_name" for main billing tasks.

## 1. Line length

Break long lines in: app_config/models.py, core/settings/*.py, core/urls.py, cloud_billing (models, services, tests), agentcore-notifier (views, tests). Prefer expression break with parentheses; in tests use variables for long @patch paths.

## 2. Logging

Replace with f-strings:
- periodic_registry.py:157 — debug with name
- periodic_registry.py:159–160 — exception with name, e
- register_periodic_tasks.py:36–37 — exception with app, e
- accounts/serializers.py:581 — error message with user/args

## 3. Imports

core/celery.py line 91: move `import time` to top (stdlib group).

## 4. Function length

cloud_billing/tasks.py: split collect_billing_data (e.g. per-provider helper) and check_alert_for_provider (e.g. rule evaluation vs alert creation).

## 5. Long-running tasks

Add TASK_* constant and "Starting/Finished task_name" logs for collect_billing_data and check_alert_for_provider.

## Checklist

- [ ] Line length <= 79
- [x] Imports at top only (fixed: core/celery.py — moved import time to top)
- [x] Logging with variables: f-strings only (fixed: periodic_registry.py, register_periodic_tasks.py)
- [ ] Functions <= 100 lines where applicable
- [ ] Start/Finish logs for long tasks

## Fixes applied in this run

- core/periodic_registry.py: logger.debug and logger.exception now use f-strings.
- core/management/commands/register_periodic_tasks.py: logger.exception now uses f-string.
- core/celery.py: import time moved to top of file (stdlib group).

---

## Staged-code review (git diff --cached)

**Scope:** Python files in staged changes (excl. README, submodule refs, review docs).

### Files reviewed

| File | Notes |
|------|--------|
| `cloud_billing/models.py` | **Fixed** — BillingData.__str__ line was 81 chars; split to two f-strings. |
| `cloud_billing/tasks.py` | **Fixed** — Single agentcore_task import with alphabetical names (prevent_duplicate_task, TaskLogCollector, TaskStatus, TaskTracker). Logging and docstrings OK. |
| `cloud_billing/tests/conftest.py` | **Fixed** — Added NOTE(Ray) above django import (Django test bootstrap requires env before import). |
| `cloud_billing/tests/settings.py` | OK (config only). |
| `cloud_billing/tests/test_models.py`, `test_tasks.py`, `test_views.py`, `urls.py` | OK. |
| `core/celery.py` | OK (imports at top, f-strings N/A here). |
| `core/periodic_registry.py` | **Fixed** — Docstring line 2 was 81 chars; wrapped to two lines. |
| `core/management/commands/register_periodic_tasks.py` | OK (f-strings already applied). |

### Fixes applied in staged-code pass

- cloud_billing/models.py: line length ≤79 for `__str__` return.
- core/periodic_registry.py: docstring line length ≤79.
- cloud_billing/tasks.py: one agentcore_task import block, alphabetical.
- cloud_billing/tests/conftest.py: NOTE(Ray) for mid-file django import (intentional).

### Checklist (staged Python)

- [x] No line over 79 characters (in reviewed files)
- [x] Imports at top; one block per third-party; alphabetical; NOTE where needed
- [x] Comments in English; NOTE(Ray) for conftest exception
- [x] Logging with variables: f-strings only
- [ ] Functions ≤100 lines (collect_billing_data, check_alert_for_provider still long; deferred)
- [ ] Start/Finish logs for long tasks (deferred)
