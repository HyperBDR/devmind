<template>
  <div class="space-y-6">
    <!-- Part 1: Status and Info (Left-Right Layout) -->
    <div class="space-y-3">
      <!-- Status -->
      <div class="flex items-center justify-between py-2">
        <span class="text-sm text-gray-700">
          {{ t('articles.statusLabel') }}
        </span>
        <StatusBadge :status="mappedStatus" />
      </div>

      <!-- Legality -->
      <div
        v-if="article.is_illegal === true"
        class="flex items-center justify-between py-2"
      >
        <span class="text-sm text-gray-700">
          {{ t('articles.legality') }}
        </span>
        <span
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200 shadow-sm"
        >
          <svg
            class="w-3.5 h-3.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          {{ t('articles.illegal') }}
        </span>
      </div>

      <!-- Transform Status -->
      <div class="flex items-center justify-between py-2">
        <span class="text-sm text-gray-700">
          {{ t('articles.transformStatus') }}
        </span>
        <span
          :class="[
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm',
            article.is_transformed === true
              ? 'bg-purple-100 text-purple-800 border-purple-200'
              : 'bg-amber-100 text-amber-700 border-amber-200'
          ]"
        >
          <svg
            v-if="article.is_transformed === true"
            class="w-3.5 h-3.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
            />
          </svg>
          <svg
            v-else
            class="w-3.5 h-3.5 flex-shrink-0"
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
          {{
            article.is_transformed === true
              ? t('articles.transformed')
              : t('articles.notTransformed')
          }}
        </span>
      </div>

      <!-- Upload Status -->
      <div class="flex items-center justify-between py-2">
        <span class="text-sm text-gray-700">
          {{ t('articles.uploadStatus') }}
        </span>
        <span
          :class="[
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm',
            article.is_uploaded === true
              ? 'bg-teal-100 text-teal-800 border-teal-200'
              : 'bg-orange-100 text-orange-700 border-orange-200'
          ]"
        >
          <svg
            v-if="article.is_uploaded === true"
            class="w-3.5 h-3.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <svg
            v-else
            class="w-3.5 h-3.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
            />
          </svg>
          {{
            article.is_uploaded === true
              ? t('articles.uploaded')
              : t('articles.notUploaded')
          }}
        </span>
      </div>

      <!-- Storage Location -->
      <div
        v-if="article.social_account"
        class="flex items-center justify-between py-2"
      >
        <span class="text-sm text-gray-700">
          {{ t('articles.storageLocation') }}
        </span>
        <StorageLocationBadge :location="article.social_account" />
      </div>

      <!-- Source URL -->
      <div v-if="sourceUrl" class="flex items-center justify-between py-2">
        <span class="text-sm text-gray-700">
          {{ t('articles.sourceUrl') }}
        </span>
        <div class="flex items-center gap-1.5 max-w-md">
          <a
            :href="sourceUrl"
            target="_blank"
            class="text-sm text-primary-600 hover:text-primary-800 hover:underline break-all transition-colors inline-flex items-center gap-1 text-right flex-1 min-w-0"
          >
            <span class="truncate">{{ sourceUrl }}</span>
            <svg
              class="w-3 h-3 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
              />
            </svg>
          </a>
          <CopyButton :text="sourceUrl" />
        </div>
      </div>
    </div>

    <!-- Part 2: Storage Paths (Sequential Display) -->
    <div v-if="hasStoragePaths" class="border-t border-gray-200 pt-6 space-y-4">
      <!-- Legacy markdown URL -->
      <div v-if="article.oss_markdown_url && !article.oss_format_urls">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm text-gray-700">
            {{ t('articles.markdownUrl') }}
          </span>
          <CopyButton :text="article.oss_markdown_url" />
        </div>
        <a
          :href="article.oss_markdown_url"
          target="_blank"
          class="text-sm text-blue-600 hover:underline break-all block"
        >
          {{ article.oss_markdown_url }}
        </a>
      </div>

      <!-- Format URLs -->
      <div v-for="(url, format) in article.oss_format_urls" :key="format">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm text-gray-700">
            {{ getFormatLabelLocal(format) }}
          </span>
          <CopyButton :text="url" />
        </div>
        <a
          :href="url"
          target="_blank"
          class="text-sm text-blue-600 hover:underline break-all block"
        >
          {{ url }}
        </a>
      </div>

      <!-- Word URL -->
      <div v-if="article.oss_word_url">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm text-gray-700">
            {{ t('articles.wordUrl') }}
          </span>
          <CopyButton :text="article.oss_word_url" />
        </div>
        <a
          :href="article.oss_word_url"
          target="_blank"
          class="text-sm text-blue-600 hover:underline break-all block"
        >
          {{ article.oss_word_url }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import CopyButton from '@/components/ui/CopyButton.vue'
import StorageLocationBadge from '@/components/ui/StorageLocationBadge.vue'
import { mapArticleStatus, getFormatLabel } from '@/utils/articleUtils'

const props = defineProps({
  article: {
    type: Object,
    required: true
  }
})

const { t } = useI18n()

const mappedStatus = computed(() => {
  return mapArticleStatus(props.article?.status)
})

const sourceUrl = computed(() => {
  return (
    props.article?.article_source?.source_url || props.article?.source_url || ''
  )
})

const hasStoragePaths = computed(() => {
  return (
    (props.article?.oss_markdown_url && !props.article?.oss_format_urls) ||
    (props.article?.oss_format_urls &&
      Object.keys(props.article.oss_format_urls).length > 0) ||
    props.article?.oss_word_url
  )
})

const getFormatLabelLocal = (format) => {
  return getFormatLabel(format, t)
}
</script>
