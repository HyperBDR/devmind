<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <OneProPageHeader
        :eyebrow="t('hyperbdrMonitor.tasksPage.eyebrow')"
        :title="t('hyperbdrMonitor.tasksPage.title')"
        :subtitle="t('hyperbdrMonitor.tasksPage.subtitle')"
        :scope-hint="t('hyperbdrMonitor.tasksPage.scopeHint')"
      >
        <template #toolbarActions>
          <BaseButton :loading="collecting" @click="triggerCollection">
            {{ t('hyperbdrMonitor.actions.collectNow') }}
          </BaseButton>
        </template>
        <template #summary>
          <article
            class="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(16,185,129,0.34)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-emerald-700/70"
            >
              {{ t('hyperbdrMonitor.tasksPage.completedTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ completedCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.tasksPage.completedSubtitle') }}
            </p>
          </article>
          <article
            class="rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(14,165,233,0.34)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-sky-700/70"
            >
              {{ t('hyperbdrMonitor.tasksPage.runningTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ runningCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.tasksPage.runningSubtitle') }}
            </p>
          </article>
          <article
            class="rounded-2xl border border-rose-100 bg-rose-50/70 px-4 py-4 shadow-[0_14px_34px_-24px_rgba(244,63,94,0.3)]"
          >
            <p
              class="text-[11px] font-medium uppercase tracking-[0.2em] text-rose-700/70"
            >
              {{ t('hyperbdrMonitor.tasksPage.failedTitle') }}
            </p>
            <p class="mt-2 text-2xl font-semibold text-gray-950">
              {{ failedCount }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              {{ t('hyperbdrMonitor.tasksPage.failedSubtitle') }}
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
                {{ t('hyperbdrMonitor.tasksPage.filtersTitle') }}
              </h2>
              <p class="mt-1 text-sm text-gray-500">
                {{ t('hyperbdrMonitor.tasksPage.filtersSubtitle') }}
              </p>
            </div>
            <p class="text-sm text-gray-500">
              {{
                t('hyperbdrMonitor.tasksPage.showingCount', {
                  count: tasks.length
                })
              }}
            </p>
          </div>
        </div>
        <div class="px-6 py-5">
          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[220px_140px]">
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
                <option value="pending">pending</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
            </label>
            <div class="flex items-end">
              <BaseButton
                class="w-full"
                :loading="loading"
                @click="loadTasks"
                >{{ t('hyperbdrMonitor.actions.filter') }}</BaseButton
              >
            </div>
          </div>
        </div>
      </section>

      <div class="bg-white border border-gray-200 rounded-2xl shadow-sm">
        <BaseLoading v-if="loading && tasks.length === 0" class="py-12" />
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.taskId') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.dataSource') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.status') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.executionTime') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.result') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr v-for="task in tasks" :key="task.id">
                <td class="px-6 py-4 text-sm text-gray-900">#{{ task.id }}</td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{ task.data_source_name || '-' }}
                </td>
                <td class="px-6 py-4 text-sm">
                  <StatusBadge :status="taskStatus(task.status)" />
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  <div>{{ formatDateTime(task.start_time) }}</div>
                  <div class="mt-1 text-xs text-gray-500">
                    {{ task.duration_seconds || 0 }}s
                  </div>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">
                  {{
                    t('hyperbdrMonitor.tasksPage.resultSummary', {
                      tenants: task.total_tenants || 0,
                      licenses: task.total_licenses || 0,
                      hosts: task.total_hosts || 0
                    })
                  }}
                </td>
                <td class="px-6 py-4 text-sm">
                  <router-link
                    :to="{
                      name: 'OneProMonitorTaskDetail',
                      params: { id: task.id }
                    }"
                    class="font-medium text-primary-600 hover:text-primary-700"
                  >
                    {{ t('hyperbdrMonitor.tasksPage.viewDetail') }}
                  </router-link>
                </td>
              </tr>
              <tr v-if="tasks.length === 0">
                <td
                  colspan="6"
                  class="px-6 py-12 text-center text-sm text-gray-500"
                >
                  {{ t('hyperbdrMonitor.tasksPage.empty') }}
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
import { useRoute } from 'vue-router'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'

import OneProPageHeader from './OneProPageHeader.vue'
import { formatDateTime, taskStatus, unwrap } from './shared'
import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const { t } = useI18n()
const { showError, showSuccess } = useToast()
const route = useRoute()
const { selectedDataSource, loadDataSources, appendDataSourceScope } =
  useOneProDataSourceScope()

const loading = ref(false)
const collecting = ref(false)
const tasks = ref([])
const filters = ref({
  status: ''
})

const completedCount = computed(
  () => tasks.value.filter((task) => task.status === 'completed').length
)
const runningCount = computed(
  () => tasks.value.filter((task) => task.status === 'running').length
)
const failedCount = computed(
  () => tasks.value.filter((task) => task.status === 'failed').length
)

function syncFiltersFromRoute() {
  filters.value = {
    status: typeof route.query.status === 'string' ? route.query.status : ''
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const response = await oneproMonitorApi.tasks.list(
      appendDataSourceScope({
        limit: 200,
        status: filters.value.status || undefined
      })
    )
    const payload = unwrap(response)
    tasks.value = payload.items || []
  } catch (error) {
    showError(
      error?.response?.data?.detail || t('hyperbdrMonitor.tasksPage.loadError')
    )
  } finally {
    loading.value = false
  }
}

async function triggerCollection() {
  collecting.value = true
  try {
    await oneproMonitorApi.tasks.collect({
      data_source_id: selectedDataSource.value || undefined
    })
    showSuccess(t('hyperbdrMonitor.tasksPage.triggerSuccess'))
    await loadTasks()
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.tasksPage.triggerError')
    )
  } finally {
    collecting.value = false
  }
}

onMounted(async () => {
  await loadDataSources()
  syncFiltersFromRoute()
  await loadTasks()
})

watch(selectedDataSource, () => {
  loadTasks()
})

watch(
  () => route.query.status,
  () => {
    syncFiltersFromRoute()
    loadTasks()
  }
)
</script>
