<template>
  <div class="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
    <h3 class="text-sm font-semibold text-gray-900 mb-4">
      {{ t('cloudBilling.billing.dailyCostBreakdown') }}
    </h3>
    <div
      v-if="!chartData || chartData.labels.length === 0"
      class="py-16 text-center"
    >
      <p class="text-sm font-medium text-gray-600">
        {{ t('cloudBilling.billing.noData') }}
      </p>
    </div>
    <div v-else class="relative" style="height: 400px">
      <Chart type="bar" :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { format, eachDayOfInterval, startOfMonth, endOfMonth } from 'date-fns'
import { zhCN, enUS } from 'date-fns/locale'
import {
  appendProviderNotesLabel,
  getLocalizedProviderDisplayName
} from '@/utils/providerDisplay'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  dailyData: {
    type: Array,
    default: () => []
  },
  statistics: {
    type: Object,
    default: null
  },
  selectedPeriod: {
    type: String,
    default: ''
  }
})

const { t, locale } = useI18n()

const dateFnsLocale = computed(() => {
  return locale.value === 'zh-CN' ? zhCN : enUS
})

const chartData = computed(() => {
  if (!props.selectedPeriod) {
    return null
  }

  if (!props.statistics || !props.statistics.by_provider) {
    return null
  }

  // Allow chart to render even if dailyData is empty (will show empty chart)
  if (!props.dailyData || props.dailyData.length === 0) {
    // Return empty chart structure
    try {
      const [year, month] = props.selectedPeriod.split('-')
      const start = startOfMonth(
        new Date(parseInt(year), parseInt(month) - 1, 1)
      )
      const end = endOfMonth(start)
      const today = new Date()
      today.setHours(0, 0, 0, 0)

      const days = eachDayOfInterval({ start, end })
      const labels = days.map((day) => {
        if (locale.value === 'zh-CN') {
          return format(day, 'M月d日', { locale: dateFnsLocale.value })
        } else {
          return format(day, 'MMM d', { locale: dateFnsLocale.value })
        }
      })

      // Get provider list from statistics
      const providerList = Object.entries(props.statistics.by_provider)
        .map(([key, data]) => ({
          id: data.provider_id,
          accountId: data.account_id || '',
          name: appendProviderNotesLabel(
            getLocalizedProviderDisplayName(
              {
                provider_type: data.provider_type,
                display_name: data.provider_name || key
              },
              t
            ),
            data.provider_notes
          )
        }))
        .sort((a, b) => {
          const nameCompare = a.name.localeCompare(b.name)
          if (nameCompare !== 0) return nameCompare
          return (a.accountId || '').localeCompare(b.accountId || '')
        })

      const colors = [
        { border: '#6366f1', background: 'rgba(99, 102, 241, 0.1)' },
        { border: '#8b5cf6', background: 'rgba(139, 92, 246, 0.1)' },
        { border: '#ec4899', background: 'rgba(236, 72, 153, 0.1)' },
        { border: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)' },
        { border: '#10b981', background: 'rgba(16, 185, 129, 0.1)' },
        { border: '#06b6d4', background: 'rgba(6, 182, 212, 0.1)' },
        { border: '#3b82f6', background: 'rgba(59, 130, 246, 0.1)' },
        { border: '#84cc16', background: 'rgba(132, 204, 22, 0.1)' },
        { border: '#f97316', background: 'rgba(249, 115, 22, 0.1)' },
        { border: '#14b8a6', background: 'rgba(20, 184, 166, 0.1)' }
      ]

      const datasets = []
      providerList.forEach((provider, index) => {
        const color = colors[index % colors.length]
        const data = new Array(labels.length).fill(null)

        let label = provider.name
        if (provider.accountId) {
          label = `${label} ${provider.accountId}`
        }

        datasets.push({
          type: 'line',
          label: label,
          data: data,
          borderColor: color.border,
          backgroundColor: color.background,
          fill: false,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointBackgroundColor: color.border,
          pointBorderColor: '#fff',
          pointBorderWidth: 2
        })
      })

      // Add total cost dataset
      const totalData = new Array(labels.length).fill(null)
      datasets.push({
        type: 'bar',
        label: t('cloudBilling.billing.totalCost'),
        data: totalData,
        backgroundColor: 'rgba(99, 102, 241, 0.8)',
        borderColor: '#6366f1',
        borderWidth: 2,
        borderRadius: 6,
        borderSkipped: false
      })

      return {
        labels,
        datasets
      }
    } catch (error) {
      console.error('Error generating empty daily cost chart:', error)
      return null
    }
  }

  try {
    const [year, month] = props.selectedPeriod.split('-')
    const start = startOfMonth(new Date(parseInt(year), parseInt(month) - 1, 1))
    const end = endOfMonth(start)
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    const days = eachDayOfInterval({ start, end })
    const labels = days.map((day) => {
      if (locale.value === 'zh-CN') {
        return format(day, 'M月d日', { locale: dateFnsLocale.value })
      } else {
        return format(day, 'MMM d', { locale: dateFnsLocale.value })
      }
    })

    // Get provider+account list from statistics
    const providerList = Object.entries(props.statistics.by_provider)
      .map(([key, data]) => ({
        id: data.provider_id,
        accountId: data.account_id || '',
        name: appendProviderNotesLabel(
          getLocalizedProviderDisplayName(
            {
              provider_type: data.provider_type,
              display_name: data.provider_name || key
            },
            t
          ),
          data.provider_notes
        )
      }))
      .sort((a, b) => {
        // Sort by provider name first, then by account_id
        const nameCompare = a.name.localeCompare(b.name)
        if (nameCompare !== 0) return nameCompare
        return (a.accountId || '').localeCompare(b.accountId || '')
      })

    // Group billing data by date and provider+account
    const dailyProviderMap = {}

    props.dailyData.forEach((billing) => {
      const date = new Date(billing.collected_at)
      const dateKey = format(date, 'yyyy-MM-dd')
      const providerId = billing.provider || billing.provider_id
      const accountId = billing.account_id || ''
      // Use provider_id + account_id as key to distinguish different accounts
      // Convert to string to ensure consistent key matching
      const providerAccountKey = `${String(providerId)}_${String(accountId)}`
      const hour = billing.hour || 0

      if (!dailyProviderMap[dateKey]) {
        dailyProviderMap[dateKey] = {}
      }

      if (!dailyProviderMap[dateKey][providerAccountKey]) {
        dailyProviderMap[dateKey][providerAccountKey] = {
          hour: -1,
          total_cost: 0
        }
      }

      // Keep the latest hour's data for each provider+account on each day
      if (hour > dailyProviderMap[dateKey][providerAccountKey].hour) {
        dailyProviderMap[dateKey][providerAccountKey] = {
          hour: hour,
          total_cost: parseFloat(billing.total_cost || 0),
          collected_at: billing.collected_at
        }
      } else if (hour === dailyProviderMap[dateKey][providerAccountKey].hour) {
        const currentTime = new Date(billing.collected_at).getTime()
        const existingTime = new Date(
          dailyProviderMap[dateKey][providerAccountKey].collected_at || 0
        ).getTime()
        if (currentTime > existingTime) {
          dailyProviderMap[dateKey][providerAccountKey] = {
            hour: hour,
            total_cost: parseFloat(billing.total_cost || 0),
            collected_at: billing.collected_at
          }
        }
      }
    })

    // Modern, professional color palette
    const colors = [
      { border: '#6366f1', background: 'rgba(99, 102, 241, 0.1)' }, // Indigo
      { border: '#8b5cf6', background: 'rgba(139, 92, 246, 0.1)' }, // Purple
      { border: '#ec4899', background: 'rgba(236, 72, 153, 0.1)' }, // Pink
      { border: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)' }, // Amber
      { border: '#10b981', background: 'rgba(16, 185, 129, 0.1)' }, // Emerald
      { border: '#06b6d4', background: 'rgba(6, 182, 212, 0.1)' }, // Cyan
      { border: '#3b82f6', background: 'rgba(59, 130, 246, 0.1)' }, // Blue
      { border: '#84cc16', background: 'rgba(132, 204, 22, 0.1)' }, // Lime
      { border: '#f97316', background: 'rgba(249, 115, 22, 0.1)' }, // Orange
      { border: '#14b8a6', background: 'rgba(20, 184, 166, 0.1)' } // Teal
    ]

    const datasets = []
    // Initialize prev day costs for each provider
    const providerPrevDayCosts = {}
    // Separate prev day costs for total calculation to avoid contamination
    const totalPrevDayCosts = {}
    providerList.forEach((provider) => {
      const providerAccountKey = `${String(provider.id)}_${provider.accountId}`
      providerPrevDayCosts[providerAccountKey] = 0
      totalPrevDayCosts[providerAccountKey] = 0
    })

    // Add provider+account datasets
    providerList.forEach((provider, index) => {
      const color = colors[index % colors.length]
      const data = []
      const providerAccountKey = `${String(provider.id)}_${provider.accountId}`

      days.forEach((day) => {
        const dateKey = format(day, 'yyyy-MM-dd')
        const dateOnly = new Date(day)
        dateOnly.setHours(0, 0, 0, 0)

        // If date is in the future, set data as null
        if (dateOnly > today) {
          data.push(null)
          return
        }

        const dayData = dailyProviderMap[dateKey]?.[providerAccountKey]

        if (dayData) {
          // Calculate daily cost: current day's total_cost - previous day's total_cost
          const prevCost = providerPrevDayCosts[providerAccountKey] || 0
          const dailyCost = dayData.total_cost - prevCost

          // Only show positive costs
          data.push(dailyCost >= 0 ? dailyCost : 0)

          // Update previous day's cost for next iteration
          providerPrevDayCosts[providerAccountKey] = dayData.total_cost
        } else {
          data.push(null)
        }
      })

      // Build label with provider name and account_id if available
      let label = provider.name
      if (provider.accountId) {
        label = `${label} ${provider.accountId}`
      }

      datasets.push({
        type: 'line',
        label: label,
        data: data,
        borderColor: color.border,
        backgroundColor: color.background,
        fill: false,
        tension: 0.4,
        pointRadius: (value) => {
          // Show points for actual data values, hide for null/undefined
          return value.raw !== null &&
            value.raw !== undefined &&
            value.raw !== 0
            ? 4
            : 0
        },
        pointHoverRadius: 6,
        pointBackgroundColor: color.border,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        spanGaps: false // Don't connect lines across null gaps
      })
    })

    // Add total cost dataset
    const totalData = []

    days.forEach((day) => {
      const dateKey = format(day, 'yyyy-MM-dd')
      const dateOnly = new Date(day)
      dateOnly.setHours(0, 0, 0, 0)

      // If date is in the future, set data as null
      if (dateOnly > today) {
        totalData.push(null)
        return
      }

      // Calculate total cost for the day (sum of all provider+account combinations' daily costs)
      let dayTotal = 0
      providerList.forEach((provider) => {
        const providerAccountKey = `${String(provider.id)}_${provider.accountId}`
        const dayData = dailyProviderMap[dateKey]?.[providerAccountKey]
        if (dayData) {
          const prevCost = totalPrevDayCosts[providerAccountKey] || 0
          const dailyCost = dayData.total_cost - prevCost
          if (dailyCost >= 0) {
            dayTotal += dailyCost
          }
          totalPrevDayCosts[providerAccountKey] = dayData.total_cost
        }
      })

      totalData.push(dayTotal)
    })

    datasets.push({
      type: 'bar',
      label: t('cloudBilling.billing.totalCost'),
      data: totalData,
      backgroundColor: 'rgba(99, 102, 241, 0.8)',
      borderColor: '#6366f1',
      borderWidth: 2,
      borderRadius: 6,
      borderSkipped: false
    })

    return {
      labels,
      datasets
    }
  } catch (error) {
    console.error('Error generating daily cost chart:', error)
    return null
  }
})

const chartOptions = computed(() => {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 15,
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function (context) {
            const value = context.parsed.y
            if (value === null || value === undefined) {
              return null
            }
            const label = context.dataset.label || ''
            return `${label}: ¥${Number(value).toFixed(2)}`
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          display: false
        },
        ticks: {
          maxRotation: 45,
          minRotation: 0,
          font: {
            size: 11
          }
        }
      },
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        },
        ticks: {
          callback: function (value) {
            return '¥' + Number(value).toFixed(0)
          },
          font: {
            size: 11
          }
        }
      }
    },
    interaction: {
      mode: 'index',
      intersect: false
    }
  }
})
</script>
