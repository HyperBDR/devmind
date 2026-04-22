<template>
  <div
    class="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-[calc(100vh-200px)] overflow-y-auto shadow-sm"
  >
    <!-- Title with underline -->
    <h2
      class="text-lg font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-300"
    >
      {{ article.title }}
    </h2>
    <!-- Content -->
    <div class="prose prose-sm max-w-none text-sm">
      <MarkdownRenderer :content="translatedContent" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'

const props = defineProps({
  article: {
    type: Object,
    required: true
  }
})

const { t } = useI18n()

const translatedContent = computed(() => {
  if (!props.article) return ''

  // Priority: local_markdown > content > oss_markdown
  // Always use local_markdown first to load images from local HTTP service
  // instead of object storage
  if (props.article.local_markdown) {
    return props.article.local_markdown
  }

  // Fallback to regular content
  if (props.article.content) {
    return props.article.content
  }

  // Last resort: use oss_markdown (but images may not load)
  if (props.article.oss_markdown) {
    return props.article.oss_markdown
  }

  return ''
})
</script>
