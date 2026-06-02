import apiClient from '@/api/index'
import { extractResponseData } from '@/utils/api'

export const externalProxyAdminApi = {
  getSites() {
    return apiClient
      .get('/v1/admin/external-proxy/sites/')
      .then(extractResponseData)
  },
  postSite(payload) {
    return apiClient
      .post('/v1/admin/external-proxy/sites/', payload)
      .then(extractResponseData)
  },
  putSite(id, payload) {
    return apiClient
      .put(`/v1/admin/external-proxy/sites/${id}/`, payload)
      .then(extractResponseData)
  },
  patchSite(id, payload) {
    return apiClient
      .patch(`/v1/admin/external-proxy/sites/${id}/`, payload)
      .then(extractResponseData)
  },
  deleteSite(id) {
    return apiClient.delete(`/v1/admin/external-proxy/sites/${id}/`)
  },
  launchSite(id) {
    return apiClient
      .post(`/v1/admin/external-proxy/sites/${id}/launch/`)
      .then(extractResponseData)
  }
}
