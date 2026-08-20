const TOKEN_KEY = 'access_token'
const LEGACY_TOKEN_KEY = 'qmp_access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

let refreshPromise: Promise<string> | null = null

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY)
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
}

function clearPlatformAuth(): void {
  clearAccessToken()
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function getApiBaseUrl(): string {
  const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
  const origin =
    rawBase && rawBase.length > 0
      ? rawBase.replace(/\/api(?:\/v\d+)?\/?$/, '').replace(/\/$/, '')
      : window.location.origin
  return `${origin}/api/v1/quotation`
}

function getPlatformApiBaseUrl(): string {
  return getApiBaseUrl().replace(/\/api\/v1\/quotation$/, '')
}

function redirectToLogin(): void {
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

export class ApiError extends Error {
  status: number
  data?: unknown

  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.status = status
    this.data = data
  }
}

function unwrapResponse<T>(payload: unknown): T {
  if (
    payload &&
    typeof payload === 'object' &&
    'code' in payload &&
    'data' in payload
  ) {
    return (payload as { data: T }).data
  }
  return payload as T
}

function extractDetail(payload: unknown, fallback: string): string {
  const unwrapped = unwrapResponse<any>(payload)
  const candidates = [
    unwrapped?.detail,
    unwrapped?.message,
    (payload as any)?.detail,
    (payload as any)?.message,
  ]
  const detail = candidates.find(Boolean)
  if (Array.isArray(detail)) return String(detail[0])
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return typeof detail === 'string' ? detail : fallback
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshToken) {
    clearPlatformAuth()
    redirectToLogin()
    throw new ApiError('Authentication required', 401)
  }

  if (!refreshPromise) {
    refreshPromise = (async () => {
      const response = await fetch(
        `${getPlatformApiBaseUrl()}/api/v1/auth/token/refresh`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh: refreshToken }),
        },
      )

      let payload: unknown
      try {
        payload = await response.json()
      } catch {
        payload = undefined
      }

      if (!response.ok) {
        if (response.status === 400 || response.status === 401) {
          clearPlatformAuth()
          redirectToLogin()
          throw new ApiError('Authentication required', response.status)
        }
        throw new ApiError(
          'Authentication service unavailable',
          response.status,
        )
      }

      const data = unwrapResponse<{ access?: string }>(payload)
      if (!data?.access) {
        clearPlatformAuth()
        redirectToLogin()
        throw new ApiError('Authentication required', 401)
      }

      setAccessToken(data.access)
      return data.access
    })().finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

function isLoginRequest(path: string): boolean {
  return path === '/auth/login'
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  allowRefresh = true,
): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401 && allowRefresh && !isLoginRequest(path)) {
    const newAccessToken = await refreshAccessToken()
    const retryHeaders = new Headers(options.headers || {})
    if (!retryHeaders.has('Content-Type') && !(options.body instanceof FormData)) {
      retryHeaders.set('Content-Type', 'application/json')
    }
    retryHeaders.set('Authorization', `Bearer ${newAccessToken}`)
    return apiRequest(path, { ...options, headers: retryHeaders }, false)
  }

  if (response.status === 204) {
    if (!response.ok) {
      throw new ApiError(`Request failed (${response.status})`, response.status)
    }
    return undefined as T
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    payload = undefined
  }

  if (!response.ok) {
    const fallback = `Request failed (${response.status})`
    throw new ApiError(extractDetail(payload, fallback), response.status, unwrapResponse(payload))
  }

  return unwrapResponse<T>(payload)
}
