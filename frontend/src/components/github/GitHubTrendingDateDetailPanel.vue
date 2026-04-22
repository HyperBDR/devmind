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
      class="fixed inset-y-0 right-0 w-full max-w-3xl bg-white shadow-xl z-50 flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0"
      >
        <h2 class="text-base font-semibold text-gray-900">
          {{
            t('githubTrending.dateDetail.title', {
              date: formatDate(selectedDate)
            })
          }}
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
        <BaseLoading v-if="loading" />

        <div v-else-if="dateRecords && dateRecords.length > 0" class="p-4">
          <!-- Tabs -->
          <div>
            <div class="border-b border-gray-200">
              <nav class="-mb-px flex space-x-4 overflow-x-auto">
                <button
                  v-for="tab in availableTabs"
                  :key="tab.id"
                  :class="[
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                    'whitespace-nowrap py-2 px-3 border-b-2 font-medium text-sm flex items-center gap-2'
                  ]"
                  @click="activeTab = tab.id"
                >
                  <span>{{ tab.icon }}</span>
                  <span>{{ tab.label }}</span>
                  <span class="text-xs text-gray-400">
                    ({{ getRecordsByPeriod(tab.id).length }}
                    {{ t('githubTrending.dateDetail.projects') }})
                  </span>
                </button>
              </nav>
            </div>

            <div class="mt-4">
              <!-- Table for active tab -->
              <div
                class="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm"
              >
                <table class="min-w-full divide-y divide-gray-200">
                  <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                    <tr>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.rank') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.project') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.language') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.stars') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.forks') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.starGrowth') }}
                      </th>
                      <th
                        class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                      >
                        {{ t('githubTrending.table.rankChange') }}
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-100">
                    <tr
                      v-for="record in getRecordsByPeriod(activeTab)"
                      :key="record.id"
                      class="transition-colors duration-150 hover:bg-gray-50"
                    >
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span class="text-sm font-semibold text-gray-900">
                          #{{ record.trending_rank }}
                        </span>
                      </td>
                      <td class="px-4 py-4">
                        <button
                          @click="handleViewProject(record.project_id)"
                          class="text-sm font-semibold text-primary-600 hover:text-primary-800 text-left transition-colors"
                        >
                          {{ record.project_name }}
                        </button>
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span
                          v-if="record.project_language"
                          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
                        >
                          {{ record.project_language }}
                        </span>
                        <span v-else class="text-sm text-gray-400">-</span>
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span class="text-sm text-gray-900 font-medium">
                          {{ formatNumber(record.project_stargazers_count) }}
                        </span>
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span class="text-sm text-gray-900 font-medium">
                          {{ formatNumber(record.project_forks_count) }}
                        </span>
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span
                          v-if="record.star_growth !== null"
                          :class="[
                            'text-sm font-semibold',
                            record.star_growth >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          ]"
                        >
                          {{ record.star_growth >= 0 ? '+' : ''
                          }}{{ formatNumber(record.star_growth) }}
                        </span>
                        <span v-else class="text-sm text-gray-400">-</span>
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <span
                          v-if="record.rank_change !== null"
                          :class="[
                            'text-sm font-semibold',
                            record.rank_change > 0
                              ? 'text-green-600'
                              : record.rank_change < 0
                                ? 'text-red-600'
                                : 'text-gray-600'
                          ]"
                        >
                          {{
                            record.rank_change > 0
                              ? '↑'
                              : record.rank_change < 0
                                ? '↓'
                                : '→'
                          }}
                          {{
                            record.rank_change !== 0
                              ? Math.abs(record.rank_change)
                              : ''
                          }}
                        </span>
                        <span v-else class="text-sm text-gray-400">-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="py-8 text-center">
          <p class="text-sm text-gray-600">
            {{ t('githubTrending.dateDetail.noRecords') }}
          </p>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { githubApi } from '@/api/github'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  selectedDate: {
    type: Date,
    default: null
  }
})

const emit = defineEmits(['close', 'view-project'])

const { t, locale } = useI18n()
const { showError } = useToast()

const dateRecords = ref([])
const loading = ref(false)
const activeTab = ref('today')

const allTabs = [
  { id: 'today', label: t('githubTrending.filter.today'), icon: '📅' },
  { id: 'weekly', label: t('githubTrending.filter.weekly'), icon: '📆' },
  { id: 'monthly', label: t('githubTrending.filter.monthly'), icon: '📊' }
]

const availableTabs = computed(() => {
  return allTabs.filter((tab) => getRecordsByPeriod(tab.id).length > 0)
})

const loadDateRecords = async () => {
  if (!props.selectedDate) {
    dateRecords.value = []
    return
  }

  loading.value = true
  try {
    const dateStr = formatDateForAPI(props.selectedDate)
    const response = await githubApi.getTrendingRecords({
      trending_date: dateStr,
      page_size: 1000,
      ordering: 'trending_period,trending_rank'
    })
    const data = extractResponseData(response)

    if (data && data.results) {
      dateRecords.value = data.results
    } else {
      dateRecords.value = Array.isArray(data) ? data : []
    }

    // Set active tab to first available period
    if (dateRecords.value.length > 0) {
      // Find first period with data
      const periods = ['today', 'weekly', 'monthly']
      for (const period of periods) {
        if (getRecordsByPeriod(period).length > 0) {
          activeTab.value = period
          break
        }
      }
    }
  } catch (error) {
    const errorMsg = extractErrorMessage(error)
    showError(errorMsg || t('githubTrending.dateDetail.loadError'))
    dateRecords.value = []
  } finally {
    loading.value = false
  }
}

const formatDateForAPI = (date) => {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const formatDate = (date) => {
  if (!date) return '-'
  const d = date instanceof Date ? date : new Date(date)
  if (locale.value === 'zh-CN') {
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  }
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const formatNumber = (num) => {
  if (num === null || num === undefined) return '-'
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

const getRecordsByPeriod = (period) => {
  if (!dateRecords.value || dateRecords.value.length === 0) return []
  return dateRecords.value
    .filter((record) => record.trending_period === period)
    .sort((a, b) => a.trending_rank - b.trending_rank)
}

const handleClose = () => {
  emit('close')
}

const handleViewProject = (projectId) => {
  emit('view-project', projectId)
}

watch(
  () => props.show,
  (newVal) => {
    if (newVal && props.selectedDate) {
      loadDateRecords()
    }
  }
)

watch(
  () => props.selectedDate,
  () => {
    if (props.show && props.selectedDate) {
      loadDateRecords()
    }
  }
)
</script>
