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

      <!-- Schedule Time, Status, Type and Menu Button -->
      <div class="flex flex-col gap-2">
        <!-- Schedule Time and Status -->
        <div class="space-y-1.5">
          <!-- Schedule Time -->
          <div v-if="scheduleText" class="text-sm text-gray-600 font-medium">
            {{ scheduleText }}
          </div>
          <!-- Status -->
          <div>
            <StatusBadge :status="task?.enabled ? 'enabled' : 'disabled'" />
          </div>
        </div>

        <!-- Task Type and Menu Button -->
        <div class="flex items-center justify-between gap-2">
          <!-- Task Type -->
          <div v-if="taskTypeLabel">
            <span
              class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
            >
              {{ taskTypeLabel }}
            </span>
          </div>

          <!-- Menu Button and Dropdown -->
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
                  v-if="task"
                  @click="handleAction('collect', $event)"
                  :disabled="collecting"
                  class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  {{ t('scheduledTasks.collectNow') }}
                </button>
                <button
                  v-if="task"
                  @click="handleAction('edit', $event)"
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
                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                    />
                  </svg>
                  {{ t('common.edit') }}
                </button>
                <button
                  v-if="task"
                  @click="handleAction('toggle', $event)"
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
                      d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
                    />
                  </svg>
                  {{
                    task.enabled
                      ? t('scheduledTasks.disable')
                      : t('scheduledTasks.enable')
                  }}
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  },
  taskTypeLabel: {
    type: String,
    default: ''
  },
  collecting: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['view', 'collect', 'edit', 'toggle', 'delete'])

const { t } = useI18n()

const showMenu = ref(false)
const menuRef = ref(null)
const buttonRef = ref(null)
const menuStyle = ref({})

const scheduleText = computed(() => {
  if (!props.task) return ''
  return formatSchedule(props.task.schedule_type, props.task.schedule_value)
})

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const formatSchedule = (type, value) => {
  if (!value) return ''

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

  return ''
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
      if (hours.length === 0) return ''
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
  } else if (action === 'collect') {
    emit('collect', props.task)
  } else if (action === 'edit') {
    emit('edit', props.task)
  } else if (action === 'toggle') {
    emit('toggle', props.task)
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
