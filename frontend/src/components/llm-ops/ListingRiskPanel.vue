<template>
  <section class="space-y-4">
    <div class="grid gap-4 md:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">{{ t('llmOps.listingRisk.title') }}</h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.listingRisk.subtitle') }}
          </p>
        </div>
        <CompactSelect
          v-model="riskFilter"
          :options="riskFilterOptions"
          class-name="w-36"
          size="sm"
        />
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.listingRisk.columns.model') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingRisk.columns.risk') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.listingRisk.columns.inputMargin') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.listingRisk.columns.outputMargin') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingRisk.columns.channel') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingRisk.columns.action') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.key">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ row.model_name }}</p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ row.provider_name }}
                </p>
              </td>
              <td class="table-cell">
                <span :class="['status-pill', row.tone]">
                  {{ row.risk_label }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.input_margin) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.output_margin) }}
              </td>
              <td class="table-cell">
                {{ row.channel_name || '-' }}
              </td>
              <td class="table-cell text-slate-600">
                {{ row.action }}
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td class="table-cell text-slate-500" colspan="6">
                {{ t('llmOps.listingRisk.empty') }}
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

import { operationScopeForRow } from '@/utils/llmOpsMonitor'
import { asArray } from '@/utils/llmOpsPagination'

import CompactSelect from './CompactSelect.vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) }
})

const { t, te } = useI18n()
const riskFilter = ref('all')
const riskFilterOptions = computed(() => [
  { label: t('llmOps.listingRisk.filters.all'), value: 'all' },
  { label: t('llmOps.listingRisk.risk.margin'), value: 'margin' },
  { label: t('llmOps.listingRisk.risk.not_lowest'), value: 'not_lowest' },
  { label: t('llmOps.listingRisk.risk.unlisted'), value: 'unlisted' },
  {
    label: t('llmOps.listingRisk.risk.currency_mismatch'),
    value: 'currency_mismatch'
  }
])

const diagnosticRows = computed(() =>
  asArray(props.summary.agione?.diagnostics)
)
const selectedPlatformId = computed(() => props.summary.agione?.platform_id)
const listingRows = computed(() => {
  const rows = asArray(props.summary.listings)
  if (!selectedPlatformId.value) return rows
  return rows.filter(
    (listing) =>
      String(listing.platform_id) === String(selectedPlatformId.value)
  )
})

const riskRows = computed(() => {
  const rows = []
  diagnosticRows.value.forEach((row) => {
    if (operationScopeForRow(row) === 'market_reference') return
    if (row.status === 'ready' || row.status === 'low_coverage') return
    rows.push({
      key: `diag-${row.model_id}-${row.status}`,
      model_id: row.model_id,
      model_name: row.model_name,
      provider_name: row.provider_name,
      risk: row.status,
      risk_label: statusLabel(row.status),
      tone: statusTone(row.status),
      input_margin: null,
      output_margin: null,
      channel_name: channelDisplayName(row.best_channel),
      action: actionText(row.status)
    })
  })
  listingRows.value.forEach((listing) => {
    const inputMargin = listing.input_margin?.margin_rate
    const outputMargin = listing.output_margin?.margin_rate
    if (!isLowMargin(inputMargin) && !isLowMargin(outputMargin)) return
    rows.push({
      key: `listing-${listing.listing_id}`,
      model_id: listing.model_id,
      model_name: listing.model_name,
      provider_name: listing.platform_name,
      risk: 'margin',
      risk_label: t('llmOps.listingRisk.risk.margin'),
      tone: 'danger',
      input_margin: inputMargin,
      output_margin: outputMargin,
      channel_name: channelDisplayName(listing),
      action: t('llmOps.listingRisk.actions.margin')
    })
  })
  return rows.sort((left, right) => riskRank(left.risk) - riskRank(right.risk))
})

const filteredRows = computed(() => {
  if (riskFilter.value === 'all') return riskRows.value
  return riskRows.value.filter((row) => row.risk === riskFilter.value)
})

const metrics = computed(() => [
  {
    label: t('llmOps.listingRisk.metrics.total.label'),
    value: riskRows.value.length,
    hint: t('llmOps.listingRisk.metrics.total.hint')
  },
  {
    label: t('llmOps.listingRisk.metrics.margin.label'),
    value: riskRows.value.filter((row) => row.risk === 'margin').length,
    hint: t('llmOps.listingRisk.metrics.margin.hint')
  },
  {
    label: t('llmOps.listingRisk.metrics.notLowest.label'),
    value: riskRows.value.filter((row) => row.risk === 'not_lowest').length,
    hint: t('llmOps.listingRisk.metrics.notLowest.hint')
  },
  {
    label: t('llmOps.listingRisk.metrics.unlisted.label'),
    value: riskRows.value.filter((row) => row.risk === 'unlisted').length,
    hint: t('llmOps.listingRisk.metrics.unlisted.hint')
  }
])

function isLowMargin(value) {
  if (value === null || value === undefined) return false
  return Number(value) < 0.1
}

function statusLabel(status) {
  const key = `llmOps.listingRisk.risk.${status}`
  return te(key) ? t(key) : status
}

function statusTone(status) {
  return (
    {
      currency_mismatch: 'info',
      missing_channel: 'danger',
      unlisted: 'warn',
      not_lowest: 'warn'
    }[status] || 'info'
  )
}

function actionText(status) {
  const key = `llmOps.listingRisk.actions.${status}`
  return te(key) ? t(key) : t('llmOps.listingRisk.actions.fallback')
}

function riskRank(status) {
  return (
    {
      margin: 1,
      missing_channel: 2,
      currency_mismatch: 3,
      not_lowest: 4,
      unlisted: 5
    }[status] || 9
  )
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function channelDisplayName(value) {
  if (!value) return ''
  if (value.channel_type === 'auto_best' || value.channel_id === null) {
    return t('llmOps.channel.autoBest')
  }
  return value.channel_name || ''
}
</script>
