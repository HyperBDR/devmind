<template>
  <AppLayout :show-sidebar="false">
    <div class="mx-auto w-full max-w-[1440px]">
      <!-- Page Header -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white shadow-sm">
        <div
          class="flex flex-col gap-5 p-6 lg:flex-row lg:items-end lg:justify-between"
        >
          <div class="max-w-3xl">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-700"
            >
              <span class="h-2 w-2 rounded-full bg-primary-500" />
              {{ t('sals.dashboard.badge') }}
            </div>
            <h1 class="mt-4 text-2xl font-semibold tracking-tight text-gray-900">
              {{ t('sals.dashboard.title') }}
            </h1>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
              {{ t('sals.dashboard.subtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              @click="loadDashboard"
            >
              {{ t('common.refresh') }}
            </BaseButton>
            <BaseButton
              variant="outline"
              size="sm"
              :loading="syncing"
              @click="syncDb"
            >
              {{ t('sals.dashboard.sync') }}
            </BaseButton>
          </div>
        </div>
      </div>

      <!-- Error Banner -->
      <div
        v-if="error"
        class="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      >
        {{ error }}
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading && !dashboardLoaded" />

      <template v-else>
        <!-- KPI Cards -->
        <div class="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <article
            v-for="card in kpiCards"
            :key="card.key"
            class="group rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-gray-300"
          >
            <div class="mb-3 flex items-center justify-between">
              <span
                class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400"
              >
                {{ card.label }}
              </span>
              <div
                class="rounded-lg bg-gray-50 p-2 text-gray-400 transition-colors group-hover:bg-primary-50 group-hover:text-primary-600"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  v-html="card.iconPath"
                />
              </div>
            </div>
            <div class="text-2xl font-bold tracking-tight text-gray-900">
              {{ card.value }}
            </div>
            <div v-if="card.sub" class="mt-1 text-xs text-gray-500">
              {{ card.sub }}
            </div>
          </article>
        </div>

        <!-- Charts Row 1: State Distribution + Monthly Trend -->
        <div class="mb-6 grid items-stretch gap-6 lg:grid-cols-3">
          <!-- State Distribution -->
          <div
            class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.stateDistribution') }}
            </h3>
            <div class="mx-auto h-[220px] w-full max-w-[240px]">
              <Doughnut
                v-if="stateChartData"
                :data="stateChartData"
                :options="doughnutOptions"
              />
            </div>
            <div class="mt-4 space-y-2">
              <div
                v-for="(item, idx) in (data.state_dist || [])"
                :key="item.state"
                class="flex items-center justify-between text-xs"
              >
                <div class="flex items-center gap-2">
                  <span
                    class="h-2.5 w-2.5 rounded-full"
                    :style="{ backgroundColor: stateColors[idx % stateColors.length] }"
                  />
                  <span class="font-medium text-gray-600">{{ item.state }}</span>
                </div>
                <span class="font-mono font-semibold text-gray-900">{{
                  item.count
                }}</span>
              </div>
            </div>
          </div>

          <!-- Monthly Trend -->
          <div
            class="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.monthlyTrend') }}
            </h3>
            <div class="h-[280px]">
              <Bar
                v-if="trendChartData"
                :data="trendChartData"
                :options="barOptions"
              />
            </div>
          </div>
        </div>

        <!-- Charts Row 2: Priority Distribution + SLA Stats -->
        <div class="mb-6 grid items-stretch gap-6 lg:grid-cols-3">
          <!-- Priority Distribution -->
          <div
            class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.priorityDistribution') }}
            </h3>
            <div class="h-[220px]">
              <Bar
                v-if="priorityChartData"
                :data="priorityChartData"
                :options="barOptions"
              />
            </div>
          </div>

          <!-- SLA Stats -->
          <div
            class="lg:col-span-2 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.slaOverview') }}
            </h3>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-100">
                    <th
                      class="pb-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.priority') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.total') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.slaMet') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.slaRate') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.avgHours') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr
                    v-for="row in (data.sla_stats || [])"
                    :key="row.priority"
                    class="hover:bg-gray-50"
                  >
                    <td class="py-3 font-medium text-gray-700">{{ row.priority }}</td>
                    <td class="py-3 text-right font-mono text-gray-900">
                      {{ row.count }}
                    </td>
                    <td class="py-3 text-right font-mono text-gray-900">
                      {{ row.sla_met }}
                    </td>
                    <td class="py-3 text-right">
                      <span
                        class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
                        :class="
                          row.sla_rate >= 80
                            ? 'bg-green-100 text-green-700'
                            : row.sla_rate >= 50
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                        "
                      >
                        {{ row.sla_rate }}%
                      </span>
                    </td>
                    <td class="py-3 text-right font-mono text-gray-600">
                      {{ row.avg_hours }}h
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Tables Row: Group Stats + Customer Stats -->
        <div class="mb-6 grid gap-6 lg:grid-cols-2">
          <!-- Group Stats -->
          <div
            class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.groupStats') }}
            </h3>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-100">
                    <th
                      class="pb-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.group') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.total') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.avgHours') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.resolvedRate') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr
                    v-for="row in (data.group_stats || [])"
                    :key="row.group"
                    class="hover:bg-gray-50"
                  >
                    <td class="py-3 font-medium text-gray-700">{{ row.group }}</td>
                    <td class="py-3 text-right font-mono text-gray-900">
                      {{ row.count }}
                    </td>
                    <td class="py-3 text-right font-mono text-gray-600">
                      {{ row.avg_hours }}h
                    </td>
                    <td class="py-3 text-right">
                      <div class="flex items-center justify-end gap-2">
                        <div
                          class="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100"
                        >
                          <div
                            class="h-full rounded-full bg-primary-500"
                            :style="{ width: `${row.resolved_rate}%` }"
                          />
                        </div>
                        <span class="w-10 text-right font-mono text-gray-600">{{
                          row.resolved_rate
                        }}%</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Customer Stats -->
          <div
            class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.customerStats') }}
            </h3>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-100">
                    <th
                      class="pb-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.company') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.total') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.resolvedRate') }}
                    </th>
                    <th
                      class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                    >
                      {{ t('sals.dashboard.product') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr
                    v-for="row in (data.customer_stats || [])"
                    :key="row.company"
                    class="hover:bg-gray-50"
                  >
                    <td class="py-3 font-medium text-gray-700">{{ row.company }}</td>
                    <td class="py-3 text-right font-mono text-gray-900">
                      {{ row.count }}
                    </td>
                    <td class="py-3 text-right">
                      <span
                        class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
                        :class="
                          row.resolve_rate >= 80
                            ? 'bg-green-100 text-green-700'
                            : row.resolve_rate >= 50
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                        "
                      >
                        {{ row.resolve_rate }}%
                      </span>
                    </td>
                    <td class="py-3 text-right text-xs text-gray-500">
                      {{ row.category }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Assignee Stats -->
        <div
          class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <h3 class="mb-5 text-sm font-semibold text-gray-900">
            {{ t('sals.dashboard.assigneeStats') }}
          </h3>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-100">
                  <th
                    class="pb-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.assignee') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.total') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.avgHours') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.pendingCount') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr
                  v-for="row in (data.assignee_stats || [])"
                  :key="row.assignee"
                  class="hover:bg-gray-50"
                >
                  <td class="py-3 font-medium text-gray-700">{{ row.assignee }}</td>
                  <td class="py-3 text-right font-mono text-gray-900">
                    {{ row.count }}
                  </td>
                  <td class="py-3 text-right font-mono text-gray-600">
                    {{ row.avg_hours }}h
                  </td>
                  <td class="py-3 text-right">
                    <span
                      v-if="row.pending_count > 0"
                      class="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-700"
                    >
                      {{ row.pending_count }}
                    </span>
                    <span v-else class="text-gray-400">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend
} from 'chart.js'
import { Bar, Doughnut } from 'vue-chartjs'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { salsApi } from '@/api/sals'

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const { t } = useI18n()

const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const dashboardLoaded = ref(false)
const data = ref({
  kpi: {},
  state_dist: [],
  priority_dist: [],
  monthly_trend: [],
  group_stats: [],
  assignee_stats: [],
  customer_stats: [],
  sla_stats: []
})

// ── Chart Colors ────────────────────────────────────
const stateColors = [
  '#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
]

const priorityColors = {
  P1: '#ef4444',
  P2: '#f97316',
  P3: '#eab308',
  P4: '#22c55e'
}

// ── Load Data ───────────────────────────────────────
async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const res = await salsApi.getDashboard()
    data.value = res.data.data ?? res.data
    dashboardLoaded.value = true
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || e.message || 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

async function syncDb() {
  syncing.value = true
  try {
    await salsApi.syncDb('api', false)
    await loadDashboard()
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || e.message || 'Sync failed'
  } finally {
    syncing.value = false
  }
}

onMounted(loadDashboard)

// ── KPI Cards ───────────────────────────────────────
const kpiCards = computed(() => {
  const kpi = data.value.kpi || {}
  return [
    {
      key: 'total',
      label: t('sals.dashboard.kpiTotal'),
      value: kpi.total ?? 0,
      sub: `${kpi.resolved_rate ?? 0}% ${t('sals.dashboard.resolved')}`,
      iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />'
    },
    {
      key: 'pending',
      label: t('sals.dashboard.kpiPending'),
      value: (kpi.pending ?? 0) + (kpi.in_progress ?? 0),
      sub: `${kpi.pending ?? 0} pending · ${kpi.in_progress ?? 0} in progress`,
      iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />'
    },
    {
      key: 'sla',
      label: t('sals.dashboard.kpiSlaRate'),
      value: `${kpi.sla_rate ?? 0}%`,
      sub: `${kpi.p1_overdue ?? 0}/${kpi.p1_total ?? 0} P1 overdue`,
      iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />'
    },
    {
      key: 'avg',
      label: t('sals.dashboard.kpiAvgHours'),
      value: `${kpi.avg_resolve_hours ?? 0}h`,
      sub: t('sals.dashboard.kpiAvgHoursHint'),
      iconPath: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />'
    }
  ]
})

// ── State Distribution Chart ──────────────────────────
const stateChartData = computed(() => {
  const dist = data.value.state_dist || []
  return {
    labels: dist.map(d => d.state),
    datasets: [{
      data: dist.map(d => d.count),
      backgroundColor: stateColors,
      borderWidth: 0
    }]
  }
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed}` } }
  },
  cutout: '65%'
}

// ── Priority Distribution Chart ───────────────────────
const priorityChartData = computed(() => {
  const dist = data.value.priority_dist || []
  return {
    labels: dist.map(d => d.priority),
    datasets: [{
      label: t('sals.dashboard.count'),
      data: dist.map(d => d.count),
      backgroundColor: dist.map(d => priorityColors[d.priority] || '#6366f1'),
      borderRadius: 6,
      borderWidth: 0
    }]
  }
})

// ── Monthly Trend Chart ──────────────────────────────
const trendChartData = computed(() => {
  const trend = data.value.monthly_trend || []
  return {
    labels: trend.map(d => d.month),
    datasets: [
      {
        label: t('sals.dashboard.total'),
        data: trend.map(d => d.total),
        backgroundColor: '#6366f1',
        borderRadius: 6,
        borderWidth: 0
      }
    ]
  }
})

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}`
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    },
    y: {
      grid: { color: '#f3f4f6' },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    }
  }
}
</script>
