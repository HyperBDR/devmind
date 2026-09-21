<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Bar, Line } from 'vue-chartjs'
import {
  BarElement,
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
} from 'chart.js'
import {
  BarChart3,
  CalendarDays,
  ChevronDown,
  TrendingUp,
} from 'lucide-vue-next'

import worldMap from '../../assets/sales-dashboard/world-map.png'
import FormSelect, { type FormSelectOption } from '../FormSelect.vue'
import { useQuotationI18n } from '../../composables/useQuotationI18n'
import { bindClickOutside } from '../useClickOutside'
import {
  getSalesDashboard,
  type SalesDashboardData,
  type SalesDimensionRow,
  type SalesPeriodRow,
} from '../../api/invoices'

type Granularity = 'month' | 'quarter' | 'year'

ChartJS.register(
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
)

const { locale, t } = useQuotationI18n()

const today = new Date()
const currentYear = today.getFullYear()
const startDate = ref(`${currentYear}-01`)
const endDate = ref(
  `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`,
)
const currency = ref('USD')
const comparisonYears = ref<1 | 2>(2)
const granularity = ref<Granularity>('month')
const comparisonGranularity = ref<Granularity>('quarter')
const showDatePicker = ref(false)
const data = ref<SalesDashboardData | null>(null)
const comparisonData = ref<SalesDashboardData | null>(null)
const loading = ref(false)
const error = ref('')
const availableCurrencies = ref<string[]>(['USD'])
const regionYear = ref(currentYear)
const productYear = ref(currentYear)
const customerYear = ref(currentYear)
const regionRows = ref<SalesDimensionRow[]>([])
const productRows = ref<SalesDimensionRow[]>([])
const customerRows = ref<SalesDimensionRow[]>([])
const dateRangeControlRef = ref<HTMLElement | null>(null)
let loadTimer: ReturnType<typeof setTimeout> | undefined
let requestSequence = 0

bindClickOutside(dateRangeControlRef, () => {
  showDatePicker.value = false
})

const dateLocale = computed(() =>
  String(locale.value).startsWith('zh') ? 'zh-CN' : 'en-US',
)
const monthLabels = computed(() =>
  Array.from({ length: 12 }, (_, index) =>
    new Intl.DateTimeFormat(dateLocale.value, { month: 'short' }).format(
      new Date(2020, index, 1),
    ),
  ),
)
const quarterLabels = computed(() =>
  Array.from({ length: 4 }, (_, index) =>
    t('quotation.sales.quarterLabel', { quarter: index + 1 }),
  ),
)

function amount(row: SalesPeriodRow | undefined): number {
  return Number(row?.amount || 0)
}

function sumRows(rows: SalesPeriodRow[] = []): number {
  return rows.reduce((total, row) => total + amount(row), 0)
}

function percentChange(current: number, previous: number): number | null {
  if (!previous) return null
  return ((current - previous) / previous) * 100
}

function formatMoney(value: number | string): string {
  const formatted = new Intl.NumberFormat(dateLocale.value, {
    maximumFractionDigits: 0,
  }).format(Number(value || 0))
  return `${currency.value} ${formatted}`
}

function formatCompactMoney(value: number | string): string {
  const number = Number(value || 0)
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`
  if (number >= 1_000) return `${Math.round(number / 1_000)}K`
  return String(Math.round(number))
}

function formatDateLabel(value: string): string {
  if (!value) return '—'
  const monthValue = value.length === 7 ? `${value}-01` : value
  return new Intl.DateTimeFormat(dateLocale.value, {
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${monthValue}T00:00:00`))
}

function formatMonthLabel(value: string): string {
  return new Intl.DateTimeFormat(dateLocale.value, {
    month: 'short',
  }).format(new Date(`${value}T00:00:00`))
}

function formatChange(value: number | null): string {
  if (value === null) return '—'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function monthEndDate(value: string): string {
  if (!/^\d{4}-\d{2}$/.test(value)) return ''
  const [year, month] = value.split('-').map(Number)
  const lastDay = new Date(year, month, 0).getDate()
  return `${value}-${String(lastDay).padStart(2, '0')}`
}

function rowWidth(row: SalesDimensionRow, rows: SalesDimensionRow[]) {
  const maximum = Math.max(...rows.map((item) => Number(item.amount)), 1)
  return `${Math.max((Number(row.amount) / maximum) * 100, 3)}%`
}

function rowShare(row: SalesDimensionRow, rows: SalesDimensionRow[]) {
  const total = rows.reduce((sum, item) => sum + Number(item.amount), 0)
  if (!total) return '0.0%'
  return `${((Number(row.amount) / total) * 100).toFixed(1)}%`
}

function displayName(value?: string): string {
  if (!value || value === 'Unspecified') {
    return t('quotation.sales.unspecified')
  }
  return value
}

function productDisplayName(value?: string): string {
  const name = displayName(value)
  const maxCharacters = 28
  if (name.length <= maxCharacters) return name
  const words = name.split(/\s+/)
  let result = ''
  for (const word of words) {
    const candidate = result ? `${result} ${word}` : word
    if (candidate.length > maxCharacters) break
    result = candidate
  }
  return result || name.slice(0, maxCharacters)
}

function rowsForYear(rows: SalesPeriodRow[], year: number): SalesPeriodRow[] {
  return rows.filter((row) => Number(row.period.slice(0, 4)) === year)
}

function periodMonthRange(period: string): [number, number] | null {
  if (/^\d{4}$/.test(period)) return [1, 12]
  if (/^\d{4}-Q[1-4]$/.test(period)) {
    const quarter = Number(period.slice(-1))
    return [(quarter - 1) * 3 + 1, quarter * 3]
  }
  if (/^\d{4}-\d{2}$/.test(period)) {
    const month = Number(period.slice(-2))
    return [month, month]
  }
  return null
}

function chartMonthBounds() {
  if (!startDate.value || !endDate.value) {
    return { startMonth: 1, endMonth: 12 }
  }
  const startYear = Number(startDate.value.slice(0, 4))
  const startMonth = startYear === selectedYear.value
    ? Number(startDate.value.slice(5, 7))
    : 1
  return { startMonth, endMonth: Number(endDate.value.slice(5, 7)) }
}

function rowsForSelectedMonths(
  rows: SalesPeriodRow[],
  year: number,
): SalesPeriodRow[] {
  const { startMonth, endMonth } = chartMonthBounds()
  return rowsForYear(rows, year).filter((row) => {
    const range = periodMonthRange(row.period)
    if (!range) return false
    return range[1] >= startMonth && range[0] <= endMonth
  })
}

function chartLabels(value: Granularity): string[] {
  if (value === 'quarter') return quarterLabels.value
  if (value === 'year') return [String(selectedYear.value)]
  return monthLabels.value
}

function bucketIndex(period: string, value: Granularity): number {
  if (value === 'year') return 0
  if (value === 'quarter') {
    if (period.includes('-Q')) return Number(period.slice(-1)) - 1
    return Math.ceil(Number(period.slice(5, 7)) / 3) - 1
  }
  return Number(period.slice(5, 7)) - 1
}

function valuesFor(
  rows: SalesPeriodRow[],
  value: Granularity,
  fullRange = false,
): Array<number | null> {
  const values: Array<number | null> = chartLabels(value).map(() => null)
  const { startMonth, endMonth } = chartMonthBounds()
  if (value === 'year') values[0] = 0
  if (value === 'month') {
    const firstMonth = fullRange ? 1 : startMonth
    const lastMonth = fullRange ? 12 : endMonth
    for (let month = firstMonth; month <= lastMonth; month += 1) {
      values[month - 1] = 0
    }
  }
  if (value === 'quarter') {
    const startQuarter = fullRange ? 1 : Math.ceil(startMonth / 3)
    const endQuarter = fullRange ? 4 : Math.ceil(endMonth / 3)
    for (let quarter = startQuarter; quarter <= endQuarter; quarter += 1) {
      values[quarter - 1] = 0
    }
  }
  rows.forEach((row) => {
    const index = bucketIndex(row.period, value)
    if (index < 0 || index >= values.length) return
    values[index] = Number(values[index] || 0) + amount(row)
  })
  return values
}

function rowsForGranularity(
  rows: SalesPeriodRow[],
  target: Granularity,
): SalesPeriodRow[] {
  if (target === 'month') return rows
  const totals = new Map<string, SalesPeriodRow>()
  rows.forEach((row) => {
    const year = Number(row.period.slice(0, 4))
    const month = Number(row.period.slice(5, 7))
    const period = target === 'year'
      ? String(year)
      : `${year}-Q${Math.ceil(month / 3)}`
    const current = totals.get(period)
    if (current) {
      current.amount = String(Number(current.amount) + Number(row.amount))
      current.invoice_count += row.invoice_count
      return
    }
    totals.set(period, {
      period,
      amount: row.amount,
      invoice_count: row.invoice_count,
    })
  })
  return [...totals.values()].sort((left, right) =>
    left.period.localeCompare(right.period),
  )
}

const dateRangeLabel = computed(
  () => `${formatDateLabel(startDate.value)} – ${formatDateLabel(
    endDate.value,
  )}`,
)
const selectedYear = computed(
  () => Number(endDate.value.slice(0, 4)) || currentYear,
)
const selectedQuarter = computed(
  () => Math.ceil(Number(endDate.value.slice(5, 7) || 1) / 3),
)
const yearOptions = computed<FormSelectOption[]>(() =>
  Array.from(
    { length: comparisonYears.value + 1 },
    (_, index) => {
      const year = selectedYear.value - index
      return {
        value: String(year),
        label: t('quotation.sales.yearToDateOption', { year }),
      }
    },
  ),
)
const currencyOptions = computed<FormSelectOption[]>(() =>
  (
    availableCurrencies.value.length
      ? availableCurrencies.value
      : [currency.value]
  ).map((value) => ({ value, label: value })),
)
const comparisonOptions = computed<FormSelectOption[]>(() => [
  { value: '1', label: t('quotation.sales.compareOneYear') },
  { value: '2', label: t('quotation.sales.compareTwoYears') },
])
const granularitySelectOptions = computed<FormSelectOption[]>(() => [
  { value: 'month', label: t('quotation.sales.month') },
  { value: 'quarter', label: t('quotation.sales.quarter') },
  { value: 'year', label: t('quotation.sales.year') },
])
const totalSales = computed(() => sumRows(data.value?.series))
const qtd = computed(() => sumRows(data.value?.quarter_to_date))
const ytd = computed(() => sumRows(data.value?.year_to_date))
const priorTotal = computed(() =>
  Number(data.value?.comparison[0]?.period_amount || 0),
)
const totalChange = computed(() =>
  percentChange(totalSales.value, priorTotal.value),
)
const priorQuarter = computed(() =>
  Number(data.value?.comparison[0]?.quarter_to_date_amount || 0),
)
const priorYtd = computed(() =>
  Number(data.value?.comparison[0]?.year_to_date_amount || 0),
)
const qtdChange = computed(() =>
  percentChange(qtd.value, Number(priorQuarter.value)),
)
const ytdChange = computed(() =>
  percentChange(ytd.value, Number(priorYtd.value)),
)
const yearOverYear = computed(() =>
  Number(data.value?.year_over_year.amount || 0),
)
const previousYearOverYear = computed(() =>
  Number(data.value?.year_over_year.previous_amount || 0),
)
const yearOverYearChange = computed(() =>
  percentChange(yearOverYear.value, previousYearOverYear.value),
)
const yearOverYearComparison = computed(() => {
  const rolling = data.value?.year_over_year
  if (!rolling) {
    return t('quotation.sales.samePeriodComparison', {
      year: selectedYear.value - 1,
    })
  }
  return t('quotation.sales.rollingComparison', {
    start: formatDateLabel(rolling.previous_start_date),
    end: formatDateLabel(rolling.previous_end_date),
  })
})

const yearlyTrendData = computed(() => {
  const result = data.value
  const points = [
    ...(result?.comparison || []).map((comparison) => ({
      year: comparison.year,
      value: sumRows(rowsForYear(comparison.series, comparison.year)),
      hasData: rowsForYear(comparison.series, comparison.year).length > 0,
    })),
    {
      year: selectedYear.value,
      value: sumRows(rowsForSelectedMonths(
        result?.series || [],
        selectedYear.value,
      )),
      hasData: rowsForSelectedMonths(
        result?.series || [],
        selectedYear.value,
      ).length
        > 0,
    },
  ]
    .filter((point) => point.hasData)
    .sort((left, right) => left.year - right.year)
  return {
    labels: points.map((point) => String(point.year)),
    values: points.map((point) => point.value),
  }
})

const trendData = computed<ChartData<'line'>>(() => {
  const colors = ['#1677ff', '#32b497', '#98abc7']
  const rows = rowsForSelectedMonths(
    data.value?.series || [],
    selectedYear.value,
  )
  const comparisons = data.value?.comparison || []
  const displayRows = rowsForGranularity(rows, granularity.value)
  if (granularity.value === 'year') {
    return {
      labels: yearlyTrendData.value.labels,
      datasets: [{
        label: t('quotation.sales.annualSales'),
        data: yearlyTrendData.value.values,
        borderColor: colors[0],
        backgroundColor: colors[0],
        pointBackgroundColor: colors[0],
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2.5,
        tension: 0.16,
      }],
    }
  }
  return {
    labels: chartLabels(granularity.value),
    datasets: [
      {
        label: String(selectedYear.value),
        data: valuesFor(displayRows, granularity.value),
        borderColor: colors[0],
        backgroundColor: colors[0],
        pointBackgroundColor: colors[0],
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
        spanGaps: false,
        tension: 0.16,
      },
      ...comparisons.map((comparison, index) => ({
        label: String(comparison.year),
        data: valuesFor(
          rowsForYear(comparison.series, comparison.year),
          granularity.value,
          true,
        ),
        borderColor: colors[index + 1],
        backgroundColor: colors[index + 1],
        pointBackgroundColor: colors[index + 1],
        pointRadius: 2.5,
        pointHoverRadius: 5,
        borderWidth: 2,
        borderDash: [5, 4],
        spanGaps: false,
        tension: 0.16,
      })),
    ],
  }
})

const trendOptions: ChartOptions<'line'> = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      position: 'top',
      align: 'end',
      labels: {
        boxWidth: 7,
        boxHeight: 7,
        usePointStyle: true,
        pointStyle: 'circle',
        color: '#60759c',
        padding: 22,
        font: { size: 12 },
      },
    },
    tooltip: {
      backgroundColor: '#ffffff',
      borderColor: '#dbe5f2',
      borderWidth: 1,
      titleColor: '#102044',
      bodyColor: '#31466f',
      padding: 12,
      displayColors: true,
      callbacks: {
        label: (context) =>
          `${context.dataset.label}    ${formatMoney(Number(context.raw))}`,
      },
    },
  },
  scales: {
    x: {
      border: { display: false },
      grid: { color: '#e8eef7' },
      ticks: { color: '#60759c', font: { size: 11 } },
    },
    y: {
      beginAtZero: true,
      border: { display: false },
      grid: { color: '#e8eef7' },
      ticks: {
        color: '#60759c',
        font: { size: 11 },
        callback: (value) => formatCompactMoney(Number(value)),
      },
    },
  },
}

const periodData = computed<ChartData<'bar'>>(() => {
  const source = comparisonData.value
  const colors = ['#1677ff', '#32b497', '#98abc7']
  if (comparisonGranularity.value === 'year') {
    return {
      labels: yearlyTrendData.value.labels,
      datasets: [{
        label: t('quotation.sales.annualSales'),
        data: yearlyTrendData.value.values,
        backgroundColor: colors[0],
        borderRadius: 0,
      }],
    }
  }
  return {
    labels: chartLabels(comparisonGranularity.value),
    datasets: [
      {
        label: String(selectedYear.value),
        data: valuesFor(
          rowsForSelectedMonths(
            source?.series || [],
            selectedYear.value,
          ),
          comparisonGranularity.value,
        ),
        backgroundColor: colors[0],
        borderRadius: 0,
        minBarLength: 4,
      },
      ...(source?.comparison || []).map((comparison, index) => ({
        label: String(comparison.year),
        data: valuesFor(
          rowsForYear(comparison.series, comparison.year),
          comparisonGranularity.value,
          true,
        ),
        backgroundColor: colors[index + 1],
        borderRadius: 0,
        minBarLength: 4,
      })),
    ],
  }
})

const periodOptions: ChartOptions<'bar'> = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        boxWidth: 8,
        boxHeight: 8,
        usePointStyle: true,
        pointStyle: 'rectRounded',
        color: '#60759c',
        padding: 22,
        font: { size: 11 },
      },
    },
    tooltip: {
      backgroundColor: '#ffffff',
      borderColor: '#dbe5f2',
      borderWidth: 1,
      titleColor: '#102044',
      bodyColor: '#31466f',
      padding: 12,
      displayColors: true,
      callbacks: {
        label: (context) =>
          `${context.dataset.label}    ${formatMoney(Number(context.raw))}`,
      },
    },
  },
  scales: {
    x: {
      border: { display: false },
      grid: { color: '#e8eef7' },
      ticks: { color: '#60759c', font: { size: 11 } },
    },
    y: {
      beginAtZero: true,
      border: { display: false },
      grid: { color: '#e8eef7' },
      ticks: {
        color: '#60759c',
        font: { size: 11 },
        callback: (value) => formatCompactMoney(Number(value)),
      },
    },
  },
}

const kpis = computed(() => [
  {
    label: t('quotation.sales.totalSales'),
    value: totalSales.value,
    change: totalChange.value,
    comparison: t('quotation.sales.samePeriodComparison', {
      year: selectedYear.value - 1,
    }),
    icon: BarChart3,
  },
  {
    label: t('quotation.sales.qtdTitle', {
      quarter: selectedQuarter.value,
      year: selectedYear.value,
    }),
    value: qtd.value,
    change: qtdChange.value,
    comparison: t('quotation.sales.quarterComparison', {
      quarter: selectedQuarter.value,
      year: selectedYear.value - 1,
    }),
    icon: CalendarDays,
  },
  {
    label: t('quotation.sales.ytdTitle', {
      month: formatMonthLabel(endDate.value),
      year: selectedYear.value,
    }),
    value: ytd.value,
    change: ytdChange.value,
    comparison: t('quotation.sales.samePeriodComparison', {
      year: selectedYear.value - 1,
    }),
    icon: CalendarDays,
  },
  {
    label: t('quotation.sales.yearOverYear'),
    value: yearOverYear.value,
    change: yearOverYearChange.value,
    comparison: yearOverYearComparison.value,
    icon: TrendingUp,
  },
])

async function loadDashboard() {
  if (!startDate.value || !endDate.value) {
    loading.value = false
    return
  }
  if (startDate.value > endDate.value) {
    error.value = t('quotation.sales.invalidDateRange')
    return
  }
  loading.value = true
  error.value = ''
  const sequence = ++requestSequence
  try {
    const params = {
      currency: currency.value,
      start_date: `${startDate.value}-01`,
      end_date: monthEndDate(endDate.value),
      comparison_years: comparisonYears.value,
    }
    const trendRequest = getSalesDashboard({
      ...params,
      granularity: 'month',
    })
    const trendResult = await trendRequest
    if (sequence !== requestSequence) return
    availableCurrencies.value = trendResult.available_currencies
    if (
      availableCurrencies.value.length
      && !availableCurrencies.value.includes(currency.value)
    ) {
      currency.value = availableCurrencies.value[0]
      return
    }
    data.value = trendResult
    comparisonData.value = trendResult
    regionRows.value = trendResult.by_region
    productRows.value = trendResult.by_product
    customerRows.value = trendResult.top_customers
  } catch (loadError: unknown) {
    error.value = loadError instanceof Error
      ? loadError.message
      : t('quotation.sales.loadDashboardFailed')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function setGranularity(value: Granularity) {
  granularity.value = value
}

function setComparisonYears(value: string) {
  comparisonYears.value = Number(value) as 1 | 2
}

function setComparisonGranularity(value: string) {
  comparisonGranularity.value = value as Granularity
}

async function loadBreakdown(
  section: 'region' | 'product' | 'customer',
  year: number,
) {
  try {
    const result = await getSalesDashboard({
      currency: currency.value,
      start_date: `${year}-01-01`,
      end_date: `${year}-12-31`,
      comparison_years: 1,
      granularity: 'month',
      dimension: section,
    })
    if (section === 'region') regionRows.value = result.by_region
    if (section === 'product') productRows.value = result.by_product
    if (section === 'customer') customerRows.value = result.top_customers
  } catch (loadError: unknown) {
    error.value = loadError instanceof Error
      ? loadError.message
      : t('quotation.sales.loadBreakdownFailed')
  }
}

function setBreakdownYear(
  section: 'region' | 'product' | 'customer',
  value: string,
) {
  const year = Number(value)
  if (section === 'region') regionYear.value = year
  if (section === 'product') productYear.value = year
  if (section === 'customer') customerYear.value = year
  void loadBreakdown(section, year)
}

function scheduleDashboardLoad() {
  if (loadTimer) clearTimeout(loadTimer)
  loadTimer = setTimeout(() => void loadDashboard(), 120)
}

watch([startDate, endDate, currency, comparisonYears], () => {
  scheduleDashboardLoad()
})

onMounted(loadDashboard)
</script>

<template>
  <div data-sales-dashboard class="sales-analytics-shell">
    <main class="sales-dashboard-main">
      <div class="dashboard-topbar">
        <div class="dashboard-title-block">
          <h1>{{ t('quotation.sales.dashboardTitle') }}</h1>
          <p>{{ t('quotation.sales.dashboardSubtitle') }}</p>
        </div>

        <div class="dashboard-filters">
          <div ref="dateRangeControlRef" class="date-range-control">
            <button
              class="filter-control date-range-button"
              type="button"
              @click="showDatePicker = !showDatePicker"
            >
              <CalendarDays :size="16" />
              <span>{{ dateRangeLabel }}</span>
              <ChevronDown :size="15" />
            </button>
            <div
              v-if="showDatePicker"
              class="date-range-popover"
              @click.stop
            >
              <label>
                <span>{{ t('quotation.sales.dateFrom') }}</span>
                <input
                  v-model="startDate"
                  type="month"
                  @change="showDatePicker = false"
                >
              </label>
              <label>
                <span>{{ t('quotation.sales.dateTo') }}</span>
                <input
                  v-model="endDate"
                  type="month"
                  @change="showDatePicker = false"
                >
              </label>
            </div>
          </div>

          <FormSelect
            v-model="currency"
            :options="currencyOptions"
            class-name="currency-control"
            trigger-class-name="dashboard-select-trigger"
            panel-class-name="dashboard-select-panel"
            :aria-label="t('quotation.sales.currencyLabel')"
          />

          <FormSelect
            :model-value="String(comparisonYears)"
            :options="comparisonOptions"
            class-name="compare-control"
            trigger-class-name="dashboard-select-trigger"
            panel-class-name="dashboard-select-panel"
            :aria-label="t('quotation.sales.comparisonYearsLabel')"
            @update:model-value="setComparisonYears"
          />

        </div>
      </div>

      <div v-if="error" class="dashboard-error">{{ error }}</div>

      <section data-sales-kpis class="dashboard-kpi-grid">
        <article
          v-for="kpi in kpis"
          :key="kpi.label"
          class="dashboard-card kpi-card"
        >
          <span class="kpi-icon">
            <component :is="kpi.icon" :size="22" />
          </span>
          <div class="kpi-content">
            <p class="kpi-label">{{ kpi.label }}</p>
            <strong>{{ formatMoney(kpi.value) }}</strong>
            <p class="kpi-comparison">
              <span
                v-if="kpi.change !== null"
                :class="kpi.change >= 0 ? 'positive' : 'negative'"
              >
                {{ kpi.change >= 0 ? '↑' : '↓' }}
                {{ formatChange(kpi.change) }}
              </span>
              <span v-else class="neutral">—</span>
              <span>{{ kpi.comparison }}</span>
            </p>
          </div>
        </article>
      </section>

      <section class="dashboard-chart-grid">
        <article data-sales-trend class="dashboard-card chart-card trend-card">
          <div class="card-heading chart-heading">
            <h2>{{ t('quotation.sales.salesTrend') }}</h2>
            <div
              class="granularity-tabs"
              role="group"
              :aria-label="t('quotation.sales.trendGranularityLabel')"
            >
              <button
                v-for="option in granularitySelectOptions"
                :key="option.value"
                type="button"
                :class="granularity === option.value ? 'is-selected' : ''"
                @click="setGranularity(option.value as Granularity)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
          <div class="trend-chart-frame">
            <Line :data="trendData" :options="trendOptions" />
          </div>
        </article>

        <article
          data-sales-period-comparison
          class="dashboard-card chart-card comparison-card"
        >
          <div class="card-heading chart-heading">
            <h2>{{ t('quotation.sales.periodComparison') }}</h2>
            <FormSelect
              :model-value="comparisonGranularity"
              :options="granularitySelectOptions"
              class-name="comparison-period-control"
              trigger-class-name="dashboard-select-trigger"
              panel-class-name="dashboard-select-panel"
              :aria-label="t('quotation.sales.comparisonPeriodLabel')"
              @update:model-value="setComparisonGranularity"
            />
          </div>
          <div class="comparison-chart-frame">
            <Bar :data="periodData" :options="periodOptions" />
          </div>
        </article>
      </section>

      <section class="dashboard-breakdown-grid">
        <article
          id="sales-region"
          data-sales-region
          class="dashboard-card breakdown-card region-card"
        >
          <div class="card-heading">
            <h2>{{ t('quotation.sales.byRegion') }}</h2>
            <FormSelect
              :model-value="String(regionYear)"
              :options="yearOptions"
              class-name="breakdown-period-select"
              trigger-class-name="dashboard-select-trigger dashboard-select-trigger--small"
              panel-class-name="dashboard-select-panel"
              :aria-label="t('quotation.sales.regionYearLabel')"
              @update:model-value="setBreakdownYear('region', $event)"
            />
          </div>
          <div class="region-breakdown-content">
            <img
              :src="worldMap"
              class="world-map"
              :alt="t('quotation.sales.worldMapAlt')"
            >
            <div class="rank-list region-list">
              <div
                v-for="row in regionRows.slice(0, 4)"
                :key="row.name"
                class="rank-row"
              >
                <span class="rank-name">{{ displayName(row.name) }}</span>
                <span class="rank-bar">
                  <i :style="{ width: rowWidth(row, regionRows) }" />
                </span>
                <span class="rank-value">
                  <strong>{{ formatMoney(row.amount) }}</strong>
                  <small>{{ rowShare(row, regionRows) }}</small>
                </span>
              </div>
            </div>
          </div>
        </article>

        <article
          data-sales-product
          class="dashboard-card breakdown-card product-card"
        >
          <div class="card-heading">
            <h2>{{ t('quotation.sales.byProduct') }}</h2>
            <FormSelect
              :model-value="String(productYear)"
              :options="yearOptions"
              class-name="breakdown-period-select"
              trigger-class-name="dashboard-select-trigger dashboard-select-trigger--small"
              panel-class-name="dashboard-select-panel"
              :aria-label="t('quotation.sales.productYearLabel')"
              @update:model-value="setBreakdownYear('product', $event)"
            />
          </div>
          <div class="rank-list product-list">
            <div
              v-for="row in productRows.slice(0, 6)"
              :key="row.name"
              class="rank-row"
            >
              <span
                class="rank-name product-rank-name"
                :title="displayName(row.name)"
              >
                {{ productDisplayName(row.name) }}
              </span>
              <span class="rank-bar">
                <i :style="{ width: rowWidth(row, productRows) }" />
              </span>
              <span class="rank-value">
                <strong>{{ formatMoney(row.amount) }}</strong>
                <small>{{ rowShare(row, productRows) }}</small>
              </span>
            </div>
          </div>
        </article>

        <article
          data-sales-customers
          class="dashboard-card breakdown-card customer-card"
        >
          <div class="card-heading">
            <h2>{{ t('quotation.sales.topCustomers') }}</h2>
            <FormSelect
              :model-value="String(customerYear)"
              :options="yearOptions"
              class-name="breakdown-period-select"
              trigger-class-name="dashboard-select-trigger dashboard-select-trigger--small"
              panel-class-name="dashboard-select-panel"
              :aria-label="t('quotation.sales.customerYearLabel')"
              @update:model-value="setBreakdownYear('customer', $event)"
            />
          </div>
          <div class="customer-table-wrap">
            <table class="customer-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{{ t('quotation.sales.customer') }}</th>
                  <th>{{ t('quotation.sales.region') }}</th>
                  <th>{{ t('quotation.sales.invoiceValue') }}</th>
                  <th>{{ t('quotation.sales.shareOfTotal') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in customerRows.slice(0, 10)"
                  :key="row.name"
                >
                  <td>{{ index + 1 }}</td>
                  <td :title="row.name">{{ row.name }}</td>
                  <td>{{ displayName(row.region) }}</td>
                  <td>{{ formatMoney(row.amount) }}</td>
                  <td>{{ rowShare(row, customerRows) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <RouterLink class="view-all-link" to="/quotation/customers">
            {{ t('quotation.sales.viewAllCustomers') }} →
          </RouterLink>
        </article>
      </section>
    </main>
  </div>
</template>

<style scoped>
.sales-analytics-shell {
  --sales-blue: #1677ff;
  --sales-navy: #0d1d3a;
  --sales-muted: #60759c;
  --sales-border: #dfe8f4;
  width: 100%;
  height: 100%;
  min-height: 0;
  color: var(--sales-navy);
  background:
    radial-gradient(circle at 56% 0, #eaf4ff 0, transparent 36%),
    #f6f9fd;
  font-family: Inter, "Segoe UI", Arial, sans-serif;
}

.sales-dashboard-main {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 16px 26px 10px;
}

.dashboard-topbar {
  display: flex;
  min-height: 58px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.dashboard-title-block h1 {
  margin: 0;
  color: #071126;
  font-size: 31px;
  font-weight: 750;
  letter-spacing: -0.04em;
  line-height: 1.05;
}

.dashboard-title-block p {
  margin: 4px 0 0;
  color: #6980a7;
  font-size: 14px;
}

.dashboard-filters {
  display: grid;
  grid-template-columns: 207px 90px 169px;
  gap: 14px;
  align-items: start;
}

.filter-control {
  height: 39px;
  border: 1px solid #d6e1ef;
  border-radius: 7px;
  background-color: rgba(255, 255, 255, 0.92);
  color: #243c67;
  font-family: inherit;
  font-size: 13px;
  outline: none;
  box-shadow: 0 2px 8px rgba(26, 58, 104, 0.04);
}

.filter-control:focus {
  border-color: var(--sales-blue);
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.12);
}

.date-range-control {
  position: relative;
}

.date-range-button {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  padding: 0 11px;
  cursor: pointer;
}

.date-range-button span {
  flex: 1;
  text-align: left;
  white-space: nowrap;
}

.date-range-popover {
  position: absolute;
  z-index: 20;
  top: 47px;
  right: 0;
  display: grid;
  width: 290px;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  border: 1px solid var(--sales-border);
  border-radius: 10px;
  padding: 13px;
  background: #fff;
  box-shadow: 0 14px 35px rgba(24, 51, 91, 0.16);
}

.date-range-popover label {
  display: grid;
  gap: 5px;
  color: var(--sales-muted);
  font-size: 11px;
  font-weight: 600;
}

.date-range-popover input {
  min-width: 0;
  border: 1px solid var(--sales-border);
  border-radius: 6px;
  padding: 7px;
  color: var(--sales-navy);
  font: inherit;
}

.currency-control,
.compare-control {
  width: 100%;
}

:deep(.dashboard-select-trigger) {
  height: 39px;
  border-color: #d6e1ef;
  border-radius: 7px;
  padding: 0 32px 0 12px;
  background-color: rgba(255, 255, 255, 0.92);
  color: #243c67;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(26, 58, 104, 0.04);
}

:deep(.dashboard-select-trigger--small) {
  height: 30px;
  padding-left: 10px;
}

:deep(.dashboard-select-panel) {
  z-index: 40;
}

.dashboard-error {
  margin: 8px 0;
  border: 1px solid #fecaca;
  border-radius: 7px;
  padding: 8px 12px;
  background: #fff1f2;
  color: #b42318;
  font-size: 13px;
}

.dashboard-card {
  border: 1px solid var(--sales-border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 5px 16px rgba(33, 69, 117, 0.035);
}

.dashboard-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 11px;
  margin-top: 9px;
}

.kpi-card {
  display: flex;
  min-width: 0;
  min-height: 156px;
  gap: 12px;
  padding: 21px 15px;
}

.kpi-icon {
  display: inline-flex;
  width: 41px;
  height: 41px;
  flex: 0 0 41px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: #eaf3ff;
  color: var(--sales-blue);
}

.kpi-content {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  overflow: hidden;
  margin: 0;
  color: #425f92;
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kpi-content strong {
  display: block;
  margin-top: 8px;
  color: #071126;
  font-size: clamp(19px, 1.45vw, 27px);
  font-weight: 750;
  letter-spacing: -0.025em;
  line-height: 1.1;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.kpi-comparison {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  margin: 8px 0 0;
  color: #5672a2;
  font-size: clamp(10px, 0.68vw, 12px);
  white-space: nowrap;
}

.kpi-comparison .positive {
  color: #07965f;
  font-size: clamp(11px, 0.74vw, 13px);
  font-weight: 700;
}

.kpi-comparison .negative {
  color: #dc2626;
  font-size: clamp(11px, 0.74vw, 13px);
  font-weight: 700;
}

.kpi-comparison .neutral {
  color: #7b8daa;
  font-weight: 700;
}

.dashboard-chart-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.42fr) minmax(340px, 1fr);
  gap: 14px;
  margin-top: 13px;
}

.chart-card {
  min-width: 0;
  height: 361px;
  padding: 16px 18px 13px;
}

.card-heading {
  display: flex;
  min-height: 31px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.card-heading h2 {
  min-width: 0;
  margin: 3px 0 0;
  color: #0a1730;
  font-size: 16px;
  font-weight: 720;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-heading {
  align-items: center;
}

.granularity-tabs {
  display: flex;
  align-items: stretch;
  overflow: hidden;
  border: 1px solid #d7e1ef;
  border-radius: 7px;
}

.granularity-tabs button {
  min-width: 77px;
  height: 37px;
  border: 0;
  border-right: 1px solid #e1e8f2;
  background: #fff;
  color: #365689;
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
}

.granularity-tabs button:last-child {
  border-right: 0;
}

.granularity-tabs button.is-selected {
  background: var(--sales-blue);
  color: #fff;
  font-weight: 600;
}

.comparison-period-control {
  width: 116px;
}

.breakdown-period-select {
  width: 106px;
}

.trend-chart-frame,
.comparison-chart-frame {
  height: 296px;
  margin-top: 2px;
}

.dashboard-breakdown-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.71fr) minmax(280px, 0.71fr)
    minmax(340px, 1fr);
  column-gap: 7px;
  margin-top: 12px;
}

.breakdown-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 382px;
  padding: 12px 18px 13px;
}

.world-map {
  display: block;
  width: min(100%, 260px);
  height: 85px;
  margin: 8px auto 8px;
  object-fit: contain;
}

.region-breakdown-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  justify-content: space-between;
  margin-top: 12px;
  margin-bottom: 20px;
}

.rank-list {
  display: grid;
}

.region-list {
  gap: 15px;
  margin-top: 0;
  margin-bottom: 0;
}

.region-list .rank-row {
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: 20px 12px;
  column-gap: 10px;
  row-gap: 4px;
}

.product-list {
  gap: 15px;
  flex: 1;
  align-content: space-between;
  margin-top: 12px;
  margin-bottom: 20px;
  margin-right: -7px;
}

.product-card {
  margin-right: 7px;
}

.rank-row {
  display: grid;
  grid-template-columns: 60px minmax(80px, 1fr) 96px;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.product-list .rank-row {
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: 20px 12px;
  column-gap: 10px;
  row-gap: 4px;
}

.rank-name {
  grid-column: 1;
  grid-row: 1;
  overflow: hidden;
  color: #294c84;
  font-size: 12px;
  white-space: nowrap;
}

.product-rank-name {
  text-overflow: clip;
}

.rank-bar {
  grid-column: 1 / -1;
  grid-row: 2;
  display: block;
  height: 20px;
  overflow: hidden;
  border-radius: 4px;
  background: #e8f0fa;
}

.rank-bar i {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #2a7ff1, #4a98ff);
}

.rank-value {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
}

.rank-value strong {
  display: block;
  width: auto;
  min-width: max-content;
  max-width: none;
  color: #0d2550;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.rank-value small {
  color: #5874a3;
  font-size: 11px;
}

.customer-card {
  display: flex;
  flex-direction: column;
  padding-right: 12px;
  padding-left: 12px;
}

.customer-table-wrap {
  flex: 0 0 auto;
  overflow: hidden;
  margin-top: 12px;
}

.customer-table {
  width: 100%;
  height: 292px;
  border-collapse: collapse;
  table-layout: fixed;
  color: #375987;
  font-size: 12px;
}

.customer-table th,
.customer-table td {
  height: 26px;
  overflow: hidden;
  border-bottom: 1px solid #e3eaf4;
  padding: 0 6px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-table th {
  height: 28px;
  background: #f4f7fb;
  color: #375987;
  font-size: 12px;
  font-weight: 600;
}

.customer-table th:nth-child(1),
.customer-table td:nth-child(1) {
  width: 26px;
}

.customer-table th:nth-child(2),
.customer-table td:nth-child(2) {
  width: 35%;
}

.customer-table th:nth-child(3),
.customer-table td:nth-child(3) {
  width: 18%;
}

.customer-table th:nth-child(4),
.customer-table td:nth-child(4) {
  width: 26%;
  text-align: left;
  font-variant-numeric: tabular-nums;
}

.customer-table th:nth-child(5),
.customer-table td:nth-child(5) {
  width: 15%;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.view-all-link {
  align-self: flex-end;
  margin-top: auto;
  margin-bottom: 20px;
  color: #0876f9;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 1220px) {
  .sales-dashboard-main {
    padding-right: 16px;
    padding-left: 16px;
  }

  .dashboard-topbar {
    flex-direction: column;
  }

  .dashboard-filters {
    width: 100%;
    grid-template-columns: minmax(190px, 1fr) 90px 155px;
  }

  .dashboard-kpi-grid,
  .dashboard-breakdown-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .customer-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 820px) {
  .sales-analytics-shell {
    overflow: auto;
  }

  .sales-dashboard-main {
    overflow: visible;
  }

  .dashboard-filters,
  .dashboard-chart-grid,
  .dashboard-breakdown-grid,
  .dashboard-kpi-grid {
    grid-template-columns: 1fr;
  }

  .customer-card {
    grid-column: auto;
  }
}
</style>
