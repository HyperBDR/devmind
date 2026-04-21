<template>
  <AppLayout>
    <div class="w-full max-w-full">
      <!-- Page Header -->
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('scheduledTasks.title') }}
        </h1>
      </div>

      <!-- Tasks Table -->
      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar -->
          <div
            class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
          >
            <!-- Batch Actions (Left) -->
            <div class="flex flex-wrap items-center gap-2">
              <BaseButton
                @click="handleCreate"
                size="sm"
                class="w-full sm:w-auto"
              >
                {{ t('scheduledTasks.create') }}
              </BaseButton>
              <BaseButton
                v-if="selectedTasks.length > 0"
                variant="outline"
                size="sm"
                @click="handleBatchDeleteClick"
                class="flex-1 sm:flex-initial"
              >
                <span class="hidden sm:inline"
                  >{{ t('scheduledTasks.batchDelete') }} ({{
                    selectedTasks.length
                  }})</span
                >
                <span class="sm:hidden">{{
                  t('scheduledTasks.batchDelete')
                }}</span>
              </BaseButton>
              <BaseButton
                v-if="selectedTasks.length > 0"
                variant="outline"
                size="sm"
                @click="handleBatchToggle"
                class="flex-1 sm:flex-initial"
              >
                <span class="hidden sm:inline"
                  >{{ t('scheduledTasks.batchToggle') }} ({{
                    selectedTasks.length
                  }})</span
                >
                <span class="sm:hidden">{{
                  t('scheduledTasks.batchToggle')
                }}</span>
              </BaseButton>
            </div>

            <!-- Search and Filter (Right) -->
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('scheduledTasks.searchPlaceholder')"
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

              <select
                v-model="statusFilter"
                class="text-sm h-9 px-3 py-1.5 border border-gray-300 rounded-md bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow shadow-sm hover:shadow-md"
                @change="handleFilterChange"
              >
                <option value="">{{ t('scheduledTasks.filter.all') }}</option>
                <option value="enabled">
                  {{ t('scheduledTasks.filter.enabled') }}
                </option>
                <option value="disabled">
                  {{ t('scheduledTasks.filter.disabled') }}
                </option>
              </select>

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

          <BaseLoading v-if="loading && filteredTasks.length === 0" />

          <div
            v-if="!loading && filteredTasks.length === 0"
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
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p class="text-sm font-medium text-gray-600">
              {{ t('scheduledTasks.noTasks') }}
            </p>
          </div>

          <template v-if="!loading && filteredTasks.length > 0">
            <!-- Mobile Card View with Infinite Scroll -->
            <div class="md:hidden space-y-3">
              <ScheduledTaskCard
                v-for="task in filteredTasks"
                :key="task?.uuid || Math.random()"
                :task="task"
                :task-type-label="getTaskTypeLabel(task?.task_type)"
                :collecting="task?.uuid && collectingTasks[task.uuid]"
                @view="handleViewDetails"
                @collect="handleCollectNow"
                @edit="handleEdit"
                @toggle="handleToggle"
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
                <p class="text-sm text-gray-400">
                  {{ t('common.noMoreData') }}
                </p>
              </div>
            </div>

            <!-- Desktop Table View -->
            <div
              class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
            >
              <!-- Loading overlay when data exists but is refreshing -->
              <div
                v-if="loading && filteredTasks.length > 0"
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
                      {{ t('scheduledTasks.name') }}
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                    >
                      {{ t('scheduledTasks.schedule') }}
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                    >
                      {{ t('scheduledTasks.status') }}
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                    >
                      {{ t('scheduledTasks.taskType') }}
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                    >
                      {{ t('scheduledTasks.createdAt') }}
                    </th>
                    <th
                      class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                    >
                      {{ t('common.moreActions') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-100">
                  <tr
                    v-for="task in filteredTasks"
                    :key="task?.uuid || Math.random()"
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
                    <td class="px-4 py-4 max-w-xs">
                      <button
                        @click="handleViewDetails(task)"
                        class="text-sm font-semibold text-primary-600 hover:text-primary-700 hover:underline line-clamp-2 break-words text-left"
                      >
                        {{ task?.name || '-' }}
                      </button>
                    </td>
                    <td class="px-4 py-4">
                      <span class="text-sm text-gray-600 font-medium">
                        {{
                          formatSchedule(
                            task?.schedule_type,
                            task?.schedule_value
                          )
                        }}
                      </span>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap">
                      <StatusBadge
                        :status="task?.enabled ? 'enabled' : 'disabled'"
                      />
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap">
                      <span class="text-sm text-gray-700 font-medium">{{
                        getTaskTypeLabel(task?.task_type)
                      }}</span>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap">
                      <span class="text-sm text-gray-600 font-medium">
                        {{ formatDate(task?.created_at) }}
                      </span>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-right">
                      <div v-if="task" class="flex justify-end gap-2">
                        <BaseButton
                          variant="primary"
                          size="sm"
                          :loading="task?.uuid && collectingTasks[task.uuid]"
                          @click="handleCollectNow(task)"
                        >
                          {{ t('scheduledTasks.collectNow') }}
                        </BaseButton>
                        <BaseButton
                          variant="outline"
                          size="sm"
                          @click="handleEdit(task)"
                        >
                          {{ t('common.edit') }}
                        </BaseButton>
                        <BaseButton
                          variant="outline"
                          size="sm"
                          @click="handleToggle(task)"
                        >
                          {{
                            task.enabled
                              ? t('scheduledTasks.disable')
                              : t('scheduledTasks.enable')
                          }}
                        </BaseButton>
                        <BaseButton
                          variant="danger"
                          size="sm"
                          @click="handleDeleteClick(task)"
                        >
                          {{ t('common.delete') }}
                        </BaseButton>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Desktop pagination with page size -->
            <div
              v-if="totalCount > 0"
              class="hidden md:flex mt-4 flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4"
            >
              <p class="text-sm text-gray-600">
                {{
                  t('common.pagination.showing', {
                    from: (currentPage - 1) * pageSize + 1,
                    to: Math.min(currentPage * pageSize, totalCount),
                    total: totalCount
                  })
                }}
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
          </template>
        </div>
      </div>

      <!-- Create/Edit Modal -->
      <ScheduledTaskModal
        :show="showModal"
        :task="editingTask"
        @close="handleModalClose"
        @save="handleSave"
        @save-error="handleSaveError"
      />

      <!-- Detail Panel -->
      <ScheduledTaskDetailPanel
        :show="showDetailPanel"
        :task="selectedTask"
        :task-type-label="selectedTaskTypeLabel"
        @close="showDetailPanel = false"
      />

      <!-- Delete Confirmation -->
      <ConfirmDialog
        :show="showDeleteDialog"
        :title="t('scheduledTasks.deleteConfirm')"
        :message="t('scheduledTasks.deleteMessage')"
        :variant="'danger'"
        :loading="deleting"
        @close="showDeleteDialog = false"
        @confirm="handleDeleteConfirm"
      />

      <!-- Batch Delete Confirmation -->
      <ConfirmDialog
        :show="showBatchDeleteDialog"
        :title="t('scheduledTasks.batchDeleteConfirm')"
        :message="
          t('scheduledTasks.batchDeleteMessage', {
            count: selectedTasks.length
          })
        "
        :variant="'danger'"
        :loading="deleting"
        @close="showBatchDeleteDialog = false"
        @confirm="handleBatchDeleteConfirm"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ScheduledTaskCard from '@/components/scheduledTasks/ScheduledTaskCard.vue'
import ScheduledTaskModal from '@/components/scheduledTasks/ScheduledTaskModal.vue'
import ScheduledTaskDetailPanel from '@/components/scheduledTasks/ScheduledTaskDetailPanel.vue'
import { scheduledTasksApi } from '@/api/scheduledTasks'
import { tasksApi } from '@/api/tasks'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { format } from 'date-fns'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const router = useRouter()

const tasks = ref([])
const filteredTasks = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(10)
const showModal = ref(false)
const editingTask = ref(null)
const showDeleteDialog = ref(false)
const deleting = ref(false)
const taskToDelete = ref(null)
const collectingTasks = ref({})
const selectedTasks = ref([])
const searchQuery = ref('')
const statusFilter = ref('')
const showBatchDeleteDialog = ref(false)
const availableTaskTypes = ref([])
const showDetailPanel = ref(false)
const selectedTask = ref(null)
const selectedTaskTypeLabel = ref('')

const loadTaskTypes = async () => {
  try {
    const response = await scheduledTasksApi.getTaskTypes()
    const data = extractResponseData(response)
    availableTaskTypes.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('Failed to load task types:', error)
    availableTaskTypes.value = []
  }
}

const getTaskTypeLabel = (taskType) => {
  if (!taskType) return '-'
  const taskTypeObj = availableTaskTypes.value.find((t) => t.value === taskType)
  return taskTypeObj?.label || taskType.split('.').pop() || '-'
}

const loadTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    const response = await scheduledTasksApi.getScheduledTasks(params)
    const data = extractResponseData(response)

    // Handle different response formats:
    // 1. DRF paginated: {count, next, previous, results: [...]}
    // 2. Direct array: [...]
    // 3. Custom format: {list: [...], pagination: {...}}
    let results = []
    if (Array.isArray(data)) {
      results = data
      totalPages.value = 1
      totalCount.value = data.length
    } else if (data && typeof data === 'object') {
      if (data.results && Array.isArray(data.results)) {
        // Standard DRF pagination format
        results = data.results
        const total = data.count || 0
        totalCount.value = total
        totalPages.value = total > 0 ? Math.ceil(total / pageSize.value) : 1
      } else if (data.list && Array.isArray(data.list)) {
        // Custom pagination format
        results = data.list
        if (data.pagination) {
          const total = data.pagination.total || 0
          totalCount.value = total
          totalPages.value = total > 0 ? Math.ceil(total / pageSize.value) : 1
        }
      } else {
        // Try to find any array-like property
        const arrayKeys = Object.keys(data).filter((key) =>
          Array.isArray(data[key])
        )
        if (arrayKeys.length > 0) {
          results = data[arrayKeys[0]]
          totalPages.value = 1
          totalCount.value = results.length
        }
      }
    }

    // Filter out any null or undefined values
    tasks.value = results.filter((t) => t != null && t !== undefined)
    // Ensure applyFilters is called to update filteredTasks
    applyFilters()
  } catch (error) {
    console.error('Failed to load scheduled tasks:', error)
    showError(extractErrorMessage(error, t('scheduledTasks.loadError')))
    tasks.value = []
    filteredTasks.value = []
    totalPages.value = 1
    totalCount.value = 0
  } finally {
    loading.value = false
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

  if (statusFilter.value) {
    if (statusFilter.value === 'enabled') {
      filtered = filtered.filter((task) => task.enabled === true)
    } else if (statusFilter.value === 'disabled') {
      filtered = filtered.filter((task) => task.enabled === false)
    }
  }

  filteredTasks.value = filtered
  selectedTasks.value = selectedTasks.value.filter((task) =>
    filtered.some((t) => t.uuid === task.uuid)
  )
}

const handleSearch = () => {
  currentPage.value = 1
  loadTasks()
}

const handleFilterChange = () => {
  currentPage.value = 1
  loadTasks()
}

const handlePageSizeChange = () => {
  currentPage.value = 1
  loadTasks()
}

const goPrevPage = () => {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadTasks()
}

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  loadTasks()
}

const handleLoadMore = async () => {
  // For mobile infinite scroll, load next page and append to existing tasks
  if (currentPage.value >= totalPages.value || loadingMore.value) return

  const nextPage = currentPage.value + 1
  loadingMore.value = true

  try {
    const params = {
      page: nextPage,
      page_size: pageSize.value
    }
    const response = await scheduledTasksApi.getScheduledTasks(params)
    const data = extractResponseData(response)

    // Append new tasks to existing list
    let newTasks = []
    if (Array.isArray(data)) {
      newTasks = data
    } else if (data && typeof data === 'object') {
      if (data.results && Array.isArray(data.results)) {
        newTasks = data.results
      } else if (data.list && Array.isArray(data.list)) {
        newTasks = data.list
      } else {
        const arrayKeys = Object.keys(data).filter((key) =>
          Array.isArray(data[key])
        )
        if (arrayKeys.length > 0) {
          newTasks = data[arrayKeys[0]]
        }
      }
    }

    // Filter out any null or undefined values and append to existing tasks
    const validNewTasks = (newTasks || []).filter(
      (t) => t != null && t !== undefined
    )
    if (Array.isArray(tasks.value) && Array.isArray(validNewTasks)) {
      tasks.value = [...tasks.value, ...validNewTasks]
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
      showError(extractErrorMessage(error, t('scheduledTasks.loadError')))
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
  return selectedTasks.value.some((t) => t && t.uuid === task.uuid)
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
    selectedTasks.value = selectedTasks.value.filter(
      (t) => t.uuid !== task.uuid
    )
  }
}

const handleBatchDeleteClick = () => {
  if (selectedTasks.value.length === 0) return
  showBatchDeleteDialog.value = true
}

const handleBatchDeleteConfirm = async () => {
  if (selectedTasks.value.length === 0) return

  deleting.value = true
  try {
    const deletePromises = selectedTasks.value.map((task) =>
      scheduledTasksApi.deleteScheduledTask(task.uuid)
    )
    await Promise.all(deletePromises)
    showSuccess(
      t('scheduledTasks.batchDeleteSuccess', {
        count: selectedTasks.value.length
      })
    )
    showBatchDeleteDialog.value = false
    selectedTasks.value = []
    await loadTasks()
  } catch (error) {
    showError(extractErrorMessage(error, t('scheduledTasks.batchDeleteError')))
  } finally {
    deleting.value = false
  }
}

const handleBatchToggle = async () => {
  if (selectedTasks.value.length === 0) return

  try {
    const togglePromises = selectedTasks.value.map((task) =>
      scheduledTasksApi
        .updateScheduledTask(task.uuid, {
          enabled: !task.enabled
        })
        .then((response) => ({
          uuid: task.uuid,
          updatedTask: extractResponseData(response)
        }))
    )
    const results = await Promise.all(togglePromises)

    // Update each task in local list
    results.forEach(({ uuid, updatedTask }) => {
      const taskIndex = tasks.value.findIndex((t) => t && t.uuid === uuid)
      if (taskIndex !== -1) {
        tasks.value[taskIndex] = updatedTask
      }

      const filteredIndex = filteredTasks.value.findIndex(
        (t) => t && t.uuid === uuid
      )
      if (filteredIndex !== -1) {
        filteredTasks.value[filteredIndex] = updatedTask
      }
    })

    showSuccess(
      t('scheduledTasks.batchToggleSuccess', {
        count: selectedTasks.value.length
      })
    )
    selectedTasks.value = []
  } catch (error) {
    showError(extractErrorMessage(error, t('scheduledTasks.batchToggleError')))
  }
}

const handleCreate = () => {
  editingTask.value = null
  showModal.value = true
}

const handleEdit = (task) => {
  editingTask.value = task
  showModal.value = true
}

const handleViewDetails = async (task) => {
  if (!task || !task.uuid) return

  try {
    // Fetch full task details to ensure we have complete data
    const response = await scheduledTasksApi.getScheduledTask(task.uuid)
    const fullTask = extractResponseData(response)
    selectedTask.value = fullTask || task
    selectedTaskTypeLabel.value = getTaskTypeLabel(
      fullTask?.task_type || task?.task_type
    )
    showDetailPanel.value = true
  } catch (error) {
    console.error('Failed to load task details:', error)
    // Fallback to using the task from the list
    selectedTask.value = task
    selectedTaskTypeLabel.value = getTaskTypeLabel(task?.task_type)
    showDetailPanel.value = true
  }
}

const handleModalClose = () => {
  showModal.value = false
  editingTask.value = null
}

const handleSave = async (taskData) => {
  try {
    if (editingTask.value && editingTask.value.uuid) {
      await scheduledTasksApi.updateScheduledTask(
        editingTask.value.uuid,
        taskData
      )
      showSuccess(t('scheduledTasks.updateSuccess'))
    } else {
      await scheduledTasksApi.createScheduledTask(taskData)
      showSuccess(t('scheduledTasks.createSuccess'))
    }
    handleModalClose()
    await loadTasks()
  } catch (error) {
    showError(extractErrorMessage(error, t('scheduledTasks.saveError')))
    // Error is already handled, modal will reset saving state via watch
  }
}

const handleSaveError = (error) => {
  // Modal already handled the error display
  // This is just for cleanup if needed
}

const handleToggle = async (task) => {
  if (!task || !task.uuid) return
  try {
    const response = await scheduledTasksApi.updateScheduledTask(task.uuid, {
      enabled: !task.enabled
    })
    const updatedTask = extractResponseData(response)

    // Update the task in local list
    const taskIndex = tasks.value.findIndex((t) => t && t.uuid === task.uuid)
    if (taskIndex !== -1) {
      tasks.value[taskIndex] = updatedTask
    }

    // Update filteredTasks if it exists there
    const filteredIndex = filteredTasks.value.findIndex(
      (t) => t && t.uuid === task.uuid
    )
    if (filteredIndex !== -1) {
      filteredTasks.value[filteredIndex] = updatedTask
    }

    showSuccess(t('scheduledTasks.toggleSuccess'))
  } catch (error) {
    showError(extractErrorMessage(error, t('scheduledTasks.toggleError')))
  }
}

const handleDeleteClick = (task) => {
  taskToDelete.value = task
  showDeleteDialog.value = true
}

const handleDeleteConfirm = async () => {
  if (!taskToDelete.value || !taskToDelete.value.uuid) return

  deleting.value = true
  const deletedUuid = taskToDelete.value.uuid

  try {
    const response = await scheduledTasksApi.deleteScheduledTask(deletedUuid)

    // DRF typically returns 204 No Content on successful delete
    // But some APIs may return 200 OK or other success codes
    const isSuccess = response.status >= 200 && response.status < 300

    if (isSuccess) {
      // Remove from local list immediately before showing success
      tasks.value = tasks.value.filter((t) => t && t.uuid !== deletedUuid)
      filteredTasks.value = filteredTasks.value.filter(
        (t) => t && t.uuid !== deletedUuid
      )
      selectedTasks.value = selectedTasks.value.filter(
        (t) => t && t.uuid !== deletedUuid
      )

      showSuccess(t('scheduledTasks.deleteSuccess'))
      showDeleteDialog.value = false
      taskToDelete.value = null

      // Then reload to ensure sync with backend
      await loadTasks()
    } else {
      showError(
        t('scheduledTasks.deleteError') + ` (Status: ${response.status})`
      )
    }
  } catch (error) {
    // Log detailed error for debugging
    if (error.response) {
      console.error('Delete failed - Status:', error.response.status)
      console.error('Delete failed - Data:', error.response.data)
    } else {
      console.error('Delete failed - Error:', error)
    }
    showError(extractErrorMessage(error, t('scheduledTasks.deleteError')))
  } finally {
    deleting.value = false
  }
}

const formatSchedule = (type, value) => {
  if (!value) return '-'

  // Handle crontab schedule
  if (type === 'crontab') {
    const minute =
      value.minute !== undefined ? String(value.minute).padStart(2, '0') : '00'
    const hour = value.hour || '*'
    const dayOfMonth = value.day_of_month || '*'
    const monthOfYear = value.month_of_year || '*'
    const dayOfWeek = value.day_of_week || '*'

    return formatCrontabSchedule(
      minute,
      hour,
      dayOfMonth,
      monthOfYear,
      dayOfWeek
    )
  }

  // Handle interval schedule (legacy support)
  if (type === 'interval' || !type) {
    const period =
      value.period === 'minutes'
        ? t('scheduledTasks.minutes')
        : value.period === 'hours'
          ? t('scheduledTasks.hours')
          : value.period === 'days'
            ? t('scheduledTasks.days')
            : value.period === 'seconds'
              ? t('scheduledTasks.seconds')
              : value.period
    return `${value.every} ${period}`
  }

  return '-'
}

// Helper function to format crontab schedule display
const formatCrontabSchedule = (
  minute,
  hour,
  dayOfMonth,
  monthOfYear,
  dayOfWeek
) => {
  // If only hour and minute are set (default case), use simple format
  if (dayOfMonth === '*' && monthOfYear === '*' && dayOfWeek === '*') {
    if (hour === '*') {
      return t('scheduledTasks.form.previewEveryHour', { minute })
    }
    if (typeof hour === 'string') {
      const hours = hour
        .split(',')
        .map((h) => h.trim())
        .filter((h) => h)
      if (hours.length === 0) return '-'
      if (hours.length === 24) {
        return t('scheduledTasks.form.previewEveryHour', { minute })
      }
      if (hours.length <= 5) {
        const hourDisplay = hours
          .map((h) => String(h).padStart(2, '0'))
          .join(', ')
        return t('scheduledTasks.form.previewSchedule', {
          minute,
          hours: hourDisplay
        })
      }
      const hourDisplay = t('scheduledTasks.form.multipleHours', {
        count: hours.length
      })
      return t('scheduledTasks.form.previewSchedule', {
        minute,
        hours: hourDisplay
      })
    }
    return t('scheduledTasks.form.previewSchedule', {
      minute,
      hours: String(hour).padStart(2, '0')
    })
  }

  // Build detailed display for complex schedules
  const parts = []

  if (monthOfYear !== '*') {
    const months = monthOfYear
      .split(',')
      .map((m) => m.trim())
      .filter((m) => m)
    if (months.length === 1) {
      parts.push(months[0] + t('scheduledTasks.form.monthUnit'))
    } else if (months.length <= 3) {
      parts.push(months.join(',') + t('scheduledTasks.form.monthUnit'))
    } else {
      parts.push(
        t('scheduledTasks.form.multipleMonths', { count: months.length })
      )
    }
  }

  if (dayOfMonth !== '*') {
    const days = dayOfMonth
      .split(',')
      .map((d) => d.trim())
      .filter((d) => d)
    if (days.length === 1) {
      parts.push(days[0] + t('scheduledTasks.form.dayUnit'))
    } else if (days.length <= 3) {
      parts.push(days.join(',') + t('scheduledTasks.form.dayUnit'))
    } else {
      parts.push(t('scheduledTasks.form.multipleDays', { count: days.length }))
    }
  }

  if (dayOfWeek !== '*') {
    const dayNames = t('scheduledTasks.form.dayOfWeekNames').split(',')
    const days = dayOfWeek.split(',').map((d) => {
      const dayNum = parseInt(d.trim())
      if (dayNum === 0 || dayNum === 7) return dayNames[0]
      if (dayNum >= 1 && dayNum <= 6) return dayNames[dayNum]
      return d
    })
    parts.push(days.join(','))
  }

  // Add time part
  let hourStr = ''
  if (hour === '*') {
    hourStr = t('scheduledTasks.form.everyHour')
  } else if (typeof hour === 'string') {
    const hours = hour.split(',').map((h) => String(h.trim()).padStart(2, '0'))
    hourStr = hours.join(',') + t('scheduledTasks.form.hourUnit')
  } else {
    hourStr = String(hour).padStart(2, '0') + t('scheduledTasks.form.hourUnit')
  }
  parts.push(hourStr)
  parts.push(minute + t('scheduledTasks.form.minuteUnit'))

  return parts.join(' ') + t('scheduledTasks.form.execute')
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const handleCollectNow = async (task) => {
  if (!task || !task.uuid) return

  const taskUuid = task.uuid

  if (collectingTasks.value[taskUuid]) {
    showError(t('scheduledTasks.collectAlreadyRunning'))
    return
  }

  collectingTasks.value[taskUuid] = true

  try {
    // Fetch full task details to get kwargs
    const fullTaskResponse = await scheduledTasksApi.getScheduledTask(task.uuid)
    const fullTask = extractResponseData(fullTaskResponse)
    const kwargs = fullTask?.kwargs || {}

    const taskType = fullTask?.task_type || ''

    // Handle GitHub trending tasks
    if (taskType === 'github_trending.collect_github_trendings') {
      try {
        const taskTypeLabel = getTaskTypeLabel(taskType)
        const taskTypeName = taskTypeLabel
          ? taskTypeLabel.replace(/\s+/g, '')
          : 'GitHubTrending'
        const taskNameParts = [`[Manual]${taskTypeName}`]

        if (kwargs.since) {
          taskNameParts.push(kwargs.since)
        }
        if (kwargs.lang && kwargs.lang !== 'any') {
          taskNameParts.push(kwargs.lang)
        }
        if (kwargs.lang_code && kwargs.lang_code !== 'any') {
          taskNameParts.push(kwargs.lang_code)
        }

        // Add timestamp
        const now = new Date()
        const timestamp =
          now.getFullYear().toString().slice(-2) +
          String(now.getMonth() + 1).padStart(2, '0') +
          String(now.getDate()).padStart(2, '0') +
          String(now.getHours()).padStart(2, '0') +
          String(now.getMinutes()).padStart(2, '0') +
          String(now.getSeconds()).padStart(2, '0')
        taskNameParts.push(timestamp)

        const collectParams = {
          lang_code: kwargs.lang_code || 'any',
          lang: kwargs.lang || 'any',
          since: kwargs.since || 'today',
          num: kwargs.num || 20,
          name: taskNameParts.join('_')
        }

        // Include social_account and transform_formats if available
        if (kwargs.social_account) {
          collectParams.social_account = kwargs.social_account
        }
        if (kwargs.transform_formats) {
          collectParams.transform_formats = kwargs.transform_formats
        }

        const response = await tasksApi.collectGithubTrendings(collectParams)
        const data = extractResponseData(response)

        showSuccess(t('scheduledTasks.collectStarted'))

        setTimeout(() => {
          collectingTasks.value[taskUuid] = false
          router.push('/tasks')
        }, 1500)
        return
      } catch (error) {
        const errorMessage = extractErrorMessage(
          error,
          t('scheduledTasks.collectError')
        )

        // Check if error is related to GitHub token configuration
        const isTokenError =
          errorMessage.toLowerCase().includes('token') ||
          errorMessage.toLowerCase().includes('configure')

        if (isTokenError) {
          showError(t('scheduledTasks.githubTokenNotConfigured'))
        } else {
          showError(errorMessage)
        }

        collectingTasks.value[taskUuid] = false
        return
      }
    }

    // Handle Google News tasks
    if (!kwargs.keywords && !kwargs.topics) {
      showError(t('scheduledTasks.collectErrorNoParams'))
      collectingTasks.value[taskUuid] = false
      return
    }

    // Generate task name with [Manual] prefix
    // Format: [Manual] + task type label + parameter info
    // Note: [Manual] is joined without underscore
    const taskTypeLabel = getTaskTypeLabel(taskType)
    const taskTypeName = taskTypeLabel
      ? taskTypeLabel.replace(/\s+/g, '')
      : 'Task'
    const taskNameParts = [`[Manual]${taskTypeName}`]

    if (kwargs.keywords && kwargs.keywords.length > 0) {
      const keywords = kwargs.keywords.slice(0, 3)
      taskNameParts.push(keywords.join('_'))
    } else if (kwargs.topics && kwargs.topics.length > 0) {
      taskNameParts.push(kwargs.topics[0])
    }

    if (kwargs.social_account) {
      taskNameParts.push(kwargs.social_account)
    }

    // Add timestamp
    const now = new Date()
    const timestamp =
      now.getFullYear().toString().slice(-2) +
      String(now.getMonth() + 1).padStart(2, '0') +
      String(now.getDate()).padStart(2, '0') +
      String(now.getHours()).padStart(2, '0') +
      String(now.getMinutes()).padStart(2, '0') +
      String(now.getSeconds()).padStart(2, '0')
    taskNameParts.push(timestamp)

    const collectParams = {
      keywords: kwargs.keywords || [],
      topics: kwargs.topics || [],
      count: kwargs.count || 10,
      source_language: kwargs.source_language || kwargs.language || 'en',
      source_region: kwargs.source_region || kwargs.region || 'US',
      period: kwargs.period || '7d',
      name: taskNameParts.join('_')
    }

    // Include additional parameters from ScheduleTask kwargs
    // These are important for proper task execution (e.g., transform_formats, social_account)
    if (kwargs.social_account) {
      collectParams.social_account = kwargs.social_account
    }
    if (kwargs.transform_formats) {
      collectParams.transform_formats = kwargs.transform_formats
    }

    const response = await tasksApi.collectArticles(collectParams)
    const data = extractResponseData(response)

    showSuccess(t('scheduledTasks.collectStarted'))

    setTimeout(() => {
      collectingTasks.value[taskUuid] = false
      router.push('/tasks')
    }, 1500)
  } catch (error) {
    const errorMessage = extractErrorMessage(
      error,
      t('scheduledTasks.collectError')
    )
    showError(errorMessage)
    collectingTasks.value[taskUuid] = false
  }
}

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

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  await loadTaskTypes()
  await loadTasks()

  // Setup intersection observer for mobile infinite scroll
  if (isMobile.value) {
    nextTick(() => {
      setupIntersectionObserver()
    })
  }
})

onUnmounted(() => {
  try {
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
</script>
