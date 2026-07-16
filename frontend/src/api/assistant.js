import apiClient from './index'
import { readDataOpsSseResponse } from '@/utils/dataOpsAiStream'

const base = '/v1/assistant'

function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return null
}

async function postSse(path, payload, callbacks, signal) {
  const baseURL = apiClient.defaults.baseURL || ''
  const url = `${baseURL.replace(/\/$/, '')}${path}`
  const token = localStorage.getItem('access_token')
  const csrf = getCookie('csrftoken')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (csrf) headers['X-CSRFToken'] = csrf

  const response = await fetch(url, {
    body: JSON.stringify(payload),
    credentials: 'include',
    headers,
    method: 'POST',
    signal
  })
  if (!response.ok) {
    let detail = response.statusText || 'Assistant request failed'
    try {
      const body = await response.json()
      detail = body?.error?.message || body?.detail || detail
    } catch (_) {
      // Ignore non-JSON error responses.
    }
    throw new Error(detail)
  }
  return readDataOpsSseResponse(response, callbacks)
}

export const assistantApi = {
  capabilities() {
    return apiClient.get(`${base}/capabilities/`)
  },

  conversations(appKey) {
    return apiClient.get(`${base}/conversations/`, {
      params: { app_key: appKey }
    })
  },

  createConversation(appKey) {
    return apiClient.post(`${base}/conversations/`, {
      app_key: appKey
    })
  },

  deleteConversation(conversationId) {
    return apiClient.delete(`${base}/conversations/${conversationId}/`)
  },

  messages(conversationId) {
    return apiClient.get(`${base}/conversations/${conversationId}/messages/`)
  },

  streamMessage(conversationId, payload, callbacks, signal) {
    return postSse(
      `${base}/conversations/${conversationId}/messages/`,
      payload,
      callbacks,
      signal
    )
  }
}
