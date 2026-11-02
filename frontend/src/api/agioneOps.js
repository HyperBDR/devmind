import apiClient from './index'

const base = '/v1/agione-ops/connections'
const connectionPath = (id) => `${base}/${encodeURIComponent(id)}`

export const agioneOpsApi = {
  notificationRules(id) {
    return apiClient.get(`${connectionPath(id)}/notification-rules/`)
  },
  saveNotificationRules(id, body) {
    return apiClient.put(`${connectionPath(id)}/notification-rules/`, body)
  },
  tenantClassifications(id, params = {}) {
    return apiClient.get(`${connectionPath(id)}/tenant-classifications/`, {
      params
    })
  },
  updateTenantClassification(id, body) {
    return apiClient.post(`${connectionPath(id)}/tenant-classifications/`, body)
  },
  connections({ offset = 0 } = {}) {
    return apiClient.get(`${base}/`, { params: { limit: 100, offset } })
  },
  createConnection(body) {
    return apiClient.post(`${base}/`, body)
  },
  updateConnection(id, body) {
    return apiClient.patch(`${connectionPath(id)}/`, body)
  },
  createPersonalConnection(body) {
    return apiClient.post(`${base}/self-service/`, body)
  },
  updatePersonalConnection(id, body) {
    return apiClient.patch(
      `${base}/self-service/${encodeURIComponent(id)}/`,
      body
    )
  },
  disconnectPersonalConnection(id) {
    return apiClient.delete(`${base}/self-service/${encodeURIComponent(id)}/`)
  },
  grantConnection(id, userId, body) {
    return apiClient.put(
      `${connectionPath(id)}/grants/${encodeURIComponent(userId)}/`,
      body
    )
  },
  verifyConnection(id) {
    return apiClient.post(`${connectionPath(id)}/verify/`, {})
  },
  refreshFinance(id) {
    return apiClient.post(`${connectionPath(id)}/finance/refresh/`, {})
  },
  liveQuery(id, body, config = {}) {
    return apiClient.post(`${connectionPath(id)}/live/query/`, body, config)
  },
  dashboard(id, dataVersion, window) {
    return apiClient.post(
      `${connectionPath(id)}/dashboard/query/`,
      dataVersion ? { dataVersion } : window ? { window } : {}
    )
  },
  snapshotQuery(id, body, config = {}) {
    return apiClient.post(`${connectionPath(id)}/snapshot/query/`, body, config)
  },
  submitSync(id, window, idempotencyKey) {
    return apiClient.post(
      `${connectionPath(id)}/sync-runs/`,
      {
        kind: 'current',
        window
      },
      { headers: { 'Idempotency-Key': idempotencyKey } }
    )
  },
  run(id, runId) {
    return apiClient.get(
      `${connectionPath(id)}/sync-runs/${encodeURIComponent(runId)}/`
    )
  }
}
