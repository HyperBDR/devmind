import apiClient from './index'

const base = '/v1/llm-ops'

function paramsOrEmpty(params) {
  return params ? { params } : {}
}

export const llmOpsApi = {
  getSummary(params) {
    return apiClient.get(`${base}/summary/`, paramsOrEmpty(params))
  },

  listAuditLogs(params) {
    return apiClient.get(`${base}/audit-logs/`, paramsOrEmpty(params))
  },

  listCollectionSources(params) {
    return apiClient.get(`${base}/collection-sources/`, paramsOrEmpty(params))
  },

  listOfficialProviderSourceOptions() {
    return apiClient.get(
      `${base}/collection-sources/official-provider-options/`
    )
  },

  listAutoSyncSourceOptions() {
    return apiClient.get(`${base}/collection-sources/auto-sync-options/`)
  },

  ensureOfficialProviderSource(providerCode) {
    return apiClient.post(`${base}/collection-sources/official-provider/`, {
      provider_code: providerCode
    })
  },

  createCollectionSource(payload) {
    return apiClient.post(`${base}/collection-sources/`, payload)
  },

  updateCollectionSource(id, payload) {
    return apiClient.patch(`${base}/collection-sources/${id}/`, payload)
  },

  deleteCollectionSource(id) {
    return apiClient.delete(`${base}/collection-sources/${id}/`)
  },

  collectCollectionSource(id) {
    return apiClient.post(`${base}/collection-sources/${id}/collect/`)
  },

  syncAllCollectionSources() {
    return apiClient.post(`${base}/collection-sources/sync-all/`)
  },

  previewOfficialPriceReset(payload) {
    return apiClient.post(
      `${base}/collection-sources/reset-official-prices-preview/`,
      payload
    )
  },

  resetOfficialPrices(payload) {
    return apiClient.post(
      `${base}/collection-sources/reset-official-prices/`,
      payload
    )
  },

  getGlobalConfig() {
    return apiClient.get(`${base}/global-config/`)
  },

  updateGlobalConfig(payload) {
    return apiClient.patch(`${base}/global-config/`, payload)
  },

  resetGlobalConfig() {
    return apiClient.delete(`${base}/global-config/`)
  },

  listCollectionRuns(params) {
    return apiClient.get(`${base}/collection-runs/`, paramsOrEmpty(params))
  },

  importManualPrices(payload) {
    return apiClient.post(`${base}/manual-price-import/`, payload)
  },

  listProviders(params) {
    return apiClient.get(`${base}/providers/`, paramsOrEmpty(params))
  },

  createProvider(payload) {
    return apiClient.post(`${base}/providers/`, payload)
  },

  updateProvider(id, payload) {
    return apiClient.patch(`${base}/providers/${id}/`, payload)
  },

  deleteProvider(id) {
    return apiClient.delete(`${base}/providers/${id}/`)
  },

  listModels(params) {
    return apiClient.get(`${base}/models/`, paramsOrEmpty(params))
  },

  listMetaModels(params) {
    return apiClient.get(`${base}/meta-models/`, paramsOrEmpty(params))
  },

  listMetaModelOwnerSummary(params) {
    return apiClient.get(
      `${base}/meta-models/owner-summary/`,
      paramsOrEmpty(params)
    )
  },

  syncMetaModels() {
    return apiClient.post(`${base}/meta-models/sync/`)
  },

  createMetaModel(payload) {
    return apiClient.post(`${base}/meta-models/`, payload)
  },

  updateMetaModel(id, payload) {
    return apiClient.patch(`${base}/meta-models/${id}/`, payload)
  },

  deleteMetaModel(id) {
    return apiClient.delete(`${base}/meta-models/${id}/`)
  },

  listModelPriceItems(params) {
    return apiClient.get(`${base}/model-price-items/`, paramsOrEmpty(params))
  },

  updateModelPriceItem(id, payload) {
    return apiClient.patch(`${base}/model-price-items/${id}/`, payload)
  },

  deleteModelPriceItem(id) {
    return apiClient.delete(`${base}/model-price-items/${id}/`)
  },

  createModel(payload) {
    return apiClient.post(`${base}/models/`, payload)
  },

  updateModel(id, payload) {
    return apiClient.patch(`${base}/models/${id}/`, payload)
  },

  deleteModel(id) {
    return apiClient.delete(`${base}/models/${id}/`)
  },

  listChannels(params) {
    return apiClient.get(`${base}/channels/`, paramsOrEmpty(params))
  },

  createChannel(payload) {
    return apiClient.post(`${base}/channels/`, payload)
  },

  updateChannel(id, payload) {
    return apiClient.patch(`${base}/channels/${id}/`, payload)
  },

  deleteChannel(id) {
    return apiClient.delete(`${base}/channels/${id}/`)
  },

  listChannelModelPrices(params) {
    return apiClient.get(`${base}/channel-model-prices/`, paramsOrEmpty(params))
  },

  listChannelPriceItems(params) {
    return apiClient.get(`${base}/channel-price-items/`, paramsOrEmpty(params))
  },

  listChannelModelPriceHistory(params) {
    return apiClient.get(
      `${base}/channel-model-price-history/`,
      paramsOrEmpty(params)
    )
  },

  bulkUpsertChannelModelPrices(items) {
    return apiClient.post(`${base}/channel-model-prices/bulk-upsert/`, {
      items
    })
  },

  deleteChannelModelPrice(id) {
    return apiClient.delete(`${base}/channel-model-prices/${id}/`)
  },

  listResalePlatforms(params) {
    return apiClient.get(`${base}/resale-platforms/`, paramsOrEmpty(params))
  },

  createResalePlatform(payload) {
    return apiClient.post(`${base}/resale-platforms/`, payload)
  },

  updateResalePlatform(id, payload) {
    return apiClient.patch(`${base}/resale-platforms/${id}/`, payload)
  },

  getResaleWorkflowConfig(platformId) {
    return apiClient.get(`${base}/resale-workflow-configs/effective/`, {
      params: { platform: platformId }
    })
  },

  updateResaleWorkflowConfig(platformId, payload) {
    return apiClient.patch(
      `${base}/resale-workflow-configs/effective/`,
      payload,
      { params: { platform: platformId } }
    )
  },

  resetResaleWorkflowConfig(platformId) {
    return apiClient.delete(`${base}/resale-workflow-configs/effective/`, {
      params: { platform: platformId }
    })
  },

  listResaleListings(params) {
    return apiClient.get(`${base}/resale-listings/`, paramsOrEmpty(params))
  },

  listResaleListingPriceHistory(params) {
    return apiClient.get(
      `${base}/resale-listing-price-history/`,
      paramsOrEmpty(params)
    )
  },

  bulkUpsertResaleListings(items) {
    return apiClient.post(`${base}/resale-listings/bulk-upsert/`, { items })
  },

  bulkDraftResaleListings(items) {
    return apiClient.post(`${base}/resale-listings/bulk-draft/`, { items })
  },

  bulkOfflineResaleListings(payload) {
    return apiClient.post(`${base}/resale-listings/bulk-offline/`, payload)
  },

  bulkTransitionResaleListings(payload) {
    return apiClient.post(`${base}/resale-listings/bulk-transition/`, payload)
  },

  listReconciliationRecords(params) {
    return apiClient.get(
      `${base}/reconciliation-records/`,
      paramsOrEmpty(params)
    )
  },

  createReconciliationRecord(payload) {
    return apiClient.post(`${base}/reconciliation-records/`, payload)
  }
}
