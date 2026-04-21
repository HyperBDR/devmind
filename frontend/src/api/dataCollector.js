import apiClient from './index'

const BASE = '/v1/data-collector'

export const dataCollectorApi = {
  async getStats(params = {}) {
    const response = await apiClient.get(`${BASE}/stats/`, { params })
    return response
  },

  async getConfigs(params = {}) {
    const response = await apiClient.get(`${BASE}/configs/`, { params })
    return response
  },

  async getConfig(uuid) {
    const response = await apiClient.get(`${BASE}/configs/${uuid}/`)
    return response
  },

  async createConfig(data) {
    const response = await apiClient.post(`${BASE}/configs/`, data)
    return response
  },

  async updateConfig(uuid, data) {
    const response = await apiClient.put(`${BASE}/configs/${uuid}/`, data)
    return response
  },

  async patchConfig(uuid, data) {
    const response = await apiClient.patch(`${BASE}/configs/${uuid}/`, data)
    return response
  },

  async deleteConfig(uuid) {
    const response = await apiClient.delete(`${BASE}/configs/${uuid}/`)
    return response
  },

  async triggerCollect(uuid, payload = {}) {
    const response = await apiClient.post(
      `${BASE}/configs/${uuid}/collect/`,
      payload
    )
    return response
  },

  async validateConfigPayload(platform, value) {
    const response = await apiClient.post(`${BASE}/configs/validate-config/`, {
      platform,
      value
    })
    return response
  },

  async validateConfig(uuid) {
    const response = await apiClient.post(
      `${BASE}/configs/${uuid}/validate-config/`
    )
    return response
  },

  async fetchProjects(platform, value, configUuid = null) {
    const payload = { platform }
    if (configUuid) {
      payload.config_uuid = configUuid
    } else {
      payload.value = value
    }
    const response = await apiClient.post(
      `${BASE}/configs/fetch-projects/`,
      payload
    )
    return response
  },

  async getLlmOptions() {
    const response = await apiClient.get(`${BASE}/configs/llm-options/`)
    return response
  },

  async triggerValidate(uuid, payload = {}) {
    const response = await apiClient.post(
      `${BASE}/configs/${uuid}/validate/`,
      payload
    )
    return response
  },

  async getRecords(params = {}) {
    const response = await apiClient.get(`${BASE}/records/`, { params })
    return response
  },

  async getRecord(uuid) {
    const response = await apiClient.get(`${BASE}/records/${uuid}/`)
    return response
  },

  async getAttachments(params = {}) {
    const response = await apiClient.get(`${BASE}/attachments/`, { params })
    return response
  },

  async getAttachment(uuid) {
    const response = await apiClient.get(`${BASE}/attachments/${uuid}/`)
    return response
  },

  getAttachmentDownloadUrl(uuid) {
    return `${apiClient.defaults.baseURL}${BASE}/attachments/${uuid}/download/`
  },

  async getAttachmentBlob(uuid) {
    const response = await apiClient.get(
      `${BASE}/attachments/${uuid}/download/`,
      {
        responseType: 'blob'
      }
    )
    if (response.status !== 200) {
      const text = (await response.data.text?.()) || response.data
      throw new Error(text || `Request failed: ${response.status}`)
    }
    return response.data
  },

  async downloadAttachment(uuid, filename) {
    const blob = await this.getAttachmentBlob(uuid)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'download'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    a.remove()
  },

  async getExecutions(params = {}) {
    const response = await apiClient.get('/v1/tasks/executions/', {
      params: { module: 'data_collector', ...params }
    })
    return response
  },

  async getExecution(id, params = {}) {
    const response = await apiClient.get(`/v1/tasks/executions/${id}/`, {
      params
    })
    return response
  }
}
