import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildFlatResalePriceItems,
  hasTieredResalePrices,
  normalizeResalePriceDraft,
  validateResalePriceDraft
} from '../src/utils/resaleTierDraft.js'

test('builds a flat resale price table for input, output, and cache', () => {
  assert.deepEqual(
    buildFlatResalePriceItems(
      { cache: '0.25', input: '1.25', output: '5' },
      'USD'
    ),
    [
      {
        billing_unit: 'per_1m_tokens',
        currency: 'USD',
        dimension: 'text_input',
        spec: {},
        tier_end: null,
        tier_start: null,
        tier_type: 'flat',
        unit_price: '1.25'
      },
      {
        billing_unit: 'per_1m_tokens',
        currency: 'USD',
        dimension: 'text_output',
        spec: {},
        tier_end: null,
        tier_start: null,
        tier_type: 'flat',
        unit_price: '5'
      },
      {
        billing_unit: 'per_1m_tokens',
        currency: 'USD',
        dimension: 'cache_input',
        spec: {},
        tier_end: null,
        tier_start: null,
        tier_type: 'flat',
        unit_price: '0.25'
      }
    ]
  )
})

test('normalizes tier rows in stable dimension and boundary order', () => {
  const items = normalizeResalePriceDraft(
    {
      cache: [
        { end: null, price: '0.20', start: '1000000' },
        { end: '1000000', price: '0.25', start: '0' }
      ],
      input: [
        { end: null, price: '0.8', start: '1000000' },
        { end: '1000000', price: '1', start: '0' }
      ],
      output: [{ end: null, price: '2', start: '0' }]
    },
    'USD'
  )

  assert.deepEqual(
    items.map((item) => [
      item.dimension,
      item.tier_start,
      item.tier_end,
      item.tier_type
    ]),
    [
      ['text_input', '0', '1000000', 'usage_range'],
      ['text_input', '1000000', null, 'usage_range'],
      ['text_output', '0', null, 'usage_range'],
      ['cache_input', '0', '1000000', 'usage_range'],
      ['cache_input', '1000000', null, 'usage_range']
    ]
  )
})

test('keeps a single unbounded usage range on the tiered API path', () => {
  const draft = {
    cache: [{ end: null, flat: false, price: '0.25', start: '0' }],
    input: [{ end: null, flat: false, price: '1', start: '0' }],
    output: [{ end: null, flat: false, price: '2', start: '0' }]
  }

  assert.equal(hasTieredResalePrices(draft), true)
  assert.deepEqual(
    normalizeResalePriceDraft(draft, 'USD').map((item) => item.tier_type),
    ['usage_range', 'usage_range', 'usage_range']
  )
})

test('locates price, overlap, and gap errors by dimension, row, and field', () => {
  const errors = validateResalePriceDraft({
    cache: [{ end: null, price: '-1', start: '0' }],
    input: [
      { end: '100', price: '1', start: '0' },
      { end: null, price: '2', start: '99' }
    ],
    output: [
      { end: '100', price: '1', start: '0' },
      { end: null, price: '2', start: '101' }
    ]
  })

  assert.equal(errors['cache:0:price'], 'price_table.invalid_price')
  assert.equal(errors['input:1:start'], 'price_table_overlap')
  assert.equal(errors['output:1:start'], 'price_table_gap')
})
