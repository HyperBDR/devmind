<template>
  <section class="space-y-6">
    <header
      class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
    >
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-slate-900">
          {{ t('dataOps.pipeline.title') }}
        </h2>
        <p class="mt-1 text-sm text-slate-500">
          {{
            t('dataOps.pipeline.subtitle', {
              count: filteredProjects.length
            })
          }}
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <label
          class="flex shrink-0 cursor-pointer select-none items-center gap-2"
        >
          <span class="text-xs font-bold text-slate-500">
            {{ t('dataOps.pipeline.includeLanded') }}
          </span>
          <input v-model="includeLanded" class="peer sr-only" type="checkbox" />
          <span
            class="relative h-5 w-10 rounded-full transition"
            :class="includeLanded ? 'bg-indigo-600' : 'bg-slate-200'"
          >
            <span
              class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition"
              :class="includeLanded ? 'translate-x-5' : 'translate-x-0.5'"
            />
          </span>
        </label>

        <div class="h-5 w-px bg-slate-200" />

        <div class="flex rounded-xl border border-slate-200 bg-white p-1">
          <button
            v-for="item in scopeTabs"
            :key="item.key"
            class="rounded-lg px-4 py-1.5 text-xs font-bold transition"
            :class="
              activeScope === item.key
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            "
            type="button"
            @click="activeScope = item.key"
          >
            {{ item.label }} {{ item.count }}
          </button>
        </div>
      </div>
    </header>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="item in metricCards"
        :key="item.label"
        class="relative flex min-h-[8.75rem] flex-col justify-between overflow-hidden rounded-xl border border-slate-100 bg-white p-5 shadow-sm"
        :style="{ '--metric-accent': item.accent }"
      >
        <div class="metric-card-accent" />
        <div class="relative flex items-start justify-between">
          <div
            class="metric-card-icon flex h-9 w-9 items-center justify-center rounded-lg bg-slate-50 text-sm font-bold"
          >
            {{ item.icon }}
          </div>
          <span v-if="item.delta" class="text-xs font-bold text-emerald-600">
            ↗ {{ item.delta }}
          </span>
        </div>
        <div class="relative">
          <p class="text-xs font-semibold text-slate-500">{{ item.label }}</p>
          <p class="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            {{ item.value }}
          </p>
          <p class="mt-1 text-[11px] text-slate-400">{{ item.caption }}</p>
        </div>
      </article>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <section class="dashboard-card lg:col-span-2">
        <PanelTitle icon="D" :title="t('dataOps.pipeline.distribution')" />
        <div class="mt-5 space-y-4">
          <MetricBar
            v-for="item in scopeDistribution"
            :key="item.label"
            :item="item"
          />
        </div>
      </section>

      <section class="dashboard-card">
        <PanelTitle icon="S" :title="t('dataOps.pipeline.contractStatus')" />
        <div class="mt-5 space-y-4">
          <MetricBar
            v-for="item in statusDistribution"
            :key="item.label"
            :item="item"
          />
        </div>
      </section>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <section class="dashboard-card">
        <PanelTitle icon="F" :title="t('dataOps.pipeline.funnel')" />
        <div class="mt-5 space-y-4">
          <div v-for="item in funnelItems" :key="item.label" class="space-y-2">
            <div class="flex justify-between text-xs">
              <span class="font-bold text-slate-600">{{ item.label }}</span>
              <span class="font-bold text-slate-400">{{ item.value }}</span>
            </div>
            <div class="h-3 overflow-hidden rounded-full bg-slate-100">
              <div
                class="h-full rounded-full"
                :style="{
                  backgroundColor: item.color,
                  width: `${item.percent}%`
                }"
              />
            </div>
          </div>
        </div>
        <div class="mt-5 rounded-lg bg-indigo-50 p-3 text-center">
          <p class="text-xs font-bold text-indigo-600">
            {{ t('dataOps.pipeline.conversionRate') }}
          </p>
          <p class="mt-1 text-lg font-black text-indigo-800">
            {{ conversionRate }}%
          </p>
        </div>
      </section>
      <section class="dashboard-card lg:col-span-2">
        <PanelTitle icon="P" :title="t('dataOps.pipeline.contribution')" />
        <div class="mt-5 max-h-72 overflow-y-auto pr-1">
          <div class="space-y-4">
            <div
              v-for="item in ownerContribution"
              :key="item.owner"
              class="flex items-center gap-3"
            >
              <div
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold text-white"
                :style="{ backgroundColor: item.color }"
              >
                {{ ownerInitial(item.owner) }}
              </div>
              <div class="min-w-0 flex-1">
                <div class="mb-1 flex justify-between gap-2">
                  <span class="truncate text-xs font-bold text-slate-700">
                    {{ item.owner }}
                  </span>
                  <span class="shrink-0 text-[11px] font-bold text-slate-500">
                    {{ t('dataOps.pipeline.projectsCount', { count: item.count }) }} ·
                    {{ currencyCountLabel(item.amountByCurrency) }}
                  </span>
                </div>
                <div class="h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    class="h-full rounded-full"
                    :style="{
                      backgroundColor: item.color,
                      width: `${item.percent}%`
                    }"
                  />
                </div>
              </div>
            </div>
            <EmptyBlock v-if="!ownerContribution.length" />
          </div>
        </div>
      </section>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <section class="dashboard-card">
        <PanelTitle icon="A" :title="t('dataOps.pipeline.settlementTrend')" />
        <div class="mt-5 h-52">
          <TrendBars color="#6366f1" :items="settlementTrend" />
        </div>
        <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div
            v-for="item in settlementTrend.slice(-3)"
            :key="item.label"
            class="rounded-lg bg-slate-50 p-2 text-center"
          >
            <p class="font-mono text-[10px] text-slate-400">
              {{ item.label }}
            </p>
            <p class="text-sm font-bold text-slate-800">
              {{
                formatCurrencyBuckets([
                  { amount: item.value, currency: item.currency }
                ])
              }}
            </p>
            <p class="text-[9px] text-emerald-500">
              {{ t('dataOps.pipeline.received') }}
              {{
                formatCurrencyBuckets([
                  { amount: item.received, currency: item.currency }
                ])
              }}
            </p>
          </div>
        </div>
      </section>

      <section class="dashboard-card">
        <PanelTitle icon="T" :title="t('dataOps.pipeline.signingTrend')" />
        <div class="mt-5 h-52">
          <TrendBars color="#10b981" :items="monthlyTrend" />
        </div>
        <div
          class="mt-3 flex items-center justify-between rounded-xl border border-amber-100 bg-amber-50 p-3"
        >
          <div>
            <p class="text-xs font-bold text-amber-800">
              {{ t('dataOps.pipeline.renewalAlert') }}
            </p>
            <p class="mt-0.5 text-[11px] text-amber-600">
              {{
                t('dataOps.pipeline.renewalSummary', {
                  future: futureRenewals.length,
                  expired: expiredRenewals.length
                })
              }}
            </p>
          </div>
          <span class="text-lg font-black text-amber-600">
            {{ t('dataOps.pipeline.urgent', { count: urgentRenewals.length }) }}
          </span>
        </div>
      </section>
    </div>

    <section
      class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div class="flex items-center gap-3 border-b border-slate-100 px-6 py-4">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-xs font-bold text-indigo-600"
        >
          L
        </div>
        <h3 class="font-bold text-slate-800">
          {{ t('dataOps.pipeline.details') }}
        </h3>
        <span class="ml-auto text-xs text-slate-400">
          {{ t('dataOps.pipeline.records', { count: filteredProjects.length }) }}
        </span>
      </div>

      <div
        class="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3"
      >
        <select v-model="ownerFilter" class="pipeline-select">
          <option value="">{{ t('dataOps.pipeline.allOwners') }}</option>
          <option v-for="owner in owners" :key="owner" :value="owner">
            {{ owner }}
          </option>
        </select>
        <select v-model="scopeFilter" class="pipeline-select">
          <option value="">{{ t('dataOps.pipeline.allRegions') }}</option>
          <option v-for="scope in scopes" :key="scope" :value="scope">
            {{ scope }}
          </option>
        </select>
        <span class="ml-auto text-xs text-slate-400">
          {{
            t('dataOps.pipeline.pagination', {
              count: tableRows.length,
              pages: totalPages
            })
          }}
        </span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr
              class="bg-slate-50 font-bold uppercase tracking-wider text-slate-500"
            >
              <th class="px-3 py-3">{{ t('dataOps.columns.projectName') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.columns.customerName') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.columns.owner') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.columns.region') }}</th>
              <th class="px-3 py-3">
                {{ t('dataOps.executive.fields.initiationDate') }}
              </th>
              <th class="px-3 py-3 text-right">
                {{ t('dataOps.executive.fields.estimatedAmount') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-50">
            <tr
              v-for="project in pagedRows"
              :key="project.id"
              class="transition-colors hover:bg-indigo-50/20"
            >
              <td
                class="max-w-[180px] truncate px-3 py-3 font-medium text-slate-800"
                :title="project.project_name"
              >
                {{ project.project_name || t('dataOps.pipeline.unnamed') }}
              </td>
              <td class="max-w-[150px] truncate px-3 py-3 text-slate-600">
                {{ customerName(project) }}
              </td>
              <td class="px-3 py-3">
                <div class="flex items-center gap-1.5">
                  <div
                    class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-[9px] font-bold text-indigo-600"
                  >
                    {{ ownerInitial(projectOwner(project)) }}
                  </div>
                  <span class="truncate text-slate-600">
                    {{ projectOwner(project) }}
                  </span>
                </div>
              </td>
              <td class="px-3 py-3">
                <span
                  class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700"
                >
                  {{ projectScope(project) }}
                </span>
              </td>
              <td class="px-3 py-3 text-slate-500">
                {{ project.oa_initiation_date || '-' }}
              </td>
              <td class="px-3 py-3 text-right font-bold text-slate-700">
                {{ projectMoney(project) }}
              </td>
            </tr>
            <tr v-if="!pagedRows.length">
              <td class="px-3 py-10 text-center text-slate-400" colspan="6">
                {{ t('dataOps.pipeline.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        class="flex items-center justify-end gap-2 border-t border-slate-100 px-4 py-3 text-xs"
      >
        <button
          class="pager-btn"
          :disabled="currentPage <= 1"
          type="button"
          @click="currentPage = 1"
        >
          {{ t('dataOps.common.firstPage') }}
        </button>
        <button
          class="pager-btn"
          :disabled="currentPage <= 1"
          type="button"
          @click="currentPage -= 1"
        >
          {{ t('dataOps.common.previousPage') }}
        </button>
        <span class="font-semibold text-slate-600">
          {{ currentPage }} / {{ totalPages }}
        </span>
        <button
          class="pager-btn"
          :disabled="currentPage >= totalPages"
          type="button"
          @click="currentPage += 1"
        >
          {{ t('dataOps.common.nextPage') }}
        </button>
        <button
          class="pager-btn"
          :disabled="currentPage >= totalPages"
          type="button"
          @click="currentPage = totalPages"
        >
          {{ t('dataOps.common.lastPage') }}
        </button>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatAmountByCurrency } from '@/composables/useDataOpsConsole'

const { locale, t } = useI18n()

const props = defineProps({
  insights: { type: Object, default: null },
  projects: { type: Array, default: () => [] },
  summary: { type: Object, default: null }
})

const activeScope = ref('all')
const includeLanded = ref(false)
const ownerFilter = ref('')
const scopeFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const chartColors = [
  '#6366f1',
  '#10b981',
  '#f59e0b',
  '#ec4899',
  '#8b5cf6',
  '#14b8a6',
  '#f97316'
]
const funnelColors = ['#94a3b8', '#6366f1', '#f59e0b', '#10b981']

const totalProjects = computed(() => filteredProjects.value.length)
const domesticProjects = computed(
  () => filteredProjects.value.filter((project) => isDomestic(project)).length
)
const overseaProjects = computed(
  () => filteredProjects.value.filter((project) => isOverseas(project)).length
)
const domesticBaseProjects = computed(
  () => baseProjects.value.filter((project) => isDomestic(project)).length
)
const overseaBaseProjects = computed(
  () => baseProjects.value.filter((project) => isOverseas(project)).length
)

const scopeTabs = computed(() => [
  {
    key: 'all',
    label: t('dataOps.pipeline.tabs.all'),
    count: baseProjects.value.length
  },
  {
    key: 'domestic',
    label: t('dataOps.pipeline.tabs.domestic'),
    count: domesticBaseProjects.value
  },
  {
    key: 'overseas',
    label: t('dataOps.pipeline.tabs.overseas'),
    count: overseaBaseProjects.value
  }
])

const baseProjects = computed(() =>
  includeLanded.value
    ? props.projects
    : props.projects.filter((project) => !isLanded(project))
)

const filteredProjects = computed(() => {
  let rows = baseProjects.value
  if (activeScope.value === 'domestic') {
    rows = rows.filter((project) => isDomestic(project))
  } else if (activeScope.value === 'overseas') {
    rows = rows.filter((project) => isOverseas(project))
  }
  return rows
})

const metricCards = computed(() => [
  {
    accent: '#6366f1',
    caption: t('dataOps.pipeline.captionSplit', {
      domestic: domesticProjects.value,
      overseas: overseaProjects.value
    }),
    delta: '8%',
    icon: 'T',
    label: t('dataOps.pipeline.totalProjects'),
    value: compactNumber(totalProjects.value)
  },
  {
    accent: '#10b981',
    caption: t('dataOps.pipeline.captionAmount', {
      domestic: currencyCountLabel(domesticAmountByCurrency.value),
      overseas: currencyCountLabel(overseaAmountByCurrency.value)
    }),
    delta: '15%',
    icon: 'M',
    label: t('dataOps.pipeline.estimatedTotal'),
    value: currencyCountLabel(totalAmountByCurrency.value)
  },
  {
    accent: '#f59e0b',
    caption: t('dataOps.pipeline.potentialCaption'),
    delta: '12%',
    icon: 'H',
    label: t('dataOps.pipeline.highPotential'),
    value: compactNumber(highPotentialProjects.value)
  },
  {
    accent: '#ef4444',
    caption: t('dataOps.pipeline.riskCaption'),
    icon: '!',
    label: t('dataOps.pipeline.riskAlerts'),
    value: compactNumber(props.summary?.at_risk)
  }
])

const scopeDistribution = computed(() =>
  distribution(filteredProjects.value, projectScope).slice(0, 5)
)

const domesticAmountByCurrency = computed(() =>
  amountBuckets(filteredProjects.value.filter((project) => isDomestic(project)))
)
const overseaAmountByCurrency = computed(() =>
  amountBuckets(filteredProjects.value.filter((project) => isOverseas(project)))
)
const totalAmountByCurrency = computed(() =>
  amountBuckets(filteredProjects.value)
)
const highPotentialProjects = computed(
  () =>
    filteredProjects.value.filter((project) => project.is_high_potential).length
)

const statusDistribution = computed(() =>
  distribution(filteredProjects.value, projectStatus)
    .map((item) => ({ ...item, color: statusColor(item.label) }))
    .slice(0, 5)
)

const funnelItems = computed(() => {
  const total = filteredProjects.value.length
  const followUp = filteredProjects.value.filter(hasOwner).length
  const negotiation = filteredProjects.value.filter(isNegotiating).length
  const signed = filteredProjects.value.filter(isSigned).length
  return [
    { label: t('dataOps.pipeline.funnelStages.potential'), value: total },
    { label: t('dataOps.pipeline.funnelStages.followUp'), value: followUp },
    {
      label: t('dataOps.pipeline.funnelStages.negotiation'),
      value: negotiation
    },
    { label: t('dataOps.pipeline.funnelStages.signed'), value: signed }
  ].map((item, index) => ({
    ...item,
    color: funnelColors[index],
    percent: total ? Math.max(6, Math.round((item.value / total) * 100)) : 0
  }))
})

const conversionRate = computed(() => {
  const total = funnelItems.value[0]?.value || 0
  const signed = funnelItems.value[3]?.value || 0
  return total ? ((signed / total) * 100).toFixed(1) : '0.0'
})

const ownerContribution = computed(() => {
  const groups = new Map()
  filteredProjects.value.forEach((project) => {
    const owner = projectOwner(project)
    const current = groups.get(owner) || {
      amountByCurrency: new Map(),
      count: 0,
      owner
    }
    const amount = projectAmount(project)
    const currency = projectCurrency(project)
    current.amountByCurrency.set(
      currency,
      (current.amountByCurrency.get(currency) || 0) + amount
    )
    current.count += 1
    groups.set(owner, current)
  })
  const rows = Array.from(groups.values())
    .sort((left, right) => right.count - left.count)
    .slice(0, 8)
  const max = Math.max(...rows.map((item) => item.count), 1)
  return rows.map((item, index) => ({
    ...item,
    amountByCurrency: Array.from(item.amountByCurrency.entries()).map(
      ([currency, amount]) => ({ currency, amount })
    ),
    color: chartColors[index % chartColors.length],
    percent: Math.max(4, Math.round((item.count / max) * 100))
  }))
})

const monthlyTrend = computed(() => {
  const buckets = new Map()
  const counts = new Map()
  filteredProjects.value.forEach((project) => {
    const month = String(project.oa_initiation_date || '').slice(0, 7)
    if (!month) return
    const currency = projectCurrency(project)
    const key = `${month}::${currency}`
    buckets.set(key, {
      currency,
      label: `${month} ${currency}`,
      month,
      value: (buckets.get(key)?.value || 0) + projectAmount(project)
    })
    counts.set(month, (counts.get(month) || 0) + 1)
  })
  const rows = Array.from(buckets.values())
  const hasAmount = rows.some((item) => item.value > 0)
  if (!hasAmount) {
    return Array.from(counts.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .slice(-9)
      .map(([label, value]) => ({
        displayValue: t('dataOps.pipeline.projectsCount', { count: value }),
        label,
        value
      }))
  }
  return rows
    .sort((left, right) =>
      `${left.month}${left.currency}`.localeCompare(
        `${right.month}${right.currency}`
      )
    )
    .slice(-9)
    .map((item) => ({
      ...item,
      displayValue: formatCurrencyBuckets([
        { amount: item.value, currency: item.currency }
      ])
    }))
})

const settlementTrend = computed(() =>
  (props.insights?.settlement_receivable_trend || []).map((item) => ({
    currency: item.currency || t('dataOps.pipeline.unknown'),
    displayValue: formatCurrencyBuckets([
      {
        amount: item.receivable_amount,
        currency: item.currency || t('dataOps.pipeline.unknown')
      }
    ]),
    label: `${item.month} ${item.currency || t('dataOps.pipeline.unknown')}`,
    received: Number(item.received_amount || 0),
    value: Number(item.receivable_amount || 0)
  }))
)

const renewals = computed(() => props.insights?.upcoming_renewals || [])
const futureRenewals = computed(() =>
  renewals.value.filter((item) => Number(item.days_left) >= 0)
)
const expiredRenewals = computed(() =>
  renewals.value.filter((item) => Number(item.days_left) < 0)
)
const urgentRenewals = computed(() =>
  futureRenewals.value.filter((item) => Number(item.days_left) <= 30)
)

const owners = computed(() =>
  unique(filteredProjects.value.map(projectOwner)).filter(Boolean)
)
const scopes = computed(() =>
  unique(filteredProjects.value.map(projectScope)).filter(Boolean)
)

const tableRows = computed(() =>
  filteredProjects.value.filter((project) => {
    const ownerMatched =
      !ownerFilter.value || projectOwner(project) === ownerFilter.value
    const scopeMatched =
      !scopeFilter.value || projectScope(project) === scopeFilter.value
    return ownerMatched && scopeMatched
  })
)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(tableRows.value.length / pageSize))
)
const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return tableRows.value.slice(start, start + pageSize)
})

watch([activeScope, includeLanded, ownerFilter, scopeFilter, tableRows], () => {
  currentPage.value = 1
})

const PanelTitle = defineComponent({
  props: {
    icon: { type: String, required: true },
    title: { type: String, required: true }
  },
  setup(componentProps) {
    return () =>
      h('h3', { class: 'flex items-center font-bold text-slate-800' }, [
        h('span', { class: 'mr-3 h-5 w-1 rounded-full bg-indigo-500' }),
        h(
          'span',
          { class: 'mr-2 text-xs font-bold text-indigo-500' },
          componentProps.icon
        ),
        componentProps.title
      ])
  }
})

const MetricBar = defineComponent({
  props: {
    item: { type: Object, required: true }
  },
  setup(componentProps) {
    return () =>
      h('div', { class: 'space-y-2' }, [
        h('div', { class: 'flex justify-between text-xs' }, [
          h(
            'span',
            { class: 'truncate font-bold text-slate-600' },
            componentProps.item.label
          ),
          h(
            'span',
            { class: 'ml-3 shrink-0 font-bold text-slate-400' },
            componentProps.item.value
          )
        ]),
        h('div', { class: 'h-1.5 overflow-hidden rounded-full bg-slate-100' }, [
          h('div', {
            class: 'h-full rounded-full',
            style: {
              backgroundColor: componentProps.item.color,
              width: `${componentProps.item.percent}%`
            }
          })
        ])
      ])
  }
})

const TrendBars = defineComponent({
  props: {
    color: { type: String, default: '#6366f1' },
    items: { type: Array, default: () => [] }
  },
  setup(componentProps) {
    return () => {
      const max = Math.max(
        ...componentProps.items.map((item) => Number(item.value || 0)),
        1
      )
      return h(
        'div',
        { class: 'flex h-full items-end gap-2 border-b border-slate-100' },
        componentProps.items.length
          ? componentProps.items.map((item) =>
              h(
                'div',
                {
                  class:
                    'flex h-full min-w-0 flex-1 flex-col items-center justify-end'
                },
                [
                  h('div', {
                    class: 'trend-bar w-full rounded-t transition-all',
                    style: {
                      backgroundColor: componentProps.color,
                      height: `${Math.max(8, (Number(item.value || 0) / max) * 100)}%`
                    },
                    title: `${item.label} ${item.displayValue || compactNumber(item.value)}`
                  }),
                  h(
                    'span',
                    {
                      class:
                        'mt-2 w-full truncate text-center text-[10px] text-slate-400'
                    },
                    item.label
                  )
                ]
              )
            )
          : h(EmptyBlock)
      )
    }
  }
})

const EmptyBlock = defineComponent({
  setup() {
    return () =>
      h(
        'div',
        {
          class:
            'flex min-h-24 items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-400'
        },
        t('dataOps.pipeline.noData')
      )
  }
})

function distribution(rows, getter) {
  const counts = new Map()
  rows.forEach((row) => {
    const label = getter(row) || t('dataOps.pipeline.uncategorized')
    counts.set(label, (counts.get(label) || 0) + 1)
  })
  const max = Math.max(...counts.values(), 1)
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .map(([label, value], index) => ({
      color: chartColors[index % chartColors.length],
      label,
      percent: Math.max(4, Math.round((value / max) * 100)),
      value
    }))
}

function statusColor(label) {
  const status = String(label || '')
  if (/已付款|正常|已完成|已签约|已落地|已验收/i.test(status)) {
    return '#10b981'
  }
  if (/未付款|逾期|失败|取消|拒绝/i.test(status)) {
    return '#ef4444'
  }
  if (/部分付款|待续约|预警/i.test(status)) {
    return '#f59e0b'
  }
  if (/付款中|进行中|跟进|谈判|审批/i.test(status)) {
    return '#6366f1'
  }
  return '#94a3b8'
}

function projectOwner(project) {
  return (
    project.owner_canonical ||
    project.owner_display ||
    project.sales_person ||
    project.project_owner ||
    t('dataOps.pipeline.unassigned')
  )
}

function projectScope(project) {
  return (
    project.domestic_type ||
    project.project_scope ||
    project.country ||
    t('dataOps.pipeline.uncategorized')
  )
}

function projectStatus(project) {
  return project.status || project.order_status || t('dataOps.pipeline.notUpdated')
}

function customerName(project) {
  return (
    project.customer_full_name ||
    project.signing_customer ||
    project.end_customer ||
    '-'
  )
}

function projectAmount(project) {
  return Number(
    project.display_amount ||
      project.payment_amount ||
      project.total_amount ||
      project.estimated_amount ||
      project.stat_amount_usd ||
      0
  )
}

function projectCurrency(project) {
  if (project.display_currency) return project.display_currency
  if (Number(project.payment_amount || 0)) {
    return (
      project.payment_currency ||
      project.currency ||
      t('dataOps.pipeline.unknown')
    )
  }
  if (Number(project.total_amount || 0)) {
    return project.currency || t('dataOps.pipeline.unknown')
  }
  if (Number(project.estimated_amount || 0)) {
    return project.currency || t('dataOps.pipeline.unknown')
  }
  if (Number(project.stat_amount_usd || 0)) return 'USD'
  return (
    project.currency ||
    project.payment_currency ||
    t('dataOps.pipeline.unknown')
  )
}

function amountBuckets(projects) {
  const buckets = new Map()
  projects.forEach((project) => {
    const amount = projectAmount(project)
    if (!amount) return
    const currency = projectCurrency(project)
    buckets.set(currency, (buckets.get(currency) || 0) + amount)
  })
  return Array.from(buckets.entries())
    .sort(([left], [right]) => left.localeCompare(right, locale.value))
    .map(([currency, amount]) => ({ currency, amount }))
}

function formatCurrencyBuckets(items) {
  return formatAmountByCurrency(null, items, { locale: locale.value })
}

function currencyCountLabel(items) {
  if (!Array.isArray(items) || !items.length) return '—'
  if (items.length === 1) return formatCurrencyBuckets(items)
  return t('dataOps.pipeline.currencyCount', { count: items.length })
}

function projectMoney(project) {
  const value = projectAmount(project)
  if (!value) return '-'
  const currency = projectCurrency(project)
  return formatAmountByCurrency(value, [{ amount: value, currency }], {
    locale: locale.value
  })
}

function compactNumber(value) {
  return new Intl.NumberFormat(locale.value).format(Number(value || 0))
}

function unique(items) {
  return Array.from(new Set(items)).sort((left, right) =>
    left.localeCompare(right, locale.value)
  )
}

function ownerInitial(value) {
  const text = String(value || '-').trim()
  if (!text) return '-'
  if (/^[A-Za-z]/.test(text)) {
    return text
      .split(/\s+/)
      .map((item) => item[0])
      .join('')
      .slice(0, 2)
      .toUpperCase()
  }
  return text.slice(0, 1)
}

function isDomestic(project) {
  return String(project.project_scope || '')
    .toLowerCase()
    .includes('domestic')
}

function isOverseas(project) {
  return String(project.project_scope || '')
    .toLowerCase()
    .includes('oversea')
}

function isLanded(project) {
  const status = `${project.status || ''} ${project.order_status || ''}`
  return /已落地|已签约|完成|closed|landed/i.test(status)
}

function hasOwner(project) {
  return Boolean(project.sales_person || project.project_owner)
}

function isNegotiating(project) {
  const status = `${project.status || ''} ${project.order_status || ''}`
  return /谈判|报价|商务|合同|po|order|审批|采购/i.test(status)
}

function isSigned(project) {
  const status = `${project.status || ''} ${project.order_status || ''}`
  return /签约|已成单|已落地|完成|closed|signed|accept/i.test(status)
}
</script>

<style scoped>
.dashboard-card {
  border: 1px solid rgb(241 245 249);
  border-radius: 0.75rem;
  background: white;
  padding: 1.25rem;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
}

.metric-card-accent {
  position: absolute;
  top: 0;
  right: 0;
  width: 6rem;
  height: 6rem;
  border-bottom-left-radius: 9999px;
  background: var(--metric-accent);
  opacity: 0.05;
}

.metric-card-icon {
  color: var(--metric-accent);
}

.trend-bar:hover {
  filter: brightness(0.92);
}

.pipeline-select {
  border-radius: 0.5rem;
  border: 1px solid rgb(226 232 240);
  background: white;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: rgb(71 85 105);
  outline: none;
}

.pipeline-select:focus {
  box-shadow: 0 0 0 2px rgb(224 231 255);
}
</style>
