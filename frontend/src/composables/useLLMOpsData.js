import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import {
  asArray,
  asObject,
  errorMessage,
  extract,
  fetchFirstPage,
  fetchList
} from '@/utils/llmOpsPagination'
import {
  dataGroupsForChannelModelManagement,
  dataGroupsForResalePublishing,
  dataGroupsForSection
} from '@/utils/llmOpsSectionData'
import { userFacingApiError } from '@/utils/llmOpsErrors'

const PRICE_HISTORY_PAGE_SIZE = 120
const RUN_LOG_PAGE_SIZE = 120
const RECONCILIATION_PAGE_SIZE = 120
const supportedDisplayCurrencies = new Set(['CNY', 'USD'])

export function useLLMOpsData() {
  const { t } = useI18n()
  const { showError } = useToast()
  const loading = ref(false)
  const pageError = ref('')
  const loadedSections = new Set()
  const inFlightGroups = new Map()
  let resaleListingsRequestId = 0
  let priceHistoryRequestId = 0
  let summaryRequestId = 0

  const sources = ref([])
  const collectionRuns = ref([])
  const providers = ref([])
  const metaModels = ref([])
  const models = ref([])
  const channels = ref([])
  const channelOfferings = ref([])
  const channelPrices = ref([])
  const channelPriceItems = ref([])
  const channelPriceHistory = ref([])
  const channelPriceVersions = ref([])
  const modelPriceItems = ref([])
  const officialPriceHistory = ref([])
  const resalePlatforms = ref([])
  const resaleWorkflowConfig = ref(null)
  const listings = ref([])
  const listingPriceHistory = ref([])
  const records = ref([])
  const summary = ref({})
  const displayCurrency = ref(
    normalizeDisplayCurrency(readStorage('llm_ops_display_currency'))
  )
  const selectedResalePlatformId = ref(
    readStorage('llm_ops_resale_platform') || ''
  )

  const providerCollectionSources = computed(() =>
    asArray(sources.value).filter((item) => item.source_type !== 'agione')
  )

  const procurementRows = computed(() => asArray(summary.value.procurement))
  const exchangeRate = computed(() =>
    Number(summary.value.currency?.usd_to_cny_rate || 7.15)
  )
  const summaryDisplayCurrency = computed(() =>
    normalizeDisplayCurrency(
      summary.value.currency?.display_currency || displayCurrency.value
    )
  )
  const exchangeRateLabel = computed(() => {
    const currency = summary.value.currency
    if (!currency) return ''
    const rate = Number(currency.usd_to_cny_rate || 0).toFixed(4)
    return `1 USD = ${rate} CNY`
  })
  const pointConversion = computed(() => summary.value.point_conversion || null)

  async function refreshAll(section, options = {}) {
    const force = options.force !== false
    if (!force && loadedSections.has(section)) {
      pageError.value = ''
      return true
    }

    loading.value = true
    pageError.value = ''
    try {
      await refreshSectionData(section, options)
      loadedSections.add(section)
      return true
    } catch (error) {
      loadedSections.delete(section)
      pageError.value = userFacingApiError(
        error,
        t('llmOps.dataErrors.loadSection')
      )
      return false
    } finally {
      loading.value = false
    }
  }

  async function refreshSectionData(section, options = {}) {
    const groups = dataGroupsForSection(section)
    if (groups.includes('platforms')) {
      await loadDataGroup('platforms', section, options)
    }
    await Promise.all(
      groups
        .filter((group) => group !== 'platforms')
        .map((group) => loadDataGroup(group, section, options))
    )
  }

  async function loadDataGroup(group, section, options) {
    const requestKey = [
      group,
      options?.modelId || '',
      options?.platformId || ''
    ].join(':')
    const existingRequest = inFlightGroups.get(requestKey)
    if (existingRequest) return existingRequest
    const request = loadDataGroupInternal(group, section, options)
    inFlightGroups.set(requestKey, request)
    try {
      return await request
    } finally {
      if (inFlightGroups.get(requestKey) === request) {
        inFlightGroups.delete(requestKey)
      }
    }
  }

  async function loadDataGroupInternal(group, section, options) {
    if (group === 'sources') {
      sources.value = asArray(await fetchList(llmOpsApi.listCollectionSources))
      return
    }
    if (group === 'runs') {
      collectionRuns.value = asArray(await fetchRecentCollectionRuns())
      return
    }
    if (group === 'providers') {
      providers.value = asArray(await fetchList(llmOpsApi.listProviders))
      return
    }
    if (group === 'metaModels') {
      metaModels.value = asArray(await fetchList(llmOpsApi.listMetaModels))
      return
    }
    if (group === 'models') {
      models.value = asArray(await fetchList(llmOpsApi.listModels))
      return
    }
    if (group === 'channels') {
      channels.value = asArray(await fetchList(llmOpsApi.listChannels))
      return
    }
    if (group === 'platforms') {
      resalePlatforms.value = asArray(
        await fetchList(llmOpsApi.listResalePlatforms)
      )
      ensureSelectedResalePlatform()
      await loadResaleWorkflowConfig()
      return
    }
    if (group === 'channelPricing') {
      await refreshChannelPricingData()
      return
    }
    if (group === 'modelPrices') {
      await refreshModelPriceItems()
      return
    }
    if (group === 'listings') {
      await refreshResaleListings()
      return
    }
    if (group === 'records') {
      await refreshReconciliationRecords()
      return
    }
    if (group === 'priceHistory') {
      await refreshPriceHistoryData(options.modelId)
      return
    }
    if (group === 'summary') {
      await refreshSummary(section === 'monitor' ? 'monitor' : 'full')
    }
  }

  async function refreshChannelPricingData() {
    const [offerings, prices, items] = await Promise.all([
      fetchList(llmOpsApi.listChannelOfferings),
      fetchList(llmOpsApi.listChannelModelPrices),
      fetchList(llmOpsApi.listChannelPriceItems, { is_effective: 'true' })
    ])
    channelOfferings.value = asArray(offerings)
    channelPrices.value = asArray(prices)
    channelPriceItems.value = asArray(items)
  }

  async function refreshModelPriceItems() {
    const items = await fetchList(llmOpsApi.listModelPriceItems, {
      is_current: 'true'
    })
    modelPriceItems.value = asArray(items)
  }

  async function refreshResaleListings(
    platformId = selectedResalePlatformId.value
  ) {
    const requestId = ++resaleListingsRequestId
    const params = platformId ? { platform: platformId } : {}
    const nextListings = asArray(
      await fetchList(llmOpsApi.listResaleListings, params)
    )
    if (
      requestId !== resaleListingsRequestId ||
      String(platformId || '') !== String(selectedResalePlatformId.value || '')
    ) {
      return
    }
    listings.value = nextListings
  }

  async function refreshResalePlatformSelection(section) {
    const platformSections = [
      'channelMatrix',
      'listingRisk',
      'modelWorkbench',
      'monitor',
      'priceChanges',
      'reseller'
    ]
    platformSections.forEach((sectionKey) => loadedSections.delete(sectionKey))
    if (section === 'monitor') {
      await refreshSummary('monitor')
      return
    }
    if (section === 'priceChanges') {
      await refreshPriceHistoryData()
      return
    }
    await Promise.all([refreshResaleListings(), refreshSummary()])
  }

  function preloadResalePublishingData() {
    const groupValues = {
      channels,
      listings,
      metaModels,
      modelPrices: modelPriceItems
    }
    const tasks = dataGroupsForResalePublishing()
      .filter((group) => {
        if (group === 'channelPricing') {
          return (
            !asArray(channelPrices.value).length ||
            !asArray(channelPriceItems.value).length ||
            !asArray(channelOfferings.value).length
          )
        }
        return !asArray(groupValues[group]?.value).length
      })
      .map((group) => loadDataGroup(group, 'reseller', {}))

    return Promise.all(tasks).catch((error) => {
      showError(errorMessage(error, t('llmOps.dataErrors.loadPublishing')))
    })
  }

  function preloadChannelModelData() {
    const groupValues = {
      metaModels,
      modelPrices: modelPriceItems,
      models,
      providers
    }
    const tasks = dataGroupsForChannelModelManagement()
      .filter((group) => {
        if (group === 'channelPricing') return true
        return !asArray(groupValues[group]?.value).length
      })
      .map((group) => loadDataGroup(group, 'channels', {}))

    return Promise.all(tasks)
  }

  async function refreshReconciliationRecords() {
    records.value = asArray(
      await fetchFirstPage(llmOpsApi.listReconciliationRecords, {
        page_size: RECONCILIATION_PAGE_SIZE
      })
    )
  }

  async function refreshPriceHistoryData(modelId = null) {
    const requestId = ++priceHistoryRequestId
    const model = Number(modelId)
    const modelFilter = Number.isInteger(model) && model > 0 ? { model } : {}
    const platformFilter = selectedResalePlatformId.value
      ? { platform: selectedResalePlatformId.value }
      : {}
    const platformId = selectedResalePlatformId.value
    const [
      channelHistoryData,
      listingHistoryData,
      officialHistoryData,
      channelVersionData
    ] = await Promise.all([
      fetchFirstPage(llmOpsApi.listChannelModelPriceHistory, {
        ...modelFilter,
        page_size: PRICE_HISTORY_PAGE_SIZE
      }),
      fetchFirstPage(llmOpsApi.listResaleListingPriceHistory, {
        ...modelFilter,
        ...platformFilter,
        page_size: PRICE_HISTORY_PAGE_SIZE
      }),
      fetchFirstPage(llmOpsApi.listCollectedPriceHistory, {
        ...modelFilter,
        page_size: PRICE_HISTORY_PAGE_SIZE
      }),
      fetchFirstPage(llmOpsApi.listChannelPriceVersions, {
        ...modelFilter,
        page_size: PRICE_HISTORY_PAGE_SIZE
      })
    ])
    if (
      requestId !== priceHistoryRequestId ||
      String(platformId || '') !== String(selectedResalePlatformId.value || '')
    ) {
      return
    }
    channelPriceHistory.value = asArray(channelHistoryData)
    listingPriceHistory.value = asArray(listingHistoryData)
    officialPriceHistory.value = asArray(officialHistoryData)
    channelPriceVersions.value = asArray(channelVersionData)
  }

  async function refreshLight() {
    const [prices, channelPriceItemsData, listingData, recordData, summaryRes] =
      await Promise.all([
        fetchList(llmOpsApi.listChannelModelPrices),
        fetchList(llmOpsApi.listChannelPriceItems, {
          is_current: 'true'
        }),
        fetchList(
          llmOpsApi.listResaleListings,
          selectedResalePlatformId.value
            ? { platform: selectedResalePlatformId.value }
            : {}
        ),
        fetchFirstPage(llmOpsApi.listReconciliationRecords, {
          page_size: RECONCILIATION_PAGE_SIZE
        }),
        llmOpsApi.getSummary(summaryParams())
      ])
    channelPrices.value = asArray(prices)
    channelPriceItems.value = asArray(channelPriceItemsData)
    listings.value = asArray(listingData)
    records.value = asArray(recordData)
    summary.value = normalizeSummary(extract(summaryRes))
  }

  async function refreshCollectionRuns() {
    const [sourceData, runData] = await Promise.all([
      fetchList(llmOpsApi.listCollectionSources),
      fetchRecentCollectionRuns()
    ])
    sources.value = sourceData
    collectionRuns.value = runData
  }

  async function refreshProviderManagementData() {
    try {
      const [sourceData, runData, providerData] = await Promise.all([
        fetchList(llmOpsApi.listCollectionSources),
        fetchRecentCollectionRuns(),
        fetchList(llmOpsApi.listProviders)
      ])
      sources.value = asArray(sourceData)
      collectionRuns.value = asArray(runData)
      providers.value = asArray(providerData)
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshProviders')))
    }
  }

  async function refreshMetaModelManagementData() {
    try {
      const [providerData, metaModelData] = await Promise.all([
        fetchList(llmOpsApi.listProviders),
        fetchList(llmOpsApi.listMetaModels)
      ])
      providers.value = asArray(providerData)
      metaModels.value = asArray(metaModelData)
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshMetaModels')))
    }
  }

  async function refreshChannelManagementData() {
    try {
      const channelData = await fetchList(llmOpsApi.listChannels)
      channels.value = asArray(channelData)
      loadedSections.clear()
      loadedSections.add('channels')
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshChannels')))
    }
  }

  async function refreshPlatformData() {
    try {
      resalePlatforms.value = asArray(
        await fetchList(llmOpsApi.listResalePlatforms)
      )
      ensureSelectedResalePlatform()
      await Promise.all([refreshResaleListings(), refreshSummary()])
      await loadResaleWorkflowConfig()
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshPlatforms')))
    }
  }

  async function loadResaleWorkflowConfig(
    platformId = selectedResalePlatformId.value
  ) {
    if (!platformId) {
      resaleWorkflowConfig.value = null
      return
    }
    try {
      const response = await llmOpsApi.getResaleWorkflowConfig(platformId)
      if (String(platformId) === String(selectedResalePlatformId.value)) {
        resaleWorkflowConfig.value = response.data?.data || response.data
      }
    } catch {
      resaleWorkflowConfig.value = null
    }
  }

  async function refreshSummary(scope = 'full') {
    const requestId = ++summaryRequestId
    const platformId = selectedResalePlatformId.value
    const summaryRes = await llmOpsApi.getSummary(summaryParams(scope))
    if (
      requestId !== summaryRequestId ||
      String(platformId || '') !== String(selectedResalePlatformId.value || '')
    ) {
      return
    }
    summary.value = normalizeSummary(extract(summaryRes))
  }

  async function fetchRecentCollectionRuns() {
    return fetchFirstPage(llmOpsApi.listCollectionRuns, {
      page_size: RUN_LOG_PAGE_SIZE
    })
  }

  function summaryParams(scope = 'full') {
    return {
      display_currency: displayCurrency.value,
      resale_platform: selectedResalePlatformId.value || '',
      scope
    }
  }

  function ensureSelectedResalePlatform() {
    const platforms = asArray(resalePlatforms.value).filter(
      (platform) => platform.is_active !== false
    )
    if (!platforms.length) {
      selectedResalePlatformId.value = ''
      return
    }
    const exists = platforms.some(
      (platform) =>
        String(platform.id) === String(selectedResalePlatformId.value || '')
    )
    if (exists) return
    const fallback =
      platforms.find((platform) => platform.code === 'agione') || platforms[0]
    selectedResalePlatformId.value = String(fallback.id)
  }

  function invalidateSectionCache() {
    loadedSections.clear()
  }

  return {
    channelOfferings,
    channelPriceHistory,
    channelPriceVersions,
    channelPriceItems,
    channelPrices,
    channels,
    collectionRuns,
    displayCurrency,
    exchangeRate,
    exchangeRateLabel,
    listingPriceHistory,
    listings,
    loadResaleWorkflowConfig,
    loading,
    metaModels,
    modelPriceItems,
    officialPriceHistory,
    models,
    invalidateSectionCache,
    normalizeDisplayCurrency,
    pageError,
    pointConversion,
    preloadChannelModelData,
    preloadResalePublishingData,
    procurementRows,
    providerCollectionSources,
    providers,
    records,
    refreshAll,
    refreshChannelPricingData,
    refreshChannelManagementData,
    refreshCollectionRuns,
    refreshLight,
    refreshMetaModelManagementData,
    refreshPlatformData,
    refreshProviderManagementData,
    refreshResalePlatformSelection,
    refreshSectionData,
    refreshSummary,
    resalePlatforms,
    resaleWorkflowConfig,
    selectedResalePlatformId,
    sources,
    summary,
    summaryDisplayCurrency
  }
}

function normalizeDisplayCurrency(value) {
  const currency = String(value || '')
    .trim()
    .toUpperCase()
  return supportedDisplayCurrencies.has(currency) ? currency : 'CNY'
}

function readStorage(key) {
  if (typeof localStorage === 'undefined') return ''
  return localStorage.getItem(key) || ''
}

function normalizeSummary(value) {
  const summary = asObject(value)
  const agione = asObject(summary.agione)
  return {
    ...summary,
    agione: {
      ...agione,
      diagnostic_counts: asObject(agione.diagnostic_counts),
      diagnostics: asArray(agione.diagnostics)
    },
    currency: asObject(summary.currency),
    kpis: asObject(summary.kpis),
    listings: asArray(summary.listings),
    procurement: asArray(summary.procurement),
    status_counts: asObject(summary.status_counts)
  }
}
