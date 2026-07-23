<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Pencil,
  RotateCcw,
  Search,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import {
  FeishuUploadConflictError,
  checkFeishuFileAccess,
  uploadBlobToFeishu,
} from '../api/feishu'
import type { FeishuUploadConflict, FeishuUploadConflictAction } from '../api/feishu'
import type { Quotation, QuoteStatus } from '../types'
import { recordQuotationDownload } from '../api/quotations'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import { buildQuotationExcelBlob, downloadQuotationExcel } from '../utils/excelGenerator'
import { clearedFeishuFields } from '../utils/feishuLinkState'
import { buildQuotationPdfBlob, downloadQuotationPdf } from '../utils/pdfExporter'
import { buildQuotationExportFileName } from '../utils/quotationFileName'
import { loadProductLineOptions } from '../utils/quotationNumbering'
import FeishuFolderPickerModal from './FeishuFolderPickerModal.vue'
import FormSelect from './FormSelect.vue'
import StatusBadge from './StatusBadge.vue'
import StatusSelect from './StatusSelect.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

type FeishuUploadFormat = 'excel' | 'pdf'

const props = defineProps<{
  quotations: Quotation[]
  loading?: boolean
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
const deleteConfirmId = ref<string | null>(null)
const uploadingQuoteId = ref<string | null>(null)
const uploadConflict = ref<{
  quote: Quotation
  format: FeishuUploadFormat
  conflict: FeishuUploadConflict
  folderToken?: string
} | null>(null)
const uploadFolderPicker = ref<{
  quote: Quotation
  format: FeishuUploadFormat
} | null>(null)
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

const ACTION_MENU_WIDTH = 176
const ACTION_MENU_HEIGHT = 88

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
  if (top + ACTION_MENU_HEIGHT > window.innerHeight - 8) {
    top = rect.top - ACTION_MENU_HEIGHT - 6
  }

  actionMenu.value = {
    quoteId: quote.id,
    type,
    top: Math.max(8, top),
    left: Math.max(8, rect.right - ACTION_MENU_WIDTH),
  }
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

function openFeishuUploadPicker(quote: Quotation, format: FeishuUploadFormat) {
  if (quote.status === 'Cancelled') return
  closeActionMenu()
  uploadFolderPicker.value = { quote, format }
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

async function handleDownloadLocal(quote: Quotation, format: FeishuUploadFormat) {
  if (quote.status === 'Cancelled') return
  closeActionMenu()
  if (
    quote.sourceType === 'document_import' &&
    quote.sourceDocumentType !== format
  ) {
    return
  }
  if (format === 'excel') {
    const success = await downloadQuotationExcel(quote, props.currentUser || undefined)
    if (success) {
      await recordQuotationDownload(quote.id, 'excel').catch(() => undefined)
      emit('updateQuoteStatus', quote.id, {
        status: quote.status === 'Draft' ? 'Generated' : quote.status,
        excelGeneratedAt: formatNow(),
        excelFileName: buildQuotationExportFileName(quote, 'xlsx'),
      })
      emit(
        'toast',
        t('quotation.pages.list.toastExcelDownloadStarted', { quoteNo: quote.quoteNo }),
        'success',
      )
    } else {
      emit('toast', t('quotation.pages.list.toastExcelDownloadFailed'), 'error')
    }
    return
  }

  const success = await downloadQuotationPdf(quote, props.currentUser || undefined)
  if (success) {
    await recordQuotationDownload(quote.id, 'pdf').catch(() => undefined)
    emit(
      'toast',
      t('quotation.pages.list.toastPdfDownloadStarted', { quoteNo: quote.quoteNo }),
      'success',
    )
  } else {
    emit('toast', t('quotation.pages.list.toastPdfDownloadFailed'), 'error')
  }
}

async function handleUploadToFeishu(
  quote: Quotation,
  format: FeishuUploadFormat = 'excel',
  conflictAction?: FeishuUploadConflictAction,
  folderToken?: string,
) {
  if (quote.status === 'Cancelled') return
  uploadingQuoteId.value = quote.id
  try {
    const uploadOpts = {
      quotationId: quote.id,
      conflictAction,
      folderToken,
    }

    if (format === 'excel') {
      const excelBlob = await buildQuotationExcelBlob(
        quote,
        props.currentUser || undefined,
      )
      if (!excelBlob) {
        emit('toast', t('quotation.pages.list.toastExcelDownloadFailed'), 'error')
        return
      }
      const excelName = buildQuotationExportFileName(quote, 'xlsx')
      const excelUploadResult = await uploadBlobToFeishu(excelBlob, excelName, uploadOpts)
      emit('feishuUploadDone', quote.id)
      emit(
        'toast',
        excelUploadResult.reused_existing
          ? t('quotation.pages.list.toastExcelReused', { quoteNo: quote.quoteNo })
          : excelUploadResult.renamed_from
            ? t('quotation.pages.list.toastExcelRenamed', {
                quoteNo: quote.quoteNo,
                fileName: excelUploadResult.file_name,
              })
            : t('quotation.pages.list.toastExcelUploaded', { quoteNo: quote.quoteNo }),
        'success',
      )
      uploadConflict.value = null
      return
    }

    const pdfBlob = await buildQuotationPdfBlob(quote, props.currentUser || undefined)
    const pdfName = buildQuotationExportFileName(quote, 'pdf')
    const pdfUploadResult = await uploadBlobToFeishu(pdfBlob, pdfName, uploadOpts)
    emit('feishuUploadDone', quote.id)
    emit(
      'toast',
      pdfUploadResult.reused_existing
        ? t('quotation.pages.list.toastPdfReused', { quoteNo: quote.quoteNo })
        : pdfUploadResult.renamed_from
          ? t('quotation.pages.list.toastPdfRenamed', {
              quoteNo: quote.quoteNo,
              fileName: pdfUploadResult.file_name,
            })
          : t('quotation.pages.list.toastPdfUploaded', { quoteNo: quote.quoteNo }),
      'success',
    )
    uploadConflict.value = null
  } catch (err: unknown) {
    if (err instanceof FeishuUploadConflictError) {
      uploadConflict.value = {
        quote,
        format,
        conflict: err.conflict,
        folderToken,
      }
      return
    }
    emit(
      'toast',
      err instanceof Error ? err.message : t('quotation.pages.list.toastUploadFailed'),
      'error',
    )
  } finally {
    uploadingQuoteId.value = null
  }
}

async function resolveUploadConflict(action: FeishuUploadConflictAction) {
  if (!uploadConflict.value) return
  const { quote, format, folderToken } = uploadConflict.value
  await handleUploadToFeishu(quote, format, action, folderToken)
}

async function handleUploadFolderSelected(folder: { token: string; name: string }) {
  const pending = uploadFolderPicker.value
  uploadFolderPicker.value = null
  if (!pending) return
  await handleUploadToFeishu(pending.quote, pending.format, undefined, folder.token)
}

function handleUploadFolderPickerOpen(open: boolean) {
  if (!open) uploadFolderPicker.value = null
}

function handleResetFilters() {
  searchText.value = ''
  selectedStatus.value = 'ALL'
  selectedProductLine.value = 'ALL'
  selectedSource.value = 'ALL'
  createdFrom.value = ''
  createdTo.value = ''
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

const filteredQuotations = computed(() => {
  return props.quotations.filter((q) => {
    const matchesText =
      q.quoteNo.toLowerCase().includes(searchText.value.toLowerCase()) ||
      q.projectName.toLowerCase().includes(searchText.value.toLowerCase()) ||
      q.clientCompany.toLowerCase().includes(searchText.value.toLowerCase()) ||
      q.contactPerson.toLowerCase().includes(searchText.value.toLowerCase()) ||
      q.email.toLowerCase().includes(searchText.value.toLowerCase())

    const matchesStatus = selectedStatus.value === 'ALL' || q.status === selectedStatus.value
    const quoteProductLine = (q.productLine || '').trim() || 'BDR'
    const matchesProductLine =
      selectedProductLine.value === 'ALL' ||
      quoteProductLine === selectedProductLine.value
    const matchesSource =
      selectedSource.value === 'ALL' ||
      (q.sourceType || 'manual') === selectedSource.value
    const quoteDate = q.createdAt.substring(0, 10)
    const matchesCreatedFrom = !createdFrom.value || quoteDate >= createdFrom.value
    const matchesCreatedTo = !createdTo.value || quoteDate <= createdTo.value

    return (
      matchesText &&
      matchesStatus &&
      matchesProductLine &&
      matchesSource &&
      matchesCreatedFrom &&
      matchesCreatedTo
    )
  })
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
              {{ t('quotation.pages.list.filterResultsCount', { count: filteredQuotations.length }) }}
            </div>
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
            <tr v-if="filteredQuotations.length === 0">
              <td colspan="8" class="py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.pages.list.emptyResults') }}
              </td>
            </tr>
            <template v-else>
            <tr
              v-for="quote in filteredQuotations"
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
              </td>
              <td class="py-3.5 px-4">
                <div class="max-w-[180px] sm:max-w-xs truncate">
                  <p class="font-semibold text-dm-text" :title="quote.projectName">
                    {{ quote.projectName }}
                  </p>
                  <p class="text-xs text-dm-text-tertiary font-mono mt-0.5">
                    {{ t('quotation.common.lineItemCount', { count: quote.items.length }) }}
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
                          : t('quotation.pages.list.downloadLocal')
                      "
                      :disabled="quote.status === 'Cancelled'"
                      :class="`p-1 rounded-sm transition duration-100 ${
                        quote.status === 'Cancelled'
                          ? 'text-slate-300 cursor-not-allowed'
                          : 'text-dm-text-tertiary hover:text-emerald-600 hover:bg-emerald-50 cursor-pointer'
                      }`"
                      @click="
                        quote.status !== 'Cancelled' &&
                          toggleActionMenu(quote, 'download', $event)
                      "
                    >
                      <Download class="w-4 h-4" />
                    </button>
                  </div>

                  <button
                    v-if="feishuDocumentId(quote, 'excel')"
                    :title="t('quotation.actions.openFeishuExcel')"
                    class="p-1 rounded-sm transition duration-100 text-dm-text-tertiary hover:text-emerald-600 hover:bg-emerald-50 cursor-pointer"
                    @click="void openFeishuFile(quote, 'excel')"
                  >
                    <FileSpreadsheet class="w-4 h-4" />
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


    <FeishuFolderPickerModal
      :open="Boolean(uploadFolderPicker)"
      intent="upload"
      @update:open="handleUploadFolderPickerOpen"
      @select="handleUploadFolderSelected"
      @toast="(message, type) => emit('toast', message, type)"
    />

    <div
      v-if="uploadConflict"
      class="fixed inset-0 z-[80] flex items-center justify-center p-4 dm-modal-overlay"
    >
      <div class="w-full max-w-md overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
        <div class="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div class="flex min-w-0 items-start gap-3">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600"
            >
              <UploadCloud class="h-4 w-4" />
            </div>
            <div class="min-w-0">
              <h3 class="text-[15px] font-semibold text-slate-900">
                {{ t('quotation.pages.list.conflictTitle') }}
              </h3>
              <p class="mt-0.5 text-xs leading-relaxed text-slate-500">
                {{
                  t('quotation.pages.list.conflictDesc', {
                    fileName: uploadConflict.conflict.file_name,
                  })
                }}
              </p>
            </div>
          </div>
          <button
            type="button"
            class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 hover:bg-slate-50 hover:text-slate-700"
            :aria-label="t('quotation.actions.cancelUpload')"
            @click="uploadConflict = null"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <div class="bg-slate-50/40 px-5 py-4">
          <div class="space-y-2 rounded-lg border border-slate-200 bg-white p-3.5 text-sm shadow-sm">
            <div class="flex items-start justify-between gap-4">
              <span class="shrink-0 text-slate-500">
                {{ t('quotation.pages.list.conflictExistingFile') }}
              </span>
              <span class="break-all text-right font-medium text-slate-900">{{
                uploadConflict.conflict.existing.file_name
              }}</span>
            </div>
            <div class="flex items-start justify-between gap-4">
              <span class="shrink-0 text-slate-500">
                {{ t('quotation.pages.list.conflictSuggestedName') }}
              </span>
              <span class="break-all text-right font-medium text-blue-600">{{
                uploadConflict.conflict.suggested_file_name
              }}</span>
            </div>
          </div>

          <div class="mt-4 rounded-lg border border-blue-100 bg-blue-50 px-3.5 py-3">
            <p class="text-sm font-semibold text-blue-800">
              {{ t('quotation.actions.reuseExistingFile') }}
            </p>
            <p class="mt-0.5 text-xs leading-relaxed text-blue-600">
              {{ t('quotation.pages.list.conflictReuseDesc') }}
            </p>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-slate-100 bg-white px-5 py-4">
          <button
            type="button"
            class="inline-flex h-9 items-center justify-center whitespace-nowrap rounded-md border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
            @click="uploadConflict = null"
          >
            {{ t('quotation.actions.cancelUpload') }}
          </button>
          <button
            type="button"
            class="inline-flex h-9 items-center justify-center whitespace-nowrap rounded-md border border-slate-200 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-600"
            @click="resolveUploadConflict('reuse')"
          >
            {{ t('quotation.actions.reuseExistingFile') }}
          </button>
          <button
            type="button"
            class="dm-btn-primary h-9 whitespace-nowrap px-3.5 text-sm font-semibold"
            @click="resolveUploadConflict('rename')"
          >
            {{ t('quotation.actions.renameAndUpload') }}
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="actionMenu && actionMenuQuote"
        data-action-menu
        class="fixed z-[120] w-44 overflow-hidden rounded-lg border border-dm-border bg-white py-1 shadow-lg"
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
          <button
            v-if="
              actionMenuQuote.sourceType !== 'document_import' ||
              actionMenuQuote.sourceDocumentType === 'excel'
            "
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
            @click="handleDownloadLocal(actionMenuQuote, 'excel')"
          >
            <FileSpreadsheet class="h-3.5 w-3.5" />
            {{ t('quotation.actions.downloadExcel') }}
          </button>
          <button
            v-if="
              actionMenuQuote.sourceType !== 'document_import' ||
              actionMenuQuote.sourceDocumentType === 'pdf'
            "
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-dm-text hover:bg-emerald-50 hover:text-emerald-700"
            @click="handleDownloadLocal(actionMenuQuote, 'pdf')"
          >
            <ExternalLink class="h-3.5 w-3.5" />
            {{ t('quotation.actions.downloadPdf') }}
          </button>
        </template>
      </div>
    </Teleport>

  </div>
</template>
