<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('dataCollector.tasks.title') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('dataCollector.tasks.subtitle') }}
        </p>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar: same as CloudBilling/Tasks -->
          <div
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <div class="flex items-center gap-3 flex-wrap">
              <!-- Optional left actions (e.g. trigger) can go here -->
            </div>

            <div class="flex items-center gap-3 w-full sm:w-auto flex-wrap">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('dataCollector.tasks.searchPlaceholder')"
                class="flex-1 min-w-[140px] sm:w-44"
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

              <span class="flex items-center gap-1.5 shrink-0">
                <span class="text-sm text-gray-600"
                  >{{ t('dataCollector.tasks.filterPlatform') }}：</span
                >
                <select
                  v-model="platformFilter"
                  :aria-label="t('dataCollector.tasks.filterPlatform')"
                  class="block px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 min-w-[100px]"
                  @change="onFilterChange"
                >
                  <option value="">
                    {{ t('dataCollector.tasks.filterAll') }}
                  </option>
                  <option value="jira">
                    {{ t('dataCollector.platforms.jira') }}
                  </option>
                  <option value="feishu">
                    {{ t('dataCollector.platforms.feishu') }}
                  </option>
                  <option value="license">
                    {{ t('dataCollector.platforms.license') }}
                  </option>
                  <option value="hyperbdr">
                    {{ t('dataCollector.platforms.hyperbdr') }}
                  </option>
                  <option value="ai_pricehub">
                    {{ t('dataCollector.platforms.ai_pricehub') }}
                  </option>
                </select>
              </span>

              <span class="flex items-center gap-1.5 shrink-0">
                <span class="text-sm text-gray-600"
                  >{{ t('dataCollector.tasks.filterConfigName') }}：</span
                >
                <select
                  v-model="configKeyFilter"
                  :aria-label="t('dataCollector.tasks.filterConfigName')"
                  class="block px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 min-w-[120px]"
                  @change="onFilterChange"
                >
                  <option value="">
                    {{ t('dataCollector.tasks.filterAll') }}
                  </option>
                  <option v-for="c in configList" :key="c.uuid" :value="c.key">
                    {{ c.key }}
                  </option>
                </select>
              </span>

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
              {{ t('dataCollector.tasks.noTasks') }}
            </p>
          </div>

          <!-- Mobile Card View -->
          <div v-if="tasks.length > 0" class="md:hidden space-y-3 relative">
            <div
              v-if="loading"
              class="absolute inset-0 bg-white/70 flex items-center justify-center z-10 rounded-lg"
            >
              <BaseLoading size="lg" variant="primary" />
            </div>
            <CollectorExecutionCard
              v-for="task in tasks"
              :key="task.id"
              :task="task"
              @view="handlePreview"
            />
          </div>

          <!-- Desktop Table View -->
          <div
            v-if="tasks.length > 0"
            class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <div
              v-if="loading"
              class="absolute inset-0 bg-white/70 flex items-center justify-center z-10 rounded-lg"
            >
              <BaseLoading size="lg" variant="primary" />
            </div>
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.tasks.taskName') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.records.platform') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.settings.key') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.tasks.status') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.tasks.startTime') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.tasks.endTime') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('dataCollector.tasks.duration') }}
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
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ getPlatformLabel(task.platform) || '—' }}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ task.config_key || '—' }}
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
                    {{ formatDurationDisplay(task.duration) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="totalCount > 0"
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
                @change="onPageSizeChange"
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

      <CollectorExecutionDetailPanel
        :show="showPreviewModal"
        :task="selectedTask"
        @close="showPreviewModal = false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useDebounce } from '@/composables/useDebounce'
import { formatDuration } from '@/utils/formatting'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import CollectorExecutionCard from '@/components/data-collector/CollectorExecutionCard.vue'
import CollectorExecutionDetailPanel from '@/components/data-collector/CollectorExecutionDetailPanel.vue'
import { dataCollectorApi } from '@/api/dataCollector'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const platformLabels = {
  jira: 'Jira'
}

function getPlatformLabel(platform) {
  if (!platform) return ''
  if (platform === 'feishu') return t('dataCollector.platforms.feishu')
  if (platform === 'license') return t('dataCollector.platforms.license')
  if (platform === 'hyperbdr') return t('dataCollector.platforms.hyperbdr')
  if (platform === 'ai_pricehub')
    return t('dataCollector.platforms.ai_pricehub')
  return platformLabels[platform] || platform
}

const loading = ref(false)
const tasks = ref([])
const searchQuery = ref('')
const platformFilter = ref('')
const configKeyFilter = ref('')
const configList = ref([])
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

const formatDurationDisplay = (seconds) => {
  if (seconds == null || seconds === '') return '-'
  return formatDuration(seconds)
}

const mapTaskStatus = (status) => {
  const statusMap = {
    pending: 'pending',
    running: 'processing',
    completed: 'success',
    failed: 'failed',
    PENDING: 'pending',
    STARTED: 'processing',
    SUCCESS: 'success',
    FAILURE: 'failed',
    RETRY: 'processing',
    REVOKED: 'failed'
  }
  return statusMap[status] || status?.toLowerCase() || 'pending'
}

const { debouncedFn: debouncedSearch } = useDebounce(() => {
  currentPage.value = 1
  loadTasks(1)
}, 300)

const handleSearch = (query) => {
  searchQuery.value = query
  debouncedSearch()
}

function onFilterChange() {
  currentPage.value = 1
  loadTasks(1)
}

const handleRefresh = () => {
  loadTasks(currentPage.value)
}

const goPrevPage = () => {
  if (currentPage.value <= 1) return
  currentPage.value--
  loadTasks(currentPage.value)
}

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value++
  loadTasks(currentPage.value)
}

function onPageSizeChange() {
  currentPage.value = 1
  loadTasks(1)
}

function extractData(res) {
  return res?.data?.data ?? res?.data ?? res
}

function isDetailTaskRunning(task) {
  if (!task || task.status == null) return false
  const s = String(task.status).toUpperCase()
  return s === 'PENDING' || s === 'STARTED' || s === 'RETRY' || s === 'RUNNING'
}

const hasRunningTasks = computed(() =>
  tasks.value.some((t) => t.status === 'processing' || t.status === 'pending')
)

const pollListWhenRunning = useIntervalFn(
  () => {
    if (!hasRunningTasks.value) return
    loadTasks(currentPage.value)
  },
  4000,
  { immediate: false }
)

watch(
  hasRunningTasks,
  (running) => {
    if (running) pollListWhenRunning.resume()
    else pollListWhenRunning.pause()
  },
  { immediate: true }
)

const pollDetailExecution = useIntervalFn(
  async () => {
    const task = selectedTask.value
    if (!showPreviewModal.value || !task?.id || !isDetailTaskRunning(task))
      return
    try {
      const res = await dataCollectorApi.getExecution(task.id)
      const data = extractData(res)
      if (data) {
        const updated = {
          id: data.id,
          task_id: data.task_id ?? task.task_id,
          task_name: data.task_name ?? task.name,
          name: data.task_name ?? task.name,
          status: data.status ?? task.status,
          created_at: data.created_at ?? task.created_at,
          started_at: data.started_at ?? task.started_at,
          finished_at: data.finished_at ?? task.finished_at,
          duration: data.duration ?? task.duration,
          result: data.result,
          error: data.error ?? task.error,
          traceback: data.traceback,
          metadata: data.metadata ?? task.metadata
        }
        selectedTask.value = updated
        const idx = tasks.value.findIndex((t) => t.id === task.id)
        if (idx !== -1) {
          const meta = updated.metadata || {}
          tasks.value = [
            ...tasks.value.slice(0, idx),
            {
              ...tasks.value[idx],
              name: updated.task_name ?? updated.name ?? tasks.value[idx].name,
              status: mapTaskStatus(updated.status),
              finished_at: updated.finished_at,
              duration:
                updated.duration ??
                calculateDuration(
                  updated.started_at ?? updated.created_at,
                  updated.finished_at
                ),
              result: updated.result,
              error: updated.error,
              metadata: updated.metadata,
              platform: meta.config_platform,
              config_key: meta.config_key
            },
            ...tasks.value.slice(idx + 1)
          ]
        }
      }
    } catch {
      // Ignore poll errors
    }
  },
  4000,
  { immediate: false }
)

watch(
  [
    showPreviewModal,
    () => selectedTask.value?.id,
    () => selectedTask.value?.status
  ],
  () => {
    if (
      showPreviewModal.value &&
      selectedTask.value?.id &&
      isDetailTaskRunning(selectedTask.value)
    ) {
      pollDetailExecution.resume()
    } else {
      pollDetailExecution.pause()
    }
  },
  { immediate: true }
)

async function handlePreview(task) {
  if (!task?.id) return
  try {
    const res = await dataCollectorApi.getExecution(task.id)
    const data = extractData(res)
    selectedTask.value = {
      id: data.id,
      task_id: data.task_id ?? task.task_id,
      task_name: data.task_name ?? task.name,
      name: data.task_name ?? task.name,
      status: data.status ?? task.status,
      created_at: data.created_at ?? task.created_at,
      started_at: data.started_at ?? task.started_at,
      finished_at: data.finished_at ?? task.finished_at,
      duration: data.duration ?? task.duration,
      result: data.result,
      error: data.error ?? task.error,
      traceback: data.traceback,
      metadata: data.metadata || task.metadata
    }
    showPreviewModal.value = true
  } catch {
    selectedTask.value = { ...task }
    showPreviewModal.value = true
  }
}

async function loadTasks(page = currentPage.value) {
  loading.value = true
  try {
    const params = {
      page,
      page_size: pageSize.value
    }
    const searchTerm =
      searchQuery.value != null ? String(searchQuery.value).trim() : ''
    if (searchTerm) {
      params.search = searchTerm
    }
    if (platformFilter.value) {
      params.config_platform = platformFilter.value
    }
    if (configKeyFilter.value) {
      params.config_key = configKeyFilter.value
    }
    const res = await dataCollectorApi.getExecutions(params)
    const data = extractData(res)
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
      name: task.task_name || task.name || '-',
      status: mapTaskStatus(task.status),
      started_at: task.started_at || task.created_at,
      finished_at: task.finished_at,
      duration:
        task.duration ??
        calculateDuration(task.started_at || task.created_at, task.finished_at),
      task_id: task.task_id,
      result: task.result,
      error: task.error,
      metadata: task.metadata,
      platform: task.metadata?.config_platform,
      config_key: task.metadata?.config_key
    }))
  } catch (e) {
    tasks.value = []
  } finally {
    loading.value = false
    const q = route.query?.task_id
    if (q && tasks.value.length) {
      const found = tasks.value.find((x) => x.task_id === q)
      if (found) {
        nextTick(() => {
          handlePreview(found)
          router.replace({ path: route.path, query: {} })
        })
      }
    }
  }
}

function calculateDuration(startTime, endTime) {
  if (!startTime || !endTime) return null
  try {
    const start = new Date(startTime)
    const end = new Date(endTime)
    return Math.floor((end - start) / 1000)
  } catch {
    return null
  }
}

async function loadConfigs() {
  try {
    const res = await dataCollectorApi.getConfigs()
    const data = extractData(res)
    const list =
      data?.results ?? data?.list ?? (Array.isArray(data) ? data : [])
    configList.value = list
      .map((c) => ({ uuid: c.uuid, key: c.key || '' }))
      .filter((c) => c.key)
  } catch {
    configList.value = []
  }
}

onMounted(() => {
  loadConfigs()
  loadTasks()
})

onUnmounted(() => {
  pollDetailExecution.pause()
  pollListWhenRunning.pause()
})
</script>
