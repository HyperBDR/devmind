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
  Columns3,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  Pencil,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import { useUserStore } from '@/store/user'

import {
  downloadInvoicePdf,
  deleteInvoice,
  InvoiceStatus,
  listInvoices,
  type InvoiceContactFacet,
  type InvoiceRecord,
  updateInvoice,
  uploadInvoiceToFeishu,
} from '../../api/invoices'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../../utils/formFieldClasses'
import {
  loadVisibleColumns,
  saveVisibleColumns,
} from '../../utils/visibleColumnStorage'
import FormSelect from '../FormSelect.vue'
import InvoiceFeishuFolderPickerModal from './InvoiceFeishuFolderPickerModal.vue'
import InvoiceDetailsDrawer from './InvoiceDetailsDrawer.vue'

const { locale, t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const invoices = ref<InvoiceRecord[]>([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const selectedCurrency = ref('ALL')
const selectedInvoiceContact = ref('ALL')
const currencies = ref<string[]>([])
const invoiceContacts = ref<InvoiceContactFacet[]>([])
const invoiceFrom = ref('')
const invoiceTo = ref('')
const downloadingId = ref('')
const issuingId = ref('')
const uploadingId = ref('')
const deletingId = ref('')
const uploadInvoice = ref<InvoiceRecord | null>(null)
const folderPickerOpen = ref(false)
const columnsOpen = ref(false)
const selectedInvoiceId = ref<string | null>(null)
const page = ref(1)
const pageSize = ref<10 | 20 | 50>(10)
const total = ref(0)
const totalPages = ref(0)
let searchTimer: number | undefined
let suppressFilterWatch = false

const pageSizeOptions = [10, 20, 50].map((value) => ({
  value: String(value),
  label: String(value),
}))

const invoiceColumnConfig = {
  invoiceNo: { label: 'invoiceNo', width: 140, min: 112, max: 300 },
  documentKind: { label: 'documentKind', width: 120, min: 104, max: 240 },
  invoiceDate: { label: 'invoiceDate', width: 130, min: 120, max: 200 },
  customer: { label: 'customer', width: 150, min: 120, max: 340 },
  customerContactPerson: {
    label: 'customerContactPerson',
    width: 130,
    min: 112,
    max: 320,
  },
  contactPerson: { label: 'contactPerson', width: 120, min: 104, max: 280 },
  contactEmail: { label: 'contactEmail', width: 160, min: 136, max: 360 },
  customerAddress: {
    label: 'customerAddress',
    width: 280,
    min: 180,
    max: 520,
  },
  purchaseOrder: { label: 'purchaseOrder', width: 170, min: 120, max: 360 },
  source: { label: 'source', width: 120, min: 96, max: 240 },
  currency: { label: 'currency', width: 100, min: 84, max: 180 },
  total: { label: 'total', width: 112, min: 100, max: 220 },
} as const
type InvoiceColumnKey = keyof typeof invoiceColumnConfig
const ACTIONS_COLUMN_WIDTH = 112
const COLUMN_RESIZE_STEP = 16
const defaultInvoiceColumns: InvoiceColumnKey[] = [
  'invoiceNo',
  'documentKind',
  'invoiceDate',
  'customer',
  'customerContactPerson',
  'contactPerson',
  'contactEmail',
  'total',
]
const visibleInvoiceColumns = ref<InvoiceColumnKey[]>(
  loadVisibleColumns(
    'invoice',
    Object.keys(invoiceColumnConfig) as InvoiceColumnKey[],
    defaultInvoiceColumns,
  ),
)
const invoiceColumns = computed(() =>
  (Object.keys(invoiceColumnConfig) as InvoiceColumnKey[]).map((key) => ({
    key,
    ...invoiceColumnConfig[key],
    label: t(`quotation.sales.fields.${invoiceColumnConfig[key].label}`),
  })),
)
const visibleColumns = computed(() =>
  invoiceColumns.value.filter((column) => columnIsVisible(column.key)),
)
const invoiceTableWidth = computed(() =>
  visibleColumns.value.reduce(
    (total, column) => total + columnWidths.value[column.key],
    ACTIONS_COLUMN_WIDTH,
  ),
)
const columnWidths = ref<Record<InvoiceColumnKey, number>>(
  Object.fromEntries(
    Object.entries(invoiceColumnConfig).map(([key, config]) => [
      key,
      config.width,
    ]),
  ) as Record<InvoiceColumnKey, number>,
)
watch(
  visibleInvoiceColumns,
  (columns) => saveVisibleColumns('invoice', columns),
  { deep: true },
)
let activeColumnResize: {
  key: InvoiceColumnKey
  pointerId: number
  startX: number
  startWidth: number
  handle: HTMLElement
  previousCursor: string
  previousUserSelect: string
} | null = null

function columnIsVisible(key: InvoiceColumnKey): boolean {
  return visibleInvoiceColumns.value.includes(key)
}

function clampColumnWidth(key: InvoiceColumnKey, width: number): number {
  const config = invoiceColumnConfig[key]
  return Math.min(config.max, Math.max(config.min, width))
}

function setColumnWidth(key: InvoiceColumnKey, width: number) {
  columnWidths.value[key] = clampColumnWidth(key, Math.round(width))
}

function finishColumnResize(event?: PointerEvent) {
  const resize = activeColumnResize
  if (!resize || (event && event.pointerId !== resize.pointerId)) return
  if (resize.handle.hasPointerCapture(resize.pointerId)) {
    resize.handle.releasePointerCapture(resize.pointerId)
  }
  document.body.style.cursor = resize.previousCursor
  document.body.style.userSelect = resize.previousUserSelect
  activeColumnResize = null
}

function startColumnResize(key: InvoiceColumnKey, event: PointerEvent) {
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

function resizeColumnBy(key: InvoiceColumnKey, delta: number) {
  setColumnWidth(key, columnWidths.value[key] + delta)
}

function handleOutsideClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('[data-invoice-column-picker]')) {
    columnsOpen.value = false
  }
}

const currencyOptions = computed(() => [
  { value: 'ALL', label: t('quotation.sales.filters.allCurrencies') },
  ...currencies.value.map((currency) => ({
    value: currency,
    label: currency,
  })),
])
const invoiceContactOptions = computed(() => [
  {
    value: 'ALL',
    label: t('quotation.sales.filters.allInvoiceContacts'),
  },
  ...Array.from(
    new Set(invoiceContacts.value.map((contact) => contact.name).filter(Boolean)),
  ).map((name) => ({ value: name, label: name })),
])
const selectedContactFacet = computed(() => {
  if (selectedInvoiceContact.value === 'ALL') return null
  return (
    invoiceContacts.value.find(
      (contact) => contact.name === selectedInvoiceContact.value,
    ) || null
  )
})

const hasActiveFilters = computed(() =>
  search.value.trim() !== ''
  || selectedCurrency.value !== 'ALL'
  || selectedInvoiceContact.value !== 'ALL'
  || invoiceFrom.value !== ''
  || invoiceTo.value !== '',
)
const rangeStart = computed(() =>
  total.value ? (page.value - 1) * pageSize.value + 1 : 0,
)
const rangeEnd = computed(() =>
  Math.min(page.value * pageSize.value, total.value),
)
const pageNumbers = computed(() => {
  if (totalPages.value <= 5) {
    return Array.from({ length: totalPages.value }, (_, index) => index + 1)
  }
  const start = Math.max(
    1,
    Math.min(page.value - 2, totalPages.value - 4),
  )
  return Array.from({ length: 5 }, (_, index) => start + index)
})

function formatAmount(invoice: InvoiceRecord): string {
  if (!invoice.currency) return invoice.total_amount || '—'
  return new Intl.NumberFormat(locale.value, {
    style: 'currency',
    currency: invoice.currency,
    currencyDisplay: 'narrowSymbol',
  }).format(Number(invoice.total_amount || 0))
}

async function loadInvoices(requestedPage = page.value) {
  loading.value = true
  error.value = ''
  try {
    const result = await listInvoices({
      search: search.value.trim() || undefined,
      invoiceContact: selectedContactFacet.value?.name,
      invoiceContactEmail: undefined,
      currency:
        selectedCurrency.value === 'ALL'
          ? undefined
          : selectedCurrency.value,
      invoiceFrom: invoiceFrom.value || undefined,
      invoiceTo: invoiceTo.value || undefined,
      page: requestedPage,
      pageSize: pageSize.value,
    })
    invoices.value = result.items
    invoiceContacts.value = result.invoiceContacts
    page.value = result.page
    pageSize.value = result.pageSize
    total.value = result.total
    totalPages.value = result.totalPages
    currencies.value = result.currencies
  } catch (loadError: unknown) {
    error.value =
      loadError instanceof Error
        ? loadError.message
        : t('quotation.sales.loadInvoicesFailed')
  } finally {
    loading.value = false
  }
}

async function resetFilters() {
  suppressFilterWatch = true
  search.value = ''
  selectedCurrency.value = 'ALL'
  selectedInvoiceContact.value = 'ALL'
  invoiceFrom.value = ''
  invoiceTo.value = ''
  page.value = 1
  await nextTick()
  suppressFilterWatch = false
  await loadInvoices()
}

async function handleDownload(invoice: InvoiceRecord) {
  error.value = ''
  downloadingId.value = invoice.id
  try {
    await downloadInvoicePdf(invoice.id, invoice.invoice_no)
  } catch (downloadError: unknown) {
    error.value =
      downloadError instanceof Error
        ? downloadError.message
        : t('quotation.sales.downloadPdfFailed')
  } finally {
    downloadingId.value = ''
  }
}

async function handleEdit(invoice: InvoiceRecord) {
  await router.push(`/quotation/sales/invoices/${invoice.id}/edit`)
}

async function handleCopy(invoice: InvoiceRecord) {
  await router.push({
    path: '/quotation/sales/create',
    query: { copy: invoice.id },
  })
}

async function handleIssue(invoice: InvoiceRecord) {
  issuingId.value = invoice.id
  error.value = ''
  try {
    const updated = await updateInvoice(invoice.id, {
      status: InvoiceStatus.ISSUED,
    })
    const index = invoices.value.findIndex((item) => item.id === invoice.id)
    if (index >= 0) invoices.value[index] = updated
  } catch (issueError: unknown) {
    error.value =
      issueError instanceof Error
        ? issueError.message
        : t('quotation.sales.detail.issueFailed')
  } finally {
    issuingId.value = ''
  }
}

async function openUploadDialog(invoice: InvoiceRecord) {
  error.value = ''
  uploadInvoice.value = invoice
  folderPickerOpen.value = true
}

async function handleFolderSelected(folder: { token: string; name: string }) {
  const invoice = uploadInvoice.value
  folderPickerOpen.value = false
  uploadInvoice.value = null
  if (!invoice) return
  uploadingId.value = invoice.id
  error.value = ''
  try {
    const updated = await uploadInvoiceToFeishu(
      invoice.id,
      folder.token,
    )
    const index = invoices.value.findIndex((item) => item.id === invoice.id)
    if (index >= 0) invoices.value[index] = updated
  } catch (uploadError: unknown) {
    error.value =
      uploadError instanceof Error
        ? uploadError.message
        : t('quotation.sales.uploadToFeishuFailed')
  } finally {
    uploadingId.value = ''
  }
}

function handleFolderPickerToast(message: string) {
  error.value = message
}

async function handleDelete(invoice: InvoiceRecord) {
  if (!window.confirm(t('quotation.sales.deleteConfirm'))) return
  deletingId.value = invoice.id
  error.value = ''
  try {
    await deleteInvoice(invoice.id)
    invoices.value = invoices.value.filter((item) => item.id !== invoice.id)
    total.value = Math.max(0, total.value - 1)
    totalPages.value = Math.max(
      1,
      Math.ceil(total.value / pageSize.value),
    )
    if (page.value > totalPages.value) await loadInvoices(totalPages.value)
  } catch (deleteError: unknown) {
    error.value =
      deleteError instanceof Error
        ? deleteError.message
        : t('quotation.sales.deleteInvoiceFailed')
  } finally {
    deletingId.value = ''
  }
}

function hasInvoiceAction(invoice: InvoiceRecord): boolean {
  const local = invoice.source_type === 'manual'
  const draft = invoice.status === InvoiceStatus.DRAFT
  return Boolean(
    invoice.feishu_url ||
    invoice.pdf_available ||
    (local && userStore.userHasInvoiceCapability('edit')) ||
    (local && draft && userStore.userHasInvoiceCapability('issue')),
  )
}

function requestPage(nextPage: number) {
  if (nextPage < 1 || nextPage > Math.max(totalPages.value, 1)) return
  void loadInvoices(nextPage)
}

function handlePageSizeChange(selectedValue: string) {
  const value = Number(selectedValue)
  if (![10, 20, 50].includes(value)) return
  pageSize.value = value as 10 | 20 | 50
  page.value = 1
  void loadInvoices(1)
}

function isNestedRowAction(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(
    target.closest('button, a, input, select, textarea, [role="button"]'),
  )
}

function openInvoiceDetails(invoice: InvoiceRecord) {
  selectedInvoiceId.value = invoice.id
}

function handleRowClick(invoice: InvoiceRecord, event: MouseEvent) {
  if (isNestedRowAction(event.target)) return
  if (event.currentTarget instanceof HTMLElement) {
    event.currentTarget.focus()
  }
  openInvoiceDetails(invoice)
}

watch(search, () => {
  if (suppressFilterWatch) return
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    void loadInvoices(1)
  }, 300)
})

watch(
  [
    selectedCurrency,
    selectedInvoiceContact,
    invoiceFrom,
    invoiceTo,
  ],
  () => {
    if (suppressFilterWatch) return
    page.value = 1
    void loadInvoices(1)
  },
)

onMounted(() => {
  document.addEventListener('mousedown', handleOutsideClick)
  void loadInvoices()
})
onBeforeUnmount(() => {
  finishColumnResize()
  document.removeEventListener('mousedown', handleOutsideClick)
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
    <section class="dm-card overflow-visible">
      <div class="border-b border-dm-border-light p-3" data-invoice-filters>
        <div class="grid grid-cols-1 items-end gap-2 md:grid-cols-2 xl:grid-cols-[minmax(15rem,1.4fr)_minmax(10rem,.8fr)_minmax(12rem,1fr)_minmax(18rem,1.4fr)]">
          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.sales.filters.keyword') }}
            </label>
            <div class="relative">
              <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
              <input
                v-model="search"
                type="search"
                class="dm-input h-9 w-full py-1.5 !pl-9 !pr-9 text-sm"
                :placeholder="t('quotation.sales.searchInvoices')"
              />
              <button
                v-if="search"
                type="button"
                class="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-dm-text-tertiary hover:bg-slate-100"
                :aria-label="t('quotation.sales.filters.clearSearch')"
                @click="search = ''"
              >
                <X class="h-4 w-4" />
              </button>
            </div>
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.sales.fields.currency') }}
            </label>
            <FormSelect
              v-model="selectedCurrency"
              :options="currencyOptions"
              :trigger-class-name="FORM_SELECT_COMPACT_TRIGGER_CLASS"
            />
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.sales.filters.invoiceContact') }}
            </label>
            <FormSelect
              v-model="selectedInvoiceContact"
              :options="invoiceContactOptions"
              :trigger-class-name="FORM_SELECT_COMPACT_TRIGGER_CLASS"
            />
          </div>

          <div class="min-w-0">
            <label class="mb-1 block truncate text-xs font-medium text-dm-text-tertiary">
              {{ t('quotation.sales.filters.invoiceDate') }}
            </label>
            <div class="grid min-w-0 grid-cols-2 gap-1.5">
              <BaseDatePicker
                v-model="invoiceFrom"
                :placeholder="t('quotation.sales.filters.from')"
                input-class="dm-input h-9 w-full px-3 py-1.5 text-sm"
              />
              <BaseDatePicker
                v-model="invoiceTo"
                :placeholder="t('quotation.sales.filters.to')"
                input-class="dm-input h-9 w-full px-3 py-1.5 text-sm"
              />
            </div>
          </div>
        </div>
        <div class="mt-2 flex items-center justify-between gap-2 border-t border-slate-100 pt-2">
          <p class="text-xs font-semibold text-dm-text-tertiary">
            {{ t('quotation.sales.invoiceCount', { count: total }) }}
          </p>
          <div class="flex items-center gap-1">
            <div class="relative" data-invoice-column-picker>
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-dm-border-light bg-white px-2.5 text-xs font-semibold text-dm-text hover:bg-slate-50"
                @click.stop="columnsOpen = !columnsOpen"
              >
                <Columns3 class="h-3.5 w-3.5" />
                {{ t('quotation.pages.list.visibleColumns') }}
              </button>
              <div
                v-if="columnsOpen"
                class="absolute right-0 top-9 z-30 max-h-80 w-60 overflow-y-auto rounded-lg border border-dm-border-light bg-white p-2 shadow-xl"
              >
                <p class="px-2 py-1 text-xs font-bold text-dm-text">
                  {{ t('quotation.sales.fields.chooseFields') }}
                </p>
                <label
                  v-for="column in invoiceColumns"
                  :key="column.key"
                  class="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-xs text-dm-text-secondary hover:bg-slate-50"
                >
                  <input
                    v-model="visibleInvoiceColumns"
                    type="checkbox"
                    :value="column.key"
                    class="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-200"
                  />
                  {{ column.label }}
                </label>
                <button
                  type="button"
                  class="mt-1 w-full border-t border-slate-100 px-2 pt-2 text-left text-xs font-semibold text-blue-600 hover:text-blue-700"
                  @click="visibleInvoiceColumns = [...defaultInvoiceColumns]"
                >
                  {{ t('quotation.pages.list.resetColumns') }}
                </button>
              </div>
            </div>
            <button
              type="button"
              :class="[
                'inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold',
                hasActiveFilters
                  ? 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  : 'text-dm-text-tertiary hover:bg-slate-50',
              ]"
              @click="resetFilters"
            >
              <RotateCcw class="h-3.5 w-3.5" />
              {{ t('quotation.actions.resetFilters') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="error" class="m-4 rounded-dm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {{ error }}
      </div>
      <div
        v-if="loading"
        class="flex min-h-64 items-center justify-center text-sm text-dm-text-tertiary"
      >
        {{ t('quotation.sales.loading') }}
      </div>
      <div
        v-else-if="invoices.length === 0"
        class="flex min-h-64 flex-col items-center justify-center gap-2 text-center"
      >
        <FileText class="h-8 w-8 text-dm-text-tertiary" />
        <p class="text-sm font-medium text-dm-text">
          {{ t('quotation.sales.noInvoices') }}
        </p>
        <p class="text-sm text-dm-text-tertiary">
          {{ t('quotation.sales.noInvoicesHint') }}
        </p>
      </div>
      <div v-else class="invoice-table-scroll overflow-x-auto">
        <table
          class="dm-table w-full table-fixed"
          :style="{
            width: '100%',
            minWidth: `${invoiceTableWidth}px`,
          }"
        >
          <colgroup>
            <col
              v-for="column in visibleColumns"
              :key="column.key"
              :data-column-key="column.key"
              :style="{ width: `${columnWidths[column.key]}px` }"
            />
            <col :style="{ width: `${ACTIONS_COLUMN_WIDTH}px` }" />
          </colgroup>
          <thead>
            <tr>
              <th
                v-for="column in visibleColumns"
                :key="column.key"
                class="relative"
                :class="{ '!text-right': column.key === 'total' }"
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
                  :aria-valuemin="column.min"
                  :aria-valuemax="column.max"
                  :aria-valuenow="columnWidths[column.key]"
                  :title="t('quotation.pages.list.resizeColumnHint')"
                  tabindex="0"
                  class="group absolute right-0 top-0 z-10 flex h-full w-3 cursor-col-resize touch-none select-none items-center justify-center focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-blue-400"
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
              <th class="!text-right">{{ t('quotation.sales.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="invoice in invoices"
              :key="invoice.id"
              tabindex="0"
              class="cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-inset focus:ring-blue-200"
              @click="handleRowClick(invoice, $event)"
              @keydown.enter="openInvoiceDetails(invoice)"
              @keydown.space.prevent="openInvoiceDetails(invoice)"
            >
              <td
                v-if="columnIsVisible('invoiceNo')"
                class="truncate font-medium text-dm-primary"
              >
                <span class="inline-flex min-w-0 items-center gap-1.5">
                  <span class="truncate">{{ invoice.invoice_no || '—' }}</span>
                  <span
                    v-if="
                      invoice.status === InvoiceStatus.DRAFT &&
                      invoice.source_type === 'manual'
                    "
                    class="shrink-0 rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700"
                  >
                    {{ t('quotation.sales.statuses.draft') }}
                  </span>
                </span>
              </td>
              <td v-if="columnIsVisible('documentKind')">
                {{ t(`quotation.sales.documentKinds.${invoice.document_kind}`) }}
              </td>
              <td
                v-if="columnIsVisible('invoiceDate')"
                class="whitespace-nowrap"
              >
                {{ invoice.invoice_date || '—' }}
              </td>
              <td v-if="columnIsVisible('customer')" class="truncate">
                {{ invoice.customer_name || '—' }}
              </td>
              <td
                v-if="columnIsVisible('customerContactPerson')"
                class="truncate"
              >
                {{ invoice.customer_contact_person || '—' }}
              </td>
              <td v-if="columnIsVisible('contactPerson')" class="truncate">
                {{ invoice.contact_person || '—' }}
              </td>
              <td v-if="columnIsVisible('contactEmail')" class="truncate">
                {{ invoice.contact_email || '—' }}
              </td>
              <td v-if="columnIsVisible('customerAddress')" class="truncate">
                {{ invoice.customer_address || '—' }}
              </td>
              <td v-if="columnIsVisible('purchaseOrder')" class="truncate">
                {{ invoice.purchase_order_no || '—' }}
              </td>
              <td v-if="columnIsVisible('source')">
                {{ t(`quotation.sales.sources.${invoice.source_type}`) }}
              </td>
              <td v-if="columnIsVisible('currency')">
                {{ invoice.currency }}
              </td>
              <td
                v-if="columnIsVisible('total')"
                class="text-right font-medium tabular-nums"
              >
                {{ formatAmount(invoice) }}
              </td>
              <td class="text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    v-if="
                      invoice.source_type === 'manual' &&
                      ([
                        InvoiceStatus.DRAFT,
                        InvoiceStatus.ISSUED,
                        InvoiceStatus.PAID,
                      ] as string[]).includes(invoice.status) &&
                      userStore.userHasInvoiceCapability('edit')
                    "
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-dm-primary-bg hover:text-dm-primary"
                    :aria-label="t('quotation.sales.editInvoice')"
                    :title="t('quotation.sales.editInvoice')"
                    @click.stop="handleEdit(invoice)"
                  >
                    <Pencil class="h-4 w-4" />
                  </button>
                  <button
                    v-if="
                      invoice.source_type === 'manual' &&
                      userStore.userHasInvoiceCapability('edit')
                    "
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-blue-50 hover:text-blue-600"
                    :aria-label="t('quotation.sales.copyInvoice')"
                    :title="t('quotation.sales.copyInvoice')"
                    @click.stop="handleCopy(invoice)"
                  >
                    <Copy class="h-4 w-4" />
                  </button>
                  <button
                    v-if="
                      invoice.source_type === 'manual' &&
                      invoice.status === InvoiceStatus.DRAFT &&
                      userStore.userHasInvoiceCapability('issue')
                    "
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-indigo-50 hover:text-indigo-600 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="issuingId === invoice.id"
                    :aria-label="t('quotation.sales.create.generateAndIssue')"
                    :title="t('quotation.sales.create.generateAndIssue')"
                    @click.stop="handleIssue(invoice)"
                  >
                    <FileCheck2 class="h-4 w-4" />
                  </button>
                  <button
                    v-if="
                      invoice.source_type === 'manual' &&
                      !invoice.feishu_url &&
                      invoice.pdf_available &&
                      ([InvoiceStatus.ISSUED, InvoiceStatus.PAID] as string[]).includes(invoice.status) &&
                      userStore.userHasInvoiceCapability('issue')
                    "
                    type="button"
                    class="inline-flex h-8 w-8 items-center justify-center rounded-md text-dm-text-tertiary transition hover:bg-blue-50 hover:text-dm-primary disabled:opacity-50"
                    :disabled="uploadingId === invoice.id"
                    :aria-label="t('quotation.sales.uploadToFeishu')"
                    :title="t('quotation.sales.uploadToFeishu')"
                    @click.stop="openUploadDialog(invoice)"
                  >
                    <Upload class="h-4 w-4" />
                  </button>
                  <button
                    v-if="
                      invoice.source_type === 'manual' &&
                      userStore.userHasInvoiceCapability('edit')
                    "
                    type="button"
                    class="inline-flex h-8 w-8 items-center justify-center rounded-md text-dm-text-tertiary transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    :disabled="deletingId === invoice.id"
                    :aria-label="t('quotation.sales.deleteInvoice')"
                    :title="t('quotation.sales.deleteInvoice')"
                    @click.stop="handleDelete(invoice)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                  <a
                    v-if="invoice.feishu_url"
                    :href="invoice.feishu_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex h-8 w-8 items-center justify-center rounded-md text-dm-text-tertiary transition hover:bg-blue-50 hover:text-dm-primary"
                    :aria-label="t('quotation.sales.openFeishu')"
                    :title="t('quotation.sales.openFeishu')"
                    @click.stop
                  >
                    <ExternalLink class="h-4 w-4" />
                  </a>
                  <button
                    v-if="invoice.pdf_available"
                    type="button"
                    class="inline-flex h-8 w-8 items-center justify-center rounded-md text-dm-primary transition hover:bg-blue-50 disabled:opacity-50"
                    :disabled="downloadingId === invoice.id"
                    :aria-label="t('quotation.sales.downloadPdf')"
                    :title="t('quotation.sales.downloadPdf')"
                    @click.stop="handleDownload(invoice)"
                  >
                    <Download class="h-4 w-4" />
                  </button>
                  <span
                    v-if="!hasInvoiceAction(invoice)"
                    class="text-dm-text-tertiary"
                  >—</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        class="flex flex-col gap-2 border-t border-dm-border-light px-3 py-2 text-sm text-dm-text-tertiary sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>{{ t('quotation.sales.paginationTotal', { count: total }) }}</span>
          <span>
            {{
              t('quotation.sales.paginationRange', {
                start: rangeStart,
                end: rangeEnd,
              })
            }}
          </span>
          <span>
            {{
              t('quotation.sales.paginationPages', {
                count: totalPages,
              })
            }}
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex items-center gap-2">
            <span>{{ t('quotation.sales.paginationPageSize') }}</span>
            <FormSelect
              :value="String(pageSize)"
              class-name="w-20"
              trigger-class-name="h-8 rounded-md border-dm-border bg-white px-2 text-sm focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              panel-class-name="!bottom-full !top-auto !mb-1 !mt-0"
              :options="pageSizeOptions"
              test-id="invoice-page-size"
              @change="handlePageSizeChange"
            />
          </label>
          <button
            type="button"
            class="h-8 rounded-md border border-dm-border px-2.5 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="page <= 1 || loading"
            @click="requestPage(page - 1)"
          >
            {{ t('quotation.sales.paginationPrevious') }}
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
            {{ t('quotation.sales.paginationNext') }}
          </button>
        </div>
      </div>
    </section>

    <InvoiceDetailsDrawer
      :invoice-id="selectedInvoiceId"
      @close="selectedInvoiceId = null"
    />

    <InvoiceFeishuFolderPickerModal
      :open="folderPickerOpen"
      :invoice-id="uploadInvoice?.id || ''"
      @update:open="folderPickerOpen = $event"
      @select="handleFolderSelected"
      @toast="handleFolderPickerToast"
    />
  </div>
</template>
