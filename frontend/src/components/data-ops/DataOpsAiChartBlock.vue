<template>
  <section class="mt-3 rounded-lg border border-slate-200 bg-white p-3">
    <div class="mb-3 flex items-center justify-between gap-3">
      <p class="text-xs font-bold text-slate-800">
        {{ chartTitle }}
      </p>
      <span class="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
        {{ chartTypeLabel }}
      </span>
    </div>

    <div class="space-y-2">
      <div
        v-for="row in rows"
        :key="row.key"
        class="grid grid-cols-[88px_minmax(0,1fr)] items-center gap-2"
      >
        <span class="truncate text-[11px] text-slate-500">
          {{ row.label }}
        </span>
        <div class="space-y-1">
          <div
            v-for="item in row.items"
            :key="`${row.key}-${item.name}`"
            class="flex items-center gap-2"
          >
            <div
              class="h-2 min-w-0 flex-1 rounded-full"
              :style="{ backgroundColor: towerChartTrackColor }"
            >
              <div
                class="h-2 rounded-full"
                :style="{
                  backgroundColor: item.color,
                  width: `${item.width}%`,
                }"
              />
            </div>
            <span class="w-16 text-right text-[11px] text-slate-600">
              {{ item.value }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  chart: { type: Object, required: true },
})

const { locale, t } = useI18n()

const towerChartPalette = [
  '#8a4cfc',
  '#2563eb',
  '#f59e0b',
  '#60a5fa',
  '#10b981',
]
const towerChartTrackColor = '#f1f5f9'

const chartTitle = computed(
  () => props.chart.title || t('dataOps.chart.dataChart')
)
const chartTypeLabel = computed(() =>
  props.chart.type === 'line'
    ? t('dataOps.chart.trend')
    : t('dataOps.chart.chart')
)

const series = computed(() => {
  if (Array.isArray(props.chart.series) && props.chart.series.length) {
    return props.chart.series
  }
  return [
    {
      name: props.chart.name || t('dataOps.chart.metric'),
      data: props.chart.data || props.chart.values || [],
    },
  ]
})

const labels = computed(() => {
  if (Array.isArray(props.chart.labels)) return props.chart.labels
  const firstSeries = series.value[0] || {}
  return (firstSeries.data || []).map((_, index) => `#${index + 1}`)
})

const maxValue = computed(() => {
  const values = series.value.flatMap((item) =>
    (item.data || []).map((value) => Math.abs(Number(value || 0)))
  )
  return Math.max(...values, 1)
})

const rows = computed(() =>
  labels.value.map((label, index) => ({
    key: `${label}-${index}`,
    label,
    items: series.value.map((item, seriesIndex) => {
      const value = Number((item.data || [])[index] || 0)
      return {
        color: towerChartPalette[seriesIndex % towerChartPalette.length],
        name: item.name || t('dataOps.chart.metric'),
        value: formatChartValue(value),
        width: chartBarWidth(value),
      }
    }),
  }))
)

function chartBarWidth(value) {
  const percentage = (Math.abs(value) / maxValue.value) * 100
  return Math.max(3, Math.min(100, percentage))
}

function formatChartValue(value) {
  return new Intl.NumberFormat(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
