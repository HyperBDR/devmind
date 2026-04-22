<template>
  <BaseModal :show="show" :title="t('articles.preview')" @close="handleClose">
    <div v-if="article" class="space-y-6">
      <div>
        <h3 class="text-lg font-medium text-gray-900 mb-4">
          {{ t('articles.basicInfo') }}
        </h3>
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-sm font-medium text-gray-500">
              {{ t('articles.statusLabel') }}
            </dt>
            <dd class="mt-1">
              <StatusBadge :status="mapArticleStatus(article.status)" />
            </dd>
          </div>
          <div v-if="article.source_url">
            <dt class="text-sm font-medium text-gray-500">
              {{ t('articles.sourceUrl') }}
            </dt>
            <dd class="mt-1 text-sm">
              <a
                :href="article.source_url"
                target="_blank"
                class="text-blue-600 hover:underline"
              >
                {{ article.source_url }}
              </a>
            </dd>
          </div>
          <div v-if="article.published_at">
            <dt class="text-sm font-medium text-gray-500">
              {{ t('articles.publishedAt') }}
            </dt>
            <dd class="mt-1 text-sm text-gray-900">
              {{ formatDate(article.published_at) }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- Tabs -->
      <div>
        <div class="border-b border-gray-200">
          <nav class="-mb-px flex space-x-8">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              :class="[
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm'
              ]"
              @click="activeTab = tab.id"
            >
              {{ tab.label }}
            </button>
          </nav>
        </div>

        <div class="mt-4">
          <!-- Original Content Tab -->
          <div v-show="activeTab === 'original'">
            <div class="space-y-4">
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.originalTitle') }}
                </h4>
                <div class="bg-gray-50 border border-gray-200 rounded p-4">
                  <p class="text-gray-900">{{ getOriginalTitle() }}</p>
                </div>
              </div>
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.originalContent') }}
                </h4>
                <div
                  class="bg-gray-50 border border-gray-200 rounded p-4 max-h-96 overflow-y-auto"
                >
                  <MarkdownRenderer :content="getOriginalContent()" />
                </div>
              </div>
            </div>
          </div>

          <!-- Translated Content Tab -->
          <div v-show="activeTab === 'translated'">
            <div class="space-y-4">
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.translatedTitle') }}
                </h4>
                <div class="bg-gray-50 border border-gray-200 rounded p-4">
                  <p class="text-gray-900">{{ article.title }}</p>
                </div>
              </div>
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.translatedContent') }}
                </h4>
                <div
                  class="bg-gray-50 border border-gray-200 rounded p-4 max-h-96 overflow-y-auto"
                >
                  <MarkdownRenderer :content="article.content" />
                </div>
              </div>
            </div>
          </div>

          <!-- Summary Tab -->
          <div v-show="activeTab === 'summary'">
            <div class="space-y-4">
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.summary') }}
                </h4>
                <div
                  class="bg-gray-50 border border-gray-200 rounded p-4 max-h-96 overflow-y-auto"
                >
                  <MarkdownRenderer
                    :content="article.summary || t('articles.noSummary')"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Comparison Tab -->
          <div v-show="activeTab === 'comparison'">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.original') }}
                </h4>
                <div
                  class="bg-gray-50 border border-gray-200 rounded p-4 max-h-96 overflow-y-auto"
                >
                  <MarkdownRenderer :content="getOriginalContent()" />
                </div>
              </div>
              <div>
                <h4 class="font-medium text-gray-900 mb-2">
                  {{ t('articles.translated') }}
                </h4>
                <div
                  class="bg-gray-50 border border-gray-200 rounded p-4 max-h-96 overflow-y-auto"
                >
                  <MarkdownRenderer :content="article.content" />
                </div>
              </div>
            </div>
          </div>

          <!-- Keywords Tab -->
          <div v-show="activeTab === 'keywords'">
            <div v-if="article.keywords && article.keywords.length > 0">
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="keyword in article.keywords"
                  :key="keyword.id"
                  class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                >
                  {{ keyword.name }}
                </span>
              </div>
            </div>
            <div v-else class="text-gray-500">
              {{ t('articles.noKeywords') }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="article.processing_error">
        <h3 class="text-lg font-medium text-gray-900 mb-4">
          {{ t('articles.error') }}
        </h3>
        <div class="bg-red-50 border border-red-200 rounded p-4">
          <pre class="text-sm text-red-800 whitespace-pre-wrap">{{
            article.processing_error
          }}</pre>
        </div>
      </div>
    </div>

    <template #footer>
      <BaseButton @click="handleClose">
        {{ t('common.close') }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'
import { format } from 'date-fns'
import { mapArticleStatus } from '@/utils/articleUtils'

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

const tabs = [
  { id: 'translated', label: t('articles.translated') },
  { id: 'original', label: t('articles.original') },
  { id: 'comparison', label: t('articles.comparison') },
  { id: 'summary', label: t('articles.summary') },
  { id: 'keywords', label: t('articles.keywords') }
]

watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      activeTab.value = 'translated'
    }
  }
)

const getOriginalTitle = () => {
  return props.article?.article_source?.title || props.article?.title || ''
}

const getOriginalContent = () => {
  return props.article?.article_source?.original_content || ''
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const handleClose = () => {
  emit('close')
}
</script>
