import api from './index'
import { extractResponseData, extractErrorMessage } from '@/utils/api'

export const articlesApi = {
  // Get articles list with pagination, search and filters
  getArticles(params = {}) {
    return api.get('/articlehub/articles', { params })
  },

  // Get single article by ID
  getArticle(id) {
    return api.get(`/articlehub/articles/${id}`)
  },

  // Retry processing an article
  retryArticle(id, force = false) {
    return api.post(`/articlehub/articles/${id}/retry`, { force })
  },

  // Upload article to object storage
  uploadArticle(id, force = false) {
    return api.post(`/articlehub/articles/${id}/upload`, { force })
  },

  // Batch retry articles
  batchRetryArticles(ids) {
    return Promise.all(ids.map((id) => this.retryArticle(id)))
  },

  // Delete article (if supported by backend)
  deleteArticle(id) {
    return api.delete(`/articlehub/articles/${id}`)
  },

  // Batch delete articles
  batchDeleteArticles(ids) {
    return Promise.all(ids.map((id) => this.deleteArticle(id)))
  },

  // Get article statistics (counts only, optimized for dashboard)
  getStats() {
    return api.get('/articlehub/articles/stats')
  },

  // Get article collection timeline data for charts
  getCollectionTimeline(params = {}) {
    return api.get('/articlehub/articles/collection_timeline', { params })
  },

  // Get list of all available social_account values
  getSocialAccounts() {
    return api.get('/articlehub/articles/social_accounts')
  }
}

export const {
  getArticles,
  getArticle,
  retryArticle,
  batchRetryArticles,
  uploadArticle,
  deleteArticle,
  batchDeleteArticles,
  getStats,
  getCollectionTimeline,
  getSocialAccounts
} = articlesApi
