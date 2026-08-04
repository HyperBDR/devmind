# Audit JSON Diff Highlighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在报价更新审计详情中以红色删除行、绿色新增行展示完整 JSON 差异。

**Architecture:** 新增一个无 UI 依赖的 TypeScript 工具，将 `{ old, new }`
转换为基于最长公共子序列的逐行 JSON 差异；审计抽屉只负责按行类型渲染。
非新旧值结构继续使用中性 JSON 行，后端数据结构不变。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS、Node.js test runner。

---

### Task 1: JSON 差异行生成器

**Files:**
- Create:
  `frontend/src/modules/quotation/utils/auditChangeDiff.ts`
- Test:
  `frontend/scripts/quotation-audit-change-diff.test.mjs`

- [ ] **Step 1: 写入失败测试**

测试直接导入 TypeScript 工具，并验证标量、对象、报价明细数组及普通 JSON：

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildAuditChangeLines,
} from '../src/modules/quotation/utils/auditChangeDiff.ts'

test('marks replaced scalar values as removed and added', () => {
  assert.deepEqual(
    buildAuditChangeLines({ old: 'Before', new: 'After' }),
    [
      { kind: 'removed', text: '"Before"' },
      { kind: 'added', text: '"After"' },
    ],
  )
})

test('keeps unchanged item fields and marks changed JSON lines', () => {
  const lines = buildAuditChangeLines({
    old: [{ qty: '1.00', description: 'test123' }],
    new: [{ qty: '1.00', description: 'test456' }],
  })

  assert.ok(lines.some(
    (line) => line.kind === 'context' && line.text.includes('"qty"'),
  ))
  assert.ok(lines.some(
    (line) => line.kind === 'removed' && line.text.includes('test123'),
  ))
  assert.ok(lines.some(
    (line) => line.kind === 'added' && line.text.includes('test456'),
  ))
})

test('renders values without old and new as neutral JSON lines', () => {
  assert.ok(
    buildAuditChangeLines({ value: 1 }).every(
      (line) => line.kind === 'context',
    ),
  )
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
node --test frontend/scripts/quotation-audit-change-diff.test.mjs
```

Expected: FAIL，提示找不到 `auditChangeDiff.ts`。

- [ ] **Step 3: 实现最小差异算法**

创建以下接口和函数：

```typescript
export type AuditDiffLineKind = 'context' | 'removed' | 'added'

export interface AuditDiffLine {
  kind: AuditDiffLineKind
  text: string
}

export function buildAuditChangeLines(
  value: unknown,
): AuditDiffLine[]
```

实现要求：

1. 使用 `JSON.stringify(value, null, 2)` 生成稳定的行数组。
2. 仅当值为同时拥有 `old`、`new` 键的普通对象时生成差异。
3. 使用最长公共子序列保留相同行为 `context`。
4. 旧值独有行标记为 `removed`，新值独有行标记为 `added`。
5. `undefined`、空字符串与无法序列化的值显示为 `null`。

- [ ] **Step 4: 运行工具测试**

Run:

```bash
node --test frontend/scripts/quotation-audit-change-diff.test.mjs
```

Expected: 3 tests PASS。

### Task 2: 审计抽屉差异渲染

**Files:**
- Modify:
  `frontend/src/modules/quotation/components/AuditLogPage.vue:14-21`
- Modify:
  `frontend/src/modules/quotation/components/AuditLogPage.vue:241-250`
- Modify:
  `frontend/src/modules/quotation/components/AuditLogPage.vue:422-435`
- Modify:
  `frontend/scripts/quotation-audit-log.test.mjs`

- [ ] **Step 1: 写入失败的组件契约测试**

在现有审计测试中增加：

```javascript
test('Audit Log renders JSON additions and removals with semantic colors', () => {
  assert.match(auditPage, /buildAuditChangeLines/)
  assert.match(auditPage, /change-line-removed/)
  assert.match(auditPage, /change-line-added/)
  assert.match(auditPage, /bg-red-50/)
  assert.match(auditPage, /bg-emerald-50/)
  assert.match(auditPage, /line\.kind === 'removed' \? '- ' :/)
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
node --test frontend/scripts/quotation-audit-log.test.mjs
```

Expected: FAIL，缺少差异行渲染标记。

- [ ] **Step 3: 修改抽屉渲染**

1. 导入 `buildAuditChangeLines` 和 `AuditDiffLineKind`。
2. `changeDetails` 为每个字段附加 `lines`。
3. 增加 `changeLineClass(kind)`：
   - `removed`: `bg-red-50 text-red-700`
   - `added`: `bg-emerald-50 text-emerald-700`
   - `context`: `text-dm-text`
4. 将单个字符串 `<pre>` 改成逐行 `<span>`；删除行显示 `- `，
   新增行显示 `+ `，上下文行显示两个空格。
5. 添加 `data-change-line-removed` 与 `data-change-line-added`，
   用于测试和无障碍检查。

- [ ] **Step 4: 运行前端测试与类型检查**

Run:

```bash
node --test \
  frontend/scripts/quotation-audit-change-diff.test.mjs \
  frontend/scripts/quotation-audit-log.test.mjs
npm --prefix frontend run typecheck
```

Expected: 全部 PASS，`vue-tsc` 退出码为 0。

### Task 3: 浏览器验收

**Files:** No source changes.

- [ ] **Step 1: 打开修改报价审计事件**

使用 ego lite 打开 `/quotation/audit`，选择一个包含报价明细变化的
“修改报价”事件。

- [ ] **Step 2: 验证视觉与行为**

确认：

- 旧值行有红色背景和 `-` 前缀。
- 新值行有绿色背景和 `+` 前缀。
- `qty` 等未变化行保持中性。
- 长 JSON 仍可在原卡片内滚动。
- 浏览器控制台无错误。

本计划不包含 Git 提交；仅在用户明确要求时提交。
