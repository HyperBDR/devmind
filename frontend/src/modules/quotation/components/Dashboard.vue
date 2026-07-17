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

const { t, locale } = useQuotationI18n()

const trendGrain = ref<TrendGrain>('monthly')

const chartQuotes = computed(() =>
  props.quotations.filter((q) => isChartQuoteStatus(q.status)),
)

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
  [...chartQuotes.value]
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
        label: `${quote.quoteNo} · ${amountLabel}`,
      }
    }),
)

const quoteBreakdownTotal = computed(() =>
  quoteBreakdownData.value.reduce((sum, row) => sum + row.value, 0),
)

const quoteBreakdownPieData = computed<ChartData<'pie'>>(() => ({
  labels: quoteBreakdownData.value.map((row) => row.label),
  datasets: [
    {
      data: quoteBreakdownData.value.map((row) => row.value),
      backgroundColor: quoteBreakdownData.value.map((row) => row.color),
      borderColor: '#ffffff',
      borderWidth: 2,
      hoverOffset: 12,
      hoverBorderWidth: 2,
    },
  ],
}))

function truncateCanvasText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string {
  if (ctx.measureText(text).width <= maxWidth) return text
  const ellipsis = '...'
  let next = text
  while (next.length > 0 && ctx.measureText(`${next}${ellipsis}`).width > maxWidth) {
    next = next.slice(0, -1)
  }
  return `${next}${ellipsis}`
}

const quotePieLeaderLinePlugin: Plugin<'pie'> = {
  id: 'quotePieLeaderLinePlugin',
  afterDatasetsDraw(chart) {
    if (chart.width < 420) return
    const dataset = chart.data.datasets[0]
    const meta = chart.getDatasetMeta(0)
    if (!dataset || !meta?.data?.length) return

    const ctx = chart.ctx
    ctx.save()
    ctx.font =
      '600 9px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
    ctx.textBaseline = 'middle'
    ctx.lineWidth = 1
    ctx.strokeStyle = '#cbd5e1'
    ctx.fillStyle = '#475569'

    meta.data.forEach((arc, index) => {
      const value = Number(dataset.data[index]) || 0
      const label = String(chart.data.labels?.[index] || '')
      if (!value || !label) return

      const section = arc as unknown as {
        x: number
        y: number
        startAngle: number
        endAngle: number
        outerRadius: number
      }
      const angle = (section.startAngle + section.endAngle) / 2
      const side = Math.cos(angle) >= 0 ? 1 : -1
      const startX = section.x + Math.cos(angle) * section.outerRadius
      const startY = section.y + Math.sin(angle) * section.outerRadius
      const bendX = section.x + Math.cos(angle) * (section.outerRadius + 18)
      const bendY = section.y + Math.sin(angle) * (section.outerRadius + 18)
      const labelReserve = Math.min(190, Math.max(150, chart.width * 0.27))
      const minLeaderLineLength = Math.min(44, Math.max(32, chart.width * 0.06))
      const minTextWidth = 96
      const preferredEndX = side > 0 ? chart.width - labelReserve : labelReserve
      const endX = side > 0
        ? Math.min(
            Math.max(preferredEndX, startX + minLeaderLineLength),
            chart.width - minTextWidth - 12,
          )
        : Math.max(
            Math.min(preferredEndX, startX - minLeaderLineLength),
            minTextWidth + 12,
          )
      const textX = side > 0 ? endX + 8 : endX - 8
      const maxTextWidth = side > 0 ? chart.width - textX - 10 : textX - 10

      ctx.beginPath()
      ctx.moveTo(startX, startY)
      ctx.lineTo(bendX, bendY)
      ctx.lineTo(endX, bendY)
      ctx.stroke()
      ctx.textAlign = side > 0 ? 'left' : 'right'
      ctx.fillText(truncateCanvasText(ctx, label, maxTextWidth), textX, bendY)
    })

    ctx.restore()
  },
}

const quoteBreakdownPieOptions = computed<ChartOptions<'pie'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: {
      top: 26,
      right: 130,
      bottom: 22,
      left: 130,
    },
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
          const row = quoteBreakdownData.value[item.dataIndex]
          const total = quoteBreakdownTotal.value || 1
          const percent = ((value / total) * 100).toFixed(1)
          return t('quotation.pages.dashboard.chartAmountPieTooltip', {
            amount: row?.amountLabel || value.toLocaleString(),
            wan: (value / 10000).toFixed(1),
            percent,
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

    <div id="dashboard-kpis" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div
        id="kpi-card-revenue"
        class="dm-card flex items-center justify-between p-5"
      >
        <div class="space-y-1">
          <span class="block text-xs text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiRevenueLabel') }}
          </span>
          <div class="font-mono text-2xl font-semibold text-dm-text">
            ¥{{ signedAmount.toLocaleString() }}
          </div>
          <div class="flex items-center gap-1 text-[10px] font-medium text-emerald-500">
            <TrendingUp class="h-3 w-3" />
            <span>{{ t('quotation.pages.dashboard.kpiRevenueHint') }}</span>
          </div>
        </div>
        <div class="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-50 text-emerald-500">
          <TrendingUp class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-active"
        class="dm-card flex items-center justify-between p-5"
      >
        <div class="space-y-1">
          <span class="block text-xs font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiSuccessRateLabel') }}
          </span>
          <div class="font-mono text-2xl font-extrabold text-dm-text">{{ successRate }}%</div>
          <p class="text-[10px] font-medium text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiSuccessRateHint') }}
          </p>
        </div>
        <div class="flex h-12 w-12 items-center justify-center rounded-lg bg-dm-primary-bg text-dm-primary">
          <FileCheck class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-feishu"
        class="dm-card flex items-center justify-between p-5"
      >
        <div class="space-y-1">
          <span class="block text-xs font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiExpiringLabel') }}
          </span>
          <div class="font-mono text-2xl font-extrabold text-dm-text">
            {{ t('quotation.pages.dashboard.kpiExpiringCount', { count: expiringSoonCount }) }}
          </div>
          <div class="flex items-center gap-1 text-[10px] font-medium text-amber-500">
            <Clock class="h-3 w-3" />
            <span>{{ t('quotation.pages.dashboard.kpiExpiringHint') }}</span>
          </div>
        </div>
        <div class="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-50 text-amber-500">
          <Clock class="h-6 w-6" />
        </div>
      </div>

      <div
        id="kpi-card-drafts"
        class="dm-card flex items-center justify-between p-5"
      >
        <div class="space-y-1">
          <span class="block text-xs font-semibold text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiActiveDraftsLabel') }}
          </span>
          <div class="font-mono text-2xl font-extrabold text-dm-text">
            {{
              t('quotation.pages.dashboard.kpiActiveDraftsValue', {
                open: activeCount,
                drafts: draftCount,
              })
            }}
          </div>
          <p class="text-[10px] font-medium text-dm-text-tertiary">
            {{ t('quotation.pages.dashboard.kpiActiveDraftsHint') }}
          </p>
        </div>
        <div class="flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500">
          <Users class="h-6 w-6" />
        </div>
      </div>
    </div>

    <div
      id="dashboard-charts"
      class="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(480px,0.82fr)]"
    >
      <div id="chart-quote-amount" class="dm-card flex h-full flex-col p-5">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0">
            <h3 class="text-sm font-semibold text-dm-text">
              {{ t('quotation.pages.dashboard.chartAmountTitle') }}
            </h3>
            <p class="mt-0.5 text-xs text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.chartAmountSubtitle') }}
            </p>
          </div>
        </div>

        <div class="relative flex h-64 flex-1 items-center justify-center overflow-hidden px-1 py-2">
          <div
            v-if="quoteBreakdownData.length === 0"
            class="absolute inset-0 flex items-center justify-center text-xs text-dm-text-tertiary"
          >
            {{ t('quotation.pages.dashboard.chartAmountEmpty') }}
          </div>
          <div v-else class="h-full w-full max-w-[680px]">
            <Pie
              :data="quoteBreakdownPieData"
              :options="quoteBreakdownPieOptions"
              :plugins="[quotePieLeaderLinePlugin]"
            />
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
            <p class="mt-0.5 text-xs text-dm-text-tertiary">
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
              class="rounded-md px-2.5 py-1 text-[11px] font-semibold transition"
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
              class="rounded-md px-2.5 py-1 text-[11px] font-semibold transition"
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
            class="absolute inset-0 flex items-center justify-center text-xs text-dm-text-tertiary"
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
          class="mt-4 flex items-center justify-between border-t border-slate-50 pt-3 text-xs text-dm-text-tertiary"
        >
          <span>{{ t('quotation.pages.dashboard.chartTrendFooterSource') }}</span>
          <span>{{ t('quotation.pages.dashboard.chartTrendFooterHint') }}</span>
        </div>
      </div>
    </div>

    <div
      id="dashboard-recent-grid"
      class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(480px,0.82fr)]"
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
            <p class="mt-0.5 text-xs text-dm-text-tertiary">
              {{ t('quotation.pages.dashboard.recentQuotesSubtitle') }}
            </p>
          </div>
          <button
            id="link-go-to-list"
            type="button"
            class="flex cursor-pointer items-center gap-1 text-xs font-medium text-dm-primary hover:text-dm-primary"
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
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-xs font-medium text-dm-primary">{{ quote.quoteNo }}</span>
                <span class="text-xs text-dm-text-tertiary">|</span>
                <span
                  class="max-w-[200px] truncate text-xs font-semibold text-dm-text-secondary sm:max-w-sm"
                >
                  {{ quote.projectName }}
                </span>
              </div>
              <div class="flex items-center gap-3 text-[11px] text-dm-text-tertiary">
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

            <div class="flex items-center gap-4">
              <div class="text-right">
                <div class="font-mono text-xs font-bold text-dm-text">
                  {{ currencySymbol(quote.currency) }}{{ quote.grandTotal.toLocaleString() }}
                </div>
                <span class="text-[10px] text-dm-text-tertiary">
                  {{ t('quotation.pages.dashboard.recentQuoteTotal') }}
                </span>
              </div>

              <StatusBadge :status="quote.status" />
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

          <div class="space-y-3 text-xs text-dm-text-secondary">
            <div class="flex items-start gap-2">
              <div
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-dm-primary-bg text-[10px] font-bold text-dm-primary"
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
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-[10px] font-bold text-emerald-500"
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
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-[10px] font-bold text-indigo-500"
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
          <div class="text-[11px] text-dm-text-tertiary">
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
