<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Building2,
  CreditCard,
  FileText,
  Landmark,
  PenLine,
  Plus,
  Save,
  Trash2,
  UserRound,
  X,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '@/store/user'

import {
  getCatalog,
  updateCatalog,
  type UserQuotationCatalog,
} from '../../api/catalog'
import {
  createInvoice,
  getInvoice,
  getInvoiceFormContext,
  InvoiceNumberingMode,
  InvoiceStatus,
  type InvoiceCreatePayload,
  type InvoiceDocumentKind,
  type InvoiceRecord,
  updateInvoice,
} from '../../api/invoices'
import type { ProductLineOption } from '../../types'
import {
  isProductLinePrefixUnique,
  isProductLinePrefixValid,
  loadProductLineOptions,
} from '../../utils/quotationNumbering'
import {
  DEFAULT_PREVIEW_WIDTH_PERCENT,
  getPreviewWidthPercentFromPointer,
} from '../../utils/resizablePreview'
import FormSelect from '../FormSelect.vue'
import HistoryTextInput, {
  type NormalizedHistoryOption,
} from '../HistoryTextInput.vue'
import SignaturePicker from '../SignaturePicker.vue'
import InvoicePreview, {
  type InvoicePreviewData,
} from './InvoicePreview.vue'

interface EditableInvoiceItem {
  id: string
  productName: string
  description: string
  quantity: number
  unitPrice: number
}

interface InvoiceItemHistory {
  invoice: InvoiceRecord
  item: InvoiceRecord['items'][number]
}

type WritableInvoiceStatus = InvoiceCreatePayload['status']

function isWritableInvoiceStatus(
  status: InvoiceStatus,
): status is WritableInvoiceStatus {
  return (
    status === InvoiceStatus.DRAFT
    || status === InvoiceStatus.ISSUED
    || status === InvoiceStatus.PAID
  )
}

const ADD_PRODUCT_LINE_OPTION = '__add_product_line__'

let itemSequence = 0

function newItem(): EditableInvoiceItem {
  itemSequence += 1
  return {
    id: `invoice-item-${itemSequence}`,
    productName: '',
    description: '',
    quantity: 1,
    unitPrice: 0,
  }
}

function todayInputValue(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const resizeContainerRef = ref<HTMLElement | null>(null)
const previewWidthPercent = ref(DEFAULT_PREVIEW_WIDTH_PERCENT)
const editingInvoiceId = computed(() =>
  route.name === 'QuoteDeskInvoiceEdit'
    ? String(route.params.invoiceId || '')
    : '',
)
const isEditing = computed(() => Boolean(editingInvoiceId.value))
const editingStatus = ref<InvoiceStatus>(InvoiceStatus.DRAFT)
const isFormalEditing = computed(
  () =>
    isEditing.value &&
    isWritableInvoiceStatus(editingStatus.value) &&
    editingStatus.value !== InvoiceStatus.DRAFT,
)
const copyInvoiceId = computed(() =>
  !isEditing.value && typeof route.query.copy === 'string'
    ? route.query.copy
    : '',
)
const catalog = ref<UserQuotationCatalog | null>(null)
const productLineOptions = ref<ProductLineOption[]>(loadProductLineOptions())
const isAddingProductLine = ref(false)
const newProductLineLabel = ref('')
const newProductLinePrefix = ref('')
const productLineError = ref('')
const historyInvoices = ref<InvoiceRecord[]>([])
const historyPage = ref(0)
const historyHasMore = ref(false)
const historyLoading = ref(false)
const selectedBankAccount = ref('')

const form = reactive({
  invoiceNumber: '',
  documentKind: 'invoice' as InvoiceDocumentKind,
  numberingMode: InvoiceNumberingMode.AUTO as InvoiceNumberingMode,
  productLine: 'BDR',
  invoiceDate: todayInputValue(),
  currency: 'USD',
  sellerName: 'OnePro Cloud Limited',
  sellerAddress: [
    'UNIT 701A, 7/F, RAILWAY PLAZA,',
    '39 CHATHAM ROAD SOUTH, TSIM SHA TSUI, HONG KONG',
  ].join('\n'),
  sellerWebsite: 'www.oneprocloud.com',
  sellerEmail: 'enquiry@oneprocloud.com',
  customerName: '',
  customerTaxId: '',
  customerAddress: '',
  customerContactPerson: '',
  customerContactEmail: '',
  contactPerson: '',
  contactEmail: '',
  purchaseOrderNo: '',
  paymentTerms: 'CIA',
  additionalNotes: '',
  remarks: '',
  bankAccountName: '',
  bankName: '',
  bankAddress: '',
  bankAccountNumber: '',
  bankCode: '',
  bankBranchCode: '',
  bankSwiftCode: '',
  remittanceInstruction: '',
  signatoryName: '',
  signatoryTitle: '',
  signature: '',
  salesOwner: '',
  items: [newItem()] as EditableInvoiceItem[],
})

const currencyOptions = ['USD', 'HKD', 'CNY', 'EUR', 'GBP', 'MYR'].map(
  (currency) => ({
    value: currency,
    label: currency,
  }),
)

const paymentTermOptions = [
  { value: 'CIA', label: 'CIA' },
  { value: 'NET15', label: 'Net 15' },
  { value: 'NET30', label: 'Net 30' },
  { value: 'NET45', label: 'Net 45' },
  { value: 'NET60', label: 'Net 60' },
]

function normalizedKey(value: string): string {
  return value.trim().toLocaleLowerCase()
}

function uniqueHistory<T>(records: T[], key: (record: T) => string): T[] {
  const seen = new Set<string>()
  return records.filter((record) => {
    const value = normalizedKey(key(record))
    if (!value || seen.has(value)) return false
    seen.add(value)
    return true
  })
}

function normalizePaymentTerm(value: string): string {
  const normalized = value.trim()
  const compact = normalized.replace(/\s+/g, '').toUpperCase()
  return paymentTermOptions.some((option) => option.value === compact)
    ? compact
    : normalized || 'CIA'
}

const customerOptions = computed(() =>
  uniqueHistory(historyInvoices.value, (invoice) => invoice.customer_name),
)

const scopedCustomerHistory = computed(() => {
  const company = normalizedKey(form.customerName)
  return company
    ? historyInvoices.value.filter(
        (invoice) => normalizedKey(invoice.customer_name) === company,
      )
    : historyInvoices.value
})

const customerContactOptions = computed(() =>
  uniqueHistory(
    scopedCustomerHistory.value,
    (invoice) =>
      `${invoice.customer_contact_person}|${invoice.customer_contact_email}`,
  ).filter((invoice) => invoice.customer_contact_person),
)

const customerEmailOptions = computed(() =>
  uniqueHistory(
    scopedCustomerHistory.value,
    (invoice) => invoice.customer_contact_email,
  ).filter((invoice) => invoice.customer_contact_email),
)

const invoiceContactOptions = computed(() =>
  uniqueHistory(
    historyInvoices.value,
    (invoice) => `${invoice.contact_person}|${invoice.contact_email}`,
  ).filter((invoice) => invoice.contact_person),
)

const invoiceContactEmailOptions = computed(() =>
  uniqueHistory(
    historyInvoices.value,
    (invoice) => invoice.contact_email,
  ).filter((invoice) => invoice.contact_email),
)

const bankHistoryOptions = computed(() =>
  uniqueHistory(
    historyInvoices.value,
    (invoice) =>
      [
        invoice.bank_account_name,
        invoice.bank_name,
        invoice.bank_address,
        invoice.bank_account_number,
        invoice.bank_code,
        invoice.bank_branch_code,
        invoice.bank_swift_code,
        invoice.remittance_instruction,
      ].join('|'),
  ).filter(
    (invoice) =>
      invoice.bank_account_name ||
      invoice.bank_name ||
      invoice.bank_account_number ||
      invoice.bank_swift_code,
  ),
)

const bankFormFieldByInvoiceField = {
  bank_account_name: 'bankAccountName',
  bank_name: 'bankName',
  bank_address: 'bankAddress',
  bank_account_number: 'bankAccountNumber',
  bank_code: 'bankCode',
  bank_branch_code: 'bankBranchCode',
  bank_swift_code: 'bankSwiftCode',
  remittance_instruction: 'remittanceInstruction',
} as const

type BankInvoiceField = keyof typeof bankFormFieldByInvoiceField

function bankFieldOptions(field: BankInvoiceField) {
  return uniqueHistory(historyInvoices.value, (invoice) => invoice[field])
    .filter((invoice) => invoice[field])
    .map((invoice) => ({
      value: invoice[field],
      label: invoice.bank_account_name || invoice.bank_name,
      key: `${invoice.id}-${field}`,
      meta: invoice,
    }))
}

const itemHistoryOptions = computed<InvoiceItemHistory[]>(() => {
  const records = historyInvoices.value.flatMap((invoice) =>
    invoice.currency === form.currency
      ? invoice.items.map((item) => ({ invoice, item }))
      : [],
  )
  return uniqueHistory(
    records,
    (record) =>
      `${record.item.product_name}|${record.item.description}|` +
      `${record.item.unit_price}`,
  ).filter(
    (record) => record.item.product_name || record.item.description,
  )
})

const productLineSelectOptions = computed(() => [
  ...productLineOptions.value.map((option) => ({
    value: option.value,
    label: `${option.label} (${option.value})`,
  })),
  {
    value: ADD_PRODUCT_LINE_OPTION,
    label: `+ ${t('quotation.pages.create.addProductLine')}`,
  },
])

async function loadProductLines() {
  try {
    catalog.value = await getCatalog()
    if (catalog.value.product_lines.length) {
      productLineOptions.value = catalog.value.product_lines
    }
  } catch (loadError: unknown) {
    error.value = responseErrorMessage(loadError)
  }
}

async function loadInvoiceHistory() {
  if (
    historyLoading.value ||
    (!historyHasMore.value && historyPage.value > 0)
  ) {
    return
  }
  historyLoading.value = true
  try {
    const result = await getInvoiceFormContext(historyPage.value + 1)
    historyInvoices.value = [...historyInvoices.value, ...result.items]
    historyPage.value = result.page
    historyHasMore.value = result.page < result.totalPages
  } catch {
    historyHasMore.value = false
  } finally {
    historyLoading.value = false
  }
}

function applyCustomerHistory(invoice: InvoiceRecord) {
  form.customerName = invoice.customer_name
  form.customerTaxId = invoice.customer_tax_id
  form.customerAddress = invoice.customer_address
  form.customerContactPerson = invoice.customer_contact_person
  form.customerContactEmail = invoice.customer_contact_email
  if (currencyOptions.some((option) => option.value === invoice.currency)) {
    form.currency = invoice.currency
  }
  form.paymentTerms = normalizePaymentTerm(invoice.payment_terms)
}

function handleCustomerSelect(option: NormalizedHistoryOption) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (invoice) applyCustomerHistory(invoice)
}

function handleCustomerContactSelect(option: NormalizedHistoryOption) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (!invoice) return
  form.customerContactPerson = invoice.customer_contact_person
  form.customerContactEmail = invoice.customer_contact_email
  if (!form.customerName.trim()) applyCustomerHistory(invoice)
}

function handleCustomerEmailSelect(option: NormalizedHistoryOption) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (!invoice) return
  form.customerContactEmail = invoice.customer_contact_email
  form.customerContactPerson = invoice.customer_contact_person
  if (!form.customerName.trim()) applyCustomerHistory(invoice)
}

function handleInvoiceContactSelect(option: NormalizedHistoryOption) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (!invoice) return
  form.contactPerson = invoice.contact_person
  form.contactEmail = invoice.contact_email
}

function handleInvoiceContactEmailSelect(option: NormalizedHistoryOption) {
  handleInvoiceContactSelect(option)
}

function handleBankHistorySelect(option: NormalizedHistoryOption) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (!invoice) return
  selectedBankAccount.value = invoice.bank_name || invoice.bank_account_name
  form.bankAccountName = invoice.bank_account_name
  form.bankName = invoice.bank_name
  form.bankAddress = invoice.bank_address
  form.bankAccountNumber = invoice.bank_account_number
  form.bankCode = invoice.bank_code
  form.bankBranchCode = invoice.bank_branch_code
  form.bankSwiftCode = invoice.bank_swift_code
  form.remittanceInstruction = invoice.remittance_instruction
}

function handleBankFieldHistorySelect(
  field: BankInvoiceField,
  option: NormalizedHistoryOption,
) {
  const invoice = option.meta as InvoiceRecord | undefined
  if (!invoice) return
  form[bankFormFieldByInvoiceField[field]] = invoice[field]
}

function handleItemDescriptionSelect(
  item: EditableInvoiceItem,
  option: NormalizedHistoryOption,
) {
  const history = option.meta as InvoiceItemHistory | undefined
  if (!history) return
  item.productName = history.item.product_name
  item.description = history.item.description
  item.unitPrice = Number(history.item.unit_price)
}

function handleProductLineChange(value: string) {
  if (value === ADD_PRODUCT_LINE_OPTION) {
    isAddingProductLine.value = true
    return
  }
  form.productLine = value
}

async function handleAddProductLine() {
  const currentCatalog = catalog.value
  const label = newProductLineLabel.value.trim()
  const prefix = newProductLinePrefix.value.trim()
  if (!label) {
    productLineError.value = t(
      'quotation.pages.create.errors.productLineNameRequired',
    )
    return
  }
  if (!isProductLinePrefixValid(prefix)) {
    productLineError.value = t(
      'quotation.pages.create.errors.productLinePrefixInvalid',
    )
    return
  }
  if (!isProductLinePrefixUnique(prefix, productLineOptions.value)) {
    productLineError.value = t(
      'quotation.pages.create.errors.productLinePrefixDuplicate',
    )
    return
  }
  if (!currentCatalog) {
    productLineError.value = t('quotation.sales.create.catalogUnavailable')
    return
  }
  try {
    const updated = await updateCatalog({
      version: currentCatalog.version,
      products: currentCatalog.products,
      services: currentCatalog.services,
      discounts: currentCatalog.discounts,
      product_lines: [
        ...productLineOptions.value,
        { value: prefix, label },
      ],
      payment_terms: currentCatalog.payment_terms,
    })
    catalog.value = updated
    productLineOptions.value = updated.product_lines
    form.productLine = prefix
    newProductLineLabel.value = ''
    newProductLinePrefix.value = ''
    productLineError.value = ''
    isAddingProductLine.value = false
  } catch (saveError: unknown) {
    productLineError.value = responseErrorMessage(saveError)
  }
}

const userEmail = computed(() =>
  String(userStore.user?.email || userStore.user?.username || ''),
)

const previewInvoice = computed<InvoicePreviewData>(() => ({
  invoiceNumber: form.invoiceNumber,
  documentKind: form.documentKind,
  invoiceDate: form.invoiceDate,
  currency: form.currency,
  sellerName: form.sellerName,
  sellerAddress: form.sellerAddress,
  sellerWebsite: form.sellerWebsite,
  sellerEmail: form.sellerEmail,
  customerName: form.customerName,
  customerTaxId: form.customerTaxId,
  customerAddress: form.customerAddress,
  customerContactPerson: form.customerContactPerson,
  customerContactEmail: form.customerContactEmail,
  customerContactPhone: '',
  contactPerson: form.contactPerson,
  contactEmail: form.contactEmail,
  purchaseOrderNo: form.purchaseOrderNo,
  paymentTerms: form.paymentTerms,
  additionalNotes: form.additionalNotes,
  remarks: form.remarks,
  bankAccountName: form.bankAccountName,
  bankName: form.bankName,
  bankAddress: form.bankAddress,
  bankAccountNumber: form.bankAccountNumber,
  bankCode: form.bankCode,
  bankBranchCode: form.bankBranchCode,
  bankSwiftCode: form.bankSwiftCode,
  remittanceInstruction: form.remittanceInstruction,
  signatoryName: form.signatoryName,
  signatoryTitle: form.signatoryTitle,
  signature: form.signature,
  items: form.items.map((item) => ({
    id: item.id,
    description: item.description,
    quantity: Number(item.quantity || 0),
    unitPrice: Number(item.unitPrice || 0),
  })),
}))

const totalAmount = computed(() =>
  form.items.reduce(
    (total, item) => total + Number(item.quantity) * Number(item.unitPrice),
    0,
  ),
)

function formatEditorAmount(value: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0)
}

function addItem() {
  form.items.push(newItem())
}

function removeItem(index: number) {
  if (form.items.length === 1) {
    form.items[0] = newItem()
    return
  }
  form.items.splice(index, 1)
}

function handleResizeStart(event: PointerEvent) {
  event.preventDefault()
  const container = resizeContainerRef.value
  if (!container) return

  const updatePreviewWidth = (pointerEvent: PointerEvent) => {
    const rect = container.getBoundingClientRect()
    previewWidthPercent.value = getPreviewWidthPercentFromPointer({
      containerLeft: rect.left,
      containerWidth: rect.width,
      pointerClientX: pointerEvent.clientX,
    })
  }

  const stopResize = () => {
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('pointermove', updatePreviewWidth)
    window.removeEventListener('pointerup', stopResize)
  }

  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  updatePreviewWidth(event)
  window.addEventListener('pointermove', updatePreviewWidth)
  window.addEventListener('pointerup', stopResize)
}

function payload(status: WritableInvoiceStatus): InvoiceCreatePayload {
  const items = form.items
    .filter((item) => item.description.trim())
    .map((item, index) => ({
      line_no: index + 1,
      product_name: item.productName.trim() || item.description.trim(),
      description: item.description.trim(),
      quantity: Number(item.quantity),
      unit_price: Number(item.unitPrice),
    }))
  return {
    invoice_no:
      form.numberingMode === InvoiceNumberingMode.AUTO
        ? ''
        : form.invoiceNumber.trim(),
    numbering_mode: form.numberingMode,
    product_line: form.productLine,
    invoice_date: form.invoiceDate,
    status,
    currency: form.currency,
    seller_name: form.sellerName.trim(),
    seller_tax_id: '',
    seller_address: form.sellerAddress.trim(),
    seller_website: form.sellerWebsite.trim(),
    seller_email: form.sellerEmail.trim(),
    customer_name: form.customerName.trim(),
    customer_tax_id: form.customerTaxId.trim(),
    customer_address: form.customerAddress.trim(),
    customer_contact_person: form.customerContactPerson.trim(),
    customer_contact_email: form.customerContactEmail.trim(),
    contact_person: form.contactPerson.trim(),
    contact_email: form.contactEmail.trim(),
    purchase_order_no: form.purchaseOrderNo.trim(),
    payment_terms: form.paymentTerms,
    region: '',
    sales_owner: form.salesOwner.trim(),
    tax_rate: '0',
    additional_notes: form.additionalNotes.trim(),
    remarks: form.remarks.trim(),
    bank_account_name: form.bankAccountName.trim(),
    bank_name: form.bankName.trim(),
    bank_address: form.bankAddress.trim(),
    bank_account_number: form.bankAccountNumber.trim(),
    bank_code: form.bankCode.trim(),
    bank_branch_code: form.bankBranchCode.trim(),
    bank_swift_code: form.bankSwiftCode.trim(),
    remittance_instruction: form.remittanceInstruction.trim(),
    signatory_name: form.signatoryName.trim(),
    signatory_title: form.signatoryTitle.trim(),
    issuer_signature: form.signature,
    items,
  }
}

function validateForm(status: WritableInvoiceStatus): boolean {
  const customNumberMissing =
    form.numberingMode === InvoiceNumberingMode.CUSTOM &&
    !form.invoiceNumber.trim()
  if (customNumberMissing || !form.invoiceDate || !form.customerName.trim()) {
    error.value = t('quotation.sales.create.requiredFields')
    return false
  }
  const completeItems = form.items.filter((item) => item.description.trim())
  if (status === InvoiceStatus.ISSUED && completeItems.length === 0) {
    error.value = t('quotation.sales.create.itemRequired')
    return false
  }
  if (
    completeItems.some(
      (item) => Number(item.quantity) <= 0 || Number(item.unitPrice) < 0,
    )
  ) {
    error.value = t('quotation.sales.create.invalidItemAmount')
    return false
  }
  return true
}

function responseErrorMessage(submitError: unknown): string {
  const responseData = (
    submitError as { response?: { data?: Record<string, unknown> } }
  )?.response?.data
  const errorData = responseData?.data
    && typeof responseData.data === 'object'
    ? responseData.data as Record<string, unknown>
    : responseData
  if (errorData) {
    const firstValue = Object.values(errorData)[0]
    if (typeof firstValue === 'string') return firstValue
    if (Array.isArray(firstValue)) return String(firstValue[0] || '')
  }
  return submitError instanceof Error
    ? submitError.message
    : t('quotation.sales.create.saveFailed')
}

function populateForm(invoice: InvoiceRecord) {
  form.invoiceNumber = invoice.invoice_no
  form.documentKind = invoice.document_kind
  form.numberingMode = invoice.numbering_mode
  form.productLine = invoice.product_line || 'BDR'
  form.invoiceDate = invoice.invoice_date || ''
  form.currency = invoice.currency
  form.sellerName = invoice.seller_name
  form.sellerAddress = invoice.seller_address
  form.sellerWebsite = invoice.seller_website
  form.sellerEmail = invoice.seller_email
  form.customerName = invoice.customer_name
  form.customerTaxId = invoice.customer_tax_id
  form.customerAddress = invoice.customer_address
  form.customerContactPerson = invoice.customer_contact_person
  form.customerContactEmail = invoice.customer_contact_email
  form.contactPerson = invoice.contact_person
  form.contactEmail = invoice.contact_email
  form.purchaseOrderNo = invoice.purchase_order_no
  form.paymentTerms = normalizePaymentTerm(invoice.payment_terms)
  form.additionalNotes = invoice.additional_notes
  form.remarks = invoice.remarks
  selectedBankAccount.value = invoice.bank_name || invoice.bank_account_name
  form.bankAccountName = invoice.bank_account_name
  form.bankName = invoice.bank_name
  form.bankAddress = invoice.bank_address
  form.bankAccountNumber = invoice.bank_account_number
  form.bankCode = invoice.bank_code
  form.bankBranchCode = invoice.bank_branch_code
  form.bankSwiftCode = invoice.bank_swift_code
  form.remittanceInstruction = invoice.remittance_instruction
  form.signatoryName = invoice.signatory_name
  form.signatoryTitle = invoice.signatory_title
  form.signature = invoice.issuer_signature
  form.salesOwner = invoice.sales_owner
  form.items = invoice.items.length
    ? invoice.items.map((item) => ({
        id: item.id,
        productName: item.product_name,
        description: item.description,
        quantity: Number(item.quantity),
        unitPrice: Number(item.unit_price),
      }))
    : [newItem()]
}

async function loadDraft() {
  if (!editingInvoiceId.value) return
  loading.value = true
  error.value = ''
  try {
    const invoice = await getInvoice(editingInvoiceId.value)
    if (!isWritableInvoiceStatus(invoice.status)) {
      await router.replace(
        `/quotation/sales/invoices/${editingInvoiceId.value}`,
      )
      return
    }
    editingStatus.value = invoice.status
    populateForm(invoice)
  } catch (loadError: unknown) {
    error.value = responseErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function loadCopy() {
  if (!copyInvoiceId.value) return
  loading.value = true
  error.value = ''
  try {
    const invoice = await getInvoice(copyInvoiceId.value)
    if (invoice.source_type !== 'manual') {
      throw new Error(t('quotation.sales.create.copyLocalOnly'))
    }
    populateForm(invoice)
    form.invoiceNumber = ''
    form.numberingMode = InvoiceNumberingMode.AUTO
    form.invoiceDate = todayInputValue()
  } catch (loadError: unknown) {
    error.value = responseErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function initializeForm() {
  await Promise.all([loadProductLines(), loadInvoiceHistory()])
  if (isEditing.value) {
    await loadDraft()
    return
  }
  await loadCopy()
}

async function submit(status: InvoiceStatus) {
  if (submitting.value) return
  error.value = ''
  const effectiveStatus: WritableInvoiceStatus =
    isFormalEditing.value && isWritableInvoiceStatus(editingStatus.value)
      ? editingStatus.value
      : isWritableInvoiceStatus(status)
        ? status
        : InvoiceStatus.DRAFT
  if (!validateForm(effectiveStatus)) return
  submitting.value = true
  try {
    const invoice = isEditing.value
      ? await updateInvoice(editingInvoiceId.value, payload(effectiveStatus))
      : await createInvoice(payload(effectiveStatus))
    if (effectiveStatus !== InvoiceStatus.DRAFT) {
      await router.push(`/quotation/sales/invoices/${invoice.id}`)
    } else {
      await router.push({
        path: '/quotation/sales/invoices',
        query: { saved: effectiveStatus },
      })
    }
  } catch (submitError: unknown) {
    error.value = responseErrorMessage(submitError)
  } finally {
    submitting.value = false
  }
}

onMounted(initializeForm)
</script>

<template>
  <div class="mx-auto w-full max-w-[1680px] space-y-5">
    <header class="dm-card flex flex-wrap items-start justify-between gap-4 p-5">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wider text-dm-primary">
          {{ t('quotation.sales.section') }}
        </p>
        <h1 class="mt-1 text-base font-bold text-dm-text">
          {{
            t(
              isEditing
                ? 'quotation.sales.create.editTitle'
                : 'quotation.sales.create.title',
            )
          }}
        </h1>
        <p class="mt-1 text-sm text-dm-text-tertiary">
          {{
            t(
              isEditing
                ? 'quotation.sales.create.editSubtitle'
                : 'quotation.sales.create.subtitle',
            )
          }}
        </p>
      </div>
      <button
        type="button"
        class="dm-btn-default px-3 py-2 text-sm"
        @click="router.push('/quotation/sales/invoices')"
      >
        {{ t('quotation.sales.create.cancel') }}
      </button>
    </header>

    <p
      v-if="error"
      class="rounded-dm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      role="alert"
    >
      {{ error }}
    </p>

    <div
      v-if="loading"
      class="dm-card flex min-h-64 items-center justify-center text-sm text-dm-text-tertiary"
    >
      {{ t('quotation.sales.loading') }}
    </div>

    <div
      v-else
      ref="resizeContainerRef"
      class="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-0"
    >
      <form
        class="space-y-5 xl:min-w-[390px] xl:basis-[calc(var(--form-width)-8px)] xl:pr-3"
        :style="{ '--form-width': `${100 - previewWidthPercent}%` }"
        @submit.prevent
      >
        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <FileText class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.invoiceInformation') }}</h2>
            <span>
              {{ t(`quotation.sales.statuses.${editingStatus}`) }}
            </span>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.numberingMode') }}</span>
              <div class="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  class="rounded-lg border p-2 text-sm font-semibold transition"
                  :class="
                    form.numberingMode === InvoiceNumberingMode.AUTO
                      ? 'border-blue-500 bg-dm-primary-bg text-dm-primary'
                      : 'border-dm-border bg-white text-dm-text-secondary hover:bg-slate-50'
                  "
                  :disabled="isEditing"
                  @click="form.numberingMode = InvoiceNumberingMode.AUTO"
                >
                  {{ t('quotation.sales.create.numberingAuto') }}
                </button>
                <button
                  type="button"
                  class="rounded-lg border p-2 text-sm font-semibold transition"
                  :class="
                    form.numberingMode === InvoiceNumberingMode.CUSTOM
                      ? 'border-blue-500 bg-dm-primary-bg text-dm-primary'
                      : 'border-dm-border bg-white text-dm-text-secondary hover:bg-slate-50'
                  "
                  :disabled="isEditing"
                  @click="form.numberingMode = InvoiceNumberingMode.CUSTOM"
                >
                  {{ t('quotation.sales.create.numberingCustom') }}
                </button>
              </div>
            </div>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.pages.create.productLine') }}</span>
              <FormSelect
                :value="form.productLine"
                :options="productLineSelectOptions"
                class-name="w-full"
                trigger-class-name="dm-input"
                @change="handleProductLineChange"
              />
            </label>
            <div
              v-if="isAddingProductLine"
              class="space-y-3 rounded-lg border border-blue-300 bg-blue-50 p-3 sm:col-span-2"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm font-semibold text-dm-primary">
                  {{ t('quotation.pages.create.addProductLine') }}
                </span>
                <button
                  type="button"
                  :aria-label="t('quotation.pages.create.closeAddProductLine')"
                  class="inline-flex h-7 w-7 items-center justify-center rounded-md text-dm-text-tertiary hover:bg-white"
                  @click="isAddingProductLine = false"
                >
                  <X class="h-4 w-4" />
                </button>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <label class="invoice-field">
                  <span>{{ t('quotation.pages.create.productLineName') }}</span>
                  <input
                    v-model="newProductLineLabel"
                    class="dm-input"
                    type="text"
                    :placeholder="t('quotation.pages.create.productLineNamePlaceholder')"
                  />
                </label>
                <label class="invoice-field">
                  <span>{{ t('quotation.pages.create.productLinePrefix') }}</span>
                  <input
                    v-model="newProductLinePrefix"
                    class="dm-input font-mono"
                    type="text"
                    :placeholder="t('quotation.pages.create.productLinePrefixPlaceholder')"
                  />
                </label>
              </div>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <small
                  :class="productLineError ? 'text-red-600' : 'text-dm-text-tertiary'"
                >
                  {{ productLineError || t('quotation.sales.create.productLineRule') }}
                </small>
                <button
                  type="button"
                  class="dm-btn-primary px-3 py-2 text-sm"
                  @click="handleAddProductLine"
                >
                  {{ t('quotation.actions.saveProductLine') }}
                </button>
              </div>
            </div>
            <label class="invoice-field">
              <span>
                {{ t('quotation.sales.create.invoiceNumber') }}
                <template
                  v-if="form.numberingMode === InvoiceNumberingMode.CUSTOM"
                >*</template>
              </span>
              <input
                v-model="form.invoiceNumber"
                class="dm-input font-mono"
                type="text"
                :placeholder="
                  form.numberingMode === InvoiceNumberingMode.AUTO
                    ? t('quotation.sales.create.autoNumberPlaceholder')
                    : t('quotation.sales.create.customNumberPlaceholder')
                "
                :readonly="form.numberingMode === InvoiceNumberingMode.AUTO"
              />
              <small class="text-xs font-normal text-dm-text-tertiary">
                {{
                  t(
                    form.numberingMode === InvoiceNumberingMode.AUTO
                      ? 'quotation.sales.create.autoNumberHint'
                      : 'quotation.sales.create.customNumberHint',
                  )
                }}
              </small>
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.invoiceDate') }} *</span>
              <input v-model="form.invoiceDate" class="dm-input" type="date" />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.template') }}</span>
              <input
                class="dm-input bg-slate-50 text-dm-text-tertiary"
                type="text"
                value="English Commercial Invoice"
                readonly
              />
            </label>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <Building2 class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.seller') }}</h2>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.companyName') }}</span>
              <input v-model="form.sellerName" class="dm-input" type="text" />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.address') }}</span>
              <textarea v-model="form.sellerAddress" class="dm-input min-h-20" />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.website') }}</span>
              <input v-model="form.sellerWebsite" class="dm-input" type="text" />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.enquiryEmail') }}</span>
              <input v-model="form.sellerEmail" class="dm-input" type="email" />
            </label>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <UserRound class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.billTo') }}</h2>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.companyName') }} *</span>
              <HistoryTextInput
                v-model="form.customerName"
                test-id="invoice-customer-company"
                :options="customerOptions.map((invoice) => ({
                  value: invoice.customer_name,
                  label: invoice.customer_contact_person,
                  key: invoice.customer_name,
                  meta: invoice,
                }))"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="handleCustomerSelect"
                @load-more="loadInvoiceHistory"
              />
            </div>
            <div class="invoice-field">
              <span>{{ t('quotation.sales.create.customerContactPerson') }}</span>
              <HistoryTextInput
                v-model="form.customerContactPerson"
                test-id="invoice-customer-contact"
                :options="customerContactOptions.map((invoice) => ({
                  value: invoice.customer_contact_person,
                  label: invoice.customer_contact_email,
                  key: `${invoice.id}-customer-contact`,
                  meta: invoice,
                }))"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="handleCustomerContactSelect"
                @load-more="loadInvoiceHistory"
              />
            </div>
            <div class="invoice-field">
              <span>{{ t('quotation.sales.create.customerContactEmail') }}</span>
              <HistoryTextInput
                v-model="form.customerContactEmail"
                test-id="invoice-customer-email"
                type="email"
                :options="customerEmailOptions.map((invoice) => ({
                  value: invoice.customer_contact_email,
                  label: invoice.customer_contact_person,
                  key: `${invoice.id}-customer-email`,
                  meta: invoice,
                }))"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="handleCustomerEmailSelect"
                @load-more="loadInvoiceHistory"
              />
            </div>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.vatNumber') }}</span>
              <input v-model="form.customerTaxId" class="dm-input" type="text" />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.address') }}</span>
              <textarea v-model="form.customerAddress" class="dm-input min-h-20" />
            </label>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <CreditCard class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.contactAndPayment') }}</h2>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="invoice-field">
              <span>{{ t('quotation.sales.create.contactPerson') }}</span>
              <HistoryTextInput
                v-model="form.contactPerson"
                test-id="invoice-contact-person"
                :options="invoiceContactOptions.map((invoice) => ({
                  value: invoice.contact_person,
                  label: invoice.contact_email,
                  key: `${invoice.id}-invoice-contact`,
                  meta: invoice,
                }))"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="handleInvoiceContactSelect"
                @load-more="loadInvoiceHistory"
              />
            </div>
            <div class="invoice-field">
              <span>{{ t('quotation.sales.create.email') }}</span>
              <HistoryTextInput
                v-model="form.contactEmail"
                test-id="invoice-contact-email"
                type="email"
                :options="invoiceContactEmailOptions.map((invoice) => ({
                  value: invoice.contact_email,
                  label: invoice.contact_person,
                  key: `${invoice.id}-invoice-email`,
                  meta: invoice,
                }))"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="handleInvoiceContactEmailSelect"
                @load-more="loadInvoiceHistory"
              />
            </div>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.purchaseOrder') }}</span>
              <input v-model="form.purchaseOrderNo" class="dm-input" type="text" />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.currency') }}</span>
              <FormSelect v-model="form.currency" :options="currencyOptions" />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.paymentTerms') }}</span>
              <HistoryTextInput
                v-model="form.paymentTerms"
                test-id="invoice-payment-terms"
                :options="paymentTermOptions"
              />
            </label>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <FileText class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.items') }}</h2>
          </div>
          <p class="text-xs text-dm-text-tertiary">
            {{ t('quotation.sales.create.productInternalHint') }}
          </p>
          <div class="space-y-3">
            <div
              v-for="(item, index) in form.items"
              :key="item.id"
              class="rounded-lg border border-dm-border-light bg-slate-50 p-3"
            >
              <div class="mb-3 flex items-center justify-between">
                <strong class="text-xs text-dm-text">
                  {{ t('quotation.sales.create.itemNumber', { number: index + 1 }) }}
                </strong>
                <button
                  type="button"
                  class="text-dm-text-tertiary hover:text-red-600"
                  :aria-label="t('quotation.sales.create.removeItem')"
                  @click="removeItem(index)"
                >
                  <Trash2 class="h-4 w-4" />
                </button>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="invoice-field">
                  <span>{{ t('quotation.sales.create.product') }}</span>
                  <HistoryTextInput
                    v-model="item.productName"
                    :options="itemHistoryOptions.map((history) => ({
                      value: history.item.product_name,
                      label: history.item.description,
                      key: `${history.invoice.id}-${history.item.id}-product`,
                      meta: history,
                    }))"
                    :has-more="historyHasMore"
                    :loading-more="historyLoading"
                    @select-option="handleItemDescriptionSelect(item, $event)"
                    @load-more="loadInvoiceHistory"
                  />
                </div>
                <div class="invoice-field sm:col-span-2">
                  <span>{{ t('quotation.sales.create.description') }}</span>
                  <HistoryTextInput
                    v-model="item.description"
                    multiline
                    :rows="2"
                    :options="itemHistoryOptions.map((history) => ({
                      value: history.item.description,
                      label: `${history.item.product_name} · ${form.currency} ${history.item.unit_price}`,
                      key: `${history.invoice.id}-${history.item.id}-description`,
                      meta: history,
                    }))"
                    :has-more="historyHasMore"
                    :loading-more="historyLoading"
                    @select-option="handleItemDescriptionSelect(item, $event)"
                    @load-more="loadInvoiceHistory"
                  />
                </div>
                <label class="invoice-field">
                  <span>{{ t('quotation.sales.create.quantity') }}</span>
                  <input
                    v-model.number="item.quantity"
                    class="dm-input"
                    min="0.0001"
                    step="0.0001"
                    type="number"
                  />
                </label>
                <label class="invoice-field">
                  <span>{{ t('quotation.sales.create.unitPrice') }}</span>
                  <input
                    v-model.number="item.unitPrice"
                    class="dm-input"
                    min="0"
                    step="0.0001"
                    type="number"
                  />
                </label>
                <p class="sm:col-span-2 text-right text-xs font-semibold text-dm-text">
                  {{ t('quotation.sales.create.extendedPrice') }}:
                  {{ form.currency }}
                  {{ formatEditorAmount(item.quantity * item.unitPrice) }}
                </p>
              </div>
            </div>
          </div>
          <div class="border-t border-dm-border-light pt-3">
            <button
              type="button"
              data-testid="invoice-add-item"
              class="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-blue-200 bg-blue-50/40 px-4 py-2.5 text-sm font-semibold text-dm-primary transition duration-150 hover:border-blue-300 hover:bg-blue-50"
              @click="addItem"
            >
              <Plus class="h-4 w-4" />
              {{ t('quotation.sales.create.addItem') }}
            </button>
          </div>
          <div class="flex justify-end border-t border-dm-border-light pt-3">
            <p class="text-sm font-semibold text-dm-text">
              {{ t('quotation.sales.create.totalAmount') }}:
              {{ form.currency }} {{ formatEditorAmount(totalAmount) }}
            </p>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <FileText class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.notesAndDisclaimers') }}</h2>
          </div>
          <label class="invoice-field">
            <span>{{ t('quotation.sales.create.additionalNotes') }}</span>
            <textarea v-model="form.additionalNotes" class="dm-input min-h-24" />
          </label>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <Landmark class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.bankDetails') }}</h2>
          </div>
          <div class="invoice-field">
            <span>{{ t('quotation.sales.create.bankHistory') }}</span>
            <HistoryTextInput
              v-model="selectedBankAccount"
              test-id="invoice-bank-account-history"
              :placeholder="t('quotation.sales.create.bankHistoryPlaceholder')"
              :options="bankHistoryOptions.map((invoice) => ({
                value: invoice.bank_name || invoice.bank_account_name,
                label: invoice.bank_account_name || invoice.bank_account_number,
                key: `${invoice.id}-bank-account`,
                meta: invoice,
              }))"
              :has-more="historyHasMore"
              :loading-more="historyLoading"
              @select-option="handleBankHistorySelect"
              @load-more="loadInvoiceHistory"
            />
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.accountName') }}</span>
              <HistoryTextInput
                v-model="form.bankAccountName"
                test-id="invoice-bank-account-name-history"
                :options="bankFieldOptions('bank_account_name')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_account_name', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.bankName') }}</span>
              <HistoryTextInput
                v-model="form.bankName"
                test-id="invoice-bank-name-history"
                :options="bankFieldOptions('bank_name')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_name', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.bankAddress') }}</span>
              <HistoryTextInput
                v-model="form.bankAddress"
                test-id="invoice-bank-address-history"
                :options="bankFieldOptions('bank_address')"
                multiline
                :rows="3"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_address', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.accountNumber') }}</span>
              <HistoryTextInput
                v-model="form.bankAccountNumber"
                test-id="invoice-bank-account-number-history"
                :options="bankFieldOptions('bank_account_number')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_account_number', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.bankCode') }}</span>
              <HistoryTextInput
                v-model="form.bankCode"
                test-id="invoice-bank-code-history"
                :options="bankFieldOptions('bank_code')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_code', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.branchCode') }}</span>
              <HistoryTextInput
                v-model="form.bankBranchCode"
                test-id="invoice-bank-branch-code-history"
                :options="bankFieldOptions('bank_branch_code')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_branch_code', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.swiftCode') }}</span>
              <HistoryTextInput
                v-model="form.bankSwiftCode"
                test-id="invoice-bank-swift-code-history"
                :options="bankFieldOptions('bank_swift_code')"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('bank_swift_code', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
            <label class="invoice-field sm:col-span-2">
              <span>{{ t('quotation.sales.create.remittanceInstruction') }}</span>
              <HistoryTextInput
                v-model="form.remittanceInstruction"
                test-id="invoice-remittance-instruction-history"
                :options="bankFieldOptions('remittance_instruction')"
                multiline
                :rows="3"
                :has-more="historyHasMore"
                :loading-more="historyLoading"
                @select-option="
                  handleBankFieldHistorySelect('remittance_instruction', $event)
                "
                @load-more="loadInvoiceHistory"
              />
            </label>
          </div>
        </section>

        <section class="dm-card space-y-4 p-5">
          <div class="invoice-form-heading">
            <PenLine class="h-4 w-4" />
            <h2>{{ t('quotation.sales.create.signature') }}</h2>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.signatoryName') }}</span>
              <input v-model="form.signatoryName" class="dm-input" type="text" />
            </label>
            <label class="invoice-field">
              <span>{{ t('quotation.sales.create.signatoryTitle') }}</span>
              <input v-model="form.signatoryTitle" class="dm-input" type="text" />
            </label>
          </div>
          <SignaturePicker
            v-model="form.signature"
            :user-email="userEmail"
            :draw-hint="t('quotation.sales.create.signatureDrawHint')"
            :upload-hint="t('quotation.sales.create.signatureUploadHint')"
          />
        </section>

        <div class="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            class="dm-btn-default inline-flex items-center justify-center gap-2 py-3 text-sm font-semibold"
            :disabled="submitting"
            @click="submit(InvoiceStatus.DRAFT)"
          >
            <Save class="h-4 w-4" />
            {{
              t(
                isFormalEditing
                  ? 'quotation.sales.create.saveChanges'
                  : 'quotation.sales.create.saveDraft',
              )
            }}
          </button>
          <button
            v-if="
              userStore.userHasInvoiceCapability('issue') &&
              !isFormalEditing
            "
            type="button"
            class="dm-btn-primary inline-flex items-center justify-center gap-2 py-3 text-sm font-semibold"
            :disabled="submitting"
            @click="submit(InvoiceStatus.ISSUED)"
          >
            <FileText class="h-4 w-4" />
            {{ t('quotation.sales.create.generateAndIssue') }}
          </button>
        </div>
      </form>

      <button
        type="button"
        class="group relative hidden w-6 shrink-0 cursor-col-resize items-center justify-center xl:sticky xl:top-5 xl:flex xl:h-[calc(100vh-2.5rem)]"
        :aria-label="t('quotation.sales.create.resizePreview')"
        @pointerdown="handleResizeStart"
      >
        <span class="h-full w-0.5 rounded-full bg-slate-200 group-hover:bg-dm-primary" />
        <span class="absolute h-20 w-1.5 rounded-full bg-slate-400 group-hover:bg-dm-primary" />
      </button>

      <aside
        class="xl:sticky xl:top-5 xl:min-w-[520px] xl:basis-[calc(var(--preview-width)-8px)] xl:pl-3"
        :style="{ '--preview-width': `${previewWidthPercent}%` }"
      >
        <div class="mb-2 flex items-center justify-between px-1">
          <strong class="text-sm text-dm-text">
            {{ t('quotation.sales.create.livePreview') }}
          </strong>
          <span class="text-xs text-dm-text-tertiary">
            English Commercial Invoice · A4
          </span>
        </div>
        <div class="max-h-[calc(100vh-80px)] overflow-auto rounded-xl border border-dm-border bg-slate-200 p-3 shadow-inner">
          <InvoicePreview :invoice="previewInvoice" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.invoice-form-heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #f1f5f9;
  color: #64748b;
}

.invoice-form-heading h2 {
  color: var(--dm-text, #111827);
  font-size: 0.875rem;
  font-weight: 700;
  line-height: 1.25rem;
}

.invoice-form-heading > span {
  margin-left: auto;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 0.6875rem;
  font-weight: 600;
}

.invoice-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.25rem;
}

.invoice-field > span {
  color: var(--dm-text-tertiary, #8c8c8c);
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.25rem;
}

.invoice-field > input.dm-input {
  height: 38px;
}
</style>
