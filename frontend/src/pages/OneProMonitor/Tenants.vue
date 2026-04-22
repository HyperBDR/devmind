<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <OneProPageHeader
        :eyebrow="t('hyperbdrMonitor.tenantsPage.eyebrow')"
        :title="t('hyperbdrMonitor.tenantsPage.title')"
        :subtitle="t('hyperbdrMonitor.tenantsPage.subtitle')"
        :scope-hint="t('hyperbdrMonitor.tenantsPage.scopeHint')"
      />

      <section class="rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div class="border-b border-gray-200 px-6 py-5">
          <div
            class="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between"
          >
            <div>
              <h2 class="text-lg font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.tenantsPage.filtersTitle') }}
              </h2>
              <p class="mt-1 text-sm text-gray-500">
                {{ t('hyperbdrMonitor.tenantsPage.filtersSubtitle') }}
              </p>
            </div>
            <p class="text-sm text-gray-500">
              {{
                t('hyperbdrMonitor.tenantsPage.showingCount', {
                  count: tenants.length
                })
              }}
            </p>
          </div>
        </div>
        <div class="px-6 py-5">
          <div
            class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_140px]"
          >
            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.labels.tenant') }}
              </span>
              <input
                v-model="filters.name"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                :placeholder="
                  t('hyperbdrMonitor.tenantsPage.searchPlaceholder')
                "
                @keyup.enter="loadTenants"
              />
            </label>
            <div class="flex items-end">
              <BaseButton
                class="w-full"
                :loading="loading"
                @click="loadTenants"
                >{{ t('hyperbdrMonitor.actions.filter') }}</BaseButton
              >
            </div>
          </div>
        </div>
      </section>

      <div class="bg-white border border-gray-200 rounded-2xl shadow-sm">
        <BaseLoading v-if="loading && tenants.length === 0" class="py-12" />
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.tenant') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.status') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.dataSource') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.tenantsPage.hostCount') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.tenantsPage.licenseOverview') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.lastCollected') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr
                v-for="tenant in tenants"
                :key="`${tenant.data_source_id}-${tenant.id}`"
              >
                <td class="px-6 py-4 text-sm text-gray-900">
                  <div class="font-medium">{{ tenant.name }}</div>
                  <div class="mt-1 text-xs text-gray-500">{{ tenant.id }}</div>
                </td>
                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium"
                    :class="pillClass(tenant.status)"
                  >
                    {{ tenant.status || t('hyperbdrMonitor.labels.unknown') }}
                  </span>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ tenant.data_source_name || '-' }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ tenant.host_count || 0 }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{
                    t('hyperbdrMonitor.tenantsPage.licenseSummary', {
                      used: tenant.license_used || 0,
                      remaining: tenant.license_remaining || 0
                    })
                  }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ formatDateTime(tenant.last_collected_at) }}
                </td>
              </tr>
              <tr v-if="tenants.length === 0">
                <td
                  colspan="6"
                  class="px-6 py-12 text-center text-sm text-gray-500"
                >
                  {{ t('hyperbdrMonitor.tenantsPage.empty') }}
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
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { useToast } from '@/composables/useToast'

import OneProPageHeader from './OneProPageHeader.vue'
import { formatDateTime, pillClass, unwrap } from './shared'
import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const { t } = useI18n()
const { showError } = useToast()
const { selectedDataSource, loadDataSources, appendDataSourceScope } =
  useOneProDataSourceScope()

const loading = ref(false)
const tenants = ref([])
const filters = ref({
  name: ''
})

async function loadTenants() {
  loading.value = true
  try {
    const response = await oneproMonitorApi.tenants.list(
      appendDataSourceScope({
        limit: 200,
        name: filters.value.name || undefined
      })
    )
    const payload = unwrap(response)
    tenants.value = payload.items || []
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.tenantsPage.loadError')
    )
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDataSources()
  await loadTenants()
})

watch(selectedDataSource, () => {
  loadTenants()
})
</script>
