import assert from 'node:assert/strict'
import test from 'node:test'

import {
  formatAmountByCurrency,
  hasMixedCurrencies,
  hasNonZeroAmount,
  topAmountsByCurrency
} from '../src/utils/currency.js'

test('formats every currency bucket with a consistent compact layout', () => {
  const result = formatAmountByCurrency(
    null,
    [
      { amount: 0, currency: '未知' },
      { amount: 16111000, currency: 'CNY' },
      { amount: 250000, currency: 'USD' }
    ],
    { compact: true }
  )

  assert.equal(result, 'CNY 1611.1万 / USD 25.0万')
})

test('uses the fallback value when currency buckets are unavailable', () => {
  assert.equal(
    formatAmountByCurrency(0, [], {
      compact: true,
      fallbackCurrency: 'CNY'
    }),
    'CNY 0'
  )
})

test('uses English compact notation when the UI locale is English', () => {
  const result = formatAmountByCurrency(
    null,
    [
      { amount: 16111000, currency: 'CNY' },
      { amount: 250000, currency: 'USD' }
    ],
    { compact: true, locale: 'en-US' }
  )

  assert.equal(result, 'CNY 16.1M / USD 250K')
})

test('detects activity in any currency bucket', () => {
  const items = [
    { amount: 0, currency: 'CNY' },
    { amount: 10, currency: 'USD' }
  ]

  assert.equal(hasNonZeroAmount(0, items), true)
})

test('detects when trend buckets contain multiple currencies', () => {
  assert.equal(
    hasMixedCurrencies([
      { amount: 100, currency: 'CNY' },
      { amount: 20, currency: 'USD' }
    ]),
    true
  )
  assert.equal(
    hasMixedCurrencies([
      { amount: 100, currency: 'CNY' },
      { amount: 20, currency: 'CNY' }
    ]),
    false
  )
})

test('ranks amounts within each currency instead of across currencies', () => {
  const rows = topAmountsByCurrency(
    [
      { customer: 'CNY A', currency: 'CNY', received: 100 },
      { customer: 'CNY B', currency: 'CNY', received: 200 },
      { customer: 'USD A', currency: 'USD', received: 90 }
    ],
    'received',
    1
  )

  assert.deepEqual(
    rows.map((item) => item.customer),
    ['CNY B', 'USD A']
  )
})
