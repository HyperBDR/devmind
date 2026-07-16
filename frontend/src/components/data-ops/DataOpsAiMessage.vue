<template>
  <div
    class="data-ops-message-row"
    :class="isUser ? 'data-ops-message-row-user' : ''"
  >
    <div
      class="data-ops-message-avatar"
      :class="isUser ? 'data-ops-message-avatar-user' : ''"
      aria-hidden="true"
    >
      <span v-if="isUser">{{ t('dataOps.ai.user') }}</span>
      <span v-else>AI</span>
    </div>

    <div
      class="data-ops-message-body"
      :class="isUser ? 'data-ops-message-body-user' : ''"
    >
      <div v-if="isUser" class="data-ops-user-card">
        {{ message.content }}
      </div>

      <template v-else>
        <div
          v-if="hasProcessPanel"
          class="data-ops-thinking-panel"
          :class="isActive ? 'data-ops-thinking-panel-live' : ''"
        >
          <button
            type="button"
            class="data-ops-thinking-header"
            @click="processOpen = !processOpen"
          >
            <span class="data-ops-thinking-dot" :class="statusDotClass" />
            <span class="data-ops-thinking-status">
              <span class="truncate">
                {{ panelStatusText }}
              </span>
              <span
                v-if="isActive && !visibleSteps.length"
                class="data-ops-typing-dots"
                aria-hidden="true"
              >
                <span /><span /><span />
              </span>
            </span>
            <span class="data-ops-thinking-elapsed">
              {{ elapsedText }}
            </span>
            <span v-if="progressSteps.length" class="data-ops-thinking-count">
              {{ progressSteps.length }}
            </span>
            <span v-if="progressSteps.length" class="data-ops-thinking-chevron">
              {{ processOpen ? '⌃' : '⌄' }}
            </span>
          </button>

          <div
            v-if="processOpen && visibleSteps.length"
            class="data-ops-thinking-body"
          >
            <div
              v-for="step in visibleSteps"
              :key="step.id"
              class="data-ops-thinking-step"
            >
              <span class="data-ops-thinking-bullet">▸</span>
              <span>
                <span class="data-ops-thinking-step-title">
                  {{ step.title }}
                </span>
                <span v-if="step.detail" class="data-ops-thinking-step-detail">
                  {{ step.detail }}
                </span>
                <span v-if="step.count > 1" class="data-ops-thinking-repeat">
                  ×{{ step.count }}
                </span>
              </span>
            </div>
          </div>
        </div>

        <div
          v-if="markdownContent || shouldShowPending"
          class="data-ops-assistant-card"
        >
          <MarkdownRenderer
            v-if="displayMarkdownContent"
            :content="displayMarkdownContent"
            :relative-internal-links="true"
            class="data-ops-ai-markdown"
            :class="{ 'data-ops-ai-markdown-streaming': isActive }"
          />
          <div v-else class="data-ops-live-text">
            {{ pendingText }}
            <span class="data-ops-typing-dots" aria-hidden="true">
              <span /><span /><span />
            </span>
          </div>
          <DataOpsAiChartBlock
            v-for="chart in charts"
            :key="chart.key"
            :chart="chart"
          />
          <div
            v-if="showFollowUpQuestions"
            class="data-ops-followups"
            :aria-label="t('dataOps.ai.followUpsLabel')"
          >
            <div class="data-ops-followups-heading">
              <span class="data-ops-followups-icon" aria-hidden="true">
                ↗
              </span>
              <div>
                <p class="data-ops-followups-title">
                  {{ t('dataOps.ai.followUpsTitle') }}
                </p>
                <p class="data-ops-followups-hint">
                  {{ t('dataOps.ai.followUpsDescription') }}
                </p>
              </div>
            </div>
            <div class="data-ops-followups-list">
              <button
                v-for="question in followUpQuestions"
                :key="question"
                class="data-ops-followup-button"
                type="button"
                @click="$emit('ask', question)"
              >
                <span>{{ question }}</span>
                <svg
                  aria-hidden="true"
                  class="data-ops-followup-arrow"
                  fill="none"
                  viewBox="0 0 20 20"
                >
                  <path
                    d="m7.5 5 5 5-5 5"
                    stroke="currentColor"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.5"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import MarkdownRenderer from '@/components/ui/MarkdownRenderer.vue'
import { splitFollowUpQuestions } from '@/utils/aiSuggestions'
import { normalizeDataOpsChart } from '@/utils/dataOpsChart'
import { localizeDataOpsProgressEvent } from '@/utils/dataOpsProgress'

import DataOpsAiChartBlock from './DataOpsAiChartBlock.vue'

const { t } = useI18n()

const props = defineProps({
  message: { type: Object, required: true }
})
defineEmits(['ask'])

const isUser = computed(() => props.message.role === 'user')
const content = computed(() => sanitizeDisplayContent(props.message.content))
const status = computed(() => props.message.status || 'done')
const isActive = computed(() =>
  ['thinking', 'streaming'].includes(status.value)
)
const elapsedText = computed(() => formatElapsed(props.message.elapsedMs || 0))
const statusLabel = computed(() => {
  const labels = {
    done: t('dataOps.ai.status.done'),
    error: t('dataOps.ai.status.error'),
    stopped: t('dataOps.ai.status.stopped'),
    streaming: t('dataOps.ai.status.streaming'),
    thinking: t('dataOps.ai.status.thinking')
  }
  return labels[status.value] || t('dataOps.ai.status.done')
})
const statusDotClass = computed(() => {
  const classes = {
    done: 'bg-emerald-500',
    error: 'bg-rose-500',
    stopped: 'bg-slate-400',
    streaming: 'animate-pulse bg-indigo-600',
    thinking: 'animate-pulse bg-amber-500'
  }
  return classes[status.value] || classes.done
})
const pendingText = computed(() => {
  if (status.value === 'thinking') return t('dataOps.ai.empty.thinking')
  if (status.value === 'streaming') return t('dataOps.ai.empty.streaming')
  return t('dataOps.ai.empty.default')
})
const rawProgressEvents = computed(() => props.message.progressEvents || [])
const progressSteps = computed(() =>
  groupProgressSteps(rawProgressEvents.value)
)
const visibleSteps = computed(() =>
  progressSteps.value.slice(0, revealedCount.value)
)
const latestStep = computed(() => {
  if (!visibleSteps.value.length) return null
  return visibleSteps.value[visibleSteps.value.length - 1]
})
const panelStatusText = computed(() => {
  if (!isActive.value) {
    const countText = progressSteps.value.length
      ? ` · ${t('dataOps.ai.stepsCount', {
          count: progressSteps.value.length
        })}`
      : ''
    return `${statusLabel.value}${countText}`
  }
  if (latestStep.value) {
    return latestStep.value.detail
      ? `${latestStep.value.title} · ${latestStep.value.detail}`
      : latestStep.value.title
  }
  return statusLabel.value
})
const hasProcessPanel = computed(
  () => isActive.value || progressSteps.value.length > 0
)
const shouldShowPending = computed(
  () => isActive.value || ['error', 'stopped'].includes(status.value)
)
const maxChartsPerAnswer = 2

const charts = computed(() => {
  const items = []
  for (const match of content.value.matchAll(chartFencePattern())) {
    const chart = parseChart(match[1])
    if (chart) items.push({ ...chart, key: `${items.length}-${chart.title}` })
    if (items.length >= maxChartsPerAnswer) break
  }
  return items
})

const plainContent = computed(() =>
  content.value.replace(chartFencePattern(), '').trim()
)
const parsedContent = computed(() => splitFollowUpQuestions(plainContent.value))
const markdownContent = computed(() => parsedContent.value.body)
const displayMarkdownContent = computed(() => markdownContent.value.trim())
const followUpQuestions = computed(() => parsedContent.value.questions)
const showFollowUpQuestions = computed(
  () => status.value === 'done' && followUpQuestions.value.length > 0
)
const processOpen = ref(isActive.value)
const revealedCount = ref(0)
let revealTimer = null

watch(
  () => progressSteps.value.length,
  () => {
    startRevealTimer()
  },
  { immediate: true }
)

watch(
  isActive,
  (active) => {
    if (active) {
      processOpen.value = true
      startRevealTimer()
      return
    }
    revealedCount.value = progressSteps.value.length
    processOpen.value = false
    stopRevealTimer()
  },
  { immediate: true }
)

watch(
  () => props.message.status,
  () => {
    if (!isActive.value) {
      revealedCount.value = progressSteps.value.length
      processOpen.value = false
    }
  }
)

onBeforeUnmount(() => {
  stopRevealTimer()
})

function chartFencePattern() {
  return /```(?:dataops-chart|chart)\s*([\s\S]*?)```/g
}

function parseChart(rawValue) {
  try {
    const value = JSON.parse(String(rawValue || '').trim())
    return normalizeDataOpsChart(value)
  } catch (_) {
    return null
  }
}

function formatElapsed(value) {
  const seconds = Number(value || 0) / 1000
  if (seconds < 10) return `${seconds.toFixed(1)}s`
  return `${Math.round(seconds)}s`
}

function groupProgressSteps(events) {
  const grouped = []
  for (const event of events) {
    const step = normalizeStep(event)
    const last = grouped[grouped.length - 1]
    if (
      last &&
      last.stage === step.stage &&
      last.title === step.title &&
      last.detail === step.detail
    ) {
      last.count += 1
    } else {
      grouped.push({
        ...step,
        count: 1,
        id: `${grouped.length}-${step.stage}-${step.title}`
      })
    }
  }
  return grouped
}

function normalizeStep(event) {
  const localized = localizeDataOpsProgressEvent(event, t)
  const metadata = localized.metadata
  const table = metadata.table
    ? t('dataOps.ai.tableRef', { table: metadata.table })
    : ''
  const result = metadata.result_summary || {}
  const rows =
    result.row_count === null || result.row_count === undefined
      ? ''
      : t('dataOps.ai.resultRows', { count: result.row_count })
  const fallbackDetail = [table, rows].filter(Boolean).join(', ')
  return {
    detail: localized.detail || fallbackDetail,
    stage: localized.stage,
    status: localized.status,
    title: localized.title || t('dataOps.feedback.progressStep')
  }
}

function startRevealTimer() {
  if (revealedCount.value < 1 && progressSteps.value.length) {
    revealedCount.value = 1
  }
  if (revealTimer || revealedCount.value >= progressSteps.value.length) {
    return
  }
  revealTimer = setInterval(() => {
    if (revealedCount.value >= progressSteps.value.length) {
      stopRevealTimer()
      return
    }
    revealedCount.value += 1
  }, 260)
}

function stopRevealTimer() {
  if (!revealTimer) return
  clearInterval(revealTimer)
  revealTimer = null
}

function sanitizeDisplayContent(value) {
  return String(value || '')
    .replace(/<｜｜DSML｜｜tool_calls>[\s\S]*?<\/｜｜DSML｜｜tool_calls>/g, '')
    .replace(/<｜｜DSML｜｜tool_calls>[\s\S]*$/g, '')
    .replace(
      /&lt;｜｜DSML｜｜tool_calls&gt;[\s\S]*?&lt;\/｜｜DSML｜｜tool_calls&gt;/g,
      ''
    )
    .replace(/&lt;｜｜DSML｜｜tool_calls&gt;[\s\S]*$/g, '')
    .trimStart()
}
</script>

<style scoped>
.data-ops-message-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 28px;
}

.data-ops-message-row-user {
  flex-direction: row-reverse;
}

.data-ops-message-avatar {
  display: flex;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-radius: 9px;
  background: #fff;
  color: #6b7280;
  font-size: 11px;
  font-weight: 700;
}

.data-ops-message-avatar-user {
  border-color: #4f46e5;
  background: #4f46e5;
  color: #fff;
}

.data-ops-message-body {
  min-width: 0;
  flex: 1;
}

.data-ops-message-body-user {
  width: fit-content;
  max-width: 640px;
  flex: none;
  text-align: right;
}

.data-ops-user-card {
  border-radius: 12px;
  background: #4f46e5;
  color: #fff;
  padding: 12px 16px;
  text-align: left;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 24px;
}

.data-ops-thinking-panel {
  width: 100%;
  overflow: hidden;
  margin-bottom: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}

.data-ops-thinking-panel-live {
  background: #f9fafb;
}

.data-ops-thinking-header {
  display: flex;
  width: 100%;
  cursor: pointer;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 8px 12px;
  text-align: left;
  transition: background 0.15s ease;
}

.data-ops-thinking-header:hover {
  background: #f3f4f6;
}

.data-ops-thinking-dot {
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 999px;
}

.data-ops-thinking-status {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 8px;
  color: #374151;
  font-size: 14px;
}

.data-ops-thinking-elapsed {
  flex-shrink: 0;
  color: #9ca3af;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.data-ops-thinking-count {
  border-radius: 999px;
  background: #e5e7eb;
  color: #6b7280;
  padding: 2px 6px;
  font-size: 12px;
}

.data-ops-thinking-chevron {
  flex-shrink: 0;
  color: #9ca3af;
  font-size: 13px;
  line-height: 1;
}

.data-ops-thinking-body {
  max-height: 160px;
  overflow-y: auto;
  border-top: 1px solid #e5e7eb;
  padding: 8px 12px;
}

.data-ops-thinking-step {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 2px 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 20px;
}

.data-ops-thinking-bullet {
  flex-shrink: 0;
  color: #d1d5db;
}

.data-ops-thinking-step-title {
  color: #374151;
  font-weight: 600;
}

.data-ops-thinking-step-detail {
  margin-left: 4px;
  overflow-wrap: anywhere;
  color: #6b7280;
}

.data-ops-thinking-repeat {
  margin-left: 4px;
  color: #9ca3af;
}

.data-ops-assistant-card {
  min-width: 0;
}

.data-ops-live-text {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 14px;
  line-height: 24px;
}

.data-ops-typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.data-ops-typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #9ca3af;
  animation: data-ops-typing-dot 1.2s ease-in-out infinite;
}

.data-ops-followups {
  margin-top: 20px;
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}

.data-ops-followups-heading {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.data-ops-followups-icon {
  display: flex;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: #f1f5f9;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.data-ops-followups-title {
  margin: 0;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  line-height: 18px;
}

.data-ops-followups-hint {
  margin: 1px 0 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 16px;
}

.data-ops-followups-list {
  display: grid;
  gap: 6px;
}

.data-ops-followup-button {
  display: flex;
  width: 100%;
  max-width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  padding: 9px 12px;
  text-align: left;
  font-size: 13px;
  line-height: 20px;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.data-ops-followup-button:hover {
  border-color: #c7d2fe;
  background: #eef2ff;
  color: #3730a3;
}

.data-ops-followup-button:focus-visible {
  outline: 2px solid #a5b4fc;
  outline-offset: 2px;
}

.data-ops-followup-arrow {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: #cbd5e1;
  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.data-ops-followup-button:hover .data-ops-followup-arrow {
  color: #6366f1;
  transform: translateX(2px);
}

.data-ops-typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.data-ops-typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.data-ops-ai-markdown :deep(.markdown-content) {
  color: inherit;
}

.data-ops-ai-markdown :deep(.markdown-content p) {
  margin-bottom: 12px;
  color: #374151;
  font-size: 16px;
  line-height: 28px;
}

.data-ops-ai-markdown :deep(.markdown-content h1),
.data-ops-ai-markdown :deep(.markdown-content h2),
.data-ops-ai-markdown :deep(.markdown-content h3),
.data-ops-ai-markdown :deep(.markdown-content h4) {
  color: #111827;
}

.data-ops-ai-markdown :deep(.markdown-content ul),
.data-ops-ai-markdown :deep(.markdown-content ol) {
  margin-bottom: 12px;
  padding-left: 20px;
}

.data-ops-ai-markdown :deep(.markdown-content li) {
  margin-bottom: 8px;
  color: #374151;
  font-size: 16px;
  line-height: 28px;
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

.data-ops-ai-markdown-streaming :deep(.markdown-content > *:last-child)::after {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  margin-left: 4px;
  vertical-align: middle;
  background: #4f46e5;
  animation: data-ops-cursor-blink 1s steps(2, start) infinite;
}

@keyframes data-ops-typing-dot {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@keyframes data-ops-cursor-blink {
  0%,
  45% {
    opacity: 1;
  }
  46%,
  100% {
    opacity: 0;
  }
}
</style>
