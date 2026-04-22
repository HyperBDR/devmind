<template>
  <div
    class="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-[calc(100vh-200px)] overflow-y-auto shadow-sm"
  >
    <!-- Title with underline -->
    <h2
      class="text-lg font-semibold text-gray-900 mb-4 pb-3 border-b border-gray-300"
    >
      {{ originalTitle }}
    </h2>
    <!-- Content -->
    <div class="prose prose-sm max-w-none text-sm">
      <MarkdownRenderer :content="originalContent" />
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

const originalTitle = computed(() => {
  return props.article?.article_source?.title || props.article?.title || ''
})

const originalContent = computed(() => {
  return props.article?.article_source?.original_content || ''
})
</script>
