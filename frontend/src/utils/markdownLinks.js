export function relativizeSameOriginUrls(value, origin) {
  const content = String(value || '')
  const normalizedOrigin = String(origin || '').replace(/\/+$/u, '')
  if (!content || !normalizedOrigin) return content

  const originPattern = new RegExp(
    `${escapeRegExp(normalizedOrigin)}(?=/)`,
    'giu'
  )
  return content.replace(originPattern, '')
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
}
