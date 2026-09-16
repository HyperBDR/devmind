<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Folder,
  Loader2,
  X,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import {
  getInvoiceFeishuTargets,
  type InvoiceFeishuTarget,
} from '../../api/invoices'

const props = defineProps<{
  open: boolean
  invoiceId: string
}>()
const { t } = useI18n()

const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [folder: { token: string; name: string }]
  toast: [message: string]
}>()

const loading = ref(false)
const folders = ref<InvoiceFeishuTarget[]>([])
const errorMessage = ref('')
const currentFolder = ref<InvoiceFeishuTarget | null>(null)
const path = ref<InvoiceFeishuTarget[]>([])

const canSelectCurrent = computed(() => !loading.value && !folders.value.length)

function close() {
  emit('update:open', false)
}

async function loadFolders(folderToken = '', folderName = '', reset = false) {
  loading.value = true
  errorMessage.value = ''
  try {
    const listing = await getInvoiceFeishuTargets(
      props.invoiceId,
      folderToken,
    )
    currentFolder.value = listing.current
    folders.value = listing.items
    const current = {
      ...listing.current,
      name: folderName || listing.current.name,
    }
    path.value = reset || !path.value.length
      ? [current]
      : [...path.value, current]
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error
      ? error.message
      : 'Could not load Feishu folders'
  } finally {
    loading.value = false
  }
}

function enterFolder(folder: InvoiceFeishuTarget) {
  void loadFolders(folder.token, folder.name)
}

function goBack() {
  if (path.value.length <= 1 || loading.value) return
  const previous = path.value[path.value.length - 2]
  path.value = path.value.slice(0, -1)
  void loadFolders(previous.token, previous.name, true)
}

function selectCurrentFolder() {
  if (!currentFolder.value || !canSelectCurrent.value) return
  emit('select', currentFolder.value)
  close()
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      path.value = []
      void loadFolders()
    }
  },
)
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[160] flex items-center justify-center bg-slate-900/35 p-4 backdrop-blur-[2px]"
  >
    <div class="flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-dm-border bg-white shadow-2xl">
      <div class="flex shrink-0 items-start justify-between border-b border-dm-border px-5 py-4">
        <div>
          <h3 class="text-base font-bold text-dm-text">
            {{ t('quotation.sales.chooseFeishuFolder') }}
          </h3>
          <p class="mt-1 text-sm text-dm-text-tertiary">
            {{ t('quotation.sales.chooseFeishuFolderHint') }}
          </p>
        </div>
        <button
          type="button"
          class="rounded-lg p-1.5 text-dm-text-tertiary hover:bg-slate-100 hover:text-dm-text"
          :aria-label="t('quotation.common.close')"
          @click="close"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="flex shrink-0 items-center gap-2 border-b border-dm-border bg-[#fafafa] px-5 py-3">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-dm-border bg-white px-3 py-1.5 text-sm font-semibold text-dm-text-secondary hover:bg-slate-50 disabled:opacity-40"
          :disabled="path.length <= 1 || loading"
          @click="goBack"
        >
          <ArrowLeft class="h-3.5 w-3.5" />
          {{ t('quotation.common.back') }}
        </button>
        <div class="flex min-w-0 flex-1 items-center gap-1 text-sm text-dm-text-tertiary">
          <template v-for="(item, index) in path" :key="item.token">
            <ChevronRight v-if="index > 0" class="h-3.5 w-3.5 shrink-0" />
            <span
              class="truncate"
              :class="index === path.length - 1 ? 'font-semibold text-dm-text' : ''"
            >
              {{ item.name }}
            </span>
          </template>
        </div>
      </div>

      <div class="min-h-[260px] flex-1 overflow-y-auto p-5">
        <p
          v-if="errorMessage"
          class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          role="alert"
        >
          {{ errorMessage }}
        </p>
        <div
          v-if="loading"
          class="flex h-56 items-center justify-center gap-2 text-sm text-dm-text-tertiary"
        >
          <Loader2 class="h-4 w-4 animate-spin" />
          {{ t('quotation.sales.loadingFeishuFolders') }}
        </div>
        <div
          v-else-if="!folders.length"
          class="flex h-56 flex-col items-center justify-center rounded-xl border border-dashed border-dm-border bg-[#fafafa] text-center"
        >
          <Folder class="h-8 w-8 text-slate-300" />
          <p class="mt-3 text-sm font-semibold text-dm-text">
            {{ t('quotation.sales.noFeishuFolders') }}
          </p>
        </div>
        <div v-else class="space-y-2">
          <button
            v-for="folder in folders"
            :key="folder.token"
            type="button"
            class="flex w-full items-center gap-3 rounded-xl border border-dm-border bg-white px-3 py-3 text-left transition hover:border-blue-200 hover:bg-blue-50/40"
            @click="enterFolder(folder)"
          >
            <Folder class="h-4 w-4 shrink-0 text-amber-500" />
            <span class="min-w-0 flex-1 truncate text-sm font-semibold text-dm-text">
              {{ folder.name }}
            </span>
            <ChevronRight class="h-4 w-4 shrink-0 text-dm-text-tertiary" />
          </button>
        </div>
      </div>

      <div class="flex shrink-0 items-center justify-between gap-3 border-t border-dm-border px-5 py-4">
        <div class="min-w-0 text-sm text-dm-text-tertiary">
          {{ t('quotation.sales.selectedFeishuFolder') }}
          <span class="font-semibold text-dm-text">
            {{ currentFolder?.name || '—' }}
          </span>
        </div>
        <div class="flex items-center gap-2">
        <button
          type="button"
          class="rounded-lg border border-dm-border px-4 py-2 text-sm font-semibold text-dm-text-secondary hover:bg-slate-50"
          @click="close"
        >
          {{ t('quotation.common.cancel') }}
        </button>
        <button
          type="button"
          class="dm-btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold disabled:opacity-40"
          :disabled="!canSelectCurrent"
          @click="selectCurrentFolder"
        >
          <Check class="h-3.5 w-3.5" />
          {{ t('quotation.sales.uploadToFeishu') }}
        </button>
        </div>
      </div>
    </div>
  </div>
</template>
