<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Cloud,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  FolderInput,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-vue-next'
import {
  deleteImportedDocument,
  downloadImportedDocument,
  listImportedFeishuDocuments,
  type ImportedDocument,
} from '../api/documents'
import { checkFeishuFileAccess, batchCheckFeishuFileAccess, getFeishuStatus } from '../api/feishu'
import { normalizeFeishuOpenUrl } from '../utils/feishuLinks'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import FeishuDriveModal from './FeishuDriveModal.vue'
import FormSelect from './FormSelect.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const emit = defineEmits<{
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const { t } = useQuotationI18n()

const docs = ref<ImportedDocument[]>([])
const loading = ref(false)
const search = ref('')
const typeFilter = ref('ALL')
const feishuOpen = ref(false)
const downloadingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const deleteConfirmDoc = ref<ImportedDocument | null>(null)
const pendingFeishuDocId = ref<string | null>(null)
let reconcileTimer: number | undefined

function scheduleFeishuDocReconcile() {
  window.clearTimeout(reconcileTimer)
  reconcileTimer = window.setTimeout(() => {
    void refresh()
  }, 250)
}

function handlePageVisible() {
  if (document.visibilityState !== 'visible') return
  scheduleFeishuDocReconcile()
}

onMounted(() => {
  document.addEventListener('visibilitychange', handlePageVisible)
  window.addEventListener('focus', handlePageVisible)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handlePageVisible)
  window.removeEventListener('focus', handlePageVisible)
  window.clearTimeout(reconcileTimer)
})

const typeFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.imports.typeAll') },
  { value: 'excel', label: t('quotation.pages.imports.typeExcel') },
  { value: 'pdf', label: t('quotation.pages.imports.typePdf') },
])

function formatBytes(size: number): string {
  if (!size || size < 0) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

function docTypeLabel(docType: string): string {
  const lower = (docType || '').toLowerCase()
  if (lower === 'pdf') return t('quotation.pages.imports.typePdf')
  if (lower === 'excel') return t('quotation.pages.imports.typeExcel')
  return docType || t('quotation.pages.imports.docTypeFile')
}

function getFeishuOpenUrl(doc: ImportedDocument): string {
  return normalizeFeishuOpenUrl(doc.feishu_url) || normalizeFeishuOpenUrl(doc.feishu_file_token)
}

function notify(message: string, type: 'success' | 'info' | 'error' = 'info') {
  emit('toast', message, type)
}

async function refresh() {
  loading.value = true
  try {
    const items = await listImportedFeishuDocuments()
    docs.value = items
    const batchItems = items
      .filter((doc) => doc.feishu_file_token)
      .map((doc) => ({
        file_token: doc.feishu_file_token as string,
        document_id: doc.id,
        doc_type: (doc.doc_type || '').toLowerCase() as 'excel' | 'pdf',
      }))
    if (batchItems.length) {
      try {
        const status = await getFeishuStatus()
        if (status.connected) {
          const response = await batchCheckFeishuFileAccess(batchItems)
          const missingIds = new Set(
            response.results
              .filter((item) => !item.exists)
              .map((item) => item.document_id)
              .filter((id): id is string => Boolean(id)),
          )
          if (missingIds.size) {
            docs.value = docs.value.map((doc) =>
              missingIds.has(doc.id)
                ? { ...doc, feishu_file_token: null, feishu_url: null }
                : doc,
            )
          }
        }
      } catch {
        // Keep listed documents when Feishu validation is unavailable.
      }
    }
  } catch (err: unknown) {
    notify(
      err instanceof Error ? err.message : t('quotation.pages.imports.loadFailed'),
      'error',
    )
    docs.value = []
  } finally {
    loading.value = false
  }
}

void refresh()

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return docs.value.filter((doc) => {
    if (typeFilter.value !== 'ALL' && (doc.doc_type || '').toLowerCase() !== typeFilter.value) {
      return false
    }
    if (!q) return true
    return (
      doc.file_name.toLowerCase().includes(q) ||
      (doc.created_by_email || '').toLowerCase().includes(q) ||
      (doc.feishu_file_token || '').toLowerCase().includes(q)
    )
  })
})

async function handleOpenFeishu(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  const url = getFeishuOpenUrl(doc)
  const token = doc.feishu_file_token
  if (!url || !token) {
    notify(t('quotation.pages.imports.missingFeishuLink'), 'error')
    return
  }
  try {
    const result = await checkFeishuFileAccess(token, { documentId: doc.id })
    if (!result.exists) {
      pendingFeishuDocId.value = null
      docs.value = docs.value.map((item) =>
        item.id === doc.id
          ? { ...item, feishu_file_token: null, feishu_url: null }
          : item,
      )
      notify(t('quotation.pages.imports.feishuFileMissing'), 'error')
      scheduleFeishuDocReconcile()
      return
    }
    pendingFeishuDocId.value = doc.id
    window.open(result.url || url, '_blank', 'noopener,noreferrer')
  } catch (err: unknown) {
    notify(
      err instanceof Error
        ? err.message
        : t('quotation.pages.imports.openFeishuFailed'),
      'error',
    )
  }
}

async function handleDownload(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  downloadingId.value = doc.id
  try {
    await downloadImportedDocument(doc.id, doc.file_name)
    notify(t('quotation.pages.imports.downloadStarted', { fileName: doc.file_name }), 'success')
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t('quotation.pages.imports.downloadFailed'), 'error')
  } finally {
    downloadingId.value = null
  }
}

async function handleDelete(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  deleteConfirmDoc.value = doc
}

async function confirmDelete() {
  if (!deleteConfirmDoc.value) return
  const doc = deleteConfirmDoc.value
  deleteConfirmDoc.value = null
  deletingId.value = doc.id
  try {
    await deleteImportedDocument(doc.id)
    docs.value = docs.value.filter((item) => item.id !== doc.id)
    notify(t('quotation.pages.imports.deleteSuccess', { fileName: doc.file_name }), 'success')
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t('quotation.pages.imports.deleteFailed'), 'error')
  } finally {
    deletingId.value = null
  }
}

function closeFeishu() {
  feishuOpen.value = false
  void refresh()
}
</script>

<template>
  <div class="flex h-[calc(100vh-7.5rem)] flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-base font-bold text-dm-text">{{ t('quotation.pages.imports.title') }}</h2>
        <p class="mt-1 text-[11px] text-dm-text-tertiary">
          {{ t('quotation.pages.imports.subtitle') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-dm-border bg-white px-3 py-1.5 text-[11px] font-semibold text-dm-text-secondary hover:bg-[#fafafa] disabled:opacity-50"
          :disabled="loading"
          @click="refresh"
        >
          <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': loading }" />
          {{ t('quotation.common.refresh') }}
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700"
          @click="feishuOpen = true"
        >
          <Cloud class="h-3.5 w-3.5" />
          {{ t('quotation.actions.importFromFeishu') }}
        </button>
      </div>
    </div>

    <div class="flex min-h-0 flex-1 flex-col dm-card p-4 shadow-xs">
        <div class="mb-4 flex shrink-0 flex-wrap items-center gap-3">
          <div class="relative min-w-[180px] flex-1">
            <Search
              class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-dm-text-tertiary"
            />
            <input
              v-model="search"
              :placeholder="t('quotation.pages.imports.searchPlaceholder')"
              class="w-full rounded-lg border border-dm-border bg-[#fafafa] py-2 pl-8 pr-3 text-xs text-dm-text outline-none focus:border-blue-300 focus:bg-white"
            />
          </div>
          <FormSelect
            v-model="typeFilter"
            class-name="w-[140px] shrink-0"
            :trigger-class-name="FORM_SELECT_COMPACT_TRIGGER_CLASS"
            :options="typeFilterOptions"
          />
          <span class="text-[11px] text-dm-text-tertiary">
            {{ t('quotation.pages.imports.totalCount', { count: filtered.length }) }}
          </span>
        </div>

        <div
          v-if="loading && docs.length === 0"
          class="flex flex-1 items-center justify-center gap-2 text-sm text-dm-text-tertiary"
        >
          <Loader2 class="h-4 w-4 animate-spin" />
          {{ t('quotation.pages.imports.loading') }}
        </div>
        <div
          v-else-if="filtered.length === 0"
          class="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-dm-border bg-[#fafafa] px-4 text-center"
        >
          <FolderInput class="mx-auto h-8 w-8 text-slate-300" />
          <p class="mt-3 text-sm font-semibold text-dm-text">
            {{ t('quotation.pages.imports.emptyTitle') }}
          </p>
          <p class="mt-1 text-[11px] text-dm-text-tertiary">
            {{ t('quotation.pages.imports.emptyDesc') }}
          </p>
        </div>
        <div v-else class="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          <div
            v-for="doc in filtered"
            :key="doc.id"
            class="w-full dm-card px-3 py-2.5 text-left transition-colors hover:border-blue-200 hover:bg-[#fafafa]"
          >
            <div class="flex items-start gap-2.5">
              <FileText
                v-if="(doc.doc_type || '').toLowerCase() === 'pdf'"
                class="mt-0.5 h-4 w-4 shrink-0 text-rose-500"
              />
              <FileSpreadsheet v-else class="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <div class="min-w-0 flex-1">
                <div class="truncate text-xs font-semibold text-dm-text" :title="doc.file_name">
                  {{ doc.file_name }}
                </div>
                <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-dm-text-tertiary">
                  <span>{{ docTypeLabel(doc.doc_type) }}</span>
                  <span>{{ formatBytes(doc.size_bytes) }}</span>
                  <span>{{ formatTime(doc.created_at) }}</span>
                  <span
                    class="rounded-full border border-amber-100 bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-700"
                  >
                    {{ t('quotation.pages.imports.statusUnparsed') }}
                  </span>
                </div>
                <div class="mt-0.5 truncate text-[10px] text-dm-text-tertiary">
                  {{ doc.created_by_email || '—' }}
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <button
                  v-if="getFeishuOpenUrl(doc)"
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg border border-[#91caff] bg-dm-primary-bg px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-100"
                  :title="t('quotation.pages.imports.openFeishu')"
                  @click="handleOpenFeishu(doc, $event)"
                >
                  <ExternalLink class="h-3 w-3" />
                  {{ t('quotation.pages.imports.openFeishu') }}
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg border border-dm-border bg-white px-2 py-1 text-[10px] font-semibold text-dm-text-secondary hover:bg-[#fafafa]"
                  :title="t('quotation.common.download')"
                  @click="handleDownload(doc, $event)"
                >
                  <Loader2 v-if="downloadingId === doc.id" class="h-3 w-3 animate-spin" />
                  <Download v-else class="h-3 w-3" />
                  {{ t('quotation.common.download') }}
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg border border-red-100 bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-600 hover:bg-red-100"
                  :title="t('quotation.common.delete')"
                  @click="handleDelete(doc, $event)"
                >
                  <Loader2 v-if="deletingId === doc.id" class="h-3 w-3 animate-spin" />
                  <Trash2 v-else class="h-3 w-3" />
                  {{ t('quotation.common.delete') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

    <FeishuDriveModal
      v-model:open="feishuOpen"
      @close="closeFeishu"
      @toast="(msg, type) => emit('toast', msg, type)"
    />

    <div
      v-if="deleteConfirmDoc"
      class="fixed inset-0 z-50 flex items-center justify-center dm-modal-overlay p-4"
    >
      <div class="w-full max-w-md dm-card p-5 shadow-xl">
        <h3 class="text-sm font-bold text-dm-text">
          {{ t('quotation.pages.imports.deleteModalTitle') }}
        </h3>
        <p class="mt-2 text-xs text-dm-text-tertiary">
          {{
            t('quotation.pages.imports.deleteModalDesc', {
              fileName: deleteConfirmDoc.file_name,
            })
          }}
        </p>
        <div class="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            class="rounded-lg border border-dm-border px-3 py-1.5 text-xs font-semibold text-dm-text-secondary hover:bg-[#fafafa]"
            @click="deleteConfirmDoc = null"
          >
            {{ t('quotation.common.cancel') }}
          </button>
          <button
            type="button"
            :disabled="deletingId === deleteConfirmDoc.id"
            class="inline-flex items-center gap-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-40"
            @click="confirmDelete"
          >
            <Loader2 v-if="deletingId === deleteConfirmDoc.id" class="h-3.5 w-3.5 animate-spin" />
            {{ t('quotation.actions.confirmDelete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
