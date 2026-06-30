<template>
  <div
    v-if="provider"
    class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
    @click.self="$emit('close')"
  >
    <aside class="h-full w-full max-w-5xl overflow-y-auto bg-white shadow-xl">
      <div
        class="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Price Catalog
            </p>
            <h3 class="mt-2 text-xl font-semibold text-slate-900">
              {{ provider.name }}
            </h3>
            <p class="mt-1 font-mono text-xs text-slate-500">
              {{ provider.code }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            @click="$emit('close')"
          >
            关闭
          </button>
        </div>
      </div>

      <div class="space-y-5 px-5 py-5">
        <div class="grid gap-3 md:grid-cols-5">
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">模型数量</p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ models.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">已定价模型</p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ pricedModelCount }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">模型价格源</p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ sourceRows.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">价格结构</p>
            <p class="mt-1 text-sm text-slate-800">
              原厂 {{ officialModelCount }} · 云托管
              {{ cloudHostedModelCount }} · 外部 {{ externalModelCount }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">价格来源</p>
            <div
              v-if="primarySource"
              class="mt-1 min-w-0"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-900">
                  {{ primarySource.name }}
                </p>
                <p class="mt-1 truncate font-mono text-xs text-slate-400">
                  {{ primarySource.slug }} · {{ sourceRows.length }} 个来源
                </p>
                <a
                  v-if="primarySource.endpoint_url"
                  class="mt-1 block truncate text-sm font-medium text-indigo-600 hover:text-indigo-700 hover:underline"
                  :href="primarySource.endpoint_url"
                  rel="noopener noreferrer"
                  target="_blank"
                  :title="primarySource.endpoint_url"
                >
                  {{ primarySource.endpoint_url }}
                </a>
              </div>
            </div>
            <p v-else class="mt-1 font-mono text-sm text-slate-800">0</p>
          </div>
        </div>

        <div class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <div>
              <h3 class="panel-title">厂商模型价格</h3>
              <p class="mt-1 text-xs text-slate-500">
                按模型汇总输入、输出、缓存等核心价格，减少逐维度展开带来的噪音。
              </p>
            </div>
            <div
              class="grid w-full gap-3 md:max-w-xl md:grid-cols-[minmax(0,1fr)_auto]"
            >
              <input
                v-model="search"
                class="field-input"
                placeholder="搜索模型、来源或 code"
              />
              <div class="filter-tabs" role="tablist" aria-label="来源类型">
                <button
                  v-for="option in categoryFilterOptions"
                  :key="option.value"
                  type="button"
                  :class="[
                    'filter-tab',
                    categoryFilter === option.value ? 'is-active' : ''
                  ]"
                  :aria-selected="categoryFilter === option.value"
                  role="tab"
                  @click="categoryFilter = option.value"
                >
                  {{ option.label }}
                  <span class="filter-tab-count">{{ option.count }}</span>
                </button>
              </div>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="data-table pricing-source-table">
              <colgroup>
                <col class="model-col" />
                <col class="type-col" />
                <col class="price-col" />
                <col class="time-col" />
              </colgroup>
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">来源类型</th>
                  <th class="table-head">价格摘要</th>
                  <th class="table-head">更新时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in filteredModelRows" :key="row.key">
                  <td class="table-cell max-w-64">
                    <p class="font-medium text-slate-900">
                      {{ row.model.name }}
                    </p>
                    <p class="mt-1 font-mono text-xs text-slate-400">
                      {{ row.model.code }} ·
                      {{ modalityLabel(row.model.modality) }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <span :class="['source-badge', row.source_tone]">
                      {{ row.source_category_label }}
                    </span>
                  </td>
                  <td class="table-cell">
                    <div
                      v-if="row.price_summary.length"
                      class="flex flex-wrap gap-1.5"
                    >
                      <span
                        v-for="item in row.price_summary"
                        :key="item.label"
                        class="price-chip"
                      >
                        <span class="text-slate-400">{{ item.label }}</span>
                        {{ item.value }}
                      </span>
                    </div>
                    <span v-else class="text-xs text-slate-400">暂无价格</span>
                  </td>
                  <td class="table-cell">
                    {{ formatDateTime(row.updated_at) }}
                  </td>
                </tr>
                <tr v-if="!filteredModelRows.length">
                  <td class="table-cell text-slate-500" colspan="4">
                    当前服务商还没有模型定价记录。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

defineEmits([
  'close',
  'manual-entry-source',
  'edit-source',
  'toggle-source',
  'collect-source',
  'delete-source'
])

const props = defineProps({
  provider: {
    type: Object,
    default: null
  },
  models: {
    type: Array,
    required: true
  },
  sources: {
    type: Array,
    required: true
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  displayCurrency: {
    type: String,
    default: 'CNY'
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  },
  collectingSourceId: {
    type: [Number, String],
    default: null
  },
  deletingSourceId: {
    type: [Number, String],
    default: null
  }
})

const search = ref('')
const categoryFilter = ref('all')

const modelRows = computed(() =>
  props.models.flatMap((model) => buildModelRows(model))
)

const categoryFilterOptions = computed(() => {
  const counts = sourceCategoryCounts(modelRows.value)
  return [
    { value: 'all', label: '全部来源', count: modelRows.value.length },
    {
      value: 'official_provider',
      label: '原厂',
      count: counts.official_provider || 0
    },
    {
      value: 'cloud_hosted',
      label: '云托管',
      count: counts.cloud_hosted || 0
    },
    { value: 'supplier', label: '供货商', count: counts.supplier || 0 },
    { value: 'manual', label: '人工', count: counts.manual || 0 }
  ]
})

const sourceRows = computed(() =>
  aggregatePriceSources(props.sources, props.priceItems)
)

const primarySource = computed(() => preferredPriceSource(sourceRows.value))

const filteredModelRows = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return modelRows.value.filter((row) => {
    if (
      categoryFilter.value !== 'all' &&
      row.source_category !== categoryFilter.value
    ) {
      return false
    }
    if (!keyword) return true
    return row.search_text.includes(keyword)
  })
})

const officialModelCount = computed(
  () =>
    modelRows.value.filter((row) => row.source_category === 'official_provider')
      .length
)

const supplierModelCount = computed(
  () =>
    modelRows.value.filter((row) => row.source_category === 'supplier').length
)

const cloudHostedModelCount = computed(
  () =>
    modelRows.value.filter((row) => row.source_category === 'cloud_hosted')
      .length
)

const internalModelCount = computed(
  () => modelRows.value.filter((row) => row.source_category === 'manual').length
)

const externalModelCount = computed(
  () => supplierModelCount.value + internalModelCount.value
)

const pricedModelCount = computed(
  () =>
    new Set(
      modelRows.value
        .filter((row) => row.price_summary.length > 0)
        .map((row) => String(row.model.id))
    ).size
)

function sourceCategoryCounts(rows) {
  return rows.reduce((counts, row) => {
    const category = row.source_category || 'unknown'
    counts[category] = (counts[category] || 0) + 1
    return counts
  }, {})
}

function convertCurrencyAmount(value, sourceCurrency = 'USD') {
  if (value === null || value === undefined || value === '') return null
  const source = String(sourceCurrency || '').toUpperCase()
  const target = String(props.displayCurrency || 'CNY').toUpperCase()
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  if (source === target) return amount
  if (source === 'USD' && target === 'CNY') {
    return amount * Number(props.exchangeRate || 7.15)
  }
  if (source === 'CNY' && target === 'USD') {
    return amount / Number(props.exchangeRate || 7.15)
  }
  return null
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  const displayValue = convertCurrencyAmount(value, currency)
  if (displayValue === null) {
    return `${currency || 'USD'} ${Number(value).toFixed(4)}`
  }
  return `${props.displayCurrency || 'CNY'} ${displayValue.toFixed(4)}`
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== ''
}

function buildModelRows(model) {
  const items = currentPriceItemsForModel(model)
  if (!items.length) {
    return [buildModelRow(model, [], sourceForModel(model), 'model-source')]
  }
  const groupedItems = new Map()
  items.forEach((item) => {
    const rawSource = rawSourceForItem(item)
    const key = rawSource
      ? priceSourceGroupKey(rawSource)
      : String(item.source || item.source_name || 'unbound-source')
    if (!groupedItems.has(key)) groupedItems.set(key, [])
    groupedItems.get(key).push(item)
  })
  return Array.from(groupedItems.entries()).map(([sourceKey, sourceItems]) =>
    buildModelRow(
      model,
      sourceItems,
      sourceForItem(sourceItems[0]) || sourceForModel(model),
      sourceKey
    )
  )
}

function buildModelRow(model, items, source = null, sourceKey = 'source') {
  const resolvedSource = source || {}
  const relation = sourceRelation({
    ...resolvedSource,
    provider_name:
      items[0]?.source_provider_name || resolvedSource.provider_name,
    channel_name: items[0]?.source_channel_name || resolvedSource.channel_name
  })
  const category = businessSourceCategory(
    items[0] || resolvedSource || model,
    model,
    resolvedSource
  )
  const priceSummary = summarizeModelPrices(model, items)
  const updatedAt = latestModelUpdatedAt(model, items)
  return {
    key: `model-${model.id}-${sourceKey}`,
    model,
    source_name:
      items[0]?.source_name ||
      model.source_name ||
      resolvedSource.name ||
      '未绑定价格源',
    source_url:
      items[0]?.source_endpoint_url ||
      model.source_endpoint_url ||
      resolvedSource.endpoint_url ||
      '',
    source_relation: relation,
    source_category: category,
    source_category_label: sourceCategoryLabel(category),
    source_tone: sourceTone(category),
    price_summary: priceSummary,
    updated_at: updatedAt,
    search_text: [
      model.name,
      model.code,
      modalityLabel(model.modality),
      items[0]?.source_name || model.source_name || resolvedSource.name,
      relation,
      category
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
  }
}

function currentPriceItemsForModel(model) {
  return props.priceItems
    .filter(
      (item) =>
        String(item.model) === String(model.id) && item.is_current !== false
    )
    .slice()
    .sort((left, right) => {
      const leftKey = `${left.dimension}-${left.tier_start || ''}`
      const rightKey = `${right.dimension}-${right.tier_start || ''}`
      return leftKey.localeCompare(rightKey)
    })
}

function legacyPricingItems(model) {
  if (model.modality === 'audio') return audioPricingItems(model)
  if (model.modality === 'video') return videoPricingItems(model)
  if (model.modality === 'multimodal') {
    if (hasVideoPrice(model)) return videoPricingItems(model)
    if (hasAudioPrice(model)) return audioPricingItems(model)
    if (hasImagePrice(model)) return imagePricingItems(model)
  }
  return tokenPricingItems(model)
}

function sourceForItem(item) {
  const source = rawSourceForItem(item)
  return aggregateSourceForRawSource(source)
}

function rawSourceForItem(item) {
  return props.sources.find(
    (source) => String(source.id) === String(item.source)
  )
}

function sourceForModel(model) {
  const source = props.sources.find(
    (source) => String(source.id) === String(model.source)
  )
  return aggregateSourceForRawSource(source)
}

function aggregatePriceSources(sources, priceItems) {
  const groups = new Map()
  sources.forEach((source) => {
    const key = priceSourceGroupKey(source)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(source)
  })

  return Array.from(groups.values())
    .map((group) => buildAggregateSource(group, priceItems))
    .sort((left, right) => {
      const leftRank = categoryRank(businessSourceCategory(left))
      const rightRank = categoryRank(businessSourceCategory(right))
      if (leftRank !== rightRank) return leftRank - rightRank
      return String(left.name || '').localeCompare(String(right.name || ''))
    })
}

function aggregateSourceForRawSource(source) {
  if (!source) return null
  const key = priceSourceGroupKey(source)
  return sourceRows.value.find((row) => row.source_group_key === key) || source
}

function buildAggregateSource(group, priceItems) {
  const sorted = group.slice().sort((left, right) => {
    if (isProviderOfficialSource(left)) return -1
    if (isProviderOfficialSource(right)) return 1
    return String(left.name || '').localeCompare(String(right.name || ''))
  })
  const primary = sorted[0]
  const sourceIds = sorted.map((source) => String(source.id))
  const endpointUrl =
    sorted.find((source) => source.endpoint_url)?.endpoint_url || ''
  const latestUpdate = sorted
    .map((source) => source.updated_at)
    .filter(Boolean)
    .sort((left, right) => new Date(right) - new Date(left))[0]

  return {
    ...primary,
    id: primary.id,
    name: aggregateSourceName(primary),
    slug: aggregateSourceSlug(primary),
    endpoint_url: endpointUrl,
    is_enabled: sorted.some((source) => source.is_enabled),
    source_group_key: priceSourceGroupKey(primary),
    source_group_ids: sourceIds,
    source_count: sorted.length,
    updated_at: latestUpdate || primary.updated_at,
    can_collect: Boolean(
      sorted.find((source) => source.can_collect)?.can_collect
    ),
    can_manual_entry: sorted.some((source) => source.can_manual_entry),
    collect_action_label: primary.collect_action_label,
    price_item_count: priceItems.filter(
      (item) =>
        sourceIds.includes(String(item.source || '')) &&
        item.is_current !== false
    ).length
  }
}

function priceSourceGroupKey(source) {
  const providerCode = String(source?.provider_code || '').trim()
  const drawerProviderCode = String(props.provider?.code || '').trim()
  if (businessSourceCategory(source) === 'official_provider') {
    return `official:${
      providerCode || drawerProviderCode || officialProviderCodeFromSlug(source)
    }`
  }
  return `source:${source?.id || source?.slug || 'unknown'}`
}

function isLegacyOfficialModelSource(source) {
  if (businessSourceCategory(source) !== 'official_provider') return false
  const providerCode = String(
    source?.provider_code ||
      props.provider?.code ||
      officialProviderCodeFromSlug(source)
  ).trim()
  if (!providerCode) return false
  const slug = String(source?.slug || '')
  return slug !== `${providerCode}-official` && slug.endsWith('-official')
}

function isProviderOfficialSource(source) {
  const providerCode = String(source?.provider_code || '').trim()
  const drawerProviderCode = String(props.provider?.code || '').trim()
  const expectedCode = providerCode || drawerProviderCode
  return (
    expectedCode &&
    businessSourceCategory(source) === 'official_provider' &&
    String(source?.slug || '') === `${expectedCode}-official`
  )
}

function aggregateSourceName(source) {
  const providerName = source.provider_name || props.provider?.name || ''
  if (!isLegacyOfficialModelSource(source)) {
    return source?.name || (providerName ? `${providerName} 官方价格` : '-')
  }
  return `${providerName || source.provider_code || '服务商'} 官方价格`
}

function aggregateSourceSlug(source) {
  const providerCode =
    source.provider_code ||
    props.provider?.code ||
    officialProviderCodeFromSlug(source)
  if (!isLegacyOfficialModelSource(source)) {
    return source?.slug || (providerCode ? `${providerCode}-official` : '')
  }
  return providerCode ? `${providerCode}-official` : source?.slug || ''
}

function officialProviderCodeFromSlug(source) {
  const slug = String(source?.slug || '')
  if (!slug.endsWith('-official')) return ''
  const providerCode = String(props.provider?.code || '').trim()
  if (providerCode && slug.startsWith(`${providerCode}-`)) {
    return providerCode
  }
  return ''
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: '文本输入',
    text_output: '文本输出',
    cache_input: '缓存输入',
    image_input: '图片输入',
    image_output: '图片输出',
    audio_input: '音频输入',
    audio_output: '音频输出',
    video_input: '视频输入',
    video_output: '视频输出'
  }
  return labels[dimension] || dimension || '-'
}

function tokenPricingItems(model) {
  return [
    priceItem('输入 / 1M', model.input_price_per_million, model.currency),
    priceItem('输出 / 1M', model.output_price_per_million, model.currency),
    priceItem(
      '缓存输入 / 1M',
      model.cache_input_price_per_million,
      model.currency
    )
  ].filter(Boolean)
}

function audioPricingItems(model) {
  return [
    priceItem(
      '音频输入 / 秒',
      model.audio_input_price_per_second,
      model.currency
    ),
    priceItem(
      '音频输出 / 秒',
      model.audio_output_price_per_second,
      model.currency
    )
  ].filter(Boolean)
}

function imagePricingItems(model) {
  return [
    priceItem(
      '图片输出 / 张',
      model.image_output_price_per_image,
      model.currency
    )
  ].filter(Boolean)
}

function videoPricingItems(model) {
  const items = [
    priceItem(
      '视频输入 / 秒',
      model.video_input_price_per_second,
      model.currency
    ),
    priceItem(
      '视频输出 / 秒',
      model.video_output_price_per_second,
      model.currency
    )
  ].filter(Boolean)
  const resolutionItems = Object.entries(model.video_resolution_prices || {})
    .slice(0, 2)
    .flatMap(([resolution, price]) => [
      priceItem(`${resolution} 输入`, price?.input, model.currency),
      priceItem(`${resolution} 输出`, price?.output, model.currency)
    ])
    .filter(Boolean)
  return [...items, ...resolutionItems]
}

function priceItem(label, value, currency) {
  if (!hasValue(value)) return null
  return {
    label,
    value: money(value, currency)
  }
}

function currentPriceItemSummary(item) {
  return {
    label: compactDimensionLabel(item.dimension, item.billing_unit),
    value: money(item.unit_price, item.currency)
  }
}

function compactDimensionLabel(dimension, billingUnit) {
  const labels = {
    text_input: '输入',
    text_output: '输出',
    cache_input: '缓存',
    image_input: '图入',
    image_output: '图出',
    audio_input: '音入',
    audio_output: '音出',
    video_input: '视入',
    video_output: '视出'
  }
  const base = labels[dimension] || dimensionLabel(dimension)
  if (billingUnit === 'per_image') return `${base}/张`
  if (billingUnit === 'per_second') return `${base}/秒`
  if (billingUnit === 'per_generation') return `${base}/次`
  return base
}

function summarizeModelPrices(model, items) {
  if (items.length) {
    const dedupedItems = dedupePriceItems(items)
    const preferredOrder = [
      'text_input',
      'text_output',
      'cache_input',
      'audio_input',
      'audio_output',
      'image_output',
      'video_input',
      'video_output'
    ]
    return dedupedItems
      .slice()
      .sort(
        (left, right) =>
          preferredOrder.indexOf(left.dimension) -
          preferredOrder.indexOf(right.dimension)
      )
      .map((item) => currentPriceItemSummary(item))
      .slice(0, 3)
  }
  return legacyPricingItems(model).slice(0, 3)
}

function dedupePriceItems(items) {
  const grouped = new Map()
  items.forEach((item) => {
    const key = [
      item.dimension,
      item.billing_unit,
      item.currency,
      item.tier_type,
      item.tier_start || '',
      item.tier_end || ''
    ].join(':')
    const current = grouped.get(key)
    if (!current || isItemNewer(item, current)) {
      grouped.set(key, item)
    }
  })
  return Array.from(grouped.values())
}

function isItemNewer(left, right) {
  const leftTime = new Date(left.updated_at || left.effective_from || 0)
  const rightTime = new Date(right.updated_at || right.effective_from || 0)
  return leftTime.getTime() >= rightTime.getTime()
}

function latestModelUpdatedAt(model, items) {
  const itemTimes = items.map((item) => item.updated_at || item.effective_from)
  const candidates = [
    ...itemTimes,
    model.last_price_updated_at,
    model.updated_at
  ].filter(Boolean)
  if (!candidates.length) return ''
  return candidates.sort(
    (left, right) => new Date(right).getTime() - new Date(left).getTime()
  )[0]
}

function sourceRelation(source) {
  if (source?.channel_name) return source.channel_name
  if (source?.provider_name) return source.provider_name
  return ''
}

function hasAudioPrice(model) {
  return (
    hasValue(model.audio_input_price_per_second) ||
    hasValue(model.audio_output_price_per_second)
  )
}

function hasVideoPrice(model) {
  return (
    hasValue(model.video_input_price_per_second) ||
    hasValue(model.video_output_price_per_second) ||
    Object.keys(model.video_resolution_prices || {}).length > 0
  )
}

function hasImagePrice(model) {
  return hasValue(model.image_output_price_per_image)
}

function modalityLabel(modality) {
  const labels = {
    text: '文本',
    audio: '音频',
    video: '视频',
    multimodal: '多模态'
  }
  return labels[modality] || modality || '-'
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function preferredPriceSource(sources) {
  return (
    sources.find(
      (source) => businessSourceCategory(source) === 'official_provider'
    ) ||
    sources.find((source) => String(source.slug || '').endsWith('-official')) ||
    sources.find((source) => source.updates_model_prices) ||
    sources.find((source) => source.endpoint_url) ||
    null
  )
}

function businessSourceCategory(item, model = {}, source = null) {
  return (
    item?.business_source_category ||
    item?.price_role ||
    model?.business_source_category ||
    model?.price_role ||
    source?.business_source_category ||
    item?.source_category ||
    model?.source_category ||
    source?.source_category ||
    'unknown'
  )
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: '原厂',
    cloud_hosted: '云托管',
    supplier: '供货商',
    manual: '内部维护',
    unknown: '其他'
  }
  return labels[category] || '其他'
}

function sourceTone(category) {
  const tones = {
    official_provider: 'official',
    cloud_hosted: 'cloud',
    supplier: 'supplier',
    manual: 'manual',
    unknown: 'unknown'
  }
  return tones[category] || 'unknown'
}

function categoryRank(category) {
  const ranks = {
    official_provider: 1,
    cloud_hosted: 2,
    supplier: 3,
    manual: 4,
    unknown: 5
  }
  return ranks[category] || 9
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.data-table {
  @apply min-w-full divide-y divide-slate-200;
  table-layout: fixed;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply min-w-0 px-4 py-3 text-sm text-slate-600;
}

.pricing-source-table .model-col {
  width: 34%;
}

.pricing-source-table .type-col {
  width: 14%;
}

.pricing-source-table .price-col {
  width: 34%;
}

.pricing-source-table .time-col {
  width: 18%;
}

.provider-source-table .source-name-col {
  width: 38%;
}

.provider-source-table .source-type-col {
  width: 18%;
}

.provider-source-table .source-status-col {
  width: 14%;
}

.provider-source-table .source-action-col {
  width: 30%;
}

.source-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
}

.field-input {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100;
}

.filter-tabs {
  @apply inline-flex h-10 shrink-0 items-center rounded-lg border border-slate-200 bg-slate-50 p-1;
}

.filter-tab {
  @apply inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-sm font-medium text-slate-500 transition hover:text-slate-800;
}

.filter-tab.is-active {
  @apply bg-white text-slate-900 shadow-sm;
}

.filter-tab-count {
  @apply font-mono text-xs text-slate-400;
}

.filter-tab.is-active .filter-tab-count {
  @apply text-slate-500;
}

.source-link {
  @apply block max-w-52 truncate font-medium text-indigo-600 hover:text-indigo-700 hover:underline;
}

.price-chip {
  @apply inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700;
}

.source-badge {
  @apply rounded-full border px-2 py-1 text-xs font-medium;
}

.source-badge.official {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.cloud {
  @apply border-sky-100 bg-sky-50 text-sky-700;
}

.source-badge.manual {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.badge-ok {
  @apply rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}

.badge-muted {
  @apply rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-500;
}
</style>
