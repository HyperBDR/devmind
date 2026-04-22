<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handleViewDetails"
  >
    <!-- Task Card Content -->
    <div class="p-4">
      <!-- Title -->
      <h3 class="text-sm font-semibold text-gray-900 mb-3 line-clamp-2">
        {{ task?.name || '-' }}
      </h3>

      <!-- Time and Status Information -->
      <div class="space-y-2">
        <!-- Created Time (First Row) -->
        <div v-if="task?.created_at" class="text-sm text-gray-500">
          {{ t('tasks.createdAt') }}: {{ formatRelativeTime(task.created_at) }}
        </div>

        <!-- Duration (Second Row) -->
        <div v-if="task?.started_at" class="text-sm text-gray-500">
          {{ t('tasks.duration') }}: {{ formatDuration(task) }}
        </div>

        <!-- Status, Success Count and Menu Button (Third Row) -->
        <div class="flex items-center justify-between gap-2 relative">
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <!-- Status Badge -->
            <StatusBadge :status="mapStatus(task?.status)" />

            <!-- Success Count -->
            <span
              v-if="getSuccessCount(task) !== '-'"
              class="text-sm text-gray-500"
            >
              {{ t('tasks.successCount') }}: {{ getSuccessCount(task) }}
            </span>
          </div>

          <!-- Menu Button -->
          <div
            :ref="
              (el) => {
                if (el) menuRef = el
              }
            "
            class="relative flex-shrink-0"
          >
            <button
              :ref="
                (el) => {
                  if (el) buttonRef = el
                }
              "
              @click.stop="handleMenuClick"
              class="p-1 text-gray-400 hover:text-gray-600 transition-colors"
              :title="t('common.moreActions')"
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
                  d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
                />
              </svg>
            </button>

            <!-- Dropdown Menu -->
            <Transition
              enter-active-class="transition ease-out duration-100"
              enter-from-class="transform opacity-0 scale-95"
              enter-to-class="transform opacity-100 scale-100"
              leave-active-class="transition ease-in duration-75"
              leave-from-class="transform opacity-100 scale-100"
              leave-to-class="transform opacity-0 scale-95"
            >
              <div
                v-if="showMenu"
                class="fixed z-[100] w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1"
                :style="menuStyle"
              >
                <button
                  @click="handleAction('view', $event)"
                  class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
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
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                    />
                  </svg>
                  {{ t('common.viewDetails') }}
                </button>
                <button
                  @click="handleAction('delete', $event)"
                  class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
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
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  {{ t('common.delete') }}
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view', 'delete'])

const { t } = useI18n()

const showMenu = ref(false)
const menuRef = ref(null)
const buttonRef = ref(null)
const menuStyle = ref({})

const mapStatus = (status) => {
  if (!status) return 'processing'
  const statusMap = {
    pending: 'processing',
    running: 'processing',
    completed: 'completed',
    failed: 'failed',
    partial: 'processing'
  }
  return statusMap[status] || 'processing'
}

const formatRelativeTime = (dateString) => {
  if (!dateString) return '-'
  try {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) {
      return t('time.justNow')
    } else if (diffMins < 60) {
      return t('time.minutesAgo', { count: diffMins })
    } else if (diffHours < 24) {
      return t('time.hoursAgo', { count: diffHours })
    } else if (diffDays < 7) {
      return t('time.daysAgo', { count: diffDays })
    } else {
      return format(date, 'yyyy-MM-dd')
    }
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

  if (task.success_count !== undefined && task.success_count !== null) {
    return task.success_count > 0 ? task.success_count : '-'
  }

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

const handleViewDetails = () => {
  emit('view', props.task)
}

const handleMenuClick = (event) => {
  event.stopPropagation()
  if (!showMenu.value && buttonRef.value) {
    const rect = buttonRef.value.getBoundingClientRect()
    menuStyle.value = {
      top: `${rect.bottom + 4}px`,
      right: `${window.innerWidth - rect.right}px`
    }
  }
  showMenu.value = !showMenu.value
}

const handleAction = (action, event) => {
  if (event) {
    event.stopPropagation()
  }
  showMenu.value = false

  if (action === 'view') {
    emit('view', props.task)
  } else if (action === 'delete') {
    emit('delete', props.task)
  }
}

const handleClickOutside = (event) => {
  if (
    showMenu.value &&
    menuRef.value &&
    !menuRef.value.contains(event.target)
  ) {
    showMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>
