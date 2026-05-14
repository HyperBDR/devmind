import apiClient from './index'

export const salsApi = {
  async getDashboard() {
    const response = await apiClient.get('/v1/sals/dashboard/')
    return response
  },

  async getKpi() {
    const response = await apiClient.get('/v1/sals/stats/kpi/')
    return response
  },

  async getPriorityDist() {
    const response = await apiClient.get('/v1/sals/stats/priority-dist/')
    return response
  },

  async getStateDist() {
    const response = await apiClient.get('/v1/sals/stats/state-dist/')
    return response
  },

  async getMonthlyTrend() {
    const response = await apiClient.get('/v1/sals/stats/monthly-trend/')
    return response
  },

  async getGroupStats() {
    const response = await apiClient.get('/v1/sals/stats/group-stats/')
    return response
  },

  async getAssigneeStats(params = {}) {
    const response = await apiClient.get('/v1/sals/stats/assignee-stats/', { params })
    return response
  },

  async getCustomerStats(params = {}) {
    const response = await apiClient.get('/v1/sals/stats/customer-stats/', { params })
    return response
  },

  async getProductStats() {
    const response = await apiClient.get('/v1/sals/stats/product-stats/')
    return response
  },

  async getSlaStats() {
    const response = await apiClient.get('/v1/sals/stats/sla-stats/')
    return response
  },

  async getEscalationStats() {
    const response = await apiClient.get('/v1/sals/stats/escalation/')
    return response
  },

  async getProductStateMatrix() {
    const response = await apiClient.get('/v1/sals/stats/product-state-matrix/')
    return response
  },

  async getRecentIncidents(params = {}) {
    const response = await apiClient.get('/v1/sals/incidents/recent/', { params })
    return response
  },

  async getIncidents(params = {}) {
    const response = await apiClient.get('/v1/sals/incidents/', { params })
    return response
  },

  async syncDb(source = 'api', fullSync = false) {
    const response = await apiClient.post('/v1/sals/init-db/', null, {
      params: { source, full_sync: fullSync }
    })
    return response
  },

  async getSyncStatus() {
    const response = await apiClient.get('/v1/sals/sync/status/')
    return response
  },

  async getSyncTaskStatus(taskId) {
    const response = await apiClient.get('/v1/sals/sync/task-status/', {
      params: { task_id: taskId }
    })
    return response
  }
}
