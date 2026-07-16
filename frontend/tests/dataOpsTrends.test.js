import test from 'node:test'
import assert from 'node:assert/strict'

import {
  availableTrendCurrencies,
  buildAmountTrendRows,
  buildCashTrendRows,
} from '../src/utils/dataOpsTrends.js'


test('builds complete monthly periods without mixing currencies', () => {
  const rows = buildAmountTrendRows(
    [
      { month: '2026-01', currency: 'CNY', amount: 100 },
      { month: '2026-03', currency: 'CNY', amount: 300 },
      { month: '2026-06', currency: 'CNY', amount: 600 },
      { month: '2026-06', currency: 'USD', amount: 10 },
      { month: '2026-07', currency: 'CNY', amount: 700 },
      { month: '2026-09', currency: 'CNY', amount: 900 },
    ],
    {
      currency: 'CNY',
      currentMonth: '2026-07',
      period: 'month',
      range: '6',
    }
  )

  assert.deepEqual(
    rows.map(({ label, amount, delta }) => ({ label, amount, delta })),
    [
      { label: '2026-01', amount: 100, delta: null },
      { label: '2026-02', amount: 0, delta: -100 },
      { label: '2026-03', amount: 300, delta: null },
      { label: '2026-04', amount: 0, delta: -100 },
      { label: '2026-05', amount: 0, delta: null },
      { label: '2026-06', amount: 600, delta: null },
    ]
  )
})

test('uses only fully completed quarters', () => {
  const rows = buildAmountTrendRows([], {
    currency: 'CNY',
    currentMonth: '2026-07',
    period: 'quarter',
    range: '3',
  })

  assert.deepEqual(
    rows.map(({ label }) => label),
    ['2025 Q4', '2026 Q1', '2026 Q2']
  )
})

test('keeps collections and expenses separate and calculates net cash', () => {
  const rows = buildCashTrendRows(
    [
      { month: '2026-04', currency: 'CNY', amount: 100 },
      { month: '2026-05', currency: 'CNY', amount: 50 },
      { month: '2026-06', currency: 'CNY', amount: 80 },
    ],
    [
      { month: '2026-04', currency: 'CNY', amount: 40 },
      { month: '2026-06', currency: 'CNY', amount: 100 },
    ],
    {
      currency: 'CNY',
      currentMonth: '2026-07',
      period: 'month',
      range: '3',
    }
  )

  assert.deepEqual(
    rows.map(({ label, received, expense, net }) => ({
      label,
      received,
      expense,
      net,
    })),
    [
      { label: '2026-04', received: 100, expense: 40, net: 60 },
      { label: '2026-05', received: 50, expense: 0, net: 50 },
      { label: '2026-06', received: 80, expense: 100, net: -20 },
    ]
  )
})

test('lists every trend currency with CNY first', () => {
  const currencies = availableTrendCurrencies(
    [{ currency: 'USD' }, { currency: 'CNY' }],
    [{ currency: 'HKD' }, { currency: 'USD' }]
  )

  assert.deepEqual(currencies, ['CNY', 'HKD', 'USD'])
})
