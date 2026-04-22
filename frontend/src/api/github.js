import api from './index'
import { extractResponseData, extractErrorMessage } from '@/utils/api'

export const githubApi = {
  // Get GitHub trending records list with pagination and filters
  getTrendingRecords(params = {}) {
    return api.get('/github-trending/trending', { params })
  },

  // Get single trending record by ID
  getTrendingRecord(id) {
    return api.get(`/github-trending/trending/${id}`)
  },

  // Get GitHub projects list with pagination and filters
  getProjects(params = {}) {
    return api.get('/github-trending/projects', { params })
  },

  // Get single project by ID
  getProject(id) {
    return api.get(`/github-trending/projects/${id}`)
  }
}

export const {
  getTrendingRecords,
  getTrendingRecord,
  getProjects,
  getProject
} = githubApi
