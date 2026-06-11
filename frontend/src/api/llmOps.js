import apiClient from './index'

const base = '/v1/llm-ops'

function paramsOrEmpty(params) {
  return params ? { params } : {}
}

export const llmOpsApi = {
  getSummary(params) {
    return apiClient.get(`${base}/summary/`, paramsOrEmpty(params))
  },

  listCollectionSources(params) {
    return apiClient.get(`${base}/collection-sources/`, paramsOrEmpty(params))
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

  listCollectionRuns(params) {
    return apiClient.get(`${base}/collection-runs/`, paramsOrEmpty(params))
  },

  listCollectedPriceSnapshots(params) {
    return apiClient.get(
      `${base}/collected-price-snapshots/`,
      paramsOrEmpty(params)
    )
  },

  listCollectedPriceHistory(params) {
    return apiClient.get(
      `${base}/collected-price-history/`,
      paramsOrEmpty(params)
    )
  },

  collectYunce(payload) {
    return apiClient.post(`${base}/collect/yunce/`, payload)
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

  listChannelModelPriceHistory(params) {
    return apiClient.get(
      `${base}/channel-model-price-history/`,
      paramsOrEmpty(params)
    )
  },

  listChannelPriceItems(params) {
    return apiClient.get(`${base}/channel-price-items/`, paramsOrEmpty(params))
  },

  createChannelModelPrice(payload) {
    return apiClient.post(`${base}/channel-model-prices/`, payload)
  },

  bulkUpsertChannelModelPrices(items) {
    return apiClient.post(`${base}/channel-model-prices/bulk-upsert/`, {
      items
    })
  },

  syncChannelPriceItems(payload) {
    return apiClient.post(
      `${base}/channel-model-prices/sync-price-items/`,
      payload
    )
  },

  updateChannelModelPrice(id, payload) {
    return apiClient.patch(`${base}/channel-model-prices/${id}/`, payload)
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

  listResaleListings(params) {
    return apiClient.get(`${base}/resale-listings/`, paramsOrEmpty(params))
  },

  listResaleListingExclusions(params) {
    return apiClient.get(
      `${base}/resale-listing-exclusions/`,
      paramsOrEmpty(params)
    )
  },

  listResaleListingPriceHistory(params) {
    return apiClient.get(
      `${base}/resale-listing-price-history/`,
      paramsOrEmpty(params)
    )
  },

  createResaleListing(payload) {
    return apiClient.post(`${base}/resale-listings/`, payload)
  },

  bulkUpsertResaleListings(items) {
    return apiClient.post(`${base}/resale-listings/bulk-upsert/`, { items })
  },

  bulkReplaceResaleListings(items) {
    return apiClient.post(`${base}/resale-listings/bulk-replace/`, { items })
  },

  bulkOfflineResaleListings(payload) {
    return apiClient.post(`${base}/resale-listings/bulk-offline/`, payload)
  },

  bulkRemoveResaleListingModels(payload) {
    return apiClient.post(
      `${base}/resale-listing-exclusions/bulk-upsert/`,
      payload
    )
  },

  bulkRestoreResaleListingModels(payload) {
    return apiClient.post(
      `${base}/resale-listing-exclusions/bulk-restore/`,
      payload
    )
  },

  updateResaleListing(id, payload) {
    return apiClient.patch(`${base}/resale-listings/${id}/`, payload)
  },

  deleteResaleListing(id) {
    return apiClient.delete(`${base}/resale-listings/${id}/`)
  },

  listReconciliationRecords(params) {
    return apiClient.get(
      `${base}/reconciliation-records/`,
      paramsOrEmpty(params)
    )
  },

  createReconciliationRecord(payload) {
    return apiClient.post(`${base}/reconciliation-records/`, payload)
  },

  deleteReconciliationRecord(id) {
    return apiClient.delete(`${base}/reconciliation-records/${id}/`)
  }
}
