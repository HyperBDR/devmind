import { computed, ref } from 'vue'

import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import {
  DATA_HEAVY_SECTIONS,
  LIGHT_CORE_SECTIONS
} from '@/composables/useLLMOpsNavigation'
import {
  errorMessage,
  extract,
  fetchFirstPage,
  fetchList
} from '@/utils/llmOpsPagination'

const PRICE_HISTORY_PAGE_SIZE = 120
const supportedDisplayCurrencies = new Set(['CNY', 'USD'])

export function useLLMOpsData() {
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
    sources.value.filter((item) => item.source_type !== 'agione')
  )

  const procurementRows = computed(() => summary.value.procurement || [])
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

    refreshSecondaryData({ force: true, silent: true })
  }

  async function refreshCoreData(section) {
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
      fetchList(llmOpsApi.listCollectionRuns),
      fetchList(llmOpsApi.listProviders),
      fetchList(llmOpsApi.listMetaModels),
      shouldLoadModels ? fetchList(llmOpsApi.listModels) : Promise.resolve([]),
      fetchList(llmOpsApi.listChannels),
      fetchList(llmOpsApi.listResalePlatforms),
      llmOpsApi.getSummary(summaryParams())
    ])
    sources.value = extract(sourceRes)
    collectionRuns.value = extract(runRes)
    providers.value = extract(providerRes)
    metaModels.value = extract(metaModelRes)
    if (shouldLoadModels) {
      models.value = extract(modelRes)
    }
    channels.value = extract(channelRes)
    resalePlatforms.value = extract(platformRes)
    summary.value = extract(summaryRes)
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
        showError(errorMessage(error, '加载 LLM Ops 扩展数据失败。'))
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
      await Promise.all([refreshChannelPricingData(), refreshModelPriceItems()])
      return
    }
    if (section === 'channelMatrix') {
      await refreshChannelPricingData()
      return
    }
    if (section === 'reseller' || section === 'listingRisk') {
      await Promise.all([
        refreshChannelPricingData(),
        refreshModelPriceItems(),
        refreshResaleListings()
      ])
      return
    }
    if (section === 'modelWorkbench') {
      await Promise.all([
        refreshModelPriceItems(),
        refreshChannelPricingData(),
        refreshResaleListings(),
        refreshReconciliationRecords()
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
    channelPrices.value = prices
    channelPriceItems.value = items
  }

  async function refreshModelPriceItems() {
    modelPriceItems.value = await fetchList(llmOpsApi.listModelPriceItems, {
      is_current: 'true'
    })
  }

  async function refreshResaleListings() {
    listings.value = await fetchList(llmOpsApi.listResaleListings)
  }

  function preloadResalePublishingData() {
    const tasks = []
    if (!metaModels.value.length) {
      tasks.push(
        fetchList(llmOpsApi.listMetaModels).then((items) => {
          metaModels.value = items
        })
      )
    }
    if (!channelPrices.value.length || !channelPriceItems.value.length) {
      tasks.push(refreshChannelPricingData())
    }
    if (!modelPriceItems.value.length) {
      tasks.push(refreshModelPriceItems())
    }
    if (!listings.value.length) {
      tasks.push(refreshResaleListings())
    }
    if (!tasks.length) return

    Promise.all(tasks).catch((error) => {
      showError(errorMessage(error, '加载发布工作台数据失败。'))
    })
  }

  async function refreshReconciliationRecords() {
    records.value = await fetchList(llmOpsApi.listReconciliationRecords)
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
    channelPriceHistory.value = channelHistoryData
    listingPriceHistory.value = listingHistoryData
  }

  async function refreshLight() {
    const [prices, channelPriceItemsData, listingData, recordData, summaryRes] =
      await Promise.all([
        fetchList(llmOpsApi.listChannelModelPrices),
        fetchList(llmOpsApi.listChannelPriceItems, {
          is_current: 'true'
        }),
        fetchList(llmOpsApi.listResaleListings),
        fetchList(llmOpsApi.listReconciliationRecords),
        llmOpsApi.getSummary(summaryParams())
      ])
    channelPrices.value = prices
    channelPriceItems.value = channelPriceItemsData
    listings.value = listingData
    records.value = recordData
    summary.value = extract(summaryRes)
  }

  async function refreshCollectionRuns() {
    const [sourceData, runData] = await Promise.all([
      fetchList(llmOpsApi.listCollectionSources),
      fetchList(llmOpsApi.listCollectionRuns)
    ])
    sources.value = sourceData
    collectionRuns.value = runData
  }

  async function refreshProviderManagementData() {
    try {
      const [sourceData, runData, providerData, summaryRes] = await Promise.all(
        [
          fetchList(llmOpsApi.listCollectionSources),
          fetchList(llmOpsApi.listCollectionRuns),
          fetchList(llmOpsApi.listProviders),
          llmOpsApi.getSummary(summaryParams())
        ]
      )
      sources.value = sourceData
      collectionRuns.value = runData
      providers.value = providerData
      summary.value = extract(summaryRes)
    } catch (error) {
      showError(errorMessage(error, '刷新价格源数据失败。'))
    }
  }

  async function refreshMetaModelManagementData() {
    try {
      const [providerData, metaModelData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listProviders),
        fetchList(llmOpsApi.listMetaModels),
        llmOpsApi.getSummary(summaryParams())
      ])
      providers.value = providerData
      metaModels.value = metaModelData
      summary.value = extract(summaryRes)
    } catch (error) {
      showError(errorMessage(error, '刷新元模型数据失败。'))
    }
  }

  async function refreshChannelManagementData() {
    try {
      const [channelData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listChannels),
        llmOpsApi.getSummary(summaryParams()),
        refreshChannelPricingData()
      ])
      channels.value = channelData
      summary.value = extract(summaryRes)
      refreshResaleListings().catch((error) => {
        showError(errorMessage(error, '刷新转售列表失败。'))
      })
    } catch (error) {
      showError(errorMessage(error, '刷新渠道数据失败。'))
    }
  }

  async function refreshPlatformData() {
    try {
      const [platformData, listingData, summaryRes] = await Promise.all([
        fetchList(llmOpsApi.listResalePlatforms),
        fetchList(llmOpsApi.listResaleListings),
        llmOpsApi.getSummary(summaryParams())
      ])
      resalePlatforms.value = platformData
      listings.value = listingData
      summary.value = extract(summaryRes)
      await loadResaleWorkflowConfig()
    } catch (error) {
      showError(errorMessage(error, '刷新转售平台数据失败。'))
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

  async function refreshSummary() {
    const summaryRes = await llmOpsApi.getSummary(summaryParams())
    summary.value = extract(summaryRes)
  }

  function summaryParams() {
    return {
      display_currency: displayCurrency.value,
      resale_platform: selectedResalePlatformId.value || ''
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
