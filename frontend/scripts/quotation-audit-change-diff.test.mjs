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

  assert.ok(
    lines.some(
      (line) =>
        line.kind === 'context' &&
        line.text.includes('"qty"'),
    ),
  )
  assert.ok(
    lines.some(
      (line) =>
        line.kind === 'removed' &&
        line.text.includes('test123'),
    ),
  )
  assert.ok(
    lines.some(
      (line) =>
        line.kind === 'added' &&
        line.text.includes('test456'),
    ),
  )
})

test('renders values without old and new as neutral JSON lines', () => {
  assert.ok(
    buildAuditChangeLines({ value: 1 }).every(
      (line) => line.kind === 'context',
    ),
  )
})
