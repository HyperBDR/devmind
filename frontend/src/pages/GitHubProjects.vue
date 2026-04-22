<template>
  <AppLayout>
    <div class="w-full max-w-full">
      <!-- Page Header -->
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('githubProjects.title') }}
          </h1>
          <p class="text-sm text-gray-500 mt-1">
            {{ t('githubProjects.description') }}
          </p>
        </div>
      </div>

      <!-- Content Card -->
      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar -->
          <div
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <!-- Left spacer for alignment -->
            <div class="flex items-center gap-2 flex-wrap"></div>

            <!-- Search and Filter (Right) -->
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('githubProjects.searchPlaceholder')"
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

          <!-- Active Filter Tags -->
          <div
            v-if="activeFilterCount > 0"
            class="flex flex-wrap items-center gap-2 mb-4"
          >
            <span
              v-if="filters.language"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
            >
              <span
                >{{ t('githubProjects.filter.language') }}:
                {{ filters.language }}</span
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

          <BaseLoading v-if="loading && (!projects || projects.length === 0)" />

          <div
            v-else-if="!projects || projects.length === 0"
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
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <p class="text-sm font-medium text-gray-600">
              {{ t('githubProjects.noProjects') }}
            </p>
          </div>

          <!-- Mobile Card View -->
          <div
            v-if="projects && projects.length > 0"
            class="md:hidden space-y-3"
          >
            <GitHubProjectCard
              v-for="project in projects"
              :key="project.id"
              :project="project"
              @view="handleViewProject"
              @trending="handleViewTrending"
            />
          </div>

          <!-- Infinite Scroll Sentinel (Mobile Only) -->
          <div
            v-if="isMobile && hasMore && !loading"
            ref="sentinelElement"
            class="h-4 md:hidden"
          />

          <!-- Loading More Indicator (Mobile Only) -->
          <div
            v-if="isMobile && loadingMore"
            class="mt-4 flex items-center justify-center py-4 md:hidden"
          >
            <BaseLoading inline size="sm" />
            <span class="ml-2 text-sm text-gray-500">{{
              t('common.loadingMore')
            }}</span>
          </div>

          <!-- No More Data (Mobile Only) -->
          <div
            v-if="isMobile && !hasMore && projects && projects.length > 0"
            class="mt-4 text-center py-4 md:hidden"
          >
            <span class="text-sm text-gray-500">{{
              t('common.noMoreData')
            }}</span>
          </div>

          <!-- Desktop Table View -->
          <div
            v-if="projects && projects.length > 0"
            class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <!-- Loading overlay when data exists but is refreshing -->
            <div
              v-if="loading"
              class="absolute inset-0 bg-white bg-opacity-80 flex items-center justify-center z-10 rounded-lg backdrop-blur-sm"
            >
              <BaseLoading
                inline
                size="lg"
                variant="primary"
                :show-text="false"
              />
            </div>
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.project') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.language') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.stars') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.forks') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.watchers') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.updated') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('githubProjects.table.actions') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-100">
                <tr
                  v-for="project in projects"
                  :key="project.id"
                  class="transition-colors duration-150 hover:bg-gray-50"
                >
                  <td class="px-4 py-4">
                    <div class="flex flex-col">
                      <button
                        @click="handleViewProject(project.id)"
                        class="text-sm font-semibold text-primary-600 hover:text-primary-800 text-left transition-colors"
                      >
                        {{ project.full_name }}
                      </button>
                      <p class="text-xs text-gray-500 mt-1.5 line-clamp-2">
                        {{ project.description }}
                      </p>
                    </div>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span
                      v-if="project.language"
                      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
                    >
                      {{ project.language }}
                    </span>
                    <span v-else class="text-sm text-gray-400">-</span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-900 font-medium">
                      {{ formatNumber(project.stargazers_count) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-900 font-medium">
                      {{ formatNumber(project.forks_count) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-900 font-medium">
                      {{ formatNumber(project.watchers_count) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <span class="text-sm text-gray-600 font-medium">
                      {{ formatDate(project.updated_at) }}
                    </span>
                  </td>
                  <td class="px-4 py-4 whitespace-nowrap">
                    <div class="flex items-center gap-2">
                      <BaseButton
                        variant="outline"
                        size="sm"
                        @click="handleViewProject(project.id)"
                      >
                        {{ t('githubProjects.viewProject') }}
                      </BaseButton>
                      <BaseButton
                        variant="outline"
                        size="sm"
                        @click="handleViewTrending(project.id)"
                      >
                        {{ t('githubProjects.viewTrending') }}
                      </BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination (Desktop Only) -->
          <div
            class="hidden md:flex mt-6 pt-4 border-t border-gray-200 flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
          >
            <div
              class="flex flex-col sm:flex-row items-start sm:items-center gap-4"
            >
              <div class="text-sm text-gray-700 font-medium">
                <span v-if="totalCount > 0">
                  {{
                    t('common.pagination.showing', {
                      from: (currentPage - 1) * pageSize + 1,
                      to: Math.min(currentPage * pageSize, totalCount),
                      total: totalCount
                    })
                  }}
                </span>
                <span v-else class="text-gray-500">
                  {{ t('common.noData') }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-sm text-gray-700 font-medium">
                  {{ t('common.pagination.itemsPerPage') }}:
                </label>
                <select
                  v-model.number="pageSize"
                  @change="handlePageSizeChange"
                  class="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white cursor-pointer shadow-sm hover:shadow-md transition-shadow font-medium"
                >
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                </select>
              </div>
            </div>
            <div v-if="totalPages > 1" class="flex items-center gap-3">
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage === 1"
                @click="handlePageChange(currentPage - 1)"
                class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ t('common.pagination.previous') }}
              </BaseButton>
              <span
                class="text-sm text-gray-700 font-semibold flex items-center px-3 py-1.5 bg-gray-50 rounded-md border border-gray-200"
              >
                {{
                  t('common.pagination.page', {
                    current: currentPage,
                    total: totalPages
                  })
                }}
              </span>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage === totalPages"
                @click="handlePageChange(currentPage + 1)"
                class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ t('common.pagination.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Project Detail Panel -->
      <GitHubProjectDetailPanel
        :show="showProjectDetail"
        :project-id="selectedProjectId"
        @close="showProjectDetail = false"
      />

      <!-- Filter Drawer -->
      <FilterDrawer
        :show="showFilterDrawer"
        :title="t('githubProjects.title')"
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
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FilterDrawer from '@/components/ui/FilterDrawer.vue'
import GitHubProjectCard from '@/components/github/GitHubProjectCard.vue'
import GitHubProjectDetailPanel from '@/components/github/GitHubProjectDetailPanel.vue'
import { githubApi } from '@/api/github'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const { showError } = useToast()

const projects = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(20)
const searchQuery = ref('')
const filters = ref({
  language: ''
})
const showProjectDetail = ref(false)
const selectedProjectId = ref(null)
const showFilterDrawer = ref(false)

const filterConfig = computed(() => [
  {
    key: 'language',
    label: t('githubProjects.filter.language'),
    options: [
      { value: '', label: t('githubProjects.filter.all') },
      { value: 'Python', label: 'Python' },
      { value: 'JavaScript', label: 'JavaScript' },
      { value: 'Java', label: 'Java' },
      { value: 'Go', label: 'Go' },
      { value: 'Rust', label: 'Rust' },
      { value: 'TypeScript', label: 'TypeScript' }
    ]
  }
])

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.value.language) count++
  return count
})

const isMobile = ref(false)
const sentinelElement = ref(null)
let observer = null
let isSettingUpObserver = false

const loadProjects = async (append = false) => {
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }

    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    if (filters.value.language) {
      params.language = filters.value.language
    }

    // Check if we need to filter by project ID from query
    if (route.query.id) {
      params.id = route.query.id
    }

    const response = await githubApi.getProjects(params)
    const data = extractResponseData(response)

    if (data && data.results) {
      if (append) {
        projects.value = [...projects.value, ...data.results]
        currentPage.value = currentPage.value + 1
      } else {
        projects.value = data.results
      }
      const total = data.count || 0
      totalPages.value = total > 0 ? Math.ceil(total / pageSize.value) : 1
      totalCount.value = total
    } else {
      const newProjects = Array.isArray(data) ? data : []
      if (append) {
        projects.value = [...projects.value, ...newProjects]
        currentPage.value = currentPage.value + 1
      } else {
        projects.value = newProjects
        totalPages.value = 1
        totalCount.value = projects.value.length
      }
    }
  } catch (error) {
    const errorMsg = extractErrorMessage(error)
    if (!append) {
      showError(errorMsg || t('githubProjects.loadError'))
      projects.value = []
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
  loadProjects()
}

const handleFilterApply = (newFilters) => {
  filters.value = { ...newFilters }
  currentPage.value = 1
  loadProjects()
}

const handleFilterClear = () => {
  filters.value = { language: '' }
  currentPage.value = 1
  loadProjects()
}

const removeLanguageFilter = () => {
  filters.value.language = ''
  currentPage.value = 1
  loadProjects()
}

const handlePageChange = (page) => {
  currentPage.value = page
  loadProjects()
}

const handlePageSizeChange = () => {
  // Reset to first page when page size changes
  currentPage.value = 1
  // Force reload projects with new page size
  loadProjects()
}

const handleRefresh = () => {
  loadProjects()
}

const handleViewProject = (projectId) => {
  selectedProjectId.value = projectId
  showProjectDetail.value = true
}

const handleViewTrending = (projectId) => {
  router.push({
    name: 'GitHubTrending',
    query: { project: projectId }
  })
}

const handleLoadMore = async () => {
  if (
    currentPage.value >= totalPages.value ||
    loadingMore.value ||
    loading.value
  )
    return
  await loadProjects(true)
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

watch(
  [
    () => projects.value?.length || 0,
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
  loadProjects()
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

watch(
  () => route.query.id,
  () => {
    if (route.query.id) {
      loadProjects()
    }
  }
)
</script>
