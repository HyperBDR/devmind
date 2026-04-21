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
        class="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0"
      >
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('githubProjectDetail.title') }}
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

        <div v-else-if="project" class="p-6">
          <!-- Tabs -->
          <div>
            <div class="border-b border-gray-200">
              <nav class="-mb-px flex space-x-4 overflow-x-auto">
                <button
                  v-for="tab in tabs"
                  :key="tab.id"
                  :class="[
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                    'whitespace-nowrap py-3 px-4 border-b-2 font-semibold text-sm transition-colors'
                  ]"
                  @click="activeTab = tab.id"
                >
                  {{ tab.label }}
                </button>
              </nav>
            </div>

            <div class="mt-6">
              <!-- Basic Info Tab -->
              <div v-show="activeTab === 'basic'">
                <div class="space-y-6">
                  <div>
                    <h4 class="text-sm font-semibold text-gray-900 mb-4">
                      {{ t('githubProjectDetail.basicInfo') }}
                    </h4>
                    <div
                      class="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4 shadow-sm"
                    >
                      <div class="flex items-center justify-between">
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.fullName') }}:
                        </span>
                        <a
                          :href="project.html_url"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-sm font-semibold text-primary-600 hover:text-primary-800 transition-colors"
                        >
                          {{ project.full_name }}
                        </a>
                      </div>
                      <div v-if="project.description" class="flex flex-col">
                        <span class="text-sm font-semibold text-gray-700 mb-2">
                          {{ t('githubProjectDetail.description') }}:
                        </span>
                        <p class="text-sm font-medium text-gray-900">
                          {{ project.description }}
                        </p>
                      </div>
                      <div
                        v-if="project.language"
                        class="flex items-center justify-between"
                      >
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.language') }}:
                        </span>
                        <span
                          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
                        >
                          {{ project.language }}
                        </span>
                      </div>
                      <div class="flex items-center justify-between">
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.stars') }}:
                        </span>
                        <span class="text-sm font-semibold text-gray-900">
                          {{ formatNumber(project.stargazers_count) }}
                        </span>
                      </div>
                      <div class="flex items-center justify-between">
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.forks') }}:
                        </span>
                        <span class="text-sm font-semibold text-gray-900">
                          {{ formatNumber(project.forks_count) }}
                        </span>
                      </div>
                      <div class="flex items-center justify-between">
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.watchers') }}:
                        </span>
                        <span class="text-sm font-semibold text-gray-900">
                          {{ formatNumber(project.watchers_count) }}
                        </span>
                      </div>
                      <div
                        v-if="project.homepage"
                        class="flex items-center justify-between"
                      >
                        <span class="text-sm font-semibold text-gray-700">
                          {{ t('githubProjectDetail.homepage') }}:
                        </span>
                        <a
                          :href="project.homepage"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-sm font-medium text-primary-600 hover:text-primary-800 truncate max-w-xs transition-colors"
                        >
                          {{ project.homepage }}
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Snapshots Tab -->
              <div v-show="activeTab === 'snapshots'">
                <div class="space-y-6">
                  <div>
                    <h4 class="text-sm font-semibold text-gray-900 mb-4">
                      {{ t('githubProjectDetail.snapshots') }}
                      ({{ project.snapshots?.length || 0 }})
                    </h4>
                    <div
                      v-if="
                        !project.snapshots || project.snapshots.length === 0
                      "
                      class="text-sm font-medium text-gray-500 py-8 text-center rounded-lg border border-gray-200 bg-gray-50"
                    >
                      {{ t('githubProjectDetail.noSnapshots') }}
                    </div>
                    <div v-else class="space-y-4">
                      <div
                        v-for="snapshot in project.snapshots"
                        :key="snapshot.id"
                        class="bg-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm transition-shadow hover:shadow-md"
                      >
                        <div class="flex items-center justify-between mb-3">
                          <span class="text-sm font-semibold text-gray-900">
                            {{ formatDate(snapshot.snapshot_date) }}
                          </span>
                          <div
                            class="flex items-center gap-4 text-sm font-medium text-gray-700"
                          >
                            <span
                              >⭐
                              {{
                                formatNumber(snapshot.stargazers_count)
                              }}</span
                            >
                            <span
                              >🍴 {{ formatNumber(snapshot.forks_count) }}</span
                            >
                            <span
                              >👁️
                              {{ formatNumber(snapshot.watchers_count) }}</span
                            >
                          </div>
                        </div>
                        <div
                          v-if="snapshot.description"
                          class="text-sm font-medium text-gray-700 line-clamp-2 mb-3"
                        >
                          {{ snapshot.description }}
                        </div>
                        <!-- Images Gallery -->
                        <div
                          v-if="getSnapshotImages(snapshot).length > 0"
                          class="mt-3 image-gallery"
                        >
                          <div class="text-xs font-medium text-gray-700 mb-2">
                            {{ t('githubProjectDetail.images') }} ({{
                              getSnapshotImages(snapshot).length
                            }})
                          </div>
                          <div class="grid grid-cols-2 gap-2">
                            <div
                              v-for="(imageUrl, idx) in getSnapshotImages(
                                snapshot
                              )"
                              :key="idx"
                              class="relative group cursor-pointer image-container"
                              @click="
                                openImageModal(
                                  getImageUrl(imageUrl, project.uuid)
                                )
                              "
                            >
                              <img
                                :src="getImageUrl(imageUrl, project.uuid)"
                                :alt="`${project.full_name} image ${idx + 1}`"
                                class="w-full h-24 object-cover rounded border border-gray-200 hover:border-primary-400 transition-colors"
                                @error="(e) => handleImageError(e, snapshot)"
                                @load="(e) => handleImageLoad(e, snapshot)"
                              />
                              <div
                                class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 transition-opacity rounded"
                              ></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Trending Records Tab -->
              <div v-show="activeTab === 'trending'">
                <div class="space-y-6">
                  <div>
                    <h4 class="text-sm font-semibold text-gray-900 mb-4">
                      {{ t('githubProjectDetail.trendingRecords') }}
                      ({{ project.trending_records?.length || 0 }})
                    </h4>
                    <div
                      v-if="
                        !project.trending_records ||
                        project.trending_records.length === 0
                      "
                      class="text-sm font-medium text-gray-500 py-8 text-center rounded-lg border border-gray-200 bg-gray-50"
                    >
                      {{ t('githubProjectDetail.noTrendingRecords') }}
                    </div>
                    <div
                      v-else
                      class="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm"
                    >
                      <table class="min-w-full divide-y divide-gray-200">
                        <thead
                          class="bg-gradient-to-r from-gray-50 to-gray-100"
                        >
                          <tr>
                            <th
                              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                            >
                              {{ t('githubProjectDetail.date') }}
                            </th>
                            <th
                              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                            >
                              {{ t('githubProjectDetail.period') }}
                            </th>
                            <th
                              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                            >
                              {{ t('githubProjectDetail.rank') }}
                            </th>
                            <th
                              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                            >
                              {{ t('githubProjectDetail.starGrowth') }}
                            </th>
                            <th
                              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                            >
                              {{ t('githubProjectDetail.rankChange') }}
                            </th>
                          </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-100">
                          <tr
                            v-for="record in project.trending_records"
                            :key="record.id"
                            class="transition-colors duration-150 hover:bg-gray-50"
                          >
                            <td class="px-4 py-4 whitespace-nowrap">
                              <span class="text-sm font-medium text-gray-900">
                                {{ formatDate(record.trending_date) }}
                              </span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap">
                              <span class="text-sm font-medium text-gray-700">
                                {{ record.trending_period }}
                              </span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap">
                              <span class="text-sm font-semibold text-gray-900">
                                #{{ record.trending_rank }}
                              </span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap">
                              <span
                                class="text-sm font-semibold"
                                :class="
                                  record.star_growth !== null &&
                                  record.star_growth >= 0
                                    ? 'text-green-600'
                                    : record.star_growth !== null
                                      ? 'text-red-600'
                                      : 'text-gray-400'
                                "
                              >
                                {{
                                  record.star_growth !== null
                                    ? (record.star_growth >= 0 ? '+' : '') +
                                      formatNumber(record.star_growth)
                                    : '-'
                                }}
                              </span>
                            </td>
                            <td class="px-4 py-4 whitespace-nowrap">
                              <span
                                class="text-sm font-semibold"
                                :class="
                                  record.rank_change !== null &&
                                  record.rank_change > 0
                                    ? 'text-green-600'
                                    : record.rank_change !== null &&
                                        record.rank_change < 0
                                      ? 'text-red-600'
                                      : 'text-gray-400'
                                "
                              >
                                {{
                                  record.rank_change !== null
                                    ? (record.rank_change > 0
                                        ? '↑'
                                        : record.rank_change < 0
                                          ? '↓'
                                          : '→') +
                                      (record.rank_change !== 0
                                        ? Math.abs(record.rank_change)
                                        : '')
                                    : '-'
                                }}
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Image Modal -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="showImageModal"
      @click="closeImageModal"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
    >
      <div class="relative max-w-4xl max-h-full">
        <button
          @click="closeImageModal"
          class="absolute -top-10 right-0 text-white hover:text-gray-300 text-2xl font-bold"
        >
          ×
        </button>
        <img
          :src="imageModalUrl"
          alt="Project image"
          class="max-w-full max-h-[90vh] object-contain rounded"
          @click.stop
        />
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch } from 'vue'
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
  projectId: {
    type: [String, Number],
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const { showError } = useToast()

const project = ref(null)
const loading = ref(false)
const activeTab = ref('basic')
const imageModalUrl = ref(null)
const showImageModal = ref(false)

const tabs = [
  { id: 'basic', label: t('githubProjectDetail.tabs.basic') },
  { id: 'snapshots', label: t('githubProjectDetail.tabs.snapshots') },
  { id: 'trending', label: t('githubProjectDetail.tabs.trending') }
]

const loadProject = async () => {
  if (!props.projectId) {
    project.value = null
    return
  }

  loading.value = true
  try {
    const response = await githubApi.getProject(props.projectId)
    const data = extractResponseData(response)
    project.value = data
  } catch (error) {
    const errorMsg = extractErrorMessage(error)
    showError(errorMsg || t('githubProjectDetail.loadError'))
    project.value = null
  } finally {
    loading.value = false
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

const getSnapshotImages = (snapshot) => {
  if (!snapshot || !snapshot.readme_images) {
    return []
  }

  // Handle different data types
  if (Array.isArray(snapshot.readme_images)) {
    return snapshot.readme_images.filter((img) => img && img.trim())
  }

  // If it's a string, try to parse it
  if (typeof snapshot.readme_images === 'string') {
    try {
      const parsed = JSON.parse(snapshot.readme_images)
      if (Array.isArray(parsed)) {
        return parsed.filter((img) => img && img.trim())
      }
    } catch (e) {
      // If parsing fails, treat as single image URL
      return snapshot.readme_images.trim() ? [snapshot.readme_images] : []
    }
  }

  return []
}

const getImageUrl = (imageUrl, projectUuid) => {
  if (!imageUrl || typeof imageUrl !== 'string') return ''

  const trimmedUrl = imageUrl.trim()
  if (!trimmedUrl) return ''

  // If it's already a full URL (http/https), return as is
  if (trimmedUrl.startsWith('http://') || trimmedUrl.startsWith('https://')) {
    return trimmedUrl
  }

  // If it's a local path, convert to accessible URL
  // Local paths are like: /opt/media/github/{project_uuid}/{filename}
  // We need to convert to: /media/github/{project_uuid}/{filename}
  if (trimmedUrl.startsWith('/opt/media/github/')) {
    const pathParts = trimmedUrl.replace('/opt/media/github/', '').split('/')
    if (pathParts.length >= 2) {
      const filename = pathParts[pathParts.length - 1]
      const uuid = pathParts[0]
      return `${window.location.origin}/media/github/${uuid}/${filename}`
    }
  }

  // If it's a relative path starting with /, assume it's already a media path
  if (trimmedUrl.startsWith('/')) {
    return `${window.location.origin}${trimmedUrl}`
  }

  // Otherwise, assume it's a filename and construct the path using UUID
  return `${window.location.origin}/media/github/${projectUuid}/${trimmedUrl}`
}

const openImageModal = (imageUrl) => {
  imageModalUrl.value = imageUrl
  showImageModal.value = true
}

const closeImageModal = () => {
  showImageModal.value = false
  imageModalUrl.value = null
}

// Track image load status per snapshot
const snapshotImageStatus = ref(new Map())

const handleImageError = (event, snapshot) => {
  // Hide broken images and their container
  const container = event.target.closest('.image-container')
  if (container) {
    container.style.display = 'none'
  } else {
    event.target.style.display = 'none'
  }

  // Track failed image
  const snapshotId = snapshot?.id || 'default'
  if (!snapshotImageStatus.value.has(snapshotId)) {
    snapshotImageStatus.value.set(snapshotId, {
      total: getSnapshotImages(snapshot).length,
      loaded: 0,
      failed: 0
    })
  }
  const status = snapshotImageStatus.value.get(snapshotId)
  status.failed++

  // Hide entire gallery if all images failed
  const gallery = event.target.closest('.image-gallery')
  if (gallery && status.failed >= status.total) {
    gallery.style.display = 'none'
  }
}

const handleImageLoad = (event, snapshot) => {
  // Track successfully loaded images
  const snapshotId = snapshot?.id || 'default'
  if (!snapshotImageStatus.value.has(snapshotId)) {
    snapshotImageStatus.value.set(snapshotId, {
      total: getSnapshotImages(snapshot).length,
      loaded: 0,
      failed: 0
    })
  }
  const status = snapshotImageStatus.value.get(snapshotId)
  status.loaded++
}

const handleClose = () => {
  emit('close')
}

watch(
  () => props.show,
  (newVal) => {
    if (newVal && props.projectId) {
      activeTab.value = 'basic'
      loadProject()
    }
  }
)

watch(
  () => props.projectId,
  () => {
    if (props.show && props.projectId) {
      loadProject()
    }
  }
)
</script>
