import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  buildPriceChangeRows,
  priceChangeDelta
} from '../src/utils/llmOpsPriceChanges.js'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

const listingDisplaySource = source(
  '../src/composables/useAgioneListingDisplay.js'
)
const globalConfigSource = source(
  '../src/components/llm-ops/GlobalConfigPanel.vue'
)
const metaModelSource = source(
  '../src/components/llm-ops/MetaModelManagement.vue'
)
const priceSourceModalSource = source(
  '../src/components/llm-ops/PriceSourceModal.vue'
)
const healthSource = source(
  '../src/components/llm-ops/CollectionHealthPanel.vue'
)
const pageSource = source('../src/pages/LLMOps.vue')

test('builds distinguishable price changes for every pricing dimension', () => {
  const rows = buildPriceChangeRows({
    channelHistory: [
      {
        id: 2,
        channel: 3,
        channel_name: 'Channel A',
        model: 7,
        offering: 9,
        price_source_name: 'Supplier A',
        currency: 'CNY',
        input_price_per_million: '2',
        effective_from: '2026-08-21T02:00:00Z'
      },
      {
        id: 1,
        channel: 3,
        channel_name: 'Channel A',
        model: 7,
        offering: 9,
        price_source_name: 'Supplier A',
        currency: 'CNY',
        input_price_per_million: '1',
        effective_from: '2026-08-20T02:00:00Z'
      }
    ],
    listingHistory: [
      {
        id: 4,
        platform: 6,
        platform_name: 'Platform A',
        model: 7,
        channel: 3,
        channel_name: 'Channel A',
        currency: 'CNY',
        retail_cache_input_price_per_million: '0.8',
        effective_from: '2026-08-21T02:30:00Z'
      },
      {
        id: 3,
        platform: 6,
        platform_name: 'Platform A',
        model: 7,
        channel: 3,
        channel_name: 'Channel A',
        currency: 'CNY',
        retail_cache_input_price_per_million: '0.5',
        effective_from: '2026-08-20T02:30:00Z'
      }
    ],
    priceItems: [
      {
        id: 5,
        model: 7,
        model_name: 'Model A',
        source_name: 'Official A',
        dimension: 'cache_input',
        currency: 'CNY',
        unit_price: '0.2',
        effective_from: '2026-08-21T03:00:00Z'
      }
    ]
  })

  const channel = rows.find(
    (row) => row.type === 'channel' && row.dimension === 'text_input'
  )
  const official = rows.find((row) => row.type === 'official')
  const listing = rows.find(
    (row) => row.type === 'listing' && row.dimension === 'cache_input'
  )
  assert.equal(channel.previous, '1')
  assert.equal(channel.current, '2')
  assert.equal(channel.source, 'Supplier A')
  assert.equal(priceChangeDelta(channel), 1)
  assert.equal(official.dimension, 'cache_input')
  assert.equal(official.current, '0.2')
  assert.equal(official.source, 'Official A')
  assert.equal(listing.previous, '0.5')
  assert.equal(listing.current, '0.8')
  assert.ok(Math.abs(priceChangeDelta(listing) - 0.3) < Number.EPSILON * 2)
})

test('builds official price changes from collected history versions', () => {
  const rows = buildPriceChangeRows({
    officialHistory: [
      {
        id: 2,
        source: 4,
        source_name: 'DeepSeek Official',
        offering: 8,
        source_platform_id: 'deepseek-v4-flash',
        model: 7,
        model_name: 'DeepSeek V4 Flash',
        currency: 'CNY',
        normalized_price_rows: [
          {
            values: {
              input_price: '1.2',
              output_price: '2.4',
              cache_hit_input_price: '0.12'
            }
          }
        ],
        effective_from: '2026-08-21T02:00:00Z'
      },
      {
        id: 1,
        source: 4,
        source_name: 'DeepSeek Official',
        offering: 8,
        source_platform_id: 'deepseek-v4-flash',
        model: 7,
        model_name: 'DeepSeek V4 Flash',
        currency: 'CNY',
        normalized_price_rows: [
          {
            values: {
              input_price: '1',
              output_price: '2',
              cache_hit_input_price: '0.1'
            }
          }
        ],
        effective_from: '2026-08-20T02:00:00Z'
      }
    ]
  })
  const input = rows.find((row) => row.dimension === 'text_input')
  const cache = rows.find((row) => row.dimension === 'cache_input')
  assert.equal(input.previous, '1')
  assert.equal(input.current, '1.2')
  assert.equal(input.source, 'DeepSeek Official')
  assert.equal(cache.previous, '0.1')
  assert.equal(cache.current, '0.12')
})

test('passes collected official history from the page data composable', () => {
  assert.match(
    pageSource,
    /const\s*\{[\s\S]*?officialPriceHistory[\s\S]*?\}\s*=\s*useLLMOpsData\(\)/
  )
})

test('labels listing KPIs as workflow scope and counts supply candidates', () => {
  assert.match(listingDisplaySource, /workflowCandidates/)
  assert.match(listingDisplaySource, /candidateModels/)
})

test('uses each parsed cron minute in schedule help and future edits', () => {
  assert.doesNotMatch(globalConfigSource, /FIXED_SCHEDULE_MINUTE/)
  assert.match(globalConfigSource, /schedule\.minute/)
})

test('does not combine filtered model totals with vendor-wide active totals', () => {
  assert.doesNotMatch(metaModelSource, /selectedVendorActiveCount/)
  assert.match(metaModelSource, /modelResult[\s\S]*?total: drawerTotal/)
})

test('shows the current sync source while an automatic source is edited', () => {
  assert.match(priceSourceModalSource, /editingSyncSourceLabel/)
  assert.match(priceSourceModalSource, /v-if="isEditing"/)
})

test('falls back to source latest status when recent runs are truncated', () => {
  assert.match(healthSource, /source\.latest_run_status/)
  assert.match(healthSource, /successRate === null/)
})

test('renders contextual loading skeletons for slow section data', () => {
  assert.match(pageSource, /llm-ops-loading-skeleton/)
  assert.match(pageSource, /loadingSectionLabel/)
})
