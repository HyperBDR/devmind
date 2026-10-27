import apiClient from './index'

const base = '/v1/agione-ops/connections'
const connectionPath = (id) => `${base}/${encodeURIComponent(id)}`

export const agioneOpsApi = {
  connections({ offset = 0 } = {}) {
    return apiClient.get(`${base}/`, { params: { limit: 100, offset } })
  },
  createConnection(body) {
    return apiClient.post(`${base}/`, body)
  },
  updateConnection(id, body) {
    return apiClient.patch(`${connectionPath(id)}/`, body)
  },
  grantConnection(id, userId, body) {
    return apiClient.put(`${connectionPath(id)}/grants/${encodeURIComponent(userId)}/`, body)
  },
  verifyConnection(id) {
    return apiClient.post(`${connectionPath(id)}/verify/`, {})
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
    return apiClient.post(
      `${connectionPath(id)}/snapshot/query/`, body, config
    )
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
