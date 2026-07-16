<template>
  <section
    class="mt-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
  >
    <div class="mb-3 flex items-center justify-between gap-3">
      <div class="min-w-0">
        <p class="truncate text-sm font-semibold text-slate-800">
          {{ chartTitle }}
        </p>
        <p v-if="chart.unit" class="mt-0.5 truncate text-[11px] text-slate-400">
          {{ chart.unit }}
        </p>
      </div>
      <span
        class="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600"
      >
        <span
          aria-hidden="true"
          :class="['h-1.5 w-1.5 rounded-full', chartTypeToneClass]"
        />
        {{ chartTypeLabel }}
      </span>
    </div>

    <div
      class="h-64 rounded-md bg-slate-50/70 px-1 py-2 ring-1 ring-inset ring-slate-100 sm:h-72 sm:px-2"
      role="img"
      :aria-label="chartAriaLabel"
    >
      <Chart :data="chartData" :options="chartOptions" :type="chartType" />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart } from 'vue-chartjs'
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
} from 'chart.js'

import { buildDataOpsChartDatasets } from '@/utils/dataOpsChart'

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
)

const props = defineProps({
  chart: { type: Object, required: true }
})

const { locale, t } = useI18n()

const chartType = computed(() => props.chart.type || 'bar')
const isPartToWhole = computed(() =>
  ['pie', 'doughnut'].includes(chartType.value)
)
const chartTitle = computed(
  () => props.chart.title || t('dataOps.chart.dataChart')
)
const chartTypeLabel = computed(() =>
  t(`dataOps.chart.types.${chartType.value}`)
)
const chartTypeToneClass = computed(
  () =>
    ({
      bar: 'bg-agione-600',
      doughnut: 'bg-emerald-600',
      line: 'bg-sky-600',
      pie: 'bg-amber-600'
    })[chartType.value] || 'bg-slate-500'
)
const chartAriaLabel = computed(() => {
  const firstSeries = props.chart.series[0]
  const summary = props.chart.labels
    .slice(0, 8)
    .map((label, index) => {
      const value = firstSeries.data[index]
      return `${label}: ${formatChartValue(value)}`
    })
    .join(', ')
  return `${chartTitle.value}. ${summary}`
})

const chartData = computed(() => {
  return {
    labels: props.chart.labels,
    datasets: buildDataOpsChartDatasets(props.chart)
  }
})

const chartOptions = computed(() => {
  const options = {
    animation: { duration: 320, easing: 'easeOutQuart' },
    interaction: {
      intersect: false,
      mode: chartType.value === 'line' ? 'index' : 'nearest'
    },
    layout: {
      padding: isPartToWhole.value
        ? { bottom: 2, left: 8, right: 8, top: 8 }
        : { bottom: 2, left: 4, right: 8, top: 6 }
    },
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: {
        display: isPartToWhole.value || props.chart.series.length > 1,
        labels: {
          boxHeight: 8,
          boxWidth: 8,
          color: '#475569',
          font: { size: 11, weight: '500' },
          padding: 16,
          usePointStyle: true
        },
        position: 'bottom'
      },
      tooltip: {
        backgroundColor: '#0f172a',
        bodyColor: '#e2e8f0',
        bodySpacing: 6,
        borderColor: '#334155',
        borderWidth: 1,
        boxPadding: 4,
        caretPadding: 8,
        cornerRadius: 8,
        padding: 10,
        titleColor: '#f8fafc',
        titleMarginBottom: 8,
        callbacks: {
          label(context) {
            return tooltipLabel(context)
          }
        }
      }
    }
  }
  if (!isPartToWhole.value) {
    options.scales = {
      x: {
        border: { display: false },
        grid: { display: false },
        ticks: {
          autoSkip: props.chart.labels.length > 8,
          color: '#64748b',
          font: { size: 11 },
          maxRotation: props.chart.labels.length > 8 ? 32 : 0,
          minRotation: 0,
          padding: 8
        }
      },
      y: {
        beginAtZero: true,
        border: { display: false },
        grid: {
          color: 'rgba(148, 163, 184, 0.18)',
          drawTicks: false
        },
        ticks: {
          callback: (value) => formatAxisValue(value),
          color: '#64748b',
          font: { size: 11 },
          padding: 10
        }
      }
    }
  }
  if (chartType.value === 'bar') {
    options.datasets = {
      bar: {
        barPercentage: 0.82,
        categoryPercentage: 0.72
      }
    }
  }
  if (isPartToWhole.value) {
    options.cutout = chartType.value === 'doughnut' ? '58%' : 0
    options.radius = '92%'
  }
  return options
})

function tooltipLabel(context) {
  const value = formatChartValue(context.raw)
  if (isPartToWhole.value) {
    const values = context.dataset.data || []
    const total = values.reduce((sum, item) => sum + Number(item || 0), 0)
    const percentage = total
      ? `${((Number(context.raw || 0) / total) * 100).toFixed(1)}%`
      : '0%'
    return `${context.label || context.dataset.label}: ${value} (${percentage})`
  }
  const name = context.dataset.label ? `${context.dataset.label}: ` : ''
  return `${name}${value}`
}

function formatChartValue(value) {
  const formatted = new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 2
  }).format(Number(value || 0))
  return props.chart.unit ? `${formatted} ${props.chart.unit}` : formatted
}

function formatAxisValue(value) {
  return new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 1,
    notation: 'compact'
  }).format(Number(value || 0))
}
</script>
