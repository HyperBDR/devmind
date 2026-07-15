import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizeDataOpsChart } from '../src/utils/dataOpsChart.js'

test('normalizes supported AI chart types and legacy data', () => {
  const line = normalizeDataOpsChart({
    type: 'line',
    title: '月度回款趋势',
    labels: ['1月', '2月', '3月'],
    data: [12, 18, 24],
    name: '回款',
    unit: '万元'
  })

  assert.deepEqual(line, {
    type: 'line',
    title: '月度回款趋势',
    labels: ['1月', '2月', '3月'],
    series: [{ name: '回款', data: [12, 18, 24] }],
    unit: '万元'
  })
  for (const type of ['bar', 'pie', 'doughnut']) {
    assert.equal(
      normalizeDataOpsChart({
        type,
        labels: ['A', 'B'],
        values: [2, 3]
      })?.type,
      type
    )
  }
})

test('rejects malformed and unsupported AI chart payloads', () => {
  assert.equal(normalizeDataOpsChart({ type: 'radar', data: [1] }), null)
  assert.equal(
    normalizeDataOpsChart({
      type: 'bar',
      labels: ['A', 'B'],
      data: [1]
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'line',
      labels: ['A'],
      data: ['not-a-number']
    }),
    null
  )
})

test('restricts part-to-whole charts to valid single-series data', () => {
  assert.equal(
    normalizeDataOpsChart({
      type: 'pie',
      labels: ['A', 'B'],
      series: [
        { name: '今年', data: [1, 2] },
        { name: '去年', data: [2, 3] }
      ]
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'doughnut',
      labels: ['A', 'B'],
      data: [1, -1]
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'pie',
      labels: ['A', 'B'],
      data: [0, 0]
    }),
    null
  )
})
