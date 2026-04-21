<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm p-4 h-full flex flex-col"
  >
    <h3 class="text-sm font-semibold text-gray-900 mb-3">
      {{ t('cloudBilling.billing.providerCostDistribution') }}
    </h3>
    <div
      v-if="!chartData || chartData.labels.length === 0"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm font-medium text-gray-600">
        {{ t('cloudBilling.billing.noData') }}
      </p>
    </div>
    <div
      v-else
      class="relative flex-1 flex items-center justify-center"
      style="min-height: 200px"
    >
      <Pie :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { formatCost } from '@/utils/formatting'
import {
  appendProviderNotesLabel,
  getLocalizedProviderDisplayName
} from '@/utils/providerDisplay'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps({
  statistics: {
    type: Object,
    default: null
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  }
})

const { t } = useI18n()

const buildProviderLabel = (providerData, fallbackKey) => {
  return appendProviderNotesLabel(
    getLocalizedProviderDisplayName(
      {
        provider_type: providerData?.provider_type,
        display_name: providerData?.provider_name || fallbackKey || ''
      },
      t
    ),
    providerData?.provider_notes
  )
}

const chartCurrency = computed(() => {
  if (!props.statistics?.by_provider) {
    return 'CNY'
  }
  const currencies = new Set(
    Object.values(props.statistics.by_provider)
      .map((providerData) => String(providerData.currency || '').toUpperCase())
      .filter(Boolean)
  )
  if (currencies.size === 1) {
    return Array.from(currencies)[0]
  }
  return 'CNY'
})

const convertValueToChartCurrency = (value, currency) => {
  const numericValue = Number(value || 0)
  const sourceCurrency = String(currency || '').toUpperCase() || 'CNY'
  const targetCurrency = chartCurrency.value
  const rate = Number(props.exchangeRate || 7.15)

  if (sourceCurrency === targetCurrency) {
    return numericValue
  }
  if (sourceCurrency === 'USD' && targetCurrency === 'CNY') {
    return numericValue * rate
  }
  if (sourceCurrency === 'CNY' && targetCurrency === 'USD') {
    return numericValue / rate
  }
  return numericValue
}

const chartData = computed(() => {
  if (!props.statistics || !props.statistics.by_provider) {
    return null
  }

  const byProvider = props.statistics.by_provider
  const providerEntries = Object.entries(byProvider)

  if (providerEntries.length === 0) {
    return null
  }

  // Modern, professional color palette for pie chart
  const colors = [
    '#6366f1', // Indigo
    '#8b5cf6', // Purple
    '#ec4899', // Pink
    '#f59e0b', // Amber
    '#10b981', // Emerald
    '#06b6d4', // Cyan
    '#3b82f6', // Blue
    '#84cc16', // Lime
    '#f97316', // Orange
    '#14b8a6' // Teal
  ]

  const labels = []
  const data = []
  const backgroundColor = []
  const borderColor = []

  providerEntries.forEach(([key, providerData], index) => {
    labels.push(buildProviderLabel(providerData, key))
    data.push(
      convertValueToChartCurrency(
        parseFloat(providerData.total_cost || 0),
        providerData.currency
      )
    )
    backgroundColor.push(colors[index % colors.length])
    borderColor.push('#ffffff')
  })

  return {
    labels,
    datasets: [
      {
        data,
        backgroundColor,
        borderColor,
        borderWidth: 2
      }
    ]
  }
})

const chartOptions = computed(() => {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right',
        labels: {
          usePointStyle: true,
          padding: 10,
          font: {
            size: 11
          },
          boxWidth: 12,
          boxHeight: 12,
          generateLabels: function (chart) {
            const data = chart.data
            if (data.labels.length && data.datasets.length) {
              const dataset = data.datasets[0]
              const total = dataset.data.reduce((a, b) => a + b, 0)

              return data.labels.map((label, i) => {
                const value = dataset.data[i]
                const percentage =
                  total > 0 ? ((value / total) * 100).toFixed(1) : 0

                return {
                  text: `${label} (${percentage}%)`,
                  fillStyle: dataset.backgroundColor[i],
                  strokeStyle: dataset.borderColor[i],
                  lineWidth: dataset.borderWidth,
                  hidden: false,
                  index: i
                }
              })
            }
            return []
          }
        }
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            const label = context.label || ''
            const value = context.parsed || 0
            const total = context.dataset.data.reduce((a, b) => a + b, 0)
            const percentage =
              total > 0 ? ((value / total) * 100).toFixed(2) : 0

            return `${label}: ${formatCost(value, chartCurrency.value)} (${percentage}%)`
          }
        }
      }
    }
  }
})
</script>
