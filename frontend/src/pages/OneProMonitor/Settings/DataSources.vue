<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <SettingsNav
        :title="t('hyperbdrMonitor.settingsPage.title')"
        :subtitle="t('hyperbdrMonitor.settingsPage.dataSourcesSubtitle')"
      />

      <div class="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div
          class="px-6 py-4 border-b border-gray-200 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h2 class="text-lg font-semibold text-gray-900">
              {{ t('hyperbdrMonitor.settingsPage.dataSourceSectionTitle') }}
            </h2>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.settingsPage.dataSourceSectionSubtitle') }}
            </p>
          </div>
          <router-link
            :to="{ name: 'OneProMonitorSettingsDataSourceCreate' }"
            class="inline-flex items-center justify-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            {{ t('hyperbdrMonitor.actions.createDataSource') }}
          </router-link>
        </div>

        <BaseLoading v-if="loading && dataSources.length === 0" class="py-12" />
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.dataSource') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.apiUrl') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.status') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.collectInterval') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.lastCollected') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr v-for="source in dataSources" :key="source.id">
                <td class="px-6 py-4 text-sm text-gray-900">
                  <div class="font-medium">{{ source.name }}</div>
                  <div class="mt-1 text-xs text-gray-500">
                    {{ source.username }}
                  </div>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ source.api_url }}
                </td>
                <td class="px-6 py-4 text-sm">
                  <label class="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      :checked="source.is_active"
                      @change="toggleStatus(source)"
                    />
                    <span class="text-gray-700">{{
                      source.is_active
                        ? t('hyperbdrMonitor.labels.active')
                        : t('hyperbdrMonitor.labels.inactive')
                    }}</span>
                  </label>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ source.collect_interval || 3600 }}s
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ formatDateTime(source.last_collected_at) }}
                </td>
                <td class="px-6 py-4 text-sm">
                  <div class="flex flex-wrap gap-3">
                    <button
                      class="font-medium text-primary-600 hover:text-primary-700"
                      @click="triggerCollect(source.id)"
                    >
                      {{ t('hyperbdrMonitor.actions.collect') }}
                    </button>
                    <router-link
                      :to="{
                        name: 'OneProMonitorSettingsDataSourceEdit',
                        params: { id: source.id }
                      }"
                      class="font-medium text-gray-700 hover:text-gray-900"
                    >
                      {{ t('hyperbdrMonitor.actions.edit') }}
                    </router-link>
                    <button
                      class="font-medium text-red-600 hover:text-red-700"
                      @click="removeSource(source)"
                    >
                      {{ t('hyperbdrMonitor.actions.delete') }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="dataSources.length === 0">
                <td
                  colspan="6"
                  class="px-6 py-12 text-center text-sm text-gray-500"
                >
                  {{ t('hyperbdrMonitor.settingsPage.emptySources') }}
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
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { useToast } from '@/composables/useToast'

import SettingsNav from '../SettingsNav.vue'
import { formatDateTime, unwrap } from '../shared'

const { t } = useI18n()
const { showError, showSuccess } = useToast()

const loading = ref(false)
const dataSources = ref([])

async function loadDataSources() {
  loading.value = true
  try {
    const response = await oneproMonitorApi.dataSources.list({ limit: 200 })
    const payload = unwrap(response)
    dataSources.value = payload.items || []
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.loadSourcesError')
    )
  } finally {
    loading.value = false
  }
}

async function toggleStatus(source) {
  try {
    await oneproMonitorApi.dataSources.patch(source.id, {
      is_active: !source.is_active
    })
    showSuccess(t('hyperbdrMonitor.settingsPage.toggleSourceSuccess'))
    await loadDataSources()
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.toggleSourceError')
    )
  }
}

async function triggerCollect(id) {
  try {
    await oneproMonitorApi.dataSources.collect(id)
    showSuccess(t('hyperbdrMonitor.settingsPage.collectSuccess'))
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.collectError')
    )
  }
}

async function removeSource(source) {
  if (
    !window.confirm(
      t('hyperbdrMonitor.settingsPage.deleteConfirm', { name: source.name })
    )
  ) {
    return
  }
  try {
    await oneproMonitorApi.dataSources.delete(source.id)
    showSuccess(t('hyperbdrMonitor.settingsPage.deleteSuccess'))
    await loadDataSources()
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.deleteError')
    )
  }
}

onMounted(() => {
  loadDataSources()
})
</script>
