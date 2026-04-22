<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <section
        class="relative overflow-hidden rounded-2xl border border-emerald-100 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.14),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] shadow-[0_20px_50px_-38px_rgba(15,23,42,0.55)]"
      >
        <div
          class="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <div class="flex flex-wrap items-center gap-4">
            <span
              class="inline-flex items-center rounded-full bg-slate-900 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.28em] text-white"
            >
              OnePro
            </span>
            <p class="text-sm text-gray-500">
              {{ t('hyperbdrMonitor.dashboardPage.scopeHint') }}
            </p>
          </div>
          <div class="w-full max-w-md">
            <OneProDataSourceSelect layout="inline" variant="toolbar" />
          </div>
        </div>
      </section>

      <section
        class="relative overflow-hidden rounded-[28px] border border-gray-200 bg-white shadow-[0_30px_80px_-48px_rgba(15,23,42,0.32)]"
      >
        <div
          class="absolute -left-10 top-0 h-40 w-40 rounded-full bg-emerald-100/80 blur-3xl"
        />
        <div
          class="absolute right-0 top-4 h-48 w-48 rounded-full bg-sky-100/70 blur-3xl"
        />
        <div class="relative px-6 py-7 lg:px-8 lg:py-8">
          <div>
            <p
              class="text-sm font-medium uppercase tracking-[0.24em] text-emerald-600"
            >
              OnePro Monitor
            </p>
            <h1
              class="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-gray-950 lg:text-4xl"
            >
              {{ t('hyperbdrMonitor.dashboardPage.title') }}
            </h1>
            <p
              class="mt-3 max-w-2xl text-sm leading-7 text-gray-600 lg:text-[15px]"
            >
              {{ t('hyperbdrMonitor.dashboardPage.subtitle') }}
            </p>
          </div>
        </div>
      </section>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article
          class="overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md cursor-pointer"
          @click="openDashboardLink('OneProMonitorTenants')"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p
                class="text-[11px] font-medium uppercase tracking-[0.2em] text-gray-400"
              >
                {{ t('hyperbdrMonitor.dashboardPage.tenantTotal') }}
              </p>
              <p class="mt-3 text-3xl font-semibold text-gray-950">
                {{ stats.tenant?.total || 0 }}
              </p>
            </div>
            <span
              class="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
            >
              {{ activeTenantCount }}
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-gray-500">
            {{
              t('hyperbdrMonitor.dashboardPage.tenantSummary', {
                active: activeTenantCount,
                disabled: disabledTenantCount
              })
            }}
          </p>
          <div class="mt-5 h-1.5 rounded-full bg-gray-100">
            <div
              class="h-1.5 rounded-full bg-emerald-500"
              :style="{ width: `${activeTenantRatio}%` }"
            />
          </div>
        </article>

        <article
          class="overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md cursor-pointer"
          @click="openDashboardLink('OneProMonitorHosts')"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p
                class="text-[11px] font-medium uppercase tracking-[0.2em] text-gray-400"
              >
                {{ t('hyperbdrMonitor.dashboardPage.hostTotal') }}
              </p>
              <p class="mt-3 text-3xl font-semibold text-gray-950">
                {{ stats.host?.total || 0 }}
              </p>
            </div>
            <span
              class="inline-flex rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700"
            >
              {{ healthyHostRatio }}%
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-gray-500">
            {{
              t('hyperbdrMonitor.dashboardPage.hostCoverageSummary', {
                healthy: healthyHostCount,
                total: stats.host?.total || 0
              })
            }}
          </p>
          <div class="mt-5 h-1.5 rounded-full bg-gray-100">
            <div
              class="h-1.5 rounded-full bg-sky-500"
              :style="{ width: `${healthyHostRatio}%` }"
            />
          </div>
        </article>

        <article
          class="overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md cursor-pointer"
          @click="openDashboardLink('OneProMonitorLicenses')"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p
                class="text-[11px] font-medium uppercase tracking-[0.2em] text-gray-400"
              >
                {{ t('hyperbdrMonitor.dashboardPage.licenseUsage') }}
              </p>
              <p class="mt-3 text-3xl font-semibold text-gray-950">
                {{ licenseUsageRatio }}%
              </p>
            </div>
            <span
              class="inline-flex rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700"
            >
              {{ stats.license?.total_used || 0 }}
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-gray-500">
            {{
              t('hyperbdrMonitor.dashboardPage.licenseSummary', {
                used: stats.license?.total_used || 0,
                unused: stats.license?.total_unused || 0
              })
            }}
          </p>
          <div class="mt-5 h-1.5 rounded-full bg-gray-100">
            <div
              class="h-1.5 rounded-full bg-violet-500"
              :style="{ width: `${licenseUsageRatio}%` }"
            />
          </div>
        </article>
      </div>

      <section
        class="overflow-hidden rounded-[24px] border border-gray-200 bg-white shadow-sm"
      >
        <div class="border-b border-gray-200 bg-gray-50/60 px-6 py-4">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.dashboardPage.riskTitle') }}
          </h2>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('hyperbdrMonitor.dashboardPage.riskSubtitle') }}
          </p>
        </div>
        <div class="grid gap-4 px-6 py-5 md:grid-cols-3">
          <div
            class="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4 transition hover:-translate-y-0.5 hover:border-amber-200 hover:shadow-sm cursor-pointer"
            @click="
              openDashboardLink('OneProMonitorTasks', { status: 'failed' })
            "
          >
            <p class="text-sm font-medium text-gray-900">
              {{ t('hyperbdrMonitor.dashboardPage.failedTasksTitle') }}
            </p>
            <p class="mt-1 text-2xl font-semibold text-gray-900">
              {{ failedTaskCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.dashboardPage.failedTasksSubtitle') }}
            </p>
          </div>
          <div
            class="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4 transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-sm cursor-pointer"
            @click="
              openDashboardLink('OneProMonitorHosts', { health_scope: 'risky' })
            "
          >
            <p class="text-sm font-medium text-gray-900">
              {{ t('hyperbdrMonitor.dashboardPage.riskyHostsTitle') }}
            </p>
            <p class="mt-1 text-2xl font-semibold text-gray-900">
              {{ riskyHostCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.dashboardPage.riskyHostsSubtitle') }}
            </p>
          </div>
          <div
            class="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4 transition hover:-translate-y-0.5 hover:border-rose-200 hover:shadow-sm cursor-pointer"
            @click="
              openDashboardLink('OneProMonitorHosts', {
                license_valid: 'false'
              })
            "
          >
            <p class="text-sm font-medium text-gray-900">
              {{ t('hyperbdrMonitor.dashboardPage.invalidLicenseHostsTitle') }}
            </p>
            <p class="mt-1 text-2xl font-semibold text-gray-900">
              {{ stats.host?.invalid_license || 0 }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{
                t('hyperbdrMonitor.dashboardPage.invalidLicenseHostsSubtitle')
              }}
            </p>
          </div>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useToast } from '@/composables/useToast'

import { toNumber, unwrap } from './shared'
import OneProDataSourceSelect from './OneProDataSourceSelect.vue'
import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const { t } = useI18n()
const { showError } = useToast()
const router = useRouter()
const { selectedDataSource, loadDataSources, appendDataSourceScope } =
  useOneProDataSourceScope()

const stats = ref({})

const activeTenantCount = computed(() => {
  const source = stats.value.tenant?.status_stats || {}
  return (source.active || 0) + (source.activated || 0)
})

const disabledTenantCount = computed(() => {
  const source = stats.value.tenant?.status_stats || {}
  return source.disabled || 0
})

const failedTaskCount = computed(() => {
  const source = stats.value.task?.status_stats || {}
  return source.failed || 0
})

const riskyHostCount = computed(() => {
  const source = stats.value.host?.health_status_stats || {}
  return (
    (source.warning || 0) + (source.unhealthy || 0) + (source.disconnected || 0)
  )
})

const healthyHostCount = computed(() => {
  const total = toNumber(stats.value.host?.total, 0)
  return Math.max(0, total - riskyHostCount.value)
})

const activeTenantRatio = computed(() => {
  const total = toNumber(stats.value.tenant?.total, 0)
  if (!total) return 0
  return Math.min(100, Math.round((activeTenantCount.value / total) * 100))
})

const healthyHostRatio = computed(() => {
  const total = toNumber(stats.value.host?.total, 0)
  if (!total) return 0
  return Math.min(
    100,
    Math.max(0, Math.round(((total - riskyHostCount.value) / total) * 100))
  )
})

const licenseUsageRatio = computed(() => {
  return Math.min(
    100,
    Math.max(0, toNumber(stats.value.license?.usage_ratio, 0))
  )
})

function openDashboardLink(name, query = {}) {
  router.push({
    name,
    query
  })
}

function queryParams() {
  return appendDataSourceScope()
}

async function loadDashboard() {
  const response = await oneproMonitorApi.dashboard(queryParams())
  stats.value = unwrap(response)
}

async function loadAll() {
  try {
    await loadDashboard()
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.dashboardPage.loadError')
    )
  }
}

onMounted(async () => {
  await loadDataSources()
  await loadAll()
})

watch(selectedDataSource, () => {
  loadAll()
})
</script>
