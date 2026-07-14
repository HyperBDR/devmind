import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import {
  DATA_HEAVY_SECTIONS,
  LIGHT_CORE_SECTIONS
} from '@/composables/useLLMOpsNavigation'
import {
  asArray,
  asObject,
  errorMessage,
  extract,
  fetchFirstPage,
  fetchList
} from '@/utils/llmOpsPagination'

const PRICE_HISTORY_PAGE_SIZE = 120
const RUN_LOG_PAGE_SIZE = 120
const RECONCILIATION_PAGE_SIZE = 120
const supportedDisplayCurrencies = new Set(['CNY', 'USD'])

export function useLLMOpsData() {
  const { t } = useI18n()
  const { showError } = useToast()
  const loading = ref(false)
  const backgroundLoading = ref(false)
  const secondaryDataLoaded = ref(false)
  const secondaryRefreshQueued = ref(false)

  const sources = ref([])
  const collectionRuns = ref([])
  const providers = ref([])
  const metaModels = ref([])
  const models = ref([])
  const channels = ref([])
  const channelPrices = ref([])
  const channelPriceItems = ref([])
  const channelPriceHistory = ref([])
  const modelPriceItems = ref([])
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

  async function refreshAll(section) {
    loading.value = true
    try {
      await refreshCoreData(section)
      await refreshSectionData(section)
    } finally {
      loading.value = false
    }

    if (DATA_HEAVY_SECTIONS.has(section)) {
      refreshSecondaryData({ force: true, silent: true })
    }
  }

  async function refreshCoreData(section) {
    if (section === 'monitor') {
      const [channelRes, platformRes, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listChannels),
        fetchList(llmOpsApi.listResalePlatforms),
        llmOpsApi.getSummary(summaryParams('monitor'))
      ])
      channels.value = asArray(extract(channelRes))
      resalePlatforms.value = asArray(extract(platformRes))
      summary.value = normalizeSummary(extract(summaryRes))
      await loadResaleWorkflowConfig()
      return
    }

    const shouldLoadModels = !LIGHT_CORE_SECTIONS.has(section)
    const [
      sourceRes,
      runRes,
      providerRes,
      metaModelRes,
      modelRes,
      channelRes,
      platformRes,
      summaryRes
    ] = await Promise.all([
      fetchList(llmOpsApi.listCollectionSources),
      fetchRecentCollectionRuns(),
      fetchList(llmOpsApi.listProviders),
      fetchList(llmOpsApi.listMetaModels),
      shouldLoadModels ? fetchList(llmOpsApi.listModels) : Promise.resolve([]),
      fetchList(llmOpsApi.listChannels),
      fetchList(llmOpsApi.listResalePlatforms),
      llmOpsApi.getSummary(summaryParams())
    ])
    sources.value = asArray(extract(sourceRes))
    collectionRuns.value = asArray(extract(runRes))
    providers.value = asArray(extract(providerRes))
    metaModels.value = asArray(extract(metaModelRes))
    if (shouldLoadModels) {
      models.value = asArray(extract(modelRes))
    }
    channels.value = asArray(extract(channelRes))
    resalePlatforms.value = asArray(extract(platformRes))
    summary.value = normalizeSummary(extract(summaryRes))
    await loadResaleWorkflowConfig()
  }

  async function refreshSecondaryData({ force = false, silent = false } = {}) {
    if (backgroundLoading.value) {
      if (force) {
        secondaryDataLoaded.value = false
        secondaryRefreshQueued.value = true
      }
      return
    }
    if (force) {
      secondaryDataLoaded.value = false
    }
    backgroundLoading.value = true
    try {
      await Promise.all([
        refreshChannelPricingData(),
        refreshResaleListings(),
        refreshReconciliationRecords()
      ])
      secondaryDataLoaded.value = true
    } catch (error) {
      if (!silent) {
        showError(errorMessage(error, t('llmOps.dataErrors.loadSecondary')))
      }
    } finally {
      backgroundLoading.value = false
      if (secondaryRefreshQueued.value) {
        secondaryRefreshQueued.value = false
        refreshSecondaryData({ force: true, silent: true })
      }
    }
  }

  async function refreshSectionData(section) {
    if (!DATA_HEAVY_SECTIONS.has(section)) return
    if (section === 'providers') {
      await refreshProviderManagementData()
      return
    }
    if (section === 'metaModels') {
      await refreshMetaModelManagementData()
      return
    }
    if (section === 'channels') {
      await Promise.all([
        refreshChannelPricingData(),
        refreshModelPriceItems(),
        refreshSummary()
      ])
      return
    }
    if (section === 'channelMatrix') {
      await Promise.all([refreshChannelPricingData(), refreshSummary()])
      return
    }
    if (section === 'reseller' || section === 'listingRisk') {
      await Promise.all([
        refreshChannelPricingData(),
        refreshModelPriceItems(),
        refreshResaleListings(),
        refreshSummary()
      ])
      return
    }
    if (section === 'modelWorkbench') {
      await Promise.all([
        refreshModelPriceItems(),
        refreshChannelPricingData(),
        refreshResaleListings(),
        refreshReconciliationRecords(),
        refreshSummary()
      ])
      return
    }
    if (section === 'priceChanges') {
      await Promise.all([refreshModelPriceItems(), refreshPriceHistoryData()])
      return
    }
    if (section === 'reconciler') {
      await refreshReconciliationRecords()
    }
  }

  async function refreshChannelPricingData() {
    const [prices, items] = await Promise.all([
      fetchList(llmOpsApi.listChannelModelPrices),
      fetchList(llmOpsApi.listChannelPriceItems, {
        is_current: 'true'
      })
    ])
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
    const params = platformId ? { platform: platformId } : {}
    listings.value = asArray(
      await fetchList(llmOpsApi.listResaleListings, params)
    )
  }

  function preloadResalePublishingData() {
    const tasks = [refreshChannelPricingData(), refreshSummary()]
    if (!asArray(metaModels.value).length) {
      tasks.push(
        fetchList(llmOpsApi.listMetaModels).then((items) => {
          metaModels.value = asArray(items)
        })
      )
    }
    if (!asArray(modelPriceItems.value).length) {
      tasks.push(refreshModelPriceItems())
    }
    if (!asArray(listings.value).length) {
      tasks.push(refreshResaleListings())
    }

    Promise.all(tasks).catch((error) => {
      showError(errorMessage(error, t('llmOps.dataErrors.loadPublishing')))
    })
  }

  async function refreshReconciliationRecords() {
    records.value = asArray(
      await fetchFirstPage(llmOpsApi.listReconciliationRecords, {
        page_size: RECONCILIATION_PAGE_SIZE
      })
    )
  }

  async function refreshPriceHistoryData() {
    const [channelHistoryData, listingHistoryData] = await Promise.all([
      fetchFirstPage(llmOpsApi.listChannelModelPriceHistory, {
        page_size: PRICE_HISTORY_PAGE_SIZE
      }),
      fetchFirstPage(llmOpsApi.listResaleListingPriceHistory, {
        page_size: PRICE_HISTORY_PAGE_SIZE
      })
    ])
    channelPriceHistory.value = asArray(channelHistoryData)
    listingPriceHistory.value = asArray(listingHistoryData)
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
      const [sourceData, runData, providerData, summaryRes] = await Promise.all(
        [
          fetchList(llmOpsApi.listCollectionSources),
          fetchRecentCollectionRuns(),
          fetchList(llmOpsApi.listProviders),
          llmOpsApi.getSummary(summaryParams())
        ]
      )
      sources.value = asArray(sourceData)
      collectionRuns.value = asArray(runData)
      providers.value = asArray(providerData)
      summary.value = normalizeSummary(extract(summaryRes))
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshProviders')))
    }
  }

  async function refreshMetaModelManagementData() {
    try {
      const [providerData, metaModelData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listProviders),
        fetchList(llmOpsApi.listMetaModels),
        llmOpsApi.getSummary(summaryParams())
      ])
      providers.value = asArray(providerData)
      metaModels.value = asArray(metaModelData)
      summary.value = normalizeSummary(extract(summaryRes))
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshMetaModels')))
    }
  }

  async function refreshChannelManagementData() {
    try {
      const [channelData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listChannels),
        llmOpsApi.getSummary(summaryParams()),
        refreshChannelPricingData()
      ])
      channels.value = asArray(channelData)
      summary.value = normalizeSummary(extract(summaryRes))
      refreshResaleListings().catch((error) => {
        showError(errorMessage(error, t('llmOps.dataErrors.refreshListings')))
      })
    } catch (error) {
      showError(errorMessage(error, t('llmOps.dataErrors.refreshChannels')))
    }
  }

  async function refreshPlatformData() {
    try {
      const [platformData, listingData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listResalePlatforms),
        fetchList(
          llmOpsApi.listResaleListings,
          selectedResalePlatformId.value
            ? { platform: selectedResalePlatformId.value }
            : {}
        ),
        llmOpsApi.getSummary(summaryParams())
      ])
      resalePlatforms.value = asArray(platformData)
      listings.value = asArray(listingData)
      summary.value = normalizeSummary(extract(summaryRes))
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
    const summaryRes = await llmOpsApi.getSummary(summaryParams(scope))
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

  return {
    backgroundLoading,
    channelPriceHistory,
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
    models,
    normalizeDisplayCurrency,
    pointConversion,
    preloadResalePublishingData,
    procurementRows,
    providerCollectionSources,
    providers,
    records,
    refreshAll,
    refreshChannelPricingData,
    refreshChannelManagementData,
    refreshCollectionRuns,
    refreshCoreData,
    refreshLight,
    refreshMetaModelManagementData,
    refreshPlatformData,
    refreshProviderManagementData,
    refreshSectionData,
    refreshSummary,
    resalePlatforms,
    resaleWorkflowConfig,
    secondaryDataLoaded,
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
