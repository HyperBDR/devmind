<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handleViewDetails"
  >
    <div class="p-4">
      <h3 class="text-sm font-semibold text-gray-900 mb-3 line-clamp-2">
        {{ task.name || task.task_name || '-' }}
      </h3>

      <p
        v-if="task.platform || task.config_key"
        class="text-xs text-gray-500 mb-2"
      >
        <span v-if="task.platform">{{ task.platform }}</span>
        <span v-if="task.platform && task.config_key"> · </span>
        <span v-if="task.config_key">{{ task.config_key }}</span>
      </p>

      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <StatusBadge :status="mapTaskStatus(task.status)" />
          <span class="text-xs text-gray-500">
            {{ formatDate(task.started_at || task.created_at) }}
          </span>
        </div>
        <div
          v-if="task.duration || (task.started_at && task.finished_at)"
          class="flex items-center justify-between"
        >
          <span class="text-xs text-gray-500">{{
            t('dataCollector.tasks.duration')
          }}</span>
          <span class="text-sm font-medium text-gray-900">
            {{
              formatDuration(
                task.duration ||
                  calculateDuration(
                    task.started_at || task.created_at,
                    task.finished_at
                  )
              )
            }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { formatDuration } from '@/utils/formatting'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view'])

const { t } = useI18n()

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const calculateDuration = (startTime, endTime) => {
  if (!startTime || !endTime) return null
  try {
    const start = new Date(startTime)
    const end = new Date(endTime)
    return Math.floor((end - start) / 1000)
  } catch {
    return null
  }
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

const handleViewDetails = () => {
  emit('view', props.task)
}
</script>
