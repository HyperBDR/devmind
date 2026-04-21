<template>
  <div class="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
    <h3 class="text-sm font-semibold text-gray-900 mb-4">
      {{ chartTitle }}
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
import {
  format,
  eachDayOfInterval,
  eachMonthOfInterval,
  startOfMonth,
  endOfMonth,
  startOfYear,
  endOfYear
} from 'date-fns'
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
  statistics: {
    type: Object,
    default: null
  },
  dailyData: {
    type: Array,
    default: () => []
  },
  periodType: {
    type: String,
    default: 'month',
    validator: (value) => ['month', 'year'].includes(value)
  },
  selectedPeriod: {
    type: String,
    default: ''
  },
  selectedYear: {
    type: Number,
    default: null
  },
  providers: {
    type: Array,
    default: () => []
  }
})

const { t, locale } = useI18n()

const dateFnsLocale = computed(() => {
  return locale.value === 'zh-CN' ? zhCN : enUS
})

const chartTitle = computed(() => {
  if (props.periodType === 'month') {
    return t('cloudBilling.billing.dailyCostChart')
  } else {
    return t('cloudBilling.billing.monthlyCostChart')
  }
})

const chartData = computed(() => {
  if (!props.statistics) return null

  const { cost_by_period, by_provider } = props.statistics

  if (!cost_by_period || Object.keys(cost_by_period).length === 0) {
    return null
  }

  // Generate all labels (days or months) for the period
  let labels = []
  let dateRange = null

  if (props.periodType === 'month' && props.selectedPeriod) {
    // Generate all days of the month (including future dates)
    try {
      const [year, month] = props.selectedPeriod.split('-')
      const start = startOfMonth(
        new Date(parseInt(year), parseInt(month) - 1, 1)
      )
      const end = endOfMonth(start)
      dateRange = { start, end }
      labels = eachDayOfInterval({ start, end }).map((date) => {
        if (locale.value === 'zh-CN') {
          return format(date, 'M月d日', { locale: dateFnsLocale.value })
        } else {
          return format(date, 'MMM d', { locale: dateFnsLocale.value })
        }
      })
    } catch (error) {
      console.error('Error parsing selected period:', error)
      return null
    }
  } else if (props.periodType === 'year' && props.selectedYear) {
    // Generate all 12 months of the year (always show all months)
    try {
      const start = startOfYear(new Date(props.selectedYear, 0, 1))
      const end = endOfYear(start)
      dateRange = { start, end }

      // Always show all 12 months
      const allMonths = eachMonthOfInterval({ start, end })
      labels = allMonths.map((date) => {
        if (locale.value === 'zh-CN') {
          return format(date, 'M月', { locale: dateFnsLocale.value })
        } else {
          return format(date, 'MMM', { locale: dateFnsLocale.value })
        }
      })
    } catch (error) {
      console.error('Error parsing selected year:', error)
      return null
    }
  } else {
    return null
  }

  // Prepare datasets
  const datasets = []
  // Modern, professional color palette (shared with BillingDailyCostChart)
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

  // Add provider+account datasets
  // Sort providers to ensure consistent color assignment across charts
  if (by_provider && Object.keys(by_provider).length > 0) {
    const providerList = Object.entries(by_provider)
      .map(([key, data]) => ({
        key,
        providerData: data,
        providerId: data.provider_id,
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
        // Sort by provider name first, then by account_id (same as BillingDailyCostChart)
        const nameCompare = a.name.localeCompare(b.name)
        if (nameCompare !== 0) return nameCompare
        return (a.accountId || '').localeCompare(b.accountId || '')
      })

    providerList.forEach((item, index) => {
      const color = colors[index % colors.length]
      const data = generateProviderData(item.providerData, labels, dateRange)

      // Build label with provider name and account_id if available
      let label = item.name
      if (item.providerData.account_id) {
        label = `${label} ${item.providerData.account_id}`
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
          return value.raw !== null && value.raw !== undefined ? 4 : 0
        },
        pointHoverRadius: 6,
        pointBackgroundColor: color.border,
        pointBorderColor: '#fff',
        pointBorderWidth: 2
      })
    })
  }

  // Add total cost dataset (as bar chart)
  const totalData = generateTotalData(cost_by_period, labels, dateRange)
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
})

function generateProviderData(providerData, labels, dateRange) {
  const data = new Array(labels.length).fill(null)
  const providerId = String(providerData.provider_id)
  const accountId = String(providerData.account_id || '')

  if (
    props.periodType === 'month' &&
    props.dailyData &&
    props.dailyData.length > 0
  ) {
    // Use daily data if available - show cumulative total cost
    const dailyMap = aggregateDailyDataByProvider(
      props.dailyData,
      providerId,
      accountId
    )
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    labels.forEach((label, index) => {
      const date = getDateForLabel(index, dateRange)
      if (date) {
        const dateKey = format(date, 'yyyy-MM-dd')
        const dateOnly = new Date(date)
        dateOnly.setHours(0, 0, 0, 0)

        // If date is in the future, keep data as null
        if (dateOnly > today) {
          data[index] = null
          return
        }

        const dayTotal = dailyMap[dateKey]
        if (dayTotal !== undefined && dayTotal !== null) {
          // Use the cumulative total_cost for that day
          data[index] = dayTotal
        } else {
          // If no data for this day (past date), keep as null
          data[index] = null
        }
      }
    })
  } else if (props.periodType === 'year') {
    // For year view, map monthly data from statistics
    // Always iterate through all 12 months
    const allMonths = eachMonthOfInterval(dateRange)
    const now = new Date()
    const currentMonth = new Date(now.getFullYear(), now.getMonth(), 1)

    // Get monthly breakdown from statistics if available
    // Otherwise, we need to calculate from cost_by_period
    let cumulativeCost = 0
    allMonths.forEach((monthDate, index) => {
      const periodKey = format(monthDate, 'yyyy-MM')

      // Check if this month is in the future (for current year)
      if (
        props.selectedYear === now.getFullYear() &&
        monthDate > currentMonth
      ) {
        data[index] = null
        return
      }

      // Try to get monthly cost from statistics
      // cost_by_period should have monthly keys like "2025-01" when not grouped by year
      if (props.statistics && props.statistics.cost_by_period) {
        const monthCost = props.statistics.cost_by_period[periodKey]
        if (monthCost !== undefined && monthCost !== null) {
          // For provider-specific monthly cost, we need to estimate from total monthly cost
          // Calculate provider's share based on total cost across all periods
          const totalMonthCost = parseFloat(monthCost) || 0
          const providerTotal = parseFloat(providerData.total_cost) || 0

          // Calculate total cost across all months for all providers
          const allProvidersTotal = Object.values(
            props.statistics.by_provider || {}
          ).reduce((sum, p) => {
            return sum + (parseFloat(p.total_cost) || 0)
          }, 0)

          if (allProvidersTotal > 0 && providerTotal > 0) {
            // Estimate provider's monthly cost based on its share of total cost
            const providerShare = providerTotal / allProvidersTotal
            const providerMonthCost = totalMonthCost * providerShare
            cumulativeCost += providerMonthCost
            data[index] = cumulativeCost
          } else {
            data[index] = null
          }
        } else {
          // No data for this month, keep as null
          data[index] = null
        }
      } else {
        // Fallback: no data available
        data[index] = null
      }
    })
  } else {
    // Fallback: show total at the end
    const totalCost = providerData.total_cost || 0
    if (totalCost > 0 && data.length > 0) {
      data[data.length - 1] = totalCost
    }
  }

  return data
}

function getDateForLabel(index, dateRange) {
  if (!dateRange) return null
  if (props.periodType === 'month') {
    const days = eachDayOfInterval(dateRange)
    return days[index] || null
  } else {
    // For year view, filter months based on current date
    const now = new Date()
    const currentMonth = new Date(now.getFullYear(), now.getMonth(), 1)
    const allMonths = eachMonthOfInterval(dateRange)
    const monthsToShow = allMonths.filter((monthDate) => {
      if (props.selectedYear === now.getFullYear()) {
        return monthDate <= currentMonth
      } else {
        return true
      }
    })
    return monthsToShow[index] || null
  }
}

function aggregateDailyDataByProvider(dailyData, providerId, accountId) {
  // Group by date and find the latest hour's total_cost for each day
  // total_cost is cumulative, so we use the last hour of each day
  // Match by both provider_id and account_id
  const dailyMap = {}
  const dailyLatestHour = {}
  dailyData.forEach((billing) => {
    const billingProviderId = String(billing.provider || billing.provider_id)
    const billingAccountId = String(billing.account_id || '')
    const targetAccountId = accountId || ''

    // Match provider and account_id (convert both to string for comparison)
    if (
      billingProviderId === providerId &&
      billingAccountId === targetAccountId
    ) {
      const date = new Date(billing.collected_at)
      const dateKey = format(date, 'yyyy-MM-dd')
      const hour = billing.hour || 0

      // Keep track of the latest hour for each day
      if (!dailyLatestHour[dateKey] || hour > dailyLatestHour[dateKey].hour) {
        dailyLatestHour[dateKey] = {
          hour: hour,
          total_cost: parseFloat(billing.total_cost || 0)
        }
      } else if (hour === dailyLatestHour[dateKey].hour) {
        // If same hour, use the latest collected_at
        const currentTime = new Date(billing.collected_at).getTime()
        const existingTime = new Date(
          dailyLatestHour[dateKey].collected_at || 0
        ).getTime()
        if (currentTime > existingTime) {
          dailyLatestHour[dateKey] = {
            hour: hour,
            total_cost: parseFloat(billing.total_cost || 0),
            collected_at: billing.collected_at
          }
        }
      }
    }
  })

  // Convert to cumulative map
  Object.keys(dailyLatestHour).forEach((dateKey) => {
    dailyMap[dateKey] = dailyLatestHour[dateKey].total_cost
  })

  return dailyMap
}

function generateTotalData(cost_by_period, labels, dateRange) {
  const data = new Array(labels.length).fill(null)

  if (
    props.periodType === 'month' &&
    props.dailyData &&
    props.dailyData.length > 0
  ) {
    // Use daily data if available - show cumulative total cost
    const dailyMap = aggregateDailyDataTotal(props.dailyData)
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    labels.forEach((label, index) => {
      const date = getDateForLabel(index, dateRange)
      if (date) {
        const dateKey = format(date, 'yyyy-MM-dd')
        const dateOnly = new Date(date)
        dateOnly.setHours(0, 0, 0, 0)

        // If date is in the future, keep data as null
        if (dateOnly > today) {
          data[index] = null
          return
        }

        // Use the cumulative total_cost for that day
        const dayTotal = dailyMap[dateKey]
        if (dayTotal !== undefined && dayTotal !== null) {
          // For cumulative display, use the day's total (which is already cumulative)
          data[index] = dayTotal
        } else {
          // If no data for this day (past date), keep as null
          data[index] = null
        }
      }
    })
  } else if (props.periodType === 'month' && dateRange) {
    // Fallback: show total at the last day of the month
    const periodKey = props.selectedPeriod
    const totalCost = cost_by_period[periodKey] || 0
    if (totalCost > 0 && data.length > 0) {
      data[data.length - 1] = totalCost
    }
  } else if (props.periodType === 'year' && dateRange) {
    // For yearly view, map monthly costs (cumulative)
    // Always iterate through all 12 months
    const allMonths = eachMonthOfInterval(dateRange)
    const now = new Date()
    const currentMonth = new Date(now.getFullYear(), now.getMonth(), 1)

    let cumulativeTotal = 0
    allMonths.forEach((monthDate, index) => {
      const periodKey = format(monthDate, 'yyyy-MM')

      // Check if this month is in the future (for current year)
      if (
        props.selectedYear === now.getFullYear() &&
        monthDate > currentMonth
      ) {
        data[index] = null
        return
      }

      const cost = cost_by_period[periodKey]
      if (cost !== undefined && cost !== null) {
        cumulativeTotal += cost
        data[index] = cumulativeTotal
      } else {
        // No data for this month, keep as null (don't carry forward)
        data[index] = null
      }
    })
  }

  return data
}

function aggregateDailyDataTotal(dailyData) {
  // Group by date and find the latest hour's total_cost for each day
  // total_cost is cumulative, so we use the last hour of each day
  // Then sum across all provider+account combinations for each day
  const dailyProviderMap = {}

  dailyData.forEach((billing) => {
    const date = new Date(billing.collected_at)
    const dateKey = format(date, 'yyyy-MM-dd')
    const hour = billing.hour || 0
    // Use provider_id + account_id as key to distinguish different accounts
    const providerKey = `${String(billing.provider || billing.provider_id)}_${String(billing.account_id || '')}`

    if (!dailyProviderMap[dateKey]) {
      dailyProviderMap[dateKey] = {}
    }

    if (!dailyProviderMap[dateKey][providerKey]) {
      dailyProviderMap[dateKey][providerKey] = {
        hour: -1,
        total_cost: 0
      }
    }

    // Keep the latest hour's data for each provider+account on each day
    if (hour > dailyProviderMap[dateKey][providerKey].hour) {
      dailyProviderMap[dateKey][providerKey] = {
        hour: hour,
        total_cost: parseFloat(billing.total_cost || 0),
        collected_at: billing.collected_at
      }
    } else if (hour === dailyProviderMap[dateKey][providerKey].hour) {
      // If same hour, use the latest collected_at
      const currentTime = new Date(billing.collected_at).getTime()
      const existingTime = new Date(
        dailyProviderMap[dateKey][providerKey].collected_at || 0
      ).getTime()
      if (currentTime > existingTime) {
        dailyProviderMap[dateKey][providerKey] = {
          hour: hour,
          total_cost: parseFloat(billing.total_cost || 0),
          collected_at: billing.collected_at
        }
      }
    }
  })

  // Sum all provider+account combinations' costs for each day
  const dailyMap = {}
  Object.keys(dailyProviderMap).forEach((dateKey) => {
    let totalCost = 0
    Object.values(dailyProviderMap[dateKey]).forEach((providerData) => {
      totalCost += providerData.total_cost || 0
    })
    dailyMap[dateKey] = totalCost
  })

  return dailyMap
}

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
          },
          boxWidth: 12,
          boxHeight: 12
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
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  }
})
</script>
