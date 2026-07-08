import { computed, onBeforeUnmount, ref } from 'vue'
import { dataOpsApi } from '@/api/dataOps'

const pageSize = 20

export function useDataOpsConsole() {
  const loading = ref(false)
  const preflightLoading = ref(false)
  const syncLoading = ref(false)
  const error = ref('')

  const summary = ref(null)
  const overview = ref(null)
  const insights = ref(null)
  const risks = ref(null)
  const opportunities = ref(null)
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
  const kanbanContracts = ref(null)
  const overseaSettlements = ref(null)
  const syncStatus = ref(null)
  const globalConfig = ref(defaultGlobalConfig())
  const collectionConfigs = ref([])
  const aiContext = ref(null)
  const aiInput = ref('')
  const aiLoading = ref(false)
  const aiStreamController = ref(null)

  const contractFilters = ref({
    customer_name: '',
    sales_person: '',
    status: '',
  })
  const salesFilters = ref({
    status: '',
    region: '',
    product_type: '',
  })
  const aiMessages = ref([
    {
      role: 'assistant',
      content: '我会基于当前数据运营上下文回答问题。请先确保飞书数据已同步。',
    },
  ])

  const syncTables = computed(() => syncStatus.value?.tables || [])
  const recentJobs = computed(() => syncStatus.value?.recent_jobs || [])
  const syncIssues = computed(() =>
    syncTables.value.filter((item) =>
      ['failed', 'warning'].includes(item.status)
    )
  )
  const contractCards = computed(() => kanbanContracts.value?.cards || [])
  const settlementCards = computed(() => overseaSettlements.value?.cards || [])

  const kpiCards = computed(() => {
    const data = summary.value || {}
    const kpis = overview.value?.kpis || {}
    return [
      { label: '合同数量', value: formatNumber(data.total_contracts) },
      {
        label: '合同金额',
        value: formatAmountByCurrency(
          data.total_contract_amount,
          data.total_contract_amount_by_currency
        ),
      },
      {
        label: '本月签约',
        value: formatAmountByCurrency(
          kpis.monthly_signed_amount,
          kpis.monthly_signed_amount_by_currency
        ),
      },
      {
        label: '累计回款',
        value: formatAmountByCurrency(
          data.total_received_amount,
          data.total_received_amount_by_currency
        ),
      },
      {
        label: '待回款',
        value: formatAmountByCurrency(
          data.total_outstanding_amount,
          data.total_outstanding_amount_by_currency
        ),
      },
    ]
  })

  const syncBannerTitle = computed(() => {
    if (!syncTables.value.length) return '尚未执行飞书权限检查'
    const status = syncStatus.value?.overall_status
    if (status === 'failed') return '飞书同步存在失败项'
    if (status === 'warning') return '飞书同步需要确认'
    return '飞书同步状态正常'
  })
  const syncBannerText = computed(() => {
    if (!syncTables.value.length) return '尚未执行飞书权限检查。'
    if (syncIssues.value.length) {
      return `发现 ${syncIssues.value.length} 张表存在权限、字段或数据完整性问题。`
    }
    return '所有已检查数据表均可读取。'
  })
  const syncBannerClass = computed(() => {
    const status = syncStatus.value?.overall_status
    if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-800'
    if (status === 'warning') {
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
        loadKanban(),
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
    ] = await Promise.all([
      dataOpsApi.summary(),
      dataOpsApi.executiveOverview(),
      dataOpsApi.insights(),
      dataOpsApi.executiveRisks(),
      dataOpsApi.executiveOpportunities(),
    ])
    summary.value = extractData(summaryRes)
    overview.value = extractData(overviewRes)
    insights.value = extractData(insightsRes)
    risks.value = extractData(risksRes)
    opportunities.value = extractData(opportunitiesRes)
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

  async function loadKanban() {
    const [contractsRes, settlementsRes] = await Promise.all([
      dataOpsApi.kanbanContracts(),
      dataOpsApi.kanbanOverseaSettlements(),
    ])
    kanbanContracts.value = extractData(contractsRes)
    overseaSettlements.value = extractData(settlementsRes)
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
        kanban: loadKanban,
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

  async function runPreflight() {
    preflightLoading.value = true
    error.value = ''
    try {
      const response = await dataOpsApi.runPreflight()
      const data = extractData(response)
      syncStatus.value = {
        ...(syncStatus.value || {}),
        overall_status: data.overall_status,
        tables: data.tables || [],
      }
      await loadSync()
    } catch (err) {
      setError(err)
    } finally {
      preflightLoading.value = false
    }
  }

  async function triggerFullSync() {
    syncLoading.value = true
    error.value = ''
    try {
      await dataOpsApi.triggerSync()
      await loadSync()
    } catch (err) {
      setError(err)
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

  async function saveSyncConfig(config) {
    try {
      const response = await dataOpsApi.updateSyncConfig(config.id, {
        table_name: config.table_name,
        app_token: config.app_token,
        table_id: config.table_id,
        is_enabled: config.is_enabled,
        sync_frequency: config.sync_frequency,
        expected_min_records: config.expected_min_records,
        required_permissions: config.required_permissions,
      })
      Object.assign(config, extractData(response))
    } catch (err) {
      setError(err)
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
    aiMessages.value.push({ role: 'user', content: message })
    aiInput.value = ''
    aiLoading.value = true
    const assistantMessage = { role: 'assistant', content: '' }
    aiMessages.value.push(assistantMessage)
    aiStreamController.value = new AbortController()
    try {
      await dataOpsApi.chatStream(
        {
          message,
          history: aiMessages.value.slice(0, -2),
        },
        {
          onChunk(content) {
            assistantMessage.content += content
          },
          onError(detail) {
            if (!assistantMessage.content) {
              assistantMessage.content = detail || 'AI 助手流式输出失败'
            }
          },
        },
        aiStreamController.value.signal
      )
    } catch (err) {
      if (err?.name !== 'AbortError' && !assistantMessage.content) {
        assistantMessage.content = errorMessage(err)
      }
    } finally {
      aiLoading.value = false
      aiStreamController.value = null
    }
  }

  function stopAiStream() {
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

  function permissionsText(config) {
    return (config.required_permissions || []).join('\n')
  }

  function updatePermissions(config, event) {
    config.required_permissions = event.target.value
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

  function updateGlobalConfigField(key, value) {
    globalConfig.value[key] = value
  }

  function setError(err) {
    error.value = errorMessage(err)
  }

  onBeforeUnmount(() => {
    if (aiStreamController.value) {
      aiStreamController.value.abort()
    }
  })

  return {
    aiContext,
    aiInput,
    aiLoading,
    aiMessages,
    collectionConfigs,
    contractCards,
    contractFilterOptions,
    contractFilters,
    contractPage,
    contractTotal,
    contracts,
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
    pageSize,
    permissionsText,
    pipelineInsights,
    pipelineProjects,
    pipelineSummary,
    preflightLoading,
    recentJobs,
    refreshActive,
    risks,
    runConfigPreflight,
    runPreflight,
    salesFilters,
    salesPage,
    salesRecords,
    salesTotal,
    saveGlobalConfig,
    saveSyncConfig,
    sendAiMessage,
    askAiQuestion,
    setContractPage,
    setSalesPage,
    settlementCards,
    syncBannerClass,
    syncBannerText,
    syncBannerTitle,
    syncLoading,
    syncTables,
    stopAiStream,
    triggerConfigSync,
    triggerFullSync,
    triggerIncrementalSync,
    updateGlobalConfigField,
    updatePermissions,
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

function extractData(response) {
  return response?.data?.data || response?.data
}

function errorMessage(err) {
  return (
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    '数据运营控制台请求失败'
  )
}

export function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value || 0))
}

export function formatAmount(value, currency = '') {
  if (value === null || value === undefined || value === '') return '-'
  const amount = Number(value || 0)
  const text = new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: 2,
  }).format(amount)
  return currency ? `${currency} ${text}` : text
}

export function formatAmountByCurrency(value, items) {
  if (Array.isArray(items) && items.length) {
    return items
      .map((item) => formatAmount(item.amount, item.currency))
      .join(' / ')
  }
  return formatAmount(value)
}

export function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
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
