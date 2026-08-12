import assert from 'node:assert/strict'
import test from 'node:test'

import {
  addResaleTierCard,
  buildResaleTierCards,
  buildFlatResalePriceItems,
  buildResaleTierDraftFromCards,
  hasTieredResalePrices,
  normalizeResalePriceDraft,
  removeResaleTierCard,
  removeResaleTierRow,
  selectPreferredChannelPriceItems,
  shouldRestoreSavedResalePriceDraft,
  updateResaleTierCard,
  updateResaleTierRows,
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

test('accepts an unbounded final tier without a terminal error', () => {
  const errors = validateResalePriceDraft({
    cache: [{ end: null, price: '0.25', start: '0' }],
    input: [
      { end: '1000000', price: '1', start: '0' },
      { end: null, price: '0.8', start: '1000000' }
    ],
    output: [{ end: null, price: '2', start: '0' }]
  })

  assert.deepEqual(errors, {})
})

test('accepts a bounded final tier copied from the upstream source', () => {
  const errors = validateResalePriceDraft({
    cache: [{ end: '1000000', price: '0.25', start: '0' }],
    input: [
      { end: '128000', price: '1', start: '0' },
      { end: '256000', price: '0.9', start: '128000' },
      { end: '1000000', price: '0.8', start: '256000' }
    ],
    output: [{ end: '1000000', price: '2', start: '0' }]
  })

  assert.deepEqual(errors, {})
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

test('keeps the next tier start connected when the current end changes', () => {
  const rows = [
    { end: '100', price: '1', start: '0' },
    { end: null, price: '2', start: '100' }
  ]

  assert.deepEqual(updateResaleTierRows(rows, 0, 'end', '250'), [
    { end: '250', price: '1', start: '0' },
    { end: null, price: '2', start: '250' }
  ])
})

test('keeps the previous tier end connected when the current start changes', () => {
  const rows = [
    { end: '100', price: '1', start: '0' },
    { end: null, price: '2', start: '100' }
  ]

  assert.deepEqual(updateResaleTierRows(rows, 1, 'start', '250'), [
    { end: '250', price: '1', start: '0' },
    { end: null, price: '2', start: '250' }
  ])
})

test('bridges adjacent ranges when a middle tier is removed', () => {
  const rows = [
    { end: '100', price: '1', start: '0' },
    { end: '200', price: '0.8', start: '100' },
    { end: null, price: '0.6', start: '200' }
  ]

  assert.deepEqual(removeResaleTierRow(rows, 1), [
    { end: '200', price: '1', start: '0' },
    { end: null, price: '0.6', start: '200' }
  ])
})

test('restores a saved pending draft when upstream ranges have changed', () => {
  const savedDraft = {
    cache: [{ end: null, flat: true, price: '0.25', start: null }],
    input: [
      { end: '100', flat: false, price: '1', start: '0' },
      { end: null, flat: false, price: '0.8', start: '100' }
    ],
    output: [{ end: null, flat: true, price: '2', start: null }]
  }
  const upstreamDraft = {
    cache: [{ end: null, flat: true, price: '0.20', start: null }],
    input: [{ end: null, flat: true, price: '0.9', start: null }],
    output: [{ end: null, flat: true, price: '1.8', start: null }]
  }

  assert.equal(
    shouldRestoreSavedResalePriceDraft(
      { pending_price_items: [{ id: 1 }] },
      savedDraft,
      upstreamDraft
    ),
    true
  )
})

test('uses upstream ranges for a published price when boundaries changed', () => {
  const savedDraft = {
    input: [
      { end: '100', flat: false, price: '1', start: '0' },
      { end: null, flat: false, price: '0.8', start: '100' }
    ]
  }
  const upstreamDraft = {
    input: [{ end: null, flat: true, price: '0.9', start: null }]
  }

  assert.equal(
    shouldRestoreSavedResalePriceDraft(
      { current_price_items: [{ id: 1 }], pending_price_items: [] },
      savedDraft,
      upstreamDraft
    ),
    false
  )
})

test('selects one coherent channel price variant before displaying tiers', () => {
  const items = [
    {
      dimension: 'text_input',
      id: 4,
      spec: { deployment_scope: '国际' },
      tier_end: '100',
      tier_start: '0'
    },
    {
      dimension: 'text_output',
      id: 5,
      spec: { deployment_scope: '国际' },
      tier_end: '100',
      tier_start: '0'
    },
    {
      dimension: 'cache_input',
      id: 6,
      spec: { deployment_scope: '国际' },
      tier_end: '100',
      tier_start: '0'
    },
    {
      dimension: 'text_input',
      id: 1,
      spec: {},
      tier_end: '100',
      tier_start: '0'
    },
    {
      dimension: 'text_output',
      id: 2,
      spec: {},
      tier_end: '100',
      tier_start: '0'
    },
    {
      dimension: 'cache_input',
      id: 3,
      spec: {},
      tier_end: '100',
      tier_start: '0'
    }
  ]

  assert.deepEqual(
    selectPreferredChannelPriceItems(items).map((item) => item.id),
    [1, 2, 3]
  )
})

test('builds one shared card for each aligned input output and cache tier', () => {
  const cards = buildResaleTierCards({
    cache: [
      { end: '100', flat: false, price: '0.1', start: '0' },
      { end: null, flat: false, price: '0.2', start: '100' }
    ],
    input: [
      { end: '100', flat: false, price: '1', start: '0' },
      { end: null, flat: false, price: '2', start: '100' }
    ],
    output: [
      { end: '100', flat: false, price: '3', start: '0' },
      { end: null, flat: false, price: '4', start: '100' }
    ]
  })

  assert.deepEqual(cards, [
    {
      end: '100',
      flat: false,
      prices: { cache: '0.1', input: '1', output: '3' },
      start: '0'
    },
    {
      end: null,
      flat: false,
      prices: { cache: '0.2', input: '2', output: '4' },
      start: '100'
    }
  ])
})

test('uses the union of dimension boundaries in the shared tier cards', () => {
  const cards = buildResaleTierCards({
    cache: [
      { end: '200', flat: false, price: '0.1', start: '0' },
      { end: null, flat: false, price: '0.2', start: '200' }
    ],
    input: [
      { end: '100', flat: false, price: '1', start: '0' },
      { end: null, flat: false, price: '2', start: '100' }
    ],
    output: [{ end: null, flat: true, price: '3', start: null }]
  })

  assert.deepEqual(
    cards.map((card) => [card.start, card.end, card.prices]),
    [
      ['0', '100', { cache: '0.1', input: '1', output: '3' }],
      ['100', '200', { cache: '0.1', input: '2', output: '3' }],
      ['200', null, { cache: '0.2', input: '2', output: '3' }]
    ]
  )
})

test('adds edits and removes shared tiers across all price dimensions', () => {
  const flatCards = buildResaleTierCards({
    cache: [{ end: null, flat: true, price: '0.1', start: null }],
    input: [{ end: null, flat: true, price: '1', start: null }],
    output: [{ end: null, flat: true, price: '3', start: null }]
  })
  const added = addResaleTierCard(flatCards)
  const updated = updateResaleTierCard(added, 0, 'end', '250')
  const removed = removeResaleTierCard(updated, 0)
  const draft = buildResaleTierDraftFromCards(removed)

  assert.deepEqual(
    added.map((card) => [card.start, card.end]),
    [
      ['0', '1000000'],
      ['1000000', null]
    ]
  )
  assert.deepEqual(
    updated.map((card) => [card.start, card.end]),
    [
      ['0', '250'],
      ['250', null]
    ]
  )
  assert.deepEqual(draft, {
    cache: [{ end: null, flat: false, price: '0.1', start: '0' }],
    input: [{ end: null, flat: false, price: '1', start: '0' }],
    output: [{ end: null, flat: false, price: '3', start: '0' }]
  })
})

test('rejects shared boundaries that would collapse adjacent tiers', () => {
  const cards = [
    {
      end: '100',
      flat: false,
      prices: { cache: '0.1', input: '1', output: '3' },
      start: '0'
    },
    {
      end: '200',
      flat: false,
      prices: { cache: '0.2', input: '2', output: '4' },
      start: '100'
    },
    {
      end: null,
      flat: false,
      prices: { cache: '0.3', input: '3', output: '5' },
      start: '200'
    }
  ]

  assert.deepEqual(updateResaleTierCard(cards, 0, 'end', ''), cards)
  assert.deepEqual(updateResaleTierCard(cards, 0, 'end', '0'), cards)
  assert.deepEqual(updateResaleTierCard(cards, 0, 'end', '200'), cards)
})
