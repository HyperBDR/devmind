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
          {{ t('articles.preview') }}
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
        <div v-if="article" class="p-6">
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
              <!-- Publish Preview Tab -->
              <ArticleTranslatedTab
                v-if="activeTab === 'translated'"
                :article="article"
              />

              <!-- Basic Info Tab -->
              <ArticleBasicInfoTab
                v-if="activeTab === 'basic'"
                :article="article"
              />

              <!-- Original Preview Tab -->
              <ArticleOriginalTab
                v-if="activeTab === 'original'"
                :article="article"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ArticleTranslatedTab from './ArticleTranslatedTab.vue'
import ArticleBasicInfoTab from './ArticleBasicInfoTab.vue'
import ArticleOriginalTab from './ArticleOriginalTab.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  article: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()

const activeTab = ref('translated')

// Check if original content exists
const hasOriginalContent = computed(() => {
  if (!props.article) return false
  const originalContent = props.article?.article_source?.original_content || ''
  return originalContent.trim().length > 0
})

// Build tabs dynamically based on whether original content exists
const tabs = computed(() => {
  const tabList = [
    { id: 'translated', label: t('articles.publishPreview') },
    { id: 'basic', label: t('articles.publishInfo') }
  ]

  // Only add original tab if original content exists
  if (hasOriginalContent.value) {
    tabList.push({ id: 'original', label: t('articles.originalPreview') })
  }

  return tabList
})

watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      activeTab.value = 'translated'
    }
  }
)

const handleClose = () => {
  emit('close')
}
</script>
