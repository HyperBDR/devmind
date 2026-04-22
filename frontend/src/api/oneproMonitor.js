import apiClient from './index'

const BASE = '/v1/onepro-monitor'

function getFilenameFromDisposition(disposition, fallback) {
  if (!disposition) return fallback
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const simpleMatch = disposition.match(/filename="?([^"]+)"?/i)
  return simpleMatch?.[1] || fallback
}

export const oneproMonitorApi = {
  dashboard(params = {}) {
    return apiClient.get(`${BASE}/analyzer/dashboard/`, { params })
  },

  tenantStatus(params = {}) {
    return apiClient.get(`${BASE}/analyzer/tenant-status/`, { params })
  },

  licenseUsage(params = {}) {
    return apiClient.get(`${BASE}/analyzer/license-usage/`, { params })
  },

  hostPerformance(params = {}) {
    return apiClient.get(`${BASE}/analyzer/host-performance/`, { params })
  },

  taskExecution(params = {}) {
    return apiClient.get(`${BASE}/analyzer/task-execution/`, { params })
  },

  dataSources: {
    list(params = {}) {
      return apiClient.get(`${BASE}/data-sources/`, { params })
    },
    get(id) {
      return apiClient.get(`${BASE}/data-sources/${id}/`)
    },
    create(data) {
      return apiClient.post(`${BASE}/data-sources/`, data)
    },
    update(id, data) {
      return apiClient.put(`${BASE}/data-sources/${id}/`, data)
    },
    patch(id, data) {
      return apiClient.patch(`${BASE}/data-sources/${id}/`, data)
    },
    delete(id) {
      return apiClient.delete(`${BASE}/data-sources/${id}/`)
    },
    collect(id) {
      return apiClient.post(`${BASE}/data-sources/${id}/collect/`)
    }
  },

  tenants: {
    list(params = {}) {
      return apiClient.get(`${BASE}/tenants/`, { params })
    },
    get(id) {
      return apiClient.get(`${BASE}/tenants/${id}/`)
    }
  },

  licenses: {
    list(params = {}) {
      return apiClient.get(`${BASE}/licenses/`, { params })
    }
  },

  hosts: {
    list(params = {}) {
      return apiClient.get(`${BASE}/hosts/`, { params })
    },
    async export(params = {}) {
      const response = await apiClient.get(`${BASE}/hosts/export/`, {
        params,
        responseType: 'blob'
      })
      const url = window.URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = getFilenameFromDisposition(
        response.headers['content-disposition'],
        'onepro-hosts.csv'
      )
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      a.remove()
      return a.download
    }
  },

  tasks: {
    list(params = {}) {
      return apiClient.get(`${BASE}/tasks/`, { params })
    },
    get(id) {
      return apiClient.get(`${BASE}/tasks/${id}/`)
    },
    collect(data = {}) {
      return apiClient.post(`${BASE}/tasks/collect/`, data)
    }
  },

  health() {
    return apiClient.get(`${BASE}/health/`)
  }
}
