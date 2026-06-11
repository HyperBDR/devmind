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
          <button type="button" class="btn-secondary" @click="$emit('close')">
            关闭
          </button>
        </div>
      </div>

      <div class="space-y-5 px-5 py-5">
        <div class="grid gap-3 md:grid-cols-4">
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">模型数量</p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ models.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">模型价格源</p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ sources.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">状态</p>
            <p class="mt-1 text-sm text-slate-800">
              {{ provider.is_active ? '启用' : '停用' }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">价格获取地址</p>
            <a
              v-if="priceSourceUrl"
              class="mt-1 block truncate text-sm font-medium text-indigo-600 hover:text-indigo-700 hover:underline"
              :href="priceSourceUrl"
              rel="noopener noreferrer"
              target="_blank"
              :title="priceSourceUrl"
            >
              {{ priceSourceUrl }}
            </a>
            <p v-else class="mt-1 text-sm text-slate-400">-</p>
          </div>
        </div>

        <div class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <h3 class="panel-title">模型定价详情</h3>
          </div>
          <div class="overflow-x-auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">计价维度</th>
                  <th class="table-head">模型价格源</th>
                  <th class="table-head">来源类型</th>
                  <th class="table-head text-right">价格</th>
                  <th class="table-head">原始币种</th>
                  <th class="table-head">更新时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in priceRows" :key="row.key">
                  <td class="table-cell max-w-64">
                    <p class="font-medium text-slate-900">
                      {{ row.model.name }}
                    </p>
                    <p class="mt-1 font-mono text-xs text-slate-400">
                      {{ row.model.code }} · {{ modalityLabel(row.model.modality) }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <p class="font-medium text-slate-800">
                      {{ row.dimension_label }}
                    </p>
                    <p
                      v-if="row.spec_label || row.tier_label"
                      class="mt-1 text-xs text-slate-400"
                    >
                      {{ [row.spec_label, row.tier_label].filter(Boolean).join(' · ') }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <a
                      v-if="row.source_url"
                      class="source-link"
                      :href="row.source_url"
                      rel="noopener noreferrer"
                      target="_blank"
                      :title="row.source_url"
                    >
                      {{ row.source_name }}
                    </a>
                    <p v-else class="font-medium text-slate-800">
                      {{ row.source_name }}
                    </p>
                    <p
                      v-if="row.source_relation"
                      class="mt-1 text-xs text-slate-400"
                    >
                      {{ row.source_relation }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <span :class="['source-badge', row.source_tone]">
                      {{ row.source_category_label }}
                    </span>
                  </td>
                  <td class="table-cell text-right font-mono font-semibold text-slate-800">
                    {{ row.price }}
                  </td>
                  <td class="table-cell font-mono">
                    {{ row.currency || '-' }}
                  </td>
                  <td class="table-cell">
                    {{ formatDateTime(row.updated_at) }}
                  </td>
                </tr>
                <tr v-if="!priceRows.length">
                  <td class="table-cell text-slate-500" colspan="7">
                    当前服务商还没有模型定价记录。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="sources.length" class="panel space-y-3">
          <h3 class="panel-title">模型价格源</h3>
          <div class="grid gap-3 md:grid-cols-2">
            <div
              v-for="source in sources"
              :key="source.id"
              class="rounded-lg border border-slate-200 px-3 py-2"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-slate-900">
                    {{ source.name }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ sourceCategoryLabel(source.source_category) }}
                    <span v-if="source.channel_name">
                      / {{ source.channel_name }}
                    </span>
                  </p>
                  <a
                    v-if="source.endpoint_url"
                    class="mt-1 block truncate text-xs text-indigo-600 hover:text-indigo-700 hover:underline"
                    :href="source.endpoint_url"
                    rel="noopener noreferrer"
                    target="_blank"
                    :title="source.endpoint_url"
                  >
                    {{ source.endpoint_url }}
                  </a>
                  <p v-else class="mt-1 text-xs text-slate-400">-</p>
                </div>
                <span :class="source.is_enabled ? 'badge-ok' : 'badge-muted'">
                  {{ source.is_enabled ? '启用' : '停用' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineEmits(['close'])

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
  }
})

const priceSourceUrl = computed(() => {
  const source = preferredPriceSource(props.sources)
  return source?.endpoint_url || props.provider?.price_source_url || ''
})

const priceRows = computed(() =>
  props.models.flatMap((model) => {
    const standardRows = standardPriceRows(model)
    return standardRows.length ? standardRows : legacyPriceRows(model)
  })
)

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

function standardPriceRows(model) {
  return props.priceItems
    .filter(
      (item) =>
        String(item.model) === String(model.id) &&
        item.is_current !== false
    )
    .slice()
    .sort((left, right) => {
      const leftKey = `${left.dimension}-${left.tier_start || ''}`
      const rightKey = `${right.dimension}-${right.tier_start || ''}`
      return leftKey.localeCompare(rightKey)
    })
    .map((item) => priceRowFromItem(model, item))
}

function priceRowFromItem(model, item) {
  const source = sourceForItem(item) || {}
  const relation = sourceRelation({
    ...source,
    provider_name: item.source_provider_name || source.provider_name,
    channel_name: item.source_channel_name || source.channel_name
  })
  return {
    key: `item-${item.id}`,
    model,
    dimension_label: `${dimensionLabel(item.dimension)} ${billingUnitLabel(item.billing_unit)}`,
    spec_label: specLabel(item.spec || {}),
    tier_label: tierLabel(item),
    source_name: item.source_name || source.name || '未绑定价格源',
    source_url: item.source_endpoint_url || source.endpoint_url || '',
    source_relation: relation,
    source_category_label: sourceCategoryLabel(
      item.source_category || source.source_category
    ),
    source_tone: sourceTone(item.source_category || source.source_category),
    price: money(item.unit_price, item.currency),
    currency: item.currency,
    updated_at: item.updated_at || item.effective_from
  }
}

function legacyPriceRows(model) {
  return legacyPricingItems(model).map((item, index) => {
    const source = sourceForModel(model) || {}
    const relation = sourceRelation(source)
    return {
      key: `legacy-${model.id}-${index}`,
      model,
      dimension_label: item.label,
      spec_label: '',
      tier_label: '',
      source_name: model.source_name || source.name || '模型主表价格',
      source_url: model.source_endpoint_url || source.endpoint_url || '',
      source_relation: relation,
      source_category_label: sourceCategoryLabel(
        model.source_category || source.source_category
      ),
      source_tone: sourceTone(model.source_category || source.source_category),
      price: item.value,
      currency: model.currency,
      updated_at: model.last_price_updated_at || model.updated_at
    }
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
  return props.sources.find(
    (source) => String(source.id) === String(item.source)
  )
}

function sourceForModel(model) {
  return props.sources.find(
    (source) => String(source.id) === String(model.source)
  )
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

function billingUnitLabel(unit) {
  const labels = {
    per_1m_tokens: '/ 1M tokens',
    per_image: '/ 张',
    per_second: '/ 秒',
    per_generation: '/ 次'
  }
  return labels[unit] || unit || ''
}

function specLabel(spec) {
  const entries = Object.entries(spec || {}).filter(
    ([, value]) => value !== null && value !== undefined && value !== ''
  )
  return entries.map(([key, value]) => `${specKeyLabel(key)}:${value}`).join(' ')
}

function specKeyLabel(key) {
  const labels = {
    resolution: '分辨率',
    size: '尺寸',
    quality: '质量',
    audio: '音频',
    mode: '模式',
    inference_type: '推理'
  }
  return labels[key] || key
}

function tierLabel(item) {
  if (!item.tier_start && !item.tier_end) return ''
  const start = item.tier_start ?? 0
  const end = item.tier_end || '不限'
  return `${start}-${end}`
}

function tokenPricingItems(model) {
  return [
    priceItem('输入 / 1M', model.input_price_per_million, model.currency),
    priceItem('输出 / 1M', model.output_price_per_million, model.currency),
    priceItem('缓存输入 / 1M', model.cache_input_price_per_million, model.currency)
  ].filter(Boolean)
}

function audioPricingItems(model) {
  return [
    priceItem('音频输入 / 秒', model.audio_input_price_per_second, model.currency),
    priceItem('音频输出 / 秒', model.audio_output_price_per_second, model.currency)
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
    priceItem('视频输入 / 秒', model.video_input_price_per_second, model.currency),
    priceItem('视频输出 / 秒', model.video_output_price_per_second, model.currency)
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
    sources.find((source) => source.source_category === 'official_provider') ||
    sources.find((source) => String(source.slug || '').endsWith('-official')) ||
    sources.find((source) => source.updates_model_prices) ||
    sources.find((source) => source.endpoint_url) ||
    null
  )
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: '原厂',
    supplier: '供货商',
    manual: '人工',
    unknown: '其他'
  }
  return labels[category] || '其他'
}

function sourceTone(category) {
  const tones = {
    official_provider: 'official',
    supplier: 'supplier',
    manual: 'manual',
    unknown: 'unknown'
  }
  return tones[category] || 'unknown'
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
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply whitespace-nowrap px-4 py-3 text-sm text-slate-600;
}

.source-link {
  @apply block max-w-52 truncate font-medium text-indigo-600 hover:text-indigo-700 hover:underline;
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
