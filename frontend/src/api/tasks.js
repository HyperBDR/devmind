import api from './index'
import { extractResponseData, extractErrorMessage } from '@/utils/api'

export const tasksApi = {
  // Get tasks list with pagination and filters
  getTasks(params = {}) {
    return api.get('/articlehub/tasks', { params })
  },

  // Get single task by ID
  getTask(id) {
    return api.get(`/articlehub/tasks/${id}`)
  },

  // Get task status details
  getTaskStatus(id) {
    return api.get(`/articlehub/tasks/${id}/status/`)
  },

  // Trigger manual collection
  collectArticles(data) {
    return api.post('/articlehub/collect', data)
  },

  // Trigger GitHub trending collection
  collectGithubTrendings(data) {
    return api.post('/articlehub/tasks/collect_github_trendings', data)
  },

  // Get task statistics (counts only, optimized for dashboard)
  getStats() {
    return api.get('/articlehub/tasks/stats')
  },

  // Get task execution time timeline grouped by task type
  getExecutionTimeline(params = {}) {
    return api.get('/articlehub/tasks/execution_timeline', { params })
  }
}

export const {
  getTasks,
  getTask,
  getTaskStatus,
  collectArticles,
  collectGithubTrendings,
  getStats,
  getExecutionTimeline
} = tasksApi
