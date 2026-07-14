function formatCompactAmount(value, locale) {
  const amount = Number(value || 0)
  const absoluteAmount = Math.abs(amount)
  if (locale.startsWith('zh') && absoluteAmount >= 100000000) {
    return `${(amount / 100000000).toFixed(1)}亿`
  }
  if (locale.startsWith('zh') && absoluteAmount >= 10000) {
    return `${(amount / 10000).toFixed(1)}万`
  }
  return new Intl.NumberFormat(locale, {
    notation: locale.startsWith('zh') ? 'standard' : 'compact',
    maximumFractionDigits: 1
  }).format(amount)
}

export function formatAmount(value, currency = '', options = {}) {
  if (value === null || value === undefined || value === '') return '-'
  const locale = options.locale || 'zh-CN'
  const text = options.compact
    ? formatCompactAmount(value, locale)
    : new Intl.NumberFormat(locale, {
        maximumFractionDigits: 2
      }).format(Number(value || 0))
  return currency ? `${currency} ${text}` : text
}

export function formatAmountByCurrency(value, items, options = {}) {
  if (Array.isArray(items) && items.length) {
    const nonZeroItems = items.filter((item) => Number(item.amount || 0) !== 0)
    const displayItems = nonZeroItems.length ? nonZeroItems : items
    return displayItems
      .map((item) => formatAmount(item.amount, item.currency, options))
      .join(' / ')
  }
  if (value === null || value === undefined) return '—'
  return formatAmount(value, options.fallbackCurrency || '', options)
}

export function hasNonZeroAmount(value, items) {
  if (Array.isArray(items) && items.length) {
    return items.some((item) => Number(item.amount || 0) !== 0)
  }
  return Number(value || 0) !== 0
}

export function hasMixedCurrencies(items) {
  const currencies = new Set(
    (items || []).map((item) => item.currency || '未知')
  )
  return currencies.size > 1
}

export function topAmountsByCurrency(items, amountKey, limit = 10) {
  const groups = new Map()
  for (const item of items || []) {
    const currency = item.currency || '未知'
    const rows = groups.get(currency) || []
    rows.push(item)
    groups.set(currency, rows)
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([, rows]) =>
      rows
        .sort(
          (left, right) =>
            Number(right[amountKey] || 0) - Number(left[amountKey] || 0)
        )
        .slice(0, limit)
    )
}
