<!--
  ResalePublishingDrawer — hosts the immersive publishing workspace.
  Modeled after the demo.html "Model Publishing Workspace" header:
  sticky top bar with back button + draft + publish.
-->
<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex justify-end bg-slate-950/40"
        @click.self="tryClose"
      >
        <Transition
          enter-active-class="transition-transform duration-300 ease-out"
          enter-from-class="translate-x-full"
          enter-to-class="translate-x-0"
          leave-active-class="transition-transform duration-200 ease-in"
          leave-from-class="translate-x-0"
          leave-to-class="translate-x-full"
        >
          <aside
            v-if="open"
            class="publishing-drawer-panel flex h-full flex-col bg-slate-50 shadow-2xl"
          >
            <header class="publishing-drawer-header">
              <div class="flex min-w-0 flex-1 items-center gap-3">
                <button type="button" class="header-back" @click="tryClose">
                  <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
                    <path
                      fill-rule="evenodd"
                      d="M12.79 5.23a.75.75 0 0 1 0 1.06L9.06 10l3.73 3.71a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <span class="sr-only">返回</span>
                </button>
                <div class="min-w-0 flex-1">
                  <p
                    class="text-[11px] font-bold uppercase tracking-[0.18em] text-indigo-600"
                  >
                    Model Publishing Workspace
                  </p>
                  <h2
                    class="mt-0.5 truncate text-base font-bold text-slate-900"
                  >
                    模型沉浸式上架工作台
                  </h2>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="saving"
                  @click="handleSaveDraft"
                >
                  暂存草稿
                </button>
                <button
                  type="button"
                  class="btn-primary"
                  :disabled="!canPublish || saving"
                  @click="handlePublish"
                >
                  {{ saving ? '发布中…' : '确认并发布上架' }}
                </button>
              </div>
            </header>

            <div class="flex-1 overflow-y-auto px-5 py-5">
              <ResalePublishingWorkspace
                ref="workspaceRef"
                :agione-platform="agionePlatform"
                :platforms="platforms"
                :providers="providers"
                :models="models"
                :channels="channels"
                :procurement-rows="procurementRows"
                :price-items="priceItems"
                :listings="listings"
                :point-conversion="pointConversion"
                :display-currency="displayCurrency"
                :exchange-rate="exchangeRate"
                @change="onWorkspaceChange"
              />
            </div>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import ResalePublishingWorkspace from '@/components/llm-ops/ResalePublishingWorkspace.vue'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  agionePlatform: {
    type: Object,
    default: null
  },
  platforms: {
    type: Array,
    required: true
  },
  providers: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  channels: {
    type: Array,
    required: true
  },
  procurementRows: {
    type: Array,
    default: () => []
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  listings: {
    type: Array,
    default: () => []
  },
  pointConversion: {
    type: Object,
    default: null
  },
  displayCurrency: {
    type: String,
    default: 'CNY'
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  }
})

const emit = defineEmits(['update:open', 'saved', 'draft'])
const { showSuccess, showError, showInfo } = useToast()

const workspaceRef = ref(null)
const saving = ref(false)
const latestPayload = ref(null)

const canPublish = computed(() => {
  if (!latestPayload.value) return false
  const { listings, platformId, modelId } = latestPayload.value
  if (!platformId || !modelId) return false
  if (!listings.length) return false
  return listings.every(
    (l) =>
      l.upstreamAccount &&
      Number.isFinite(Number(l.priceIn)) &&
      Number.isFinite(Number(l.priceOut)) &&
      Number(l.priceIn) > 0 &&
      Number(l.priceOut) > 0
  )
})

function onWorkspaceChange(payload) {
  latestPayload.value = payload
}

function tryClose() {
  emit('update:open', false)
}

function handleSaveDraft() {
  if (!latestPayload.value?.listings?.length) {
    showInfo('当前没有可暂存的选择')
    return
  }
  emit('draft', latestPayload.value)
  showSuccess('已暂存草稿，可稍后继续')
  tryClose()
}

async function handlePublish() {
  if (!canPublish.value) return
  saving.value = true
  try {
    emit('saved', latestPayload.value)
    showSuccess('上架请求已提交，正在同步到挂售平台')
    tryClose()
  } catch (error) {
    showError(error?.message || '发布失败')
  } finally {
    saving.value = false
  }
}

function handleKeydown(event) {
  if (event.key === 'Escape' && props.open) {
    tryClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

watch(
  () => props.open,
  (next, prev) => {
    if (next && !prev) {
      latestPayload.value = null
    }
  }
)
</script>

<style scoped>
.publishing-drawer-panel {
  width: min(100vw, 960px);
}

@media (min-width: 1280px) {
  .publishing-drawer-panel {
    width: min(80vw, 1200px);
  }
}

.publishing-drawer-header {
  @apply sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-3 shadow-sm;
}

.header-back {
  @apply inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50;
}
</style>
