import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  buildSourcePriceSchedules,
  tierRangeLabel
} from '../src/utils/sourcePriceCatalog.js'
import {
  channelPriceItemLabel,
  channelPriceSummaryRows,
  channelPriceTierRows
} from '../src/utils/channelPriceCatalog.js'

const providerManagementSource = readFileSync(
  new URL('../src/components/llm-ops/ProviderManagement.vue', import.meta.url),
  'utf8'
)
const sourceDrawerSource = readFileSync(
  new URL('../src/components/llm-ops/SourcePriceDrawer.vue', import.meta.url),
  'utf8'
)
const apiSource = readFileSync(
  new URL('../src/api/llmOps.js', import.meta.url),
  'utf8'
)
const sectionDataSource = readFileSync(
  new URL('../src/utils/llmOpsSectionData.js', import.meta.url),
  'utf8'
)
const dataComposableSource = readFileSync(
  new URL('../src/composables/useLLMOpsData.js', import.meta.url),
  'utf8'
)
const channelManagementSource = readFileSync(
  new URL('../src/components/llm-ops/ChannelManagement.vue', import.meta.url),
  'utf8'
)
const channelModelDrawerSource = readFileSync(
  new URL('../src/components/llm-ops/ChannelModelDrawer.vue', import.meta.url),
  'utf8'
)
const llmOpsPageSource = readFileSync(
  new URL('../src/pages/LLMOps.vue', import.meta.url),
  'utf8'
)
const resaleTierEditorSource = readFileSync(
  new URL('../src/components/llm-ops/ResaleTierEditor.vue', import.meta.url),
  'utf8'
)
const resaleWorkspaceSource = readFileSync(
  new URL(
    '../src/components/llm-ops/ResalePublishingWorkspace.vue',
    import.meta.url
  ),
  'utf8'
)
const resaleTierCardSource = readFileSync(
  new URL('../src/components/llm-ops/ResaleTierCard.vue', import.meta.url),
  'utf8'
)

test('searches the complete source catalogue through the API', () => {
  assert.match(apiSource, /price-catalog/)
  assert.match(providerManagementSource, /search:\s*selectedProviderSearch/)
  assert.match(sourceDrawerSource, /emit\('search'/)
  assert.doesNotMatch(
    sourceDrawerSource,
    /row\.search_text\.includes\(keyword\)/
  )
})

test('keeps the newest source catalogue response during fast searches', () => {
  assert.match(providerManagementSource, /selectedProviderRequestId/)
  assert.match(
    providerManagementSource,
    /requestId !== selectedProviderRequestId/
  )
})

test('renders all source tiers instead of selecting one price per dimension', () => {
  assert.match(sourceDrawerSource, /price-schedule/)
  assert.match(sourceDrawerSource, /tier\.range_label/)
  assert.match(sourceDrawerSource, /billingUnitLabel\(tier\.billing_unit\)/)
  assert.match(sourceDrawerSource, /variant\.scope_label/)
  assert.match(sourceDrawerSource, /variant\.tiers/)
  assert.doesNotMatch(sourceDrawerSource, /rows\.find\(/)
})

test('shows collection and coverage counts with distinct labels', () => {
  assert.match(sourceDrawerSource, /catalogModelCount/)
  assert.match(sourceDrawerSource, /collectedSkuCount/)
  assert.match(sourceDrawerSource, /coveredMetaModelCount/)
  assert.match(sourceDrawerSource, /currentPriceItemCount/)
})

test('does not preload full model and price catalogues for the source page', () => {
  const providersGroup = sectionDataSource.match(
    /providers:\s*\[([^\]]+)\]/
  )?.[1]

  assert.ok(providersGroup)
  assert.match(providersGroup, /'sources'/)
  assert.match(providersGroup, /'runs'/)
  assert.match(providersGroup, /'providers'/)
  assert.doesNotMatch(providersGroup, /'metaModels'/)
  assert.doesNotMatch(providersGroup, /'models'/)
  assert.doesNotMatch(providersGroup, /'modelPrices'/)
})

test('loads only provider owners before opening the meta model manager', () => {
  const metaModelsGroup = sectionDataSource.match(
    /metaModels:\s*\[([^\]]+)\]/
  )?.[1]

  assert.equal(metaModelsGroup?.trim(), "'providers'")
})

test('does not refresh the full summary for isolated management updates', () => {
  for (const name of [
    'refreshProviderManagementData',
    'refreshMetaModelManagementData',
    'refreshChannelManagementData'
  ]) {
    const body = dataComposableSource.match(
      new RegExp(`async function ${name}\\(\\) \\{([\\s\\S]*?)\\n  \\}`)
    )?.[1]

    assert.ok(body, `${name} should exist`)
    assert.doesNotMatch(body, /getSummary/)
  }
})

test('loads LLM Ops panels and publishing workspaces on demand', () => {
  assert.match(llmOpsPageSource, /defineAsyncComponent/)
  assert.match(llmOpsPageSource, /const asyncPanel/)

  for (const component of [
    'ProviderManagement',
    'MetaModelManagement',
    'ChannelManagement',
    'ResalePublishingDrawer',
    'ResalePublishingWorkspace'
  ]) {
    assert.match(
      llmOpsPageSource,
      new RegExp(`const ${component} = asyncPanel`)
    )
    assert.doesNotMatch(
      llmOpsPageSource,
      new RegExp(`import ${component} from`)
    )
  }
})

test('keeps the channel toolbar compact and groups default settings', () => {
  assert.doesNotMatch(
    channelManagementSource,
    /llmOps\.channelManagement\.title/
  )
  assert.doesNotMatch(
    channelManagementSource,
    /llmOps\.channelManagement\.description/
  )
  assert.match(channelManagementSource, /channel-config-summary/)
  assert.match(channelManagementSource, /apiStatus/)
  assert.match(channelManagementSource, /settlementCurrency/)
  assert.match(channelManagementSource, /defaultDiscount/)
})

test('uses one compact visual language across the channel table', () => {
  assert.match(channelManagementSource, /class="channel-code"/)
  assert.match(channelManagementSource, /class="channel-actions"/)
  assert.match(
    channelManagementSource,
    /\.channel-table \{[\s\S]*border-separate/
  )
  assert.match(channelManagementSource, /\.channel-code \{[\s\S]*rounded-md/)
  assert.match(channelManagementSource, /\.channel-actions \{[\s\S]*rounded-lg/)
})

test('opens the channel model drawer before deferred data finishes loading', () => {
  assert.match(channelManagementSource, /prepareModelManagement/)
  assert.match(
    channelManagementSource,
    /await props\.prepareModelManagement\(channel\.id\)/
  )
  const drawerOpenIndex = channelManagementSource.indexOf(
    'selectedChannelForModels.value = channel'
  )
  const prepareIndex = channelManagementSource.indexOf(
    'await props.prepareModelManagement(channel.id)'
  )
  assert.ok(drawerOpenIndex >= 0)
  assert.ok(drawerOpenIndex < prepareIndex)
  assert.match(
    dataComposableSource,
    /refreshChannelPricingData\(options\.channelId\)/
  )
  assert.match(
    dataComposableSource,
    /fetchList\(llmOpsApi\.listChannelOfferings, params\)/
  )
  assert.match(
    dataComposableSource,
    /fetchList\(llmOpsApi\.listChannelModelPrices, params\)/
  )
  assert.match(dataComposableSource, /is_effective: 'true'/)
  assert.match(channelManagementSource, /openingChannelId/)
})

test('keeps the price source drawer localized and keyboard accessible', () => {
  assert.match(sourceDrawerSource, /role="dialog"/)
  assert.match(sourceDrawerSource, /aria-modal="true"/)
  assert.match(
    sourceDrawerSource,
    /aria-labelledby="source-price-drawer-title"/
  )
  assert.match(sourceDrawerSource, /event\.key === 'Escape'/)
  assert.match(sourceDrawerSource, /closeButtonRef\.value\?\.focus\(\)/)
  assert.match(sourceDrawerSource, /sourcePriceDrawer\.catalogLabel/)
  assert.match(sourceDrawerSource, /sourcePriceDrawer\.tierCount/)
})

test('groups dimensions into complete regional tier schedules', () => {
  const items = [
    ['text_input', '12', '0', '1000000', '全球'],
    ['text_output', '36', '0', '1000000', '全球'],
    ['cache_input', '1.2', '0', '1000000', '全球'],
    ['text_input', '16', '1000000', null, '全球'],
    ['text_output', '48', '1000000', null, '全球'],
    ['cache_input', '1.6', '1000000', null, '全球'],
    ['text_input', '14.988', '0', '1000000', '国际']
  ].map(([dimension, unit_price, tier_start, tier_end, region]) => ({
    sku_code: 'qwen3.8-max',
    dimension,
    billing_unit: 'per_1m_tokens',
    currency: 'CNY',
    unit_price,
    tier_type: 'usage_range',
    tier_start,
    tier_end,
    spec: {
      region,
      deployment_scope: region,
      tier_metric: 'request_input_tokens'
    }
  }))

  const schedules = buildSourcePriceSchedules(items)

  assert.equal(schedules.length, 2)
  const global = schedules.find((variant) =>
    variant.scope_label.includes('全球')
  )
  assert.ok(global)
  assert.equal(global.tiers.length, 2)
  assert.deepEqual(
    global.tiers.map((tier) => tier.prices.map((price) => price.dimension)),
    [
      ['text_input', 'text_output', 'cache_input'],
      ['text_input', 'text_output', 'cache_input']
    ]
  )
  assert.equal(global.tiers[0].range_label, '[0, 1,000,000)')
  assert.equal(global.tiers[1].range_label, '[1,000,000, ∞)')
})

test('labels flat and usage-range prices explicitly', () => {
  assert.equal(
    tierRangeLabel({ tier_type: 'flat' }, { flat: '全部用量' }),
    '全部用量'
  )
  assert.equal(
    tierRangeLabel({
      tier_type: 'usage_range',
      tier_start: '0',
      tier_end: null
    }),
    '[0, ∞)'
  )
})

test('groups peak prices under one Beijing schedule with clear labels', () => {
  const items = [
    ['peak', 'text_input', '3'],
    ['peak', 'text_output', '9'],
    ['peak', 'cache_input', '0.3'],
    ['off_peak', 'text_input', '1.5'],
    ['off_peak', 'text_output', '4.5'],
    ['off_peak', 'cache_input', '0.15']
  ].map(([code, dimension, unit_price]) => ({
    sku_code: 'deepseek-v4-flash-0731',
    sku_access_region: 'cn-beijing',
    sku_deployment_scope: 'china_mainland',
    dimension,
    billing_unit: 'per_1m_tokens',
    currency: 'CNY',
    unit_price,
    tier_type: 'flat',
    pricing_condition: {
      type: 'provider_schedule',
      code,
      timezone: 'Asia/Shanghai'
    },
    spec: {
      access_region: 'cn-beijing',
      deployment_scope: 'china_mainland'
    }
  }))

  const schedules = buildSourcePriceSchedules(items, {
    flat: '全部用量',
    peak: '忙时',
    offPeak: '闲时',
    beijing: '华北 2（北京）',
    chinaMainland: '中国内地'
  })

  assert.equal(schedules.length, 1)
  assert.match(schedules[0].scope_label, /华北 2（北京）/)
  assert.match(schedules[0].scope_label, /中国内地/)
  assert.deepEqual(
    schedules[0].tiers.map((tier) => tier.range_label),
    ['忙时', '闲时']
  )
  assert.deepEqual(
    schedules[0].tiers.map((tier) =>
      tier.prices.map((price) => price.dimension)
    ),
    [
      ['text_input', 'text_output', 'cache_input'],
      ['text_input', 'text_output', 'cache_input']
    ]
  )
})

test('keeps every channel price tier when summarizing one dimension', () => {
  const items = [
    ['text_input', '3', '0', '32000'],
    ['text_output', '14', '0', '32000'],
    ['cache_input', '0.3', '0', '32000'],
    ['text_input', '4', '32000', '96000'],
    ['text_output', '16', '32000', '96000'],
    ['cache_input', '0.4', '32000', '96000']
  ].map(([dimension, unit_price, tier_start, tier_end]) => ({
    dimension,
    unit_price,
    currency: 'CNY',
    tier_type: 'usage_range',
    tier_start,
    tier_end
  }))

  const rows = channelPriceSummaryRows(items)

  assert.deepEqual(
    rows.map((item) => item.label),
    [
      '[0, 32,000) Input',
      '[0, 32,000) Output',
      '[0, 32,000) Cache',
      '[32,000, 96,000) Input',
      '[32,000, 96,000) Output',
      '[32,000, 96,000) Cache'
    ]
  )
  assert.equal(channelPriceItemLabel(items[3]), '[32,000, 96,000) Input')
})

test('groups channel prices by usage tier for side-by-side display', () => {
  const items = [
    ['text_input', '3', '0', '32000'],
    ['text_output', '14', '0', '32000'],
    ['cache_input', '0.3', '0', '32000'],
    ['text_input', '4', '32000', null],
    ['text_output', '16', '32000', null],
    ['cache_input', '0.4', '32000', null]
  ].map(([dimension, unit_price, tier_start, tier_end]) => ({
    dimension,
    unit_price,
    currency: 'CNY',
    tier_type: 'usage_range',
    tier_start,
    tier_end
  }))

  assert.deepEqual(channelPriceTierRows(items), [
    {
      prices: [
        { currency: 'CNY', label: 'Input', value: '3' },
        { currency: 'CNY', label: 'Output', value: '14' },
        { currency: 'CNY', label: 'Cache', value: '0.3' }
      ],
      rangeLabel: '[0, 32,000)'
    },
    {
      prices: [
        { currency: 'CNY', label: 'Input', value: '4' },
        { currency: 'CNY', label: 'Output', value: '16' },
        { currency: 'CNY', label: 'Cache', value: '0.4' }
      ],
      rangeLabel: '[32,000, ∞)'
    }
  ])
})

test('keeps peak and off-peak channel prices in separate rows', () => {
  const items = [
    ['peak', '忙时', 'text_input', '3'],
    ['peak', '忙时', 'text_output', '9'],
    ['off_peak', '闲时', 'text_input', '1.5'],
    ['off_peak', '闲时', 'text_output', '4.5']
  ].map(([code, label, dimension, unit_price]) => ({
    dimension,
    unit_price,
    currency: 'CNY',
    tier_type: 'flat',
    spec: {
      access_region: 'cn-beijing',
      deployment_scope: 'china_mainland',
      pricing_condition: {
        type: 'provider_schedule',
        code,
        label,
        timezone: 'Asia/Shanghai'
      }
    }
  }))

  const rows = channelPriceTierRows(items)

  assert.equal(rows.length, 2)
  assert.deepEqual(
    rows.map((row) => row.rangeLabel),
    ['忙时 · cn-beijing · china_mainland', '闲时 · cn-beijing · china_mainland']
  )
})

test('renders configured channel prices as grouped tier comparisons', () => {
  assert.match(channelModelDrawerSource, /price-tier-list/)
  assert.match(channelModelDrawerSource, /priceTierComparisonRows\(row\)/)
  assert.match(channelModelDrawerSource, /price-tier-values/)
})

test('shows final point values for every resale tier price', () => {
  assert.match(resaleTierEditorSource, /:point-label="pointLabel"/)
  assert.match(resaleTierCardSource, /tiers\.finalPoint/)
  assert.match(resaleTierCardSource, /pointLabel\(card\.prices/)
  assert.match(resaleWorkspaceSource, /:point-label="formatCredit"/)
})
