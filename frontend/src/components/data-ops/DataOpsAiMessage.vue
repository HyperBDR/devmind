<template>
  <div class="flex" :class="isUser ? 'justify-end' : ''">
    <div
      class="max-w-[88%] rounded-xl px-4 py-3 text-sm leading-6"
      :class="
        isUser
          ? 'bg-indigo-600 text-white'
          : 'border border-slate-200 bg-slate-50 text-slate-700'
      "
    >
      <p v-if="isUser" class="whitespace-pre-wrap">
        {{ message.content }}
      </p>
      <template v-else>
        <MarkdownRenderer
          v-if="markdownContent"
          :content="markdownContent"
          class="data-ops-ai-markdown"
        />
        <p v-else class="text-sm text-slate-500">
          正在整理分析...
        </p>
        <DataOpsAiChartBlock
          v-for="chart in charts"
          :key="chart.key"
          :chart="chart"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'

import DataOpsAiChartBlock from './DataOpsAiChartBlock.vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const isUser = computed(() => props.message.role === 'user')
const content = computed(() => String(props.message.content || ''))

const charts = computed(() => {
  const items = []
  for (const match of content.value.matchAll(chartFencePattern())) {
    const chart = parseChart(match[1])
    if (chart) items.push({ ...chart, key: `${items.length}-${chart.title}` })
  }
  return items
})

const markdownContent = computed(() =>
  content.value.replace(chartFencePattern(), '').trim()
)

function chartFencePattern() {
  return /```(?:dataops-chart|chart)\s*([\s\S]*?)```/g
}

function parseChart(rawValue) {
  try {
    const value = JSON.parse(String(rawValue || '').trim())
    if (!value || typeof value !== 'object') return null
    if (
      !Array.isArray(value.labels) &&
      !Array.isArray(value.data) &&
      !Array.isArray(value.series)
    ) {
      return null
    }
    return value
  } catch (_) {
    return null
  }
}
</script>

<style scoped>
.data-ops-ai-markdown :deep(.markdown-content) {
  color: inherit;
}

.data-ops-ai-markdown :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  font-size: 0.75rem;
}

.data-ops-ai-markdown :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
