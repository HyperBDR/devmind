import apiClient from './index'

export const aiPriceHubApi = {
  async getOverview(platformSlug) {
    return apiClient.get('/v1/ai-pricehub/overview/', {
      params: platformSlug ? { platform_slug: platformSlug } : {}
    })
  },

  async getComparison(primaryModelId, platformSlug) {
    const params = {}
    if (primaryModelId) params.primary_model_id = primaryModelId
    if (platformSlug) params.platform_slug = platformSlug
    return apiClient.get('/v1/ai-pricehub/compare/', {
      params
    })
  },

  async triggerSync() {
    return apiClient.post('/v1/ai-pricehub/sync/')
  }
}
