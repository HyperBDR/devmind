<template>
  <div class="p-6">
    <div
      class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
    >
      <div class="flex items-center gap-2 flex-wrap"></div>
      <div class="flex items-center gap-3 w-full sm:w-auto">
        <BaseButton
          variant="outline"
          size="sm"
          :loading="loading"
          :disabled="loading"
          class="flex items-center gap-1.5"
          @click="loadConfigs"
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
          {{ t('common.refresh') }}
        </BaseButton>
        <BaseButton
          @click="showCreateModal = true"
          size="sm"
          class="flex items-center gap-1.5"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          {{ t('dataCollector.settings.addConfig') }}
        </BaseButton>
      </div>
    </div>

    <BaseLoading v-if="loading" size="lg" variant="primary" />

    <template v-else>
      <div
        v-if="configs.length === 0"
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
            d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
          />
        </svg>
        <p class="text-sm font-medium text-gray-600">
          {{ t('dataCollector.settings.noConfigs') }}
        </p>
      </div>

      <template v-else>
        <div
          class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
        >
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
              <tr>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200 w-1/4 min-w-[160px]"
                >
                  {{ t('dataCollector.settings.key') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('dataCollector.settings.platform') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('dataCollector.settings.scheduleCron') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('common.status.enabled') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('cloudBilling.providers.createdAt') }}
                </th>
                <th
                  class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('common.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-100">
              <tr
                v-for="c in configs"
                :key="c.uuid"
                class="transition-colors duration-150 hover:bg-gray-50"
              >
                <td class="px-4 py-3">
                  <div class="text-sm font-medium text-gray-900 break-words">
                    {{ c.key }}
                  </div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {{ getPlatformLabel(c.platform) }}
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {{ c.schedule_cron || '0 */2 * * *' }}
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <label
                    class="relative inline-flex items-center cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      :checked="c.is_enabled"
                      @change="toggleEnabled(c, $event.target.checked)"
                      class="sr-only peer"
                      :disabled="togglingIds.includes(c.uuid)"
                    />
                    <div
                      class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"
                    />
                  </label>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDate(c.updated_at) }}
                </td>
                <td
                  class="px-4 py-3 whitespace-nowrap text-right text-sm font-medium"
                >
                  <div class="flex items-center justify-end gap-2">
                    <button
                      v-if="
                        c.platform === 'jira' ||
                        c.platform === 'feishu' ||
                        c.platform === 'license' ||
                        c.platform === 'hyperbdr' ||
                        c.platform === 'ai_pricehub'
                      "
                      @click="openFullEdit(c)"
                      class="text-amber-600 hover:text-amber-900 transition-colors"
                      :title="t('dataCollector.settings.editConfig')"
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
                          d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964a6 6 0 117.743 7.743z"
                        />
                      </svg>
                    </button>
                    <button
                      @click="openSectionEdit(c, 'schedule')"
                      class="text-primary-600 hover:text-primary-900 transition-colors"
                      :title="
                        t('dataCollector.settings.editScheduleAndRetention')
                      "
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
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </button>
                    <button
                      @click="openCollectModal(c)"
                      class="text-blue-600 hover:text-blue-900 transition-colors"
                      :title="t('dataCollector.settings.triggerCollect')"
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
                    </button>
                    <button
                      @click="deleteConfig(c)"
                      class="text-red-600 hover:text-red-900 transition-colors"
                      :title="t('common.delete')"
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
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="md:hidden space-y-3">
          <div
            v-for="c in configs"
            :key="c.uuid"
            class="bg-white rounded-lg border border-gray-200 shadow-sm p-4"
          >
            <div class="flex items-start justify-between mb-3">
              <div class="flex-1">
                <h3 class="text-sm font-semibold text-gray-900 mb-1">
                  {{ c.key }}
                </h3>
                <p class="text-xs text-gray-500">
                  {{ getPlatformLabel(c.platform) }}
                </p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="c.is_enabled"
                  @change="toggleEnabled(c, $event.target.checked)"
                  class="sr-only peer"
                  :disabled="togglingIds.includes(c.uuid)"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600 peer-disabled:opacity-50"
                />
              </label>
            </div>
            <div class="text-xs text-gray-500 mb-3">
              {{ t('dataCollector.settings.scheduleCron') }}:
              {{ c.schedule_cron || '0 */2 * * *' }}
            </div>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                v-if="
                  c.platform === 'jira' ||
                  c.platform === 'feishu' ||
                  c.platform === 'license' ||
                  c.platform === 'hyperbdr' ||
                  c.platform === 'ai_pricehub'
                "
                variant="outline"
                size="sm"
                @click="openFullEdit(c)"
                >{{ t('dataCollector.settings.editConfig') }}</BaseButton
              >
              <BaseButton
                variant="outline"
                size="sm"
                @click="openSectionEdit(c, 'schedule')"
                >{{
                  t('dataCollector.settings.editScheduleAndRetention')
                }}</BaseButton
              >
              <BaseButton
                variant="outline"
                size="sm"
                @click="openCollectModal(c)"
                >{{ t('dataCollector.settings.triggerCollect') }}</BaseButton
              >
              <BaseButton
                variant="outline"
                size="sm"
                class="text-red-600"
                @click="deleteConfig(c)"
                >{{ t('common.delete') }}</BaseButton
              >
            </div>
          </div>
        </div>
      </template>
    </template>

    <CollectorConfigFormModal
      v-if="
        showCreateModal ||
        (editingConfig &&
          (editSection === 'full' || editSection === 'schedule'))
      "
      :show="
        showCreateModal ||
        !!(
          editingConfig &&
          (editSection === 'full' || editSection === 'schedule')
        )
      "
      :config="showCreateModal ? null : editingConfig"
      :edit-section="editSection"
      @close="closeModal"
      @saved="handleSaved"
      @section-saved="handleSectionSaved"
    />

    <BaseModal
      :show="showCollectModal"
      :title="t('dataCollector.settings.collectRangeTitle')"
      @close="closeCollectModal"
    >
      <div class="space-y-4">
        <p class="text-sm text-gray-600">
          {{ t('dataCollector.settings.collectRangeDesc') }}
        </p>
        <div>
          <label
            for="collect-range-select"
            class="block text-sm font-medium text-gray-700 mb-1"
            >{{ t('dataCollector.settings.collectRangeLabel') }}</label
          >
          <select
            id="collect-range-select"
            v-model="collectRange"
            class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option
              v-for="opt in collectRangeOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
        <template v-if="collectRange === 'custom'">
          <div class="grid grid-cols-2 gap-4 pt-2 border-t border-gray-200">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{
                t('dataCollector.settings.customStartDate')
              }}</label>
              <input
                v-model="customStartDate"
                type="date"
                :max="feishuDateMax"
                :min="feishuDateMin"
                class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{
                t('dataCollector.settings.customEndDate')
              }}</label>
              <input
                v-model="customEndDate"
                type="date"
                :max="feishuDateMax"
                :min="feishuDateMin"
                class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
          <p v-if="collectRangeError" class="text-sm text-red-600">
            {{ collectRangeError }}
          </p>
        </template>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <BaseButton variant="outline" @click="closeCollectModal">{{
            t('common.cancel')
          }}</BaseButton>
          <BaseButton
            variant="primary"
            :disabled="!!collectRangeError || submittingCollect"
            @click="confirmCollect"
          >
            {{
              submittingCollect
                ? t('common.submitting')
                : t('dataCollector.settings.startCollect')
            }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { format, subDays, startOfDay, endOfDay } from 'date-fns'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { dataCollectorApi } from '@/api/dataCollector'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import CollectorConfigFormModal from '@/components/data-collector/CollectorConfigFormModal.vue'

const router = useRouter()
const { t } = useI18n()
const { showSuccess, showError } = useToast()
const loading = ref(true)
const configs = ref([])
const showCreateModal = ref(false)
const editingConfig = ref(null)
const editSection = ref(null)
const togglingIds = ref([])
const showCollectModal = ref(false)
const collectConfig = ref(null)
const collectRange = ref('1w')
const customStartDate = ref('')
const customEndDate = ref('')
const submittingCollect = ref(false)

const collectRangeOptions = computed(() => {
  const platform = collectConfig.value?.platform
  if (platform === 'feishu') {
    return [
      { value: '1w', label: t('dataCollector.settings.collectRange1w') },
      { value: '1m', label: t('dataCollector.settings.collectRange1m') },
      { value: 'custom', label: t('dataCollector.settings.collectRangeCustom') }
    ]
  }
  return [
    { value: '1w', label: t('dataCollector.settings.collectRange1w') },
    { value: '1m', label: t('dataCollector.settings.collectRange1m') },
    { value: '3m', label: t('dataCollector.settings.collectRange3m') },
    { value: 'custom', label: t('dataCollector.settings.collectRangeCustom') }
  ]
})

const feishuDateMax = computed(() => {
  const platform = collectConfig.value?.platform
  if (platform !== 'feishu') return null
  const today = new Date()
  return format(today, 'yyyy-MM-dd')
})

const feishuDateMin = computed(() => {
  const platform = collectConfig.value?.platform
  if (platform !== 'feishu') return null
  const today = new Date()
  const min = subDays(today, 30)
  return format(min, 'yyyy-MM-dd')
})

const collectRangeError = computed(() => {
  if (collectRange.value !== 'custom') return ''
  const start = customStartDate.value
  const end = customEndDate.value
  if (!start || !end)
    return t('dataCollector.settings.collectRangeCustomRequired')
  const startD = new Date(start)
  const endD = new Date(end)
  if (startD > endD) return t('dataCollector.settings.collectRangeCustomOrder')
  const days = (endD - startD) / (24 * 60 * 60 * 1000)
  const platform = collectConfig.value?.platform
  const maxDays = platform === 'feishu' ? 30 : 90
  if (days > maxDays) {
    return platform === 'feishu'
      ? t('dataCollector.settings.collectRangeMax30Days')
      : t('dataCollector.settings.collectRangeMax3Months')
  }
  return ''
})

const platformLabels = {
  jira: 'Jira'
}

function getPlatformLabel(platform) {
  if (platform === 'feishu') return t('dataCollector.platforms.feishu')
  if (platform === 'license') return t('dataCollector.platforms.license')
  if (platform === 'hyperbdr') return t('dataCollector.platforms.hyperbdr')
  if (platform === 'ai_pricehub')
    return t('dataCollector.platforms.ai_pricehub')
  return platformLabels[platform] || platform
}

function formatDate(dateString) {
  if (!dateString) return ''
  return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
}

async function loadConfigs() {
  loading.value = true
  try {
    const res = await dataCollectorApi.getConfigs()
    const data = extractResponseData(res)
    const list =
      data?.results ?? data?.list ?? (Array.isArray(data) ? data : [])
    configs.value = list
  } catch (e) {
    configs.value = []
  } finally {
    loading.value = false
  }
}

async function openFullEdit(c) {
  editSection.value = 'full'
  try {
    const res = await dataCollectorApi.getConfig(c.uuid)
    const full = extractResponseData(res)
    editingConfig.value = { ...c, ...full, value: full?.value ?? {} }
  } catch (e) {
    editSection.value = null
    showError(extractErrorMessage(e, t('common.error')))
  }
}

async function openSectionEdit(c, section) {
  editSection.value = section
  try {
    const res = await dataCollectorApi.getConfig(c.uuid)
    const full = extractResponseData(res)
    editingConfig.value = { ...c, ...full, value: full?.value ?? {} }
  } catch (e) {
    editSection.value = null
    showError(extractErrorMessage(e, t('common.error')))
  }
}

function closeModal() {
  showCreateModal.value = false
  editingConfig.value = null
  editSection.value = null
}

function handleSaved() {
  closeModal()
  loadConfigs()
}

function handleSectionSaved(config) {
  editingConfig.value = config
  closeModal()
  loadConfigs()
}

async function toggleEnabled(c, enabled) {
  togglingIds.value.push(c.uuid)
  try {
    const payload = {
      key: c.key,
      value: c.value || {},
      is_enabled: enabled,
      version: c.version
    }
    await dataCollectorApi.patchConfig(c.uuid, payload)
    const idx = configs.value.findIndex((x) => x.uuid === c.uuid)
    if (idx !== -1) configs.value[idx].is_enabled = enabled
    showSuccess(
      enabled
        ? t('dataCollector.settings.enableSuccess')
        : t('dataCollector.settings.disableSuccess')
    )
  } catch (e) {
    showError(extractErrorMessage(e, t('common.error')))
  } finally {
    togglingIds.value = togglingIds.value.filter((id) => id !== c.uuid)
  }
}

function openCollectModal(c) {
  collectConfig.value = c
  collectRange.value = '1w'
  customStartDate.value = ''
  customEndDate.value = ''
  showCollectModal.value = true
}

function closeCollectModal() {
  showCollectModal.value = false
  collectConfig.value = null
}

function computeCollectRangeTimes() {
  const now = new Date()
  if (collectRange.value === '1w') {
    return {
      start_time: subDays(now, 7).toISOString(),
      end_time: now.toISOString()
    }
  }
  if (collectRange.value === '1m') {
    return {
      start_time: subDays(now, 30).toISOString(),
      end_time: now.toISOString()
    }
  }
  if (collectRange.value === '3m') {
    return {
      start_time: subDays(now, 90).toISOString(),
      end_time: now.toISOString()
    }
  }
  const start = startOfDay(new Date(customStartDate.value))
  const end = endOfDay(new Date(customEndDate.value))
  return { start_time: start.toISOString(), end_time: end.toISOString() }
}

async function confirmCollect() {
  if (collectRangeError.value || !collectConfig.value) return
  submittingCollect.value = true
  try {
    const payload = computeCollectRangeTimes()
    const res = await dataCollectorApi.triggerCollect(
      collectConfig.value.uuid,
      payload
    )
    const data = extractResponseData(res)
    const taskId = data?.task_id
    showSuccess(t('dataCollector.settings.collectTriggered'))
    closeCollectModal()
    loadConfigs()
    if (taskId) {
      router.push({
        path: '/data-collector/tasks',
        query: { task_id: taskId }
      })
    }
  } catch (e) {
    showError(extractErrorMessage(e, t('common.error')))
  } finally {
    submittingCollect.value = false
  }
}

function deleteConfig(c) {
  if (!confirm(t('dataCollector.settings.confirmDelete'))) return
  dataCollectorApi
    .deleteConfig(c.uuid)
    .then(() => {
      showSuccess(t('dataCollector.settings.deleteSuccess'))
      loadConfigs()
    })
    .catch((e) => {
      showError(extractErrorMessage(e, t('common.error')))
    })
}

onMounted(() => {
  loadConfigs()
})
</script>
