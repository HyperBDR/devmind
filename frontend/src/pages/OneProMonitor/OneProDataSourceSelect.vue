<template>
  <label :class="wrapperClass">
    <span :class="labelClass">
      <span
        v-if="props.variant === 'prominent' || props.variant === 'toolbar'"
        class="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]"
      />
      {{ t('hyperbdrMonitor.labels.dataSource') }}
    </span>
    <select
      :value="selectedDataSource"
      :class="selectClass"
      @change="handleChange"
    >
      <option value="">{{ t('hyperbdrMonitor.labels.allDataSources') }}</option>
      <option
        v-for="source in dataSources"
        :key="source.id"
        :value="String(source.id)"
      >
        {{ source.name }}
      </option>
    </select>
  </label>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const props = defineProps({
  layout: {
    type: String,
    default: 'stacked'
  },
  variant: {
    type: String,
    default: 'default'
  }
})

const { t } = useI18n()
const {
  dataSources,
  selectedDataSource,
  setSelectedDataSource,
  loadDataSources
} = useOneProDataSourceScope()

const wrapperClass = computed(() =>
  props.layout === 'inline'
    ? [
        'flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-end sm:gap-3',
        props.variant === 'prominent'
          ? 'rounded-2xl border border-gray-200 bg-white/95 px-3 py-2 shadow-[0_16px_40px_-24px_rgba(15,23,42,0.45)] backdrop-blur'
          : props.variant === 'toolbar'
            ? 'rounded-2xl border border-white/60 bg-white/80 px-3 py-2 shadow-[0_18px_48px_-30px_rgba(15,23,42,0.35)] backdrop-blur'
            : ''
      ]
        .filter(Boolean)
        .join(' ')
    : 'flex min-w-[220px] flex-col gap-2'
)

const labelClass = computed(() =>
  props.layout === 'inline'
    ? [
        'text-xs font-medium uppercase tracking-[0.18em] sm:whitespace-nowrap',
        props.variant === 'prominent' || props.variant === 'toolbar'
          ? 'inline-flex items-center gap-2 px-1 text-emerald-700'
          : 'text-gray-500'
      ].join(' ')
    : 'text-xs font-medium uppercase tracking-[0.18em] text-gray-500'
)

const selectClass = computed(() =>
  props.layout === 'inline'
    ? [
        'w-full rounded-xl border bg-white text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100 sm:min-w-[240px] sm:w-auto',
        props.variant === 'prominent'
          ? 'border-gray-200 px-4 py-2.5 shadow-sm'
          : props.variant === 'toolbar'
            ? 'border-emerald-100 bg-emerald-50/70 px-4 py-2.5 shadow-inner'
            : 'border-gray-300 px-4 py-3'
      ].join(' ')
    : 'rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100'
)

function handleChange(event) {
  setSelectedDataSource(event.target.value)
}

onMounted(() => {
  loadDataSources()
})
</script>
