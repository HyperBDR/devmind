<template>
  <section
    class="rounded-xl border border-slate-200 bg-white"
    aria-labelledby="observation-detail-title"
  >
    <div class="border-b border-slate-200 px-4 py-3">
      <h2
        id="observation-detail-title"
        class="text-sm font-bold text-slate-950"
      >
        {{ t('dataOps.observations.detailTitle') }}
      </h2>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('dataOps.observations.detailDescription') }}
      </p>
    </div>

    <div
      v-if="loading"
      class="px-4 py-12 text-center text-sm text-slate-500"
      role="status"
    >
      {{ t('dataOps.observations.loadingDetail') }}
    </div>
    <div
      v-else-if="!observation"
      class="px-4 py-12 text-center text-sm text-slate-400"
    >
      {{ t('dataOps.observations.selectPrompt') }}
    </div>

    <div v-else class="space-y-5 p-4">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="rounded-full px-2 py-1 text-[11px] font-bold"
            :class="severityClass(observation.severity)"
          >
            {{ severityLabel(observation.severity) }}
          </span>
          <span
            class="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600"
          >
            {{ statusLabel(observation.status) }}
          </span>
        </div>
        <p class="mt-3 text-sm font-semibold leading-6 text-slate-900">
          {{ observation.statement }}
        </p>
        <p class="mt-2 text-xs text-slate-500">
          {{ t('dataOps.observations.lastEvaluated') }} ·
          {{ formatDateTime(observation.last_evaluated_at, locale) }}
        </p>
      </div>

      <div>
        <h3 class="text-xs font-bold uppercase tracking-wide text-slate-500">
          {{ t('dataOps.observations.factsTitle') }}
        </h3>
        <dl
          class="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200"
        >
          <div
            v-for="([key, value], index) in structuredEntries"
            :key="key"
            class="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-3 px-3 py-2 text-xs"
            :class="index % 2 ? 'bg-slate-50/60' : 'bg-white'"
          >
            <dt class="text-slate-500">{{ fieldLabel(key) }}</dt>
            <dd class="break-words text-right font-semibold text-slate-800">
              {{ formatValue(value) }}
            </dd>
          </div>
        </dl>
      </div>

      <div>
        <h3 class="text-xs font-bold uppercase tracking-wide text-slate-500">
          {{ t('dataOps.observations.evidenceTitle') }}
        </h3>
        <div v-if="observation.evidence?.length" class="mt-3 space-y-3">
          <article
            v-for="item in observation.evidence"
            :key="item.id"
            class="rounded-lg border border-slate-200 bg-slate-50 p-3"
          >
            <p class="text-xs font-bold text-slate-800">
              {{ item.source_model }} · {{ item.source_record_id }}
            </p>
            <p class="mt-1 text-[11px] text-slate-500">
              {{ t('dataOps.observations.capturedAt') }}
              {{ formatDateTime(item.captured_at, locale) }}
            </p>
            <dl class="mt-3 space-y-2 border-t border-slate-200 pt-3">
              <div
                v-for="[key, value] in snapshotEntries(item)"
                :key="key"
                class="flex items-start justify-between gap-3 text-xs"
              >
                <dt class="text-slate-500">{{ fieldLabel(key) }}</dt>
                <dd class="max-w-[60%] break-words text-right text-slate-800">
                  {{ formatValue(value) }}
                </dd>
              </div>
            </dl>
          </article>
        </div>
        <p v-else class="mt-3 text-sm text-slate-400">
          {{ t('dataOps.observations.noEvidence') }}
        </p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateTime } from '@/composables/useDataOpsConsole'

const props = defineProps({
  loading: { type: Boolean, default: false },
  observation: { type: Object, default: null }
})

const { locale, t } = useI18n()

const structuredEntries = computed(() =>
  Object.entries(props.observation?.structured_value || {})
)

function snapshotEntries(evidence) {
  return Object.entries(evidence?.snapshot || {})
}

function fieldLabel(key) {
  const labels = {
    contract_number: t('dataOps.columns.contractNumber'),
    currency: t('dataOps.columns.currency'),
    customer_name: t('dataOps.columns.customerName'),
    days_overdue: t('dataOps.observations.fields.daysOverdue'),
    days_until_expiry: t('dataOps.observations.fields.daysUntilExpiry'),
    expected_payment_date: t('dataOps.observations.fields.expectedPaymentDate'),
    expiry_status: t('dataOps.observations.fields.expiryStatus'),
    ledger_type: t('dataOps.observations.fields.ledgerType'),
    outstanding: t('dataOps.observations.fields.outstanding'),
    payment_status: t('dataOps.observations.fields.paymentStatus'),
    project_name: t('dataOps.columns.projectName'),
    sales_person: t('dataOps.columns.owner'),
    service_end: t('dataOps.columns.serviceEnd'),
    status: t('dataOps.observations.fields.contractStatus')
  }
  return labels[key] || key.replaceAll('_', ' ')
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function severityLabel(value) {
  return t(`dataOps.observations.severity.${value || 'low'}`)
}

function statusLabel(value) {
  return t(`dataOps.observations.status.${value || 'active'}`)
}

function severityClass(value) {
  return (
    {
      critical: 'bg-rose-100 text-rose-800',
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-amber-100 text-amber-800',
      low: 'bg-sky-100 text-sky-800'
    }[value] || 'bg-slate-100 text-slate-700'
  )
}
</script>
