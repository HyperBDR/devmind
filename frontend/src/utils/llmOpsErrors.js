const TECHNICAL_ERROR_PATTERNS = [
  /<\/?(?:html|head|body|title|h1|pre|center)\b/i,
  /bad gateway/i,
  /gateway timeout/i,
  /request failed with status code/i,
  /network error/i
]

export function userFacingApiError(error, fallback) {
  const status = Number(error?.response?.status || 0)
  if (status >= 500) return fallback

  const data = error?.response?.data
  const candidates = [data?.detail, data?.message, data, error?.message]
  const message = candidates.find(
    (value) => typeof value === 'string' && value.trim()
  )

  if (!message) return fallback

  const normalized = message.trim().replace(/\s+/g, ' ')
  if (
    normalized.length > 240 ||
    TECHNICAL_ERROR_PATTERNS.some((pattern) => pattern.test(normalized))
  ) {
    return fallback
  }

  return normalized
}
