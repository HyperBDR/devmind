import { userFacingApiError } from './llmOpsErrors.js'

const LIST_PAGE_SIZE = 200

export const LIST_PARAMS = { page_size: LIST_PAGE_SIZE }

export function asArray(value) {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.results)) return value.results
  return []
}

export function asObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value
}

export function extract(response) {
  if (Array.isArray(response)) return response
  const data = response?.data?.data || response?.data || []
  return Array.isArray(data.results) ? data.results : data
}

export function paginationPayload(response) {
  return response?.data?.data || response?.data || []
}

export function paginationResults(payload) {
  return asArray(payload)
}

export async function fetchList(request, params = {}) {
  const firstResponse = await request({
    ...LIST_PARAMS,
    ...params,
    page: 1
  })
  const firstPayload = paginationPayload(firstResponse)
  const results = paginationResults(firstPayload)
  const total = Number(firstPayload?.count || results.length)
  const totalPages = Math.max(1, Math.ceil(total / LIST_PAGE_SIZE))

  if (!firstPayload?.results || totalPages <= 1) {
    return results
  }

  const pageRequests = []
  for (let page = 2; page <= totalPages; page += 1) {
    pageRequests.push(request({ ...LIST_PARAMS, ...params, page }))
  }
  const pageResponses = await Promise.all(pageRequests)
  pageResponses.forEach((response) => {
    results.push(...paginationResults(paginationPayload(response)))
  })
  return results
}

export async function fetchFirstPage(request, params = {}) {
  const response = await request({
    ...params,
    page: 1
  })
  return paginationResults(paginationPayload(response))
}

export function errorMessage(error, fallback) {
  return userFacingApiError(error, fallback)
}
