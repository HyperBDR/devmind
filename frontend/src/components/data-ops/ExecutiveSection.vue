<template>
  <section class="space-y-6">
    <section
      class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]"
    >
      <article
        class="rounded-lg border p-5"
        :class="executiveSeverity.panelClass"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="rounded-full px-2 py-1 text-xs font-bold"
            :class="executiveSeverity.badgeClass"
          >
            {{ executiveSeverity.label }}
          </span>
          <span class="text-sm font-medium text-slate-500">
            {{ t('dataOps.executive.conclusion', { month: currentMonth }) }}
          </span>
        </div>
        <h2 class="mt-4 text-2xl font-bold text-slate-950">
          {{ executiveHeadline }}
        </h2>
        <p class="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          {{ executiveSummary }}
        </p>
      </article>

      <aside class="rounded-lg border border-slate-200 bg-white p-4">
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-base font-bold text-slate-950">
            {{ t('dataOps.executive.todayPriority') }}
          </h3>
          <span class="text-xs font-semibold text-slate-400">
            {{
              t('dataOps.executive.items', {
                count: priorityActionItems.length
              })
            }}
          </span>
        </div>
        <div class="mt-3 space-y-3">
          <button
            v-for="item in priorityActionItems"
            :key="item.key"
            type="button"
            class="block w-full rounded-lg bg-slate-50 p-3 text-left transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            @click="openAction(item, $event)"
          >
            <div class="flex items-center gap-2">
              <span
                class="rounded-full px-2 py-0.5 text-xs font-bold"
                :class="item.priorityClass"
              >
                {{ item.type }}
              </span>
              <span class="truncate text-xs font-medium text-slate-400">
                {{ item.owner }}
              </span>
            </div>
            <p class="mt-2 truncate text-sm font-semibold text-slate-900">
              {{ item.title }}
            </p>
            <p class="mt-1 truncate text-xs text-slate-500">
              {{ item.detail }}
            </p>
          </button>
          <p
            v-if="!priorityActionItems.length"
            class="rounded-lg bg-slate-50 p-4 text-sm text-slate-400"
          >
            {{ t('dataOps.executive.noPriority') }}
          </p>
        </div>
      </aside>
    </section>

    <section class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <article
        v-for="item in coreMetricCards"
        :key="item.label"
        class="rounded-lg border border-slate-200 bg-white p-4"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="text-sm font-medium text-slate-500">{{ item.label }}</div>
          <span
            v-if="item.delta?.badge"
            class="shrink-0 rounded-full px-2 py-1 text-xs font-medium"
            :class="item.delta.className"
          >
            {{ item.delta.text }}
          </span>
        </div>
        <div class="mt-2 text-2xl font-bold text-slate-900">
          {{ item.value }}
        </div>
        <p class="mt-2 text-xs text-slate-400">{{ item.caption }}</p>
      </article>
    </section>

    <nav
      :aria-label="t('dataOps.executive.dashboardGroups')"
      class="sticky top-0 z-10 -mx-4 border-y border-slate-200 bg-slate-50/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border"
    >
      <div
        class="flex gap-2 overflow-x-auto"
        role="tablist"
        :aria-label="t('dataOps.executive.resourceGroups')"
      >
        <button
          v-for="item in cockpitTabs"
          :key="item.key"
          type="button"
          role="tab"
          :aria-selected="item.key === activeTab"
          class="inline-flex h-10 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
          :class="
            item.key === activeTab
              ? 'bg-slate-950 text-white shadow-sm'
              : 'border border-slate-200 bg-white text-slate-600 hover:text-slate-950'
          "
          @click="activeTab = item.key"
        >
          <svg
            aria-hidden="true"
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.8"
            viewBox="0 0 24 24"
          >
            <path :d="item.iconPath" />
          </svg>
          {{ item.label }}
        </button>
      </div>
    </nav>

    <main class="space-y-6">
      <template v-if="activeTab === 'overview'">
      <section
        class="overflow-hidden rounded-lg border border-slate-200 bg-white"
      >
        <div class="border-b border-slate-200 px-5 py-4">
          <h3 class="text-lg font-bold text-slate-950">
            {{ t('dataOps.executive.actionList') }}
          </h3>
          <p class="mt-1 text-sm text-slate-500">
            {{ t('dataOps.executive.actionListDescription') }}
          </p>
        </div>
        <div class="divide-y divide-slate-100">
          <button
            v-for="item in actionItems"
            :key="item.key"
            type="button"
            class="grid w-full gap-4 px-5 py-4 text-left transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-slate-400 lg:grid-cols-[minmax(0,1fr)_160px_180px]"
            @click="openAction(item, $event)"
          >
            <div class="min-w-0">
              <div class="mb-2 flex flex-wrap items-center gap-2">
                <span
                  class="rounded-full px-2 py-0.5 text-xs font-bold"
                  :class="item.priorityClass"
                >
                  {{ item.priority }}
                </span>
                <span class="text-xs font-semibold text-slate-400">
                  {{ item.type }}
                </span>
              </div>
              <h4 class="truncate text-base font-bold text-slate-950">
                {{ item.title }}
              </h4>
              <p class="mt-1 text-sm text-slate-500">{{ item.detail }}</p>
            </div>
            <div>
              <p class="text-xs font-semibold text-slate-400">
                {{ t('dataOps.executive.owner') }}
              </p>
              <p class="mt-1 text-sm font-semibold text-slate-700">
                {{ item.owner }}
              </p>
            </div>
            <div>
              <p class="text-xs font-semibold text-slate-400">
                {{ t('dataOps.executive.timeBasis') }}
              </p>
              <p class="mt-1 text-sm font-semibold text-slate-700">
                {{ item.date }}
              </p>
            </div>
          </button>
          <div
            v-if="!actionItems.length"
            class="px-5 py-10 text-center text-sm text-slate-400"
          >
            {{ t('dataOps.executive.noActions') }}
          </div>
        </div>
      </section>
      </template>

      <section
        v-else-if="activeTab === 'trend'"
        class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <h2 class="mb-4 text-lg font-semibold text-slate-900">
          {{ t('dataOps.executive.trendTitle') }}
        </h2>
        <div
          class="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
        >
          <p class="text-sm text-slate-500">
            {{ t('dataOps.executive.trendDescription') }}
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <div class="inline-flex rounded-lg border border-slate-200 bg-white p-1">
              <button
                v-for="item in trendPeriodOptions"
                :key="item.key"
                type="button"
                class="h-8 rounded-md px-3 text-xs font-medium transition-colors"
                :class="
                  selectedTrendPeriod === item.key
                    ? 'bg-slate-900 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                "
                @click="selectedTrendPeriod = item.key"
              >
                {{ item.label }}
              </button>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in trendRangeOptions"
                :key="item.key"
                type="button"
                class="rounded-full px-3 py-1.5 text-xs font-medium transition-colors"
                :class="
                  selectedTrendRange === item.key
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                "
                @click="selectedTrendRange = item.key"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div
            v-for="item in trendSummaries"
            :key="item.label"
            class="rounded-lg border border-slate-200 bg-white px-3 py-2"
          >
            <div class="text-xs text-slate-500">{{ item.label }}</div>
            <div class="mt-1 flex items-baseline justify-between gap-3">
              <span class="text-sm font-semibold text-slate-900">
                {{ item.period }}
              </span>
              <span
                class="rounded-full px-2 py-1 text-xs font-medium"
                :class="item.deltaClass"
              >
                {{ item.deltaLabel }} {{ item.delta }}
              </span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <TrendPanel
            v-for="item in trendPanelConfigs"
            :key="item.title"
            :chart-data="item.chartData"
            :chart-options="item.chartOptions"
            :description="item.description"
            :title="item.title"
          />
        </div>
      </section>

      <section
        v-else-if="activeTab === 'customer'"
        class="grid grid-cols-1 gap-6 xl:grid-cols-2"
      >
        <RankPanel
          :title="t('dataOps.executive.keyCustomers')"
          :description="t('dataOps.executive.keyCustomersDescription')"
          :items="customerRankItems"
        />
        <RankPanel
          :title="t('dataOps.executive.salesRanking')"
          :description="t('dataOps.executive.salesRankingDescription')"
          :items="salesRankItems"
        />
      </section>

      <section
        v-else-if="activeTab === 'risk'"
        class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div class="flex flex-col gap-4 border-b border-slate-100 pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 class="text-lg font-bold text-slate-950">
              {{ t('dataOps.executive.riskTitle') }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('dataOps.executive.riskDescription') }}
            </p>
          </div>
          <div class="flex gap-3">
            <strong class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {{
                t('dataOps.executive.renewalAlerts', {
                  count: effectiveRenewalItems.length
                })
              }}
            </strong>
            <strong class="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {{
                t('dataOps.executive.largeOutstanding', {
                  count: highOutstandingItems.length
                })
              }}
            </strong>
          </div>
        </div>
        <div class="grid grid-cols-1 gap-6 pt-4 xl:grid-cols-2">
          <SimpleList
            :title="t('dataOps.executive.renewalTop')"
            :items="renewalRiskList"
          />
          <SimpleList
            :title="t('dataOps.executive.outstandingTop')"
            :items="outstandingRiskList"
          />
        </div>
      </section>

      <section
        v-else-if="activeTab === 'opportunity'"
        class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div class="border-b border-slate-100 pb-4">
          <h3 class="text-lg font-bold text-slate-950">
            {{ t('dataOps.executive.opportunityPool') }}
          </h3>
          <p class="mt-1 text-sm text-slate-500">
            {{
              t('dataOps.executive.opportunitySummary', {
                count: opportunityCount,
                amount: formatPlainAmount(
                  opportunitySummary.high_potential_total_amount
                )
              })
            }}
          </p>
        </div>
        <div class="divide-y divide-slate-100">
          <article
            v-for="item in opportunityListItems"
            :key="item.id || item.project_name"
            class="grid gap-3 py-4 lg:grid-cols-[minmax(0,1fr)_160px_80px]"
          >
            <div class="min-w-0">
              <h4 class="truncate text-sm font-bold text-slate-950">
                {{ item.project_name || t('dataOps.executive.unnamedProject') }}
              </h4>
              <p class="mt-1 truncate text-sm text-slate-500">
                {{ item.customer_full_name || '-' }} ·
                {{ ownerLabel(item) || t('dataOps.executive.unassignedOwner') }} ·
                {{ item.domestic_international || '-' }}
              </p>
            </div>
            <strong class="text-sm text-slate-900">
              {{ formatPlainAmount(item.estimated_amount) }}
            </strong>
            <span class="text-sm font-semibold text-amber-600">high</span>
          </article>
        </div>
      </section>

    </main>

    <Teleport to="body">
      <div
        v-if="selectedAction"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"
        @click.self="closeActionDetail"
        @keydown.esc="closeActionDetail"
      >
        <article
          ref="detailDialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="action-detail-title"
          class="w-full max-w-xl rounded-xl bg-white shadow-xl outline-none"
          tabindex="-1"
        >
          <header
            class="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4"
          >
            <div class="min-w-0">
              <div class="mb-2 flex flex-wrap items-center gap-2">
                <span
                  class="rounded-full px-2 py-0.5 text-xs font-bold"
                  :class="selectedAction.priorityClass"
                >
                  {{ selectedAction.priority }}
                </span>
                <span class="text-xs font-semibold text-slate-500">
                  {{ selectedAction.type }}
                </span>
              </div>
              <h3
                id="action-detail-title"
                class="text-lg font-bold text-slate-950"
              >
                {{ selectedAction.title }}
              </h3>
            </div>
            <button
              type="button"
              :aria-label="t('dataOps.executive.closeDetails')"
              class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400"
              @click="closeActionDetail"
            >
              <svg
                aria-hidden="true"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-width="1.8"
                viewBox="0 0 24 24"
              >
                <path d="m6 6 12 12M18 6 6 18" />
              </svg>
            </button>
          </header>

          <div class="space-y-5 px-5 py-5">
            <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div
                v-for="row in selectedAction.details"
                :key="row.label"
                class="rounded-lg bg-slate-50 px-3 py-2.5"
              >
                <dt class="text-xs font-semibold text-slate-400">
                  {{ row.label }}
                </dt>
                <dd class="mt-1 break-words text-sm font-semibold text-slate-800">
                  {{ row.value || '—' }}
                </dd>
              </div>
            </dl>
            <div class="rounded-lg border border-slate-200 px-4 py-3">
              <p class="text-xs font-semibold text-slate-400">
                {{ t('dataOps.executive.recommendedAction') }}
              </p>
              <p class="mt-1 text-sm leading-6 text-slate-700">
                {{ selectedAction.nextAction }}
              </p>
            </div>
          </div>
        </article>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, h, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart } from 'vue-chartjs'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'

import {
  formatAmountByCurrency,
  hasMixedCurrencies,
  hasNonZeroAmount,
  topAmountsByCurrency,
} from '@/utils/currency'

const { locale, t } = useI18n()

ChartJS.register(
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
)

const props = defineProps({
  insights: { type: Object, default: null },
  kpiCards: { type: Array, default: () => [] },
  opportunities: { type: Object, default: null },
  overview: { type: Object, default: null },
  risks: { type: Object, default: null },
  summary: { type: Object, default: null },
  topCustomers: { type: Object, default: null },
  topSales: { type: Object, default: null },
})

const activeTab = ref('overview')
const detailDialog = ref(null)
const selectedAction = ref(null)
const selectedTrendPeriod = ref('month')
const selectedTrendRange = ref('6')
let actionTrigger = null

const towerChartColors = {
  amber: '#f59e0b',
  blue: '#2563eb',
  grid: '#f1f5f9',
  purple: '#8a4cfc',
  tick: '#94a3b8',
}

const trendPeriodOptions = computed(() => [
  { key: 'month', label: t('dataOps.executive.period.month') },
  { key: 'quarter', label: t('dataOps.executive.period.quarter') },
  { key: 'year', label: t('dataOps.executive.period.year') }
])

const trendRangeOptions = computed(() => [
  { key: '3', label: t('dataOps.executive.period.last3') },
  { key: '6', label: t('dataOps.executive.period.last6') },
  { key: '12', label: t('dataOps.executive.period.last12') },
  { key: 'ytd', label: t('dataOps.executive.period.ytd') }
])

const cockpitTabs = computed(() => [
  {
    key: 'overview',
    label: t('dataOps.executive.tabs.overview'),
    iconPath: 'M4 6h16v12H4z M8 10h8 M8 14h5',
    active: true,
  },
  {
    key: 'trend',
    label: t('dataOps.executive.tabs.trend'),
    iconPath: 'M5 17l4-5 4 3 6-8 M5 7v10h14',
    active: false,
  },
  {
    key: 'customer',
    label: t('dataOps.executive.tabs.customer'),
    iconPath: 'M7 19v-1a4 4 0 014-4h2a4 4 0 014 4v1 M12 11a4 4 0 100-8 4 4 0 000 8z',
    active: false,
  },
  {
    key: 'risk',
    label: t('dataOps.executive.tabs.risk'),
    iconPath: 'M12 3l7 4v5c0 5-3 8-7 9-4-1-7-4-7-9V7l7-4z M12 9v4 M12 16h.01',
    active: false,
  },
  {
    key: 'opportunity',
    label: t('dataOps.executive.tabs.opportunity'),
    iconPath: 'M4 16l5-5 4 4 7-8 M4 20h16',
    active: false,
  },
])

const currentMonth = computed(
  () => props.overview?.meta?.current_month || new Date().toISOString().slice(0, 7)
)

const overviewKpis = computed(() => props.overview?.kpis || {})
const highOutstandingItems = computed(
  () => props.risks?.high_outstanding_items || []
)
const renewalAlerts = computed(() => props.risks?.renewal_alerts || [])
const opportunityItems = computed(() => props.opportunities?.items || [])
const opportunitySummary = computed(() => props.opportunities?.summary || {})
const renewalWindowItems = computed(() =>
  (props.insights?.upcoming_renewals || [])
    .filter((item) => item.days_left >= 0 && item.days_left <= 90)
    .sort((left, right) => left.days_left - right.days_left)
)
const effectiveRenewalItems = computed(() =>
  renewalWindowItems.value.length ? renewalWindowItems.value : renewalAlerts.value
)
const renewalHorizonDays = computed(() =>
  renewalWindowItems.value.length ? 90 : 30
)
const signedMoM = computed(() =>
  buildMonthOverMonth(
    props.insights?.monthly_signings || [],
    'amount',
    currentMonth.value
  )
)
const receivedMoM = computed(() =>
  buildMonthOverMonth(
    props.insights?.monthly_payment_trend || [],
    'payment_received',
    currentMonth.value
  )
)

const signedMetric = computed(() =>
  metricFromCurrency(
    overviewKpis.value.monthly_signed_amount,
    overviewKpis.value.monthly_signed_amount_by_currency,
    { fallbackZero: true }
  )
)

const receivedMetric = computed(() =>
  metricFromCurrency(
    overviewKpis.value.monthly_received_amount,
    overviewKpis.value.monthly_received_amount_by_currency,
    { fallbackZero: true }
  )
)

const outstandingMetric = computed(() =>
  metricFromCurrency(
    overviewKpis.value.monthly_outstanding_amount,
    overviewKpis.value.monthly_outstanding_amount_by_currency,
    { fallbackZero: true }
  )
)

const coreMetricCards = computed(() => [
  {
    label: t('dataOps.executive.metrics.monthlySigned'),
    value: signedMetric.value.value,
    delta: signedMoM.value,
    caption: signedMoM.value.badge
      ? signedMoM.value.text
      : t('dataOps.executive.metrics.noComparison'),
  },
  {
    label: t('dataOps.executive.metrics.monthlyReceived'),
    value: receivedMetric.value.value,
    delta: receivedMoM.value,
    caption: receivedMoM.value.badge
      ? receivedMoM.value.text
      : t('dataOps.executive.metrics.noComparison'),
  },
  {
    label: t('dataOps.executive.metrics.outstandingBalance'),
    value: outstandingMetric.value.value,
    delta: neutralDelta(),
    caption: t('dataOps.executive.metrics.fullBalance'),
  },
])

const executiveSeverity = computed(() => {
  const hasReceived = hasNonZeroAmount(
    overviewKpis.value.monthly_received_amount,
    overviewKpis.value.monthly_received_amount_by_currency
  )
  const hasOutstanding = hasNonZeroAmount(
    overviewKpis.value.monthly_outstanding_amount,
    overviewKpis.value.monthly_outstanding_amount_by_currency
  )
  if (!hasReceived && hasOutstanding) {
    return {
      label: t('dataOps.executive.severity.high'),
      panelClass: 'border-rose-200 bg-rose-50',
      badgeClass: 'bg-rose-100 text-rose-700',
    }
  }
  if (highOutstandingItems.value.length || effectiveRenewalItems.value.length) {
    return {
      label: t('dataOps.executive.severity.attention'),
      panelClass: 'border-amber-200 bg-amber-50',
      badgeClass: 'bg-amber-100 text-amber-700',
    }
  }
  return {
    label: t('dataOps.executive.severity.normal'),
    panelClass: 'border-emerald-200 bg-emerald-50',
    badgeClass: 'bg-emerald-100 text-emerald-700',
  }
})

const executiveHeadline = computed(() => {
  const hasReceived = hasNonZeroAmount(
    overviewKpis.value.monthly_received_amount,
    overviewKpis.value.monthly_received_amount_by_currency
  )
  const hasOutstanding = hasNonZeroAmount(
    overviewKpis.value.monthly_outstanding_amount,
    overviewKpis.value.monthly_outstanding_amount_by_currency
  )
  if (!hasReceived && hasOutstanding) {
    return t('dataOps.executive.headline.stalled')
  }
  if (highOutstandingItems.value.length) {
    return t('dataOps.executive.headline.outstanding')
  }
  if (effectiveRenewalItems.value.length) {
    return t('dataOps.executive.headline.renewal')
  }
  return t('dataOps.executive.headline.normal')
})

const executiveSummary = computed(() => {
  const parts = [
    t('dataOps.executive.summary.signed', {
      value: signedMetric.value.shortValue
    }),
    t('dataOps.executive.summary.received', {
      value: receivedMetric.value.shortValue
    }),
    t('dataOps.executive.summary.outstanding', {
      value: outstandingMetric.value.shortValue
    }),
  ]
  const actionHints = []
  if (highOutstandingItems.value.length) {
    actionHints.push(
      t('dataOps.executive.summary.largeOutstanding', {
        count: highOutstandingItems.value.length
      })
    )
  }
  if (effectiveRenewalItems.value.length) {
    actionHints.push(
      t('dataOps.executive.summary.renewal', {
        days: renewalHorizonDays.value,
        count: effectiveRenewalItems.value.length
      })
    )
  }
  if (opportunityCount.value) {
    actionHints.push(
      t('dataOps.executive.summary.opportunities', {
        count: opportunityCount.value
      })
    )
  }
  return `${parts.join(', ')}. ${
    actionHints.join(', ') || t('dataOps.executive.summary.none')
  }.`
})

const trendSummaries = computed(() => [
  latestTrendSummary(
    t('dataOps.executive.trend.latestSigned'),
    props.insights?.monthly_signings || [],
    'amount'
  ),
  latestTrendSummary(
    t('dataOps.executive.trend.latestReceived'),
    props.insights?.monthly_payment_trend || [],
    'payment_received'
  ),
  latestNetTrendSummary(),
])

const signedTrendRows = computed(() =>
  buildTrendRows(props.insights?.monthly_signings || [], 'amount')
)

const receivedTrendRows = computed(() =>
  buildTrendRows(
    props.insights?.monthly_payment_trend || [],
    'payment_received'
  )
)

const netTrendRows = computed(() =>
  buildNetTrendRows(props.insights?.monthly_net_trend || [])
)

const trendPanelConfigs = computed(() => [
  {
    title: t('dataOps.executive.trend.signedTitle'),
    description: t('dataOps.executive.trend.signedDescription'),
    chartData: buildTrendChartData(
      signedTrendRows.value,
      t('dataOps.executive.trend.signedAmount'),
      towerChartColors.purple
    ),
    chartOptions: buildTrendChartOptions(),
  },
  {
    title: t('dataOps.executive.trend.cashTitle'),
    description: t('dataOps.executive.trend.cashDescription'),
    chartData: buildTrendChartData(
      receivedTrendRows.value,
      t('dataOps.executive.trend.receivedAmount'),
      towerChartColors.blue
    ),
    chartOptions: buildTrendChartOptions(),
  },
  {
    title: t('dataOps.executive.trend.netTitle'),
    description: t('dataOps.executive.trend.netDescription'),
    chartData: buildTrendChartData(
      netTrendRows.value,
      t('dataOps.executive.trend.netAmount'),
      towerChartColors.amber
    ),
    chartOptions: buildTrendChartOptions(),
  },
])

const customerRankItems = computed(() =>
  topAmountsByCurrency(
    (props.topCustomers?.top_received || []).filter(
      (item) => Number(item.received_amount || 0) > 0
    ),
    'received_amount',
    10
  )
    .map((item) => ({
      title: `${
        item.customer_name || t('dataOps.executive.unknownCustomer')
      } · ${ownerLabel(item) || t('dataOps.executive.unassignedOwner')}`,
      meta: t('dataOps.executive.customerMeta', {
        contracts: item.contract_count || 0,
        outstanding: formatAmountByCurrency(
          null,
          [{ amount: item.outstanding_amount, currency: item.currency }],
          { locale: locale.value }
        )
      }),
      value: formatAmountByCurrency(
        null,
        [{ amount: item.received_amount, currency: item.currency }],
        { locale: locale.value }
      ),
      status: t('dataOps.executive.riskLevel', {
        level: item.risk_level || 'low'
      }),
    }))
)

const salesRankItems = computed(() =>
  topAmountsByCurrency(
    (props.topSales?.top_received || []).filter(
      (item) => Number(item.received_amount || 0) > 0
    ),
    'received_amount',
    10
  )
    .map((item) => ({
      title: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
      meta: t('dataOps.executive.salesMeta', {
        customers: item.customer_count || 0,
        opportunities: item.high_potential_count || 0
      }),
      value: formatAmountByCurrency(
        null,
        [{ amount: item.received_amount, currency: item.currency }],
        { locale: locale.value }
      ),
      status: t('dataOps.executive.salesOutstanding', {
        amount: formatAmountByCurrency(
          null,
          [{ amount: item.outstanding_amount, currency: item.currency }],
          { locale: locale.value }
        )
      }),
    }))
)

const renewalRiskList = computed(() =>
  effectiveRenewalItems.value.slice(0, 8).map((item) => ({
    title: item.customer_name || t('dataOps.executive.unknownCustomer'),
    value: t('dataOps.executive.days', { count: item.days_left }),
    meta: item.contract_number || item.service_end || '-',
  }))
)

const outstandingRiskList = computed(() =>
  highOutstandingItems.value.slice(0, 8).map((item) => ({
    title:
      item.customer_name ||
      item.project_name ||
      t('dataOps.executive.unknownCustomer'),
    value: formatPlainAmount(item.outstanding_amount),
    meta: item.project_name || ownerLabel(item) || '-',
  }))
)

const opportunityListItems = computed(() => opportunityItems.value.slice(0, 10))

const opportunityCount = computed(
  () =>
    opportunitySummary.value.high_potential_count ||
    opportunityItems.value.length ||
    0
)

const actionItems = computed(() => [
  ...highOutstandingItems.value.slice(0, 3).map((item, index) => ({
    key: `cash-${index}-${item.customer_name}`,
    priority: t('dataOps.executive.priority.high'),
    priorityClass: 'bg-rose-100 text-rose-600',
    type: t('dataOps.executive.type.cash'),
    title: t('dataOps.executive.actions.cashTitle', {
      name:
        item.customer_name ||
        item.project_name ||
        t('dataOps.executive.fields.customer')
    }),
    detail: t('dataOps.executive.actions.cashDetail', {
      amount: formatCompact(item.outstanding_amount)
    }),
    owner: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
    date:
      item.expected_payment_date ||
      t('dataOps.executive.confirmPaymentDate'),
    details: [
      {
        label: t('dataOps.executive.fields.customer'),
        value: item.customer_name || '—'
      },
      {
        label: t('dataOps.executive.fields.project'),
        value: item.project_name || '—'
      },
      {
        label: t('dataOps.executive.fields.outstanding'),
        value: formatCompact(item.outstanding_amount),
      },
      {
        label: t('dataOps.executive.owner'),
        value: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
      },
      {
        label: t('dataOps.executive.fields.expectedPayment'),
        value:
          item.expected_payment_date ||
          t('dataOps.executive.pendingConfirmation'),
      },
    ],
    nextAction: t('dataOps.executive.actions.cashNext'),
  })),
  ...renewalAlerts.value.slice(0, 2).map((item, index) => ({
    key: `renewal-${index}-${item.contract_number}`,
    priority: t('dataOps.executive.priority.medium'),
    priorityClass: 'bg-amber-100 text-amber-600',
    type: t('dataOps.executive.type.renewal'),
    title: t('dataOps.executive.actions.renewalTitle', {
      name: item.customer_name || t('dataOps.executive.fields.customer')
    }),
    detail: t('dataOps.executive.actions.renewalDetail', {
      contract: item.contract_number || '-',
      days: item.days_left
    }),
    owner: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
    date: item.service_end || t('dataOps.executive.confirmExpiryDate'),
    details: [
      {
        label: t('dataOps.executive.fields.customer'),
        value: item.customer_name || '—'
      },
      {
        label: t('dataOps.executive.fields.contractNumber'),
        value: item.contract_number || '—'
      },
      {
        label: t('dataOps.executive.fields.remainingDays'),
        value: t('dataOps.executive.days', { count: item.days_left ?? '—' })
      },
      {
        label: t('dataOps.executive.owner'),
        value: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
      },
      {
        label: t('dataOps.executive.fields.serviceEnd'),
        value: item.service_end || t('dataOps.executive.pendingConfirmation')
      },
    ],
    nextAction: t('dataOps.executive.actions.renewalNext'),
  })),
  ...opportunityItems.value.slice(0, 1).map((item, index) => ({
    key: `opportunity-${index}-${item.id}`,
    priority: t('dataOps.executive.priority.medium'),
    priorityClass: 'bg-amber-100 text-amber-600',
    type: t('dataOps.executive.type.growth'),
    title: t('dataOps.executive.actions.growthTitle', {
      name: item.project_name || t('dataOps.executive.fields.project')
    }),
    detail: t('dataOps.executive.actions.growthDetail', {
      amount: formatCompact(item.estimated_amount)
    }),
    owner: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
    date: item.oa_initiation_date || t('dataOps.executive.confirmActivity'),
    details: [
      {
        label: t('dataOps.executive.fields.project'),
        value: item.project_name || '—'
      },
      {
        label: t('dataOps.executive.fields.customer'),
        value: item.customer_full_name || '—'
      },
      {
        label: t('dataOps.executive.fields.estimatedAmount'),
        value: formatCompact(item.estimated_amount),
      },
      {
        label: t('dataOps.executive.owner'),
        value: ownerLabel(item) || t('dataOps.executive.unassignedOwner'),
      },
      {
        label: t('dataOps.executive.fields.initiationDate'),
        value:
          item.oa_initiation_date ||
          t('dataOps.executive.pendingConfirmation'),
      },
    ],
    nextAction: t('dataOps.executive.actions.growthNext'),
  })),
])

const priorityActionItems = computed(() => actionItems.value.slice(0, 3))

function openAction(item, event) {
  actionTrigger = event?.currentTarget || null
  selectedAction.value = item
  nextTick(() => detailDialog.value?.focus())
}

function closeActionDetail() {
  selectedAction.value = null
  nextTick(() => actionTrigger?.focus())
}

function metricFromCurrency(value, items, options = {}) {
  const fallbackValue =
    value ?? (options.fallbackZero ? 0 : null)
  if (!items?.length && fallbackValue === null) {
    return { value: '—', shortValue: '—' }
  }
  const displayValue = formatAmountByCurrency(fallbackValue, items, {
    compact: true,
    fallbackCurrency: 'CNY',
    locale: locale.value,
  })
  return {
    value: displayValue,
    shortValue: displayValue,
  }
}

function ownerLabel(item) {
  if (!item) return ''
  return (
    item.owner_display ||
    item.owner_canonical ||
    item.sales_person ||
    ''
  )
}
function formatCompact(value) {
  const amount = Number(value || 0)
  const absAmount = Math.abs(amount)
  if (absAmount >= 100000000) {
    return t('dataOps.executive.unit.hundredMillion', {
      value: formatScaled(amount / 100000000)
    })
  }
  if (absAmount >= 10000) {
    return t('dataOps.executive.unit.tenThousand', {
      value: formatScaled(amount / 10000)
    })
  }
  return trimNumber(amount)
}

function formatScaled(value) {
  return Number(value).toFixed(1)
}

function trimNumber(value) {
  return new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 1,
  }).format(value)
}

function neutralDelta() {
  return { text: '—', badge: false, className: 'text-slate-400' }
}

function buildMonthOverMonth(items, valueKey, month) {
  const totals = groupMonthlyTotals(items, valueKey)
  const current = totals.get(month) || 0
  const previous = totals.get(previousMonth(month)) || 0
  if (!previous) {
    return neutralDelta()
  }
  const ratio = ((current - previous) / previous) * 100
  const deltaText = `${Math.abs(ratio).toFixed(2)}%`
  if (ratio < 0) {
    return {
      text: t('dataOps.executive.trend.down', { value: deltaText }),
      badge: true,
      className: 'text-rose-600 bg-rose-50',
    }
  }
  if (ratio > 0) {
    return {
      text: t('dataOps.executive.trend.up', { value: deltaText }),
      badge: true,
      className: 'text-emerald-600 bg-emerald-50',
    }
  }
  return neutralDelta()
}

function groupMonthlyTotals(items, valueKey) {
  const totals = new Map()
  if (hasMixedCurrencies(items)) return totals
  for (const item of items) {
    const month = item.month
    if (!month) continue
    totals.set(month, (totals.get(month) || 0) + Number(item[valueKey] || 0))
  }
  return totals
}

function previousMonth(month) {
  const [year, monthIndex] = String(month).split('-').map(Number)
  if (!year || !monthIndex) return ''
  const date = new Date(year, monthIndex - 2, 1)
  const nextYear = date.getFullYear()
  const nextMonth = String(date.getMonth() + 1).padStart(2, '0')
  return `${nextYear}-${nextMonth}`
}

function latestTrendSummary(label, items, valueKey) {
  const rows = buildTrendRows(items, valueKey)
  const currentRow = rows[rows.length - 1]
  const delta = currentRow?.delta ?? null
  return {
    label,
    period: currentRow?.label || '—',
    delta: formatTrendDelta(delta),
    deltaClass: trendDeltaClass(delta),
    deltaLabel:
      selectedTrendPeriod.value === 'year'
        ? t('dataOps.executive.trend.yoy')
        : t('dataOps.executive.trend.mom'),
  }
}

function latestNetTrendSummary() {
  const rows = buildNetTrendSource(props.insights?.monthly_net_trend || [])
  return latestTrendSummary(
    t('dataOps.executive.trend.latestNet'),
    rows,
    'amount'
  )
}

function buildTrendRows(items, valueKey) {
  if (hasMixedCurrencies(items)) return []
  const totals = new Map()
  for (const item of items) {
    const period = periodBucket(item.month)
    if (!period) continue
    const row = totals.get(period.key) || {
      amount: 0,
      label: period.label,
      sortKey: period.sortKey,
      year: period.year,
    }
    row.amount += Number(item[valueKey] || 0)
    totals.set(period.key, row)
  }
  const rows = [...totals.values()].sort((left, right) =>
    left.sortKey.localeCompare(right.sortKey)
  )
  const rowsWithDelta = rows.map((item, index) => {
    const previous = rows[index - 1]?.amount || 0
    return {
      ...item,
      delta: previous ? ((item.amount - previous) / previous) * 100 : null,
    }
  })
  return filterTrendRows(rowsWithDelta)
}

function buildNetTrendRows(items) {
  return buildTrendRows(buildNetTrendSource(items), 'amount')
}

function buildNetTrendSource(items) {
  return items.map((item) => ({
    amount: Number(item.amount || 0),
    currency: item.currency,
    month: item.month,
  }))
}

function periodBucket(month) {
  const [year, monthIndex] = String(month || '').split('-').map(Number)
  if (!year || !monthIndex) return null
  if (selectedTrendPeriod.value === 'year') {
    return {
      key: String(year),
      label: String(year),
      sortKey: String(year),
      year,
    }
  }
  if (selectedTrendPeriod.value === 'quarter') {
    const quarter = Math.floor((monthIndex - 1) / 3) + 1
    return {
      key: `${year}-Q${quarter}`,
      label: `${year} Q${quarter}`,
      sortKey: `${year}-${String(quarter).padStart(2, '0')}`,
      year,
    }
  }
  return {
    key: `${year}-${String(monthIndex).padStart(2, '0')}`,
    label: `${year}-${String(monthIndex).padStart(2, '0')}`,
    sortKey: `${year}-${String(monthIndex).padStart(2, '0')}`,
    year,
  }
}

function filterTrendRows(rows) {
  if (selectedTrendRange.value === 'ytd') {
    const currentYear = Number(String(currentMonth.value).slice(0, 4))
    const latestYear = rows[rows.length - 1]?.year
    const year = currentYear || latestYear
    return rows.filter((item) => item.year === year)
  }
  const limit = Number(selectedTrendRange.value || 6)
  return rows.slice(-limit)
}

function buildTrendChartData(rows, barLabel, barColor) {
  return {
    labels: rows.map((item) => item.label),
    datasets: [
      {
        type: 'line',
        label: t('dataOps.executive.trend.momGrowth'),
        data: rows.map((item) => item.delta),
        borderColor: towerChartColors.amber,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointBackgroundColor: towerChartColors.amber,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointRadius: 3,
        tension: 0.3,
        yAxisID: 'y1',
      },
      {
        type: 'bar',
        label: barLabel,
        data: rows.map((item) => item.amount),
        backgroundColor: barColor,
        borderRadius: 4,
        borderSkipped: false,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
        yAxisID: 'y',
      },
    ],
  }
}

function buildTrendChartOptions() {
  return {
    maintainAspectRatio: false,
    responsive: true,
    interaction: {
      intersect: false,
      mode: 'index',
    },
    plugins: {
      legend: {
        labels: {
          boxWidth: 14,
          color: '#64748b',
          font: {
            size: 11,
            weight: 600,
          },
          usePointStyle: true,
        },
        position: 'bottom',
      },
      tooltip: {
        backgroundColor: 'white',
        bodyColor: '#64748b',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        cornerRadius: 12,
        padding: 10,
        titleColor: '#0f172a',
        titleFont: {
          weight: 600,
        },
      },
    },
    scales: {
      x: {
        border: {
          display: false,
        },
        grid: {
          display: false,
        },
        ticks: {
          color: towerChartColors.tick,
          font: {
            size: 10,
            weight: 600,
          },
          maxRotation: 0,
        },
      },
      y: {
        border: {
          display: false,
        },
        grid: {
          color: towerChartColors.grid,
        },
        ticks: {
          callback: (value) => formatCompact(value),
          color: towerChartColors.tick,
          font: {
            size: 10,
          },
        },
      },
      y1: {
        border: {
          display: false,
        },
        grid: {
          display: false,
        },
        position: 'right',
        ticks: {
          callback: (value) => `${trimNumber(value)}%`,
          color: towerChartColors.tick,
          font: {
            size: 10,
          },
        },
      },
    },
  }
}

function formatTrendDelta(value) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}%`
}

function trendDeltaClass(value) {
  if (value === null || value === undefined) {
    return 'bg-slate-100 text-slate-500'
  }
  if (value < 0) return 'bg-rose-50 text-rose-700'
  if (value > 0) return 'bg-emerald-50 text-emerald-700'
  return 'bg-slate-100 text-slate-500'
}

function formatPlainAmount(value) {
  const amount = Number(value || 0)
  return new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 2,
  }).format(amount)
}

const TrendPanel = {
  props: {
    chartData: { type: Object, required: true },
    chartOptions: { type: Object, required: true },
    description: { type: String, required: true },
    title: { type: String, required: true },
  },
  setup(panelProps) {
    return () =>
      h('section', { class: 'rounded-xl bg-slate-50 p-4' }, [
        h('h4', { class: 'mb-1 text-sm font-medium text-slate-700' }, panelProps.title),
        h('p', { class: 'mb-3 text-xs text-slate-500' }, panelProps.description),
        h('div', { class: 'h-[300px]' }, [
          h(Chart, {
            data: panelProps.chartData,
            options: panelProps.chartOptions,
            type: 'bar',
          }),
        ]),
      ])
  },
}

const RankPanel = {
  props: {
    description: { type: String, required: true },
    items: { type: Array, default: () => [] },
    title: { type: String, required: true },
  },
  setup(panelProps) {
    return () =>
      h('section', { class: 'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm' }, [
        h('h3', { class: 'text-lg font-bold text-slate-950' }, panelProps.title),
        h('p', { class: 'mt-1 text-sm text-slate-500' }, panelProps.description),
        h(
          'div',
          { class: 'mt-4 divide-y divide-slate-100' },
          panelProps.items.map((item) =>
            h('article', { class: 'grid grid-cols-[minmax(0,1fr)_9rem] gap-4 py-3' }, [
              h('div', { class: 'min-w-0' }, [
                h('h4', { class: 'truncate text-sm font-bold text-slate-950' }, item.title),
                h('p', { class: 'mt-1 truncate text-xs text-slate-500' }, item.meta),
                h('p', { class: 'mt-1 text-xs text-slate-400' }, item.status),
              ]),
              h('strong', { class: 'text-right text-sm text-slate-900' }, item.value),
            ])
          )
        ),
      ])
  },
}

const SimpleList = {
  props: {
    items: { type: Array, default: () => [] },
    title: { type: String, required: true },
  },
  setup(listProps) {
    return () =>
      h('section', { class: 'rounded-lg border border-slate-200 p-4' }, [
        h('h4', { class: 'text-sm font-bold text-slate-950' }, listProps.title),
        h(
          'div',
          { class: 'mt-4 space-y-3' },
          listProps.items.map((item) =>
            h('div', { class: 'flex items-start justify-between gap-4 text-sm' }, [
              h('div', { class: 'min-w-0' }, [
                h('p', { class: 'truncate font-semibold text-slate-900' }, item.title),
                h('p', { class: 'mt-1 truncate text-xs text-slate-500' }, item.meta),
              ]),
              h('strong', { class: 'shrink-0 text-slate-700' }, item.value),
            ])
          )
        ),
      ])
  },
}

</script>
