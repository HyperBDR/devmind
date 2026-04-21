<template>
  <AppLayout>
    <div class="w-full max-w-full">
      <!-- Page Header -->
      <div class="mb-4 flex items-center justify-between">
        <div class="flex-1 min-w-0">
          <h1 class="text-lg font-semibold text-gray-900 truncate">
            {{ t('githubTrending.title') }}
          </h1>
          <p class="text-sm text-gray-500 mt-1 truncate">
            {{ t('githubTrending.description') }}
          </p>
        </div>
      </div>

      <!-- Toolbar -->
      <div class="bg-white rounded border border-gray-200 shadow-sm p-4 mb-4">
        <div
          class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <!-- Left spacer for alignment -->
          <div class="flex items-center gap-2 flex-wrap"></div>

          <!-- Search and Filter (Right) -->
          <div class="flex items-center gap-3 w-full sm:w-auto">
            <BaseInput
              v-model="searchQuery"
              :placeholder="t('githubTrending.searchPlaceholder')"
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

            <!-- Filter Button -->
            <BaseButton
              variant="outline"
              size="sm"
              @click="showFilterDrawer = true"
              class="relative flex items-center gap-2 shadow-sm hover:shadow-md transition-shadow"
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
                  d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                />
              </svg>
              {{ t('common.filter') }}
              <span
                v-if="activeFilterCount > 0"
                class="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 text-xs font-medium text-white bg-primary-600 rounded-full"
              >
                {{ activeFilterCount }}
              </span>
            </BaseButton>
          </div>
        </div>

        <!-- Active Filter Tags -->
        <div
          v-if="activeFilterCount > 0"
          class="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-gray-200"
        >
          <span
            v-if="filters.trending_period"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
          >
            <span
              >{{ t('githubTrending.filter.period') }}:
              {{ getPeriodLabel(filters.trending_period) }}</span
            >
            <button
              @click="removePeriodFilter"
              class="text-gray-500 hover:text-gray-700 transition-colors"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </span>
          <span
            v-if="filters.trending_lang"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
          >
            <span
              >{{ t('githubTrending.filter.language') }}:
              {{ getLanguageLabel(filters.trending_lang) }}</span
            >
            <button
              @click="removeLanguageFilter"
              class="text-gray-500 hover:text-gray-700 transition-colors"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </span>
        </div>
      </div>

      <!-- Desktop Calendar View -->
      <div
        class="hidden md:block bg-white rounded border border-gray-200 shadow-sm p-4 mb-4"
      >
        <GitHubTrendingCalendar
          :records="allRecords"
          :selected-date="selectedCalendarDate"
          @date-click="handleCalendarDateClick"
          @month-change="handleCalendarMonthChange"
        />
      </div>

      <!-- Mobile Card View -->
      <div
        class="md:hidden bg-white rounded border border-gray-200 shadow-sm p-4"
      >
        <BaseLoading v-if="loading && (!records || records.length === 0)" />

        <div
          v-else-if="!records || records.length === 0"
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
              d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
            />
          </svg>
          <p class="text-sm font-medium text-gray-600">
            {{ t('githubTrending.noRecords') }}
          </p>
        </div>

        <div v-else class="space-y-4">
          <template
            v-for="dateGroup in groupedRecordsByDate"
            :key="dateGroup.date"
          >
            <!-- Date Header -->
            <div class="sticky top-0 z-10 bg-white py-2 -mt-1 pt-3">
              <h2 class="text-sm font-semibold text-gray-900">
                {{ formatDateHeader(dateGroup.date) }}
              </h2>
            </div>

            <!-- Period Groups -->
            <div class="space-y-3">
              <template
                v-for="periodGroup in dateGroup.periods"
                :key="periodGroup.period"
              >
                <!-- Period Label and Records -->
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <span
                      class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-primary-100 text-primary-800 border border-primary-200"
                    >
                      {{ getPeriodLabel(periodGroup.period) }}
                    </span>
                  </div>
                  <div class="space-y-2 pl-2 border-l-2 border-gray-200">
                    <GitHubTrendingCard
                      v-for="record in periodGroup.records"
                      :key="`${record.id}-${record.trending_date}-${record.trending_period}`"
                      :record="record"
                      @view="handleViewProject"
                    />
                  </div>
                </div>
              </template>
            </div>
          </template>
        </div>

        <!-- Infinite Scroll Sentinel (Mobile Only) -->
        <div
          v-if="isMobile && hasMore && !loading"
          ref="sentinelElement"
          class="h-4"
        />

        <!-- Loading More Indicator (Mobile Only) -->
        <div
          v-if="isMobile && loadingMore"
          class="mt-4 flex items-center justify-center py-4"
        >
          <BaseLoading inline size="sm" />
          <span class="ml-2 text-sm text-gray-500">{{
            t('common.loadingMore')
          }}</span>
        </div>

        <!-- No More Data (Mobile Only) -->
        <div
          v-if="isMobile && !hasMore && records && records.length > 0"
          class="mt-4 text-center py-4"
        >
          <span class="text-sm text-gray-500">{{
            t('common.noMoreData')
          }}</span>
        </div>
      </div>

      <!-- Date Detail Panel -->
      <GitHubTrendingDateDetailPanel
        :show="showDateDetail"
        :selected-date="selectedCalendarDate"
        @close="showDateDetail = false"
        @view-project="handleViewProject"
      />

      <!-- Project Detail Panel -->
      <GitHubProjectDetailPanel
        :show="showProjectDetail"
        :project-id="selectedProjectId"
        @close="showProjectDetail = false"
      />

      <!-- Filter Drawer -->
      <FilterDrawer
        :show="showFilterDrawer"
        :title="t('githubTrending.title')"
        :filters="filterConfig"
        v-model="filters"
        @close="showFilterDrawer = false"
        @apply="handleFilterApply"
        @clear="handleFilterClear"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FilterDrawer from '@/components/ui/FilterDrawer.vue'
import GitHubTrendingCard from '@/components/github/GitHubTrendingCard.vue'
import GitHubTrendingCalendar from '@/components/github/GitHubTrendingCalendar.vue'
import GitHubTrendingDateDetailPanel from '@/components/github/GitHubTrendingDateDetailPanel.vue'
import GitHubProjectDetailPanel from '@/components/github/GitHubProjectDetailPanel.vue'
import { githubApi } from '@/api/github'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'

const { t, locale } = useI18n()
const router = useRouter()
const { showError } = useToast()

const records = ref([])
const allRecords = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(20)
const searchQuery = ref('')
const filters = ref({
  trending_period: '',
  trending_lang: ''
})
const currentMonth = ref(new Date())
const showProjectDetail = ref(false)
const selectedProjectId = ref(null)
const showDateDetail = ref(false)
const selectedCalendarDate = ref(null)
const showFilterDrawer = ref(false)

const filterConfig = computed(() => [
  {
    key: 'trending_period',
    label: t('githubTrending.filter.period'),
    options: [
      { value: '', label: t('githubTrending.filter.all') },
      { value: 'today', label: t('githubTrending.filter.today') },
      { value: 'weekly', label: t('githubTrending.filter.weekly') },
      { value: 'monthly', label: t('githubTrending.filter.monthly') }
    ]
  },
  {
    key: 'trending_lang',
    label: t('githubTrending.filter.language'),
    options: [
      { value: '', label: t('githubTrending.filter.all') },
      { value: 'any', label: t('githubTrending.filter.any') },
      { value: 'python', label: 'Python' },
      { value: 'javascript', label: 'JavaScript' },
      { value: 'java', label: 'Java' },
      { value: 'go', label: 'Go' },
      { value: 'rust', label: 'Rust' }
    ]
  }
])

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.value.trending_period) count++
  if (filters.value.trending_lang) count++
  return count
})

const getPeriodLabel = (period) => {
  const periodMap = {
    today: t('githubTrending.filter.today'),
    weekly: t('githubTrending.filter.weekly'),
    monthly: t('githubTrending.filter.monthly')
  }
  return periodMap[period] || period
}

const getLanguageLabel = (lang) => {
  if (lang === 'any') return t('githubTrending.filter.any')
  const langMap = {
    python: 'Python',
    javascript: 'JavaScript',
    java: 'Java',
    go: 'Go',
    rust: 'Rust'
  }
  return langMap[lang] || lang
}

const isMobile = ref(false)
const sentinelElement = ref(null)
let observer = null
let isSettingUpObserver = false

const loadRecords = async (append = false) => {
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }
  try {
    // Only load calendar data when not appending (initial load or refresh)
    if (!append) {
      // Load all records for calendar view (current month)
      const year = currentMonth.value.getFullYear()
      const month = currentMonth.value.getMonth()
      const firstDay = new Date(year, month, 1)
      firstDay.setHours(0, 0, 0, 0)
      const lastDay = new Date(year, month + 1, 0)
      lastDay.setHours(23, 59, 59, 999)

      const calendarParams = {
        page_size: 1000,
        ordering: 'trending_date,trending_period,trending_rank'
      }

      if (filters.value.trending_period) {
        calendarParams.trending_period = filters.value.trending_period
      }

      if (filters.value.trending_lang) {
        calendarParams.trending_lang = filters.value.trending_lang
      }

      try {
        const calendarResponse =
          await githubApi.getTrendingRecords(calendarParams)
        const calendarData = extractResponseData(calendarResponse)

        // Helper function to parse date string without timezone conversion
        const parseDateString = (dateStr) => {
          if (!dateStr) return null
          // If already in YYYY-MM-DD format, parse directly
          if (
            typeof dateStr === 'string' &&
            /^\d{4}-\d{2}-\d{2}$/.test(dateStr)
          ) {
            const [year, month, day] = dateStr.split('-').map(Number)
            return new Date(year, month - 1, day)
          }
          // Otherwise, use standard Date parsing
          return new Date(dateStr)
        }

        if (calendarData && calendarData.results) {
          allRecords.value = calendarData.results.filter((record) => {
            if (!record.trending_date) return false
            const recordDate = parseDateString(record.trending_date)
            if (!recordDate) return false
            recordDate.setHours(0, 0, 0, 0)
            return recordDate >= firstDay && recordDate <= lastDay
          })
        } else {
          allRecords.value = Array.isArray(calendarData)
            ? calendarData.filter((record) => {
                if (!record.trending_date) return false
                const recordDate = parseDateString(record.trending_date)
                if (!recordDate) return false
                recordDate.setHours(0, 0, 0, 0)
                return recordDate >= firstDay && recordDate <= lastDay
              })
            : []
        }
      } catch (calendarError) {
        console.error('Failed to load calendar data:', calendarError)
        allRecords.value = []
      }
    }

    // Load paginated records for table view
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ordering: '-trending_date,trending_period,trending_rank'
    }

    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    if (filters.value.trending_period) {
      params.trending_period = filters.value.trending_period
    }

    if (filters.value.trending_lang) {
      params.trending_lang = filters.value.trending_lang
    }

    const response = await githubApi.getTrendingRecords(params)
    const data = extractResponseData(response)

    if (data && data.results) {
      if (append) {
        records.value = [...records.value, ...data.results]
      } else {
        records.value = data.results
      }
      const total = data.count || 0
      totalPages.value = total > 0 ? Math.ceil(total / pageSize.value) : 1
      totalCount.value = total
      if (append) {
        currentPage.value = currentPage.value + 1
      }
    } else {
      const newRecords = Array.isArray(data) ? data : []
      if (append) {
        records.value = [...records.value, ...newRecords]
        currentPage.value = currentPage.value + 1
      } else {
        records.value = newRecords
        totalPages.value = 1
        totalCount.value = records.value.length
      }
    }
  } catch (error) {
    const errorMsg = extractErrorMessage(error)
    if (!append) {
      showError(errorMsg || t('githubTrending.loadError'))
      records.value = []
      allRecords.value = []
    }
  } finally {
    if (append) {
      loadingMore.value = false
    } else {
      loading.value = false
    }
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadRecords()
}

const handleFilterApply = (newFilters) => {
  filters.value = { ...newFilters }
  currentPage.value = 1
  loadRecords()
}

const handleFilterClear = () => {
  filters.value = { trending_period: '', trending_lang: '' }
  currentPage.value = 1
  loadRecords()
}

const removePeriodFilter = () => {
  filters.value.trending_period = ''
  currentPage.value = 1
  loadRecords()
}

const removeLanguageFilter = () => {
  filters.value.trending_lang = ''
  currentPage.value = 1
  loadRecords()
}

const handleCalendarMonthChange = (newMonth) => {
  currentMonth.value = newMonth
  loadRecords()
}

const handlePageChange = (page) => {
  currentPage.value = page
  loadRecords()
}

const handleLoadMore = async () => {
  if (
    currentPage.value >= totalPages.value ||
    loadingMore.value ||
    loading.value
  )
    return
  await loadRecords(true)
}

const hasMore = computed(() => {
  return currentPage.value < totalPages.value
})

const checkMobile = () => {
  try {
    const wasMobile = isMobile.value
    isMobile.value = window.innerWidth < 768

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

  if (observer) {
    return
  }

  isSettingUpObserver = true

  try {
    observer = new IntersectionObserver(
      (entries) => {
        if (!entries || entries.length === 0) return
        const entry = entries[0]
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
        root: null,
        rootMargin: '200px',
        threshold: 0.01
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

const handleViewProject = (projectId) => {
  selectedProjectId.value = projectId
  showProjectDetail.value = true
  showDateDetail.value = false
}

const handleCalendarDateClick = (date) => {
  selectedCalendarDate.value = date
  showDateDetail.value = true
  showProjectDetail.value = false
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

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString()
}

const formatDateHeader = (dateStr) => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const dateOnly = new Date(date)
    dateOnly.setHours(0, 0, 0, 0)

    if (dateOnly.getTime() === today.getTime()) {
      return t('githubTrending.filter.today')
    }

    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    if (dateOnly.getTime() === yesterday.getTime()) {
      return t('time.yesterday')
    }

    if (locale.value === 'zh-CN') {
      return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
    }
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  } catch {
    return dateStr
  }
}

const parseDateString = (dateStr) => {
  if (!dateStr) return null
  if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [year, month, day] = dateStr.split('-').map(Number)
    return new Date(year, month - 1, day)
  }
  return new Date(dateStr)
}

const groupedRecordsByDate = computed(() => {
  if (!records.value || records.value.length === 0) return []

  const dateMap = new Map()

  records.value.forEach((record) => {
    if (!record.trending_date) return

    const dateStr = record.trending_date
    if (!dateMap.has(dateStr)) {
      dateMap.set(dateStr, {
        date: dateStr,
        periods: new Map()
      })
    }

    const dateGroup = dateMap.get(dateStr)
    const period = record.trending_period || 'unknown'

    if (!dateGroup.periods.has(period)) {
      dateGroup.periods.set(period, {
        period: period,
        records: []
      })
    }

    dateGroup.periods.get(period).records.push(record)
  })

  const periodOrder = { today: 1, weekly: 2, monthly: 3 }

  return Array.from(dateMap.values())
    .map((dateGroup) => {
      const periods = Array.from(dateGroup.periods.values())
        .sort((a, b) => {
          const orderA = periodOrder[a.period] || 99
          const orderB = periodOrder[b.period] || 99
          return orderA - orderB
        })
        .map((periodGroup) => ({
          ...periodGroup,
          records: periodGroup.records.sort(
            (a, b) => (a.trending_rank || 0) - (b.trending_rank || 0)
          )
        }))

      return {
        date: dateGroup.date,
        periods
      }
    })
    .sort((a, b) => {
      const dateA = parseDateString(a.date)
      const dateB = parseDateString(b.date)
      if (!dateA || !dateB) return 0
      return dateB.getTime() - dateA.getTime()
    })
})

watch(
  [
    () => records.value?.length || 0,
    hasMore,
    isMobile,
    () => loading.value,
    () => loadingMore.value
  ],
  () => {
    try {
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

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  if (isMobile.value) {
    nextTick(() => {
      setupIntersectionObserver()
    })
  }
  loadRecords()
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
