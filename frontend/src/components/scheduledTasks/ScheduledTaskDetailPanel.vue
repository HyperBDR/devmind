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

  <!-- Right Panel -->
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-250 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0"
      >
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('scheduledTasks.details') }}
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
      <div class="flex-1 overflow-y-auto">
        <div v-if="task" class="p-6 space-y-6">
          <!-- Basic Information -->
          <div>
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('scheduledTasks.basicInfo') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.name') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.name }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.taskType') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ taskTypeLabel }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.status') }}
                </dt>
                <dd>
                  <StatusBadge
                    :status="task.enabled ? 'success' : 'disabled'"
                  />
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.createdAt') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatDate(task.created_at) }}
                </dd>
              </div>
              <div v-if="task.updated_at">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.updatedAt') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatDate(task.updated_at) }}
                </dd>
              </div>
              <div v-if="task.start_time">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.startTime') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatDate(task.start_time) }}
                </dd>
              </div>
            </dl>
          </div>

          <!-- Schedule Configuration -->
          <div class="border-t border-gray-200 pt-6">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('scheduledTasks.scheduleConfig') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.scheduleType') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{
                    task.schedule_type === 'crontab'
                      ? t('scheduledTasks.crontab')
                      : t('scheduledTasks.interval')
                  }}
                </dd>
              </div>
              <div v-if="task.schedule_value">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.scheduleValue') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{
                    formatScheduleDisplay(
                      task.schedule_type,
                      task.schedule_value
                    )
                  }}
                </dd>
              </div>
            </dl>
          </div>

          <!-- Task Parameters -->
          <div
            v-if="task.kwargs && Object.keys(task.kwargs).length > 0"
            class="border-t border-gray-200 pt-6"
          >
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('scheduledTasks.taskParameters') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <!-- Keywords -->
              <div
                v-if="task.kwargs.keywords && task.kwargs.keywords.length > 0"
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.keywords') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="(keyword, index) in task.kwargs.keywords"
                      :key="index"
                      class="inline-block bg-gray-100 px-2.5 py-1 rounded-full text-xs font-medium border border-gray-200 shadow-sm"
                    >
                      {{ keyword }}
                    </span>
                  </div>
                </dd>
              </div>

              <!-- Topics -->
              <div v-if="task.kwargs.topics && task.kwargs.topics.length > 0">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.topics') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="(topic, index) in task.kwargs.topics"
                      :key="index"
                      class="inline-block bg-gray-100 px-2.5 py-1 rounded-full text-xs font-medium border border-gray-200 shadow-sm"
                    >
                      {{ topic }}
                    </span>
                  </div>
                </dd>
              </div>

              <!-- Count -->
              <div v-if="task.kwargs.count !== undefined">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.count') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.kwargs.count }}
                </dd>
              </div>

              <!-- Source Language -->
              <div v-if="task.kwargs.source_language">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.sourceLanguage') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.kwargs.source_language }}
                </dd>
              </div>

              <!-- Source Region -->
              <div v-if="task.kwargs.source_region">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.sourceRegion') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.kwargs.source_region }}
                </dd>
              </div>

              <!-- Period -->
              <div v-if="task.kwargs.period">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.period') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.kwargs.period }}
                </dd>
              </div>

              <!-- Social Account -->
              <div v-if="task.kwargs.social_account">
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.socialAccount') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ task.kwargs.social_account }}
                </dd>
              </div>

              <!-- Transform Formats -->
              <div
                v-if="
                  task.kwargs.transform_formats &&
                  task.kwargs.transform_formats.length > 0
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('scheduledTasks.form.transformFormats') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="(format, index) in task.kwargs.transform_formats"
                      :key="index"
                      class="inline-block bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full text-xs font-semibold border border-blue-200 shadow-sm"
                    >
                      {{ getTransformFormatLabel(format) }}
                    </span>
                  </div>
                </dd>
              </div>
            </dl>
          </div>

          <!-- Raw JSON View -->
          <div class="border-t border-gray-200 pt-6">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('scheduledTasks.rawData') }}
            </h3>
            <div
              class="bg-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm"
            >
              <details class="cursor-pointer">
                <summary class="text-xs font-semibold text-gray-700 mb-2">
                  {{ t('scheduledTasks.viewRawData') }}
                </summary>
                <pre
                  class="text-xs font-mono font-medium text-gray-800 whitespace-pre-wrap mt-3 bg-white p-3 rounded border border-gray-200 overflow-x-auto"
                  >{{ JSON.stringify(task, null, 2) }}</pre
                >
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
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
  },
  taskTypeLabel: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm:ss')
  } catch {
    return dateString
  }
}

const formatScheduleDisplay = (type, value) => {
  if (!value) return '-'

  if (type === 'crontab') {
    const minute =
      value.minute !== undefined ? String(value.minute).padStart(2, '0') : '00'
    let hourDisplay = ''

    if (value.hour === '*') {
      return t('scheduledTasks.form.previewEveryHour', { minute })
    } else if (typeof value.hour === 'string') {
      const hours = value.hour
        .split(',')
        .map((h) => h.trim())
        .filter((h) => h)
      if (hours.length === 0) {
        return '-'
      } else if (hours.length === 24) {
        return t('scheduledTasks.form.previewEveryHour', { minute })
      } else if (hours.length <= 5) {
        hourDisplay = hours.map((h) => String(h).padStart(2, '0')).join(', ')
        return t('scheduledTasks.form.previewSchedule', {
          minute,
          hours: hourDisplay
        })
      } else {
        hourDisplay = t('scheduledTasks.form.multipleHours', {
          count: hours.length
        })
        return t('scheduledTasks.form.previewSchedule', {
          minute,
          hours: hourDisplay
        })
      }
    } else {
      hourDisplay = value.hour || '*'
    }

    return t('scheduledTasks.form.scheduleFormat', {
      minute,
      hour: hourDisplay
    })
  }

  if (type === 'interval') {
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
    return `${value.every || 0} ${period}`
  }

  return '-'
}

const getTransformFormatLabel = (format) => {
  if (format === 'markdown_json') {
    return t('scheduledTasks.form.markdownJson')
  } else if (format === 'toutiao') {
    return t('scheduledTasks.form.toutiao')
  } else if (format === 'wechat_html') {
    return t('scheduledTasks.form.wechatHtml')
  } else if (format === 'douyin_markdown') {
    return t('scheduledTasks.form.douyinMarkdownJson')
  }
  return format
}

const handleClose = () => {
  emit('close')
}
</script>
