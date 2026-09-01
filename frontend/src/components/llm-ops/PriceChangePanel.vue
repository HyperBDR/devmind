<template>
  <section class="space-y-4">
    <div class="grid gap-4 md:grid-cols-3">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.priceChangePanel.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.priceChangePanel.subtitle') }}
          </p>
        </div>
        <CompactSelect
          v-model="typeFilter"
          :options="typeFilterOptions"
          class-name="w-36"
          size="sm"
        />
        <p class="text-xs text-slate-500">{{ rangeSummary }}</p>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.object') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.dimension') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.source') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.priceChangePanel.columns.previous') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.priceChangePanel.columns.current') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.priceChangePanel.columns.change') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.currency') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.time') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.key">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ row.name }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ row.context }}</p>
              </td>
              <td class="table-cell">
                {{ dimensionLabel(row.dimension) }}
              </td>
              <td class="table-cell">
                <p>{{ row.source || '-' }}</p>
                <span :class="['status-pill', row.tone]">
                  {{ row.type_label }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.previous, row.currency) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.current, row.currency) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ deltaText(row) }}
              </td>
              <td class="table-cell">{{ row.currency || '-' }}</td>
              <td class="table-cell">{{ formatDateTime(row.time) }}</td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td class="table-cell text-slate-500" colspan="8">
                {{ t('llmOps.priceChangePanel.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from './CompactSelect.vue'
import {
  buildPriceChangeRows,
  priceChangeDelta
} from '@/utils/llmOpsPriceChanges'

const props = defineProps({
  channelHistory: { type: Array, default: () => [] },
  channelVersions: { type: Array, default: () => [] },
  focusModelId: { type: [Number, String], default: null },
  listingHistory: { type: Array, default: () => [] },
  officialHistory: { type: Array, default: () => [] },
  priceItems: { type: Array, default: () => [] }
})

const { t } = useI18n()
const typeFilter = ref('all')
const MAX_VISIBLE_ROWS = 120
const typeFilterOptions = computed(() => [
  { label: t('llmOps.priceChangePanel.filters.all'), value: 'all' },
  { label: t('llmOps.priceChangePanel.types.channel'), value: 'channel' },
  { label: t('llmOps.priceChangePanel.types.discount'), value: 'discount' },
  { label: t('llmOps.priceChangePanel.types.listing'), value: 'listing' },
  { label: t('llmOps.priceChangePanel.types.official'), value: 'official' }
])

const changeRows = computed(() => {
  return buildPriceChangeRows({
    channelHistory: props.channelHistory,
    channelVersions: props.channelVersions,
    listingHistory: props.listingHistory,
    officialHistory: props.officialHistory,
    priceItems: props.priceItems
  }).map((row) => ({
    ...row,
    name:
      row.name ||
      t('llmOps.priceChangePanel.fallback.model', { id: row.modelId }),
    type_label: t(`llmOps.priceChangePanel.types.${row.type}`),
    tone: {
      channel: 'info',
      discount: 'info',
      listing: 'warn',
      official: 'success'
    }[row.type]
  }))
})

const allFilteredRows = computed(() => {
  let rows = changeRows.value
  if (props.focusModelId) {
    rows = rows.filter(
      (row) => String(row.modelId) === String(props.focusModelId)
    )
  }
  if (typeFilter.value !== 'all') {
    rows = rows.filter((row) => row.type === typeFilter.value)
  }
  return rows
})

const filteredRows = computed(() =>
  allFilteredRows.value.slice(0, MAX_VISIBLE_ROWS)
)

const rangeSummary = computed(() =>
  t('llmOps.priceChangePanel.rangeSummary', {
    channel: props.channelHistory.length,
    listing: props.listingHistory.length,
    shown: filteredRows.value.length,
    total: allFilteredRows.value.length
  })
)

const metrics = computed(() => [
  {
    label: t('llmOps.priceChangePanel.metrics.channelHistory.label'),
    value: props.channelHistory.length,
    hint: t('llmOps.priceChangePanel.metrics.channelHistory.hint')
  },
  {
    label: t('llmOps.priceChangePanel.metrics.listingHistory.label'),
    value: props.listingHistory.length,
    hint: t('llmOps.priceChangePanel.metrics.listingHistory.hint')
  },
  {
    label: t('llmOps.priceChangePanel.metrics.officialItems.label'),
    value: props.priceItems.length,
    hint: t('llmOps.priceChangePanel.metrics.officialItems.hint')
  }
])

function dimensionLabel(value) {
  return (
    {
      discount: t('llmOps.priceChangePanel.dimension.discount'),
      text_input: t('llmOps.priceChangePanel.dimension.textInput'),
      text_output: t('llmOps.priceChangePanel.dimension.textOutput'),
      cache_input: t('llmOps.priceChangePanel.dimension.cacheInput'),
      image_output: t('llmOps.priceChangePanel.dimension.imageOutput'),
      audio_input: t('llmOps.priceChangePanel.dimension.audioInput'),
      audio_output: t('llmOps.priceChangePanel.dimension.audioOutput'),
      video_input: t('llmOps.priceChangePanel.dimension.videoInput'),
      video_output: t('llmOps.priceChangePanel.dimension.videoOutput')
    }[value] || value
  )
}

function deltaText(row) {
  const delta = priceChangeDelta(row)
  if (delta === null) return '-'
  const previous = Number(row.previous)
  const percent = previous ? ` (${((delta / previous) * 100).toFixed(2)}%)` : ''
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(6)}${percent}`
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  if (currency === 'ratio') return `${(Number(value) * 100).toFixed(2)}%`
  if (currency === 'fixed') return Number(value).toFixed(6)
  return `${currency || ''} ${Number(value).toFixed(6)}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
