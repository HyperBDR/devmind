# Ray Code Standards — agentcore-task

**Rule:** ray-code-standards  
**Scope:** `devmind/agentcore/agentcore-task` (hand-written Python; migrations excluded)  
**Date:** 2025-02-26

## Summary

- Applied Ray Code Standards to the agentcore-task package.
- **Fixes applied:** Line length (79-char limit) in 3 files.
- **No change:** Imports, docstrings, comments, logging (f-strings), NOTE(Ray), naming, block structure, and long-task logs already compliant or explicitly excepted.

## Files Reviewed (hand-written)

| File | Status |
|------|--------|
| `agentcore_task/adapters/django/conf.py` | OK (NOTE for lazy import; no change) |
| `agentcore_task/adapters/django/services/task_tracker.py` | OK (NOTE above block; f-strings; start/finish logs) |
| `agentcore_task/adapters/django/services/timeout.py` | **Fixed** — 2 lines >79 chars |
| `agentcore_task/adapters/django/services/task_config.py` | OK |
| `agentcore_task/adapters/django/services/task_stats.py` | **Fixed** — 5 lines >79 chars |
| `agentcore_task/adapters/django/services/lock.py` | OK |
| `agentcore_task/adapters/django/services/cleanup.py` (re-export) | OK (minimal boilerplate) |
| `agentcore_task/adapters/django/services/task_lock.py` (re-export) | OK |
| `agentcore_task/adapters/django/services/log_collector.py` | OK |
| `agentcore_task/adapters/django/cleanup.py` | OK |
| `agentcore_task/adapters/django/tasks/cleanup.py` | OK |
| `agentcore_task/adapters/django/tasks/timeout.py` | OK |
| `agentcore_task/adapters/django/views/task.py` | OK |
| `agentcore_task/adapters/django/views/config.py` | OK |
| `agentcore_task/adapters/django/models.py` | OK |
| `agentcore_task/adapters/django/serializers.py` | **Fixed** — 1 docstring >79 chars |
| `agentcore_task/adapters/django/periodic_tasks.py` | OK |
| `agentcore_task/adapters/django/apps.py` | OK (minimal boilerplate) |
| `agentcore_task/adapters/django/admin.py` | OK |
| `agentcore_task/adapters/django/urls.py` | OK |
| `agentcore_task/constants.py` | OK |
| `agentcore_task/adapters/django/services/__init__.py` | OK |
| `agentcore_task/adapters/django/utils/log_collector.py` | OK (re-export) |

**Excluded (per skill):** `migrations/`, `**/__init__.py` (re-exports only), tests (not in scope for this pass).

## Changes Made

### 1. `agentcore_task/adapters/django/services/timeout.py`

- Lines 49 and 79: `"cutoff": ... if hasattr(...) else str(...)` exceeded 79 characters. Extracted the ternary into a variable `cutoff_str` and used it in the dict.

### 2. `agentcore_task/adapters/django/services/task_stats.py`

- `day_start = start_date.replace(...)` and `timezone.make_aware(...)`: Broke across lines with parentheses.
- `year = end_date.year if hasattr(...)`: Broke across lines.
- List item `{"bucket": f"...", "count": ...}`: Broke into multiple lines.
- Docstring of `get_task_stats`: Shortened "24h / 30d / 12mo" to "24h/30d/12mo" so the line fits.

### 3. `agentcore_task/adapters/django/serializers.py`

- `TaskStatsSerializer` docstring was one long line. Split into a short multi-line docstring.

## Checklist (post-fix)

- [x] No line over 79 characters (in reviewed files)
- [x] Imports at top; three groups; absolute preferred (conf.py lazy import has NOTE)
- [x] Comments in English; above code; no inline comments
- [x] Docstrings present (English)
- [x] NOTE(Ray) where needed (conf, task_tracker)
- [x] Naming short and precise
- [x] Logging/print with variables use f-strings
- [x] Functions under 100 lines
- [x] Logical blocks with single blank line; comments where needed
- [x] Logs with context (task_id, task_name, etc.)
- [x] Long-running tasks: "Starting/Finished &lt;task_name&gt;" (task_tracker, tasks)
- [x] Review record saved to `docs/review_histories/ray-code-standards_agentcore-task.md`
