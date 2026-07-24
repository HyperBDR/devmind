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
import { dataGroupsForSection } from '@/utils/llmOpsSectionData'
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
    await Promise.all(
      groups.map((group) => loadDataGroup(group, section, options))
    )
  }

  async function loadDataGroup(group, section, options) {
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

  async function refreshResalePlatformSelection(section) {
    const platformSections = [
      'listingRisk',
      'modelWorkbench',
      'monitor',
      'reseller'
    ]
    platformSections.forEach((sectionKey) => loadedSections.delete(sectionKey))
    if (section === 'monitor') {
      await refreshSummary('monitor')
      return
    }
    await Promise.all([refreshResaleListings(), refreshSummary()])
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

  async function refreshPriceHistoryData(modelId = null) {
    const model = Number(modelId)
    const modelFilter = Number.isInteger(model) && model > 0 ? { model } : {}
    const [channelHistoryData, listingHistoryData] = await Promise.all([
      fetchFirstPage(llmOpsApi.listChannelModelPriceHistory, {
        ...modelFilter,
        page_size: PRICE_HISTORY_PAGE_SIZE
      }),
      fetchFirstPage(llmOpsApi.listResaleListingPriceHistory, {
        ...modelFilter,
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

  function invalidateSectionCache() {
    loadedSections.clear()
  }

  return {
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
    invalidateSectionCache,
    normalizeDisplayCurrency,
    pageError,
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
