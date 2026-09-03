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
    const identity = variantIdentity(item, labels)
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
      stableJson(priceSpec(item.spec)),
      stableJson(pricingCondition(item))
    ].join('|')
    let tier = variant.tiers.find((candidate) => candidate.key === tierKey)
    if (!tier) {
      tier = {
        key: tierKey,
        billing_unit: item.billing_unit,
        range_label: tierRangeLabel(item, labels),
        pricing_condition: pricingCondition(item),
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
  const condition = pricingCondition(item)
  const conditionLabel = pricingConditionLabel(condition, labels)
  if (item.tier_type !== 'usage_range') {
    return conditionLabel || labels.flat || 'All usage'
  }
  const start = compactNumber(item.tier_start ?? 0)
  const end = item.tier_end === null ? '∞' : compactNumber(item.tier_end)
  return [conditionLabel, `[${start}, ${end})`].filter(Boolean).join(' · ')
}

function variantIdentity(item, labels = {}) {
  const spec = priceSpec(item.spec)
  const scopeParts = [
    locationLabel(
      item.sku_access_region || item.spec?.access_region || item.sku_region,
      labels
    ),
    locationLabel(
      item.sku_deployment_scope || item.spec?.deployment_scope,
      labels
    ),
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
          ![
            'currency',
            'access_region',
            'deployment_scope',
            'pricing_condition',
            'region'
          ].includes(key) &&
          value !== '' &&
          value !== null &&
          value !== undefined
        )
      })
      .sort(([left], [right]) => left.localeCompare(right))
  )
}

function pricingCondition(item = {}) {
  const condition = item.pricing_condition || item.spec?.pricing_condition
  return condition && typeof condition === 'object' ? condition : {}
}

function pricingConditionLabel(condition = {}, labels = {}) {
  const code = condition.code || ''
  if (!code || code === 'all_time') return ''
  const conditionLabels = {
    peak: labels.peak || condition.label || 'Peak',
    off_peak: labels.offPeak || condition.label || 'Off-peak'
  }
  return conditionLabels[code] || condition.label || code
}

function locationLabel(value, labels = {}) {
  const normalized = String(value || '').trim()
  const locationLabels = {
    'cn-beijing': labels.beijing || 'cn-beijing',
    china_mainland: labels.chinaMainland || 'china_mainland'
  }
  return locationLabels[normalized] || normalized
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
