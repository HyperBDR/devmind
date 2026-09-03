import { tierRangeLabel } from './sourcePriceCatalog.js'

export function channelPriceSummaryRows(priceItems = []) {
  return priceItems
    .slice()
    .sort(channelPriceItemSort)
    .map((item) => ({
      label: channelPriceItemLabel(item),
      value: item.unit_price,
      currency: item.currency
    }))
}

export function channelPriceTierRows(priceItems = []) {
  const tiers = new Map()

  priceItems
    .slice()
    .sort(channelPriceItemSort)
    .forEach((item) => {
      const specLabel = priceSpecLabel(item.spec)
      const key = [
        item.tier_type || 'flat',
        item.tier_start || '',
        item.tier_end || '',
        specLabel,
        pricingConditionCode(item)
      ].join(':')
      const tier = tiers.get(key) || {
        prices: [],
        rangeLabel: [tierRangeLabel(item), specLabel]
          .filter(Boolean)
          .join(' · ')
      }

      const price = {
        currency: item.currency,
        label: priceDimensionLabel(item.dimension),
        value: item.unit_price
      }
      if (specLabel) price.specLabel = specLabel
      tier.prices.push(price)
      tiers.set(key, tier)
    })

  return Array.from(tiers.values())
}

export function priceSpecLabel(spec = {}) {
  if (!spec || typeof spec !== 'object') return ''
  const values = [
    spec.access_region,
    spec.region,
    spec.deployment_scope,
    spec.scope,
    spec.source,
    spec.provider,
    spec.sku,
    spec.variant
  ]
    .filter(Boolean)
    .map((value) => String(value).trim())
  return [...new Set(values)].join(' · ')
}

export function channelPriceItemLabel(item = {}) {
  const label = priceDimensionLabel(item.dimension)
  const hasCondition = !['', 'all_time'].includes(pricingConditionCode(item))
  const tierLabel =
    item.tier_type === 'usage_range' || hasCondition
      ? `${tierRangeLabel(item)} `
      : ''
  const specLabel = priceSpecLabel(item.spec)
  return [tierLabel + label, specLabel].filter(Boolean).join(' · ')
}

function pricingConditionCode(item = {}) {
  return String(
    item.pricing_condition?.code || item.spec?.pricing_condition?.code || ''
  )
}

function channelPriceItemSort(left, right) {
  const tierComparison =
    Number(left.tier_start || 0) - Number(right.tier_start || 0)
  if (tierComparison !== 0) return tierComparison
  return (
    priceDimensionOrder(left.dimension) - priceDimensionOrder(right.dimension)
  )
}

function priceDimensionLabel(dimension) {
  const labels = {
    text_input: 'Input',
    text_output: 'Output',
    cache_input: 'Cache',
    image_input: 'Image In',
    image_output: 'Image Out',
    audio_input: 'Audio In',
    audio_output: 'Audio Out',
    video_input: 'Video In',
    video_output: 'Video Out'
  }
  return labels[dimension] || dimension || '-'
}

function priceDimensionOrder(dimension) {
  const order = {
    text_input: 10,
    text_output: 20,
    cache_input: 30,
    image_input: 40,
    image_output: 50,
    audio_input: 60,
    audio_output: 70,
    video_input: 80,
    video_output: 90
  }
  return order[dimension] || 999
}
