<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import {
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Pencil,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import {
  checkFeishuFileAccess,
  getFeishuSyncJob,
  syncFeishuArchiveFolder,
} from '../api/feishu'
import {
  archiveQuotationFile,
  exportQuotationFile,
  retryQuotationUpload,
  waitForQuotationExport,
  type QuotationExportStatus,
} from '../api/exports'
import { downloadImportedDocument } from '../api/documents'
import type { QuotationListParams } from '../api/quotations'
import type { Quotation, QuoteStatus } from '../types'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import { clearedFeishuFields } from '../utils/feishuLinkState'
import { buildQuotationExportFileName } from '../utils/quotationFileName'
import { loadProductLineOptions } from '../utils/quotationNumbering'
import FormSelect from './FormSelect.vue'
import StatusBadge from './StatusBadge.vue'
import StatusSelect from './StatusSelect.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

type FeishuUploadFormat = 'excel' | 'pdf'

const props = defineProps<{
  quotations: Quotation[]
  loading?: boolean
  page: number
  pageSize: 10 | 20 | 50
  total: number
  totalPages: number
  currentUser?: {
    name: string
    title: string
    email: string
    role?: string
  } | null
}>()

const emit = defineEmits<{
  viewQuote: [id: string]
  deleteQuote: [id: string]
  updateQuoteStatus: [id: string, updatedFields: Partial<Quotation>, notes?: string]
  feishuUploadDone: [id: string]
  reconcileFeishuLinks: []
  editQuote: [id: string]
  toast: [message: string, type?: 'success' | 'info' | 'error']
  queryChange: [query: QuotationListParams]
}>()

const { t, quoteStatusLabel, statusFilterOptions } = useQuotationI18n()

const productLineFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.list.productLineAll') },
  ...loadProductLineOptions().map((option) => ({
    value: option.value,
    label: option.label,
  })),
])

const sourceFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.list.sourceAll') },
  { value: 'manual', label: t('quotation.pages.list.sourceManual') },
  {
    value: 'document_import',
    label: t('quotation.pages.list.sourceDocumentImport'),
  },
])

const pageSizeOptions = [10, 20, 50].map((value) => ({
  value: String(value),
  label: String(value),
}))

const tableStatusValues: QuoteStatus[] = [
  'Draft',
  'Generated',
  'Uploaded',
  'Sent',
  'Accepted',
  'Rejected',
  'Expired',
  'Cancelled',
]

const searchText = ref('')
const selectedStatus = ref('ALL')
const selectedProductLine = ref('ALL')
const selectedSource = ref('ALL')
const createdFrom = ref('')
const createdTo = ref('')
const syncingFeishu = ref(false)
const deleteConfirmId = ref<string | null>(null)
const uploadingQuoteId = ref<string | null>(null)
const exportProgressByQuote = ref<Record<string, QuotationExportStatus>>({})
const failedUploadByQuote = ref<
  Record<string, { jobId: string; format: FeishuUploadFormat }>
>({})
const actionMenu = ref<{
  quoteId: string
  type: 'upload' | 'download'
  top: number
  left: number
} | null>(null)
const pendingFeishuOpen = ref<{
  quoteId: string
  format: FeishuUploadFormat
  documentId: string
} | null>(null)
let reconcileTimer: number | undefined
let searchTimer: number | undefined
let suppressFilterWatch = false

function scheduleFeishuLinkReconcile() {
  window.clearTimeout(reconcileTimer)
  reconcileTimer = window.setTimeout(() => {
    emit('reconcileFeishuLinks')
  }, 250)
}

async function verifyPendingFeishuOpen() {
  const pending = pendingFeishuOpen.value
  if (!pending) return
  pendingFeishuOpen.value = null
  try {
    const result = await checkFeishuFileAccess(pending.documentId, {
      auditSource: 'automatic',
    })
    if (!result.exists) {
      emit('updateQuoteStatus', pending.quoteId, clearedFeishuFields(pending.format))
      emit(
        'toast',
        t('quotation.pages.list.toastFeishuFileMissing', {
          quoteNo:
            props.quotations.find((quote) => quote.id === pending.quoteId)?.quoteNo ||
            pending.quoteId,
          format: pending.format === 'excel' ? 'Excel' : 'PDF',
        }),
        'error',
      )
      scheduleFeishuLinkReconcile()
    }
  } catch {
    // Ignore background validation errors.
  }
}

function handlePageVisible() {
  if (document.visibilityState !== 'visible') return
  scheduleFeishuLinkReconcile()
  void verifyPendingFeishuOpen()
}

const ACTION_MENU_WIDTH = 240
const ACTION_MENU_MAX_HEIGHT = 320

const actionMenuQuote = computed(() =>
  actionMenu.value
    ? props.quotations.find((quote) => quote.id === actionMenu.value?.quoteId) ?? null
    : null,
)

function closeActionMenu() {
  actionMenu.value = null
}

function toggleActionMenu(
  quote: Quotation,
  type: 'upload' | 'download',
  event: MouseEvent,
) {
  if (
    actionMenu.value?.quoteId === quote.id &&
    actionMenu.value.type === type
  ) {
    closeActionMenu()
    return
  }

  const trigger = event.currentTarget as HTMLElement
  const rect = trigger.getBoundingClientRect()
  let top = rect.bottom + 6
  if (top + ACTION_MENU_MAX_HEIGHT > window.innerHeight - 8) {
    top = Math.max(8, rect.top - ACTION_MENU_MAX_HEIGHT - 6)
  }

  actionMenu.value = {
    quoteId: quote.id,
    type,
    top: Math.max(8, top),
    left: Math.max(8, rect.right - ACTION_MENU_WIDTH),
  }
}

function canDownloadQuote(quote: Quotation): boolean {
  if (quote.status === 'Cancelled') return false
  if (quote.sourceType !== 'document_import') return true
  return Boolean(quote.sourceDocument)
}

function handleDownloadClick(quote: Quotation, event: MouseEvent) {
  if (!canDownloadQuote(quote)) return
  if (quote.sourceDocument?.docType === 'pdf') {
    void handleDownloadOriginal(quote)
    return
  }
  toggleActionMenu(quote, 'download', event)
}

const quoteToDelete = computed(() => props.quotations.find((q) => q.id === deleteConfirmId.value))

function handleOutsideClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('[data-action-menu]')) {
    closeActionMenu()
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleOutsideClick)
  window.addEventListener('scroll', closeActionMenu, true)
  window.addEventListener('resize', closeActionMenu)
  document.addEventListener('visibilitychange', handlePageVisible)
  window.addEventListener('focus', handlePageVisible)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  window.removeEventListener('scroll', closeActionMenu, true)
  window.removeEventListener('resize', closeActionMenu)
  document.removeEventListener('visibilitychange', handlePageVisible)
  window.removeEventListener('focus', handlePageVisible)
  window.clearTimeout(reconcileTimer)
  window.clearTimeout(searchTimer)
})

function currencySymbol(currency: Quotation['currency']): string {
  if (currency === 'CNY') return '¥'
  if (currency === 'USD') return '$'
  return '€'
}

function formatNow(): string {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')} ${String(today.getHours()).padStart(2, '0')}:${String(today.getMinutes()).padStart(2, '0')}:${String(today.getSeconds()).padStart(2, '0')}`
}

function updateExportProgress(
  quoteId: string,
  status: QuotationExportStatus,
) {
  exportProgressByQuote.value[quoteId] = status
}

function exportProgressLabel(quoteId: string): string {
  const status = exportProgressByQuote.value[quoteId]
  return status
    ? t(`quotation.common.exportStatuses.${status}`)
    : ''
}

function openFeishuUploadPicker(quote: Quotation, format: FeishuUploadFormat) {
  if (quote.status === 'Cancelled') return
  closeActionMenu()
  void handleUploadToFeishu(quote, format)
}

function feishuDocumentId(
  quote: Quotation,
  format: FeishuUploadFormat,
): string | undefined {
  return format === 'excel'
    ? quote.feishuExcelDocumentId
    : quote.feishuPdfDocumentId
}

async function openFeishuFile(quote: Quotation, format: FeishuUploadFormat) {
  const documentId = feishuDocumentId(quote, format)
  if (!documentId) return
  closeActionMenu()
  const popup = window.open('about:blank', '_blank')
  if (popup) popup.opener = null
  try {
    const result = await checkFeishuFileAccess(documentId)
    if (!result.exists) {
      popup?.close()
      pendingFeishuOpen.value = null
      emit('updateQuoteStatus', quote.id, clearedFeishuFields(format))
      scheduleFeishuLinkReconcile()
      emit(
        'toast',
        t('quotation.pages.list.toastFeishuFileMissing', {
          quoteNo: quote.quoteNo,
          format: format === 'excel' ? 'Excel' : 'PDF',
        }),
        'error',
      )
      return
    }
    const directUrl = String(result.url || '').trim()
    if (!result.direct_access_allowed || !directUrl) {
      popup?.close()
      throw new Error(t('quotation.pages.list.toastFeishuOpenFailed'))
    }
    pendingFeishuOpen.value = {
      quoteId: quote.id,
      format,
      documentId,
    }
    if (popup) {
      popup.location.replace(directUrl)
    } else {
      window.open(directUrl, '_blank', 'noopener,noreferrer')
    }
  } catch (err: unknown) {
    popup?.close()
    emit(
      'toast',
      err instanceof Error
        ? err.message
        : t('quotation.pages.list.toastFeishuOpenFailed'),
      'error',
    )
  }
}

async function handleDownloadOriginal(quote: Quotation) {
  const sourceDocument = quote.sourceDocument
  if (!sourceDocument || quote.status === 'Cancelled') return
  closeActionMenu()
  try {
    await downloadImportedDocument(
      sourceDocument.id,
      sourceDocument.fileName,
    )
    emit(
      'toast',
      t('quotation.pages.list.toastOriginalDownloadStarted', {
        quoteNo: quote.quoteNo,
      }),
      'success',
    )
  } catch (error) {
    emit(
      'toast',
      error instanceof Error
        ? error.message
        : t('quotation.pages.list.toastOriginalDownloadFailed'),
      'error',
    )
  }
}

async function handleDownloadLocal(
  quote: Quotation,
  format: FeishuUploadFormat,
  quotationVersion?: number,
) {
  if (quote.status === 'Cancelled') return
  closeActionMenu()
  try {
    if (
      format === 'excel' &&
      quote.sourceDocument?.docType === 'excel' &&
      quotationVersion === quote.sourceDocument.versionNo
    ) {
      await handleDownloadOriginal(quote)
      return
    }
    const exportFormat = format === 'excel' ? 'xlsx' : 'pdf'
    await exportQuotationFile(quote.id, exportFormat, {
      onProgress: (job) => updateExportProgress(quote.id, job.status),
      quotationVersion,
    })
    if (format === 'excel') {
      if (quote.sourceType !== 'document_import') {
        emit('updateQuoteStatus', quote.id, {
          status: quote.status === 'Draft' ? 'Generated' : quote.status,
          excelGeneratedAt: formatNow(),
          excelFileName: buildQuotationExportFileName(quote, 'xlsx'),
        })
      }
      emit(
        'toast',
        t('quotation.pages.list.toastExcelDownloadStarted', { quoteNo: quote.quoteNo }),
        'success',
      )
      return
    }
    emit(
      'toast',
      t('quotation.pages.list.toastPdfDownloadStarted', { quoteNo: quote.quoteNo }),
      'success',
    )
  } catch (error) {
    emit(
      'toast',
      error instanceof Error
        ? error.message
        : t('quotation.pages.list.toastExcelDownloadFailed'),
      'error',
    )
  }
}

async function handleUploadToFeishu(
  quote: Quotation,
  format: FeishuUploadFormat = 'excel',
) {
  if (quote.status === 'Cancelled') return
  uploadingQuoteId.value = quote.id
  try {
    const exportFormat = format === 'excel' ? 'xlsx' : 'pdf'
    const job = await archiveQuotationFile(quote.id, exportFormat, {
      onProgress: (progressJob) => {
        updateExportProgress(quote.id, progressJob.status)
      },
    })
    if (job.status === 'upload_failed') {
      failedUploadByQuote.value[quote.id] = {
        jobId: job.job_id,
        format,
      }
      emit(
        'toast',
        job.error_message || t('quotation.pages.list.toastUploadFailed'),
        'error',
      )
      return
    }
    delete failedUploadByQuote.value[quote.id]
    emit('feishuUploadDone', quote.id)
    emit(
      'toast',
      format === 'excel'
        ? t('quotation.pages.list.toastExcelUploaded', {
            quoteNo: quote.quoteNo,
          })
        : t('quotation.pages.list.toastPdfUploaded', {
            quoteNo: quote.quoteNo,
          }),
      'success',
    )
  } catch (err: unknown) {
    emit(
      'toast',
      err instanceof Error ? err.message : t('quotation.pages.list.toastUploadFailed'),
      'error',
    )
  } finally {
    uploadingQuoteId.value = null
  }
}

async function retryFailedUpload(quote: Quotation) {
  const failedUpload = failedUploadByQuote.value[quote.id]
  if (!failedUpload) return
  uploadingQuoteId.value = quote.id
  try {
    const created = await retryQuotationUpload(failedUpload.jobId)
    const job = await waitForQuotationExport(created.job_id, {
      onProgress: (progressJob) => {
        updateExportProgress(quote.id, progressJob.status)
      },
    })
    if (job.status === 'upload_failed') {
      emit(
        'toast',
        job.error_message || t('quotation.pages.list.toastUploadFailed'),
        'error',
      )
      return
    }
    delete failedUploadByQuote.value[quote.id]
    emit('feishuUploadDone', quote.id)
    emit(
      'toast',
      t('quotation.pages.list.toastUploadRetrySucceeded', {
        quoteNo: quote.quoteNo,
      }),
      'success',
    )
  } catch (error) {
    emit(
      'toast',
      error instanceof Error
        ? error.message
        : t('quotation.pages.list.toastUploadFailed'),
      'error',
    )
  } finally {
    uploadingQuoteId.value = null
  }
}

function listQuery(
  page = props.page,
  pageSize = props.pageSize,
): QuotationListParams {
  return {
    page,
    pageSize,
    search: searchText.value.trim() || undefined,
    status:
      selectedStatus.value === 'ALL'
        ? undefined
        : (selectedStatus.value as QuoteStatus),
    productLine:
      selectedProductLine.value === 'ALL'
        ? undefined
        : selectedProductLine.value,
    sourceType:
      selectedSource.value === 'ALL'
        ? undefined
        : (selectedSource.value as 'manual' | 'document_import'),
    createdFrom: createdFrom.value || undefined,
    createdTo: createdTo.value || undefined,
  }
}

function requestPage(page: number) {
  if (page < 1 || page > Math.max(props.totalPages, 1)) return
  emit('queryChange', listQuery(page))
}

function handlePageSizeChange(selectedValue: string) {
  const value = Number(selectedValue)
  if (![10, 20, 50].includes(value)) return
  emit('queryChange', listQuery(1, value as 10 | 20 | 50))
}

async function handleResetFilters() {
  suppressFilterWatch = true
  searchText.value = ''
  selectedStatus.value = 'ALL'
  selectedProductLine.value = 'ALL'
  selectedSource.value = 'ALL'
  createdFrom.value = ''
  createdTo.value = ''
  await nextTick()
  suppressFilterWatch = false
  emit('queryChange', listQuery(1))
}

watch(searchText, () => {
  if (suppressFilterWatch) return
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    emit('queryChange', listQuery(1))
  }, 300)
})

watch(
  [
    selectedStatus,
    selectedProductLine,
    selectedSource,
    createdFrom,
    createdTo,
  ],
  () => {
    if (suppressFilterWatch) return
    emit('queryChange', listQuery(1))
  },
)

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

async function waitForFeishuSyncJob(jobId: string) {
  const deadline = Date.now() + 10 * 60 * 1000
  while (Date.now() < deadline) {
    const job = await getFeishuSyncJob(jobId)
    if (job.status === 'success') return job.result
    if (job.status === 'failed') {
      throw new Error(
        job.error_message || t('quotation.pages.list.feishuSyncFailed'),
      )
    }
    await wait(1000)
  }
  throw new Error(t('quotation.pages.list.feishuSyncTimeout'))
}

async function handleManualFeishuSync() {
  if (syncingFeishu.value) return
  syncingFeishu.value = true
  try {
    let result = await syncFeishuArchiveFolder({ source: 'user' })
    if (result.sync_job_id && result.sync_status !== 'success') {
      const completed = await waitForFeishuSyncJob(result.sync_job_id)
      result = {
        ...result,
        ...(completed as Partial<typeof result>),
      }
    }
    emit('feishuUploadDone', '')
    const errorCount = result.errors?.length || 0
    emit(
      'toast',
      t(
        errorCount
          ? 'quotation.pages.list.feishuSyncPartial'
          : 'quotation.pages.list.feishuSyncComplete',
        {
          created: result.created_count || 0,
          queued: result.queued_parse_count || 0,
          errors: errorCount,
        },
      ),
      errorCount ? 'info' : 'success',
    )
  } catch (error: unknown) {
    emit(
      'toast',
      error instanceof Error
        ? error.message
        : t('quotation.pages.list.feishuSyncFailed'),
      'error',
    )
  } finally {
    syncingFeishu.value = false
  }
}

const hasActiveFilters = computed(
  () =>
    searchText.value.trim() !== '' ||
    selectedStatus.value !== 'ALL' ||
    selectedProductLine.value !== 'ALL' ||
    selectedSource.value !== 'ALL' ||
    createdFrom.value !== '' ||
    createdTo.value !== '',
)

const rangeStart = computed(() =>
  props.total ? (props.page - 1) * props.pageSize + 1 : 0,
)
const rangeEnd = computed(() =>
  Math.min(props.page * props.pageSize, props.total),
)
const pageNumbers = computed(() => {
  const totalPages = props.totalPages
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }
  const start = Math.max(1, Math.min(props.page - 2, totalPages - 4))
  return Array.from({ length: 5 }, (_, index) => start + index)
})

function displayContact(quote: Quotation): string {
  const value = String(quote.contactPerson || '').trim()
  if (
    quote.sourceType === 'document_import'
    && (!value || value === 'Not specified')
  ) {
    return '—'
  }
  return value || '—'
}

function displayTotal(quote: Quotation): string {
  const total = Number(quote.grandTotal || 0)
  if (quote.sourceType === 'document_import' && total === 0) {
    return '—'
  }
  return `${currencySymbol(quote.currency)}${total.toLocaleString()}`
}

</script>

<template>
  <div id="quote-list-root" class="space-y-6">
    <div v-if="loading" class="text-sm text-dm-text-tertiary">
      {{ t('quotation.pages.list.syncing') }}
    </div>
    <p v-if="currentUser" class="text-sm text-dm-text-tertiary">
      {{ t('quotation.pages.list.userHint', { name: currentUser.name }) }}
    </p>

    <div
      id="filter-panel"
      data-filter-toolbar
      aria-label="Quote filters"
      class="rounded-xl border border-dm-border-light bg-white p-2.5 shadow-xs"
    >
      <div class="grid grid-cols-1 items-end gap-2 md:grid-cols-2 xl:grid-cols-[minmax(220px,1.35fr)_minmax(110px,0.55fr)_minmax(120px,0.6fr)_minmax(120px,0.6fr)_minmax(220px,1fr)_auto]">
          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.keywordLabel') }}
            </label>
            <div class="relative">
              <input
                v-model="searchText"
                type="text"
                :placeholder="t('quotation.pages.list.keywordPlaceholder')"
                class="h-10 w-full min-w-0 rounded-lg border border-dm-border-light bg-slate-50/70 py-2 pl-9 pr-9 text-sm text-dm-text transition placeholder:text-slate-400 hover:bg-white focus:border-blue-300 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-100"
              />
              <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
              <button
                v-if="searchText"
                type="button"
                class="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-200 hover:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-blue-200"
                :aria-label="t('quotation.pages.list.clearSearch')"
                :title="t('quotation.pages.list.clearSearch')"
                @click="searchText = ''"
              >
                <X class="h-4 w-4" />
              </button>
            </div>
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.statusLabel') }}
            </label>
            <FormSelect
              v-model="selectedStatus"
              class-name="w-full"
              :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
              :options="statusFilterOptions"
            />
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.productLineLabel') }}
            </label>
            <FormSelect
              v-model="selectedProductLine"
              class-name="w-full"
              :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
              :options="productLineFilterOptions"
            />
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.sourceLabel') }}
            </label>
            <FormSelect
              v-model="selectedSource"
              class-name="w-full"
              :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
              :options="sourceFilterOptions"
            />
          </div>

          <div data-filter-date-range class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.createdFromLabel') }} / {{ t('quotation.pages.list.createdToLabel') }}
            </label>
            <div class="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
              <BaseDatePicker
                v-model="createdFrom"
                :placeholder="t('quotation.pages.list.createdFromLabel')"
                input-class="h-10 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-2 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
              />
              <BaseDatePicker
                v-model="createdTo"
                :placeholder="t('quotation.pages.list.createdToLabel')"
                input-class="h-10 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-2 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
              />
            </div>
          </div>

          <div class="flex items-center gap-1 md:col-span-2 xl:col-span-1">
            <div class="flex h-10 min-w-20 items-center justify-center whitespace-nowrap rounded-lg bg-slate-50 px-2.5 text-xs font-semibold text-dm-text-tertiary">
              {{ t('quotation.pages.list.filterResultsCount', { count: total }) }}
            </div>
            <button
              type="button"
              data-feishu-sync-button
              class="inline-flex h-10 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-blue-300 bg-blue-50 px-2.5 text-xs font-semibold text-blue-700 transition hover:border-blue-400 hover:bg-blue-100 focus:outline-hidden focus:ring-2 focus:ring-blue-200 disabled:cursor-wait disabled:opacity-70"
              :disabled="syncingFeishu"
              @click="handleManualFeishuSync"
            >
              <RefreshCw
                class="h-3.5 w-3.5"
                :class="{ 'animate-spin': syncingFeishu }"
              />
              {{
                syncingFeishu
                  ? t('quotation.pages.list.feishuSyncing')
                  : t('quotation.pages.list.feishuSync')
              }}
            </button>
            <button
              type="button"
              :class="`inline-flex h-10 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-xs font-semibold transition cursor-pointer ${
                hasActiveFilters
                  ? 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  : 'text-dm-text-tertiary hover:bg-slate-50 hover:text-dm-text-secondary'
              }`"
              @click="handleResetFilters"
            >
              <RotateCcw class="h-3.5 w-3.5" />
              {{ t('quotation.actions.resetFilters') }}
            </button>
          </div>
      </div>
    </div>

    <div id="table-panel" class="bg-white rounded-xl border border-dm-border-light shadow-xs overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full min-w-[1180px] text-left border-collapse">
          <thead>
            <tr
              class="bg-[#fafafa] border-b border-dm-border-light text-dm-text-tertiary text-xs font-bold tracking-wider"
            >
              <th class="w-[220px] py-3 px-4">
                {{ t('quotation.pages.list.tableQuoteNo') }}
              </th>
              <th class="py-3 px-4">{{ t('quotation.pages.list.tableProjectName') }}</th>
              <th class="py-3 px-4">{{ t('quotation.pages.list.tableCustomer') }}</th>
              <th class="py-3 px-4">{{ t('quotation.pages.list.tableContact') }}</th>
              <th class="whitespace-nowrap py-3 px-4">{{ t('quotation.pages.list.tableCreatedAt') }}</th>
              <th class="py-3 px-4 text-right">{{ t('quotation.pages.list.tableTotal') }}</th>
              <th class="w-[136px] whitespace-nowrap py-3 px-4 text-center">
                {{ t('quotation.pages.list.tableStatusSource') }}
              </th>
              <th class="w-[200px] py-3 px-4 text-center">
                {{ t('quotation.pages.list.tableActions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-sm">
            <tr v-if="loading">
              <td colspan="8" class="py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.pages.list.syncing') }}
              </td>
            </tr>
            <tr v-else-if="quotations.length === 0">
              <td colspan="8" class="py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.pages.list.emptyResults') }}
              </td>
            </tr>
            <template v-else>
            <tr
              v-for="quote in quotations"
              :key="quote.id"
              class="hover:bg-[#fafafa] transition duration-150"
            >
              <td class="w-[220px] max-w-[220px] py-3.5 px-4">
                <p
                  class="block truncate whitespace-nowrap font-mono font-medium text-dm-primary"
                  :title="quote.quoteNo"
                >
                  {{ quote.quoteNo }}
                </p>
                <p
                  v-if="exportProgressByQuote[quote.id]"
                  class="mt-1 text-xs font-medium text-indigo-600"
                >
                  {{ exportProgressLabel(quote.id) }}
                </p>
              </td>
              <td class="py-3.5 px-4">
                <div class="max-w-[180px] sm:max-w-xs truncate">
                  <p class="font-semibold text-dm-text" :title="quote.projectName">
                    {{ quote.projectName }}
                  </p>
                  <p class="text-xs text-dm-text-tertiary font-mono mt-0.5">
                    {{
                      t('quotation.common.lineItemCount', {
                        count: quote.itemCount ?? quote.items.length,
                      })
                    }}
                  </p>
                </div>
              </td>
              <td class="py-3.5 px-4">
                <div class="max-w-[160px] truncate">
                  <p class="text-dm-text font-medium" :title="quote.clientCompany">
                    {{ quote.clientCompany }}
                  </p>
                </div>
              </td>
              <td
                class="py-3.5 px-4 text-dm-text-secondary font-medium"
                :title="displayContact(quote) === '—' ? undefined : displayContact(quote)"
              >
                {{ displayContact(quote) }}
              </td>
              <td class="whitespace-nowrap py-3.5 px-4 text-dm-text-tertiary font-mono">
                {{ quote.createdAt.substring(0, 10) }}
              </td>
              <td class="py-3.5 px-4 text-right font-bold text-dm-text font-mono">
                {{ displayTotal(quote) }}
              </td>
              <td class="w-[136px] py-3.5 px-4 text-center">
                <span
                  v-if="quote.sourceType === 'document_import'"
                  class="inline-flex whitespace-nowrap rounded-full bg-fuchsia-100 px-2.5 py-1 text-xs font-semibold text-fuchsia-800 ring-1 ring-inset ring-fuchsia-300"
                >
                  {{ t('quotation.pages.list.sourceDocumentImport') }}
                </span>
                <StatusBadge
                  v-else-if="quote.status === 'Cancelled'"
                  :status="quote.status"
                />
                <StatusSelect
                  v-else
                  :model-value="quote.status"
                  :options="tableStatusValues"
                  @change="
                    emit('updateQuoteStatus', quote.id, {
                      status: $event,
                    })
                  "
                />
              </td>
              <td class="w-[200px] py-3.5 px-4">
                <div class="flex items-center justify-center gap-1.5">
                  <button
                    :title="t('quotation.pages.list.viewDetails')"
                    class="p-1 text-dm-text-tertiary hover:text-dm-text hover:bg-slate-100 rounded-sm transition duration-100 cursor-pointer"
                    @click="emit('viewQuote', quote.id)"
                  >
                    <FileText class="w-4 h-4" />
                  </button>

                  <button
                    v-if="quote.sourceType !== 'document_import'"
                    :title="
                      quote.status === 'Cancelled'
                        ? t('quotation.pages.list.editDisabled')
                        : t('quotation.pages.list.editQuote')
                    "
                    :disabled="quote.status === 'Cancelled'"
                    :class="`p-1 rounded-sm transition duration-100 ${
                      quote.status === 'Cancelled'
                        ? 'text-slate-300 cursor-not-allowed'
                        : 'text-dm-text-tertiary hover:text-dm-primary hover:bg-dm-primary-bg cursor-pointer'
                    }`"
                    @click="quote.status !== 'Cancelled' && emit('editQuote', quote.id)"
                  >
                    <Pencil class="w-4 h-4" />
                  </button>

                  <div
                    v-if="quote.sourceType !== 'document_import'"
                    class="relative"
                    data-action-menu
                  >
                    <button
                      :title="
                        quote.status === 'Cancelled'
                          ? t('quotation.pages.list.uploadDisabled')
                          : t('quotation.pages.list.uploadFeishu')
                      "
                      :disabled="quote.status === 'Cancelled' || uploadingQuoteId === quote.id"
                      :class="`p-1 rounded-sm transition duration-100 ${
                        quote.status === 'Cancelled' || uploadingQuoteId === quote.id
                          ? 'text-slate-300 cursor-not-allowed'
                          : 'text-dm-text-tertiary hover:text-indigo-600 hover:bg-indigo-50 cursor-pointer'
                      }`"
                      @click="
                        quote.status !== 'Cancelled' &&
                          toggleActionMenu(quote, 'upload', $event)
                      "
                    >
                      <UploadCloud class="w-4 h-4" />
                    </button>
                  </div>

                  <div class="relative" data-action-menu>
                    <button
                      :title="
                        quote.status === 'Cancelled'
                          ? t('quotation.pages.list.downloadDisabled')
                          : !canDownloadQuote(quote)
                            ? t('quotation.pages.list.downloadUnavailable')
                          : t('quotation.pages.list.downloadLocal')
                      "
                      :disabled="!canDownloadQuote(quote)"
                      :class="`p-1 rounded-sm transition duration-100 ${
                        !canDownloadQuote(quote)
                          ? 'text-slate-300 cursor-not-allowed'
                          : 'text-dm-text-tertiary hover:text-emerald-600 hover:bg-emerald-50 cursor-pointer'
                      }`"
                      @click="handleDownloadClick(quote, $event)"
                    >
                      <Download class="w-4 h-4" />
                    </button>
                  </div>

                  <button
                    v-if="failedUploadByQuote[quote.id]"
                    type="button"
                    :title="t('quotation.pages.list.retryUpload')"
                    :disabled="uploadingQuoteId === quote.id"
                    class="cursor-pointer rounded-sm p-1 text-amber-600 transition duration-100 hover:bg-amber-50 hover:text-amber-700 disabled:cursor-not-allowed disabled:text-slate-300"
                    @click="void retryFailedUpload(quote)"
                  >
                    <RotateCcw class="h-4 w-4" />
                  </button>

                  <button
                    v-if="feishuDocumentId(quote, 'excel')"
                    :title="t('quotation.actions.openFeishuExcel')"
                    class="p-1 rounded-sm transition duration-100 text-dm-text-tertiary hover:text-emerald-600 hover:bg-emerald-50 cursor-pointer"
                    @click="void openFeishuFile(quote, 'excel')"
                  >
                    <ExternalLink class="w-4 h-4" />
                  </button>

                  <button
                    v-if="feishuDocumentId(quote, 'pdf')"
                    :title="t('quotation.actions.openFeishuPdf')"
                    class="p-1 rounded-sm transition duration-100 text-dm-text-tertiary hover:text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                    @click="void openFeishuFile(quote, 'pdf')"
                  >
                    <ExternalLink class="w-4 h-4" />
                  </button>

                  <button
                    v-if="quote.sourceType !== 'document_import'"
                    :title="t('quotation.pages.list.deleteQuote')"
                    class="p-1 text-dm-text-tertiary hover:text-red-500 hover:bg-red-50 rounded-sm transition duration-100 cursor-pointer"
                    @click="deleteConfirmId = quote.id"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>
      <div
        class="flex flex-col gap-3 border-t border-dm-border-light px-4 py-3 text-sm text-dm-text-tertiary sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>共 {{ total }} 条</span>
          <span>显示 {{ rangeStart }}–{{ rangeEnd }} 条</span>
          <span>共 {{ totalPages }} 页</span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex items-center gap-2">
            <span>每页</span>
            <FormSelect
              :value="String(pageSize)"
              class-name="w-20"
              trigger-class-name="h-8 rounded-md border-dm-border bg-white px-2 text-sm focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              panel-class-name="bottom-full top-auto mb-1 mt-0"
              :options="pageSizeOptions"
              test-id="quotation-page-size"
              @change="handlePageSizeChange"
            />
            <span>条</span>
          </label>
          <button
            type="button"
            class="h-8 rounded-md border border-dm-border px-2.5 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="page <= 1 || loading"
            @click="requestPage(page - 1)"
          >
            上一页
          </button>
          <button
            v-for="pageNumber in pageNumbers"
            :key="pageNumber"
            type="button"
            class="h-8 min-w-8 rounded-md border px-2"
            :class="
              pageNumber === page
                ? 'border-dm-primary bg-dm-primary text-white'
                : 'border-dm-border bg-white text-dm-text-secondary'
            "
            :disabled="loading"
            @click="requestPage(pageNumber)"
          >
            {{ pageNumber }}
          </button>
          <button
            type="button"
            class="h-8 rounded-md border border-dm-border px-2.5 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="page >= totalPages || loading || totalPages === 0"
            @click="requestPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="deleteConfirmId && quoteToDelete"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 dm-modal-overlay backdrop-blur-[2px]"
    >
      <div class="bg-white rounded-xl border border-dm-border-light p-6 shadow-2xl max-w-sm w-full space-y-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 bg-red-50 rounded-full flex items-center justify-center shrink-0">
            <Trash2 class="w-5 h-5 text-red-600" />
          </div>
          <div class="space-y-1">
            <h3 class="text-sm font-bold text-dm-text">
              {{ t('quotation.pages.list.deleteModalTitle') }}
            </h3>
            <p class="text-sm text-dm-text-tertiary leading-relaxed">
              {{ t('quotation.pages.list.deleteModalDesc') }}
            </p>
          </div>
        </div>

        <div
          class="bg-[#fafafa] p-3.5 rounded-lg border border-dm-border-light text-sm text-dm-text-secondary space-y-2 font-medium"
        >
          <div class="flex justify-between">
            <span class="text-dm-text-tertiary">{{ t('quotation.pages.list.deleteModalQuoteNo') }}</span>
            <span class="font-mono text-dm-text font-bold">{{ quoteToDelete.quoteNo }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-dm-text-tertiary">{{ t('quotation.pages.list.deleteModalCompany') }}</span>
            <span class="text-dm-text text-right truncate max-w-[180px]">{{
              quoteToDelete.clientCompany
            }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-dm-text-tertiary">{{ t('quotation.pages.list.deleteModalTotal') }}</span>
            <span class="font-bold text-dm-text font-mono">
              {{ currencySymbol(quoteToDelete.currency)
              }}{{ quoteToDelete.grandTotal.toLocaleString() }}
            </span>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-2">
          <button
            type="button"
            class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-dm-text text-sm font-semibold rounded-lg border border-dm-border transition duration-150 cursor-pointer"
            @click="deleteConfirmId = null"
          >
            {{ t('quotation.common.cancel') }}
          </button>
          <button
            type="button"
            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg shadow-sm transition duration-150 cursor-pointer"
            @click="
              emit('deleteQuote', quoteToDelete.id);
              deleteConfirmId = null
            "
          >
            {{ t('quotation.actions.confirmDelete') }}
          </button>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div
        v-if="actionMenu && actionMenuQuote"
        data-action-menu
        class="fixed z-[120] w-60 max-h-80 overflow-y-auto rounded-lg border border-dm-border bg-white py-1 shadow-lg"
        :style="{
          top: `${actionMenu.top}px`,
          left: `${actionMenu.left}px`,
        }"
      >
        <template v-if="actionMenu.type === 'upload'">
          <button
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-indigo-50 hover:text-indigo-700"
            @click="openFeishuUploadPicker(actionMenuQuote, 'excel')"
          >
            <FileSpreadsheet class="h-3.5 w-3.5" />
            {{ t('quotation.actions.uploadExcel') }}
          </button>
          <button
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-indigo-50 hover:text-indigo-700"
            @click="openFeishuUploadPicker(actionMenuQuote, 'pdf')"
          >
            <ExternalLink class="h-3.5 w-3.5" />
            {{ t('quotation.actions.uploadPdf') }}
          </button>
        </template>
        <template v-else>
          <template v-if="actionMenuQuote.sourceType === 'document_import'">
            <template v-if="actionMenuQuote.availableVersions?.length">
              <p class="px-3 py-1 text-xs font-semibold text-dm-text-tertiary">
                {{ t('quotation.pages.list.downloadGeneratedRevision') }}
              </p>
              <div
                v-for="version in actionMenuQuote.availableVersions"
                :key="version.versionNo"
                class="px-3 py-2"
              >
                <p class="mb-1 text-xs text-dm-text-secondary">
                  {{
                    t('quotation.pages.list.downloadRevision', {
                      version: version.versionNo,
                    })
                  }}
                </p>
                <div class="grid grid-cols-2 gap-1">
                  <button
                    type="button"
                    class="flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
                    @click="
                      handleDownloadLocal(
                        actionMenuQuote,
                        'excel',
                        version.versionNo,
                      )
                    "
                  >
                    <FileSpreadsheet class="h-3.5 w-3.5" />
                    {{ t('quotation.actions.downloadExcel') }}
                  </button>
                  <button
                    type="button"
                    class="flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
                    @click="
                      handleDownloadLocal(
                        actionMenuQuote,
                        'pdf',
                        version.versionNo,
                      )
                    "
                  >
                    <FileText class="h-3.5 w-3.5" />
                    {{ t('quotation.actions.downloadPdf') }}
                  </button>
                </div>
              </div>
            </template>
          </template>
          <template v-else>
            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
              @click="handleDownloadLocal(actionMenuQuote, 'excel')"
            >
              <FileSpreadsheet class="h-3.5 w-3.5" />
              {{ t('quotation.actions.downloadExcel') }}
            </button>
            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
              @click="handleDownloadLocal(actionMenuQuote, 'pdf')"
            >
              <ExternalLink class="h-3.5 w-3.5" />
              {{ t('quotation.actions.downloadPdf') }}
            </button>
          </template>
        </template>
      </div>
    </Teleport>

  </div>
</template>
