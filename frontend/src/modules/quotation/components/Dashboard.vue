<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Line, Pie } from 'vue-chartjs'
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
  type Plugin,
  type TooltipItem
} from 'chart.js'
import {
  getDashboardAnalytics,
  getDashboardRecent,
  getDashboardSummary,
  type DashboardAnalytics,
  type DashboardCurrency,
  type DashboardRecentQuotation,
  type DashboardSummary
} from '../api/dashboard'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import FormSelect from './FormSelect.vue'
import { ChevronRight, FileSpreadsheet } from 'lucide-vue-next'

ChartJS.register(
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
)

type TrendGrain = 'weekly' | 'monthly'

const QUOTE_BREAKDOWN_COLORS = [
  '#2b9da3',
  '#389e0d',
  '#67b7bc',
  '#58b42d',
  '#1f7f86',
  '#9bcf53',
  '#136b73',
  '#d6a21f'
]
const CURRENCY_ORDER = ['USD', 'CNY', 'EUR', 'GBP', 'MYR', 'HKD']

const emit = defineEmits<{
  viewQuote: [id: string]
  navigateToTab: [
    payload: {
      tab: string
      createdFrom?: string
      createdTo?: string
    },
  ]
}>()

const { t, locale } = useQuotationI18n()

const trendGrain = ref<TrendGrain>('monthly')
const dashboardCurrency = ref('USD')
const selectedPeriod = ref(
  `${new Date().getFullYear()}-${String(
    new Date().getMonth() + 1
  ).padStart(2, '0')}`
)
const summary = ref<DashboardSummary | null>(null)
const analytics = ref<DashboardAnalytics | null>(null)
const recentQuotes = ref<DashboardRecentQuotation[]>([])
const summaryLoading = ref(true)
const summaryError = ref(false)
const analyticsLoading = ref(true)
const analyticsError = ref(false)

function normalizeDashboardCurrency(currency: string): string {
  const code = String(currency || '').trim().toUpperCase()
  if (code === 'RMB' || code === '¥' || code === '￥') return 'CNY'
  if (code === 'EURO' || code === 'EUROS' || code === '€') return 'EUR'
  if (code === '£') return 'GBP'
  if (code === 'RM') return 'MYR'
  if (code === 'HK$') return 'HKD'
  return code
}

function currencyShortLabel(currency: DashboardCurrency): string {
  const code = normalizeDashboardCurrency(currency)
  if (code === 'MYR') return 'RM'
  return code
}

function currencyOptionLabel(currency: string): string {
  return currencyShortLabel(currency)
}

const monthQuoteDelta = computed(() => {
  if (summary.value == null) return null
  const monthQuoteCount = summary.value.monthQuoteCount || 0
  if (monthQuoteCount === 0) return null
  return monthQuoteCount - (summary.value.previousMonthQuoteCount || 0)
})
const monthQuoteDeltaLabel = computed(() => {
  if (monthQuoteDelta.value == null) return '—'
  const delta = monthQuoteDelta.value
  return delta > 0 ? `+${delta}` : String(delta)
})
const monthQuoteDeltaClass = computed(() => {
  const delta = monthQuoteDelta.value
  if (delta == null || summaryLoading.value) return 'text-dm-text'
  if (delta > 0) return 'text-emerald-700'
  if (delta < 0) return 'text-dm-text-secondary'
  return 'text-dm-text'
})
const availableCurrencyOptions = computed(() =>
  CURRENCY_ORDER.map((currency) => ({
    value: currency,
    label: currencyOptionLabel(currency)
  }))
)
const availablePeriodOptions = computed(() => {
  const periods = summary.value?.availablePeriods || []
  const normalized = [...new Set([...periods, selectedPeriod.value])]
    .filter(Boolean)
    .sort((left, right) => right.localeCompare(left))
  return normalized.map((period) => ({
    value: period,
    label: formatSummaryPeriod(period)
  }))
})
const overviewRecentQuotes = computed(() => recentQuotes.value.slice(0, 3))

function formatSummaryPeriod(value: string): string {
  const [year = '', month = ''] = String(value || '').split('-')
  if (!year || !month) return value
  if (String(locale.value || '').startsWith('zh')) {
    return t('quotation.pages.dashboard.overviewPeriod', {
      year: Number(year),
      month: Number(month)
    })
  }
  return new Date(`${value}-01T00:00:00`).toLocaleString('en', {
    month: 'short',
    year: 'numeric'
  })
}

const selectedDashboardCurrency = computed(() =>
  normalizeDashboardCurrency(dashboardCurrency.value)
)

const quoteBreakdownData = computed(() =>
  (analytics.value?.amountBreakdown || [])
    .filter((quote) =>
      normalizeDashboardCurrency(
        quote.currency || analytics.value?.currency || ''
      ) === selectedDashboardCurrency.value
    )
    .map((quote, index) => {
      const currency = selectedDashboardCurrency.value
      const amountLabel = `${currencyShortLabel(currency)} ${quote.amount.toLocaleString()}`
      return {
        key: quote.quotationId,
        quoteNo: quote.quoteNo,
        value: quote.amount,
        color: QUOTE_BREAKDOWN_COLORS[index % QUOTE_BREAKDOWN_COLORS.length],
        amountLabel,
        currency,
        share: 0,
        status: quote.status,
        label: `${quote.quoteNo} · ${amountLabel}`
      }
    })
)

const quoteBreakdownTotal = computed(() =>
  quoteBreakdownData.value.reduce((sum, row) => sum + row.value, 0)
)

const quoteBreakdownChartRows = computed(() => {
  const total = quoteBreakdownTotal.value || 1
  const rows = quoteBreakdownData.value.map((row) => ({
    ...row,
    share: (row.value / total) * 100
  }))
  return rows
})

const quoteBreakdownRotation = computed(() => {
  const total = quoteBreakdownChartRows.value.reduce(
    (sum, row) => sum + row.value,
    0
  )
  const largestShare = total
    ? quoteBreakdownChartRows.value[0]?.value / total
    : 0
  return 180 - largestShare * 180
})

type PieLeaderLabel = {
  index: number
  side: -1 | 1
  anchorX: number
  anchorY: number
  labelY: number
}

function arrangePieLineLabels(
  entries: PieLeaderLabel[],
  minY: number,
  maxY: number,
  gap: number
) {
  const sorted = [...entries].sort((a, b) => a.labelY - b.labelY)
  sorted.forEach((entry, index) => {
    const floor = index === 0 ? minY : sorted[index - 1].labelY + gap
    entry.labelY = Math.max(entry.labelY, floor)
  })
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const ceiling =
      index === sorted.length - 1 ? maxY : sorted[index + 1].labelY - gap
    sorted[index].labelY = Math.min(sorted[index].labelY, ceiling)
  }
  return sorted
}

const quotePieLeaderLabelPlugin: Plugin<'pie'> = {
  id: 'quotePieLeaderLabelPlugin',
  afterDatasetsDraw(chart) {
    const meta = chart.getDatasetMeta(0)
    if (!meta.data.length) return
    const entries: PieLeaderLabel[] = meta.data.map((element, index) => {
      const arc = element as ArcElement
      const angle = (arc.startAngle + arc.endAngle) / 2
      const side: -1 | 1 = Math.cos(angle) >= 0 ? 1 : -1
      return {
        index,
        side,
        anchorX: arc.x + Math.cos(angle) * arc.outerRadius,
        anchorY: arc.y + Math.sin(angle) * arc.outerRadius,
        labelY: arc.y + Math.sin(angle) * (arc.outerRadius + 10)
      }
    })
    const minY = chart.chartArea.top + 12
    const maxY = chart.chartArea.bottom - 12
    const arranged = [
      ...arrangePieLineLabels(
        entries.filter((entry) => entry.side === -1),
        minY,
        maxY,
        40
      ),
      ...arrangePieLineLabels(
        entries.filter((entry) => entry.side === 1),
        minY,
        maxY,
        40
      )
    ]
    const { ctx } = chart
    ctx.save()
    arranged.forEach((entry) => {
      const row = quoteBreakdownChartRows.value[entry.index]
      if (!row) return
      const bendX = entry.anchorX + entry.side * 22
      const lineEndX = bendX + entry.side * 44
      const textX = lineEndX + entry.side * 6
      const availableTextWidth =
        entry.side === 1 ? chart.width - textX - 6 : textX - 6
      const maxTextWidth = Math.max(64, availableTextWidth)
      ctx.strokeStyle = row.color
      ctx.lineWidth = 1.25
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.beginPath()
      ctx.moveTo(entry.anchorX, entry.anchorY)
      ctx.lineTo(bendX, entry.labelY)
      ctx.lineTo(lineEndX, entry.labelY)
      ctx.stroke()
      ctx.fillStyle = '#334155'
      ctx.font = '600 12px ui-monospace, SFMono-Regular, Menlo, monospace'
      ctx.textAlign = entry.side === 1 ? 'left' : 'right'
      ctx.textBaseline = 'bottom'
      ctx.fillText(row.quoteNo, textX, entry.labelY - 2, maxTextWidth)
      ctx.fillStyle = '#64748b'
      ctx.font = '11px ui-sans-serif, system-ui, sans-serif'
      ctx.textBaseline = 'top'
      ctx.fillText(row.amountLabel, textX, entry.labelY + 2, maxTextWidth)
    })
    ctx.restore()
  }
}

const quoteBreakdownPieData = computed<ChartData<'pie'>>(() => ({
  labels: quoteBreakdownChartRows.value.map((row) => row.label),
  datasets: [
    {
      data: quoteBreakdownChartRows.value.map((row) => row.value),
      backgroundColor: quoteBreakdownChartRows.value.map((row) => row.color),
      borderColor: '#ffffff',
      borderWidth: 2,
      radius: '92%',
      hoverOffset: 6,
      hoverBorderWidth: 2
    }
  ]
}))

const quoteBreakdownPieOptions = computed<ChartOptions<'pie'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  rotation: quoteBreakdownRotation.value,
  layout: {
    padding: { top: 20, right: 72, bottom: 20, left: 72 }
  },
  animation: {
    animateRotate: true,
    animateScale: true,
    duration: 450
  },
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      titleFont: { size: 11, weight: 'bold' },
      bodyFont: { size: 11 },
      padding: 10,
      displayColors: true,
      callbacks: {
        label: (item: TooltipItem<'pie'>) => {
          const value = Number(item.raw) || 0
          const row = quoteBreakdownChartRows.value[item.dataIndex]
          const amount = row?.amountLabel || value.toLocaleString()
          return t('quotation.pages.dashboard.chartAmountValueTooltip', {
            amount
          })
        }
      }
    }
  },
  onHover: (_event, elements, chart) => {
    const canvas = chart.canvas
    canvas.style.cursor = elements.length ? 'pointer' : 'default'
  }
}))

function formatPeriodLabel(period: string, grain: TrendGrain): string {
  const [, month = '', day = ''] = period.split('-')
  if (grain === 'monthly') {
    if (String(locale.value || '').startsWith('zh')) {
      return t('quotation.pages.dashboard.chartTrendMonthLabel', {
        month: Number(month)
      })
    }
    const date = new Date(`${period}-01T00:00:00`)
    return date.toLocaleString('en', { month: 'short' })
  }
  return `${month}-${day}`
}

const trendPeriods = computed(() =>
  (analytics.value?.trends[trendGrain.value] || []).map((row) => ({
    key: row.period,
    label: formatPeriodLabel(row.period, trendGrain.value)
  }))
)

const trendSeries = computed(() => {
  const rows = analytics.value?.trends[trendGrain.value] || []
  return {
    created: rows.map((row) => row.createdAmount),
    won: rows.map((row) => row.wonAmount)
  }
})

const hasTrendData = computed(
  () =>
    trendSeries.value.created.some((value) => value > 0) ||
    trendSeries.value.won.some((value) => value > 0)
)

const trendLineData = computed<ChartData<'line'>>(() => ({
  labels: trendPeriods.value.map((period) => period.label),
  datasets: [
    {
      label: t('quotation.pages.dashboard.chartTrendCreated'),
      data: trendSeries.value.created,
      borderColor: '#1677ff',
      backgroundColor: 'rgba(22, 119, 255, 0.12)',
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2
    },
    {
      label: t('quotation.pages.dashboard.chartTrendWon'),
      data: trendSeries.value.won,
      borderColor: '#389e0d',
      backgroundColor: 'rgba(56, 158, 13, 0.08)',
      fill: false,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2,
      borderDash: [5, 4]
    }
  ]
}))

const trendLineOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false
  },
  plugins: {
    legend: {
      display: true,
      position: 'bottom',
      labels: {
        boxWidth: 10,
        boxHeight: 10,
        font: { size: 11 },
        color: '#64748b',
        usePointStyle: true,
        pointStyle: 'circle'
      }
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      titleFont: { size: 11, weight: 'bold' },
      bodyFont: { size: 11 },
      padding: 10,
      callbacks: {
        label: (item: TooltipItem<'line'>) => {
          const value = Number(item.raw) || 0
          const label = currencyShortLabel(
            analytics.value?.currency || 'USD'
          )
          return `${item.dataset.label}: ${label} ${value.toLocaleString()}`
        }
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: {
        color: '#94a3b8',
        font: { size: 10 }
      },
      border: { display: false }
    },
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(148, 163, 184, 0.2)'
      },
      ticks: {
        color: '#94a3b8',
        font: { size: 10 },
        callback: (value) => {
          const amount = Number(value) || 0
          if (String(locale.value || '').startsWith('zh')) {
            return `${(amount / 10000).toFixed(amount >= 10000 ? 0 : 1)}万`
          }
          if (amount >= 1000) {
            return `${Math.round(amount / 1000)}k`
          }
          return `${amount}`
        }
      },
      border: { display: false }
    }
  }
}))

function formatRecentQuoteTime(value: string): string {
  const match = String(value || '').match(
    /^\d{4}-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/
  )
  if (!match) return String(value || '').replace('T', ' ')
  const [, month, day, hour, minute] = match
  if (String(locale.value || '').startsWith('zh')) {
    return `${month}月${day}日 ${hour}:${minute}`
  }
  return `${month}/${day} ${hour}:${minute}`
}

function setTrendGrain(grain: TrendGrain) {
  trendGrain.value = grain
}

function monthDateRange(period: string) {
  const [yearText = '', monthText = ''] = String(period || '').split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  if (!year || !month) return {}
  const lastDay = new Date(year, month, 0).getDate()
  const pad = (value: number) => String(value).padStart(2, '0')
  return {
    createdFrom: `${yearText}-${pad(month)}-01`,
    createdTo: `${yearText}-${pad(month)}-${pad(lastDay)}`,
  }
}

function openSelectedMonthQuotes() {
  emit('navigateToTab', {
    tab: 'list',
    ...monthDateRange(selectedPeriod.value),
  })
}

let summaryRequestId = 0
let analyticsRequestId = 0

async function loadDashboardSummary() {
  const requestId = ++summaryRequestId
  const period = selectedPeriod.value
  summaryLoading.value = true
  summaryError.value = false
  try {
    const data = await getDashboardSummary(period)
    if (
      requestId !== summaryRequestId
      || period !== selectedPeriod.value
    ) {
      return
    }
    summary.value = data
  } catch (error) {
    if (requestId !== summaryRequestId) return
    summaryError.value = true
    console.error('Unable to load dashboard summary', error)
  } finally {
    if (requestId === summaryRequestId) summaryLoading.value = false
  }
}

async function loadDashboardAnalytics() {
  const requestId = ++analyticsRequestId
  const currency = normalizeDashboardCurrency(dashboardCurrency.value)
  analyticsLoading.value = true
  analyticsError.value = false
  analytics.value = null
  try {
    const data = await getDashboardAnalytics(currency)
    if (
      requestId !== analyticsRequestId
      || currency !== normalizeDashboardCurrency(dashboardCurrency.value)
      || currency !== normalizeDashboardCurrency(data.currency)
    ) {
      return
    }
    analytics.value = data
  } catch (error) {
    if (requestId !== analyticsRequestId) return
    analyticsError.value = true
    console.error('Unable to load dashboard analytics', error)
  } finally {
    if (requestId === analyticsRequestId) analyticsLoading.value = false
  }
}

async function loadRecentQuotations() {
  try {
    recentQuotes.value = await getDashboardRecent(3)
  } catch (error) {
    recentQuotes.value = []
    console.error('Unable to load recent quotations', error)
  }
}

watch(dashboardCurrency, () => {
  void loadDashboardAnalytics()
})

watch(
  availableCurrencyOptions,
  (options) => {
    if (
      options.length
      && !options.some((option) => option.value === dashboardCurrency.value)
    ) {
      dashboardCurrency.value = options[0].value
    }
  }
)

watch(selectedPeriod, () => {
  void loadDashboardSummary()
})

onMounted(async () => {
  await Promise.all([
    loadDashboardSummary(),
    loadDashboardAnalytics(),
    loadRecentQuotations()
  ])
})
</script>

<template>
  <div
    id="dashboard-root"
    class="min-w-0 max-w-full space-y-4 overflow-x-hidden"
  >
    <div
      id="dashboard-overview-header"
      class="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between"
    >
      <div class="min-w-0">
        <h2 class="text-xl font-semibold text-dm-text">
          {{ t('quotation.pages.dashboard.overviewTitle') }}
        </h2>
        <p class="mt-1 text-sm text-dm-text-tertiary">
          {{ t('quotation.pages.dashboard.overviewSubtitle') }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-3">
        <FormSelect
          v-model="selectedPeriod"
          :aria-label="t('quotation.pages.dashboard.monthLabel')"
          :options="availablePeriodOptions"
          class-name="w-28 shrink-0"
          trigger-class-name="h-9 px-3 text-xs font-semibold text-dm-text-secondary"
          panel-class-name="min-w-28"
          test-id="dashboard-period"
        />
        <FormSelect
          v-model="dashboardCurrency"
          :aria-label="t('quotation.pages.dashboard.currencyLabel')"
          :options="availableCurrencyOptions"
          compact
          class-name="w-[4.5rem] shrink-0"
          trigger-class-name="h-9 !px-2 text-xs font-semibold leading-none text-dm-text-secondary"
          panel-class-name="!left-0 !right-auto min-w-0 w-full py-0.5"
          test-id="dashboard-currency"
        />
        <button
          id="btn-quick-create"
          type="button"
          class="dm-btn-primary cursor-pointer px-3 py-2 text-xs"
          @click="emit('navigateToTab', { tab: 'create' })"
        >
          <FileSpreadsheet class="h-4 w-4" />
          {{ t('quotation.actions.quickCreate') }}
        </button>
      </div>
    </div>

    <div
      id="dashboard-quotation-overview"
      class="grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-[minmax(23rem,0.86fr)_minmax(0,1.64fr)]"
    >
      <div
        id="dashboard-month-summary"
        class="dm-card min-h-40 min-w-0 p-4"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.monthSummaryTitle') }}
            </h3>
          </div>
          <span
            v-if="summary?.currentPeriod"
            class="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-600"
          >
            {{ formatSummaryPeriod(summary.currentPeriod) }}
          </span>
        </div>

        <div
          v-if="summaryError"
          class="flex min-h-24 items-center justify-center"
        >
          <button
            type="button"
            class="text-sm font-medium text-dm-primary"
            @click="loadDashboardSummary"
          >
            {{ t('quotation.pages.dashboard.retrySummary') }}
          </button>
        </div>
        <div
          v-else
          class="mt-5 grid grid-cols-[0.75fr_1.25fr] divide-x divide-dm-border-light"
          :class="{ 'animate-pulse opacity-50': summaryLoading }"
        >
          <div class="pr-4">
            <span class="text-xs text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.monthQuoteCount') }}
            </span>
            <div class="mt-1 font-mono text-2xl font-bold text-dm-text">
              {{ summaryLoading ? '—' : summary?.monthQuoteCount || 0 }}
              <span class="font-sans text-xs font-medium text-dm-text-tertiary">
                {{ t('quotation.pages.dashboard.quoteUnit') }}
              </span>
            </div>
          </div>
          <div class="pl-4">
            <span class="text-xs text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.monthQuoteDelta') }}
            </span>
            <div
              class="mt-1 font-mono text-2xl font-bold"
              :class="monthQuoteDeltaClass"
            >
              {{ summaryLoading ? '—' : monthQuoteDeltaLabel }}
            </div>
            <div
              v-if="!summaryLoading && summary"
              class="mt-1 text-xs text-dm-text-tertiary"
            >
              {{
                t('quotation.pages.dashboard.previousMonthCount', {
                  count: summary.previousMonthQuoteCount || 0
                })
              }}
            </div>
          </div>
        </div>
        <div
          class="mt-4 flex justify-end border-t border-dm-border-light pt-3 text-xs"
        >
          <button
            type="button"
            class="font-medium text-dm-primary"
            @click="openSelectedMonthQuotes"
          >
            {{ t('quotation.pages.dashboard.viewMonthQuotes') }}
          </button>
        </div>
      </div>

      <div
        id="dashboard-recent-overview"
        class="dm-card min-h-40 min-w-0 p-4"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.recentOverviewTitle') }}
            </h3>
            <p class="mt-0.5 text-xs text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.recentOverviewSubtitle') }}
            </p>
          </div>
          <button
            type="button"
            class="flex items-center gap-1 text-xs font-medium text-dm-primary"
            @click="emit('navigateToTab', { tab: 'list' })"
          >
            {{ t('quotation.actions.viewAll') }}
            <ChevronRight class="h-3.5 w-3.5" />
          </button>
        </div>

        <div
          class="mt-3 overflow-hidden rounded-lg border border-dm-border-light"
        >
          <button
            v-for="quote in overviewRecentQuotes"
            :key="quote.id"
            type="button"
            class="grid w-full grid-cols-[7.5rem_minmax(0,1fr)_6.5rem_6.5rem_1rem] items-center gap-3 border-b border-dm-border-light bg-white px-3 py-2 text-left text-xs last:border-b-0 hover:bg-slate-50"
            @click="emit('viewQuote', quote.id)"
          >
            <span class="truncate font-mono font-semibold text-dm-primary">
              {{ quote.quoteNo }}
            </span>
            <span class="flex min-w-0 items-baseline gap-2">
              <strong class="truncate font-medium text-dm-text">
                {{ quote.projectName }}
              </strong>
              <span class="truncate text-dm-text-tertiary">
                {{ quote.clientCompany }}
              </span>
            </span>
            <span class="text-right text-dm-text-tertiary">
              {{ formatRecentQuoteTime(quote.updatedAt) }}
            </span>
            <strong class="text-right font-mono text-dm-text">
              {{ currencyShortLabel(quote.currency) }}
              {{ quote.grandTotal.toLocaleString() }}
            </strong>
            <ChevronRight class="h-3.5 w-3.5 text-slate-400" />
          </button>
          <div
            v-if="overviewRecentQuotes.length === 0"
            class="flex min-h-24 items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.recentOverviewEmpty') }}
          </div>
        </div>
      </div>
    </div>

    <div
      id="dashboard-charts"
      class="grid min-w-0 max-w-full grid-cols-1 items-stretch gap-6"
    >
      <div
        id="chart-quote-amount"
        class="dm-card flex h-full min-w-0 max-w-full flex-col p-5"
      >
        <div
          class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
        >
          <div class="min-w-0">
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.chartAmountTitle') }}
            </h3>
            <p class="mt-0.5 text-sm text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.chartAmountSubtitle') }}
            </p>
          </div>
        </div>

        <div
          class="relative flex min-h-[16rem] min-w-0 max-w-full flex-1 items-center justify-center overflow-hidden px-1 py-2"
        >
          <div
            v-if="analyticsLoading"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.loading') }}
          </div>
          <button
            v-else-if="analyticsError"
            type="button"
            class="absolute inset-0 flex items-center justify-center text-sm font-medium text-dm-primary"
            @click="loadDashboardAnalytics"
          >
            {{ t('quotation.pages.dashboard.retryAnalytics') }}
          </button>
          <div
            v-else-if="quoteBreakdownData.length === 0"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.chartAmountEmpty') }}
          </div>
          <div
            v-else
            id="quote-breakdown-layout"
            class="flex w-full min-w-0 items-center justify-center"
          >
            <div
              class="flex min-h-[320px] w-full min-w-0 max-w-full items-center justify-center"
            >
              <div class="relative h-80 w-[min(100%,700px)]">
                <Pie
                  :key="
                    normalizeDashboardCurrency(
                      analytics?.currency || dashboardCurrency
                    )
                  "
                  :data="quoteBreakdownPieData"
                  :options="quoteBreakdownPieOptions"
                  :plugins="[quotePieLeaderLabelPlugin]"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        id="chart-trend"
        class="dm-card flex h-full min-w-0 max-w-full flex-col justify-between p-5"
      >
        <div
          class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
        >
          <div class="min-w-0">
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.chartTrendTitle') }}
            </h3>
            <p class="mt-0.5 text-sm text-dm-text-tertiary">
              {{
                trendGrain === 'monthly'
                  ? t('quotation.pages.dashboard.chartTrendSubtitleMonthly')
                  : t('quotation.pages.dashboard.chartTrendSubtitleWeekly')
              }}
            </p>
          </div>
          <div
            class="inline-flex shrink-0 rounded-lg border border-dm-border bg-[#fafafa] p-0.5"
            role="group"
            :aria-label="t('quotation.pages.dashboard.chartTrendToggleAria')"
          >
            <button
              type="button"
              class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
              :class="
                trendGrain === 'weekly'
                  ? 'bg-white text-dm-text shadow-xs'
                  : 'text-dm-text-tertiary hover:text-dm-text-secondary'
              "
              @click="setTrendGrain('weekly')"
            >
              {{ t('quotation.pages.dashboard.chartTrendToggleWeekly') }}
            </button>
            <button
              type="button"
              class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
              :class="
                trendGrain === 'monthly'
                  ? 'bg-white text-dm-text shadow-xs'
                  : 'text-dm-text-tertiary hover:text-dm-text-secondary'
              "
              @click="setTrendGrain('monthly')"
            >
              {{ t('quotation.pages.dashboard.chartTrendToggleMonthly') }}
            </button>
          </div>
        </div>

        <div class="relative h-64 w-full">
          <div
            v-if="analyticsLoading"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.loading') }}
          </div>
          <button
            v-else-if="analyticsError"
            type="button"
            class="absolute inset-0 flex items-center justify-center text-sm font-medium text-dm-primary"
            @click="loadDashboardAnalytics"
          >
            {{ t('quotation.pages.dashboard.retryAnalytics') }}
          </button>
          <div
            v-else-if="!hasTrendData"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.chartTrendEmpty') }}
          </div>
          <Line v-else :data="trendLineData" :options="trendLineOptions" />
        </div>

        <div
          class="mt-4 flex items-center justify-between border-t border-slate-50 pt-3 text-sm text-dm-text-tertiary"
        >
          <span>{{
            t('quotation.pages.dashboard.chartTrendFooterSource')
          }}</span>
          <span>{{ t('quotation.pages.dashboard.chartTrendFooterHint') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
