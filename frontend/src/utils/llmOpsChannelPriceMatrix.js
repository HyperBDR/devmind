const DEFAULT_STALE_AFTER_MS = 24 * 60 * 60 * 1000

const PRICE_FIELDS = {
  input: 'input_price_per_million',
  output: 'output_price_per_million'
}

export function optionFreshness(
  option = {},
  now = Date.now(),
  staleAfterMs = DEFAULT_STALE_AFTER_MS
) {
  const value = option.price_updated_at || option.updated_at
  if (!value) return { ageMs: null, state: 'unknown', updatedAt: null }

  const updatedAt = new Date(value).getTime()
  if (!Number.isFinite(updatedAt)) {
    return { ageMs: null, state: 'unknown', updatedAt: null }
  }

  const ageMs = Math.max(0, Number(now) - updatedAt)
  return {
    ageMs,
    state: ageMs > staleAfterMs ? 'stale' : 'fresh',
    updatedAt
  }
}

export function hasStaleChannelPrice(row = {}, now = Date.now()) {
  return (row.options || []).some(
    (option) => optionFreshness(option, now).state === 'stale'
  )
}

export function effectiveMatrixAction(row = {}, now = Date.now()) {
  if (hasStaleChannelPrice(row, now)) return 'refresh_prices'
  return row.decision_action || 'keep'
}

export function compareChannelOptions(row = {}, dimension = 'input') {
  const field = PRICE_FIELDS[dimension] || PRICE_FIELDS.input
  return (row.options || [])
    .filter((option) => {
      if (
        option[field] === null ||
        option[field] === undefined ||
        option[field] === ''
      ) {
        return false
      }
      const value = Number(option[field])
      return Number.isFinite(value) && value >= 0
    })
    .slice()
    .sort((left, right) => Number(left[field]) - Number(right[field]))
}

export function optionsForChannel(row = {}, channelId) {
  return (row.options || [])
    .filter((option) => String(option.channel_id) === String(channelId))
    .slice()
    .sort((left, right) => {
      const leftCost = Number(left.estimated_cost)
      const rightCost = Number(right.estimated_cost)
      if (Number.isFinite(leftCost) && Number.isFinite(rightCost)) {
        return leftCost - rightCost
      }
      return String(left.offering_name || '').localeCompare(
        String(right.offering_name || '')
      )
    })
}

export function bestOptionForChannel(row = {}, channelId) {
  return optionsForChannel(row, channelId)[0] || null
}

export function channelOfferingForOption(offerings = [], option = {}) {
  return (
    offerings.find(
      (offering) =>
        String(offering.channel) === String(option.channel_id) &&
        String(offering.id) === String(option.offering_id)
    ) || null
  )
}

export function savingsPercent(row = {}, dimension = 'input') {
  const channelId = row.current_listing?.channel_id
  if (channelId === null || channelId === undefined) return null

  const field = PRICE_FIELDS[dimension] || PRICE_FIELDS.input
  const current = (row.options || []).find(
    (option) => String(option.channel_id) === String(channelId)
  )
  const lowest = compareChannelOptions(row, dimension)[0]
  const currentPrice = Number(current?.[field])
  const lowestPrice = Number(lowest?.[field])
  if (
    !Number.isFinite(currentPrice) ||
    !Number.isFinite(lowestPrice) ||
    currentPrice <= 0
  ) {
    return null
  }
  return Math.max(0, ((currentPrice - lowestPrice) / currentPrice) * 100)
}
