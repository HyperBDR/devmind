<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeft, Check, ChevronRight, Folder, Loader2, X } from 'lucide-vue-next'
import {
  feishuFolderOpenToken,
  isFeishuFolderItem,
  listFeishuFolder,
  type FeishuFileItem,
} from '../api/feishu'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const props = defineProps<{
  open: boolean
  intent: 'upload' | 'import'
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [folder: { token: string; name: string }]
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

interface BreadcrumbItem {
  token: string
  name: string
}

const { t } = useQuotationI18n()

const loading = ref(false)
const currentToken = ref('')
const currentName = ref('')
const rootToken = ref('')
const files = ref<FeishuFileItem[]>([])
const path = ref<BreadcrumbItem[]>([])

const folders = computed(() => files.value.filter(isFeishuFolderItem))

const title = computed(() =>
  props.intent === 'upload'
    ? t('quotation.components.folderPicker.uploadTitle')
    : t('quotation.components.folderPicker.importTitle'),
)

const confirmLabel = computed(() =>
  props.intent === 'upload'
    ? t('quotation.components.folderPicker.uploadConfirm')
    : t('quotation.components.folderPicker.importConfirm'),
)

function close() {
  emit('update:open', false)
}

async function openFolder(token?: string, name?: string, replacePath = false) {
  loading.value = true
  try {
    const listing = await listFeishuFolder(token)
    currentToken.value = listing.folder_token
    currentName.value = name || listing.folder_name
    rootToken.value = listing.root_folder_token || listing.folder_token
    files.value = listing.files || []

    if (replacePath || !path.value.length) {
      path.value = [{ token: listing.folder_token, name: currentName.value }]
    } else if (token) {
      path.value = [...path.value, { token: listing.folder_token, name: currentName.value }]
    }
  } catch (err: unknown) {
    emit(
      'toast',
      err instanceof Error
        ? err.message
        : t('quotation.components.folderPicker.loadFailed'),
      'error',
    )
  } finally {
    loading.value = false
  }
}

function enterFolder(folder: FeishuFileItem) {
  const token = feishuFolderOpenToken(folder)
  if (!token) return
  void openFolder(token, folder.name)
}

function goBack() {
  if (path.value.length <= 1) return
  const nextPath = path.value.slice(0, -1)
  const target = nextPath[nextPath.length - 1]
  path.value = nextPath
  void openFolder(target.token, target.name, true)
}

function selectCurrentFolder() {
  if (!currentToken.value) return
  emit('select', { token: currentToken.value, name: currentName.value })
  close()
}

watch(
  () => props.open,
  (open) => {
    if (open) void openFolder(undefined, undefined, true)
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
          <h3 class="text-base font-bold text-dm-text">{{ title }}</h3>
          <p class="mt-1 text-sm text-dm-text-tertiary">
            {{ t('quotation.components.folderPicker.subtitle') }}
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

      <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-dm-border bg-[#fafafa] px-5 py-3">
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

      <div class="min-h-[300px] flex-1 overflow-y-auto p-5">
        <div
          v-if="loading"
          class="flex h-56 items-center justify-center gap-2 text-sm text-dm-text-tertiary"
        >
          <Loader2 class="h-4 w-4 animate-spin" />
          {{ t('quotation.components.folderPicker.loading') }}
        </div>

        <div
          v-else-if="!folders.length"
          class="flex h-56 flex-col items-center justify-center rounded-xl border border-dashed border-dm-border bg-[#fafafa] text-center"
        >
          <Folder class="h-8 w-8 text-slate-300" />
          <p class="mt-3 text-sm font-semibold text-dm-text">
            {{ t('quotation.components.folderPicker.emptyTitle') }}
          </p>
          <p class="mt-1 text-sm text-dm-text-tertiary">
            {{ t('quotation.components.folderPicker.emptyDesc') }}
          </p>
        </div>

        <div v-else class="space-y-2">
          <button
            v-for="folder in folders"
            :key="feishuFolderOpenToken(folder)"
            type="button"
            class="flex w-full items-center gap-3 rounded-xl border border-dm-border bg-white px-3 py-3 text-left hover:border-blue-200 hover:bg-blue-50/40"
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
          {{ t('quotation.components.folderPicker.selectedPrefix') }}
          <span class="font-semibold text-dm-text">{{ currentName || '-' }}</span>
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
            class="dm-btn-primary px-4 py-2 text-sm font-semibold disabled:opacity-40"
            :disabled="loading || !currentToken"
            @click="selectCurrentFolder"
          >
            <Check class="h-3.5 w-3.5" />
            {{ confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
