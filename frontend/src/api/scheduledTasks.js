import api from './index'
import { extractResponseData, extractErrorMessage } from '@/utils/api'

export const scheduledTasksApi = {
  // Get scheduled tasks list
  getScheduledTasks(params = {}) {
    return api.get('/articlehub/scheduled-tasks', { params })
  },

  // Get single scheduled task by UUID
  getScheduledTask(uuid) {
    return api.get(`/articlehub/scheduled-tasks/${uuid}`)
  },

  // Get available task types
  getTaskTypes() {
    return api.get('/articlehub/scheduled-tasks/task_types')
  },

  // Create new scheduled task
  createScheduledTask(data) {
    return api.post('/articlehub/scheduled-tasks', data)
  },

  // Update scheduled task
  updateScheduledTask(uuid, data) {
    return api.patch(`/articlehub/scheduled-tasks/${uuid}`, data)
  },

  // Delete scheduled task
  deleteScheduledTask(uuid) {
    return api.delete(`/articlehub/scheduled-tasks/${uuid}`)
  }
}

export const {
  getScheduledTasks,
  getScheduledTask,
  createScheduledTask,
  updateScheduledTask,
  deleteScheduledTask
} = scheduledTasksApi
