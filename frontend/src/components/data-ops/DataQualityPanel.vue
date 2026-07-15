<template>
  <section class="space-y-4" aria-labelledby="data-quality-title">
    <div class="rounded-lg border p-5" :class="statusPanelClass">
      <div
        class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"
      >
        <div>
          <p class="text-sm font-bold" :class="statusTextClass">
            {{ t('dataOps.quality.label', { status: dataQualityLabel }) }}
          </p>
          <h2
            id="data-quality-title"
            class="mt-3 text-xl font-bold text-slate-950"
          >
            {{ t('dataOps.quality.title') }}
          </h2>
          <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {{ t('dataOps.quality.description') }}
          </p>
        </div>
        <span
          class="inline-flex shrink-0 items-center rounded-full px-3 py-1 text-xs font-bold"
          :class="statusBadgeClass"
        >
          {{ dataQualityLabel }}
        </span>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div
          v-for="metric in qualityMetrics"
          :key="metric.label"
          class="rounded-lg bg-white/75 px-3 py-2"
        >
          <p class="text-xs font-semibold text-slate-500">
            {{ metric.label }}
          </p>
          <p class="mt-1 text-lg font-bold text-slate-950">
            {{ metric.value }}
          </p>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <section
        v-for="panel in currencyPanels"
        :key="panel.title"
        class="rounded-lg border border-slate-200 bg-white p-4"
      >
        <h3 class="text-sm font-bold text-slate-950">
          {{ panel.title }}
        </h3>
        <div class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="item in panel.items"
            :key="`${panel.title}-${item.currency}`"
            class="rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600"
          >
            {{ item.currency || t('dataOps.common.unknown') }} ·
            {{ formatPlainAmount(item.amount) }}
          </span>
          <span v-if="!panel.items.length" class="text-sm text-slate-400">
            {{ t('dataOps.quality.noCurrency') }}
          </span>
        </div>
      </section>
    </div>

    <section class="rounded-lg border border-slate-200 bg-white p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 class="text-base font-bold text-slate-950">
            {{ t('dataOps.quality.issues') }}
          </h3>
          <p class="mt-1 text-sm text-slate-500">
            {{ t('dataOps.quality.currencyNote') }}
          </p>
        </div>
        <span class="text-xs font-semibold text-slate-400">
          {{
            t('dataOps.quality.issueTypes', {
              count: dataQualityIssues.length
            })
          }}
        </span>
      </div>
      <div class="mt-4 divide-y divide-slate-100">
        <article
          v-for="item in dataQualityIssues"
          :key="item.id || item.title"
          class="py-4 first:pt-0 last:pb-0"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h4 class="text-sm font-bold text-slate-950">
              {{ item.title }}
            </h4>
            <span
              class="rounded-full px-2 py-0.5 text-xs font-bold"
              :class="
                item.severity === 'failed'
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-amber-100 text-amber-700'
              "
            >
              {{
                item.severity === 'failed'
                  ? t('dataOps.quality.highRisk')
                  : t('dataOps.quality.attention')
              }}
              {{ t('dataOps.quality.items', { count: item.count || 0 }) }}
            </span>
          </div>
          <p class="mt-2 text-sm text-slate-600">{{ item.detail }}</p>
          <p class="mt-1 text-sm text-slate-500">
            {{ item.recommendation }}
          </p>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale, t } = useI18n()

const props = defineProps({
  dataQuality: { type: Object, default: null },
  summary: { type: Object, default: null }
})

const dataQualityLabel = computed(() => {
  if (props.dataQuality?.overall_status === 'failed') {
    return t('dataOps.quality.highRisk')
  }
  if (props.dataQuality?.overall_status === 'warning') {
    return t('dataOps.quality.attention')
  }
  return t('dataOps.quality.normal')
})

const statusPanelClass = computed(() => {
  if (props.dataQuality?.overall_status === 'failed') {
    return 'border-rose-200 bg-rose-50'
  }
  if (props.dataQuality?.overall_status === 'warning') {
    return 'border-amber-200 bg-amber-50'
  }
  return 'border-emerald-200 bg-emerald-50'
})

const statusTextClass = computed(() => {
  if (props.dataQuality?.overall_status === 'failed') return 'text-rose-700'
  if (props.dataQuality?.overall_status === 'warning') return 'text-amber-700'
  return 'text-emerald-700'
})

const statusBadgeClass = computed(() => {
  if (props.dataQuality?.overall_status === 'failed') {
    return 'bg-rose-100 text-rose-700'
  }
  if (props.dataQuality?.overall_status === 'warning') {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-emerald-100 text-emerald-700'
})

const qualityMetrics = computed(() => [
  {
    label: t('dataOps.quality.runningJobs'),
    value: props.dataQuality?.running_sync_count || 0
  },
  {
    label: t('dataOps.quality.failedJobs'),
    value: props.dataQuality?.failed_sync_count || 0
  },
  {
    label: t('dataOps.quality.warningJobs'),
    value: props.dataQuality?.warning_sync_count || 0
  }
])

const currencyPanels = computed(() => [
  {
    title: t('dataOps.quality.contractCurrencies'),
    items: props.summary?.total_contract_amount_by_currency || []
  },
  {
    title: t('dataOps.quality.ledgerCurrencies'),
    items: props.summary?.total_received_amount_by_currency || []
  }
])

const dataQualityIssues = computed(() => {
  const issues = props.dataQuality?.issues || []
  if (issues.length) return issues
  return [
    {
      id: 'currency',
      title: t('dataOps.quality.mixedCurrency'),
      severity: 'warning',
      count: currencyPanels.value[0].items.length,
      detail: t('dataOps.quality.mixedCurrencyDetail'),
      recommendation: t('dataOps.quality.mixedCurrencyRecommendation')
    }
  ]
})

function formatPlainAmount(value) {
  return new Intl.NumberFormat(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
    maximumFractionDigits: 2
  }).format(Number(value || 0))
}
</script>
