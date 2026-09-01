import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { userFacingApiError } from '../src/utils/llmOpsErrors.js'
import {
  dataGroupsForChannelModelManagement,
  dataGroupsForResalePublishing,
  dataGroupsForSection,
  toolbarForSection
} from '../src/utils/llmOpsSectionData.js'
import {
  normalizeResalePriceDraft,
  resalePriceItemsForListing,
  resalePriceItemsMatch,
  resaleTierDraftRangesMatch,
  resaleTierDraftFromItems
} from '../src/utils/resaleTierDraft.js'

const globalConfigSource = readFileSync(
  new URL('../src/components/llm-ops/GlobalConfigPanel.vue', import.meta.url),
  'utf8'
)
const llmOpsPageSource = readFileSync(
  new URL('../src/pages/LLMOps.vue', import.meta.url),
  'utf8'
)
const llmOpsHeaderSource = readFileSync(
  new URL('../src/components/llm-ops/LLMOpsHeader.vue', import.meta.url),
  'utf8'
)
const modelWorkbenchSource = readFileSync(
  new URL('../src/components/llm-ops/ModelWorkbenchPanel.vue', import.meta.url),
  'utf8'
)
const listingBoardSource = readFileSync(
  new URL(
    '../src/components/llm-ops/AgioneListingStatusBoard.vue',
    import.meta.url
  ),
  'utf8'
)
const metaModelManagementSource = readFileSync(
  new URL('../src/components/llm-ops/MetaModelManagement.vue', import.meta.url),
  'utf8'
)
const operationErrorSources = [
  '../src/components/llm-ops/AgioneListingStatusBoard.vue',
  '../src/components/llm-ops/ChannelManagement.vue',
  '../src/components/llm-ops/ManualPriceEntryModal.vue',
  '../src/components/llm-ops/PriceSourceModal.vue',
  '../src/components/llm-ops/ResalePublishingDrawer.vue',
  '../src/components/llm-ops/ResaleWorkflowConfigPanel.vue',
  '../src/composables/useLLMOpsResalePublishing.js'
].map((path) => readFileSync(new URL(path, import.meta.url), 'utf8'))
const reconciliationSource = readFileSync(
  new URL('../src/components/llm-ops/ReconciliationPanel.vue', import.meta.url),
  'utf8'
)
const resalePublishingSource = readFileSync(
  new URL('../src/composables/useLLMOpsResalePublishing.js', import.meta.url),
  'utf8'
)
const llmOpsDataSource = readFileSync(
  new URL('../src/composables/useLLMOpsData.js', import.meta.url),
  'utf8'
)
const resaleWorkspaceSource = readFileSync(
  new URL(
    '../src/components/llm-ops/ResalePublishingWorkspace.vue',
    import.meta.url
  ),
  'utf8'
)

test('replaces server and HTML errors with a safe page message', () => {
  const htmlError = {
    response: {
      status: 502,
      data: '<html><title>502 Bad Gateway</title></html>'
    },
    message: 'Request failed with status code 502'
  }

  assert.equal(
    userFacingApiError(htmlError, '当前页面暂时不可用'),
    '当前页面暂时不可用'
  )
})

test('keeps concise validation messages returned by the API', () => {
  const validationError = {
    response: {
      status: 400,
      data: { detail: '执行周期不能为空' }
    }
  }

  assert.equal(
    userFacingApiError(validationError, '保存失败'),
    '执行周期不能为空'
  )
})

test('loads only the data groups required by each section', () => {
  assert.deepEqual(dataGroupsForSection('taskLogs'), ['sources', 'runs'])
  assert.deepEqual(dataGroupsForSection('globalConfig'), ['sources'])
  assert.deepEqual(dataGroupsForSection('audit'), ['channels'])
  assert.ok(dataGroupsForSection('modelWorkbench').includes('modelPrices'))
  assert.ok(dataGroupsForSection('modelWorkbench').includes('records'))
  assert.ok(!dataGroupsForSection('taskLogs').includes('summary'))
  assert.ok(!dataGroupsForSection('audit').includes('models'))
  assert.deepEqual(dataGroupsForSection('reseller'), [
    'platforms',
    'providers',
    'models',
    'listings',
    'summary'
  ])
})

test('loads publishing-only data when the resale workspace opens', () => {
  assert.deepEqual(dataGroupsForResalePublishing(), [
    'metaModels',
    'channels',
    'channelPricing',
    'modelPrices',
    'listings'
  ])
})

test('loads channel model details only when model management opens', () => {
  assert.deepEqual(dataGroupsForSection('channels'), ['channels'])
  assert.deepEqual(dataGroupsForChannelModelManagement(), [
    'providers',
    'metaModels',
    'models',
    'channelPricing',
    'modelPrices'
  ])
  assert.match(
    llmOpsPageSource,
    /:prepare-model-management="preloadChannelModelData"/
  )
  assert.match(
    llmOpsDataSource,
    /if \(group === 'channelPricing'\) return true/
  )
  const refreshChannelBlock = llmOpsDataSource.match(
    /async function refreshChannelManagementData\(\)[\s\S]*?\n[ ]{2}}/
  )?.[0]
  assert.ok(refreshChannelBlock)
  assert.doesNotMatch(refreshChannelBlock, /refreshChannelPricingData/)
  assert.doesNotMatch(refreshChannelBlock, /refreshResaleListings/)
})

test('does not pass unused model price items to the listing status board', () => {
  const boardUsage = llmOpsPageSource.match(
    /<AgioneListingStatusBoard[\s\S]*?\/>/
  )?.[0]

  assert.ok(boardUsage)
  assert.doesNotMatch(boardUsage, /:price-items=/)
  assert.doesNotMatch(listingBoardSource, /\bpriceItems\b/)
  assert.doesNotMatch(listingBoardSource, /\bpriceItemsRef\b/)
})

test('shows page toolbar controls only where they are meaningful', () => {
  assert.deepEqual(toolbarForSection('taskLogs'), {
    currency: false,
    refresh: false
  })
  assert.deepEqual(toolbarForSection('globalConfig'), {
    currency: false,
    refresh: false
  })
  assert.deepEqual(toolbarForSection('modelWorkbench'), {
    currency: true,
    refresh: true
  })
})

test('renders a persistent page error instead of business zero values', () => {
  assert.match(llmOpsPageSource, /<LLMOpsErrorState/)
  assert.match(llmOpsPageSource, /v-else-if="pageError"/)
  assert.match(
    llmOpsPageSource,
    /:actions-disabled="Boolean\(pageError\) \|\| loading"/
  )
})

test('keeps global configuration unavailable until a load succeeds', () => {
  assert.match(globalConfigSource, /v-else-if="configLoadError"/)
  assert.match(globalConfigSource, /v-else-if="config"/)
  assert.match(
    globalConfigSource,
    /:disabled="loading \|\| saving \|\| !config"/
  )
})

test('uses a guided empty state when no workbench models exist', () => {
  assert.match(modelWorkbenchSource, /v-if="!modelOptions\.length"/)
  assert.match(
    modelWorkbenchSource,
    /llmOps\.modelWorkbenchPanel\.emptyModelsTitle/
  )
})

test('disambiguates same-name models by provider and price source', () => {
  assert.match(modelWorkbenchSource, /source_name: modelRecord\?\.source_name/)
  assert.match(modelWorkbenchSource, /model\.source_name/)
})

test('requests meta-model drawer rows by release date descending', () => {
  assert.match(metaModelManagementSource, /ordering:\s*'-release_date'/)
})

test('reads meta-model sync stats from the unified API payload', () => {
  assert.match(
    metaModelManagementSource,
    /const stats = paginationPayload\(response\)/
  )
})

test('sanitizes operation errors before showing them to users', () => {
  operationErrorSources.forEach((source) => {
    assert.doesNotMatch(source, /error\?\.response\?\.data\?\.detail/)
    assert.doesNotMatch(source, /showError\(error\?\.message/)
    assert.match(source, /userFacingApiError|errorMessage/)
  })
})

test('uses a recognizable create icon in the reconciliation action', () => {
  assert.doesNotMatch(reconciliationSource, /class="icon-mark"/)
  assert.match(reconciliationSource, /d="M12 5v14M5 12h14"/)
})

test('refreshes platform-bound data in every platform-aware section', () => {
  const platformSections = [
    'channelMatrix',
    'listingRisk',
    'modelWorkbench',
    'monitor',
    'priceChanges',
    'reseller'
  ]

  platformSections.forEach((section) => {
    assert.ok(dataGroupsForSection(section).includes('platforms'))
    assert.match(llmOpsHeaderSource, new RegExp(`'${section}'`))
  })
  assert.match(
    resalePublishingSource,
    /'channelMatrix',[\s\S]*'listingRisk',[\s\S]*'modelWorkbench',[\s\S]*'monitor',[\s\S]*'priceChanges',[\s\S]*'reseller'/
  )
  assert.match(
    resalePublishingSource,
    /refreshResalePlatformSelection\(activeSection\.value\)/
  )
})

test('keeps the persisted platform until platform options have loaded', () => {
  assert.match(resalePublishingSource, /if \(!platforms\.length\) return/)
  assert.match(
    llmOpsDataSource,
    /const selectedResalePlatformId = ref\([\s\S]*readStorage\('llm_ops_resale_platform'\)/
  )
})

test('keeps workspace saves successful when the follow-up refresh fails', () => {
  assert.match(
    resalePublishingSource,
    /async function refreshAfterResaleSave\(\)[\s\S]*await refreshLight\(\)[\s\S]*catch \(error\)/
  )
  assert.equal(
    resalePublishingSource.match(/await refreshAfterResaleSave\(\)/g)?.length,
    2
  )
})

test('compares flat listing edits against flat prices', () => {
  assert.match(
    resaleWorkspaceSource,
    /savedDraft && hasTieredResalePrices\(savedDraft\)/
  )
})

test('uses an in-page confirmation dialog for listing actions', () => {
  assert.doesNotMatch(listingBoardSource, /\b(?:window\.)?confirm\s*\(/)
  assert.match(listingBoardSource, /LLMOpsConfirmDialog/)
  assert.match(listingBoardSource, /askConfirmation\(/)
})

test('keeps tier ranges readable in the listing table', () => {
  assert.match(listingBoardSource, /metric-tier-range-list/)
  assert.match(listingBoardSource, /metric\.tierPrices\?\.length/)
  assert.match(listingBoardSource, /metric\.tierPoints\?\.length/)
  assert.match(
    listingBoardSource,
    /v-for="tier in metric\.tierPrices \|\| \[\]"/
  )
  assert.match(
    listingBoardSource,
    /v-for="tier in metric\.tierPoints \|\| \[\]"/
  )
  assert.match(listingBoardSource, /tier\.price/)
  assert.doesNotMatch(listingBoardSource, /metric\.shape/)
})

test('manual and resale price entry compose the same tier editor', () => {
  const manualSource = readFileSync(
    new URL(
      '../src/components/llm-ops/ManualPriceEntryModal.vue',
      import.meta.url
    ),
    'utf8'
  )
  const resaleSource = readFileSync(
    new URL('../src/components/llm-ops/ResaleTierEditor.vue', import.meta.url),
    'utf8'
  )

  assert.match(manualSource, /<TierPriceEditor/)
  assert.match(resaleSource, /<TierPriceEditor/)
  assert.match(manualSource, /buildManualPriceItems/)
  assert.doesNotMatch(manualSource, /<ResaleTierCard/)
  assert.doesNotMatch(resaleSource, /<ResaleTierCard/)
})

test('restores saved resale tiers from the active listing revision', () => {
  const items = [
    {
      billing_unit: 'per_1m_tokens',
      currency: 'CNY',
      dimension: 'text_input',
      tier_end: '1000000.000000',
      tier_start: '0.000000',
      tier_type: 'usage_range',
      unit_price: '3.46'
    },
    {
      billing_unit: 'per_1m_tokens',
      currency: 'CNY',
      dimension: 'text_input',
      tier_end: null,
      tier_start: '1000000.000000',
      tier_type: 'usage_range',
      unit_price: '3.20'
    }
  ]
  const listing = {
    current_price_items: [],
    pending_price_items: items
  }

  const draft = resaleTierDraftFromItems(resalePriceItemsForListing(listing))

  assert.equal(draft.input.length, 2)
  assert.equal(
    resalePriceItemsMatch(normalizeResalePriceDraft(draft, 'CNY'), items),
    true
  )
})

test('keeps downstream ranges controlled by the upstream price shape', () => {
  const upstreamItems = [
    {
      dimension: 'text_input',
      tier_end: '1000000',
      tier_start: '0',
      tier_type: 'usage_range',
      unit_price: '1'
    },
    {
      dimension: 'text_input',
      tier_end: null,
      tier_start: '1000000',
      tier_type: 'usage_range',
      unit_price: '0.8'
    },
    {
      dimension: 'text_output',
      tier_end: null,
      tier_start: null,
      tier_type: 'flat',
      unit_price: '2'
    }
  ]
  const upstreamDraft = resaleTierDraftFromItems(upstreamItems)
  const savedDraft = {
    ...upstreamDraft,
    input: upstreamDraft.input.map((row, index) => ({
      ...row,
      price: index ? '3.2' : '3.46'
    }))
  }
  const changedBoundaryDraft = {
    ...savedDraft,
    input: [
      { ...savedDraft.input[0], end: '900000' },
      { ...savedDraft.input[1], start: '900000' }
    ]
  }

  assert.equal(resaleTierDraftRangesMatch(savedDraft, upstreamDraft), true)
  assert.equal(
    resaleTierDraftRangesMatch(changedBoundaryDraft, upstreamDraft),
    false
  )
})
