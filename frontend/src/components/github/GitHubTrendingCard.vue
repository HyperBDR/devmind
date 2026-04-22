<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handleViewProject"
  >
    <!-- Trending Card Content -->
    <div class="p-4">
      <!-- Title and Rank -->
      <div class="flex items-start justify-between mb-2">
        <h3 class="text-sm font-semibold text-gray-900 flex-1 line-clamp-2">
          {{ record.project_name }}
        </h3>
        <span class="text-xs font-semibold text-primary-600 ml-2 flex-shrink-0">
          #{{ record.trending_rank }}
        </span>
      </div>

      <!-- Description -->
      <p
        v-if="record.project_description"
        class="text-xs text-gray-500 mb-3 line-clamp-2"
      >
        {{ record.project_description }}
      </p>

      <!-- Language, Stats and Menu Button Row -->
      <div class="flex items-center justify-between gap-2 relative flex-wrap">
        <div class="flex items-center gap-2 flex-wrap flex-1 min-w-0">
          <!-- Language -->
          <span
            v-if="record.project_language"
            class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
          >
            {{ record.project_language }}
          </span>

          <!-- Stats -->
          <div class="flex items-center gap-3 text-xs text-gray-600">
            <span>⭐ {{ formatNumber(record.project_stargazers_count) }}</span>
            <span>🍴 {{ formatNumber(record.project_forks_count) }}</span>
          </div>

          <!-- Trending Date -->
          <span v-if="record.trending_date" class="text-sm text-gray-500">
            {{ formatRelativeTime(record.trending_date) }}
          </span>
        </div>

        <!-- Menu Button -->
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
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'

const props = defineProps({
  record: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view'])

const { t } = useI18n()

const showMenu = ref(false)
const menuRef = ref(null)
const buttonRef = ref(null)
const menuStyle = ref({})

const formatNumber = (num) => {
  if (num === null || num === undefined) return '0'
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

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

const handleViewProject = () => {
  emit('view', props.record.project_id)
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
    emit('view', props.record.project_id)
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
