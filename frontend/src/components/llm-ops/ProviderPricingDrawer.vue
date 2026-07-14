<template>
  <div
    v-if="provider"
    class="provider-pricing-drawer fixed inset-0 z-50 flex justify-end bg-slate-950/30"
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
            {{ t('common.close') }}
          </button>
        </div>
      </div>

      <div class="space-y-5 px-5 py-5">
        <div class="grid gap-3 md:grid-cols-5">
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">
              {{ t('llmOps.providerPricingDrawer.modelCount') }}
            </p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ models.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">
              {{ t('llmOps.providerPricingDrawer.pricedModelCount') }}
            </p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ pricedModelCount }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">
              {{ t('llmOps.providerPricingDrawer.modelPriceSources') }}
            </p>
            <p class="mt-1 font-mono text-sm text-slate-800">
              {{ sourceRows.length }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">
              {{ t('llmOps.providerPricingDrawer.priceStructure') }}
            </p>
            <p class="mt-1 text-sm text-slate-800">
              {{
                t('llmOps.providerPricingDrawer.priceStructureSummary', {
                  official: officialModelCount,
                  cloud: cloudHostedModelCount,
                  external: externalModelCount
                })
              }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-xs text-slate-500">
              {{ t('llmOps.providerPricingDrawer.priceSource') }}
            </p>
            <div v-if="primarySource" class="mt-1 min-w-0">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-900">
                  {{ primarySource.name }}
                </p>
                <p class="mt-1 truncate font-mono text-xs text-slate-400">
                  {{
                    t('llmOps.providerPricingDrawer.sourceSummary', {
                      slug: primarySource.slug,
                      count: sourceRows.length
                    })
                  }}
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
              <h3 class="panel-title">
                {{ t('llmOps.providerPricingDrawer.title') }}
              </h3>
              <p class="mt-1 text-xs text-slate-500">
                {{ t('llmOps.providerPricingDrawer.subtitle') }}
              </p>
            </div>
            <div
              class="grid w-full gap-3 md:max-w-xl md:grid-cols-[minmax(0,1fr)_auto]"
            >
              <input
                v-model="search"
                class="field-input"
                :placeholder="
                  t('llmOps.providerPricingDrawer.searchPlaceholder')
                "
              />
              <div
                class="filter-tabs"
                role="tablist"
                :aria-label="t('llmOps.providerPricingDrawer.sourceType')"
              >
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
                  <th class="table-head">{{ t('llmOps.fields.model') }}</th>
                  <th class="table-head">
                    {{ t('llmOps.providerPricingDrawer.sourceType') }}
                  </th>
                  <th class="table-head">
                    {{ t('llmOps.providerPricingDrawer.priceSummary') }}
                  </th>
                  <th class="table-head">
                    {{ t('llmOps.providerPricingDrawer.updatedAt') }}
                  </th>
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
                    <span v-else class="text-xs text-slate-400">
                      {{ t('llmOps.providerPricingDrawer.noPrice') }}
                    </span>
                  </td>
                  <td class="table-cell">
                    {{ formatDateTime(row.updated_at) }}
                  </td>
                </tr>
                <tr v-if="!filteredModelRows.length">
                  <td class="table-cell text-slate-500" colspan="4">
                    {{ t('llmOps.providerPricingDrawer.empty') }}
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
import '@/components/llm-ops/providerPricingDrawer.css'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  canCollectPriceSource,
  canManualEntryPriceSource,
  isLegacyOfficialModelSource as baseIsLegacyOfficialModelSource,
  isProviderOfficialPriceSource as baseIsProviderOfficialPriceSource,
  normalizePriceSourceCategory as businessSourceCategory,
  officialProviderCodeFromSlug as baseOfficialProviderCodeFromSlug,
  preferredPriceSource,
  priceSourceCategoryRank as categoryRank,
  priceSourceGroupKey as basePriceSourceGroupKey,
  priceSourceTone as sourceTone
} from '@/utils/llmOpsPriceSources'

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

const modelRows = computed(() =>
  props.models.flatMap((model) => buildModelRows(model))
)

const categoryFilterOptions = computed(() => {
  const counts = sourceCategoryCounts(modelRows.value)
  return [
    {
      value: 'all',
      label: t('llmOps.providerPricingDrawer.allSources'),
      count: modelRows.value.length
    },
    {
      value: 'official_provider',
      label: sourceCategoryLabel('official_provider'),
      count: counts.official_provider || 0
    },
    {
      value: 'cloud_hosted',
      label: sourceCategoryLabel('cloud_hosted'),
      count: counts.cloud_hosted || 0
    },
    {
      value: 'supplier',
      label: sourceCategoryLabel('supplier'),
      count: counts.supplier || 0
    },
    {
      value: 'manual',
      label: sourceCategoryLabel('manual'),
      count: counts.manual || 0
    }
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
      t('llmOps.providerPricingDrawer.unboundPriceSource'),
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
    category_label: sourceCategoryLabel(businessSourceCategory(primary)),
    category_tone: sourceTone(businessSourceCategory(primary)),
    source_group_key: priceSourceGroupKey(primary),
    source_group_ids: sourceIds,
    source_count: sorted.length,
    updated_at: latestUpdate || primary.updated_at,
    can_collect: sorted.some((source) => canCollectPriceSource(source)),
    can_manual_entry: sorted.some((source) =>
      canManualEntryPriceSource(source)
    ),
    collect_action_label: primary.collect_action_label,
    price_item_count: priceItems.filter(
      (item) =>
        sourceIds.includes(String(item.source || '')) &&
        item.is_current !== false
    ).length
  }
}

function priceSourceGroupKey(source) {
  return basePriceSourceGroupKey(source, props.provider?.code || '')
}

function isLegacyOfficialModelSource(source) {
  return baseIsLegacyOfficialModelSource(source, props.provider?.code || '')
}

function isProviderOfficialSource(source) {
  return baseIsProviderOfficialPriceSource(source, props.provider?.code || '')
}

function aggregateSourceName(source) {
  const providerName = source.provider_name || props.provider?.name || ''
  if (!isLegacyOfficialModelSource(source)) {
    return (
      source?.name ||
      (providerName
        ? t('llmOps.providerPricingDrawer.officialPriceName', {
            provider: providerName
          })
        : '-')
    )
  }
  return t('llmOps.providerPricingDrawer.officialPriceName', {
    provider:
      providerName ||
      source.provider_code ||
      t('llmOps.providerPricingDrawer.providerFallback')
  })
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
  return baseOfficialProviderCodeFromSlug(source, props.provider?.code || '')
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: t('llmOps.providerPricingDrawer.dimension.textInput'),
    text_output: t('llmOps.providerPricingDrawer.dimension.textOutput'),
    cache_input: t('llmOps.providerPricingDrawer.dimension.cacheInput'),
    image_input: t('llmOps.providerPricingDrawer.dimension.imageInput'),
    image_output: t('llmOps.providerPricingDrawer.dimension.imageOutput'),
    audio_input: t('llmOps.providerPricingDrawer.dimension.audioInput'),
    audio_output: t('llmOps.providerPricingDrawer.dimension.audioOutput'),
    video_input: t('llmOps.providerPricingDrawer.dimension.videoInput'),
    video_output: t('llmOps.providerPricingDrawer.dimension.videoOutput')
  }
  return labels[dimension] || dimension || '-'
}

function tokenPricingItems(model) {
  return [
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.input1m'),
      model.input_price_per_million,
      model.currency
    ),
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.output1m'),
      model.output_price_per_million,
      model.currency
    ),
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.cacheInput1m'),
      model.cache_input_price_per_million,
      model.currency
    )
  ].filter(Boolean)
}

function audioPricingItems(model) {
  return [
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.audioInputSecond'),
      model.audio_input_price_per_second,
      model.currency
    ),
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.audioOutputSecond'),
      model.audio_output_price_per_second,
      model.currency
    )
  ].filter(Boolean)
}

function imagePricingItems(model) {
  return [
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.imageOutputImage'),
      model.image_output_price_per_image,
      model.currency
    )
  ].filter(Boolean)
}

function videoPricingItems(model) {
  const items = [
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.videoInputSecond'),
      model.video_input_price_per_second,
      model.currency
    ),
    priceItem(
      t('llmOps.providerPricingDrawer.legacyPrice.videoOutputSecond'),
      model.video_output_price_per_second,
      model.currency
    )
  ].filter(Boolean)
  const resolutionItems = Object.entries(model.video_resolution_prices || {})
    .slice(0, 2)
    .flatMap(([resolution, price]) => [
      priceItem(
        t('llmOps.providerPricingDrawer.legacyPrice.resolutionInput', {
          resolution
        }),
        price?.input,
        model.currency
      ),
      priceItem(
        t('llmOps.providerPricingDrawer.legacyPrice.resolutionOutput', {
          resolution
        }),
        price?.output,
        model.currency
      )
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
    text_input: t('llmOps.providerPricingDrawer.compactDimension.input'),
    text_output: t('llmOps.providerPricingDrawer.compactDimension.output'),
    cache_input: t('llmOps.providerPricingDrawer.compactDimension.cache'),
    image_input: t('llmOps.providerPricingDrawer.compactDimension.imageInput'),
    image_output: t(
      'llmOps.providerPricingDrawer.compactDimension.imageOutput'
    ),
    audio_input: t('llmOps.providerPricingDrawer.compactDimension.audioInput'),
    audio_output: t(
      'llmOps.providerPricingDrawer.compactDimension.audioOutput'
    ),
    video_input: t('llmOps.providerPricingDrawer.compactDimension.videoInput'),
    video_output: t('llmOps.providerPricingDrawer.compactDimension.videoOutput')
  }
  const base = labels[dimension] || dimensionLabel(dimension)
  if (billingUnit === 'per_image') {
    return t('llmOps.providerPricingDrawer.billingUnit.perImage', { base })
  }
  if (billingUnit === 'per_second') {
    return t('llmOps.providerPricingDrawer.billingUnit.perSecond', { base })
  }
  if (billingUnit === 'per_generation') {
    return t('llmOps.providerPricingDrawer.billingUnit.perGeneration', {
      base
    })
  }
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
    text: t('llmOps.providerPricingDrawer.modality.text'),
    audio: t('llmOps.providerPricingDrawer.modality.audio'),
    video: t('llmOps.providerPricingDrawer.modality.video'),
    multimodal: t('llmOps.providerPricingDrawer.modality.multimodal')
  }
  return labels[modality] || modality || '-'
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: t(
      'llmOps.providerPricingDrawer.sourceCategory.officialProvider'
    ),
    cloud_hosted: t('llmOps.providerPricingDrawer.sourceCategory.cloudHosted'),
    supplier: t('llmOps.providerPricingDrawer.sourceCategory.supplier'),
    manual: t('llmOps.providerPricingDrawer.sourceCategory.manual'),
    unknown: t('llmOps.providerPricingDrawer.sourceCategory.unknown')
  }
  return labels[category] || labels.unknown
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
