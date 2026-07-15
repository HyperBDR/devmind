<template>
  <button
    class="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-slate-900 text-white shadow-lg shadow-slate-300 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
    type="button"
    :aria-label="t('dataOps.ai.openLabel')"
    @click="openDrawer"
  >
    <svg
      aria-hidden="true"
      class="h-6 w-6"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z"
        stroke="currentColor"
        stroke-linejoin="round"
        stroke-width="1.8"
      />
      <path
        d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"
        stroke="currentColor"
        stroke-linejoin="round"
        stroke-width="1.6"
      />
    </svg>
  </button>

  <Transition name="data-ops-ai-overlay">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 bg-slate-950/30 backdrop-blur-sm"
      @click.self="closeDrawer"
    />
  </Transition>

  <Transition name="data-ops-ai-drawer">
    <aside
      v-if="isOpen"
      class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[980px] flex-col border-l border-slate-200 bg-white shadow-2xl"
      :aria-label="t('dataOps.ai.drawerLabel')"
    >
      <header class="border-b border-slate-200 px-5 py-4">
        <div
          class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
        >
          <div>
            <p class="text-base font-semibold text-slate-900">
              {{ t('dataOps.ai.title') }}
            </p>
            <p class="mt-1 text-xs text-slate-500">
              {{ t('dataOps.ai.subtitle') }}
            </p>
          </div>
          <div class="flex shrink-0 flex-wrap items-center gap-2">
            <button
              class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              type="button"
              @click="historyOpen = !historyOpen"
            >
              {{
                historyOpen
                  ? t('dataOps.ai.collapseHistory')
                  : t('dataOps.ai.history')
              }}
            </button>
            <button
              class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              :disabled="loading"
              type="button"
              @click="$emit('new-chat')"
            >
              {{ t('dataOps.ai.newChat') }}
            </button>
            <button
              class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              type="button"
              @click="closeDrawer"
            >
              {{ t('dataOps.ai.close') }}
            </button>
          </div>
        </div>
      </header>

      <div
        class="min-h-0 flex-1"
        :class="historyOpen ? 'grid lg:grid-cols-[280px_minmax(0,1fr)]' : ''"
      >
        <aside
          v-if="historyOpen"
          class="min-h-0 overflow-y-auto border-b border-slate-200 bg-slate-50 p-3 lg:border-b-0 lg:border-r"
          :aria-label="t('dataOps.ai.historyLabel')"
        >
          <div class="mb-3 flex items-center justify-between gap-3">
            <p class="text-sm font-bold text-slate-900">
              {{ t('dataOps.ai.historyLabel') }}
            </p>
            <span class="text-xs text-slate-400">{{ history.length }}</span>
          </div>
          <div v-if="history.length" class="space-y-2">
            <article
              v-for="item in history"
              :key="item.id"
              class="group rounded-lg border bg-white p-3 transition hover:border-indigo-200"
              :class="
                item.id === activeHistoryId
                  ? 'border-indigo-300 ring-1 ring-indigo-100'
                  : 'border-slate-200'
              "
            >
              <button
                class="block w-full text-left"
                :disabled="loading"
                type="button"
                @click="$emit('select-history', item.id)"
              >
                <p class="line-clamp-2 text-sm font-semibold text-slate-800">
                  {{ item.title }}
                </p>
                <p class="mt-1 text-xs text-slate-400">
                  {{ formatHistoryTime(item.updatedAt) }} ·
                  {{
                    t('dataOps.ai.messagesCount', {
                      count: item.messageCount || 0
                    })
                  }}
                </p>
              </button>
              <button
                class="mt-2 text-xs font-medium text-slate-400 hover:text-rose-600"
                type="button"
                @click.stop="$emit('delete-history', item.id)"
              >
                {{ t('dataOps.ai.delete') }}
              </button>
            </article>
          </div>
          <div
            v-else
            class="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-6 text-center text-xs leading-5 text-slate-400"
          >
            {{ t('dataOps.ai.noHistory') }}
          </div>
        </aside>

        <section
          class="flex h-full min-h-0 flex-col"
          :class="
            isEmptyConversation ? 'justify-center gap-5 px-4 py-6 sm:px-6' : ''
          "
        >
          <div
            ref="messagesEl"
            class="min-h-0 overflow-y-auto"
            :class="
              isEmptyConversation
                ? 'w-full max-w-3xl self-center'
                : 'w-full max-w-4xl flex-1 self-center space-y-3 p-4 sm:p-6'
            "
          >
            <div v-if="showQuickQuestions" class="w-full">
              <div class="mb-5 text-center">
                <span
                  class="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700"
                  aria-hidden="true"
                >
                  <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <path
                      d="M12 3l1.7 4.6L18 9.2l-4.3 1.6L12 15.4l-1.7-4.6L6 9.2l4.3-1.6L12 3Z"
                      stroke="currentColor"
                      stroke-linejoin="round"
                      stroke-width="1.7"
                    />
                    <path
                      d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z"
                      stroke="currentColor"
                      stroke-linejoin="round"
                      stroke-width="1.5"
                    />
                  </svg>
                </span>
                <h2 class="mt-3 text-lg font-semibold text-slate-900">
                  {{ t('dataOps.ai.startTitle') }}
                </h2>
                <p class="mt-1 text-sm text-slate-500">
                  {{ t('dataOps.ai.startDescription') }}
                </p>
              </div>

              <div
                class="flex flex-col gap-2"
                :aria-label="t('dataOps.ai.recommendedQuestions')"
              >
                <button
                  v-for="prompt in quickPrompts"
                  :key="`${prompt.groupKey}-${prompt.question}`"
                  class="group flex w-full items-center gap-3 rounded-lg bg-slate-50 px-4 py-3 text-left transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="loading"
                  type="button"
                  @click="$emit('ask', prompt.question)"
                >
                  <span
                    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-slate-400 shadow-sm ring-1 ring-slate-200 transition group-hover:text-indigo-600 group-hover:ring-indigo-200"
                    aria-hidden="true"
                  >
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 20 20">
                      <path
                        d="M4.5 5.5h11v7h-6l-3 2v-2h-2v-7Z"
                        stroke="currentColor"
                        stroke-linejoin="round"
                        stroke-width="1.4"
                      />
                    </svg>
                  </span>
                  <span class="min-w-0 flex-1">
                    <span
                      class="block text-[11px] font-semibold text-slate-400"
                    >
                      {{ prompt.groupTitle }}
                    </span>
                    <span
                      class="mt-0.5 block text-sm leading-5 text-slate-700 transition group-hover:text-slate-950"
                    >
                      {{ prompt.question }}
                    </span>
                  </span>
                  <svg
                    aria-hidden="true"
                    class="h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500"
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

            <DataOpsAiMessage
              v-for="(message, index) in messages"
              :key="index"
              :fallback-suggestions="
                index === lastAssistantIndex ? fallbackSuggestions : []
              "
              :message="message"
              @ask="$emit('ask', $event)"
            />
            <div
              v-if="loading"
              aria-hidden="true"
              class="data-ops-stream-reserve"
            />
          </div>

          <form
            class="w-full"
            :class="
              isEmptyConversation
                ? 'max-w-3xl self-center rounded-xl border border-slate-200 bg-white p-2 shadow-sm'
                : 'border-t border-slate-100 bg-white p-4'
            "
            @submit.prevent="$emit('send')"
          >
            <div
              class="flex gap-2"
              :class="
                isEmptyConversation
                  ? ''
                  : 'mx-auto max-w-4xl rounded-xl border border-slate-200 p-2 shadow-sm'
              "
            >
              <textarea
                :value="input"
                class="max-h-28 min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-5 text-slate-800 outline-none placeholder:text-slate-400"
                :class="isEmptyConversation ? 'min-h-20' : 'min-h-10'"
                :aria-label="t('dataOps.ai.inputLabel')"
                :placeholder="t('dataOps.ai.placeholder')"
                rows="1"
                @input="$emit('update:input', $event.target.value)"
                @keydown.enter.exact.prevent="$emit('send')"
              />
              <button
                v-if="loading"
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-2"
                :aria-label="t('dataOps.ai.stop')"
                :title="t('dataOps.ai.stop')"
                type="button"
                @click="$emit('stop')"
              >
                <svg
                  aria-hidden="true"
                  class="h-4 w-4"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <rect height="10" rx="1.5" width="10" x="7" y="7" />
                </svg>
              </button>
              <button
                v-else
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                :class="isEmptyConversation ? 'self-end' : ''"
                :disabled="!input.trim()"
                :aria-label="t('dataOps.ai.send')"
                :title="t('dataOps.ai.send')"
                type="submit"
              >
                <svg
                  aria-hidden="true"
                  class="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M12 19V5m0 0-6 6m6-6 6 6"
                    stroke="currentColor"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2.2"
                  />
                </svg>
              </button>
            </div>
          </form>
        </section>
      </div>
    </aside>
  </Transition>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  buildQuickPrompts,
  selectFollowUpQuestions
} from '@/utils/aiSuggestions'

import DataOpsAiMessage from './DataOpsAiMessage.vue'

const props = defineProps({
  activeHistoryId: { type: String, default: '' },
  context: { type: Object, default: null },
  history: { type: Array, default: () => [] },
  input: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  messages: { type: Array, default: () => [] }
})

const { locale, t, tm } = useI18n()

defineEmits([
  'ask',
  'delete-history',
  'new-chat',
  'select-history',
  'send',
  'stop',
  'update:input'
])

const isOpen = ref(false)
const historyOpen = ref(false)
const messagesEl = ref(null)
let streamScrollFrame = null
const assistantProfile = computed(() => props.context?.assistant || {})
const localizedQuestionGroups = computed(() => {
  const translatedGroups = tm('dataOps.ai.questionGroups') || {}
  const sourceGroups = assistantProfile.value.question_groups || []
  const keys = sourceGroups.length
    ? sourceGroups.map((group) => group.key)
    : Object.keys(translatedGroups)
  return keys
    .filter((key) => translatedGroups[key])
    .map((key) => ({ key, ...translatedGroups[key] }))
})
const questionGroups = computed(
  () => localizedQuestionGroups.value
)
const hasUserMessages = computed(() =>
  props.messages.some((message) => message.role === 'user')
)
const isEmptyConversation = computed(
  () => props.messages.length === 0 && !props.loading
)
const quickPrompts = computed(() => buildQuickPrompts(questionGroups.value, 6))
const showQuickQuestions = computed(
  () =>
    quickPrompts.value.length > 0 && !hasUserMessages.value && !props.loading
)
const lastAssistantIndex = computed(() => {
  for (let index = props.messages.length - 1; index >= 0; index -= 1) {
    if (props.messages[index]?.role === 'assistant') return index
  }
  return -1
})
const latestUserQuestion = computed(() => {
  for (let index = props.messages.length - 1; index >= 0; index -= 1) {
    const message = props.messages[index]
    if (message?.role === 'user') return message.content || ''
  }
  return ''
})
const fallbackSuggestions = computed(() =>
  selectFollowUpQuestions(latestUserQuestion.value, questionGroups.value)
)
const lastMessageContent = computed(() => {
  const lastMessage = props.messages[props.messages.length - 1]
  return lastMessage?.content || ''
})
const lastProgressCount = computed(() => {
  const lastMessage = props.messages[props.messages.length - 1]
  return lastMessage?.progressEvents?.length || 0
})

watch(
  () => [props.messages.length, props.loading],
  ([messageCount, loading], [previousCount, wasLoading] = []) => {
    if (loading && (messageCount > (previousCount || 0) || !wasLoading)) {
      positionLatestUserQuestion()
      return
    }
    if (!loading && messageCount !== previousCount) {
      scrollToBottom()
    }
  }
)

watch(
  () => [lastMessageContent.value, lastProgressCount.value],
  () => {
    if (props.loading) {
      scheduleStreamingScroll()
      return
    }
    scrollToBottom()
  }
)

function openDrawer() {
  isOpen.value = true
  positionConversationOnOpen()
}

function closeDrawer() {
  isOpen.value = false
}

function formatHistoryTime(value) {
  if (!value) return t('dataOps.ai.justNow')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return t('dataOps.ai.justNow')
  return date.toLocaleString(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
    day: '2-digit',
    hour: '2-digit',
    hour12: false,
    minute: '2-digit',
    month: '2-digit'
  })
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

async function positionLatestUserQuestion() {
  await nextTick()
  if (!messagesEl.value) return
  const userRows = messagesEl.value.querySelectorAll(
    '.data-ops-message-row-user'
  )
  const latestUser = userRows[userRows.length - 1]
  if (!latestUser) return
  const containerRect = messagesEl.value.getBoundingClientRect()
  const latestUserRect = latestUser.getBoundingClientRect()
  const latestUserTop =
    latestUserRect.top - containerRect.top + messagesEl.value.scrollTop
  messagesEl.value.scrollTop = Math.max(
    0,
    latestUserTop - messagesEl.value.clientHeight * 0.25
  )
}

function scheduleStreamingScroll() {
  if (streamScrollFrame !== null) return
  streamScrollFrame = requestAnimationFrame(() => {
    streamScrollFrame = null
    keepStreamingAnswerVisible()
  })
}

async function keepStreamingAnswerVisible() {
  await nextTick()
  if (!messagesEl.value) return
  const assistantRows = messagesEl.value.querySelectorAll(
    '.data-ops-message-row:not(.data-ops-message-row-user)'
  )
  const latestAssistant = assistantRows[assistantRows.length - 1]
  if (!latestAssistant) return
  const containerRect = messagesEl.value.getBoundingClientRect()
  const assistantRect = latestAssistant.getBoundingClientRect()
  const overflow = assistantRect.bottom - (containerRect.bottom - 24)
  if (overflow > 0) {
    messagesEl.value.scrollTop += overflow
  }
}

async function positionConversationOnOpen() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = isEmptyConversation.value
      ? 0
      : messagesEl.value.scrollHeight
  }
}

onBeforeUnmount(() => {
  if (streamScrollFrame !== null) {
    cancelAnimationFrame(streamScrollFrame)
  }
})
</script>

<style scoped>
.data-ops-ai-overlay-enter-active,
.data-ops-ai-overlay-leave-active,
.data-ops-ai-drawer-enter-active,
.data-ops-ai-drawer-leave-active {
  transition: all 0.18s ease;
}

.data-ops-ai-overlay-enter-from,
.data-ops-ai-overlay-leave-to {
  opacity: 0;
}

.data-ops-ai-drawer-enter-from,
.data-ops-ai-drawer-leave-to {
  transform: translateX(100%);
}

.data-ops-stream-reserve {
  height: 75%;
  min-height: 18rem;
}
</style>
