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
              {{ sources.length }}
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
            <div>
              <h3 class="panel-title">模型价格源</h3>
              <p class="mt-1 text-xs text-slate-500">
                管理该厂商下可采集、手工维护或供货商维护的价格来源。
              </p>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="data-table provider-source-table">
              <colgroup>
                <col class="source-name-col" />
                <col class="source-type-col" />
                <col class="source-status-col" />
                <col class="source-action-col" />
              </colgroup>
              <thead>
                <tr>
                  <th class="table-head">价格源</th>
                  <th class="table-head">类型</th>
                  <th class="table-head">状态</th>
                  <th class="table-head">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="source in sourceRows" :key="source.id">
                  <td class="table-cell">
                    <p class="truncate font-medium text-slate-900">
                      {{ source.name }}
                    </p>
                    <p class="mt-1 truncate font-mono text-xs text-slate-400">
                      {{ source.slug }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <span :class="['source-badge', source.source_tone]">
                      {{ source.source_category_label }}
                    </span>
                    <p class="mt-1 truncate text-xs text-slate-400">
                      {{ sourceModeLabel(source) }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <span
                      :class="[source.is_enabled ? 'badge-ok' : 'badge-muted']"
                    >
                      {{ source.is_enabled ? '启用' : '停用' }}
                    </span>
                  </td>
                  <td class="table-cell">
                    <div class="source-actions">
                      <OperationIconButton
                        icon="view"
                        :label="sourceViewLabel"
                        @click="$emit('view-source', source)"
                      />
                      <OperationIconButton
                        icon="edit"
                        :label="t('llmOps.providerManagement.actions.edit')"
                        @click="$emit('edit-source', source)"
                      />
                      <OperationIconButton
                        v-if="sourceCanManualEntry(source)"
                        icon="manual"
                        :label="
                          t('llmOps.providerManagement.actions.manualPricing')
                        "
                        @click="$emit('manual-entry-source', source)"
                      />
                      <OperationIconButton
                        :icon="source.is_enabled ? 'toggleOn' : 'toggleOff'"
                        :label="sourceToggleLabel(source)"
                        @click="$emit('toggle-source', source)"
                      />
                      <OperationIconButton
                        icon="collect"
                        tone="primary"
                        :disabled="
                          !sourceCanCollect(source) ||
                          String(collectingSourceId || '') === String(source.id)
                        "
                        :label="sourceCollectLabel(source)"
                        @click="$emit('collect-source', source)"
                      />
                      <OperationIconButton
                        icon="delete"
                        tone="danger"
                        :disabled="
                          String(deletingSourceId || '') === String(source.id)
                        "
                        :label="sourceDeleteLabel(source)"
                        @click="$emit('delete-source', source)"
                      />
                    </div>
                  </td>
                </tr>
                <tr v-if="!sourceRows.length">
                  <td class="table-cell text-slate-500" colspan="4">
                    当前厂商还没有模型价格源。
                  </td>
                </tr>
              </tbody>
            </table>
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
              class="grid w-full gap-3 md:max-w-md md:grid-cols-[minmax(0,1fr)_9rem]"
            >
              <input
                v-model="search"
                class="field-input"
                placeholder="搜索模型、来源或 code"
              />
              <select v-model="categoryFilter" class="field-input">
                <option value="all">全部来源</option>
                <option value="official_provider">原厂</option>
                <option value="cloud_hosted">云托管</option>
                <option value="supplier">供货商</option>
                <option value="manual">内部维护</option>
              </select>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="data-table pricing-source-table">
              <colgroup>
                <col class="model-col" />
                <col class="source-col" />
                <col class="type-col" />
                <col class="price-col" />
                <col class="time-col" />
              </colgroup>
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">模型价格源</th>
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
                  <td class="table-cell text-slate-500" colspan="5">
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
import { useI18n } from 'vue-i18n'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'

defineEmits([
  'close',
  'view-source',
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

const { t } = useI18n()
const search = ref('')
const categoryFilter = ref('all')
const sourceViewLabel = computed(() =>
  t('llmOps.providerManagement.actions.viewModels')
)

const priceSourceUrl = computed(() => {
  const source = preferredPriceSource(props.sources)
  return source?.endpoint_url || props.provider?.price_source_url || ''
})

const modelRows = computed(() =>
  props.models.flatMap((model) => buildModelRows(model))
)

const sourceRows = computed(() =>
  props.sources.map((source) => {
    const ownerType = sourceOwnerType(source)
    return {
      ...source,
      source_category_label: sourceOwnerTypeLabel(ownerType),
      source_tone: sourceOwnerTone(ownerType)
    }
  })
)

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
    const key = String(item.source || item.source_name || 'unbound-source')
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
    return items
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

function sourceCanCollect(source) {
  return Boolean(
    source?.is_enabled &&
      (source?.can_collect ||
        (source?.can_collect_prices &&
          sourceCollectionMethod(source) === 'auto_collect' &&
          source?.updates_model_prices))
  )
}

function sourceCanManualEntry(source) {
  return Boolean(
    source?.can_manual_entry ||
      ['manual_entry', 'manual_import', 'unknown'].includes(
        sourceCollectionMethod(source)
      )
  )
}

function sourceModeLabel(source) {
  const type = source?.source_type || ''
  const method = sourceCollectionMethod(source)
  if (String(source?.endpoint_url || '').includes('models.dev/api.json')) {
    return '聚合同步'
  }
  if (method === 'auto_collect') return '自动采集'
  if (method === 'manual_entry') return '手动维护'
  if (method === 'manual_import') return '批量导入'
  if (method === 'api_sync') return 'API 同步'
  if (type === 'yunce') return '专用采集'
  if (type === 'agione') return 'Agione'
  return type || '待适配'
}

function sourceCollectionMethod(source) {
  const method = source?.collection_method
  if (method && method !== 'unknown') return method
  if (source?.source_type === 'yunce') return 'api_sync'
  if (
    source?.source_category === 'official_provider' &&
    source?.updates_model_prices
  ) {
    return 'auto_collect'
  }
  if (source?.source_category === 'manual') return 'manual_entry'
  return method || 'unknown'
}

function sourceToggleLabel(source) {
  if (source?.is_enabled) {
    return t('llmOps.providerManagement.sourceStatus.inactive.label')
  }
  return t('llmOps.providerManagement.sourceStatus.active.label')
}

function sourceCollectLabel(source) {
  if (String(props.collectingSourceId || '') === String(source?.id)) {
    return t('llmOps.providerManagement.actions.submitting')
  }
  return t('llmOps.providerManagement.actions.syncPrice')
}

function sourceDeleteLabel(source) {
  if (String(props.deletingSourceId || '') === String(source?.id)) {
    return t('llmOps.providerManagement.actions.deleting')
  }
  return t('llmOps.providerManagement.actions.delete')
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

function sourceOwnerType(source) {
  const ownerType = source?.source_owner_type
  if (ownerType && ownerType !== 'unknown') return ownerType
  if (source?.source_category === 'official_provider') {
    return 'model_provider_official'
  }
  if (source?.source_category === 'supplier') return 'supplier'
  if (source?.source_category === 'manual') return 'internal'
  return ownerType || 'unknown'
}

function sourceOwnerTypeLabel(ownerType) {
  const labels = {
    model_provider_official: '模型厂商官方',
    cloud_provider_official: '云厂商官方',
    supplier: '供货商',
    internal: '内部维护',
    unknown: '其他'
  }
  return labels[ownerType] || labels.unknown
}

function sourceOwnerTone(ownerType) {
  const tones = {
    model_provider_official: 'official',
    cloud_provider_official: 'cloud',
    supplier: 'supplier',
    internal: 'manual',
    unknown: 'unknown'
  }
  return tones[ownerType] || 'unknown'
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
  width: 24%;
}

.pricing-source-table .source-col {
  width: 24%;
}

.pricing-source-table .type-col {
  width: 14%;
}

.pricing-source-table .price-col {
  width: 24%;
}

.pricing-source-table .time-col {
  width: 14%;
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
