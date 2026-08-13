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

export function channelPriceItemLabel(item = {}) {
  const label = priceDimensionLabel(item.dimension)
  if (item.tier_type !== 'usage_range') return label
  return `${tierRangeLabel(item)} ${label}`
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
