<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('cloudBilling.tasks.title') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('cloudBilling.tasks.subtitle') }}
        </p>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar -->
          <div
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <!-- Actions (Left) -->
            <div class="flex items-center gap-3 flex-wrap">
              <BaseButton
                variant="primary"
                size="sm"
                :loading="triggering"
                @click="handleTriggerCollection"
                class="flex items-center gap-2"
              >
                <svg
                  v-if="!triggering"
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                {{
                  triggering
                    ? t('cloudBilling.tasks.triggering')
                    : t('cloudBilling.tasks.triggerCollection')
                }}
              </BaseButton>
            </div>

            <!-- Search and Filter (Right) -->
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('common.search')"
                class="flex-1 sm:w-64"
                @update:modelValue="handleSearch"
              >
                <template #icon>
                  <svg
                    class="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                </template>
              </BaseInput>

              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                @click="handleRefresh"
                :title="t('common.refresh')"
                class="flex items-center gap-1 shadow-sm hover:shadow-md transition-shadow"
              >
                <svg
                  v-if="!loading"
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                <span class="sr-only">{{ t('common.refresh') }}</span>
              </BaseButton>
            </div>
          </div>

          <BaseLoading v-if="loading && tasks.length === 0" />

          <div
            v-if="!loading && tasks.length === 0"
            class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
          >
            <svg
              class="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
            <p class="text-sm font-medium text-gray-600">
              {{ t('cloudBilling.tasks.noTasks') }}
            </p>
          </div>

          <!-- Mobile Card View -->
          <div v-if="!loading && tasks.length > 0" class="md:hidden space-y-3">
            <TaskCard
              v-for="task in tasks"
              :key="task.id"
              :task="task"
              @view="handlePreview"
            />
          </div>

          <!-- Desktop Table View -->
          <div
            v-if="!loading && tasks.length > 0"
            class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.tasks.taskName') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.tasks.status') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.tasks.startTime') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.tasks.endTime') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.tasks.duration') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-100">
                <tr
                  v-for="task in tasks"
                  :key="task.id"
                  @click="handlePreview(task)"
                  class="cursor-pointer transition-colors duration-150 hover:bg-gray-50"
                >
                  <td
                    class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900"
                  >
                    {{ task.name }}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <StatusBadge :status="mapTaskStatus(task.status)" />
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ formatDate(task.started_at) }}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ formatDate(task.finished_at) }}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ formatDuration(task.duration) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="!loading && totalCount > 0"
            class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4"
          >
            <p class="text-sm text-gray-600">
              {{ t('common.pagination.showing', paginationShowing) }}
            </p>
            <div class="flex items-center gap-2">
              <label class="text-sm text-gray-600"
                >{{ t('common.pagination.itemsPerPage') }}:</label
              >
              <select
                v-model.number="pageSize"
                class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                @change="handlePageSizeChange"
              >
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage <= 1"
                @click="goPrevPage"
              >
                {{ t('common.pagination.previous') }}
              </BaseButton>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage >= totalPages"
                @click="goNextPage"
              >
                {{ t('common.pagination.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Detail Panel -->
      <TaskDetailPanel
        :show="showPreviewModal"
        :task="selectedTask"
        @close="showPreviewModal = false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useDebounce } from '@/composables/useDebounce'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { formatDuration } from '@/utils/formatting'
import { cloudBillingApi } from '@/api/cloudBilling'
import { taskManagementApi } from '@/admin/api'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TaskCard from '@/components/cloud-billing/TaskCard.vue'
import TaskDetailPanel from '@/components/cloud-billing/TaskDetailPanel.vue'

const { t } = useI18n()
const { showSuccess, showError } = useToast()

const loading = ref(false)
const triggering = ref(false)
const tasks = ref([])
const searchQuery = ref('')
const showPreviewModal = ref(false)
const selectedTask = ref(null)
const currentPage = ref(1)
const totalCount = ref(0)
const pageSize = ref(10)

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const paginationShowing = computed(() => ({
  from:
    totalCount.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1,
  to: Math.min(currentPage.value * pageSize.value, totalCount.value),
  total: totalCount.value
}))

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const mapTaskStatus = (status) => {
  const statusMap = {
    pending: 'pending',
    running: 'processing',
    completed: 'success',
    failed: 'failed'
  }
  return statusMap[status] || status
}

const { debouncedFn: debouncedSearch } = useDebounce((query) => {
  currentPage.value = 1
  loadTasks(query, 1)
}, 300)

const handleSearch = (query) => {
  searchQuery.value = query
  debouncedSearch(query)
}

const handleRefresh = () => {
  loadTasks(searchQuery.value, currentPage.value)
}

const goPrevPage = () => {
  if (currentPage.value <= 1) return
  currentPage.value--
  loadTasks(searchQuery.value, currentPage.value)
}

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value++
  loadTasks(searchQuery.value, currentPage.value)
}

const handlePageSizeChange = () => {
  currentPage.value = 1
  loadTasks(searchQuery.value, 1)
}

async function handlePreview(task) {
  if (!task?.id) return
  try {
    const res = await taskManagementApi.getExecution(task.id)
    const data = extractResponseData(res)
    selectedTask.value = {
      id: data.id,
      task_id: data.task_id ?? task.task_id,
      task_name: data.task_name ?? task.name,
      name: data.task_name ?? task.name,
      status: data.status ?? task.status,
      created_at: data.created_at,
      started_at: data.started_at ?? task.started_at,
      finished_at: data.finished_at ?? task.finished_at,
      duration: data.duration ?? task.duration,
      result: data.result,
      error: data.error,
      traceback: data.traceback,
      metadata: data.metadata || task.metadata
    }
    showPreviewModal.value = true
  } catch (e) {
    showError(extractErrorMessage(e, t('common.error')))
  }
}

const handleTriggerCollection = async () => {
  triggering.value = true
  try {
    const response = await cloudBillingApi.triggerCollection()
    const data = extractResponseData(response)

    if (data.success) {
      showSuccess(t('cloudBilling.tasks.collectionTriggered'))
      // Refresh task list after a short delay
      setTimeout(() => {
        loadTasks(searchQuery.value)
      }, 1000)
    } else {
      showError(data.message || t('cloudBilling.tasks.collectionFailed'))
    }
  } catch (error) {
    console.error('Failed to trigger collection:', error)
    const errorMessage =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      t('cloudBilling.tasks.collectionFailed')
    showError(errorMessage)
  } finally {
    triggering.value = false
  }
}

const loadTasks = async (query = '', page = currentPage.value) => {
  loading.value = true
  try {
    const params = {
      page,
      page_size: pageSize.value
    }
    if (query) {
      params.task_name = query
    }
    const response = await cloudBillingApi.getCollectionTasks(params)
    const data = extractResponseData(response)

    const list =
      data?.results ?? data?.list ?? (Array.isArray(data) ? data : [])
    const serverTotal = data?.count ?? data?.pagination?.total
    const hasServerPagination = Number.isFinite(Number(serverTotal))
    const total = hasServerPagination ? Number(serverTotal) : list.length

    totalCount.value = total
    currentPage.value = page
    const pageList = hasServerPagination
      ? list
      : list.slice((page - 1) * pageSize.value, page * pageSize.value)

    tasks.value = pageList.map((task) => ({
      id: task.id,
      name: task.task_name || 'cloud_billing.tasks.collect_billing_data',
      status: mapTaskManagerStatus(task.status),
      started_at: task.started_at || task.created_at,
      finished_at: task.finished_at,
      duration: calculateDuration(task.started_at, task.finished_at),
      task_id: task.task_id,
      result: task.result,
      error: task.error,
      metadata: task.metadata
    }))
  } catch (error) {
    console.error('Failed to load tasks:', error)
    tasks.value = []
  } finally {
    loading.value = false
  }
}

const calculateDuration = (startTime, endTime) => {
  if (!startTime || !endTime) return null
  try {
    const start = new Date(startTime)
    const end = new Date(endTime)
    return Math.floor((end - start) / 1000) // Duration in seconds
  } catch {
    return null
  }
}

const mapTaskManagerStatus = (status) => {
  const statusMap = {
    PENDING: 'pending',
    STARTED: 'running',
    SUCCESS: 'completed',
    FAILURE: 'failed',
    RETRY: 'running',
    REVOKED: 'failed'
  }
  return statusMap[status] || status?.toLowerCase() || 'pending'
}

onMounted(() => {
  loadTasks()
})
</script>
