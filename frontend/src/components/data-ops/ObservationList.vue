<template>
  <div class="space-y-3">
    <div
      v-if="observations.length"
      class="overflow-hidden rounded-xl border border-slate-200 bg-white"
    >
      <button
        v-for="item in observations"
        :key="item.id"
        type="button"
        class="block w-full border-b border-slate-100 px-4 py-4 text-left transition-colors last:border-b-0 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500"
        :class="selectedId === item.id ? 'bg-indigo-50/70' : 'bg-white'"
        :aria-pressed="selectedId === item.id"
        @click="$emit('select', item.id)"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span
              class="rounded-full px-2 py-1 text-[11px] font-bold"
              :class="severityClass(item.severity)"
            >
              {{ severityLabel(item.severity) }}
            </span>
            <span class="text-[11px] font-semibold text-slate-500">
              {{ typeLabel(item.observation_type) }}
            </span>
          </div>
          <span class="text-[11px] text-slate-500">
            {{ formatDateTime(item.generated_at, locale) }}
          </span>
        </div>
        <p class="mt-2 text-sm font-semibold leading-6 text-slate-900">
          {{ item.statement }}
        </p>
        <p class="mt-2 text-xs text-slate-500">
          {{ statusLabel(item.status) }} · {{ item.producer_key }}
        </p>
      </button>
    </div>
    <div
      v-else
      class="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-16 text-center text-sm text-slate-400"
    >
      {{ t('dataOps.observations.empty') }}
    </div>
    <Pager
      :page="page"
      :page-size="pageSize"
      :total="total"
      @change="$emit('page-change', $event)"
    />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { formatDateTime } from '@/composables/useDataOpsConsole'

import { Pager } from './DataOpsPrimitives'

defineProps({
  observations: { type: Array, default: () => [] },
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  selectedId: { type: String, default: '' },
  total: { type: Number, required: true }
})

defineEmits(['page-change', 'select'])
const { locale, t } = useI18n()

function typeLabel(value) {
  const key =
    value === 'receivable_overdue_risk'
      ? 'receivableOverdue'
      : 'contractRenewal'
  return t(`dataOps.observations.types.${key}`)
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
