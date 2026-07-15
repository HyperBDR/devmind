import apiClient from './index'
import { readDataOpsSseResponse } from '@/utils/dataOpsAiStream'

const base = '/v1/data-ops'

function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return null
}

function paramsOrEmpty(params) {
  return params ? { params } : {}
}

async function postSse(path, payload, callbacks = {}, signal = null) {
  const baseURL = apiClient.defaults.baseURL || ''
  const url = `${baseURL.replace(/\/$/, '')}${path}`
  const token =
    typeof localStorage !== 'undefined'
      ? localStorage.getItem('access_token')
      : null
  const csrf = getCookie('csrftoken')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (csrf) headers['X-CSRFToken'] = csrf

  const options = {
    method: 'POST',
    body: JSON.stringify(payload),
    headers,
    credentials: 'include'
  }
  if (signal) options.signal = signal

  const response = await fetch(url, options)
  if (!response.ok) {
    const error = new Error(response.statusText || 'Stream request failed')
    error.response = { status: response.status }
    try {
      const data = await response.json()
      error.detail = data?.detail || data?.message
    } catch (_) {
      // Ignore response bodies that are not valid JSON.
    }
    callbacks.onError?.(error.detail || error.message)
    throw error
  }

  await readDataOpsSseResponse(response, callbacks)
}

export const dataOpsApi = {
  summary() {
    return apiClient.get(`${base}/summary/`)
  },

  executiveOverview() {
    return apiClient.get(`${base}/executive/overview/`)
  },

  executiveTrends() {
    return apiClient.get(`${base}/executive/trends/`)
  },

  executiveTopCustomers() {
    return apiClient.get(`${base}/executive/top-customers/`)
  },

  executiveTopSales() {
    return apiClient.get(`${base}/executive/top-sales/`)
  },

  executiveRisks() {
    return apiClient.get(`${base}/executive/risks/`)
  },

  executiveOpportunities() {
    return apiClient.get(`${base}/executive/opportunities/`)
  },

  dataQuality() {
    return apiClient.get(`${base}/executive/data-quality/`)
  },

  insights() {
    return apiClient.get(`${base}/insights/`)
  },

  aiContext() {
    return apiClient.get(`${base}/ai/context/`)
  },

  chat(payload) {
    return apiClient.post(`${base}/llm/chat/`, payload)
  },

  chatStream(payload, callbacks = {}, signal = null) {
    return postSse(`${base}/llm/chat/stream/`, payload, callbacks, signal)
  },

  query(payload) {
    return apiClient.post(`${base}/llm/query/`, payload)
  },

  pipelineProjects(params) {
    return apiClient.get(`${base}/pipeline/projects/`, paramsOrEmpty(params))
  },

  pipelineDomesticLedgers() {
    return apiClient.get(`${base}/pipeline/domestic-ledgers/`)
  },

  pipelineInsights() {
    return apiClient.get(`${base}/pipeline/insights/`)
  },

  pipelineSummary() {
    return apiClient.get(`${base}/pipeline/summary/`)
  },

  contracts(params) {
    return apiClient.get(`${base}/contracts/`, paramsOrEmpty(params))
  },

  contractCount(params) {
    return apiClient.get(`${base}/contracts/count/`, paramsOrEmpty(params))
  },

  contractFilterOptions() {
    return apiClient.get(`${base}/contracts/filter-options/`)
  },

  contractHistory(contractId, params) {
    return apiClient.get(
      `${base}/contracts/${contractId}/history/`,
      paramsOrEmpty(params)
    )
  },

  salesRecords(params) {
    return apiClient.get(`${base}/sales-records/`, paramsOrEmpty(params))
  },

  salesRecordCount(params) {
    return apiClient.get(`${base}/sales-records/count/`, paramsOrEmpty(params))
  },

  salesPersons() {
    return apiClient.get(`${base}/sales-persons/`)
  },

  domesticLedgers(params) {
    return apiClient.get(`${base}/domestic-ledgers/`, paramsOrEmpty(params))
  },

  overseaProjects() {
    return apiClient.get(`${base}/oversea-projects/`)
  },

  projectInits() {
    return apiClient.get(`${base}/project-inits/`)
  },

  exportContracts() {
    return apiClient.get(`${base}/export/contracts/`, {
      responseType: 'blob'
    })
  },

  exportSalesRecords() {
    return apiClient.get(`${base}/export/sales-records/`, {
      responseType: 'blob'
    })
  },

  exportSummary() {
    return apiClient.get(`${base}/export/summary/`, {
      responseType: 'blob'
    })
  },

  syncStatus() {
    return apiClient.get(`${base}/sync/status/`)
  },

  globalConfig() {
    return apiClient.get(`${base}/settings/global/`)
  },

  updateGlobalConfig(payload) {
    return apiClient.patch(`${base}/settings/global/`, payload)
  },

  syncConfigs() {
    return apiClient.get(`${base}/sync/configs/`)
  },

  updateSyncConfig(configId, payload) {
    return apiClient.patch(`${base}/sync/configs/${configId}/`, payload)
  },

  runConfigPreflight(configId) {
    return apiClient.post(`${base}/sync/configs/${configId}/preflight/`)
  },

  triggerConfigSync(configId) {
    return apiClient.post(`${base}/sync/configs/${configId}/trigger/`)
  },

  runPreflight() {
    return apiClient.post(`${base}/sync/preflight/`)
  },

  triggerSync() {
    return apiClient.post(`${base}/sync/`)
  },

  triggerRefreshSync() {
    return apiClient.post(`${base}/sync/`, { force: false })
  },

  triggerIncrementalSync(sourceKey) {
    return apiClient.post(`${base}/sync/incremental/`, {
      source_key: sourceKey
    })
  },

}
