<template>
  <button
    class="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-slate-900 text-white shadow-lg shadow-slate-300 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-300"
    type="button"
    aria-label="打开 AI 数据助手"
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
      class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[920px] flex-col border-l border-slate-200 bg-white shadow-2xl"
      aria-label="AI 数据助手"
    >
      <header class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-base font-semibold text-slate-900">
              AI 数据助手
            </p>
            <p class="mt-1 text-xs text-slate-500">
              基于当前 Data Ops 上下文进行经营洞察分析
            </p>
          </div>
          <button
            class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            type="button"
            @click="closeDrawer"
          >
            关闭
          </button>
        </div>
      </header>

      <div class="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section class="flex min-h-0 flex-col border-r border-slate-100">
          <div
            v-if="questionGroups.length"
            class="border-b border-slate-100 p-4"
          >
            <div class="flex gap-2 overflow-x-auto pb-1">
              <button
                v-for="question in quickQuestions"
                :key="question"
                class="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs leading-5 text-slate-600 hover:border-indigo-200 hover:text-indigo-700 disabled:opacity-50"
                :disabled="loading"
                type="button"
                @click="$emit('ask', question)"
              >
                {{ question }}
              </button>
            </div>
          </div>

          <div
            ref="messagesEl"
            class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4"
          >
            <DataOpsAiMessage
              v-for="(message, index) in messages"
              :key="index"
              :message="message"
            />
          </div>

          <form
            class="border-t border-slate-100 p-4"
            @submit.prevent="$emit('send')"
          >
            <div class="flex gap-2">
              <textarea
                :value="input"
                class="max-h-28 min-h-10 min-w-0 flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm leading-5 outline-none focus:border-indigo-300"
                placeholder="输入业务问题，例如：用表格列出待回款风险"
                rows="1"
                @input="$emit('update:input', $event.target.value)"
                @keydown.enter.exact.prevent="$emit('send')"
              />
              <button
                v-if="loading"
                class="h-10 rounded-lg border border-slate-200 px-4 text-sm font-medium text-slate-600 hover:bg-slate-50"
                type="button"
                @click="$emit('stop')"
              >
                停止
              </button>
              <button
                v-else
                class="h-10 rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white disabled:opacity-50"
                :disabled="!input.trim()"
                type="submit"
              >
                发送
              </button>
            </div>
          </form>
        </section>

        <DataOpsAiContextPanel :context="context" />
      </div>
    </aside>
  </Transition>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import DataOpsAiContextPanel from './DataOpsAiContextPanel.vue'
import DataOpsAiMessage from './DataOpsAiMessage.vue'

const props = defineProps({
  context: { type: Object, default: null },
  input: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  messages: { type: Array, default: () => [] },
})

defineEmits(['ask', 'send', 'stop', 'update:input'])

const isOpen = ref(false)
const messagesEl = ref(null)
const assistantProfile = computed(() => props.context?.assistant || {})
const questionGroups = computed(
  () => assistantProfile.value.question_groups || []
)
const quickQuestions = computed(() =>
  questionGroups.value.flatMap((group) => group.questions || []).slice(0, 8)
)
const lastMessageContent = computed(() => {
  const lastMessage = props.messages[props.messages.length - 1]
  return lastMessage?.content || ''
})

watch(
  () => [props.messages.length, props.loading, lastMessageContent.value],
  () => scrollToBottom()
)

function openDrawer() {
  isOpen.value = true
  scrollToBottom()
}

function closeDrawer() {
  isOpen.value = false
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}
</script>

<style scoped>
.data-ops-ai-overlay-enter-active,
.data-ops-ai-overlay-leave-active,
.data-ops-ai-drawer-enter-active,
.data-ops-ai-drawer-leave-active {
  transition: all 0.18s ease;
}

.data-ops-ai-overlay-enter-from,
.data-ops-ai-overlay-leave-to { opacity: 0; }

.data-ops-ai-drawer-enter-from,
.data-ops-ai-drawer-leave-to { transform: translateX(100%); }
</style>
