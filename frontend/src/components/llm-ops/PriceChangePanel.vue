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
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.object') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.priceChangePanel.columns.type') }}
              </th>
              <th class="table-head text-right">Input</th>
              <th class="table-head text-right">Output</th>
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
                <span :class="['status-pill', row.tone]">
                  {{ row.type_label }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.input, row.currency) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.output, row.currency) }}
              </td>
              <td class="table-cell">{{ row.currency || '-' }}</td>
              <td class="table-cell">{{ formatDateTime(row.time) }}</td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td class="table-cell text-slate-500" colspan="6">
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

const props = defineProps({
  channelHistory: { type: Array, default: () => [] },
  listingHistory: { type: Array, default: () => [] },
  priceItems: { type: Array, default: () => [] }
})

const { t } = useI18n()
const typeFilter = ref('all')
const typeFilterOptions = computed(() => [
  { label: t('llmOps.priceChangePanel.filters.all'), value: 'all' },
  { label: t('llmOps.priceChangePanel.types.channel'), value: 'channel' },
  { label: t('llmOps.priceChangePanel.types.listing'), value: 'listing' },
  { label: t('llmOps.priceChangePanel.types.official'), value: 'official' }
])

const changeRows = computed(() => {
  const channelRows = props.channelHistory.map((item) => ({
    key: `channel-${item.id}`,
    type: 'channel',
    type_label: t('llmOps.priceChangePanel.types.channel'),
    tone: 'info',
    name:
      item.model_name ||
      t('llmOps.priceChangePanel.fallback.model', { id: item.model }),
    context:
      item.channel_name ||
      t('llmOps.priceChangePanel.fallback.channel', { id: item.channel }),
    input: item.input_price_per_million,
    output: item.output_price_per_million,
    currency: item.currency,
    time: item.effective_from || item.created_at
  }))
  const listingRows = props.listingHistory.map((item) => ({
    key: `listing-${item.id}`,
    type: 'listing',
    type_label: t('llmOps.priceChangePanel.types.listing'),
    tone: 'warn',
    name:
      item.model_name ||
      t('llmOps.priceChangePanel.fallback.model', { id: item.model }),
    context:
      item.platform_name ||
      t('llmOps.priceChangePanel.fallback.platform', {
        id: item.platform
      }),
    input: item.retail_input_price_per_million,
    output: item.retail_output_price_per_million,
    currency: item.currency,
    time: item.effective_from || item.created_at
  }))
  const officialRows = recentOfficialRows()
  return [...channelRows, ...listingRows, ...officialRows].sort(
    (left, right) => new Date(right.time || 0) - new Date(left.time || 0)
  )
})

const filteredRows = computed(() => {
  const rows = changeRows.value.slice(0, 120)
  if (typeFilter.value === 'all') return rows
  return rows.filter((row) => row.type === typeFilter.value)
})

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

function recentOfficialRows() {
  return props.priceItems.slice(0, 80).map((item) => ({
    key: `official-${item.id}`,
    type: 'official',
    type_label: t('llmOps.priceChangePanel.types.official'),
    tone: 'success',
    name:
      item.model_name ||
      t('llmOps.priceChangePanel.fallback.model', { id: item.model }),
    context: dimensionLabel(item.dimension),
    input: item.dimension === 'text_input' ? item.unit_price : null,
    output: item.dimension === 'text_output' ? item.unit_price : null,
    currency: item.currency,
    time: item.effective_from || item.updated_at || item.created_at
  }))
}

function dimensionLabel(value) {
  return (
    {
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

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || ''} ${Number(value).toFixed(6)}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
