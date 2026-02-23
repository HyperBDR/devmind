# Ray Code Standards – Review: agentcore-task adapter

**Base commit:** 3b0024  
**Scope:** Hand-written Python in `devmind/agentcore/agentcore-task/agentcore_task/adapters/django/` (excluding migrations, `__init__.py` re-exports, and tests).  
**Date:** 2025-02-21

## Summary

- **Line length:** Several lines > 79 chars in `__init__.py`, `conf.py`, `tasks/cleanup.py` — fixed by wrapping.
- **Imports:** `task_tracker.py` local group not alphabetical (constants before adapters) — fixed.
- **Logging:** `cleanup.py` and `services/timeout.py` used f-string + literal for one message — fixed to single f-string.
- **Type hint:** `lock.py` used `lock_param: str = None` — fixed to `Optional[str] = None`.
- **Docstrings / NOTE(Ray):** Present and in English; block comments above code.
- **No inline comments;** no non–f-string logging with variables.

## Checklist (after fixes)

| Item | Status |
|------|--------|
| No line over 79 characters | Done |
| Imports at top; three groups; alphabetical within group | Done |
| Comments in English; above code; no inline | Done |
| Docstrings (English) on public classes/functions | Done |
| NOTE(Ray) where needed (conf, apps) | Done |
| Short, precise names | Done |
| F-strings for print/logging with variables | Done |
| Logical blocks with single blank line | Done |
| Logs with context (task_id, lock_name, etc.) | Done |
| Long-running tasks: Starting/Finished paired logs | Done (tasks/cleanup, tasks/timeout, task_tracker) |

## Files changed in this pass

- `agentcore_task/adapters/django/__init__.py` – wrap long `_SYMBOLS` lines.
- `agentcore_task/adapters/django/conf.py` – wrap long docstrings.
- `agentcore_task/adapters/django/cleanup.py` – single f-string for warning.
- `agentcore_task/adapters/django/services/timeout.py` – single f-string for warning.
- `agentcore_task/adapters/django/services/task_tracker.py` – import order.
- `agentcore_task/adapters/django/services/lock.py` – `Optional[str]` for `lock_param`.
- `agentcore_task/adapters/django/tasks/cleanup.py` – break long decorator line.

## Excluded from strict review (per skill)

- `migrations/*` – auto-generated.
- Minimal re-export `__init__.py` (e.g. `services/cleanup.py`, `views/__init__.py`, `utils/__init__.py`).
- Test files (conftest, settings, test_*.py) – relaxed.
