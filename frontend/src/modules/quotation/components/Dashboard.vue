<script setup lang="ts">
import { computed, ref } from 'vue'
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
  type TooltipItem,
} from 'chart.js'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import type { Quotation } from '../types'
import StatusBadge from './StatusBadge.vue'
import {
  isChartQuoteStatus,
  isExpiringSoonStatus,
  isOpenQuoteStatus,
  isWonQuoteStatus,
} from '../utils/quoteStatus'
import {
  TrendingUp,
  Users,
  FileCheck,
  Clock,
  ChevronRight,
  FileSpreadsheet,
  Building,
} from 'lucide-vue-next'

ChartJS.register(
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
)

type TrendGrain = 'weekly' | 'monthly'

const TREND_WEEK_COUNT = 8
const TREND_MONTH_COUNT = 6
const QUOTE_BREAKDOWN_MIN_SHARE = 2
const QUOTE_BREAKDOWN_MAX_SLICES = 8

const QUOTE_BREAKDOWN_COLORS = [
  '#2b9da3',
  '#389e0d',
  '#67b7bc',
  '#58b42d',
  '#1f7f86',
  '#9bcf53',
  '#136b73',
  '#d6a21f',
]

const props = defineProps<{
  quotations: Quotation[]
}>()

const emit = defineEmits<{
  viewQuote: [id: string]
  navigateToTab: [tab: string]
}>()

const { t, locale, quoteStatusLabel } = useQuotationI18n()

const trendGrain = ref<TrendGrain>('monthly')

function currencySymbol(currency: Quotation['currency']): string {
  if (currency === 'USD') return t('quotation.common.currencyUsd')
  if (currency === 'EUR') return t('quotation.common.currencyEur')
  return t('quotation.common.currencyCny')
}

const signedAmount = computed(() =>
  props.quotations
    .filter((q) => isWonQuoteStatus(q.status))
    .reduce((sum, q) => sum + q.grandTotal, 0),
)

const activeForRate = computed(() =>
  props.quotations.filter(
    (q) => isOpenQuoteStatus(q.status) || isWonQuoteStatus(q.status),
  ),
)

const successRate = computed(() =>
  activeForRate.value.length > 0
    ? Math.round(
        (props.quotations.filter((q) => isWonQuoteStatus(q.status)).length /
          activeForRate.value.length) *
          100,
      )
    : 0,
)

const expiringSoonCount = computed(
  () => props.quotations.filter((q) => isExpiringSoonStatus(q.status)).length,
)

const activeCount = computed(
  () => props.quotations.filter((q) => isOpenQuoteStatus(q.status)).length,
)

const draftCount = computed(
  () => props.quotations.filter((q) => q.status === 'Draft').length,
)

const quoteBreakdownData = computed(() =>
  props.quotations
    .filter((quote) => quote.grandTotal > 0)
    .sort((a, b) => b.grandTotal - a.grandTotal)
    .map((quote, index) => {
      const amountLabel = `${currencySymbol(quote.currency)}${quote.grandTotal.toLocaleString()}`
      return {
        key: quote.id,
        quoteNo: quote.quoteNo,
        value: quote.grandTotal,
        color: QUOTE_BREAKDOWN_COLORS[index % QUOTE_BREAKDOWN_COLORS.length],
        amountLabel,
        currency: quote.currency,
        share: 0,
        status: quote.status,
        label: `${quote.quoteNo} · ${amountLabel}`,
      }
    }),
)

const quoteBreakdownTotal = computed(() =>
  quoteBreakdownData.value.reduce((sum, row) => sum + row.value, 0),
)

const quoteBreakdownChartRows = computed(() => {
  const total = quoteBreakdownTotal.value || 1
  const rows = quoteBreakdownData.value.map((row) => ({
    ...row,
    share: (row.value / total) * 100,
  }))
  const visible = rows
    .filter((row) => row.share >= QUOTE_BREAKDOWN_MIN_SHARE)
    .slice(0, QUOTE_BREAKDOWN_MAX_SLICES)
  return visible.length ? visible : rows.slice(0, 1)
})

const quoteBreakdownRotation = computed(() => {
  const total = quoteBreakdownChartRows.value.reduce(
    (sum, row) => sum + row.value,
    0,
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
  gap: number,
) {
  const sorted = [...entries].sort((a, b) => a.labelY - b.labelY)
  sorted.forEach((entry, index) => {
    const floor = index === 0 ? minY : sorted[index - 1].labelY + gap
    entry.labelY = Math.max(entry.labelY, floor)
  })
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const ceiling = index === sorted.length - 1
      ? maxY
      : sorted[index + 1].labelY - gap
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
        labelY: arc.y + Math.sin(angle) * (arc.outerRadius + 10),
      }
    })
    const minY = chart.chartArea.top + 12
    const maxY = chart.chartArea.bottom - 12
    const arranged = [
      ...arrangePieLineLabels(
        entries.filter((entry) => entry.side === -1),
        minY,
        maxY,
        40,
      ),
      ...arrangePieLineLabels(
        entries.filter((entry) => entry.side === 1),
        minY,
        maxY,
        40,
      ),
    ]
    const { ctx } = chart
    ctx.save()
    arranged.forEach((entry) => {
      const row = quoteBreakdownChartRows.value[entry.index]
      if (!row) return
      const bendX = entry.anchorX + entry.side * 22
      const lineEndX = bendX + entry.side * 44
      const textX = lineEndX + entry.side * 6
      const availableTextWidth = entry.side === 1
        ? chart.width - textX - 6
        : textX - 6
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
      ctx.fillText(
        row.amountLabel,
        textX,
        entry.labelY + 2,
        maxTextWidth,
      )
    })
    ctx.restore()
  },
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
      hoverBorderWidth: 2,
    },
  ],
}))

const quoteBreakdownPieOptions = computed<ChartOptions<'pie'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  rotation: quoteBreakdownRotation.value,
  layout: {
    padding: { top: 20, right: 72, bottom: 20, left: 72 },
  },
  animation: {
    animateRotate: true,
    animateScale: true,
    duration: 450,
  },
  plugins: {
    legend: {
      display: false,
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
            amount,
          })
        },
      },
    },
  },
  onHover: (_event, elements, chart) => {
    const canvas = chart.canvas
    canvas.style.cursor = elements.length ? 'pointer' : 'default'
  },
}))

function parseQuoteDate(value?: string): Date | null {
  if (!value) return null
  const normalized = value.includes('T')
    ? value
    : value.replace(' ', 'T')
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function startOfWeekMonday(date: Date): Date {
  const next = new Date(date)
  next.setHours(0, 0, 0, 0)
  const day = next.getDay()
  const diff = (day + 6) % 7
  next.setDate(next.getDate() - diff)
  return next
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function periodKey(date: Date, grain: TrendGrain): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  if (grain === 'monthly') return `${year}-${month}`
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatPeriodLabel(date: Date, grain: TrendGrain): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  if (grain === 'monthly') {
    if (String(locale.value || '').startsWith('zh')) {
      return t('quotation.pages.dashboard.chartTrendMonthLabel', {
        month: Number(month),
      })
    }
    return date.toLocaleString('en', { month: 'short' })
  }
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

/**
 * Prefer first Accepted version timestamp; else updatedAt; else createdAt.
 */
function resolveWonAt(quote: Quotation): Date | null {
  if (!isWonQuoteStatus(quote.status)) return null
  const acceptedVersions = (quote.versions || [])
    .filter((version) => version.status === 'Accepted')
    .map((version) => parseQuoteDate(version.updateTime))
    .filter((date): date is Date => Boolean(date))
    .sort((a, b) => a.getTime() - b.getTime())
  if (acceptedVersions[0]) return acceptedVersions[0]
  return (
    parseQuoteDate(quote.updatedAt) || parseQuoteDate(quote.createdAt)
  )
}

const trendPeriods = computed(() => {
  const grain = trendGrain.value
  const periods: Array<{ key: string; label: string; start: Date }> = []

  if (grain === 'monthly') {
    const current = startOfMonth(new Date())
    for (let index = TREND_MONTH_COUNT - 1; index >= 0; index -= 1) {
      const start = new Date(
        current.getFullYear(),
        current.getMonth() - index,
        1,
      )
      periods.push({
        key: periodKey(start, grain),
        label: formatPeriodLabel(start, grain),
        start,
      })
    }
    return periods
  }

  const latestMonday = startOfWeekMonday(new Date())
  for (let index = TREND_WEEK_COUNT - 1; index >= 0; index -= 1) {
    const start = new Date(latestMonday)
    start.setDate(latestMonday.getDate() - index * 7)
    periods.push({
      key: periodKey(start, grain),
      label: formatPeriodLabel(start, grain),
      start,
    })
  }
  return periods
})

const trendSeries = computed(() => {
  const grain = trendGrain.value
  const createdMap = new Map<string, number>()
  const wonMap = new Map<string, number>()
  trendPeriods.value.forEach((period) => {
    createdMap.set(period.key, 0)
    wonMap.set(period.key, 0)
  })

  const firstStart = trendPeriods.value[0]?.start
  if (!firstStart) {
    return { created: [] as number[], won: [] as number[] }
  }

  props.quotations.forEach((quote) => {
    if (!isChartQuoteStatus(quote.status)) return

    const createdAt = parseQuoteDate(quote.createdAt)
    if (createdAt && createdAt >= firstStart) {
      const bucketStart =
        grain === 'monthly'
          ? startOfMonth(createdAt)
          : startOfWeekMonday(createdAt)
      const key = periodKey(bucketStart, grain)
      if (createdMap.has(key)) {
        createdMap.set(
          key,
          (createdMap.get(key) || 0) + (quote.grandTotal || 0),
        )
      }
    }

    const wonAt = resolveWonAt(quote)
    if (wonAt && wonAt >= firstStart) {
      const bucketStart =
        grain === 'monthly' ? startOfMonth(wonAt) : startOfWeekMonday(wonAt)
      const key = periodKey(bucketStart, grain)
      if (wonMap.has(key)) {
        wonMap.set(key, (wonMap.get(key) || 0) + (quote.grandTotal || 0))
      }
    }
  })

  return {
    created: trendPeriods.value.map(
      (period) => createdMap.get(period.key) || 0,
    ),
    won: trendPeriods.value.map((period) => wonMap.get(period.key) || 0),
  }
})

const hasTrendData = computed(() =>
  trendSeries.value.created.some((value) => value > 0) ||
  trendSeries.value.won.some((value) => value > 0),
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
      borderWidth: 2,
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
      borderDash: [5, 4],
    },
  ],
}))

const trendLineOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false,
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
        pointStyle: 'circle',
      },
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      titleFont: { size: 11, weight: 'bold' },
      bodyFont: { size: 11 },
      padding: 10,
      callbacks: {
        label: (item: TooltipItem<'line'>) => {
          const value = Number(item.raw) || 0
          return `${item.dataset.label}: ¥${value.toLocaleString()}`
        },
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: {
        color: '#94a3b8',
        font: { size: 10 },
      },
      border: { display: false },
    },
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(148, 163, 184, 0.2)',
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
        },
      },
      border: { display: false },
    },
  },
}))

const recentQuotes = computed(() =>
  [...props.quotations]
    .sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
    .slice(0, 5),
)

function setTrendGrain(grain: TrendGrain) {
  trendGrain.value = grain
}
</script>

<template>
  <div id="dashboard-root" class="space-y-6">
    <div
      id="dashboard-welcome"
      class="dm-card flex flex-col items-start justify-between gap-4 p-6 md:flex-row md:items-center"
    >
      <div>
        <h2 class="text-xl font-semibold text-dm-text">
          {{ t('quotation.pages.dashboard.welcomeTitle') }}
        </h2>
        <p class="mt-1 text-sm text-dm-text-tertiary">
          {{ t('quotation.pages.dashboard.welcomeSubtitle') }}
        </p>
      </div>
      <button
        id="btn-quick-create"
        type="button"
        class="dm-btn-primary cursor-pointer px-4 py-2 text-sm"
        @click="emit('navigateToTab', 'create')"
      >
        <FileSpreadsheet class="h-4 w-4" />
        {{ t('quotation.actions.quickCreate') }}
      </button>
    </div>

    <div id="dashboard-kpis" class="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-4">
      <div
        id="kpi-card-revenue"
        class="dm-card flex min-w-0 items-center justify-between gap-4 p-5"
      >
        <div class="space-y-1">
          <span class="block text-sm text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiRevenueLabel') }}
          </span>
          <div class="font-mono text-2xl font-semibold text-dm-text">
            ¥{{ signedAmount.toLocaleString() }}
          </div>
          <div class="flex items-center gap-1 text-xs font-medium text-emerald-500">
            <TrendingUp class="h-3 w-3" />
            <span>{{ t('quotation.pages.dashboard.kpiRevenueHint') }}</span>
          </div>
        </div>
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-500">
          <TrendingUp class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-active"
        class="dm-card flex min-w-0 items-center justify-between gap-4 p-5"
      >
        <div class="space-y-1">
          <span class="block text-sm font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiSuccessRateLabel') }}
          </span>
          <div class="font-mono text-2xl font-extrabold text-dm-text">{{ successRate }}%</div>
          <p class="text-xs font-medium text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiSuccessRateHint') }}
          </p>
        </div>
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-dm-primary-bg text-dm-primary">
          <FileCheck class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-feishu"
        class="dm-card flex min-w-0 items-center justify-between gap-4 p-5"
      >
        <div class="space-y-1">
          <span class="block text-sm font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiExpiringLabel') }}
          </span>
          <div class="font-mono text-2xl font-extrabold text-dm-text">
            {{ t('quotation.pages.dashboard.kpiExpiringCount', { count: expiringSoonCount }) }}
          </div>
          <div class="flex items-center gap-1 text-xs font-medium text-amber-500">
            <Clock class="h-3 w-3" />
            <span>{{ t('quotation.pages.dashboard.kpiExpiringHint') }}</span>
          </div>
        </div>
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-500">
          <Clock class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-drafts"
        class="dm-card flex min-w-0 items-center justify-between gap-4 p-5"
      >
        <div class="space-y-1">
          <span class="block text-sm font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiActiveDraftsLabel') }}
          </span>
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-dm-text">
            <span class="whitespace-nowrap font-mono text-2xl font-extrabold">
              {{ activeCount }}
              <span class="font-sans text-sm font-semibold">
                {{ t('quotation.pages.dashboard.kpiActiveOpenLabel') }}
              </span>
            </span>
            <span class="hidden h-4 border-l border-dm-border sm:block" />
            <span class="whitespace-nowrap font-mono text-2xl font-extrabold">
              {{ draftCount }}
              <span class="font-sans text-sm font-semibold">
                {{ t('quotation.pages.dashboard.kpiActiveDraftLabel') }}
              </span>
            </span>
          </div>
          <p class="text-xs font-medium text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiActiveDraftsHint') }}
          </p>
        </div>
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500">
          <Users class="h-6 w-6" />
        </div>
      </div>
    </div>

    <div
      id="dashboard-charts"
      class="grid grid-cols-1 items-stretch gap-6 2xl:grid-cols-[minmax(0,1.18fr)_minmax(480px,0.82fr)]"
    >
      <div id="chart-quote-amount" class="dm-card flex h-full flex-col p-5">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0">
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.chartAmountTitle') }}
            </h3>
            <p class="mt-0.5 text-sm text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.chartAmountSubtitle') }}
            </p>
          </div>
        </div>

        <div class="relative flex min-h-[16rem] flex-1 items-center justify-center overflow-hidden px-1 py-2">
          <div
            v-if="quoteBreakdownData.length === 0"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.chartAmountEmpty') }}
          </div>
          <div
            v-else
            id="quote-breakdown-layout"
            class="flex w-full min-w-0 items-center justify-center"
          >
            <div class="flex min-h-[320px] w-full items-center justify-center">
              <div class="relative h-80 w-[min(100%,700px)]">
                <Pie
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
        class="dm-card flex h-full flex-col justify-between p-5"
      >
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
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
            v-if="!hasTrendData"
            class="absolute inset-0 flex items-center justify-center text-sm text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.chartTrendEmpty') }}
          </div>
          <Line
            v-else
            :data="trendLineData"
            :options="trendLineOptions"
          />
        </div>

        <div
          class="mt-4 flex items-center justify-between border-t border-slate-50 pt-3 text-sm text-dm-text-tertiary"
        >
          <span>{{ t('quotation.pages.dashboard.chartTrendFooterSource') }}</span>
          <span>{{ t('quotation.pages.dashboard.chartTrendFooterHint') }}</span>
        </div>
      </div>
    </div>

    <div
      id="dashboard-recent-grid"
      class="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.18fr)_minmax(480px,0.82fr)]"
    >
      <div
        id="dashboard-recent-quotes"
        class="dm-card space-y-4 p-5"
      >
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.recentQuotesTitle') }}
            </h3>
            <p class="mt-0.5 text-sm text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.recentQuotesSubtitle') }}
            </p>
          </div>
          <button
            id="link-go-to-list"
            type="button"
            class="flex cursor-pointer items-center gap-1 text-sm font-medium text-dm-primary hover:text-dm-primary"
            @click="emit('navigateToTab', 'list')"
          >
            <span>{{ t('quotation.actions.viewAll') }}</span>
            <ChevronRight class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="divide-y divide-dm-border-light">
          <div
            v-for="quote in recentQuotes"
            :key="quote.id"
            class="flex cursor-pointer items-center justify-between rounded-lg px-2 py-3 transition duration-150 hover:bg-[#fafafa]"
            @click="emit('viewQuote', quote.id)"
          >
            <div class="min-w-0 space-y-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-sm font-medium text-dm-primary">{{ quote.quoteNo }}</span>
                <span class="text-sm text-dm-text-tertiary">|</span>
                <span
                  class="max-w-[200px] truncate text-sm font-semibold text-dm-text-secondary sm:max-w-sm"
                >
                  {{ quote.projectName }}
                </span>
              </div>
              <div class="flex items-center gap-3 text-xs text-dm-text-tertiary">
                <span>
                  {{ t('quotation.pages.dashboard.recentQuoteCompany', { company: quote.clientCompany }) }}
                </span>
                <span>{{ t('quotation.common.separator') }}</span>
                <span>
                  {{ t('quotation.pages.dashboard.recentQuoteSales', { salesperson: quote.salesperson }) }}
                </span>
                <span>{{ t('quotation.common.separator') }}</span>
                <span>
                  {{ t('quotation.pages.dashboard.recentQuoteTime', { time: quote.createdAt.substring(5, 16) }) }}
                </span>
              </div>
            </div>

            <div class="grid shrink-0 grid-cols-[8.5rem_5.5rem] items-center gap-3">
              <div class="min-w-0 text-right">
                <div class="font-mono text-sm font-bold text-dm-text">
                  {{ currencySymbol(quote.currency) }}{{ quote.grandTotal.toLocaleString() }}
                </div>
                <span class="text-xs text-dm-text-tertiary">
                  {{ t('quotation.pages.dashboard.recentQuoteTotal') }}
                </span>
              </div>

              <div class="flex justify-center">
                <StatusBadge :status="quote.status" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        id="dashboard-instructions"
        class="dm-card flex flex-col justify-between space-y-4 p-5"
      >
        <div class="space-y-3">
          <h3 class="text-sm font-semibold text-dm-text">
            {{ t('quotation.pages.dashboard.guideTitle') }}
          </h3>

          <div class="space-y-3 text-sm text-dm-text-secondary">
            <div class="flex items-start gap-2">
              <div
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-dm-primary-bg text-xs font-bold text-dm-primary"
              >
                1
              </div>
              <div>
                <h4 class="font-medium text-dm-text">
                  {{ t('quotation.pages.dashboard.guideStep1Title') }}
                </h4>
                <p class="mt-0.5 text-dm-text-tertiary">
                  {{ t('quotation.pages.dashboard.guideStep1Desc') }}
                </p>
              </div>
            </div>

            <div class="flex items-start gap-2">
              <div
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-xs font-bold text-emerald-500"
              >
                2
              </div>
              <div>
                <h4 class="font-medium text-dm-text">
                  {{ t('quotation.pages.dashboard.guideStep2Title') }}
                </h4>
                <p class="mt-0.5 text-dm-text-tertiary">
                  {{ t('quotation.pages.dashboard.guideStep2Desc') }}
                </p>
              </div>
            </div>

            <div class="flex items-start gap-2">
              <div
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-500"
              >
                3
              </div>
              <div>
                <h4 class="font-medium text-dm-text">
                  {{ t('quotation.pages.dashboard.guideStep3Title') }}
                </h4>
                <p class="mt-0.5 text-dm-text-tertiary">
                  {{ t('quotation.pages.dashboard.guideStep3Desc') }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2.5 rounded-lg bg-[#fafafa] p-3">
          <Building class="h-8 w-8 shrink-0 text-dm-text-tertiary" />
          <div class="text-xs text-dm-text-tertiary">
            <p class="font-medium text-dm-text">
              {{ t('quotation.pages.dashboard.securityTitle') }}
            </p>
            <p>{{ t('quotation.pages.dashboard.securityDesc') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
