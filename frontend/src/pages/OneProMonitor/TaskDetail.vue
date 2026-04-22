<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.taskDetailPage.title') }}
          </h1>
          <p class="mt-2 text-sm text-gray-500">
            {{ t('hyperbdrMonitor.taskDetailPage.subtitle') }}
          </p>
        </div>
        <router-link
          :to="{ name: 'OneProMonitorTasks' }"
          class="text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          {{ t('hyperbdrMonitor.actions.backToTasks') }}
        </router-link>
      </div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.labels.basicInfo') }}
          </h2>
          <dl class="mt-4 space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.taskId') }}
              </dt>
              <dd class="text-gray-900">#{{ task.id || '-' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.dataSource') }}
              </dt>
              <dd class="text-gray-900">{{ task.data_source_name || '-' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.status') }}
              </dt>
              <dd><StatusBadge :status="taskStatus(task.status)" /></dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.triggerMode') }}
              </dt>
              <dd class="text-gray-900">{{ task.trigger_mode || '-' }}</dd>
            </div>
          </dl>
        </div>

        <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.labels.executionTime') }}
          </h2>
          <dl class="mt-4 space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.startTime') }}
              </dt>
              <dd class="text-gray-900">
                {{ formatDateTime(task.start_time) }}
              </dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.endTime') }}
              </dt>
              <dd class="text-gray-900">{{ formatDateTime(task.end_time) }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.duration') }}
              </dt>
              <dd class="text-gray-900">{{ task.duration_seconds || 0 }}s</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-gray-500">
                {{ t('hyperbdrMonitor.labels.celeryTaskId') }}
              </dt>
              <dd class="text-gray-900 break-all">
                {{ task.celery_task_id || '-' }}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.labels.collectionResult') }}
          </h2>
          <div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div class="rounded-lg bg-gray-50 border border-gray-200 p-4">
              <p class="text-sm text-gray-500">
                {{ t('hyperbdrMonitor.taskDetailPage.tenantCount') }}
              </p>
              <p class="mt-2 text-2xl font-semibold text-gray-900">
                {{ task.total_tenants || 0 }}
              </p>
            </div>
            <div class="rounded-lg bg-gray-50 border border-gray-200 p-4">
              <p class="text-sm text-gray-500">
                {{ t('hyperbdrMonitor.taskDetailPage.licenseCount') }}
              </p>
              <p class="mt-2 text-2xl font-semibold text-gray-900">
                {{ task.total_licenses || 0 }}
              </p>
            </div>
            <div class="rounded-lg bg-gray-50 border border-gray-200 p-4">
              <p class="text-sm text-gray-500">
                {{ t('hyperbdrMonitor.taskDetailPage.hostCount') }}
              </p>
              <p class="mt-2 text-2xl font-semibold text-gray-900">
                {{ task.total_hosts || 0 }}
              </p>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('hyperbdrMonitor.labels.errorMessage') }}
          </h2>
          <div
            class="mt-4 min-h-[120px] rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700 whitespace-pre-wrap break-words"
          >
            {{
              task.error_message || t('hyperbdrMonitor.taskDetailPage.noError')
            }}
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'

import { formatDateTime, taskStatus, unwrap } from './shared'

const route = useRoute()
const { t } = useI18n()
const { showError } = useToast()

const task = ref({})

async function loadTask() {
  try {
    const response = await oneproMonitorApi.tasks.get(route.params.id)
    task.value = unwrap(response)
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.taskDetailPage.loadError')
    )
  }
}

onMounted(() => {
  loadTask()
})
</script>
