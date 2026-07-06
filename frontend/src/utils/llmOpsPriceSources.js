const DEFAULT_CATEGORY_LABELS = {
  official_provider: '原厂',
  cloud_hosted: '云托管',
  supplier: '供货商',
  manual: '内部维护',
  unknown: '其他'
}

const CATEGORY_TONES = {
  official_provider: 'official',
  cloud_hosted: 'cloud',
  supplier: 'supplier',
  manual: 'manual',
  unknown: 'unknown'
}

const CATEGORY_RANKS = {
  official_provider: 1,
  cloud_hosted: 2,
  supplier: 3,
  manual: 4,
  unknown: 5
}

const OWNER_TYPE_LABELS = {
  model_provider_official: '模型厂商官方',
  cloud_provider_official: '云厂商官方',
  supplier: '供应商',
  internal: '内部维护',
  unknown: '未知'
}

const COLLECTION_METHOD_LABELS = {
  auto_collect: '自动采集',
  api_sync: '接口同步',
  manual_entry: '手动录入',
  manual_import: '手动导入',
  unknown: '待配置'
}

const COLLECTION_GROUP_RANKS = {
  auto: 1,
  manual: 2,
  unknown: 3
}

export function normalizePriceSourceCategory(item, model = {}, source = null) {
  return (
    item?.business_source_category ||
    item?.price_role ||
    model?.business_source_category ||
    model?.price_role ||
    source?.business_source_category ||
    item?.source_category ||
    model?.source_category ||
    source?.source_category ||
    'unknown'
  )
}

export function priceSourceOwnerType(source) {
  const ownerType = source?.source_owner_type
  if (ownerType && ownerType !== 'unknown') return ownerType

  const category = source?.source_category || source?.business_source_category
  if (category === 'supplier') return 'supplier'
  if (category === 'manual') return 'internal'
  if (category === 'cloud_hosted') return 'cloud_provider_official'
  if (category === 'official_provider') return 'model_provider_official'
  return ownerType || 'unknown'
}

export function priceSourceOwnerTypeLabel(ownerType, labels = {}) {
  const key = ownerType || 'unknown'
  return (
    labels[key] ||
    OWNER_TYPE_LABELS[key] ||
    labels.unknown ||
    OWNER_TYPE_LABELS.unknown
  )
}

export function priceSourceCategoryLabel(category, labels = {}) {
  const key = category || 'unknown'
  return (
    labels[key] ||
    DEFAULT_CATEGORY_LABELS[key] ||
    labels.unknown ||
    DEFAULT_CATEGORY_LABELS.unknown
  )
}

export function priceSourceTone(category) {
  return CATEGORY_TONES[category || 'unknown'] || CATEGORY_TONES.unknown
}

export function priceSourceCategory(category, labels = {}) {
  return {
    label: priceSourceCategoryLabel(category, labels),
    tone: priceSourceTone(category)
  }
}

export function priceSourceCategoryRank(category) {
  return CATEGORY_RANKS[category || 'unknown'] || 9
}

export function comparePriceSources(left, right) {
  const leftRank = priceSourceCategoryRank(normalizePriceSourceCategory(left))
  const rightRank = priceSourceCategoryRank(normalizePriceSourceCategory(right))
  if (leftRank !== rightRank) return leftRank - rightRank
  return String(left?.name || '').localeCompare(String(right?.name || ''))
}

export function priceSourceCollectionMethod(source) {
  const method = source?.collection_method
  if (method && method !== 'unknown') return method

  if (source?.source_type === 'yunce') return 'api_sync'
  if (source?.can_collect_prices && source?.updates_model_prices) {
    return 'auto_collect'
  }
  if (priceSourceOwnerType(source) === 'internal') {
    return 'manual_entry'
  }
  return method || 'unknown'
}

export function priceSourceCollectionMethodLabel(method, labels = {}) {
  const key = method || 'unknown'
  return (
    labels[key] ||
    COLLECTION_METHOD_LABELS[key] ||
    labels.unknown ||
    COLLECTION_METHOD_LABELS.unknown
  )
}

export function priceSourceCollectionGroup(source) {
  const method = priceSourceCollectionMethod(source)
  if (['auto_collect', 'api_sync'].includes(method)) return 'auto'
  if (['manual_entry', 'manual_import'].includes(method)) return 'manual'
  return 'unknown'
}

export function priceSourceCollectionGroupRank(group) {
  return COLLECTION_GROUP_RANKS[group || 'unknown'] || 9
}

export function canCollectPriceSource(source) {
  if (!source) return false
  if (source.can_collect === true) return true
  return Boolean(
    source.can_collect_prices &&
      source.updates_model_prices &&
      priceSourceCollectionMethod(source) === 'auto_collect'
  )
}

export function canApiSyncPriceSource(source) {
  return priceSourceCollectionMethod(source) === 'api_sync'
}

export function canManualEntryPriceSource(source) {
  if (!source) return false
  if (canCollectPriceSource(source)) return false
  if (source.can_manual_entry === true) return true
  if (priceSourceOwnerType(source) === 'internal') return true
  return ['manual_entry', 'manual_import', 'unknown'].includes(
    priceSourceCollectionMethod(source)
  )
}

export function isEntryPriceSource(source) {
  return (
    canCollectPriceSource(source) ||
    canManualEntryPriceSource(source) ||
    canApiSyncPriceSource(source)
  )
}

export function isModelsDevPriceSource(source) {
  return String(source?.endpoint_url || '')
    .toLowerCase()
    .includes('models.dev/api.json')
}

export function officialProviderCodeFromSlug(
  source,
  fallbackProviderCode = ''
) {
  const slug = String(source?.slug || '')
  if (!slug.endsWith('-official')) return ''
  const providerCode = String(fallbackProviderCode || '').trim()
  if (providerCode && slug.startsWith(`${providerCode}-`)) {
    return providerCode
  }
  return ''
}

export function priceSourceGroupKey(source, fallbackProviderCode = '') {
  const providerCode = String(source?.provider_code || '').trim()
  const resolvedProviderCode =
    providerCode ||
    String(fallbackProviderCode || '').trim() ||
    officialProviderCodeFromSlug(source, fallbackProviderCode)

  if (normalizePriceSourceCategory(source) === 'official_provider') {
    return `official:${resolvedProviderCode}`
  }
  return `source:${source?.id || source?.slug || 'unknown'}`
}

export function isLegacyOfficialModelSource(source, fallbackProviderCode = '') {
  if (normalizePriceSourceCategory(source) !== 'official_provider') {
    return false
  }
  const providerCode = String(
    source?.provider_code ||
      fallbackProviderCode ||
      officialProviderCodeFromSlug(source, fallbackProviderCode)
  ).trim()
  if (!providerCode) return false
  const slug = String(source?.slug || '')
  return slug !== `${providerCode}-official` && slug.endsWith('-official')
}

export function isProviderOfficialPriceSource(
  source,
  fallbackProviderCode = ''
) {
  const providerCode = String(source?.provider_code || '').trim()
  const expectedCode = providerCode || String(fallbackProviderCode || '').trim()
  return Boolean(
    expectedCode &&
      normalizePriceSourceCategory(source) === 'official_provider' &&
      String(source?.slug || '') === `${expectedCode}-official`
  )
}

export function preferredPriceSource(sources) {
  return (
    sources.find(
      (source) => normalizePriceSourceCategory(source) === 'official_provider'
    ) ||
    sources.find((source) => String(source.slug || '').endsWith('-official')) ||
    sources.find((source) => source.updates_model_prices) ||
    sources.find((source) => source.endpoint_url) ||
    null
  )
}
