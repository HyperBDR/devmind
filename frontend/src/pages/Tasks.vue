<template>
  <AppLayout>
    <div class="w-full max-w-full">
      <!-- Page Header -->
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('tasks.title') }}
          </h1>
        </div>
      </div>

      <!-- Content Card -->
      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar -->
          <div
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <!-- Batch Actions (Left) -->
            <div class="flex items-center gap-2 flex-wrap">
              <BaseButton
                v-if="selectedTasks.length > 0"
                variant="outline"
                size="sm"
                @click="handleBatchDeleteClick"
                class="shadow-sm"
              >
                {{ t('tasks.batchDelete') }} ({{ selectedTasks.length }})
              </BaseButton>
            </div>

            <!-- Search and Filter (Right) -->
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('tasks.searchPlaceholder')"
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

              <!-- Filter Button -->
              <BaseButton
                variant="outline"
                size="sm"
                @click="showFilterDrawer = true"
                class="relative flex items-center gap-2 shadow-sm hover:shadow-md transition-shadow"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                  />
                </svg>
                {{ t('common.filter') }}
                <span
                  v-if="activeFilterCount > 0"
                  class="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 text-xs font-medium text-white bg-primary-600 rounded-full"
                >
                  {{ activeFilterCount }}
                </span>
              </BaseButton>

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

          <!-- Active Filter Tags -->
          <div
            v-if="activeFilterCount > 0"
            class="flex flex-wrap items-center gap-2 mb-4"
          >
            <span
              v-if="filters.status"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
            >
              <span
                >{{ t('tasks.statusLabel') }}:
                {{ getStatusLabel(filters.status) }}</span
              >
              <button
                @click="removeStatusFilter"
                class="text-gray-500 hover:text-gray-700 transition-colors"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </span>
          </div>

          <BaseLoading v-if="loading && (!tasks || tasks.length === 0)" />

          <div
            v-else-if="!filteredTasks || filteredTasks.length === 0"
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
              {{ t('tasks.noTasks') }}
            </p>
          </div>

          <!-- Mobile Card View with Infinite Scroll -->
          <div
            v-if="filteredTasks && filteredTasks.length > 0"
            class="md:hidden space-y-3"
          >
            <TaskCard
              v-for="task in filteredTasks"
              :key="task?.id || Math.random()"
              :task="task"
              @view="handleViewDetails"
              @delete="handleDeleteClick"
            />

            <!-- Sentinel element for intersection observer - must always exist when hasMore -->
            <div
              v-if="hasMore"
              ref="sentinelElement"
              class="h-20 flex items-center justify-center"
            >
              <!-- Loading More Indicator (Auto-load when scrolling) -->
              <div v-if="loading || loadingMore" class="py-6">
                <BaseLoading inline size="sm" />
                <p class="text-sm text-gray-500 mt-2">
                  {{ t('common.loadingMore') }}
                </p>
              </div>
            </div>

            <!-- No More Data -->
            <div
              v-if="!hasMore && filteredTasks.length > 0"
              class="py-6 text-center"
            >
              <p class="text-sm text-gray-400">{{ t('common.noMoreData') }}</p>
            </div>
          </div>

          <!-- Desktop Table View -->
          <div
            v-if="filteredTasks && filteredTasks.length > 0"
            class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <div
              v-if="loading"
              class="absolute inset-0 bg-white bg-opacity-80 flex items-center justify-center z-10 rounded-lg backdrop-blur-sm"
            >
              <BaseLoading
                inline
                size="lg"
                variant="primary"
                :show-text="false"
              />
            </div>
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    <input
                      type="checkbox"
                      :checked="allSelected"
                      @change="handleSelectAll"
                      class="w-4 h-4 rounded border-gray-300 bg-white text-primary-600 focus:ring-primary-500 focus:ring-2 cursor-pointer checked:bg-primary-600 checked:border-primary-600"
                    />
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.name') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.statusLabel') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.startedAt') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.finishedAt') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.duration') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('tasks.successCount') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-100">
                <tr
                  v-for="task in filteredTasks"
                  :key="task?.id || Math.random()"
                  :class="[
                    'transition-colors duration-150',
                    isTaskSelected(task)
                      ? 'bg-primary-50 hover:bg-primary-100'
                      : 'hover:bg-gray-50'
                  ]"
                >
                  <td class="px-4 py-4 whitespace-nowrap">
                    <input
                      type="checkbox"
                      :checked="isTaskSelected(task)"
                      @change="handleTaskSelect(task, $event.target.checked)"
                      class="w-4 h-4 rounded border-gray-300 bg-white text-primary-600 focus:ring-primary-500 focus:ring-2 cursor-pointer checked:bg-primary-600 checked:border-primary-600"
                    />
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <button
                      v-if="task"
                      @click="handleViewDetails(task)"
                      class="text-sm font-semibold text-gray-900 hover:text-primary-600 transition-colors cursor-pointer text-left"
                      :title="task?.name || '-'"
                    >
                      {{ task?.name || '-' }}
                    </button>
                    <div v-else class="text-sm font-semibold text-gray-900">
                      -
                    </div>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <StatusBadge :status="mapStatus(task?.status)" />
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-600 font-medium">
                      {{ formatDate(task?.started_at) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-600 font-medium">
                      {{ formatDate(task?.finished_at) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-600 font-medium">
                      {{ formatDuration(task) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-600 font-medium">
                      {{ getSuccessCount(task) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination (Desktop Only) -->
          <div
            class="hidden md:flex mt-6 pt-4 border-t border-gray-200 flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
          >
            <div
              class="flex flex-col sm:flex-row items-start sm:items-center gap-4"
            >
              <div class="text-sm text-gray-700 font-medium">
                <span v-if="totalCount > 0">
                  {{
                    t('common.pagination.showing', {
                      from: (currentPage - 1) * pageSize + 1,
                      to: Math.min(currentPage * pageSize, totalCount),
                      total: totalCount
                    })
                  }}
                </span>
                <span v-else class="text-gray-500">
                  {{ t('common.noData') }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-sm text-gray-700 font-medium">
                  {{ t('common.pagination.itemsPerPage') }}:
                </label>
                <select
                  v-model.number="pageSize"
                  @change="handlePageSizeChange"
                  class="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white cursor-pointer shadow-sm hover:shadow-md transition-shadow font-medium"
                >
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                </select>
              </div>
            </div>
            <div v-if="totalPages > 1" class="flex items-center gap-3">
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage === 1"
                @click="handlePageChange(currentPage - 1)"
                class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ t('common.previous') }}
              </BaseButton>
              <span
                class="text-sm text-gray-700 font-semibold flex items-center px-3 py-1.5 bg-gray-50 rounded-md border border-gray-200"
              >
                {{
                  t('common.pagination.page', {
                    current: currentPage,
                    total: totalPages
                  })
                }}
              </span>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage === totalPages"
                @click="handlePageChange(currentPage + 1)"
                class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ t('common.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Details Modal -->
      <TaskDetailsModal
        :show="showDetailsModal"
        :task="selectedTask"
        @close="showDetailsModal = false"
      />

      <!-- Batch Delete Confirmation -->
      <ConfirmDialog
        :show="showBatchDeleteDialog"
        :title="t('tasks.batchDeleteConfirm')"
        :message="
          t('tasks.batchDeleteMessage', { count: selectedTasks.length })
        "
        :variant="'danger'"
        :loading="deleting"
        @close="showBatchDeleteDialog = false"
        @confirm="handleBatchDeleteConfirm"
      />

      <!-- Filter Drawer -->
      <FilterDrawer
        :show="showFilterDrawer"
        :title="t('tasks.title')"
        :filters="filterConfig"
        v-model="filters"
        @close="showFilterDrawer = false"
        @apply="handleFilterApply"
        @clear="handleFilterClear"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useIntervalFn } from '@vueuse/core'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import FilterDrawer from '@/components/ui/FilterDrawer.vue'
import TaskCard from '@/components/tasks/TaskCard.vue'
import TaskDetailsModal from '@/components/tasks/TaskDetailsModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { tasksApi } from '@/api/tasks'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { format } from 'date-fns'

const { t } = useI18n()
const { showError } = useToast()

const tasks = ref([])
const filteredTasks = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(10)
const filters = ref({
  status: ''
})
const searchQuery = ref('')
const showDetailsModal = ref(false)
const selectedTask = ref(null)
const showFilterDrawer = ref(false)

const filterConfig = computed(() => [
  {
    key: 'status',
    label: t('tasks.statusLabel'),
    options: [
      { value: '', label: t('tasks.filter.all') },
      { value: 'pending', label: t('tasks.status.pending') },
      { value: 'running', label: t('tasks.status.running') },
      { value: 'completed', label: t('tasks.status.completed') },
      { value: 'failed', label: t('tasks.status.failed') },
      { value: 'partial', label: t('tasks.status.partial') }
    ]
  }
])

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.value.status) count++
  return count
})

const getStatusLabel = (status) => {
  const statusMap = {
    pending: t('tasks.status.pending'),
    running: t('tasks.status.running'),
    completed: t('tasks.status.completed'),
    failed: t('tasks.status.failed'),
    partial: t('tasks.status.partial')
  }
  return statusMap[status] || status
}

const removeStatusFilter = () => {
  filters.value.status = ''
  handleFilterChange()
}
const selectedTasks = ref([])
const showBatchDeleteDialog = ref(false)
const deleting = ref(false)

const loadTasks = async (isPolling = false) => {
  // Don't show loading indicator during polling to avoid flickering
  if (!isPolling) {
    loading.value = true
  }
  try {
    // Ensure pageSize is a valid number
    const validPageSize = Number(pageSize.value) || 10
    const params = {
      page: currentPage.value,
      page_size: validPageSize
    }
    if (filters.value.status) {
      params.status = filters.value.status
    }
    const response = await tasksApi.getTasks(params)
    const data = extractResponseData(response)

    let newTasks = []
    // Handle paginated response
    // Standard DRF format: {count, next, previous, results: [...]}
    // Custom format: {list: [...], pagination: {total, page, pageSize, ...}}
    if (Array.isArray(data)) {
      newTasks = data
      if (!isPolling) {
        totalPages.value = 1
      }
    } else if (data && data.results) {
      // Standard DRF pagination format
      newTasks = data.results
      if (!isPolling) {
        const total = data.count || 0
        const validPageSize = Number(pageSize.value) || 10
        totalCount.value = total
        totalPages.value = total > 0 ? Math.ceil(total / validPageSize) : 1
      }
    } else if (data && data.list && data.pagination) {
      // Custom pagination format
      newTasks = data.list
      if (!isPolling) {
        // Use the current pageSize.value (user's choice) instead of backend's value
        // This ensures user's page size selection is respected
        const total = data.pagination.total || 0
        const validPageSize = Number(pageSize.value) || 10
        totalCount.value = total
        totalPages.value = total > 0 ? Math.ceil(total / validPageSize) : 1
        // Only update currentPage if it's not already set by user action (e.g., page size change)
        // This prevents overriding user's page reset when changing page size
        if (
          data.pagination.page &&
          data.pagination.page !== currentPage.value
        ) {
          // Only sync if backend returned a different page (shouldn't happen normally)
          // But we keep currentPage.value as user set it
        }
        // Don't override pageSize.value - keep user's selection
      }
    } else {
      newTasks = data || []
      if (!isPolling) {
        totalPages.value = 1
        totalCount.value = newTasks.length
      }
    }

    // During polling, merge updates instead of replacing entire list
    if (isPolling) {
      mergeTaskUpdates(newTasks)
    } else {
      tasks.value = newTasks
      applyFilters()
    }
  } catch (error) {
    // Don't show error during polling to avoid annoying users
    if (!isPolling) {
      showError(extractErrorMessage(error, t('tasks.loadError')))
      tasks.value = []
      filteredTasks.value = []
      totalPages.value = 1
      totalCount.value = 0
    }
  } finally {
    if (!isPolling) {
      loading.value = false
    }
  }
}

// Merge task updates during polling to avoid full table re-render
const mergeTaskUpdates = (newTasks) => {
  // Create a map of existing tasks by ID for quick lookup
  const existingTasksMap = new Map(tasks.value.map((task) => [task.id, task]))

  let hasChanges = false

  // Update existing tasks by comparing with new data
  const updatedTasks = tasks.value.map((existingTask) => {
    const newTask = newTasks.find((nt) => nt.id === existingTask.id)
    if (newTask) {
      // Check if key fields have changed
      const keyFieldsChanged =
        existingTask.status !== newTask.status ||
        existingTask.finished_at !== newTask.finished_at ||
        existingTask.success_count !== newTask.success_count ||
        existingTask.started_at !== newTask.started_at

      if (keyFieldsChanged) {
        // Use new task object to trigger Vue reactivity
        hasChanges = true
        return newTask
      }
      // Keep existing task object reference if nothing changed
      return existingTask
    }
    // Task not in new data, keep existing (shouldn't happen in pagination)
    return existingTask
  })

  // Only update if there are actual changes to avoid unnecessary re-renders
  if (hasChanges) {
    tasks.value = updatedTasks
    applyFilters()
  }
}

const applyFilters = () => {
  let filtered = [...tasks.value]

  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter((task) =>
      task.name?.toLowerCase().includes(query)
    )
  }

  if (filters.value.status) {
    filtered = filtered.filter((task) => task.status === filters.value.status)
  }

  filteredTasks.value = filtered
  selectedTasks.value = selectedTasks.value.filter((task) =>
    filtered.some((t) => t.id === task.id)
  )
}

const handleSearch = () => {
  currentPage.value = 1
  loadTasks()
}

const mapStatus = (status) => {
  if (!status) return 'processing'
  const statusMap = {
    pending: 'processing', // Show loading spinner for pending tasks
    running: 'processing',
    completed: 'completed',
    failed: 'failed',
    partial: 'processing' // Show loading spinner for partial tasks too
  }
  return statusMap[status] || 'processing'
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const formatDuration = (task) => {
  if (!task) return '-'

  const startedAt = task.started_at
  if (!startedAt) return '-'

  const endTime = task.finished_at ? new Date(task.finished_at) : new Date()
  const startTime = new Date(startedAt)
  const diffMs = endTime - startTime

  if (diffMs < 0) return '-'

  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    const hours = diffHours % 24
    if (hours > 0) {
      return `${diffDays}${t('tasks.durationDays')}${hours}${t('tasks.durationHours')}`
    }
    return `${diffDays}${t('tasks.durationDays')}`
  }

  if (diffHours > 0) {
    const minutes = diffMinutes % 60
    if (minutes > 0) {
      return `${diffHours}${t('tasks.durationHours')}${minutes}${t('tasks.durationMinutes')}`
    }
    return `${diffHours}${t('tasks.durationHours')}`
  }

  if (diffMinutes > 0) {
    return `${diffMinutes}${t('tasks.durationMinutes')}`
  }

  return `${diffSeconds}${t('tasks.durationSeconds')}`
}

const getSuccessCount = (task) => {
  if (!task) return '-'

  // Try success_count field first (from TaskListSerializer)
  if (task.success_count !== undefined && task.success_count !== null) {
    return task.success_count > 0 ? task.success_count : '-'
  }

  // Fallback to result field (for detail view)
  if (!task.result) return '-'

  const result = task.result
  const statistics = result.statistics || {}

  const successful =
    statistics.successful ??
    result.successful_count ??
    result.success_count ??
    result.processed_count ??
    0

  return successful > 0 ? successful : '-'
}

const handleViewDetails = async (task) => {
  try {
    // Fetch full task details including result, parameters, and steps
    const response = await tasksApi.getTask(task.id)
    const fullTask = extractResponseData(response)
    selectedTask.value = fullTask
    showDetailsModal.value = true
  } catch (error) {
    showError(extractErrorMessage(error, t('tasks.loadError')))
    // Fallback to list data if detail fetch fails
    selectedTask.value = task
    showDetailsModal.value = true
  }
}

const handleFilterChange = () => {
  currentPage.value = 1
  loadTasks()
}

const handleFilterApply = (newFilters) => {
  filters.value = { ...newFilters }
  handleFilterChange()
}

const handleFilterClear = () => {
  filters.value = { status: '' }
  handleFilterChange()
}

const handleRefresh = () => {
  loadTasks()
}

const allSelected = computed(() => {
  return (
    filteredTasks.value.length > 0 &&
    filteredTasks.value.every((task) => isTaskSelected(task))
  )
})

const isTaskSelected = (task) => {
  if (!task || !selectedTasks.value) return false
  return selectedTasks.value.some((t) => t && t.id === task.id)
}

const handleSelectAll = (event) => {
  if (!filteredTasks.value) return
  if (event.target.checked) {
    selectedTasks.value = [...filteredTasks.value]
  } else {
    selectedTasks.value = []
  }
}

const handleTaskSelect = (task, checked) => {
  if (checked) {
    if (!isTaskSelected(task)) {
      selectedTasks.value.push(task)
    }
  } else {
    selectedTasks.value = selectedTasks.value.filter((t) => t.id !== task.id)
  }
}

const handleDeleteClick = (task) => {
  // Tasks don't support individual delete, only batch delete
  // This is a placeholder for the card component
  showError(t('tasks.deleteNotSupported'))
}

const handleBatchDeleteClick = () => {
  if (selectedTasks.value.length === 0) return
  showBatchDeleteDialog.value = true
}

const handleBatchDeleteConfirm = async () => {
  if (selectedTasks.value.length === 0) return

  deleting.value = true
  try {
    showError(t('tasks.batchDeleteNotSupported'))
  } catch (error) {
    showError(extractErrorMessage(error, t('tasks.batchDeleteError')))
  } finally {
    deleting.value = false
    showBatchDeleteDialog.value = false
    selectedTasks.value = []
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  loadTasks()
}

const handlePageSizeChange = () => {
  currentPage.value = 1
  loadTasks()
}

const handleLoadMore = async () => {
  // For mobile infinite scroll, load next page and append to existing tasks
  if (currentPage.value >= totalPages.value || loadingMore.value) return

  const nextPage = currentPage.value + 1
  loadingMore.value = true

  try {
    const validPageSize = Number(pageSize.value) || 10
    const params = {
      page: nextPage,
      page_size: validPageSize
    }
    if (filters.value && filters.value.status) {
      params.status = filters.value.status
    }
    const response = await tasksApi.getTasks(params)
    const data = extractResponseData(response)

    // Append new tasks to existing list
    let newTasks = []
    if (Array.isArray(data)) {
      newTasks = data
    } else if (data && data.results) {
      newTasks = data.results
    } else if (data && data.list && data.pagination) {
      newTasks = data.list
    } else {
      newTasks = data || []
    }

    // Append to existing tasks instead of replacing
    if (Array.isArray(tasks.value) && Array.isArray(newTasks)) {
      tasks.value = [...tasks.value, ...newTasks]
      applyFilters()
      currentPage.value = nextPage
    }
  } catch (error) {
    // Only show error if it's not a cancellation
    if (
      error &&
      error.name !== 'AbortError' &&
      error.name !== 'CanceledError'
    ) {
      showError(extractErrorMessage(error, t('tasks.loadError')))
    }
  } finally {
    loadingMore.value = false
  }
}

const hasMore = computed(() => {
  return currentPage.value < totalPages.value
})

const isMobile = ref(false)
const sentinelElement = ref(null)
let observer = null
let isSettingUpObserver = false

const checkMobile = () => {
  try {
    const wasMobile = isMobile.value
    isMobile.value = window.innerWidth < 768

    // Re-setup observer if mobile status changed
    if (wasMobile !== isMobile.value) {
      if (observer) {
        try {
          observer.disconnect()
        } catch (e) {
          // Ignore errors when disconnecting
        }
        observer = null
      }
      if (isMobile.value && hasMore.value) {
        nextTick(() => {
          setupIntersectionObserver()
        })
      }
    }
  } catch (e) {
    console.error('Error in checkMobile:', e)
  }
}

const setupIntersectionObserver = () => {
  if (!isMobile.value || !sentinelElement.value || isSettingUpObserver) {
    return
  }

  // Prevent duplicate setup
  if (observer) {
    return
  }

  isSettingUpObserver = true

  // Create new observer - trigger when sentinel is visible
  // Use rootMargin to trigger earlier (200px before element enters viewport)
  try {
    observer = new IntersectionObserver(
      (entries) => {
        if (!entries || entries.length === 0) return
        const entry = entries[0]
        // Auto-load when sentinel element becomes visible (or is about to)
        if (
          entry &&
          entry.isIntersecting &&
          hasMore.value &&
          !loadingMore.value &&
          !loading.value
        ) {
          handleLoadMore()
        }
      },
      {
        root: null, // Use viewport
        rootMargin: '200px', // Trigger 200px before reaching the element for smoother loading
        threshold: 0.01 // Trigger as soon as any part is visible
      }
    )

    if (sentinelElement.value) {
      observer.observe(sentinelElement.value)
    }
  } catch (e) {
    console.error('Failed to setup IntersectionObserver:', e)
    observer = null
  } finally {
    isSettingUpObserver = false
  }
}

// Check if there are running or pending tasks
const hasRunningTasks = computed(() => {
  if (!Array.isArray(tasks.value)) return false
  return tasks.value.some(
    (task) => task?.status === 'running' || task?.status === 'pending'
  )
})

const isDetailTaskRunning = (task) => {
  if (!task || !task.status) return false
  const s = String(task.status).toLowerCase()
  return s === 'running' || s === 'pending' || s === 'started' || s === 'retry'
}

// Poll single task when detail modal is open and task is still running
const pollDetailTask = useIntervalFn(
  async () => {
    const task = selectedTask.value
    if (!showDetailsModal.value || !task?.id || !isDetailTaskRunning(task))
      return
    try {
      const response = await tasksApi.getTask(task.id)
      const data = extractResponseData(response)
      if (data) selectedTask.value = data
    } catch {
      // Ignore poll errors (e.g. network), keep showing current data
    }
  },
  4000,
  { immediate: false }
)

watch(
  [
    showDetailsModal,
    () => selectedTask.value?.id,
    () => selectedTask.value?.status
  ],
  () => {
    if (
      showDetailsModal.value &&
      selectedTask.value?.id &&
      isDetailTaskRunning(selectedTask.value)
    ) {
      pollDetailTask.resume()
    } else {
      pollDetailTask.pause()
    }
  },
  { immediate: true }
)

// Polling for real-time updates only when there are running tasks (list)
const { pause, resume } = useIntervalFn(() => {
  if (hasRunningTasks.value) {
    loadTasks(true)
  }
}, 10000)

// Watch for changes in tasks, hasMore, loading states, or mobile status to re-setup observer
watch(
  [
    () => filteredTasks.value?.length || 0,
    hasMore,
    isMobile,
    () => loading.value,
    () => loadingMore.value
  ],
  () => {
    try {
      // Only setup observer when not loading and has more data
      if (
        isMobile.value &&
        hasMore.value &&
        !loading.value &&
        !loadingMore.value &&
        !observer
      ) {
        nextTick(() => {
          setupIntersectionObserver()
        })
      } else if (
        observer &&
        (!hasMore.value ||
          loading.value ||
          loadingMore.value ||
          !isMobile.value)
      ) {
        // Disconnect observer when loading or no more data
        try {
          observer.disconnect()
        } catch (e) {
          // Ignore errors when disconnecting
        }
        observer = null
      }
    } catch (e) {
      console.error('Error in observer watch:', e)
    }
  },
  { immediate: false }
)

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  // Setup intersection observer for mobile infinite scroll
  if (isMobile.value) {
    nextTick(() => {
      setupIntersectionObserver()
    })
  }
  loadTasks()
  // Start polling if there are running tasks
  if (hasRunningTasks.value) {
    resume()
  }
})

onUnmounted(() => {
  try {
    pause()
    pollDetailTask.pause()
    window.removeEventListener('resize', checkMobile)
    if (observer) {
      try {
        observer.disconnect()
      } catch (e) {
        // Ignore errors when disconnecting
      }
      observer = null
    }
  } catch (e) {
    console.error('Error in onUnmounted:', e)
  }
})

// Watch for changes in running tasks to start/stop polling
watch(
  hasRunningTasks,
  (hasRunning) => {
    if (hasRunning) {
      resume()
    } else {
      pause()
    }
  },
  { immediate: true }
)
</script>
