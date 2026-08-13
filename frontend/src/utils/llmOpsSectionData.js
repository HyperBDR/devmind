const SECTION_DATA_GROUPS = {
  audit: ['channels'],
  channelMatrix: ['channels', 'summary'],
  channels: ['channels'],
  collectionHealth: ['sources', 'runs'],
  globalConfig: ['sources'],
  listingRisk: ['summary'],
  metaModels: ['providers'],
  modelWorkbench: [
    'models',
    'channels',
    'modelPrices',
    'channelPricing',
    'listings',
    'records',
    'summary'
  ],
  monitor: ['platforms', 'summary'],
  priceChanges: ['modelPrices', 'priceHistory'],
  providers: ['sources', 'runs', 'providers'],
  reconciler: ['channels', 'models', 'records'],
  reseller: ['platforms', 'providers', 'models', 'listings', 'summary'],
  taskLogs: ['sources', 'runs'],
  workflow: ['platforms']
}

const CURRENCY_SECTIONS = new Set([
  'channelMatrix',
  'channels',
  'listingRisk',
  'modelWorkbench',
  'monitor',
  'providers',
  'reseller'
])

const GLOBAL_REFRESH_SECTIONS = new Set([
  'channelMatrix',
  'channels',
  'collectionHealth',
  'listingRisk',
  'modelWorkbench',
  'monitor',
  'priceChanges',
  'reconciler',
  'reseller'
])

const RESALE_PUBLISHING_DATA_GROUPS = [
  'metaModels',
  'channels',
  'channelPricing',
  'modelPrices',
  'listings'
]

const CHANNEL_MODEL_DATA_GROUPS = [
  'providers',
  'metaModels',
  'models',
  'channelPricing',
  'modelPrices'
]

export function dataGroupsForResalePublishing() {
  return [...RESALE_PUBLISHING_DATA_GROUPS]
}

export function dataGroupsForChannelModelManagement() {
  return [...CHANNEL_MODEL_DATA_GROUPS]
}

export function dataGroupsForSection(section) {
  return [...(SECTION_DATA_GROUPS[section] || [])]
}

export function toolbarForSection(section) {
  return {
    currency: CURRENCY_SECTIONS.has(section),
    refresh: GLOBAL_REFRESH_SECTIONS.has(section)
  }
}
