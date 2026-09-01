const channelDimensions = [
  ['text_input', 'input_price_per_million'],
  ['text_output', 'output_price_per_million'],
  ['image_output', 'image_output_price_per_image'],
  ['audio_input', 'audio_input_price_per_second'],
  ['audio_output', 'audio_output_price_per_second'],
  ['video_input', 'video_input_price_per_second'],
  ['video_output', 'video_output_price_per_second']
]

const listingDimensions = [
  ['text_input', 'retail_input_price_per_million'],
  ['text_output', 'retail_output_price_per_million'],
  ['cache_input', 'retail_cache_input_price_per_million'],
  ['image_output', 'retail_image_output_price_per_image'],
  ['audio_input', 'retail_audio_input_price_per_second'],
  ['audio_output', 'retail_audio_output_price_per_second'],
  ['video_input', 'retail_video_input_price_per_second'],
  ['video_output', 'retail_video_output_price_per_second']
]

export function buildPriceChangeRows({
  channelHistory = [],
  channelVersions = [],
  listingHistory = [],
  officialHistory = [],
  priceItems = []
} = {}) {
  const rows = [
    ...historyRows(channelHistory, {
      type: 'channel',
      dimensions: channelDimensions,
      groupKey: (item) =>
        [item.channel, item.model, item.offering || 'default'].join(':'),
      context: (item) => item.offering_name || item.channel_name || '',
      source: (item) => item.price_source_name || item.channel_name || ''
    }),
    ...discountHistoryRows(channelVersions),
    ...historyRows(listingHistory, {
      type: 'listing',
      dimensions: listingDimensions,
      groupKey: (item) =>
        [item.platform, item.model, item.channel || 'automatic'].join(':'),
      context: (item) => item.channel_name || item.platform_name || '',
      source: (item) => item.platform_name || ''
    }),
    ...officialHistoryRows(officialHistory),
    ...(officialHistory.length
      ? []
      : priceItems.map((item) => ({
          key: `official-${item.id}-${item.dimension}`,
          type: 'official',
          modelId: item.model,
          name: item.model_name || item.meta_model_name || '',
          context:
            item.offering_exposed_model_name || item.sku_display_name || '',
          source: item.source_name || item.provider_name || '',
          dimension: item.dimension,
          previous: null,
          current: item.unit_price,
          currency: item.currency,
          time: item.effective_from || item.updated_at || item.created_at
        })))
  ]
  return rows.sort(
    (left, right) => new Date(right.time || 0) - new Date(left.time || 0)
  )
}

function discountHistoryRows(items = []) {
  const groups = new Map()
  items.forEach((item) => {
    const key = [item.offering, item.model].join(':')
    const versions = groups.get(key) || []
    versions.push(item)
    groups.set(key, versions)
  })
  const rows = []
  groups.forEach((versions) => {
    versions.sort(
      (left, right) => Number(right.version || 0) - Number(left.version || 0)
    )
    versions.forEach((item, index) => {
      const previous = versions[index + 1]
      rows.push({
        key: `discount-${item.id}`,
        type: 'discount',
        modelId: item.model,
        name: item.model_name || item.meta_model_name || '',
        context: item.offering_name || item.channel_name || '',
        source: item.channel_name || '',
        dimension: 'discount',
        previous: previous?.discount_value ?? null,
        current: item.discount_value,
        currency: item.discount_type || '',
        time: item.effective_from || item.created_at,
        version: item.version,
        discountType: item.discount_type
      })
    })
  })
  return rows
}

export function officialHistoryRows(items = []) {
  const dimensions = [
    ['text_input', 'input_price'],
    ['text_output', 'output_price'],
    ['cache_input', 'cache_input_price'],
    ['image_input', 'image_input_price'],
    ['image_output', 'image_output_price'],
    ['audio_input', 'audio_input_price'],
    ['audio_output', 'audio_output_price'],
    ['video_input', 'video_input_price'],
    ['video_output', 'video_output_price']
  ]
  const groups = new Map()
  items.forEach((item) => {
    const key = [
      item.source,
      item.offering || 'default',
      item.source_platform_id,
      item.model
    ].join(':')
    const versions = groups.get(key) || []
    versions.push(item)
    groups.set(key, versions)
  })
  const rows = []
  groups.forEach((versions) => {
    versions.sort((left, right) => historyTime(right) - historyTime(left))
    versions.forEach((item, index) => {
      const previous = versions[index + 1] || null
      const currentValues = flattenHistoryValues(item)
      const previousValues = flattenHistoryValues(previous)
      dimensions.forEach(([dimension, field]) => {
        if (!hasValue(currentValues[field])) return
        rows.push({
          key: `official-${item.id}-${dimension}`,
          type: 'official',
          modelId: item.model,
          name: item.model_name || item.meta_model_name || '',
          context: item.source_model_name || item.sku_code || '',
          source: item.source_name || item.provider_name || '',
          dimension,
          previous: previousValues[field] ?? null,
          current: currentValues[field],
          currency: item.currency,
          time: item.effective_from || item.collected_at
        })
      })
    })
  })
  return rows
}

export function priceChangeDelta(row) {
  const previous = numericValue(row?.previous)
  const current = numericValue(row?.current)
  if (previous === null || current === null) return null
  return current - previous
}

function historyRows(items, config) {
  const groups = new Map()
  items.forEach((item) => {
    const key = config.groupKey(item)
    const versions = groups.get(key) || []
    versions.push(item)
    groups.set(key, versions)
  })

  const rows = []
  groups.forEach((versions) => {
    versions.sort((left, right) => historyTime(right) - historyTime(left))
    versions.forEach((item, index) => {
      const previous = versions[index + 1] || null
      config.dimensions.forEach(([dimension, field]) => {
        if (!hasValue(item[field])) return
        rows.push({
          key: `${config.type}-${item.id}-${dimension}`,
          type: config.type,
          modelId: item.model,
          name: item.model_name || item.meta_model_name || '',
          context: config.context(item),
          source: config.source(item),
          dimension,
          previous: previous?.[field] ?? null,
          current: item[field],
          currency: item.currency,
          time: item.effective_from || item.created_at
        })
      })
    })
  })
  return rows
}

function historyTime(item) {
  return new Date(item?.effective_from || item?.created_at || 0).getTime()
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== ''
}

function numericValue(value) {
  if (!hasValue(value)) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function flattenHistoryValues(item) {
  if (!item) return {}
  const values = (item.normalized_price_rows || []).reduce((result, row) => {
    Object.entries(row?.values || {}).forEach(([key, value]) => {
      if (key !== 'currency' && hasValue(value)) result[key] = value
    })
    return result
  }, {})
  if (
    !hasValue(values.cache_input_price) &&
    hasValue(values.cache_hit_input_price)
  ) {
    values.cache_input_price = values.cache_hit_input_price
  }
  return values
}
