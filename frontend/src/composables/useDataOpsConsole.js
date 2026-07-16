import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { dataOpsApi } from '@/api/dataOps'
import {
  formatAmount as formatCurrencyAmount,
  formatAmountByCurrency as formatCurrencyAmounts,
} from '@/utils/currency'
import {
  appendAiContent,
  resolveFinalAiContent,
  sanitizeAiContent,
} from '@/utils/dataOpsAiStream'
import { normalizeDataOpsProgressEvent } from '@/utils/dataOpsProgress'
import { syncJobError, syncJobFailureDetails } from '@/utils/sync'

const pageSize = 20
const aiHistoryStorageKey = 'data_ops_ai_chat_history_v1'
const maxAiHistoryItems = 30
const syncPollIntervalMs = 1000
const syncPollMaxAttempts = 120
const terminalSyncStatuses = new Set(['ok', 'warning', 'failed'])

export function useDataOpsConsole() {
  const { locale, t } = useI18n()
  const loading = ref(false)
  const preflightLoading = ref(false)
  const syncLoading = ref(false)
  const error = ref('')
  const syncFailure = ref(null)
  const preflightFeedback = ref('')
  const refreshFeedback = ref('')
  const refreshFeedbackTone = ref('ok')

  const summary = ref(null)
  const overview = ref(null)
  const insights = ref(null)
  const risks = ref(null)
  const opportunities = ref(null)
  const dataQuality = ref(null)
  const topCustomers = ref(null)
  const pipelineSummary = ref(null)
  const pipelineProjects = ref([])
  const pipelineInsights = ref(null)
  const contracts = ref([])
  const contractTotal = ref(0)
  const contractPage = ref(1)
  const contractFilterOptions = ref({})
  const salesRecords = ref([])
  const salesTotal = ref(0)
  const salesPage = ref(1)
  const syncStatus = ref(null)
  const globalConfig = ref(defaultGlobalConfig())
  const collectionConfigs = ref([])
  const aiContext = ref(null)
  const aiInput = ref('')
  const aiLoading = ref(false)
  const aiActiveAssistantMessage = ref(null)
  const aiActiveHistoryId = ref('')
  const aiHistory = ref(loadAiHistory())
  const aiStreamController = ref(null)

  const contractFilters = ref({
    customer_name: '',
    signing_entity: '',
    sales_person: '',
    status: '',
  })
  const salesFilters = ref({
    status: '',
    region: '',
    product_type: '',
  })
  const aiMessages = ref([])

  const syncTables = computed(() => syncStatus.value?.tables || [])
  const recentJobs = computed(() => syncStatus.value?.recent_jobs || [])
  const syncIssues = computed(() =>
    syncTables.value.filter((item) =>
      ['failed', 'warning'].includes(item.status)
    )
  )
  const kpiCards = computed(() => {
    const data = summary.value || {}
    const kpis = overview.value?.kpis || {}
    return [
      {
        label: t('dataOps.kpi.contractCount'),
        value: formatNumber(data.total_contracts, locale.value)
      },
      {
        label: t('dataOps.kpi.contractAmount'),
        value: formatAmountByCurrency(
          data.total_contract_amount,
          data.total_contract_amount_by_currency,
          { locale: locale.value }
        ),
      },
      {
        label: t('dataOps.kpi.monthlySigned'),
        value: formatAmountByCurrency(
          kpis.monthly_signed_amount,
          kpis.monthly_signed_amount_by_currency,
          { locale: locale.value }
        ),
      },
      {
        label: t('dataOps.kpi.received'),
        value: formatAmountByCurrency(
          data.total_received_amount,
          data.total_received_amount_by_currency,
          { locale: locale.value }
        ),
      },
      {
        label: t('dataOps.kpi.outstanding'),
        value: formatAmountByCurrency(
          data.total_outstanding_amount,
          data.total_outstanding_amount_by_currency,
          { locale: locale.value }
        ),
      },
    ]
  })

  const syncBannerTitle = computed(() => {
    if (!syncTables.value.length) return t('dataOps.banner.unchecked')
    const status = syncStatus.value?.overall_status
    if (status === 'failed') return t('dataOps.banner.failed')
    if (status === 'warning') return t('dataOps.banner.warning')
    return t('dataOps.banner.healthy')
  })
  const syncBannerText = computed(() => {
    if (!syncTables.value.length) return t('dataOps.banner.uncheckedText')
    if (syncIssues.value.length) {
      return t('dataOps.banner.issues', { count: syncIssues.value.length })
    }
    return t('dataOps.banner.allReadable')
  })
  const syncBannerClass = computed(() => {
    const status = syncStatus.value?.overall_status
    if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-800'
    if (status === 'warning') {
      return 'border-amber-200 bg-amber-50 text-amber-800'
    }
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  })
  const preflightFeedbackClass = computed(() => {
    const status = syncStatus.value?.overall_status
    if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-800'
    if (status === 'warning') {
      return 'border-amber-200 bg-amber-50 text-amber-800'
    }
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  })
  const refreshFeedbackClass = computed(() => {
    if (refreshFeedbackTone.value === 'warning') {
      return 'border-amber-200 bg-amber-50 text-amber-800'
    }
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  })

  async function loadAll(includeConfigs = true) {
    loading.value = true
    error.value = ''
    try {
      await Promise.all([
        loadExecutive(),
        loadPipeline(),
        loadContracts(),
        loadSalesRecords(),
        loadSync(includeConfigs),
        loadAiContext(),
      ])
    } catch (err) {
      setError(err)
    } finally {
      loading.value = false
    }
  }

  async function loadExecutive() {
    const [
      summaryRes,
      overviewRes,
      insightsRes,
      risksRes,
      opportunitiesRes,
      dataQualityRes,
      topCustomersRes,
    ] = await Promise.all([
      dataOpsApi.summary(),
      dataOpsApi.executiveOverview(),
      dataOpsApi.insights(),
      dataOpsApi.executiveRisks(),
      dataOpsApi.executiveOpportunities(),
      dataOpsApi.dataQuality(),
      dataOpsApi.executiveTopCustomers(),
    ])
    summary.value = extractData(summaryRes)
    overview.value = extractData(overviewRes)
    insights.value = extractData(insightsRes)
    risks.value = extractData(risksRes)
    opportunities.value = extractData(opportunitiesRes)
    dataQuality.value = extractData(dataQualityRes)
    topCustomers.value = extractData(topCustomersRes)
  }

  async function loadPipeline() {
    const [summaryRes, projectsRes, insightsRes] = await Promise.all([
      dataOpsApi.pipelineSummary(),
      dataOpsApi.pipelineProjects(),
      dataOpsApi.pipelineInsights(),
    ])
    pipelineSummary.value = extractData(summaryRes)
    pipelineProjects.value = extractData(projectsRes)?.cards || []
    pipelineInsights.value = extractData(insightsRes)
  }

  async function loadContracts() {
    const params = {
      ...compactObject(contractFilters.value),
      page: contractPage.value,
      page_size: pageSize,
    }
    const [listRes, countRes, optionsRes] = await Promise.all([
      dataOpsApi.contracts(params),
      dataOpsApi.contractCount(params),
      dataOpsApi.contractFilterOptions(),
    ])
    contracts.value = extractData(listRes) || []
    contractTotal.value = extractData(countRes)?.total || 0
    contractFilterOptions.value = extractData(optionsRes) || {}
  }

  async function loadSalesRecords() {
    const params = {
      ...compactObject(salesFilters.value),
      page: salesPage.value,
      page_size: pageSize,
    }
    const [listRes, countRes] = await Promise.all([
      dataOpsApi.salesRecords(params),
      dataOpsApi.salesRecordCount(params),
    ])
    salesRecords.value = extractData(listRes) || []
    salesTotal.value = extractData(countRes)?.total || 0
  }

  async function loadSync(includeConfigs = true) {
    const requests = [dataOpsApi.syncStatus()]
    if (includeConfigs) {
      requests.push(dataOpsApi.syncConfigs())
      requests.push(dataOpsApi.globalConfig())
    }
    const [syncRes, configsRes, globalConfigRes] = await Promise.all(requests)
    syncStatus.value = extractData(syncRes)
    if (includeConfigs) {
      collectionConfigs.value = extractData(configsRes) || []
      Object.assign(
        globalConfig.value,
        normalizeGlobalConfig(extractData(globalConfigRes))
      )
    }
  }

  async function loadAiContext() {
    const response = await dataOpsApi.aiContext()
    aiContext.value = extractData(response)
  }

  async function refreshActive(section, includeConfigs = true) {
    loading.value = true
    error.value = ''
    try {
      const loaders = {
        executive: loadExecutive,
        pipeline: loadPipeline,
        contracts: loadContracts,
        sales: loadSalesRecords,
        sync: () => loadSync(includeConfigs),
        config: () => loadSync(true),
      }
      await (loaders[section] || loadExecutive)()
    } catch (err) {
      setError(err)
    } finally {
      loading.value = false
    }
  }

  async function refreshFromFeishu(section, includeConfigs = true) {
    loading.value = true
    error.value = ''
    preflightFeedback.value = ''
    refreshFeedback.value = ''
    refreshFeedbackTone.value = 'ok'
    syncFailure.value = null
    try {
      const response = await dataOpsApi.triggerRefreshSync()
      const queuedJob = extractData(response)
      const job = await waitForSyncJob(queuedJob?.id)
      if (!job) {
        refreshFeedbackTone.value = 'warning'
        refreshFeedback.value = t('dataOps.feedback.refreshRunning')
        await refreshActive(section, includeConfigs)
        return false
      }
      if (job.status === 'failed') {
        syncFailure.value = syncJobFailureDetails(job)
        throw new Error(syncJobError(job))
      }

      await refreshActive(section, includeConfigs)
      const recordsSynced = Number(job.records_synced || 0)
      const skippedTables = Object.values(job.results || {}).filter(
        (result) => result?.skipped
      ).length
      if (recordsSynced > 0) {
        refreshFeedback.value = t('dataOps.feedback.recordsUpdated', {
          count: recordsSynced
        })
      } else if (job.status === 'warning' && job.error_message) {
        refreshFeedback.value = job.error_message
      } else if (skippedTables > 0) {
        refreshFeedback.value = t('dataOps.feedback.tablesUnchanged', {
          count: skippedTables
        })
      } else {
        refreshFeedback.value = t('dataOps.feedback.noChanges')
      }
      if (job.status === 'warning') {
        refreshFeedbackTone.value = 'warning'
      }
      return true
    } catch (err) {
      error.value = errorMessage(err, t('dataOps.feedback.requestFailed'))
      return false
    } finally {
      loading.value = false
    }
  }

  async function waitForSyncJob(jobId) {
    if (!jobId) return null
    for (let attempt = 0; attempt < syncPollMaxAttempts; attempt += 1) {
      const response = await dataOpsApi.syncStatus()
      const data = extractData(response) || {}
      syncStatus.value = data
      const job = (data.recent_jobs || []).find(
        (item) => String(item.id) === String(jobId)
      )
      if (job && terminalSyncStatuses.has(job.status)) {
        return job
      }
      await delay(syncPollIntervalMs)
    }
    return null
  }

  async function runPreflight() {
    preflightLoading.value = true
    error.value = ''
    preflightFeedback.value = ''
    try {
      const response = await dataOpsApi.runPreflight()
      const data = extractData(response)
      const tables = data.tables || []
      syncStatus.value = {
        ...(syncStatus.value || {}),
        overall_status: data.overall_status,
        tables,
      }
      await loadSync()
      preflightFeedback.value = preflightSummary(
        data.overall_status,
        tables,
        data.discovery,
        t
      )
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      preflightLoading.value = false
    }
  }

  async function triggerFullSync() {
    if (syncLoading.value) return false
    syncLoading.value = true
    error.value = ''
    syncFailure.value = null
    try {
      const response = await dataOpsApi.triggerSync()
      const queuedJob = extractData(response)
      const job = await waitForSyncJob(queuedJob?.id)
      await loadSync()
      if (!job) {
        refreshFeedbackTone.value = 'warning'
        refreshFeedback.value = t('dataOps.feedback.fullSyncRunning')
        return false
      }
      if (job.status === 'failed') {
        syncFailure.value = syncJobFailureDetails(job)
        error.value = syncJobError(job)
        return false
      }
      return true
    } catch (err) {
      setError(err)
      return false
    } finally {
      syncLoading.value = false
    }
  }

  async function triggerIncrementalSync(sourceKey) {
    syncLoading.value = true
    error.value = ''
    try {
      await dataOpsApi.triggerIncrementalSync(sourceKey)
      await loadSync()
    } catch (err) {
      setError(err)
    } finally {
      syncLoading.value = false
    }
  }

  async function saveGlobalConfig() {
    try {
      const payload = {
        feishu_app_id: globalConfig.value.feishu_app_id,
        feishu_date_timezone: globalConfig.value.feishu_date_timezone,
        active_sync_job_timeout_hours: Number(
          globalConfig.value.active_sync_job_timeout_hours || 3
        ),
      }
      if (globalConfig.value.feishu_app_secret) {
        payload.feishu_app_secret = globalConfig.value.feishu_app_secret
      }
      const response = await dataOpsApi.updateGlobalConfig(payload)
      Object.assign(
        globalConfig.value,
        normalizeGlobalConfig(extractData(response))
      )
    } catch (err) {
      setError(err)
    }
  }

  async function runConfigPreflight(config) {
    try {
      await dataOpsApi.runConfigPreflight(config.id)
      await loadSync()
    } catch (err) {
      setError(err)
    }
  }

  async function triggerConfigSync(config) {
    try {
      await dataOpsApi.triggerConfigSync(config.id)
      await loadSync()
    } catch (err) {
      setError(err)
    }
  }

  async function sendAiMessage() {
    const message = aiInput.value.trim()
    if (!message || aiLoading.value) return
    const historyId = ensureAiHistoryId()
    aiMessages.value.push({ role: 'user', content: message })
    aiInput.value = ''
    aiLoading.value = true
    const startedAt = Date.now()
    let timerId = null
    const assistantMessage = {
      role: 'assistant',
      content: '',
      elapsedMs: 0,
      progressEvents: [],
      startedAt,
      status: 'thinking',
    }
    aiMessages.value.push(assistantMessage)
    const assistantIndex = aiMessages.value.length - 1
    aiActiveAssistantMessage.value = aiMessages.value[assistantIndex]
    const updateAssistantMessage = (patch) => {
      const current = aiMessages.value[assistantIndex]
      if (!current) return
      Object.assign(current, patch)
    }
    timerId = setInterval(() => {
      updateAssistantMessage({ elapsedMs: Date.now() - startedAt })
    }, 200)
    aiStreamController.value = new AbortController()
    try {
      await dataOpsApi.chatStream(
        {
          message,
          history: aiMessages.value.slice(0, -2),
        },
        {
          onProgress(event) {
            const current = aiMessages.value[assistantIndex]
            updateAssistantMessage({
              progressEvents: [
                ...(current?.progressEvents || []),
                normalizeDataOpsProgressEvent(event),
              ],
            })
          },
          onChunk(content) {
            const current = aiMessages.value[assistantIndex]
            updateAssistantMessage({
              content: appendAiContent(current?.content, content),
              status: 'streaming',
            })
          },
          onDone(payload) {
            const current = aiMessages.value[assistantIndex]
            const finalContent =
              payload?.reply || payload?.answer || payload?.content || ''
            const patch = {
              llm: payload?.llm || null,
              status: 'done',
              usage: payload?.usage || null,
            }
            patch.content = resolveFinalAiContent(
              current?.content,
              finalContent,
              t('dataOps.feedback.analysisEmpty')
            )
            updateAssistantMessage({
              ...patch,
            })
          },
          onError(detail) {
            const current = aiMessages.value[assistantIndex]
            updateAssistantMessage({ status: 'error' })
            if (!sanitizeAiContent(current?.content)) {
              updateAssistantMessage({
                content: detail || t('dataOps.feedback.streamFailed'),
              })
            }
          },
        },
        aiStreamController.value.signal
      )
    } catch (err) {
      if (err?.name === 'AbortError') {
        const current = aiMessages.value[assistantIndex]
        updateAssistantMessage({ status: 'stopped' })
        if (!current?.content) {
          updateAssistantMessage({ content: t('dataOps.feedback.stopped') })
        }
      } else {
        const current = aiMessages.value[assistantIndex]
        updateAssistantMessage({ status: 'error' })
        if (!sanitizeAiContent(current?.content)) {
          updateAssistantMessage({
            content: errorMessage(err, t('dataOps.feedback.requestFailed'))
          })
        }
      }
    } finally {
      if (timerId) clearInterval(timerId)
      updateAssistantMessage({ elapsedMs: Date.now() - startedAt })
      persistAiConversation(historyId)
      aiLoading.value = false
      aiActiveAssistantMessage.value = null
      aiStreamController.value = null
    }
  }

  function stopAiStream() {
    if (aiActiveAssistantMessage.value) {
      aiActiveAssistantMessage.value.status = 'stopped'
      aiActiveAssistantMessage.value.elapsedMs =
        Date.now() - aiActiveAssistantMessage.value.startedAt
      if (!aiActiveAssistantMessage.value.content) {
        aiActiveAssistantMessage.value.content = t('dataOps.feedback.stopped')
      }
      persistAiConversation(aiActiveHistoryId.value)
    }
    if (aiStreamController.value) {
      aiStreamController.value.abort()
      aiStreamController.value = null
    }
    aiLoading.value = false
  }

  function askAiQuestion(question) {
    aiInput.value = question
    return sendAiMessage()
  }

  function ensureAiHistoryId() {
    if (!aiActiveHistoryId.value) {
      aiActiveHistoryId.value = `data_ops_ai_${Date.now()}_${Math.random()
        .toString(36)
        .slice(2, 8)}`
    }
    return aiActiveHistoryId.value
  }

  function persistAiConversation(id) {
    if (!id) return
    const messages = cloneMessages(aiMessages.value).filter(
      (item) => item?.role && (item?.content || item?.progressEvents?.length)
    )
    const firstUser = messages.find((item) => item.role === 'user')
    if (!firstUser) return
    const item = {
      id,
      messageCount: messages.length,
      messages,
      title: summarizeAiHistoryTitle(
        firstUser.content,
        t('dataOps.feedback.untitledConversation')
      ),
      updatedAt: new Date().toISOString(),
    }
    aiHistory.value = [
      item,
      ...aiHistory.value.filter((entry) => entry.id !== id),
    ].slice(0, maxAiHistoryItems)
    saveAiHistory(aiHistory.value)
  }

  function startNewAiConversation() {
    if (aiLoading.value) return
    aiMessages.value = []
    aiInput.value = ''
    aiActiveHistoryId.value = ''
  }

  function selectAiHistoryItem(id) {
    if (aiLoading.value) return
    const item = aiHistory.value.find((entry) => entry.id === id)
    if (!item) return
    aiMessages.value = cloneMessages(item.messages || [])
    aiInput.value = ''
    aiActiveHistoryId.value = item.id
  }

  function deleteAiHistoryItem(id) {
    aiHistory.value = aiHistory.value.filter((item) => item.id !== id)
    saveAiHistory(aiHistory.value)
    if (aiActiveHistoryId.value === id) {
      aiActiveHistoryId.value = ''
    }
  }

  function setContractPage(page) {
    contractPage.value = page
    loadContracts()
  }

  function setSalesPage(page) {
    salesPage.value = page
    loadSalesRecords()
  }

  async function downloadContracts() {
    const response = await dataOpsApi.exportContracts()
    downloadBlob(response.data, 'contracts.csv')
  }

  async function downloadSales() {
    const response = await dataOpsApi.exportSalesRecords()
    downloadBlob(response.data, 'sales_records.csv')
  }

  function updateGlobalConfigField(key, value) {
    globalConfig.value[key] = value
  }

  function setError(err) {
    syncFailure.value = null
    error.value = errorMessage(err, t('dataOps.feedback.requestFailed'))
  }

  onBeforeUnmount(() => {
    if (aiStreamController.value) {
      aiStreamController.value.abort()
    }
  })

  return {
    aiContext,
    aiActiveHistoryId,
    aiHistory,
    aiInput,
    aiLoading,
    aiMessages,
    collectionConfigs,
    contractFilterOptions,
    contractFilters,
    contractPage,
    contractTotal,
    contracts,
    dataQuality,
    deleteAiHistoryItem,
    downloadContracts,
    downloadSales,
    error,
    globalConfig,
    insights,
    kpiCards,
    loadAll,
    loadContracts,
    loadSalesRecords,
    loading,
    opportunities,
    overview,
    pageSize,
    preflightFeedback,
    preflightFeedbackClass,
    pipelineInsights,
    pipelineProjects,
    pipelineSummary,
    preflightLoading,
    recentJobs,
    refreshFeedback,
    refreshFeedbackClass,
    refreshActive,
    refreshFromFeishu,
    risks,
    runConfigPreflight,
    runPreflight,
    salesFilters,
    salesPage,
    salesRecords,
    salesTotal,
    saveGlobalConfig,
    selectAiHistoryItem,
    sendAiMessage,
    askAiQuestion,
    setContractPage,
    setSalesPage,
    summary,
    syncBannerClass,
    syncBannerText,
    syncBannerTitle,
    syncFailure,
    syncLoading,
    syncTables,
    stopAiStream,
    startNewAiConversation,
    topCustomers,
    triggerConfigSync,
    triggerFullSync,
    triggerIncrementalSync,
    updateGlobalConfigField,
  }
}

function defaultGlobalConfig() {
  return {
    feishu_app_id: '',
    feishu_app_secret: '',
    has_feishu_app_secret: false,
    feishu_date_timezone: 'Asia/Shanghai',
    active_sync_job_timeout_hours: 3,
  }
}

function normalizeGlobalConfig(config) {
  return {
    ...defaultGlobalConfig(),
    ...(config || {}),
    feishu_app_secret: '',
  }
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== '' && item != null)
  )
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

function extractData(response) {
  return response?.data?.data || response?.data
}

function errorMessage(err, fallback = 'Data Ops request failed') {
  return (
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    fallback
  )
}

function preflightSummary(status, tables, discovery = null, t) {
  const failed = tables.filter((item) => item.status === 'failed').length
  const warning = tables.filter((item) => item.status === 'warning').length
  const total = tables.length
  const discoveryText = discovery
    ? t('dataOps.feedback.discovery', {
        seen: discovery.tables_seen || 0,
        matched: discovery.matched || 0
      })
    : ''
  if (!total) return t('dataOps.feedback.preflightEmpty')
  if (status === 'failed') {
    return t('dataOps.feedback.preflightFailed', {
      failed,
      warning,
      total,
      discovery: discoveryText
    })
  }
  if (status === 'warning') {
    return t('dataOps.feedback.preflightWarning', {
      warning,
      total,
      discovery: discoveryText
    })
  }
  return t('dataOps.feedback.preflightOk', {
    total,
    discovery: discoveryText
  })
}

function loadAiHistory() {
  if (typeof localStorage === 'undefined') return []
  try {
    const parsed = JSON.parse(
      localStorage.getItem(aiHistoryStorageKey) || '[]'
    )
    return Array.isArray(parsed) ? parsed.slice(0, maxAiHistoryItems) : []
  } catch (_) {
    return []
  }
}

function saveAiHistory(items) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(
    aiHistoryStorageKey,
    JSON.stringify(items.slice(0, maxAiHistoryItems))
  )
}

function cloneMessages(messages) {
  return JSON.parse(JSON.stringify(messages || []))
}

function summarizeAiHistoryTitle(value, fallback = 'Untitled conversation') {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return fallback
  return text.length > 32 ? `${text.slice(0, 32)}...` : text
}

export function formatNumber(value, locale = 'zh-CN') {
  return new Intl.NumberFormat(locale).format(Number(value || 0))
}

export function formatAmount(value, currency = '', options = {}) {
  return formatCurrencyAmount(value, currency, options)
}

export function formatAmountByCurrency(value, items, options = {}) {
  return formatCurrencyAmounts(value, items, options)
}

export function formatDateTime(value, locale = 'zh-CN') {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString(locale, { hour12: false })
}

export function statusPillClass(status) {
  if (status === 'failed') return 'bg-rose-100 text-rose-700'
  if (status === 'warning') return 'bg-amber-100 text-amber-700'
  if (status === 'ok') return 'bg-emerald-100 text-emerald-700'
  return 'bg-slate-100 text-slate-600'
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
