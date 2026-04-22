<template>
  <!-- Overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="show"
      @click="handleClose"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40"
    />
  </Transition>

  <!-- Center Modal -->
  <Transition
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition-all duration-150 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
    >
      <div
        class="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col pointer-events-auto"
        @click.stop
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0 rounded-t-lg"
        >
          <h2 class="text-lg font-semibold text-gray-900">
            {{ t('tasks.details') }}
          </h2>
          <button
            @click="handleClose"
            class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <svg
              class="w-5 h-5"
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
        </div>

        <!-- Content - Scrollable -->
        <div class="flex-1 overflow-y-auto min-h-0">
          <div v-if="task" class="p-6 space-y-6">
            <div>
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('tasks.basicInfo') }}
              </h3>
              <dl class="grid grid-cols-1 gap-4">
                <div>
                  <dt
                    class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                  >
                    {{ t('tasks.name') }}
                  </dt>
                  <dd class="text-sm font-medium text-gray-900">
                    {{ task.name }}
                  </dd>
                </div>
                <div>
                  <dt
                    class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                  >
                    {{ t('tasks.statusLabel') }}
                  </dt>
                  <dd>
                    <StatusBadge :status="mapStatus(task.status)" />
                  </dd>
                </div>
                <div>
                  <dt
                    class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                  >
                    {{ t('tasks.startedAt') }}
                  </dt>
                  <dd class="text-sm font-medium text-gray-900">
                    {{ formatDate(task.started_at) }}
                  </dd>
                </div>
                <div>
                  <dt
                    class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                  >
                    {{ t('tasks.finishedAt') }}
                  </dt>
                  <dd class="text-sm font-medium text-gray-900">
                    {{ formatDate(task.finished_at) }}
                  </dd>
                </div>
                <div>
                  <dt
                    class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                  >
                    {{ t('tasks.createdAt') }}
                  </dt>
                  <dd class="text-sm font-medium text-gray-900">
                    {{ formatDate(task.created_at) }}
                  </dd>
                </div>
              </dl>
            </div>

            <div v-if="task.last_error" class="border-t border-gray-200 pt-6">
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('tasks.error') }}
              </h3>
              <div
                class="bg-red-50 border border-red-200 rounded-lg p-4 shadow-sm"
              >
                <pre
                  class="text-xs font-medium text-red-800 whitespace-pre-wrap"
                  >{{ task.last_error }}</pre
                >
              </div>
            </div>

            <div
              v-if="task.result && Object.keys(task.result).length > 0"
              class="border-t border-gray-200 pt-6"
            >
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('tasks.result') }}
              </h3>
              <div class="space-y-3">
                <!-- Formatted Result Display -->
                <div
                  v-if="formattedResult"
                  class="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-4 shadow-sm"
                >
                  <div
                    v-for="(value, key) in formattedResult"
                    :key="key"
                    class="flex items-start"
                  >
                    <span
                      class="text-sm font-semibold text-gray-700 min-w-[140px]"
                      >{{ key }}:</span
                    >
                    <span
                      class="text-sm font-medium text-gray-900 flex-1 break-words"
                      :class="Array.isArray(value) ? 'block' : ''"
                    >
                      <template v-if="Array.isArray(value)">
                        <div class="space-y-2">
                          <span
                            v-for="(item, idx) in value"
                            :key="idx"
                            class="inline-block bg-white px-2.5 py-1 rounded-full text-xs font-medium border border-gray-200 shadow-sm mr-2 mb-1"
                          >
                            {{ item }}
                          </span>
                        </div>
                      </template>
                      <template v-else>
                        {{ value }}
                      </template>
                    </span>
                  </div>
                </div>
                <!-- Statistics with Progress Bars -->
                <div
                  v-if="statisticsData"
                  class="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4 shadow-sm"
                >
                  <!-- Collected Count -->
                  <div v-if="statisticsData.collected > 0">
                    <div class="flex items-center justify-between mb-2">
                      <span
                        class="text-xs font-semibold text-gray-700 uppercase tracking-wider"
                      >
                        {{ t('tasks.collectedCount') }}
                      </span>
                      <span class="text-sm font-semibold text-gray-900">
                        {{ statisticsData.collected }}
                      </span>
                    </div>
                  </div>

                  <!-- Success Progress -->
                  <div v-if="statisticsData.total > 0">
                    <div class="flex items-center justify-between mb-2">
                      <span
                        class="text-xs font-semibold text-gray-700 uppercase tracking-wider"
                      >
                        {{ t('tasks.success') }}
                      </span>
                      <span class="text-sm font-semibold text-green-700">
                        {{ statisticsData.successful }} /
                        {{ statisticsData.total }}
                      </span>
                    </div>
                    <div
                      class="w-full bg-gray-200 rounded-full h-2.5 shadow-inner"
                    >
                      <div
                        class="bg-green-600 h-2.5 rounded-full transition-all shadow-sm"
                        :style="{
                          width: `${statisticsData.successPercentage}%`
                        }"
                      />
                    </div>
                  </div>

                  <!-- Failed Progress -->
                  <div v-if="statisticsData.failed > 0">
                    <div class="flex items-center justify-between mb-2">
                      <span
                        class="text-xs font-semibold text-gray-700 uppercase tracking-wider"
                      >
                        {{ t('tasks.failed') }}
                      </span>
                      <span class="text-sm font-semibold text-red-700">
                        {{ statisticsData.failed }} / {{ statisticsData.total }}
                      </span>
                    </div>
                    <div
                      class="w-full bg-gray-200 rounded-full h-2.5 shadow-inner"
                    >
                      <div
                        class="bg-red-600 h-2.5 rounded-full transition-all shadow-sm"
                        :style="{
                          width: `${statisticsData.failedPercentage}%`
                        }"
                      />
                    </div>
                  </div>

                  <!-- Success Rate -->
                  <div
                    v-if="statisticsData.total > 0"
                    class="pt-3 border-t border-gray-200"
                  >
                    <div class="flex items-center justify-between">
                      <span
                        class="text-xs font-semibold text-gray-700 uppercase tracking-wider"
                      >
                        {{ t('tasks.successRate') }}
                      </span>
                      <span class="text-sm font-semibold text-primary-700">
                        {{ statisticsData.successRate }}%
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Failure Reasons -->
                <div
                  v-if="failureReasons && failureReasons.length > 0"
                  class="border-t border-gray-200 pt-4"
                >
                  <h4
                    class="text-xs font-semibold text-gray-900 mb-3 uppercase tracking-wider"
                  >
                    {{ t('tasks.failureReasons') }}
                  </h4>
                  <div
                    class="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm"
                  >
                    <table class="min-w-full divide-y divide-gray-200">
                      <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                        <tr>
                          <th
                            class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                          >
                            {{ t('tasks.reason') }}
                          </th>
                          <th
                            class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                          >
                            {{ t('tasks.count') }}
                          </th>
                        </tr>
                      </thead>
                      <tbody class="bg-white divide-y divide-gray-100">
                        <tr
                          v-for="(item, index) in failureReasons"
                          :key="index"
                          class="transition-colors duration-150 hover:bg-gray-50"
                        >
                          <td
                            class="px-4 py-4 text-sm font-medium text-gray-900"
                          >
                            {{ item.reason }}
                          </td>
                          <td
                            class="px-4 py-4 text-sm font-semibold text-red-600 text-right"
                          >
                            {{ item.count }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- Raw Data -->
                <div
                  class="bg-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm"
                >
                  <details class="cursor-pointer">
                    <summary class="text-xs font-semibold text-gray-700 mb-2">
                      {{ t('tasks.viewRawData') }}
                    </summary>
                    <pre
                      class="text-xs font-mono text-gray-800 whitespace-pre-wrap mt-3 bg-white p-3 rounded border border-gray-200"
                      >{{ JSON.stringify(task.result, null, 2) }}</pre
                    >
                  </details>
                </div>
              </div>
            </div>

            <div
              v-if="task.parameters && Object.keys(task.parameters).length > 0"
              class="border-t border-gray-200 pt-6"
            >
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('tasks.parameters') }}
              </h3>
              <div
                class="bg-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm"
              >
                <pre
                  class="text-xs font-mono font-medium text-gray-800 whitespace-pre-wrap"
                  >{{ JSON.stringify(task.parameters, null, 2) }}</pre
                >
              </div>
            </div>

            <div
              v-if="task.steps && task.steps.length > 0"
              class="border-t border-gray-200 pt-6"
            >
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('tasks.steps') }}
              </h3>
              <div class="space-y-3">
                <div
                  v-for="(step, index) in task.steps"
                  :key="index"
                  class="border border-gray-200 rounded-lg p-4 bg-white shadow-sm transition-shadow hover:shadow-md"
                >
                  <div class="text-sm font-semibold text-gray-900 mb-2">
                    {{ step.step || step.name || `Step ${index + 1}` }}
                  </div>
                  <div
                    v-if="step.message"
                    class="text-sm font-medium text-gray-700"
                  >
                    {{ step.message }}
                  </div>
                  <div
                    v-if="step.timestamp"
                    class="text-xs font-medium text-gray-500 mt-2"
                  >
                    {{ formatDate(step.timestamp) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { format } from 'date-fns'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  task: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()

const resultStats = computed(() => {
  if (!props.task || !props.task.result) return {}
  try {
    return getResultStats(props.task.result) || {}
  } catch (error) {
    console.error('Error computing resultStats:', error)
    return {}
  }
})

const failureReasons = computed(() => {
  if (!props.task || !props.task.result) return []
  try {
    return getFailureReasons(props.task.result) || []
  } catch (error) {
    console.error('Error computing failureReasons:', error)
    return []
  }
})

const formattedResult = computed(() => {
  if (!props.task || !props.task.result) return null

  const result = props.task.result
  const taskType = props.task.parameters?.task_type || ''
  const taskName = props.task.name || ''

  // Format OSS_SCAN task results
  if (taskType === 'OSS_SCAN') {
    const formatted = {}
    if (result.scanned_count !== undefined) {
      formatted[t('tasks.scannedCount')] = result.scanned_count
    }
    if (result.published_count !== undefined) {
      formatted[t('tasks.publishedCount')] = result.published_count
    }
    if (result.users_processed !== undefined) {
      formatted[t('tasks.usersProcessed')] = result.users_processed
    }
    if (
      result.articles &&
      Array.isArray(result.articles) &&
      result.articles.length > 0
    ) {
      formatted[t('tasks.publishedArticles')] = result.articles.length
      formatted[t('tasks.articleList')] = result.articles.map((a) =>
        a.title
          ? `${a.id} (${a.title.substring(0, 30)}${a.title.length > 30 ? '...' : ''})`
          : a.id
      )
    }
    if (Object.keys(formatted).length > 0) {
      return formatted
    }
  }

  // Format CLEANUP task results
  if (taskType === 'CLEANUP') {
    const formatted = {}
    if (result.cleaned_count !== undefined) {
      formatted[t('tasks.cleanedCount')] = result.cleaned_count
    }
    if (result.users_processed !== undefined) {
      formatted[t('tasks.usersProcessed')] = result.users_processed
    }
    if (result.total_size_freed !== undefined) {
      formatted[t('tasks.sizeFreed')] = formatFileSize(result.total_size_freed)
    }
    if (Object.keys(formatted).length > 0) {
      return formatted
    }
  }

  return null
})

const statisticsData = computed(() => {
  if (!props.task || !props.task.result) return null

  const result = props.task.result
  const statistics = result.statistics || {}

  const successful =
    statistics.successful ??
    result.successful_count ??
    result.success_count ??
    result.processed_count ??
    0
  const failed = statistics.failed ?? result.failed_count ?? 0
  const collected =
    statistics.total ??
    result.collected_count ??
    result.article_source_count ??
    successful + failed

  const total = successful + failed || collected

  if (total === 0 && collected === 0) return null

  const successPercentage =
    total > 0 ? Math.round((successful / total) * 100) : 0
  const failedPercentage = total > 0 ? Math.round((failed / total) * 100) : 0
  const successRate =
    statistics.success_rate ??
    (total > 0 ? ((successful / total) * 100).toFixed(1) : 0)

  return {
    collected,
    successful,
    failed,
    total,
    successPercentage,
    failedPercentage,
    successRate
  }
})

const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const formattedParameters = computed(() => {
  if (!props.task || !props.task.parameters) return null

  const params = props.task.parameters
  const formatted = {}

  // Format task_type
  if (params.task_type) {
    formatted.task_type = params.task_type
  }

  // Format scan_hours if exists
  if (params.scan_hours !== undefined) {
    formatted.scan_hours = `${params.scan_hours} ${t('tasks.durationHours')}`
  }

  // Format collection task parameters
  if (params.query_keywords && Array.isArray(params.query_keywords)) {
    formatted.query_keywords = params.query_keywords.join(', ')
  }

  if (params.query_topics && Array.isArray(params.query_topics)) {
    formatted.query_topics = params.query_topics.join(', ')
  }

  if (params.count !== undefined) {
    formatted.count = params.count
  }

  if (params.source_language) {
    formatted.source_language = params.source_language
  }

  if (params.source_region) {
    formatted.source_region = params.source_region
  }

  if (params.period) {
    formatted.period = params.period
  }

  if (params.social_account) {
    formatted.social_account = params.social_account
  }

  // Only return formatted if we have something to show
  if (Object.keys(formatted).length > 0) {
    return formatted
  }

  return null
})

const formatParameterKey = (key) => {
  const keyMap = {
    task_type: t('tasks.taskType'),
    scan_hours: t('tasks.scanHours'),
    query_keywords: t('tasks.queryKeywords'),
    query_topics: t('tasks.queryTopics'),
    count: t('tasks.count'),
    source_language: t('tasks.sourceLanguage'),
    source_region: t('tasks.sourceRegion'),
    period: t('tasks.period'),
    social_account: t('tasks.socialAccount')
  }
  return keyMap[key] || key
}

const formatParameterValue = (value) => {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const mapStatus = (status) => {
  if (!status) return 'pending'
  const statusMap = {
    pending: 'pending',
    running: 'processing',
    completed: 'completed',
    failed: 'failed',
    partial: 'pending'
  }
  return statusMap[status] || 'pending'
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    if (typeof dateString === 'string' && dateString.includes('T')) {
      return format(new Date(dateString), 'yyyy-MM-dd HH:mm:ss')
    }
    return dateString
  } catch {
    return dateString
  }
}

const handleClose = () => {
  emit('close')
}

const getResultStats = (result) => {
  if (!result || typeof result !== 'object') return {}

  const stats = {}

  // Check for nested statistics object
  const statistics = result.statistics || {}

  // Extract counts from statistics or direct properties
  const total =
    statistics.total ?? result.total_count ?? result.article_source_count ?? 0
  const successful =
    statistics.successful ??
    result.successful_count ??
    result.success_count ??
    result.processed_count ??
    0
  const failed = statistics.failed ?? result.failed_count ?? 0
  const skipped = statistics.skipped ?? result.skipped_count ?? 0
  const collected =
    result.collected_count ?? result.article_source_count ?? total

  // Check for arrays that indicate counts
  if (Array.isArray(result.processed_articles)) {
    const count = result.processed_articles.length
    if (count > 0 && successful === 0) {
      stats[t('tasks.processedCount')] = count
    }
  }
  if (Array.isArray(result.failed_articles)) {
    const count = result.failed_articles.length
    if (count > 0 && failed === 0) {
      stats[t('tasks.failedCount')] = count
    }
  }
  if (Array.isArray(result.article_source_ids)) {
    const count = result.article_source_ids.length
    if (count > 0 && collected === 0) {
      stats[t('tasks.collectedCount')] = count
    }
  }

  // Set collected count
  if (collected > 0) {
    stats[t('tasks.collectedCount')] = collected
  }

  // Set successful count
  if (successful > 0) {
    stats[t('tasks.successCount')] = successful
  }

  // Set failed count
  if (failed > 0) {
    stats[t('tasks.failedCount')] = failed
  }

  // Set skipped count
  if (skipped > 0) {
    stats[t('tasks.skippedCount')] = skipped
  }

  // Calculate total from available counts
  const finalTotal = total || successful + failed + skipped || collected
  if (finalTotal > 0) {
    stats[t('tasks.totalCount')] = finalTotal

    // Calculate success rate
    if (statistics.success_rate !== undefined) {
      stats[t('tasks.successRate')] = `${statistics.success_rate}%`
    } else if (finalTotal > 0 && successful > 0) {
      const successRate = ((successful / finalTotal) * 100).toFixed(1)
      stats[t('tasks.successRate')] = `${successRate}%`
    }
  }

  // Success flag
  if (typeof result.success === 'boolean') {
    stats[t('tasks.overallStatus')] = result.success
      ? t('tasks.success')
      : t('tasks.failed')
  }

  return stats
}

const getFailureReasons = (result) => {
  if (!result || typeof result !== 'object') return []

  const reasons = []
  const statistics = result.statistics || {}

  // Extract error reasons
  if (
    statistics.error_reasons &&
    typeof statistics.error_reasons === 'object'
  ) {
    Object.entries(statistics.error_reasons).forEach(([reason, count]) => {
      if (count > 0) {
        reasons.push({
          reason,
          count
        })
      }
    })
  }

  // Extract skip reasons
  if (statistics.skip_reasons && typeof statistics.skip_reasons === 'object') {
    Object.entries(statistics.skip_reasons).forEach(([reason, count]) => {
      if (count > 0) {
        reasons.push({
          reason,
          count,
          type: 'skip'
        })
      }
    })
  }

  return reasons
}
</script>
