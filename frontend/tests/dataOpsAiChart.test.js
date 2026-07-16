import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildDataOpsChartDatasets,
  normalizeDataOpsChart
} from '../src/utils/dataOpsChart.js'

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
  assert.equal(
    normalizeDataOpsChart({
      type: 'bar',
      labels: ['A', 'B'],
      series: Array.from({ length: 9 }, (_, index) => ({
        name: `${index + 1}`,
        data: [1, 2]
      }))
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

test('rejects chart shapes that do not add useful visual context', () => {
  assert.equal(
    normalizeDataOpsChart({
      type: 'line',
      labels: ['1月', '2月'],
      data: [1, 2]
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'bar',
      labels: Array.from({ length: 13 }, (_, index) => `${index + 1}`),
      data: Array.from({ length: 13 }, (_, index) => index)
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'pie',
      labels: Array.from({ length: 9 }, (_, index) => `${index + 1}`),
      data: Array.from({ length: 9 }, () => 1)
    }),
    null
  )
  assert.equal(
    normalizeDataOpsChart({
      type: 'bar',
      labels: ['A', ''],
      data: [1, 2]
    }),
    null
  )
})

test('uses distinct category colors for a single-series bar chart', () => {
  const datasets = buildDataOpsChartDatasets({
    type: 'bar',
    labels: ['华东', '华南', '华北'],
    series: [{ name: '回款风险', data: [42, 31, 18] }]
  })

  assert.equal(datasets.length, 1)
  assert.equal(datasets[0].backgroundColor.length, 3)
  assert.equal(new Set(datasets[0].backgroundColor).size, 3)
  assert.equal(new Set(datasets[0].hoverBackgroundColor).size, 3)
})

test('distinguishes multiple bar and line series by color and point shape', () => {
  const groupedBars = buildDataOpsChartDatasets({
    type: 'bar',
    labels: ['一月', '二月'],
    series: [
      { name: '已回款', data: [12, 18] },
      { name: '待回款', data: [8, 5] }
    ]
  })
  const lines = buildDataOpsChartDatasets({
    type: 'line',
    labels: ['一月', '二月', '三月'],
    series: [
      { name: '合同额', data: [10, 12, 15] },
      { name: '回款额', data: [6, 9, 11] }
    ]
  })

  assert.notEqual(
    groupedBars[0].backgroundColor,
    groupedBars[1].backgroundColor
  )
  assert.notEqual(lines[0].borderColor, lines[1].borderColor)
  assert.notEqual(lines[0].pointStyle, lines[1].pointStyle)
  assert.equal(
    lines.every((item) => item.fill === false),
    true
  )
})

test('uses distinct segment and hover colors for pie charts', () => {
  const datasets = buildDataOpsChartDatasets({
    type: 'pie',
    labels: ['高风险', '中风险', '低风险'],
    series: [{ name: '客户分布', data: [6, 12, 20] }]
  })

  assert.equal(new Set(datasets[0].backgroundColor).size, 3)
  assert.equal(new Set(datasets[0].hoverBackgroundColor).size, 3)
  assert.equal(datasets[0].hoverOffset, 8)
})
