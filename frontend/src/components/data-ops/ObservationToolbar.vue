<template>
  <div class="space-y-4">
    <div
      class="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 xl:flex-row xl:items-end xl:justify-between"
    >
      <div>
        <h2
          id="observation-explorer-title"
          class="text-sm font-bold text-slate-950"
        >
          {{ t('dataOps.observations.title') }}
        </h2>
        <p class="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
          {{ t('dataOps.observations.description') }}
        </p>
      </div>
      <div v-if="canRun" class="flex flex-wrap items-end gap-2">
        <label class="space-y-1 text-xs font-semibold text-slate-600">
          <span>{{ t('dataOps.observations.producer') }}</span>
          <select
            id="observation-producer"
            v-model="producerKey"
            class="field-sm block min-w-52"
            name="observation_producer"
          >
            <option
              v-for="option in producerOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <button
          class="btn-secondary"
          type="button"
          :disabled="runLoading"
          @click="$emit('run', producerKey)"
        >
          {{
            runLoading
              ? t('dataOps.observations.running')
              : t('dataOps.observations.runNow')
          }}
        </button>
      </div>
    </div>

    <p
      v-if="feedback"
      class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
      role="status"
    >
      {{ feedback }}
    </p>
    <p
      v-if="error"
      class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
      role="alert"
    >
      {{ error }}
    </p>

    <div
      class="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4"
    >
      <label class="space-y-1 text-xs font-semibold text-slate-600">
        <span>{{ t('dataOps.observations.type') }}</span>
        <select
          id="observation-type-filter"
          :value="filters.observation_type"
          class="field-sm block"
          name="observation_type"
          @change="updateFilter('observation_type', $event.target.value)"
        >
          <option value="">{{ t('dataOps.observations.allTypes') }}</option>
          <option value="contract_renewal_risk">
            {{ t('dataOps.observations.types.contractRenewal') }}
          </option>
          <option value="receivable_overdue_risk">
            {{ t('dataOps.observations.types.receivableOverdue') }}
          </option>
        </select>
      </label>
      <label class="space-y-1 text-xs font-semibold text-slate-600">
        <span>{{ t('dataOps.common.status') }}</span>
        <select
          id="observation-status-filter"
          :value="filters.status"
          class="field-sm block"
          name="observation_status"
          @change="updateFilter('status', $event.target.value)"
        >
          <option value="">{{ t('dataOps.observations.allStatuses') }}</option>
          <option v-for="value in statuses" :key="value" :value="value">
            {{ statusLabel(value) }}
          </option>
        </select>
      </label>
      <label class="space-y-1 text-xs font-semibold text-slate-600">
        <span>{{ t('dataOps.observations.severityLabel') }}</span>
        <select
          id="observation-severity-filter"
          :value="filters.severity"
          class="field-sm block"
          name="observation_severity"
          @change="updateFilter('severity', $event.target.value)"
        >
          <option value="">
            {{ t('dataOps.observations.allSeverities') }}
          </option>
          <option v-for="value in severities" :key="value" :value="value">
            {{ severityLabel(value) }}
          </option>
        </select>
      </label>
      <button class="btn-secondary" type="button" @click="$emit('load')">
        {{ t('dataOps.common.query') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps({
  canRun: { type: Boolean, default: false },
  error: { type: String, default: '' },
  feedback: { type: String, default: '' },
  filters: { type: Object, required: true },
  runLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['load', 'run', 'update-filter'])
const { t } = useI18n()
const producerKey = ref('contract-renewal-risk')
const severities = ['critical', 'high', 'medium', 'low']
const statuses = ['active', 'resolved', 'superseded', 'invalidated']
const producerOptions = computed(() => [
  {
    label: t('dataOps.observations.producers.contractRenewal'),
    value: 'contract-renewal-risk'
  },
  {
    label: t('dataOps.observations.producers.receivableOverdue'),
    value: 'receivable-overdue-risk'
  }
])

function updateFilter(key, value) {
  emit('update-filter', key, value)
}

function severityLabel(value) {
  return t(`dataOps.observations.severity.${value || 'low'}`)
}

function statusLabel(value) {
  return t(`dataOps.observations.status.${value || 'active'}`)
}
</script>
