import apiClient from './index'

export const hyperbdrDashboardApi = {
  /**
   * GET /v1/hyperbdr-dashboard/overview/
   * Returns full dashboard payload: kpis, focus_cards, distribution, funnel, tenant_table.
   * Query params: year, month
   */
  overview(params = {}) {
    return apiClient.get('/v1/hyperbdr-dashboard/overview/', { params })
  },

  /**
   * GET /v1/hyperbdr-dashboard/trends/
   * Query params: days (default 30, max 365)
   */
  trends(params = {}) {
    return apiClient.get('/v1/hyperbdr-dashboard/trends/', { params })
  },

  /**
   * GET /v1/hyperbdr-dashboard/trends/monthly/
   * Query params: year (optional, "all" or integer year)
   */
  monthlyTrends(params = {}) {
    return apiClient.get('/v1/hyperbdr-dashboard/trends/monthly/', { params })
  },

  /**
   * GET /v1/hyperbdr-dashboard/tenants/
   * Query params: skip, limit (for pagination)
   */
  tenants(params = {}) {
    return apiClient.get('/v1/hyperbdr-dashboard/tenants/', { params })
  }
}
