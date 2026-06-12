import apiClient from './index'

let feishuUsersResponseCache = null
let feishuUsersRequestPromise = null
const FEISHU_USERS_STORAGE_KEY = 'devmind.cloudBilling.feishuUsers.v2'
const FEISHU_USERS_STORAGE_TTL_MS = 12 * 60 * 60 * 1000

function getCachedFeishuUsersResponse() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(FEISHU_USERS_STORAGE_KEY)
    if (!raw) return null
    const cached = JSON.parse(raw)
    if (!cached?.savedAt || !cached?.data) return null
    const users = cached.data?.users
    if (Array.isArray(users) && users.length === 1) {
      window.localStorage.removeItem(FEISHU_USERS_STORAGE_KEY)
      return null
    }
    if (Date.now() - cached.savedAt > FEISHU_USERS_STORAGE_TTL_MS) {
      window.localStorage.removeItem(FEISHU_USERS_STORAGE_KEY)
      return null
    }
    return { data: cached.data }
  } catch {
    return null
  }
}

function setCachedFeishuUsersResponse(response) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      FEISHU_USERS_STORAGE_KEY,
      JSON.stringify({
        savedAt: Date.now(),
        data: response?.data || response
      })
    )
  } catch {
    // Ignore storage quota or privacy-mode failures.
  }
}

function clearCachedFeishuUsersResponse() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(FEISHU_USERS_STORAGE_KEY)
  } catch {
    // Ignore storage failures.
  }
}

export const cloudBillingApi = {
  // Cloud Provider APIs
  async getProviders(params = {}) {
    const response = await apiClient.get('/v1/cloud-billing/providers/', {
      params
    })
    return response
  },

  async getProvider(id) {
    const response = await apiClient.get(`/v1/cloud-billing/providers/${id}/`)
    return response
  },

  async createProvider(data) {
    const response = await apiClient.post('/v1/cloud-billing/providers/', data)
    return response
  },

  async updateProvider(id, data) {
    const response = await apiClient.put(
      `/v1/cloud-billing/providers/${id}/`,
      data
    )
    return response
  },

  async patchProvider(id, data) {
    const response = await apiClient.patch(
      `/v1/cloud-billing/providers/${id}/`,
      data
    )
    return response
  },

  async deleteProvider(id) {
    const response = await apiClient.delete(
      `/v1/cloud-billing/providers/${id}/`
    )
    return response
  },

  async validateProvider(id) {
    const response = await apiClient.post(
      `/v1/cloud-billing/providers/${id}/validate/`
    )
    return response
  },

  async validateProviderConfig(providerType, config) {
    const response = await apiClient.post(
      '/v1/cloud-billing/providers/validate-config/',
      {
        provider_type: providerType,
        config: config
      }
    )
    return response
  },

  async getProviderTags() {
    const response = await apiClient.get('/v1/cloud-billing/providers/tags/')
    return response
  },

  async submitProviderRechargeApproval(id, data = {}) {
    const response = await apiClient.post(
      `/v1/cloud-billing/providers/${id}/submit-recharge-approval/`,
      data
    )
    return response
  },

  async getFeishuUsers({ forceRefresh = false } = {}) {
    if (!forceRefresh && feishuUsersResponseCache) {
      return feishuUsersResponseCache
    }
    if (!forceRefresh) {
      const persistedResponse = getCachedFeishuUsersResponse()
      if (persistedResponse) {
        feishuUsersResponseCache = persistedResponse
        return persistedResponse
      }
    }
    if (!forceRefresh && feishuUsersRequestPromise) {
      return feishuUsersRequestPromise
    }
    feishuUsersRequestPromise = apiClient
      .get('/v1/cloud-billing/feishu-users/', {
        params: forceRefresh ? { refresh: 1 } : {}
      })
      .then((response) => {
        feishuUsersResponseCache = response
        setCachedFeishuUsersResponse(response)
        return response
      })
      .finally(() => {
        feishuUsersRequestPromise = null
      })
    return feishuUsersRequestPromise
  },

  clearFeishuUsersCache() {
    feishuUsersResponseCache = null
    feishuUsersRequestPromise = null
    clearCachedFeishuUsersResponse()
  },

  async refreshFeishuUsers() {
    return this.getFeishuUsers({ forceRefresh: true })
  },

  async getFeishuUsersUncached() {
    const response = await apiClient.get('/v1/cloud-billing/feishu-users/')
    return response
  },

  // Billing Data APIs
  async getBillingData(params = {}) {
    const response = await apiClient.get('/v1/cloud-billing/billing-data/', {
      params
    })
    return response
  },

  async getLatestBillingByProviderAccount(params = {}) {
    const response = await apiClient.get(
      '/v1/cloud-billing/billing-data/latest-by-provider-account/',
      { params }
    )
    return response
  },

  async getBillingDataDetail(id) {
    const response = await apiClient.get(
      `/v1/cloud-billing/billing-data/${id}/`
    )
    return response
  },

  async getBillingStats(params = {}) {
    const response = await apiClient.get(
      '/v1/cloud-billing/billing-data/stats/',
      { params }
    )
    return response
  },

  async getBillingDailySeries(params = {}) {
    const response = await apiClient.get(
      '/v1/cloud-billing/billing-data/daily-series/',
      { params }
    )
    return response
  },

  async getOverview(params = {}) {
    const response = await apiClient.get(
      '/v1/cloud-billing/billing-data/overview/',
      { params }
    )
    return response
  },

  // Alert Rule APIs
  async getAlertRules(params = {}) {
    const response = await apiClient.get('/v1/cloud-billing/alert-rules/', {
      params
    })
    return response
  },

  async getAlertRule(id) {
    const response = await apiClient.get(`/v1/cloud-billing/alert-rules/${id}/`)
    return response
  },

  async createAlertRule(data) {
    const response = await apiClient.post(
      '/v1/cloud-billing/alert-rules/',
      data
    )
    return response
  },

  async updateAlertRule(id, data) {
    const response = await apiClient.put(
      `/v1/cloud-billing/alert-rules/${id}/`,
      data
    )
    return response
  },

  async patchAlertRule(id, data) {
    const response = await apiClient.patch(
      `/v1/cloud-billing/alert-rules/${id}/`,
      data
    )
    return response
  },

  async deleteAlertRule(id) {
    const response = await apiClient.delete(
      `/v1/cloud-billing/alert-rules/${id}/`
    )
    return response
  },

  // Alert Record APIs
  async getAlertRecords(params = {}) {
    const response = await apiClient.get('/v1/cloud-billing/alert-records/', {
      params
    })
    return response
  },

  async getAlertRecord(id) {
    const response = await apiClient.get(
      `/v1/cloud-billing/alert-records/${id}/`
    )
    return response
  },

  async getRechargeApprovals(params = {}) {
    const response = await apiClient.get(
      '/v1/cloud-billing/recharge-approvals/',
      {
        params
      }
    )
    return response
  },

  async getRechargeApproval(id) {
    const response = await apiClient.get(
      `/v1/cloud-billing/recharge-approvals/${id}/`
    )
    return response
  },

  // Task APIs
  async triggerCollection(providerId = null) {
    const params = providerId ? { provider_id: providerId } : {}
    const response = await apiClient.post(
      '/v1/cloud-billing/tasks/collect/',
      null,
      { params }
    )
    return response
  },

  async getTaskStatus(taskId) {
    const response = await apiClient.get('/v1/cloud-billing/tasks/status/', {
      params: { task_id: taskId }
    })
    return response
  },

  // Get cloud billing tasks from unified task management (agentcore-task).
  // By default only module=cloud_billing so all task types show: collect_billing_data,
  // send_alert_notification, check_alert_for_provider. Pass task_name in params to filter.
  async getCollectionTasks(params = {}) {
    const queryParams = {
      module: 'cloud_billing',
      my_tasks: 'false',
      ...params
    }
    const response = await apiClient.get('/v1/tasks/executions/', {
      params: queryParams
    })
    return response
  }
}
