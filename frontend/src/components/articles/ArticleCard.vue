<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handlePreview"
  >
    <!-- Article Card Content -->
    <div class="p-4">
      <!-- Title -->
      <h3 class="text-sm font-semibold text-gray-900 mb-3 line-clamp-2">
        {{ article.title }}
      </h3>

      <!-- Source, Time, Status and Storage Prefix -->
      <div class="space-y-2">
        <!-- Source and Time -->
        <div class="flex items-center gap-2 text-sm text-gray-500">
          <span v-if="article.source_url" class="truncate">
            {{ getSourceDomain(article.source_url) }}
          </span>
          <span v-if="article.source_url && article.created_at">•</span>
          <span v-if="article.created_at">
            {{ formatRelativeTime(article.created_at) }}
          </span>
        </div>

        <!-- Status, Storage Prefix and Menu Button Row -->
        <div class="flex items-center justify-between gap-2 relative flex-wrap">
          <div class="flex items-center gap-2 flex-wrap flex-1 min-w-0">
            <!-- Status Badge -->
            <StatusBadge :status="mapArticleStatus(article.status)" />

            <!-- Storage Prefix as Badge -->
            <StorageLocationBadge :location="article.social_account" />
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
                  v-if="article.is_transformed"
                  @click="handleAction('upload', $event)"
                  :disabled="uploading"
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
                      d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"
                    />
                  </svg>
                  {{
                    article.is_uploaded
                      ? t('articles.reupload')
                      : t('articles.upload')
                  }}
                </button>
                <button
                  v-if="
                    article.status === 'failed' ||
                    article.status === 'processing' ||
                    article.status === 'completed'
                  "
                  @click="handleAction('retry', $event)"
                  :disabled="retrying"
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
                  {{ t('common.tryAgain') }}
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
import StorageLocationBadge from '@/components/ui/StorageLocationBadge.vue'
import { mapArticleStatus } from '@/utils/articleUtils'

const props = defineProps({
  article: {
    type: Object,
    required: true
  },
  uploading: {
    type: Boolean,
    default: false
  },
  retrying: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['preview', 'upload', 'retry', 'delete'])

const { t } = useI18n()

const showMenu = ref(false)
const menuRef = ref(null)
const buttonRef = ref(null)
const menuStyle = ref({})

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

const getSourceDomain = (url) => {
  if (!url) return ''
  try {
    const urlObj = new URL(url)
    return urlObj.hostname.replace('www.', '')
  } catch {
    const match = url.match(/https?:\/\/([^\/]+)/)
    return match ? match[1].replace('www.', '') : url
  }
}

const handlePreview = () => {
  emit('preview', props.article)
}

const handleMenuClick = (event) => {
  event.stopPropagation()
  if (!showMenu.value && buttonRef.value) {
    // Calculate menu position when opening
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

  if (action === 'upload') {
    emit('upload', props.article)
  } else if (action === 'retry') {
    emit('retry', props.article)
  } else if (action === 'delete') {
    emit('delete', props.article)
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
