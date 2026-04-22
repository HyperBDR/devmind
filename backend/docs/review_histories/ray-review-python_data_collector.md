# Ray Review Python – data_collector (second pass)

**Rule:** ray-review-python  
**Scope:** `devmind/data_collector/` (hand-written Python; migrations and trivial `__init__.py` excluded)  
**Date:** 2026-03-02  
**Tool:** Flake8 `--max-line-length=79` (excl. migrations, tests)

---

## 1. Findings (by severity)

### High

- **Line length > 79 characters (93 violations across app).**  
  Ray rule: max 79. Flake8 reports E501 in:
  - **views/config.py:** 2, 18, 45, 59, 84, 127, 175, 296, 342 (descriptions, ValidationError, Response).
  - **views/records.py:** 25, 76 (extend_schema description; import os inline).
  - **views/stats.py:** 24 (extend_schema description).
  - **tasks.py:** 39, 41, 49, 67, 100, 117, 157, 187–191, 205, 217, 236, 249, 265, 271, 279, 336, 428–429, 442–443, 448–450, 480, 491, 601 (docstrings, logger, TaskTracker, long expressions).
  - **serializers.py:** 2, 22, 47, 58, 109, 127–128, 170, 212 (docstrings, Conflict message, method field doc, list comp).
  - **models.py:** 71, 76, 173 (help_text, __str__).
  - **services/storage.py:** 2, 3, 19, 21, 28, 30–31, 33 (docstrings, path comments).
  - **services/beat_sync.py:** 60, 62, 98 (logger, update_or_create).
  - **services/providers/jira.py:** 2, 23, 32–33, 43, 62, 67, 80, 108, 146–147, 159, 167, 192, 195–196, 230, 257 (docstrings, _client, JQL, logger, method signatures).
  - **services/providers/base.py:** 36, 75–76 (docstrings).
  - **services/providers/feishu.py:** 45 (docstring).
  - **api_urls.py:** 17.  
  - **__init__.py:** 3.  
  **Action:** Break long lines (wrap strings, split kwargs, assign to variables) or shorten text to ≤ 79.

### Medium

- **Imports not at top / unused imports.**  
  - **serializers.py L43:** `from rest_framework.exceptions import Conflict` inside `update()`. Ray: imports at file top only.  
  - **views/records.py L5:** `get_object_or_404` imported but unused (F401).  
  - **views/records.py L91:** `import os` inside `download()`; move to file top.  
  - **views/stats.py L5:** `timezone` imported but unused (F401).  
  - **services/beat_sync.py L8:** `transaction` imported but unused (F401).  
  - **tasks.py L10:** `Decimal` imported but unused (F401).  
  - **tasks.py L25:** `get_data_collector_root` imported but unused (F401).  
  **Action:** Move `Conflict` to top of serializers.py; remove or use unused imports; move `os` to top in records.py.

### Low / Advisory

- **User-facing and UI strings in Chinese** (e.g. config.py "该平台下已存在采集配置…", tasks metadata "开始采集", "拉取原始数据").  
  Ray: "Comments and docstrings must be English."  
  **Advisory:** Runtime messages for UI/i18n; no change required for docstring/comment rule.

- **Relative imports** (e.g. `from .models`, `from ..serializers`).  
  Ray: "Prefer absolute imports; use relative when necessary."  
  **Advisory:** Django app convention; acceptable.

- **NOTE(Ray)/TODO(Ray)/FIXME(Ray):** No special markers present; none required unless introducing constraints or known workarounds.

---

## 2. Open questions / assumptions

- **Migrations** and **trivial `__init__.py`** are out of scope per skill.  
- **Test files** (`tests/`) were excluded from Flake8 run; style can be aligned in a follow-up.  
- Assumed fixing all 93 E501 in one pass is optional; prioritise views/config.py, tasks.py, serializers.py, and jira.py for impact.

---

## 3. Summary and residual risks

**Summary:**  
- **Second pass** re-checked `data_collector` against Ray rules. **High:** 93 lines over 79 characters across the app; **Medium:** one inline import (Conflict in serializers), several unused imports, and one inline `import os` in views/records.  
- Previous pass had addressed: logging f-strings, serializers long line, jira datetime imports, tasks Prefetch/update_fields break, run_cleanup redundant `import os`.  
- **Remaining:** Systematic line-length fixes (wrap/split/shorten), move `Conflict` to top in serializers, remove unused imports, move `os` to top in records.

**Residual risks / testing gaps:**  
- No behavior change from style-only fixes.  
- Recommend: `flake8 devmind/data_collector --max-line-length=79 --exclude=...` and `pytest devmind/data_collector/tests/` after applying fixes.
