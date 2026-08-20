import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  compareChannelOptions,
  effectiveMatrixAction,
  optionFreshness,
  savingsPercent
} from '../src/utils/llmOpsChannelPriceMatrix.js'
import { dataGroupsForSection } from '../src/utils/llmOpsSectionData.js'

const matrixSource = readFileSync(
  new URL(
    '../src/components/llm-ops/ChannelPriceMatrixPanel.vue',
    import.meta.url
  ),
  'utf8'
)
const drawerSource = readFileSync(
  new URL(
    '../src/components/llm-ops/ChannelPriceCompareDrawer.vue',
    import.meta.url
  ),
  'utf8'
)
const pageSource = readFileSync(
  new URL('../src/pages/LLMOps.vue', import.meta.url),
  'utf8'
)

const now = new Date('2026-08-20T12:00:00Z').getTime()

test('marks channel prices older than 24 hours as stale', () => {
  assert.equal(
    optionFreshness({ price_updated_at: '2026-08-19T11:59:59Z' }, now).state,
    'stale'
  )
  assert.equal(
    optionFreshness({ price_updated_at: '2026-08-20T11:30:00Z' }, now).state,
    'fresh'
  )
  assert.equal(optionFreshness({}, now).state, 'unknown')
})

test('requires a price refresh before another commercial action', () => {
  const row = {
    decision_action: 'switch_lowest_channel',
    options: [
      {
        price_updated_at: '2026-08-18T12:00:00Z'
      }
    ]
  }

  assert.equal(effectiveMatrixAction(row, now), 'refresh_prices')
  assert.equal(
    effectiveMatrixAction(
      {
        ...row,
        options: [{ price_updated_at: '2026-08-20T11:30:00Z' }]
      },
      now
    ),
    'switch_lowest_channel'
  )
})

test('sorts comparable offers by the selected pricing dimension', () => {
  const row = {
    options: [
      {
        channel_id: 1,
        input_price_per_million: 3,
        output_price_per_million: 6
      },
      {
        channel_id: 2,
        input_price_per_million: 2,
        output_price_per_million: 9
      },
      {
        channel_id: 3,
        input_price_per_million: null,
        output_price_per_million: 4
      }
    ]
  }

  assert.deepEqual(
    compareChannelOptions(row, 'input').map((item) => item.channel_id),
    [2, 1]
  )
  assert.deepEqual(
    compareChannelOptions(row, 'output').map((item) => item.channel_id),
    [3, 1, 2]
  )
})

test('calculates savings against the currently listed channel', () => {
  const row = {
    current_listing: { channel_id: 1 },
    options: [
      { channel_id: 1, input_price_per_million: 4 },
      { channel_id: 2, input_price_per_million: 3 }
    ]
  }

  assert.equal(savingsPercent(row, 'input'), 25)
  assert.equal(savingsPercent({ options: row.options }, 'input'), null)
})

test('loads contract pricing data only when the matrix is opened', () => {
  assert.deepEqual(dataGroupsForSection('channelMatrix'), [
    'channels',
    'channelPricing',
    'summary'
  ])
})

test('connects dimension pricing, comparison details, and model drill-down', () => {
  assert.match(matrixSource, /v-for="dimension in dimensions"/)
  assert.match(matrixSource, /<ChannelPriceCompareDrawer/)
  assert.match(matrixSource, /emit\('navigate-to-detail', row\.model_id\)/)
  assert.match(matrixSource, /section: staleOption\?\.price_source_id/)
  assert.match(drawerSource, /role="dialog"/)
  assert.match(drawerSource, /contractContext\(offer\)\.effectiveWindow/)
  assert.match(pageSource, /@navigate-to-detail="openChannelListingDetail"/)
  assert.match(pageSource, /:channel-price-versions="channelPriceVersions"/)
})
