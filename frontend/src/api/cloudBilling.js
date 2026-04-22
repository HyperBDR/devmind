import apiClient from './index'

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

  async syncProviderRechargeInfoFromFeishu(id, data = {}) {
    const response = await apiClient.post(
      `/v1/cloud-billing/providers/${id}/sync-recharge-info-from-feishu/`,
      data
    )
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
