<template>
  <div
    v-if="source"
    class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
    @click.self="$emit('close')"
  >
    <aside
      class="h-full w-full max-w-[72rem] overflow-y-auto bg-white shadow-xl"
    >
      <div
        class="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Supplier Source
            </p>
            <h3 class="mt-2 truncate text-xl font-semibold text-slate-900">
              {{ source.name }}
            </h3>
            <p class="mt-1 truncate font-mono text-xs text-slate-500">
              {{ source.slug }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="btn-danger btn-action-danger"
              :disabled="deleting"
              @click="$emit('delete', source)"
            >
              {{ deleting ? '删除中' : '删除' }}
            </button>
            <button
              type="button"
              class="btn-secondary btn-action-cancel"
              @click="$emit('close')"
            >
              关闭
            </button>
          </div>
        </div>
      </div>

      <div class="space-y-5 px-5 py-5">
        <div class="grid gap-3 md:grid-cols-4">
          <div class="summary-card">
            <p>覆盖元模型</p>
            <strong>{{ modelRows.length }}</strong>
          </div>
          <div class="summary-card">
            <p>当前价格项</p>
            <strong>{{ sourceItemRows.length }}</strong>
          </div>
          <div class="summary-card">
            <p>默认币种</p>
            <strong>{{ source.currency || '-' }}</strong>
          </div>
          <div class="summary-card">
            <p>状态</p>
            <strong>{{ source.is_enabled ? '启用' : '停用' }}</strong>
          </div>
        </div>

        <div class="source-info-grid">
          <div>
            <span>来源归属</span>
            <strong>{{ relationName }}</strong>
          </div>
          <div>
            <span>更新方式</span>
            <strong>{{ sourceConfigSummary }}</strong>
          </div>
          <div>
            <span>价格地址</span>
            <a
              v-if="source.endpoint_url"
              class="source-link"
              :href="source.endpoint_url"
              rel="noopener noreferrer"
              target="_blank"
              :title="source.endpoint_url"
            >
              {{ sourceAddressLabel }}
            </a>
            <strong v-else class="text-slate-400">-</strong>
          </div>
        </div>

        <div class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <div>
              <h3 class="panel-title">供货商下的元模型价格</h3>
              <p class="mt-1 text-xs text-slate-500">
                按元模型直接展示 Input、Output、Cache 三项核心价格。
              </p>
            </div>
            <input
              v-model="search"
              class="field-input w-full md:w-72"
              placeholder="搜索元模型、厂商或 code"
            />
          </div>
          <div class="overflow-x-auto">
            <table class="data-table source-price-table">
              <colgroup>
                <col class="model-col" />
                <col class="price-col" />
                <col class="time-col" />
              </colgroup>
              <thead>
                <tr>
                  <th class="table-head">元模型</th>
                  <th class="table-head">{{ priceHeaderLabel }}</th>
                  <th class="table-head">最近更新</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="row in filteredModelRows" :key="row.key">
                  <tr>
                    <td class="table-cell">
                      <p class="truncate font-medium text-slate-900">
                        {{ row.meta_model_name }}
                      </p>
                      <p class="mt-1 font-mono text-xs text-slate-400">
                        {{ row.meta_model_code }}
                        <span v-if="row.modality_label">
                          · {{ row.modality_label }}
                        </span>
                      </p>
                    </td>
                    <td class="table-cell">
                      <div
                        v-if="row.token_price_rows.length"
                        class="token-price-list"
                      >
                        <div
                          v-for="item in row.token_price_rows"
                          :key="`${row.key}-${item.label}`"
                          class="token-price-row"
                        >
                          <span>{{ item.label }}</span>
                          <strong>{{ item.value }}</strong>
                        </div>
                      </div>
                      <span v-else class="text-xs text-slate-400">
                        暂无价格
                      </span>
                    </td>
                    <td class="table-cell">
                      {{ formatDateTime(row.updated_at) }}
                    </td>
                  </tr>
                </template>
                <tr v-if="!filteredModelRows.length">
                  <td class="table-cell text-slate-500" colspan="3">
                    当前价格源还没有模型价格记录。
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

defineEmits(['close', 'delete', 'refresh'])

const props = defineProps({
  source: {
    type: Object,
    default: null
  },
  models: {
    type: Array,
    default: () => []
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  deleting: {
    type: Boolean,
    default: false
  }
})

const search = ref('')

const tokenPriceDimensions = [
  { dimension: 'text_input', label: 'Input' },
  { dimension: 'text_output', label: 'Output' },
  { dimension: 'cache_input', label: 'Cache' }
]

const modelMap = computed(() => {
  const entries = props.models.map((model) => [String(model.id), model])
  return new Map(entries)
})

const sourceItemRows = computed(() =>
  props.priceItems
    .filter(
      (item) =>
        String(item.source) === String(props.source?.id) &&
        item.is_current !== false
    )
    .slice()
    .sort((left, right) => {
      const leftModel = modelName(left).localeCompare(modelName(right))
      if (leftModel !== 0) return leftModel
      return dimensionSort(left, right)
    })
    .map((item) => buildRawItemRow(item))
)

const modelRows = computed(() => {
  const grouped = new Map()
  const rows = []

  sourceItemRows.value.forEach((row) => {
    const key = String(row.meta_model_id || row.meta_model_code || row.id)
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key).push(row)
  })

  Array.from(grouped.entries()).forEach(([key, groupedRows]) => {
    rows.push(buildModelRow(key, groupedRows))
  })

  sourceBoundModels.value.forEach((model) => {
    const key = String(model.meta_model || model.meta_model_code || model.id)
    if (!grouped.has(key)) {
      rows.push(buildFallbackModelRow(model, key))
      grouped.set(key, [])
    }
  })

  return rows.sort((left, right) =>
    left.meta_model_name.localeCompare(right.meta_model_name)
  )
})

const sourceBoundModels = computed(() =>
  props.models.filter(
    (model) => String(model.source) === String(props.source?.id)
  )
)

const filteredModelRows = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return modelRows.value
  return modelRows.value.filter((row) => row.search_text.includes(keyword))
})

const relationName = computed(() => {
  if (props.source?.provider_name) return props.source.provider_name
  if (props.source?.channel_name) return props.source.channel_name
  return '未绑定'
})

const sourceConfigSummary = computed(() =>
  [
    sourceCategoryLabel(businessSourceCategory(props.source)),
    sourceModeLabel(props.source),
    props.source?.currency
  ]
    .filter(Boolean)
    .join(' · ')
)

const sourceAddressLabel = computed(() => {
  const value = props.source?.endpoint_url
  if (!value) return ''
  try {
    const url = new URL(value)
    return `${url.hostname}${url.pathname === '/' ? '' : url.pathname}`
  } catch {
    return String(value)
  }
})

const priceHeaderLabel = computed(() => '价格（原始币种 / 1M tokens）')

function buildRawItemRow(item) {
  const model = modelMap.value.get(String(item.model)) || {}
  return {
    key: `source-price-${item.id}`,
    id: item.id,
    model_id: item.model,
    meta_model_id: item.meta_model || model.meta_model || '',
    raw: item,
    meta_model_name:
      item.meta_model_name || model.meta_model_name || '未知元模型',
    meta_model_code: item.meta_model_code || model.meta_model_code || '-',
    provider_name:
      item.meta_model_vendor_name ||
      model.meta_model_vendor_name ||
      item.provider_name ||
      model.provider_name ||
      '未绑定厂商',
    sku_name: item.model_name || model.name || '',
    sku_code: item.model_code || model.code || '',
    modality_label: modalityLabel(model.modality),
    dimension_label: `${dimensionLabel(item.dimension)} ${billingUnitLabel(item.billing_unit)}`,
    price: money(item.unit_price, item.currency),
    unit_price: item.unit_price,
    currency: item.currency,
    dimension: item.dimension,
    billing_unit: item.billing_unit,
    tier_type: item.tier_type,
    tier_start: item.tier_start,
    tier_end: item.tier_end,
    spec: item.spec || {},
    updated_at: item.updated_at || item.effective_from
  }
}

function buildModelRow(key, rows) {
  const sortedRows = rows.slice().sort(dimensionSort)
  const firstRow = sortedRows[0]

  return {
    key,
    meta_model_name: firstRow.meta_model_name,
    meta_model_code: firstRow.meta_model_code,
    provider_name: firstRow.provider_name,
    modality_label: firstRow.modality_label,
    token_price_rows: tokenPriceRowsFromRawRows(sortedRows),
    price_count: sortedRows.length,
    updated_at: latestUpdatedAt(sortedRows),
    raw_rows: sortedRows,
    search_text: [
      firstRow.meta_model_name,
      firstRow.meta_model_code,
      firstRow.provider_name,
      ...sortedRows.map((row) => row.sku_name),
      ...sortedRows.map((row) => row.sku_code),
      firstRow.modality_label,
      ...sortedRows.map((row) => row.dimension_label)
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
  }
}

function buildFallbackModelRow(model, key) {
  return {
    key,
    meta_model_name: model.meta_model_name || model.name || '未知元模型',
    meta_model_code: model.meta_model_code || model.code || '-',
    provider_name:
      model.meta_model_vendor_name || model.provider_name || '未绑定厂商',
    modality_label: modalityLabel(model.modality),
    token_price_rows: tokenPriceRowsFromModel(model),
    price_count: 0,
    updated_at: model.last_price_updated_at || model.updated_at || '',
    raw_rows: [],
    search_text: [
      model.meta_model_name,
      model.name,
      model.meta_model_code,
      model.code,
      model.provider_name,
      modalityLabel(model.modality)
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
  }
}

function tokenPriceRowsFromRawRows(rows) {
  return tokenPriceDimensions.map((item) => {
    const matchedRow = rows.find(
      (row) =>
        row.dimension === item.dimension && row.billing_unit === 'per_1m_tokens'
    )
    return {
      label: item.label,
      value: matchedRow?.price || '-'
    }
  })
}

function tokenPriceRowsFromModel(model) {
  return [
    {
      label: 'Input',
      value: legacyPriceValue(model.input_price_per_million, model.currency)
    },
    {
      label: 'Output',
      value: legacyPriceValue(model.output_price_per_million, model.currency)
    },
    {
      label: 'Cache',
      value: legacyPriceValue(
        model.cache_input_price_per_million,
        model.currency
      )
    }
  ]
}

function legacyPriceValue(value, currency) {
  if (!hasValue(value)) return '-'
  return money(value, currency)
}

function modelName(item) {
  const model = modelMap.value.get(String(item.model)) || {}
  return item.meta_model_name || model.meta_model_name || item.model_name || ''
}

function latestUpdatedAt(rows) {
  const values = rows.map((row) => row.updated_at).filter(Boolean)
  if (!values.length) return ''
  return values.sort(
    (left, right) => new Date(right).getTime() - new Date(left).getTime()
  )[0]
}

function dimensionSort(left, right) {
  const order = [
    'text_input',
    'text_output',
    'cache_input',
    'audio_input',
    'audio_output',
    'image_input',
    'image_output',
    'video_input',
    'video_output'
  ]
  const leftIndex = order.indexOf(left.dimension)
  const rightIndex = order.indexOf(right.dimension)
  if (leftIndex !== rightIndex) return leftIndex - rightIndex

  const leftKey = `${left.dimension}-${left.tier_start || ''}`
  const rightKey = `${right.dimension}-${right.tier_start || ''}`
  return leftKey.localeCompare(rightKey)
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || 'USD'} ${Number(value).toFixed(4)}`
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== ''
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
    per_1m_tokens: '/ 百万 tokens',
    per_image: '/ 张',
    per_second: '/ 秒',
    per_generation: '/ 次'
  }
  return labels[unit] || ''
}

function modalityLabel(modality) {
  const labels = {
    text: '文本',
    audio: '音频',
    video: '视频',
    multimodal: '多模态'
  }
  return labels[modality] || modality || ''
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: '原厂价格',
    supplier: '供货商价格',
    manual: '人工录入',
    unknown: '其他'
  }
  return labels[category] || labels.unknown
}

function businessSourceCategory(source) {
  return (
    source?.business_source_category || source?.source_category || 'unknown'
  )
}

function sourceModeLabel(source) {
  const category = source?.source_category || ''
  if (String(source?.endpoint_url || '').includes('models.dev/api.json')) {
    return '聚合同步'
  }
  if (category === 'official_provider') return '自动采集'
  if (category === 'supplier') return '供货商维护'
  if (category === 'manual') return '手动维护'
  if (source?.source_type === 'yunce') return '专用采集'
  return '待适配'
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.summary-card {
  @apply rounded-lg bg-slate-50 px-3 py-2;
}

.summary-card p {
  @apply text-xs text-slate-500;
}

.summary-card strong {
  @apply mt-1 block font-mono text-sm text-slate-800;
}

.source-info-grid {
  @apply grid gap-3 md:grid-cols-3;
}

.source-info-grid div {
  @apply min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.source-info-grid span {
  @apply block text-xs text-slate-500;
}

.source-info-grid strong,
.source-info-grid a {
  @apply mt-1 block truncate text-sm font-medium text-slate-800;
}

.source-link {
  @apply text-indigo-600 hover:text-indigo-700 hover:underline;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 md:flex-row md:items-center md:justify-between;
}

.data-table {
  @apply min-w-full table-fixed divide-y divide-slate-200;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply min-w-0 px-4 py-3 text-sm text-slate-600;
}

.source-price-table .model-col {
  width: 38%;
}

.source-price-table .price-col {
  width: 44%;
}

.source-price-table .time-col {
  width: 18%;
}

.token-price-list {
  @apply grid max-w-md gap-1.5;
}

.token-price-row {
  @apply grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-3 text-xs;
}

.token-price-row span {
  @apply text-slate-400;
}

.token-price-row strong {
  @apply truncate text-right font-mono font-semibold text-slate-800;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-danger {
  @apply inline-flex items-center gap-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-200 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60;
}

.field-input {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}
</style>
