<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <OneProPageHeader
        :eyebrow="t('hyperbdrMonitor.licensesPage.eyebrow')"
        :title="t('hyperbdrMonitor.licensesPage.title')"
        :subtitle="t('hyperbdrMonitor.licensesPage.subtitle')"
        :scope-hint="t('hyperbdrMonitor.licensesPage.scopeHint')"
      >
        <template #summary>
          <article
            class="rounded-2xl border border-cyan-100 bg-cyan-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(14,165,233,0.38)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-cyan-700/70"
            >
              {{ t('hyperbdrMonitor.licensesPage.catalogTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ licenses.length }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.licensesPage.catalogSubtitle') }}
            </p>
          </article>
          <article
            class="rounded-2xl border border-violet-100 bg-violet-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(139,92,246,0.34)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-violet-700/70"
            >
              {{ t('hyperbdrMonitor.licensesPage.utilizationTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ totalUsageRatio }}%
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.licensesPage.utilizationSubtitle') }}
            </p>
          </article>
          <article
            class="rounded-2xl border border-amber-100 bg-amber-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(245,158,11,0.34)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-amber-700/70"
            >
              {{ t('hyperbdrMonitor.licensesPage.exhaustedTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ exhaustedCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.licensesPage.exhaustedSubtitle') }}
            </p>
          </article>
        </template>
      </OneProPageHeader>

      <section class="rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div class="border-b border-gray-200 px-6 py-5">
          <div
            class="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between"
          >
            <div>
              <h2 class="text-lg font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.licensesPage.filtersTitle') }}
              </h2>
              <p class="mt-1 text-sm text-gray-500">
                {{ t('hyperbdrMonitor.licensesPage.filtersSubtitle') }}
              </p>
            </div>
            <p class="text-sm text-gray-500">
              {{
                t('hyperbdrMonitor.licensesPage.showingCount', {
                  count: licenses.length
                })
              }}
            </p>
          </div>
        </div>
        <div class="px-6 py-5">
          <div
            class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_140px]"
          >
            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.labels.type') }}
              </span>
              <select
                v-model="filters.type"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              >
                <option value="">
                  {{ t('hyperbdrMonitor.labels.allTypes') }}
                </option>
                <option value="dr">DR</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.labels.status') }}
              </span>
              <select
                v-model="filters.status"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              >
                <option value="">
                  {{ t('hyperbdrMonitor.labels.allStatuses') }}
                </option>
                <option value="available">
                  {{ t('hyperbdrMonitor.labels.statusAvailable') }}
                </option>
                <option value="exhausted">
                  {{ t('hyperbdrMonitor.labels.statusExhausted') }}
                </option>
              </select>
            </label>
            <div class="flex items-end">
              <BaseButton
                class="w-full"
                :loading="loading"
                @click="loadLicenses"
                >{{ t('hyperbdrMonitor.actions.filter') }}</BaseButton
              >
            </div>
          </div>
        </div>
      </section>

      <div class="bg-white border border-gray-200 rounded-2xl shadow-sm">
        <BaseLoading v-if="loading && licenses.length === 0" class="py-12" />
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.type') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.tenant') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.licensesPage.capacityOverview') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.dataSource') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.licensesPage.validity') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr v-for="license in licenses" :key="license.id">
                <td class="px-6 py-4 text-sm text-gray-900">
                  {{ license.scene || '-' }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-900">
                  {{ license.tenant_name || '-' }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  <div class="flex items-center justify-between gap-3">
                    <span>{{
                      t('hyperbdrMonitor.licensesPage.usedOfTotal', {
                        used: license.total_used || 0,
                        total: license.total_amount || 0
                      })
                    }}</span>
                    <span class="font-medium text-gray-900"
                      >{{
                        percentage(license.total_used, license.total_amount)
                      }}%</span
                    >
                  </div>
                  <div class="mt-2 h-2 rounded-full bg-gray-100">
                    <div
                      class="h-2 rounded-full"
                      :class="
                        percentage(license.total_used, license.total_amount) >=
                        90
                          ? 'bg-amber-500'
                          : 'bg-cyan-500'
                      "
                      :style="{
                        width: `${percentage(license.total_used, license.total_amount)}%`
                      }"
                    />
                  </div>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ license.data_source_name || '-' }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ formatDateTime(license.expire_at) }}
                </td>
              </tr>
              <tr v-if="licenses.length === 0">
                <td
                  colspan="5"
                  class="px-6 py-12 text-center text-sm text-gray-500"
                >
                  {{ t('hyperbdrMonitor.licensesPage.empty') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { useToast } from '@/composables/useToast'

import OneProPageHeader from './OneProPageHeader.vue'
import { formatDateTime, percentage, toNumber, unwrap } from './shared'
import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const { t } = useI18n()
const { showError } = useToast()
const { selectedDataSource, loadDataSources, appendDataSourceScope } =
  useOneProDataSourceScope()

const loading = ref(false)
const licenses = ref([])
const filters = ref({
  type: '',
  status: ''
})

const exhaustedCount = computed(
  () =>
    licenses.value.filter((license) => Number(license.total_unused || 0) <= 0)
      .length
)

const totalUsageRatio = computed(() => {
  const totals = licenses.value.reduce(
    (acc, license) => {
      acc.used += toNumber(license.total_used, 0)
      acc.amount += toNumber(license.total_amount, 0)
      return acc
    },
    { used: 0, amount: 0 }
  )

  return totals.amount ? Math.round((totals.used / totals.amount) * 100) : 0
})

async function loadLicenses() {
  loading.value = true
  try {
    const response = await oneproMonitorApi.licenses.list(
      appendDataSourceScope({
        limit: 200,
        type: filters.value.type || undefined,
        status: filters.value.status || undefined
      })
    )
    const payload = unwrap(response)
    licenses.value = payload.items || []
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.licensesPage.loadError')
    )
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDataSources()
  await loadLicenses()
})

watch(selectedDataSource, () => {
  loadLicenses()
})
</script>
