const SECTION_DATA_GROUPS = {
  audit: ['channels'],
  channelMatrix: ['channels', 'summary'],
  channels: [
    'channels',
    'providers',
    'metaModels',
    'models',
    'channelPricing',
    'modelPrices'
  ],
  collectionHealth: ['sources', 'runs'],
  globalConfig: ['sources'],
  listingRisk: ['summary'],
  metaModels: ['providers', 'metaModels', 'models', 'modelPrices'],
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
  providers: [
    'sources',
    'runs',
    'providers',
    'metaModels',
    'models',
    'modelPrices'
  ],
  reconciler: ['channels', 'models', 'records'],
  reseller: [
    'platforms',
    'providers',
    'metaModels',
    'models',
    'channels',
    'channelPricing',
    'modelPrices',
    'listings',
    'summary'
  ],
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

export function dataGroupsForSection(section) {
  return [...(SECTION_DATA_GROUPS[section] || [])]
}

export function toolbarForSection(section) {
  return {
    currency: CURRENCY_SECTIONS.has(section),
    refresh: GLOBAL_REFRESH_SECTIONS.has(section)
  }
}
