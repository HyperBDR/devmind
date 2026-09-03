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
  Columns3,
  Copy,
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
  checkFeishuFileAccess,
  isFeishuFolderItem,
  listFeishuFolder,
} from '../api/feishu'
import { getAccessRequestContext } from '../api/accessRequests'
import {
  archiveQuotationFile,
  exportQuotationFile,
  retryQuotationUpload,
  waitForQuotationExport,
  type QuotationExportStatus,
} from '../api/exports'
import { downloadImportedDocument } from '../api/documents'
import PublicAttachmentPicker from './PublicAttachmentPicker.vue'
import type { QuotationListParams } from '../api/quotations'
import type { Quotation } from '../types'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import { clearedFeishuFields } from '../utils/feishuLinkState'
import { buildQuotationExportFileName } from '../utils/quotationFileName'
import {
  getCurrencyShortLabel,
  getCurrencySymbol,
} from '../utils/quotationPreviewModel'
import FeishuFolderPickerModal from './FeishuFolderPickerModal.vue'
import FormSelect from './FormSelect.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

type FeishuUploadFormat = 'excel' | 'pdf'

const props = defineProps<{
  quotations: Quotation[]
  productLines: string[]
  currencies?: string[]
  loading?: boolean
  page: number
  pageSize: 10 | 20 | 50
  total: number
  totalPages: number
  initialCreatedFrom?: string
  initialCreatedTo?: string
  currentUser?: {
    name: string
    title: string
    email: string
    role?: string
  } | null
}>()

const emit = defineEmits<{
  viewQuote: [id: string]
  openDetailDrawer: [id: string]
  deleteQuote: [id: string]
  updateQuoteStatus: [id: string, updatedFields: Partial<Quotation>, notes?: string]
  feishuUploadDone: [id: string]
  reconcileFeishuLinks: []
  editQuote: [id: string]
  copyQuote: [id: string]
  toast: [message: string, type?: 'success' | 'info' | 'error']
  queryChange: [query: QuotationListParams]
}>()

const { t } = useQuotationI18n()

const productLineFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.list.productLineAll') },
  ...props.productLines.map((productLine) => ({
    value: productLine,
    label: productLine,
  })),
])

const sourceFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.list.sourceAll') },
  { value: 'manual', label: t('quotation.pages.list.sourceLocalCreated') },
  {
    value: 'document_import',
    label: t('quotation.pages.list.sourceDocumentImport'),
  },
])

const currencyFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.list.currencyAll') },
  ...Array.from(new Set(
    (props.currencies || props.quotations.map((quote) => quote.currency)),
  ))
    .filter(Boolean)
    .sort()
    .map((currency) => ({
      value: currency,
      label: getCurrencyShortLabel(currency),
    })),
])

const pageSizeOptions = [10, 20, 50].map((value) => ({
  value: String(value),
  label: String(value),
}))

const columnConfig = {
  quoteNo: {
    defaultWidth: 170,
    minWidth: 130,
    maxWidth: 360,
    labelKey: 'quotation.pages.list.tableQuoteNo',
    align: 'left',
  },
  project: {
    defaultWidth: 360,
    minWidth: 180,
    maxWidth: 720,
    labelKey: 'quotation.pages.list.tableProjectName',
    align: 'left',
  },
  customer: {
    defaultWidth: 300,
    minWidth: 160,
    maxWidth: 600,
    labelKey: 'quotation.pages.list.tableCustomer',
    align: 'left',
  },
  contact: {
    defaultWidth: 180,
    minWidth: 150,
    maxWidth: 480,
    labelKey: 'quotation.pages.list.tableContact',
    align: 'left',
  },
  salesperson: {
    defaultWidth: 170,
    minWidth: 140,
    maxWidth: 480,
    labelKey: 'quotation.pages.list.tableSalesperson',
    align: 'left',
  },
  total: {
    defaultWidth: 120,
    minWidth: 108,
    maxWidth: 280,
    labelKey: 'quotation.pages.list.tableTotal',
    align: 'right',
  },
  currency: {
    defaultWidth: 92,
    minWidth: 80,
    maxWidth: 160,
    labelKey: 'quotation.pages.list.tableCurrency',
    align: 'center',
  },
  source: {
    defaultWidth: 170,
    minWidth: 150,
    maxWidth: 360,
    labelKey: 'quotation.pages.list.tableSource',
    align: 'center',
  },
  quoteDate: {
    defaultWidth: 120,
    minWidth: 112,
    maxWidth: 240,
    labelKey: 'quotation.pages.list.tableQuoteDate',
    align: 'left',
  },
} as const

type ResizableColumnKey = keyof typeof columnConfig

const ACTIONS_COLUMN_WIDTH = 152
const COLUMN_RESIZE_STEP = 16

const columnWidths = ref<Record<ResizableColumnKey, number>>({
  quoteNo: columnConfig.quoteNo.defaultWidth,
  project: columnConfig.project.defaultWidth,
  customer: columnConfig.customer.defaultWidth,
  contact: columnConfig.contact.defaultWidth,
  salesperson: columnConfig.salesperson.defaultWidth,
  total: columnConfig.total.defaultWidth,
  currency: columnConfig.currency.defaultWidth,
  source: columnConfig.source.defaultWidth,
  quoteDate: columnConfig.quoteDate.defaultWidth,
})

const resizableColumns = computed(() =>
  (Object.keys(columnConfig) as ResizableColumnKey[]).map((key) => ({
    key,
    ...columnConfig[key],
    label: t(columnConfig[key].labelKey),
  })),
)

const defaultColumnKeys: ResizableColumnKey[] = [
  'quoteNo',
  'project',
  'customer',
  'total',
]
const visibleColumnKeys = ref<ResizableColumnKey[]>([...defaultColumnKeys])
const columnsOpen = ref(false)
const visibleColumns = computed(() =>
  resizableColumns.value.filter((column) =>
    visibleColumnKeys.value.includes(column.key),
  ),
)
const visibleTableWidth = computed(
  () =>
    visibleColumns.value.reduce(
      (total, column) => total + columnWidths.value[column.key],
      ACTIONS_COLUMN_WIDTH,
    ),
)
const tableUsesHorizontalScroll = computed(
  () => visibleColumnKeys.value.length > defaultColumnKeys.length,
)

function tableColumnWidth(key: ResizableColumnKey | 'actions'): string {
  const width = key === 'actions'
    ? ACTIONS_COLUMN_WIDTH
    : columnWidths.value[key]
  return tableUsesHorizontalScroll.value
    ? `${width}px`
    : `${(width / visibleTableWidth.value) * 100}%`
}

let activeColumnResize: {
  key: ResizableColumnKey
  pointerId: number
  startX: number
  startWidth: number
  handle: HTMLElement
  previousCursor: string
  previousUserSelect: string
} | null = null

const searchText = ref('')
const selectedProductLine = ref('ALL')
const selectedSource = ref('ALL')
const selectedCurrency = ref('ALL')
const createdFrom = ref(props.initialCreatedFrom || '')
const createdTo = ref(props.initialCreatedTo || '')
const uploadAccessLoading = ref(false)
const hasUploadAccess = ref(false)
const uploadUnavailable = computed(
  () => uploadAccessLoading.value || !hasUploadAccess.value,
)
const deleteConfirmId = ref<string | null>(null)
const uploadingQuoteId = ref<string | null>(null)
const exportProgressByQuote = ref<Record<string, QuotationExportStatus>>({})
const failedUploadByQuote = ref<
  Record<string, { jobId: string; format: FeishuUploadFormat }>
>({})
const folderPickerOpen = ref(false)
const pendingFeishuUpload = ref<{
  quote: Quotation
  format: FeishuUploadFormat
} | null>(null)
const attachmentPickerOpen = ref(false)
const pendingAttachmentDownload = ref<{
  quote: Quotation
  quotationVersion?: number
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
let searchTimer: number | undefined
let suppressFilterWatch = false

watch(
  () => [props.initialCreatedFrom, props.initialCreatedTo] as const,
  async ([nextFrom, nextTo]) => {
    const createdFromValue = nextFrom || ''
    const createdToValue = nextTo || ''
    if (
      createdFrom.value === createdFromValue
      && createdTo.value === createdToValue
    ) {
      return
    }
    suppressFilterWatch = true
    createdFrom.value = createdFromValue
    createdTo.value = createdToValue
    await nextTick()
    suppressFilterWatch = false
  },
)

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
  void loadUploadAccess()
}

async function loadUploadAccess() {
  if (uploadAccessLoading.value) return
  uploadAccessLoading.value = true
  try {
    const context = await getAccessRequestContext()
    if (context.is_admin) {
      hasUploadAccess.value = true
      return
    }
    const listing = await listFeishuFolder(undefined, 'upload')
    hasUploadAccess.value = listing.files.some(isFeishuFolderItem)
  } catch {
    hasUploadAccess.value = false
  } finally {
    uploadAccessLoading.value = false
  }
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
  if (!target?.closest('[data-column-picker]')) {
    columnsOpen.value = false
  }
}

function clampColumnWidth(key: ResizableColumnKey, width: number): number {
  const config = columnConfig[key]
  return Math.min(config.maxWidth, Math.max(config.minWidth, width))
}

function setColumnWidth(key: ResizableColumnKey, width: number) {
  columnWidths.value[key] = clampColumnWidth(key, Math.round(width))
}

function finishColumnResize(event?: PointerEvent) {
  const resize = activeColumnResize
  if (!resize) return
  if (event && event.pointerId !== resize.pointerId) return

  if (resize.handle.hasPointerCapture(resize.pointerId)) {
    resize.handle.releasePointerCapture(resize.pointerId)
  }
  document.body.style.cursor = resize.previousCursor
  document.body.style.userSelect = resize.previousUserSelect
  activeColumnResize = null
}

function startColumnResize(key: ResizableColumnKey, event: PointerEvent) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  finishColumnResize()

  const handle = event.currentTarget as HTMLElement
  activeColumnResize = {
    key,
    pointerId: event.pointerId,
    startX: event.clientX,
    startWidth: columnWidths.value[key],
    handle,
    previousCursor: document.body.style.cursor,
    previousUserSelect: document.body.style.userSelect,
  }
  handle.setPointerCapture(event.pointerId)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function handleColumnResize(event: PointerEvent) {
  const resize = activeColumnResize
  if (!resize || event.pointerId !== resize.pointerId) return
  setColumnWidth(
    resize.key,
    resize.startWidth + event.clientX - resize.startX,
  )
}

function resizeColumnBy(key: ResizableColumnKey, delta: number) {
  setColumnWidth(key, columnWidths.value[key] + delta)
}

function isNestedRowAction(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest(
      'button, a, input, select, textarea, [role="button"], [data-row-action]',
    ),
  )
}

function openQuoteDetails(quote: Quotation) {
  emit('openDetailDrawer', quote.id)
}

function handleRowClick(quote: Quotation, event: MouseEvent) {
  if (isNestedRowAction(event.target)) return
  if (event.currentTarget instanceof HTMLElement) {
    event.currentTarget.focus()
  }
  openQuoteDetails(quote)
}

function handleRowKeydown(quote: Quotation, event: KeyboardEvent) {
  if (isNestedRowAction(event.target)) return
  event.preventDefault()
  openQuoteDetails(quote)
}

onMounted(async () => {
  suppressFilterWatch = true
  document.addEventListener('mousedown', handleOutsideClick)
  window.addEventListener('scroll', closeActionMenu, true)
  window.addEventListener('resize', closeActionMenu)
  document.addEventListener('visibilitychange', handlePageVisible)
  window.addEventListener('focus', handlePageVisible)
  void loadUploadAccess()
  await nextTick()
  suppressFilterWatch = false
})

onBeforeUnmount(() => {
  finishColumnResize()
  document.removeEventListener('mousedown', handleOutsideClick)
  window.removeEventListener('scroll', closeActionMenu, true)
  window.removeEventListener('resize', closeActionMenu)
  document.removeEventListener('visibilitychange', handlePageVisible)
  window.removeEventListener('focus', handlePageVisible)
  window.clearTimeout(reconcileTimer)
  window.clearTimeout(searchTimer)
})

function currencySymbol(currency: Quotation['currency'] | string): string {
  return getCurrencySymbol(currency)
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
  if (quote.status === 'Cancelled' || !hasUploadAccess.value) {
    return
  }
  closeActionMenu()
  pendingFeishuUpload.value = { quote, format }
  folderPickerOpen.value = true
}

function handleFeishuFolderSelected(folder: { token: string; name: string }) {
  const pending = pendingFeishuUpload.value
  folderPickerOpen.value = false
  pendingFeishuUpload.value = null
  if (!pending) return
  void handleUploadToFeishu(pending.quote, pending.format, folder.token)
}

function feishuDocumentId(
  quote: Quotation,
  format: FeishuUploadFormat,
): string | undefined {
  return format === 'excel'
    ? quote.feishuExcelDocumentId
    : quote.feishuPdfDocumentId
}

function feishuDocumentUrl(
  quote: Quotation,
  format: FeishuUploadFormat,
): string | undefined {
  return format === 'excel' ? quote.feishuExcelUrl : quote.feishuPdfUrl
}

async function openFeishuFile(quote: Quotation, format: FeishuUploadFormat) {
  const documentId = feishuDocumentId(quote, format)
  if (!documentId) return
  closeActionMenu()
  const cachedUrl = feishuDocumentUrl(quote, format)
  const popup = cachedUrl
    ? window.open(cachedUrl, '_blank', 'noopener,noreferrer')
    : null
  if (popup) popup.opener = null
  try {
    const result = await checkFeishuFileAccess(documentId)
    if (!result.exists) {
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
    if (!result.direct_access_allowed && result.content_url) {
      const contentUrl = result.content_url
      if (popup) {
        popup.location.replace(contentUrl)
      } else {
        window.open(contentUrl, '_blank', 'noopener,noreferrer')
      }
      return
    }
    if (!result.direct_access_allowed || !directUrl) {
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
  if (format === 'pdf') {
    closeActionMenu()
    pendingAttachmentDownload.value = { quote, quotationVersion }
    attachmentPickerOpen.value = true
    return
  }
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

async function handleAttachmentDownload(ids: string[]) {
  const pending = pendingAttachmentDownload.value
  attachmentPickerOpen.value = false
  pendingAttachmentDownload.value = null
  if (!pending) return
  try {
    await exportQuotationFile(pending.quote.id, 'pdf', {
      onProgress: (job) => updateExportProgress(pending.quote.id, job.status),
      quotationVersion: pending.quotationVersion,
      attachmentSelection: ids,
    })
    emit(
      'toast',
      t('quotation.pages.list.toastPdfDownloadStarted', {
        quoteNo: pending.quote.quoteNo,
      }),
      'success',
    )
  } catch (error) {
    emit('toast', error instanceof Error ? error.message : 'Download failed', 'error')
  }
}

async function handleUploadToFeishu(
  quote: Quotation,
  format: FeishuUploadFormat = 'excel',
  folderToken = '',
) {
  if (quote.status === 'Cancelled') return
  uploadingQuoteId.value = quote.id
  try {
    const exportFormat = format === 'excel' ? 'xlsx' : 'pdf'
    const job = await archiveQuotationFile(quote.id, exportFormat, {
      onProgress: (progressJob) => {
        updateExportProgress(quote.id, progressJob.status)
      },
      archiveFolderToken: folderToken,
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
    const uploadedAsset = job.assets.find(
      (asset) => asset.format === exportFormat,
    )
    if (uploadedAsset) {
      emit('updateQuoteStatus', quote.id, {
        ...(format === 'excel'
          ? { feishuExcelDocumentId: uploadedAsset.id }
          : { feishuPdfDocumentId: uploadedAsset.id }),
      })
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
    const uploadedAsset = job.assets.find(
      (asset) => asset.format === failedUpload.format,
    )
    if (uploadedAsset) {
      emit('updateQuoteStatus', quote.id, {
        ...(failedUpload.format === 'excel'
          ? { feishuExcelDocumentId: uploadedAsset.id }
          : { feishuPdfDocumentId: uploadedAsset.id }),
      })
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
    productLine:
      selectedProductLine.value === 'ALL'
        ? undefined
        : selectedProductLine.value,
    sourceType:
      selectedSource.value === 'ALL'
        ? undefined
        : (selectedSource.value as 'manual' | 'document_import'),
    currency: selectedCurrency.value === 'ALL' ? undefined : selectedCurrency.value,
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
  selectedProductLine.value = 'ALL'
  selectedSource.value = 'ALL'
  selectedCurrency.value = 'ALL'
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
    selectedProductLine,
    selectedSource,
    selectedCurrency,
    createdFrom,
    createdTo,
  ],
  () => {
    if (suppressFilterWatch) return
    emit('queryChange', listQuery(1))
  },
)

const hasActiveFilters = computed(
  () =>
    searchText.value.trim() !== '' ||
    selectedProductLine.value !== 'ALL' ||
    selectedSource.value !== 'ALL' ||
    selectedCurrency.value !== 'ALL' ||
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

function displayQuoteDate(quote: Quotation): string {
  return quote.quoteDate ? quote.quoteDate.substring(0, 10) : '—'
}

</script>

<template>
  <div
    id="quote-list-root"
    class="flex h-full min-h-[calc(100dvh-7.0625rem)] flex-col gap-3"
  >
    <div
      id="filter-panel"
      data-filter-toolbar
      aria-label="Quote filters"
      class="rounded-xl border border-dm-border-light bg-white p-2 shadow-xs"
    >
      <div class="grid grid-cols-1 items-end gap-2 md:grid-cols-2 xl:grid-cols-[minmax(0,1.35fr)_repeat(3,minmax(0,.7fr))_minmax(0,1.4fr)]">
          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.keywordLabel') }}
            </label>
            <div class="relative">
              <input
                v-model="searchText"
                type="text"
                :placeholder="t('quotation.pages.list.keywordPlaceholder')"
                class="h-9 w-full min-w-0 rounded-lg border border-dm-border-light bg-slate-50/70 py-1.5 pl-9 pr-9 text-sm text-dm-text transition placeholder:text-slate-400 hover:bg-white focus:border-blue-300 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-100"
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

          <div class="min-w-0" data-currency-filter>
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.currencyLabel') }}
            </label>
            <FormSelect
              v-model="selectedCurrency"
              class-name="w-full"
              :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
              :options="currencyFilterOptions"
            />
          </div>

          <div data-filter-date-range class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.list.dateRangeLabel') }}
            </label>
            <div class="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
              <BaseDatePicker
                v-model="createdFrom"
                :placeholder="t('quotation.pages.list.quoteDateFromLabel')"
                input-class="h-9 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-1.5 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
              />
              <BaseDatePicker
                v-model="createdTo"
                :placeholder="t('quotation.pages.list.quoteDateToLabel')"
                input-class="h-9 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-1.5 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
              />
            </div>
          </div>

      </div>
      <div class="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2">
        <div class="flex h-9 min-w-20 items-center justify-center whitespace-nowrap rounded-lg bg-slate-50 px-2.5 text-xs font-semibold text-dm-text-tertiary">
          {{ t('quotation.pages.list.filterResultsCount', { count: total }) }}
        </div>
        <div class="flex flex-wrap items-center justify-end gap-1">
            <div class="relative" data-column-picker>
              <button
                type="button"
                class="inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-dm-border-light bg-white px-2.5 text-xs font-semibold text-dm-text transition hover:bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-blue-200"
                @click.stop="columnsOpen = !columnsOpen"
              >
                <Columns3 class="h-3.5 w-3.5" />
                {{ t('quotation.pages.list.visibleColumns') }}
              </button>
              <div
                v-if="columnsOpen"
                class="absolute right-0 top-10 z-30 w-56 rounded-lg border border-dm-border-light bg-white p-2 shadow-xl"
              >
                <p class="px-2 py-1 text-xs font-bold text-dm-text">
                  {{ t('quotation.pages.list.visibleColumns') }}
                </p>
                <label
                  v-for="column in resizableColumns"
                  :key="column.key"
                  class="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-xs text-dm-text-secondary hover:bg-slate-50"
                >
                  <input
                    v-model="visibleColumnKeys"
                    type="checkbox"
                    :value="column.key"
                    class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-200"
                  />
                  {{ column.label }}
                </label>
                <button
                  type="button"
                  class="mt-1 w-full border-t border-slate-100 px-2 pt-2 text-left text-xs font-semibold text-blue-600 hover:text-blue-700"
                  @click="visibleColumnKeys = [...defaultColumnKeys]"
                >
                  {{ t('quotation.pages.list.resetColumns') }}
                </button>
              </div>
            </div>
            <button
              type="button"
              :class="`inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-xs font-semibold transition cursor-pointer ${
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

    <div
      id="table-panel"
      class="flex flex-1 flex-col rounded-xl border border-dm-border-light bg-white shadow-xs"
    >
      <div class="flex flex-1 overflow-hidden rounded-t-xl">
        <div
          class="flex-1"
          :class="tableUsesHorizontalScroll ? 'overflow-x-auto' : 'overflow-hidden'"
          data-quotation-table-scroller
        >
        <table
          class="w-full table-fixed border-collapse text-left"
          :class="{ 'h-full': pageSize === 10 && quotations.length === 10 }"
          :style="tableUsesHorizontalScroll
            ? { width: `${visibleTableWidth}px`, minWidth: `${visibleTableWidth}px` }
            : { width: '100%' }"
        >
          <colgroup>
            <col
              v-for="column in visibleColumns"
              :key="column.key"
              :data-column-key="column.key"
              :style="{ width: tableColumnWidth(column.key) }"
            />
            <col :style="{ width: tableColumnWidth('actions') }" />
          </colgroup>
          <thead>
            <tr
              class="bg-[#fafafa] border-b border-dm-border-light text-dm-text-tertiary text-xs font-bold tracking-wider"
            >
              <th
                v-for="column in visibleColumns"
                :key="column.key"
                :data-column-header="column.key"
                class="relative px-3 py-1.5"
                :class="{
                  'text-center': column.align === 'center',
                  'text-right': column.align === 'right',
                }"
              >
                <span class="block truncate whitespace-nowrap">
                  {{ column.label }}
                </span>
                <span
                  role="separator"
                  aria-orientation="vertical"
                  :aria-label="
                    t('quotation.pages.list.resizeColumn', {
                      column: column.label,
                    })
                  "
                  :aria-valuemin="column.minWidth"
                  :aria-valuemax="column.maxWidth"
                  :aria-valuenow="columnWidths[column.key]"
                  :title="t('quotation.pages.list.resizeColumnHint')"
                  tabindex="0"
                  class="group absolute right-0 top-0 z-10 flex h-full w-3 touch-none select-none items-center justify-center cursor-col-resize focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-blue-400"
                  data-column-resizer
                  :data-column-key="column.key"
                  @click.stop.prevent
                  @pointerdown.stop.prevent="startColumnResize(column.key, $event)"
                  @pointermove.stop.prevent="handleColumnResize"
                  @pointerup.stop.prevent="finishColumnResize"
                  @pointercancel.stop.prevent="finishColumnResize"
                  @keydown.left.stop.prevent="
                    resizeColumnBy(column.key, -COLUMN_RESIZE_STEP)
                  "
                  @keydown.right.stop.prevent="
                    resizeColumnBy(column.key, COLUMN_RESIZE_STEP)
                  "
                >
                  <span
                    class="h-5 w-px bg-slate-300 transition group-hover:w-0.5 group-hover:bg-blue-500 group-focus:w-0.5 group-focus:bg-blue-500"
                  />
                </span>
              </th>
              <th class="px-3 py-1.5 text-center">
                {{ t('quotation.pages.list.tableActions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-sm">
            <tr v-if="loading">
              <td
                :colspan="visibleColumns.length + 1"
                class="py-12 text-center text-dm-text-tertiary"
              >
                {{ t('quotation.pages.list.syncing') }}
              </td>
            </tr>
            <tr v-else-if="quotations.length === 0">
              <td
                :colspan="visibleColumns.length + 1"
                class="py-12 text-center text-dm-text-tertiary"
              >
                {{ t('quotation.pages.list.emptyResults') }}
              </td>
            </tr>
            <template v-else>
            <tr
              v-for="quote in quotations"
              :key="quote.id"
              data-quotation-row
              :data-source-type="quote.sourceType"
              tabindex="0"
              :aria-label="
                t('quotation.pages.list.openRowDetails', {
                  quoteNo: quote.quoteNo,
                })
              "
              class="group transition duration-150 hover:bg-[#fafafa] focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-blue-300"
              :class="{ 'cursor-pointer': true }"
              @click="handleRowClick(quote, $event)"
              @keydown.enter="handleRowKeydown(quote, $event)"
              @keydown.space="handleRowKeydown(quote, $event)"
            >
              <td v-if="visibleColumnKeys.includes('quoteNo')" class="px-3 py-1">
                <p
                  class="block truncate whitespace-nowrap font-mono font-semibold text-slate-700 transition group-hover:text-blue-700"
                  :title="quote.quoteNo"
                >
                  <span>{{ quote.quoteNo }}</span>
                  <span
                    v-if="quote.status === 'Draft'"
                    class="ml-1 font-sans text-xs font-medium text-dm-text-secondary"
                  >
                    {{ t('quotation.pages.list.draftSuffix') }}
                  </span>
                </p>
                <p
                  v-if="exportProgressByQuote[quote.id]"
                  class="mt-1 text-xs font-medium text-indigo-600"
                >
                  {{ exportProgressLabel(quote.id) }}
                </p>
              </td>
              <td v-if="visibleColumnKeys.includes('project')" class="px-3 py-1">
                <div class="min-w-0">
                  <p
                    class="truncate whitespace-nowrap font-semibold text-dm-text"
                    :title="quote.projectName"
                  >
                    {{ quote.projectName }}
                  </p>
                  <p class="mt-0.5 truncate whitespace-nowrap font-mono text-xs text-dm-text-tertiary">
                    {{
                      t('quotation.common.lineItemCount', {
                        count: quote.itemCount ?? quote.items.length,
                      })
                    }}
                  </p>
                </div>
              </td>
              <td v-if="visibleColumnKeys.includes('customer')" class="px-3 py-1">
                <div class="min-w-0">
                  <p
                    class="truncate whitespace-nowrap font-medium text-dm-text"
                    :title="quote.clientCompany"
                  >
                    {{ quote.clientCompany }}
                  </p>
                </div>
              </td>
              <td
                v-if="visibleColumnKeys.includes('contact')"
                class="truncate whitespace-nowrap px-3 py-1 text-dm-text-secondary font-medium"
                :title="displayContact(quote) === '—' ? undefined : displayContact(quote)"
              >
                {{ displayContact(quote) }}
              </td>
              <td
                v-if="visibleColumnKeys.includes('salesperson')"
                class="truncate whitespace-nowrap px-3 py-1 text-dm-text-secondary font-medium"
              >
                {{ quote.salesperson || '—' }}
              </td>
              <td
                v-if="visibleColumnKeys.includes('total')"
                class="px-3 py-1 text-right font-bold text-dm-text font-mono"
              >
                {{ displayTotal(quote) }}
              </td>
              <td
                v-if="visibleColumnKeys.includes('currency')"
                class="px-3 py-1 text-center font-mono text-xs font-semibold text-dm-text-secondary"
              >
                {{ getCurrencyShortLabel(quote.currency) }}
              </td>
              <td
                v-if="visibleColumnKeys.includes('source')"
                class="px-3 py-1 text-center"
              >
                <span
                  v-if="quote.sourceType === 'document_import'"
                  class="inline-flex whitespace-nowrap rounded-full bg-fuchsia-100 px-2 py-0.5 text-xs font-semibold text-fuchsia-800 ring-1 ring-inset ring-fuchsia-300"
                >
                  {{ t('quotation.pages.list.sourceDocumentImport') }}
                </span>
                <span
                  v-else
                  class="inline-flex whitespace-nowrap rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700 ring-1 ring-inset ring-sky-200"
                >
                  {{ t('quotation.pages.list.sourceLocalCreated') }}
                </span>
              </td>
              <td
                v-if="visibleColumnKeys.includes('quoteDate')"
                class="whitespace-nowrap px-3 py-1 font-mono text-dm-text-tertiary"
              >
                {{ displayQuoteDate(quote) }}
              </td>
              <td class="px-3 py-1">
                <div class="flex items-center justify-center gap-1.5">
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

                  <button
                    v-if="quote.sourceType !== 'document_import'"
                    type="button"
                    :title="t('quotation.pages.list.copyQuote')"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-blue-50 hover:text-blue-600"
                    @click.stop="emit('copyQuote', quote.id)"
                  >
                    <Copy class="h-4 w-4" />
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
                      :disabled="quote.status === 'Cancelled' || uploadingQuoteId === quote.id || uploadUnavailable"
                      :class="`p-1 rounded-sm transition duration-100 ${
                        quote.status === 'Cancelled' || uploadingQuoteId === quote.id || uploadUnavailable
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
                    :disabled="uploadingQuoteId === quote.id || uploadUnavailable"
                    class="cursor-pointer rounded-sm p-1 text-amber-600 transition duration-100 hover:bg-amber-50 hover:text-amber-700 disabled:cursor-not-allowed disabled:text-slate-300"
                    @click="void retryFailedUpload(quote)"
                  >
                    <RotateCcw class="h-4 w-4" />
                  </button>

                  <button
                    v-if="feishuDocumentId(quote, 'excel')"
                    :title="t('quotation.actions.openFeishuExcel')"
                    :class="[
                      'p-1 rounded-sm transition duration-100 cursor-pointer',
                      quote.sourceType === 'document_import'
                        ? 'text-dm-text-tertiary hover:text-emerald-600 hover:bg-emerald-50'
                        : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50',
                    ]"
                    @click="void openFeishuFile(quote, 'excel')"
                  >
                    <ExternalLink
                      v-if="quote.sourceType === 'document_import'"
                      class="w-4 h-4"
                    />
                    <FileSpreadsheet v-else class="w-4 h-4" />
                  </button>

                  <button
                    v-if="feishuDocumentId(quote, 'pdf')"
                    :title="t('quotation.actions.openFeishuPdf')"
                    :class="[
                      'p-1 rounded-sm transition duration-100 cursor-pointer',
                      quote.sourceType === 'document_import'
                        ? 'text-dm-text-tertiary hover:text-indigo-600 hover:bg-indigo-50'
                        : 'text-red-600 hover:text-red-700 hover:bg-red-50',
                    ]"
                    @click="void openFeishuFile(quote, 'pdf')"
                  >
                    <ExternalLink
                      v-if="quote.sourceType === 'document_import'"
                      class="w-4 h-4"
                    />
                    <FileText v-else class="w-4 h-4" />
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
        class="flex flex-col gap-2 border-t border-dm-border-light px-3 py-2 text-sm text-dm-text-tertiary sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>
            {{ t('quotation.pages.list.paginationTotal', { count: total }) }}
          </span>
          <span>
            {{
              t('quotation.pages.list.paginationRange', {
                start: rangeStart,
                end: rangeEnd,
              })
            }}
          </span>
          <span>
            {{
              t('quotation.pages.list.paginationPages', {
                count: totalPages,
              })
            }}
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex items-center gap-2">
            <span>{{ t('quotation.pages.list.paginationPageSize') }}</span>
            <FormSelect
              :value="String(pageSize)"
              class-name="w-20"
              trigger-class-name="h-8 rounded-md border-dm-border bg-white px-2 text-sm focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              panel-class-name="!bottom-full !top-auto !mb-1 !mt-0"
              :options="pageSizeOptions"
              test-id="quotation-page-size"
              @change="handlePageSizeChange"
            />
          </label>
          <button
            type="button"
            class="h-8 rounded-md border border-dm-border px-2.5 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="page <= 1 || loading"
            @click="requestPage(page - 1)"
          >
            {{ t('quotation.pages.list.paginationPrevious') }}
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
            {{ t('quotation.pages.list.paginationNext') }}
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

    <FeishuFolderPickerModal
      :open="folderPickerOpen"
      intent="upload"
      @update:open="folderPickerOpen = $event"
      @select="handleFeishuFolderSelected"
      @toast="(message, type) => emit('toast', message, type)"
    />

    <PublicAttachmentPicker
      :open="attachmentPickerOpen"
      @close="attachmentPickerOpen = false"
      @confirm="handleAttachmentDownload"
    />

  </div>
</template>
