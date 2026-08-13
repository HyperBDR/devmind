const TIER_SPEC_KEYS = new Set([
  'aggregation_period',
  'tier_charge_mode',
  'tier_metric'
])

const DIMENSION_ORDER = [
  'text_input',
  'text_output',
  'cache_input',
  'image_input',
  'image_output',
  'audio_input',
  'audio_output',
  'video_input',
  'video_output'
]

export function buildSourcePriceSchedules(priceItems = [], labels = {}) {
  const variants = new Map()
  priceItems.forEach((item) => {
    const identity = variantIdentity(item)
    if (!variants.has(identity.key)) {
      variants.set(identity.key, {
        key: identity.key,
        scope_label: identity.label || labels.defaultScope || 'Default',
        sku_code: item.sku_code || '',
        tiers: []
      })
    }
    const variant = variants.get(identity.key)
    const tierKey = [
      item.billing_unit,
      item.tier_type,
      item.tier_start ?? '',
      item.tier_end ?? '',
      stableJson(priceSpec(item.spec))
    ].join('|')
    let tier = variant.tiers.find((candidate) => candidate.key === tierKey)
    if (!tier) {
      tier = {
        key: tierKey,
        billing_unit: item.billing_unit,
        range_label: tierRangeLabel(item, labels),
        prices: []
      }
      variant.tiers.push(tier)
    }
    tier.prices.push({
      dimension: item.dimension,
      currency: item.currency,
      unit_price: item.unit_price
    })
  })

  return Array.from(variants.values())
    .map((variant) => ({
      ...variant,
      tiers: variant.tiers
        .map((tier) => ({
          ...tier,
          prices: tier.prices.sort(dimensionSort)
        }))
        .sort(tierSort)
    }))
    .sort((left, right) => left.scope_label.localeCompare(right.scope_label))
}

export function tierRangeLabel(item, labels = {}) {
  if (item.tier_type !== 'usage_range') {
    return labels.flat || 'All usage'
  }
  const start = compactNumber(item.tier_start ?? 0)
  const end = item.tier_end === null ? '∞' : compactNumber(item.tier_end)
  return `[${start}, ${end})`
}

function variantIdentity(item) {
  const spec = priceSpec(item.spec)
  const scopeParts = [
    item.spec?.deployment_scope,
    item.spec?.region,
    ...Object.entries(spec).map(([key, value]) => `${key}: ${value}`)
  ].filter(Boolean)
  const uniqueParts = Array.from(new Set(scopeParts.map(String)))
  const key = [item.sku_code || '', stableJson(spec), ...uniqueParts].join('|')
  return {
    key,
    label: [item.sku_code, ...uniqueParts].filter(Boolean).join(' · ')
  }
}

function priceSpec(spec = {}) {
  return Object.fromEntries(
    Object.entries(spec || {})
      .filter(([key, value]) => {
        return (
          !TIER_SPEC_KEYS.has(key) &&
          !['currency', 'deployment_scope', 'region'].includes(key) &&
          value !== '' &&
          value !== null &&
          value !== undefined
        )
      })
      .sort(([left], [right]) => left.localeCompare(right))
  )
}

function compactNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value ?? '')
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 6
  }).format(number)
}

function stableJson(value) {
  return JSON.stringify(value || {})
}

function dimensionSort(left, right) {
  return (
    DIMENSION_ORDER.indexOf(left.dimension) -
    DIMENSION_ORDER.indexOf(right.dimension)
  )
}

function tierSort(left, right) {
  const leftStart = Number(left.key.split('|')[2] || 0)
  const rightStart = Number(right.key.split('|')[2] || 0)
  return leftStart - rightStart
}
