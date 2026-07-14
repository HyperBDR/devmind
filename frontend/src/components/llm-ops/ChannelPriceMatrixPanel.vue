<template>
  <section class="space-y-4">
    <div class="panel">
      <div
        class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"
      >
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.channelPriceMatrixPanel.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.channelPriceMatrixPanel.subtitle') }}
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <input
            v-model="keyword"
            class="llm-ops-input h-9 w-full sm:w-64"
            :placeholder="t('llmOps.channelPriceMatrixPanel.searchPlaceholder')"
            type="search"
          />
          <CompactSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
            class-name="w-full sm:w-36"
            size="sm"
          />
        </div>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="overflow-x-auto">
        <table class="data-table min-w-[980px]">
          <thead>
            <tr>
              <th class="table-head sticky left-0 z-10 bg-white">
                {{ t('llmOps.fields.model') }}
              </th>
              <th
                v-for="channel in visibleChannels"
                :key="channel.id"
                class="table-head text-right"
              >
                {{ channel.name }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.channelPriceMatrixPanel.columns.coverage') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.channelPriceMatrixPanel.columns.lowestChannel') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.model_id">
              <td class="table-cell sticky left-0 z-10 bg-white">
                <p class="font-medium text-slate-900">{{ row.model_name }}</p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ row.provider_name }}
                </p>
              </td>
              <td
                v-for="channel in visibleChannels"
                :key="`${row.model_id}-${channel.id}`"
                class="table-cell text-right"
              >
                <span
                  v-if="optionFor(row, channel)"
                  :class="[
                    'font-mono text-xs',
                    isBest(row, channel) ? 'text-emerald-700' : 'text-slate-700'
                  ]"
                >
                  {{ priceSummary(optionFor(row, channel)) }}
                </span>
                <span v-else class="text-xs text-slate-400">-</span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ row.coverage_count || 0 }} / {{ visibleChannels.length }}
              </td>
              <td class="table-cell">
                <span v-if="row.best_channel" class="status-pill success">
                  {{ row.best_channel.channel_name }}
                </span>
                <span v-else class="status-pill danger">
                  {{ t('llmOps.channelPriceMatrixPanel.status.missing') }}
                </span>
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td
                class="table-cell text-slate-500"
                :colspan="visibleChannels.length + 3"
              >
                {{ t('llmOps.channelPriceMatrixPanel.empty') }}
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

import { asArray } from '@/utils/llmOpsPagination'

import CompactSelect from './CompactSelect.vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
  channels: { type: Array, default: () => [] }
})

const { t } = useI18n()
const keyword = ref('')
const statusFilter = ref('all')
const statusFilterOptions = computed(() => [
  { label: t('llmOps.channelPriceMatrixPanel.filters.all'), value: 'all' },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.missing'),
    value: 'missing'
  },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.single'),
    value: 'single'
  },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.ready'),
    value: 'ready'
  }
])

const rows = computed(() => asArray(props.summary.agione?.diagnostics))
const visibleChannels = computed(() =>
  props.channels.filter((channel) => channel.is_active !== false)
)

const filteredRows = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const matchesKeyword =
      !query ||
      String(row.model_name || '')
        .toLowerCase()
        .includes(query) ||
      String(row.model_code || '')
        .toLowerCase()
        .includes(query) ||
      String(row.provider_name || '')
        .toLowerCase()
        .includes(query)
    if (!matchesKeyword) return false
    if (statusFilter.value === 'missing') return !row.best_channel
    if (statusFilter.value === 'single') return row.coverage_count === 1
    if (statusFilter.value === 'ready') return row.coverage_count > 1
    return true
  })
})

const metrics = computed(() => {
  const total = rows.value.length
  const covered = rows.value.filter((row) => row.best_channel).length
  const single = rows.value.filter((row) => row.coverage_count === 1).length
  const missing = rows.value.filter((row) => !row.best_channel).length
  return [
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.total.label'),
      value: total,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.total.hint')
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.covered.label'),
      value: covered,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.covered.hint', {
        percent: percentage(covered, total)
      })
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.single.label'),
      value: single,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.single.hint')
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.missing.label'),
      value: missing,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.missing.hint')
    }
  ]
})

function optionFor(row, channel) {
  return (row.options || []).find(
    (option) => String(option.channel_id) === String(channel.id)
  )
}

function isBest(row, channel) {
  return String(row.best_channel?.channel_id) === String(channel.id)
}

function priceSummary(option) {
  const input = money(option.input_price_per_million, option.currency)
  const output = money(option.output_price_per_million, option.currency)
  return `In ${input} / Out ${output}`
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || ''} ${Number(value).toFixed(4)}`
}

function percentage(value, total) {
  if (!total) return 0
  return Math.round((Number(value || 0) / Number(total)) * 100)
}
</script>
