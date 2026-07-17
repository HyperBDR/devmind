<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  Briefcase,
  DollarSign,
  FileSpreadsheet,
  FileText,
  Hash,
  Layers,
  PenLine,
  Plus,
  Save,
  Trash2,
  User,
  X,
} from 'lucide-vue-next'
import type {
  ItemType,
  PaymentTermOption,
  Product,
  ProductLineOption,
  Quotation,
  QuotationLineItem,
  QuoteProductLine,
  Service,
  DiscountOption,
} from '../types'
import { MOCK_SALESPERSONS } from '../data'
import QuotationPreview from './QuotationPreview.vue'
import SignaturePicker from './SignaturePicker.vue'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'
import HistoryTextInput, { type NormalizedHistoryOption } from './HistoryTextInput.vue'
import FormSelect from './FormSelect.vue'
import { buildDescriptionHistoryOptions } from '../utils/descriptionCatalog'
import {
  DEFAULT_ISSUER_COMPANY_NAME,
  DEFAULT_REMARKS_DISCLAIMER,
} from '../utils/quotationPreviewModel'
import {
  DEFAULT_TAX_LABEL,
  getMergedTaxLabelHistory,
  normalizeTaxLabel,
  rememberTaxLabel,
  resolveTaxLabel,
} from '../utils/taxLabels'
import { DEFAULT_PREVIEW_WIDTH_PERCENT, getPreviewWidthPercentFromPointer } from '../utils/resizablePreview'
import {
  dateFromInput,
  getNextAutoQuoteNumber,
  getProductLineDeletionState,
  getNextRevisionQuoteNumber,
  inferProductLineFromQuoteNumber,
  isProductLinePrefixUnique,
  isProductLinePrefixValid,
  isQuotationNumberUnique,
} from '../utils/quotationNumbering'
import {
  DEFAULT_PAYMENT_TERM_OPTION,
  PAYMENT_TERM_OPTIONS,
  getPaymentTermsValue,
  inferPaymentTermOption,
  isPaymentTermValid,
} from '../utils/paymentTerms'
import {
  calculateLineItemPrices,
  calculateQuotationTotals,
  formatVatRateForInput,
  parseVatRateInput,
} from '../utils/quotationTotals'
import {
  buildCustomerHistory,
  buildBillingHistory,
  type BillingHistoryRecord,
  type CustomerHistoryRecord,
  getCompanyOptions,
  getCompanyOptionLabel,
  getContactOptions,
  getEmailOptions,
  getBillingCompanyOptions,
  getBillingCompanyOptionLabel,
  getBillingContactOptions,
  getBillingEmailOptions,
} from '../utils/customerHistory'
import { clearCurrentUserSignature, rememberUserSignature } from '../utils/signatureStorage'
import {
  loadCreateQuoteDraft,
  saveCreateQuoteDraft,
  type CreateQuoteDraft,
} from '../utils/createDraftStorage'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const ADD_PRODUCT_LINE_OPTION = '__add_product_line__'

const props = withDefaults(
  defineProps<{
    products: Product[]
    services: Service[]
    discounts: DiscountOption[]
    quotations: Quotation[]
    historyQuotations?: Quotation[]
    editingQuote?: Quotation | null
    currentUser?: {
      name: string
      title: string
      email: string
      role: string
    }
    productLineOptions: ProductLineOption[]
  }>(),
  {
    historyQuotations: undefined,
    editingQuote: null,
  },
)

const emit = defineEmits<{
  saveQuote: [newQuote: Quotation]
  navigateToTab: [tab: string]
  addProductLine: [option: ProductLineOption]
  deleteProductLine: [productLine: QuoteProductLine]
}>()

const { t } = useQuotationI18n()

function formatDateInput(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function getDefaultExpireDate() {
  const today = new Date()
  return formatDateInput(new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000))
}

const quoteNo = ref('')
const quoteNoMode = ref<'auto' | 'custom'>('auto')
const productLine = ref<QuoteProductLine>('BDR')
const projectName = ref('')
const clientCompany = ref('')
const contactPerson = ref('')
const email = ref('')
const billingCompany = ref('')
const billingContact = ref('')
const billingEmail = ref('')
const region = ref('')
const industry = ref('')
const salesperson = ref(MOCK_SALESPERSONS[0])
const currency = ref<'CNY' | 'USD' | 'EUR'>('USD')
const paymentTermOption = ref<PaymentTermOption>(DEFAULT_PAYMENT_TERM_OPTION)
const paymentTermsCustom = ref('')
const vatRateInput = ref('')
const taxLabel = ref(DEFAULT_TAX_LABEL)
const historySourceQuotations = computed(() => props.historyQuotations ?? props.quotations)
const taxLabelHistory = ref<string[]>(
  getMergedTaxLabelHistory(props.currentUser?.email, historySourceQuotations.value),
)
const quoteDate = ref(formatDateInput(new Date()))
const expireDate = ref(getDefaultExpireDate())
const remarksDisclaimer = ref('')
const issuerCompanyName = ref(DEFAULT_ISSUER_COMPANY_NAME)
const issuerContactName = ref(props.currentUser?.name ?? '')
const issuerContactEmail = ref(props.currentUser?.email ?? '')
const issuerContactTitle = ref(props.currentUser?.title ?? '')
const issuerSignature = ref('')
const previewWidthPercent = ref(DEFAULT_PREVIEW_WIDTH_PERCENT)
const isAddingProductLine = ref(false)
const newProductLineLabel = ref('')
const newProductLinePrefix = ref('')
const productLineError = ref('')
const resizeContainerRef = ref<HTMLElement | null>(null)
const errors = ref<Record<string, string>>({})
const applyingCreateDraft = ref(false)
const preferDraftQuoteNo = ref(false)
let createDraftSaveTimer: number | undefined

function sanitizeVatRateInput(value: string): string {
  const numeric = value.replace(/[^\d.]/g, '')
  const [integer = '', ...decimalParts] = numeric.split('.')
  const decimal = decimalParts.join('').slice(0, 2)
  const hasDecimalPoint = numeric.includes('.')
  const normalizedInteger = integer || (hasDecimalPoint ? '0' : '')
  const normalized = hasDecimalPoint
    ? `${normalizedInteger}.${decimal}`
    : normalizedInteger

  if (normalized && Number(normalized) > 100) return String(Math.min(100, Number(normalized)))
  return normalized
}

function handleVatRateInput(event: Event) {
  const input = event.target as HTMLInputElement
  const sanitized = sanitizeVatRateInput(input.value)
  input.value = sanitized
  vatRateInput.value = sanitized
}

const items = ref<QuotationLineItem[]>([
  {
    id: 'init-item-1',
    type: 'Software',
    itemId: '',
    name: '',
    description: '',
    listPrice: 0,
    discountPercent: 0,
    qty: 1,
    netUnitPrice: 0,
    extendedPrice: 0,
  },
])

const paymentTerms = computed(() =>
  getPaymentTermsValue(paymentTermOption.value, paymentTermsCustom.value),
)

const currencyOptions = computed(() => [
  { value: 'CNY', label: t('quotation.pages.create.currencyCny') },
  { value: 'USD', label: t('quotation.pages.create.currencyUsd') },
  { value: 'EUR', label: t('quotation.pages.create.currencyEur') },
])

const paymentTermSelectOptions = PAYMENT_TERM_OPTIONS.map((option) => ({
  value: option.value,
  label: option.label,
}))

const existingQuoteNumbers = computed(() => props.quotations.map((quote) => quote.quoteNo))
const quoteNoIsUnique = computed(() =>
  isQuotationNumberUnique(quoteNo.value, props.quotations, props.editingQuote?.id),
)

const customerHistory = computed(() => buildCustomerHistory(historySourceQuotations.value))
const customerCompanyOptions = computed(() => getCompanyOptions(customerHistory.value))
const customerContactOptions = computed(() =>
  getContactOptions(customerHistory.value, clientCompany.value),
)
const customerEmailOptions = computed(() => getEmailOptions(customerHistory.value, clientCompany.value))
const billingHistory = computed(() => buildBillingHistory(historySourceQuotations.value))
const billingCompanyOptions = computed(() => getBillingCompanyOptions(billingHistory.value))
const billingContactOptions = computed(() =>
  getBillingContactOptions(billingHistory.value, billingCompany.value),
)
const billingEmailOptions = computed(() =>
  getBillingEmailOptions(billingHistory.value, billingCompany.value),
)

const availableProductLineOptions = computed(() => {
  if (props.productLineOptions.some((option) => option.value === productLine.value)) {
    return props.productLineOptions
  }
  return [...props.productLineOptions, { value: productLine.value, label: productLine.value }]
})

const selectedProductLineOption = computed(() =>
  availableProductLineOptions.value.find((option) => option.value === productLine.value),
)

const productLineDeletionState = computed(() =>
  getProductLineDeletionState(productLine.value, availableProductLineOptions.value, props.quotations),
)

const productLineDeleteDisabled = computed(() => !productLineDeletionState.value.canDelete)
const productLineDeleteHint = computed(
  () =>
    productLineDeletionState.value.reason ||
    t('quotation.pages.create.deleteProductLine'),
)

const productLineSelectOptions = computed(() => [
  ...availableProductLineOptions.value.map((option) => ({
    value: option.value,
    label: `${option.label} (${option.value})`,
  })),
  { value: ADD_PRODUCT_LINE_OPTION, label: `+ ${t('quotation.pages.create.addProductLine')}...` },
])

function regenerateQuoteNo(line = productLine.value, date = quoteDate.value) {
  if (props.editingQuote) {
    quoteNo.value = getNextRevisionQuoteNumber(props.editingQuote.quoteNo, existingQuoteNumbers.value)
    return
  }
  quoteNo.value = getNextAutoQuoteNumber(line, dateFromInput(date), existingQuoteNumbers.value)
}

function handleAddProductLine() {
  const label = newProductLineLabel.value.trim()
  const prefix = newProductLinePrefix.value.trim()
  if (!label) {
    productLineError.value = t('quotation.pages.create.errors.productLineNameRequired')
    return
  }
  if (!isProductLinePrefixValid(prefix)) {
    productLineError.value = t('quotation.pages.create.errors.productLinePrefixInvalid')
    return
  }
  if (!isProductLinePrefixUnique(prefix, props.productLineOptions)) {
    productLineError.value = t('quotation.pages.create.errors.productLinePrefixDuplicate')
    return
  }
  const option = { value: prefix, label }
  emit('addProductLine', option)
  productLine.value = prefix
  if (!props.editingQuote && quoteNoMode.value === 'auto') {
    quoteNo.value = getNextAutoQuoteNumber(prefix, dateFromInput(quoteDate.value), existingQuoteNumbers.value)
  }
  newProductLineLabel.value = ''
  newProductLinePrefix.value = ''
  productLineError.value = ''
  isAddingProductLine.value = false
}

function handleDeleteProductLine() {
  if (!productLineDeletionState.value.canDelete) return
  const label = selectedProductLineOption.value?.label || productLine.value
  const usageNote =
    productLineDeletionState.value.usageCount > 0
      ? `\n\n${t('quotation.pages.create.confirmDeleteProductLineUsage', {
          count: productLineDeletionState.value.usageCount,
        })}`
      : ''
  const confirmed = window.confirm(
    `${t('quotation.pages.create.confirmDeleteProductLine', {
      label,
      prefix: productLine.value,
    })}${usageNote}`,
  )
  if (!confirmed) return
  const remainingOptions = props.productLineOptions.filter((option) => option.value !== productLine.value)
  const nextProductLine = remainingOptions[0]?.value || 'BDR'
  emit('deleteProductLine', productLine.value)
  productLine.value = nextProductLine
  if (!props.editingQuote && quoteNoMode.value === 'auto') {
    quoteNo.value = getNextAutoQuoteNumber(
      nextProductLine,
      dateFromInput(quoteDate.value),
      existingQuoteNumbers.value,
    )
  }
  productLineError.value = ''
}

function applyCustomerRecord(record: CustomerHistoryRecord) {
  clientCompany.value = record.clientCompany
  contactPerson.value = record.contactPerson
  email.value = record.email
}

function applyBillingRecord(record: BillingHistoryRecord) {
  billingCompany.value = record.billingCompany
  billingContact.value = record.billingContact
  billingEmail.value = record.billingEmail
}

function handleClientCompanyInput(value: string) {
  clientCompany.value = value
}

function handleClientCompanySelect(option: NormalizedHistoryOption) {
  clientCompany.value = option.value
  const contacts = getContactOptions(customerHistory.value, option.value)
  if (contacts.length === 1) {
    contactPerson.value = contacts[0].contactPerson
    email.value = contacts[0].email
    return
  }
  const stillValid = contacts.some(
    (record) => record.contactPerson === contactPerson.value && record.email === email.value,
  )
  if (!stillValid) {
    contactPerson.value = ''
    email.value = ''
  }
}

function handleContactPersonInput(value: string) {
  contactPerson.value = value
}

function handleContactPersonSelect(option: NormalizedHistoryOption) {
  const record = option.meta as CustomerHistoryRecord | undefined
  if (record) {
    if (!clientCompany.value.trim()) clientCompany.value = record.clientCompany
    contactPerson.value = record.contactPerson
    email.value = record.email
    return
  }
  contactPerson.value = option.value
}

function handleEmailInput(value: string) {
  email.value = value
}

function handleEmailSelect(option: NormalizedHistoryOption) {
  const record = option.meta as CustomerHistoryRecord | undefined
  if (record) applyCustomerRecord(record)
  else email.value = option.value
}

function handleBillingCompanyInput(value: string) {
  billingCompany.value = value
}

function handleBillingCompanySelect(option: NormalizedHistoryOption) {
  billingCompany.value = option.value
  const contacts = getBillingContactOptions(billingHistory.value, option.value)
  if (contacts.length === 1) {
    billingContact.value = contacts[0].billingContact
    billingEmail.value = contacts[0].billingEmail
    return
  }
  const stillValid = contacts.some(
    (record) =>
      record.billingContact === billingContact.value && record.billingEmail === billingEmail.value,
  )
  if (!stillValid) {
    billingContact.value = ''
    billingEmail.value = ''
  }
}

function handleBillingContactInput(value: string) {
  billingContact.value = value
}

function handleBillingContactSelect(option: NormalizedHistoryOption) {
  const record = option.meta as BillingHistoryRecord | undefined
  if (record) {
    if (!billingCompany.value.trim()) billingCompany.value = record.billingCompany
    billingContact.value = record.billingContact
    billingEmail.value = record.billingEmail
    return
  }
  billingContact.value = option.value
}

function handleBillingEmailInput(value: string) {
  billingEmail.value = value
}

function handleBillingEmailSelect(option: NormalizedHistoryOption) {
  const record = option.meta as BillingHistoryRecord | undefined
  if (record) applyBillingRecord(record)
  else billingEmail.value = option.value
}

watch(
  [() => props.currentUser?.email, historySourceQuotations],
  () => {
    taxLabelHistory.value = getMergedTaxLabelHistory(
      props.currentUser?.email,
      historySourceQuotations.value,
    )
  },
  { immediate: true },
)

function loadEditingQuoteIntoForm(editingQuote: Quotation) {
  preferDraftQuoteNo.value = false
  quoteNoMode.value = 'auto'
  productLine.value =
    editingQuote.productLine ||
    inferProductLineFromQuoteNumber(editingQuote.quoteNo, props.productLineOptions)
  quoteNo.value = getNextRevisionQuoteNumber(editingQuote.quoteNo, existingQuoteNumbers.value)
  projectName.value = editingQuote.projectName
  clientCompany.value = editingQuote.clientCompany
  contactPerson.value = editingQuote.contactPerson
  email.value = editingQuote.email
  billingCompany.value = editingQuote.billingCompany || editingQuote.clientCompany
  billingContact.value = editingQuote.billingContact || editingQuote.contactPerson
  billingEmail.value = editingQuote.billingEmail || editingQuote.email
  region.value = editingQuote.region || ''
  industry.value = editingQuote.industry || ''
  salesperson.value = editingQuote.salesperson
  currency.value = editingQuote.currency
  const loadedPaymentTermOption =
    editingQuote.paymentTermOption || inferPaymentTermOption(editingQuote.paymentTerms || '')
  paymentTermOption.value = loadedPaymentTermOption
  paymentTermsCustom.value =
    loadedPaymentTermOption === 'Others' ? editingQuote.paymentTerms || '' : ''
  vatRateInput.value = formatVatRateForInput(editingQuote.vatRate)
  taxLabel.value = resolveTaxLabel(editingQuote.taxLabel)
  quoteDate.value = editingQuote.quoteDate || formatDateInput(new Date())
  expireDate.value = editingQuote.expireDate || getDefaultExpireDate()
  remarksDisclaimer.value = editingQuote.remarksDisclaimer ?? ''
  issuerCompanyName.value = editingQuote.issuerCompanyName ?? DEFAULT_ISSUER_COMPANY_NAME
  issuerContactName.value =
    editingQuote.issuerContactName || editingQuote.salesperson || props.currentUser?.name || ''
  issuerContactEmail.value = editingQuote.issuerContactEmail || props.currentUser?.email || ''
  issuerContactTitle.value = editingQuote.issuerContactTitle || props.currentUser?.title || ''
  issuerSignature.value = editingQuote.issuerSignature ?? ''
  items.value = JSON.parse(JSON.stringify(editingQuote.items)).map((item: QuotationLineItem) => ({
    ...item,
    type: item.type === 'Software' ? 'Software' : 'Other',
    name: '',
    description: item.description || item.name || '',
  }))
}

function resetCreateForm() {
  preferDraftQuoteNo.value = false
  quoteNoMode.value = 'auto'
  productLine.value = 'BDR'
  const todayInput = formatDateInput(new Date())
  quoteNo.value = getNextAutoQuoteNumber('BDR', dateFromInput(todayInput), existingQuoteNumbers.value)
  projectName.value = ''
  clientCompany.value = ''
  contactPerson.value = ''
  email.value = ''
  billingCompany.value = ''
  billingContact.value = ''
  billingEmail.value = ''
  region.value = ''
  industry.value = ''
  salesperson.value = props.currentUser ? props.currentUser.name : MOCK_SALESPERSONS[0]
  currency.value = 'USD'
  paymentTermOption.value = DEFAULT_PAYMENT_TERM_OPTION
  paymentTermsCustom.value = ''
  vatRateInput.value = ''
  taxLabel.value = DEFAULT_TAX_LABEL
  quoteDate.value = todayInput
  expireDate.value = getDefaultExpireDate()
  remarksDisclaimer.value = ''
  issuerCompanyName.value = DEFAULT_ISSUER_COMPANY_NAME
  issuerContactName.value = props.currentUser?.name ?? ''
  issuerContactEmail.value = props.currentUser?.email ?? ''
  issuerContactTitle.value = props.currentUser?.title ?? ''
  issuerSignature.value = ''
  items.value = [
    {
      id: 'init-item-1',
      type: 'Software',
      itemId: '',
      name: '',
      description: '',
      listPrice: 0,
      discountPercent: 0,
      qty: 1,
      netUnitPrice: 0,
      extendedPrice: 0,
    },
  ]
}

function buildCreateDraftPayload(): Omit<CreateQuoteDraft, 'version' | 'savedAt'> {
  return {
    quoteNo: quoteNo.value,
    quoteNoMode: quoteNoMode.value,
    productLine: productLine.value,
    projectName: projectName.value,
    clientCompany: clientCompany.value,
    contactPerson: contactPerson.value,
    email: email.value,
    billingCompany: billingCompany.value,
    billingContact: billingContact.value,
    billingEmail: billingEmail.value,
    region: region.value,
    industry: industry.value,
    salesperson: salesperson.value,
    currency: currency.value,
    paymentTermOption: paymentTermOption.value,
    paymentTermsCustom: paymentTermsCustom.value,
    vatRateInput: vatRateInput.value,
    taxLabel: taxLabel.value,
    quoteDate: quoteDate.value,
    expireDate: expireDate.value,
    remarksDisclaimer: remarksDisclaimer.value,
    issuerCompanyName: issuerCompanyName.value,
    issuerContactName: issuerContactName.value,
    issuerContactEmail: issuerContactEmail.value,
    issuerContactTitle: issuerContactTitle.value,
    issuerSignature: issuerSignature.value,
    items: JSON.parse(JSON.stringify(items.value)) as QuotationLineItem[],
  }
}

function applyCreateDraft(draft: CreateQuoteDraft) {
  applyingCreateDraft.value = true
  preferDraftQuoteNo.value = true
  quoteNoMode.value = draft.quoteNoMode || 'auto'
  productLine.value = draft.productLine || 'BDR'
  quoteNo.value = draft.quoteNo || ''
  projectName.value = draft.projectName || ''
  clientCompany.value = draft.clientCompany || ''
  contactPerson.value = draft.contactPerson || ''
  email.value = draft.email || ''
  billingCompany.value = draft.billingCompany || ''
  billingContact.value = draft.billingContact || ''
  billingEmail.value = draft.billingEmail || ''
  region.value = draft.region || ''
  industry.value = draft.industry || ''
  salesperson.value = draft.salesperson || salesperson.value
  currency.value = draft.currency || 'USD'
  paymentTermOption.value =
    draft.paymentTermOption || DEFAULT_PAYMENT_TERM_OPTION
  paymentTermsCustom.value = draft.paymentTermsCustom || ''
  vatRateInput.value = draft.vatRateInput || ''
  taxLabel.value = draft.taxLabel || DEFAULT_TAX_LABEL
  quoteDate.value = draft.quoteDate || formatDateInput(new Date())
  expireDate.value = draft.expireDate || getDefaultExpireDate()
  remarksDisclaimer.value = draft.remarksDisclaimer || ''
  issuerCompanyName.value =
    draft.issuerCompanyName || DEFAULT_ISSUER_COMPANY_NAME
  issuerContactName.value =
    draft.issuerContactName || props.currentUser?.name || ''
  issuerContactEmail.value =
    draft.issuerContactEmail || props.currentUser?.email || ''
  issuerContactTitle.value =
    draft.issuerContactTitle || props.currentUser?.title || ''
  issuerSignature.value = draft.issuerSignature || ''
  items.value =
    Array.isArray(draft.items) && draft.items.length > 0
      ? JSON.parse(JSON.stringify(draft.items))
      : items.value
  window.setTimeout(() => {
    applyingCreateDraft.value = false
  }, 0)
}

function persistCreateDraftSoon() {
  if (props.editingQuote || applyingCreateDraft.value) return
  const emailKey = props.currentUser?.email
  if (!emailKey) return
  window.clearTimeout(createDraftSaveTimer)
  createDraftSaveTimer = window.setTimeout(() => {
    if (props.editingQuote || applyingCreateDraft.value) return
    saveCreateQuoteDraft(emailKey, buildCreateDraftPayload())
  }, 300)
}

function initCreateForm() {
  const draft = loadCreateQuoteDraft(props.currentUser?.email)
  if (draft) {
    applyCreateDraft(draft)
    return
  }
  resetCreateForm()
}

onBeforeUnmount(() => {
  window.clearTimeout(createDraftSaveTimer)
})

watch(
  () => [props.editingQuote?.id ?? null, props.currentUser?.email ?? null] as const,
  ([editingQuoteId]) => {
    if (editingQuoteId && props.editingQuote) {
      loadEditingQuoteIntoForm(props.editingQuote)
      return
    }
    if (!editingQuoteId) {
      initCreateForm()
    }
  },
  { immediate: true },
)

watch(
  [() => props.editingQuote, existingQuoteNumbers, productLine, quoteDate, quoteNoMode],
  (next, prev) => {
    if (props.editingQuote || applyingCreateDraft.value) return
    if (quoteNoMode.value !== 'auto') return
    if (preferDraftQuoteNo.value) {
      if (!prev) return
      const prevLine = prev[2]
      const prevDate = prev[3]
      const prevMode = prev[4]
      const nextLine = next[2]
      const nextDate = next[3]
      const nextMode = next[4]
      if (
        prevLine === nextLine &&
        prevDate === nextDate &&
        prevMode === nextMode
      ) {
        return
      }
      preferDraftQuoteNo.value = false
    }
    quoteNo.value = getNextAutoQuoteNumber(
      productLine.value,
      dateFromInput(quoteDate.value),
      existingQuoteNumbers.value,
    )
  },
)

watch(
  [
    quoteNo,
    quoteNoMode,
    productLine,
    projectName,
    clientCompany,
    contactPerson,
    email,
    billingCompany,
    billingContact,
    billingEmail,
    region,
    industry,
    salesperson,
    currency,
    paymentTermOption,
    paymentTermsCustom,
    vatRateInput,
    taxLabel,
    quoteDate,
    expireDate,
    remarksDisclaimer,
    issuerCompanyName,
    issuerContactName,
    issuerContactEmail,
    issuerContactTitle,
    issuerSignature,
    items,
  ],
  () => {
    persistCreateDraftSoon()
  },
  { deep: true },
)

function handleAddLineItem() {
  items.value = [
    ...items.value,
    {
      id: `custom-item-${Date.now()}-${Math.random()}`,
      type: 'Software',
      itemId: '',
      name: '',
      description: '',
      listPrice: 0,
      discountPercent: 0,
      qty: 1,
      netUnitPrice: 0,
      extendedPrice: 0,
    },
  ]
}

function handleRemoveLineItem(id: string) {
  if (items.value.length === 1) {
    alert(t('quotation.pages.create.alertMinLineItems'))
    return
  }
  items.value = items.value.filter((item) => item.id !== id)
}

function handleRowChange(id: string, updatedFields: Partial<QuotationLineItem>) {
  items.value = items.value.map((item) => {
    if (item.id !== id) return item
    let tempItem = { ...item, ...updatedFields }
    if (updatedFields.type && updatedFields.type !== item.type) {
      tempItem = {
        ...tempItem,
        itemId: '',
        name: '',
        description: '',
        listPrice: 0,
        discountPercent: 0,
        qty: 1,
        netUnitPrice: 0,
        extendedPrice: 0,
      }
    }
    const prices = calculateLineItemPrices({
      listPrice: tempItem.listPrice,
      discountPercent: tempItem.discountPercent,
      qty: tempItem.qty,
    })
    tempItem.netUnitPrice = prices.netUnitPrice
    tempItem.extendedPrice = prices.extendedPrice
    return tempItem
  })
}

function descriptionOptionsFor(itemType: QuotationLineItem['type']) {
  return buildDescriptionHistoryOptions(
    itemType,
    props.products,
    props.services,
    historySourceQuotations.value,
  )
}

function handleDescriptionSelect(
  item: QuotationLineItem,
  option: NormalizedHistoryOption,
) {
  const listPrice = Number(
    (option.meta as { listPrice?: number } | undefined)?.listPrice,
  )
  const patch: Partial<QuotationLineItem> = {
    description: option.value,
  }
  if (Number.isFinite(listPrice) && listPrice > 0 && !item.listPrice) {
    patch.listPrice = listPrice
  }
  handleRowChange(item.id, patch)
}

const parsedVatRate = computed(() => parseVatRateInput(vatRateInput.value))
const quotationTotals = computed(() => calculateQuotationTotals(items.value, parsedVatRate.value))
const softwareSubtotal = computed(() => quotationTotals.value.softwareSubtotal)
const othersSubtotal = computed(() => quotationTotals.value.othersSubtotal)
const subtotalBeforeVat = computed(() => quotationTotals.value.subtotalBeforeVat)
const vatAmount = computed(() => quotationTotals.value.vatAmount)
const grandTotal = computed(() => quotationTotals.value.grandTotal)
const currencySymbol = computed(() =>
  currency.value === 'CNY' ? '¥' : currency.value === 'USD' ? '$' : '€',
)

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

const previewQuote = computed<Quotation>(() => ({
  id: props.editingQuote ? props.editingQuote.id : 'live-preview',
  quoteNo: quoteNo.value,
  productLine: productLine.value,
  projectName: projectName.value,
  clientCompany: clientCompany.value,
  contactPerson: contactPerson.value,
  email: email.value,
  billingCompany: billingCompany.value || clientCompany.value,
  billingContact: billingContact.value || contactPerson.value,
  billingEmail: billingEmail.value || email.value,
  region: region.value,
  industry: industry.value,
  salesperson: issuerContactName.value.trim() || salesperson.value,
  currency: currency.value,
  paymentTermOption: paymentTermOption.value,
  paymentTerms: paymentTerms.value,
  quoteDate: quoteDate.value,
  expireDate: expireDate.value,
  remarksDisclaimer: remarksDisclaimer.value,
  issuerCompanyName: issuerCompanyName.value,
  issuerContactName: issuerContactName.value,
  issuerContactEmail: issuerContactEmail.value,
  issuerContactTitle: issuerContactTitle.value,
  issuerSignature: issuerSignature.value,
  status: props.editingQuote ? props.editingQuote.status : 'Draft',
  items: items.value,
  softwareSubtotal: softwareSubtotal.value,
  othersSubtotal: othersSubtotal.value,
  subtotalBeforeVat: subtotalBeforeVat.value,
  taxLabel: resolveTaxLabel(taxLabel.value),
  vatRate: quotationTotals.value.vatRate,
  vatAmount: vatAmount.value,
  grandTotal: grandTotal.value,
  createdAt: props.editingQuote ? props.editingQuote.createdAt : `${quoteDate.value} 00:00:00`,
}))

function validateForm() {
  const tempErrors: Record<string, string> = {}
  if (!quoteNo.value.trim()) {
    tempErrors.quoteNo = t('quotation.pages.create.errors.quoteNoRequired')
  }
  if (quoteNo.value.trim() && !quoteNoIsUnique.value) {
    tempErrors.quoteNo = t('quotation.pages.create.errors.quoteNoDuplicate')
  }
  if (!paymentTerms.value.trim()) {
    tempErrors.paymentTerms = t('quotation.pages.create.errors.paymentTermsRequired')
  }
  if (!isPaymentTermValid(paymentTermOption.value, paymentTermsCustom.value)) {
    tempErrors.paymentTerms = t('quotation.pages.create.errors.paymentTermsCustomRequired')
  }
  if (
    !Number.isFinite(parsedVatRate.value) ||
    parsedVatRate.value < 0 ||
    parsedVatRate.value > 100
  ) {
    tempErrors.vatRate = t('quotation.pages.create.errors.vatRateInvalid')
  }
  if (!normalizeTaxLabel(taxLabel.value)) {
    tempErrors.taxLabel = t('quotation.pages.create.errors.taxLabelRequired')
  }
  if (!projectName.value.trim()) {
    tempErrors.projectName = t('quotation.pages.create.errors.projectNameRequired')
  }
  if (!clientCompany.value.trim()) {
    tempErrors.clientCompany = t('quotation.pages.create.errors.clientCompanyRequired')
  }
  if (!contactPerson.value.trim()) {
    tempErrors.contactPerson = t('quotation.pages.create.errors.contactPersonRequired')
  }
  if (!issuerContactName.value.trim()) {
    tempErrors.issuerContactName = t('quotation.pages.create.errors.issuerContactRequired')
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!email.value.trim()) {
    tempErrors.email = t('quotation.pages.create.errors.emailRequired')
  } else if (!emailRegex.test(email.value)) {
    tempErrors.email = t('quotation.pages.create.errors.emailInvalid')
  }

  if (!issuerContactEmail.value.trim()) {
    tempErrors.issuerContactEmail = t('quotation.pages.create.errors.issuerEmailRequired')
  } else if (!emailRegex.test(issuerContactEmail.value)) {
    tempErrors.issuerContactEmail = t('quotation.pages.create.errors.emailInvalid')
  }

  items.value.forEach((item, index) => {
    if (!(item.description || item.name).trim()) {
      tempErrors[`item-${index}`] = t('quotation.pages.create.errors.itemDescriptionRequired', {
        line: index + 1,
      })
    }
    if (item.listPrice <= 0) {
      tempErrors[`itemPrice-${index}`] = t('quotation.pages.create.errors.itemPriceRequired', {
        line: index + 1,
      })
    }
  })

  errors.value = tempErrors
  return tempErrors
}

function handleSubmit(status: 'Draft' | 'Generated') {
  const validationErrors = validateForm()
  if (Object.keys(validationErrors).length > 0) {
    const firstErrorMsg =
      Object.values(validationErrors)[0] ||
      t('quotation.pages.create.alertValidationDefault')
    alert(
      t('quotation.pages.create.alertValidationFailed', { message: firstErrorMsg }),
    )
    return
  }

  const today = new Date()
  const formattedDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')} ${String(today.getHours()).padStart(2, '0')}:${String(today.getMinutes()).padStart(2, '0')}:${String(today.getSeconds()).padStart(2, '0')}`
  const normalizedTaxLabel = resolveTaxLabel(taxLabel.value)
  taxLabelHistory.value = rememberTaxLabel(normalizedTaxLabel, props.currentUser?.email)

  const newQuote: Quotation = {
    id: props.editingQuote ? props.editingQuote.id : `quote-${Date.now()}`,
    quoteNo: quoteNo.value,
    productLine: productLine.value,
    projectName: projectName.value,
    clientCompany: clientCompany.value,
    contactPerson: contactPerson.value,
    email: email.value,
    billingCompany: billingCompany.value || clientCompany.value,
    billingContact: billingContact.value || contactPerson.value,
    billingEmail: billingEmail.value || email.value,
    region: region.value,
    industry: industry.value,
    salesperson: issuerContactName.value.trim() || salesperson.value,
    createdByEmail: props.editingQuote?.createdByEmail || props.currentUser?.email,
    currency: currency.value,
    paymentTermOption: paymentTermOption.value,
    paymentTerms: paymentTerms.value,
    quoteDate: quoteDate.value,
    expireDate: expireDate.value,
    remarksDisclaimer: remarksDisclaimer.value,
    issuerCompanyName: issuerCompanyName.value,
    issuerContactName: issuerContactName.value,
    issuerContactEmail: issuerContactEmail.value,
    issuerContactTitle: issuerContactTitle.value,
    issuerSignature: issuerSignature.value,
    status,
    items: items.value,
    softwareSubtotal: softwareSubtotal.value,
    othersSubtotal: othersSubtotal.value,
    subtotalBeforeVat: subtotalBeforeVat.value,
    taxLabel: normalizedTaxLabel,
    vatRate: quotationTotals.value.vatRate,
    vatAmount: vatAmount.value,
    grandTotal: grandTotal.value,
    createdAt: props.editingQuote ? props.editingQuote.createdAt : formattedDate,
  }

  emit('saveQuote', newQuote)
  issuerSignature.value = ''
  if (props.currentUser?.email) {
    clearCurrentUserSignature(props.currentUser.email)
  }
}

function autoItemNumber(index: number, type: ItemType) {
  return items.value
    .slice(0, index + 1)
    .filter((row) => (type === 'Software' ? row.type === 'Software' : row.type !== 'Software')).length
}

function onProductLineSelect(selectedValue: string) {
  if (selectedValue === ADD_PRODUCT_LINE_OPTION) {
    isAddingProductLine.value = true
    productLineError.value = ''
    return
  }
  productLine.value = selectedValue
}

const itemErrorEntries = computed(() =>
  Object.entries(errors.value).filter(([key]) => key.startsWith('item')),
)
</script>

<template>
  <div id="create-quote-root" class="mx-auto max-w-[1680px] space-y-6">
    <div class="flex items-center justify-between dm-card p-4 shadow-xs">
      <div>
        <h2 class="text-base font-bold text-dm-text">
          {{ editingQuote ? t('quotation.pages.create.titleEdit') : t('quotation.pages.create.titleCreate') }}
        </h2>
        <p class="mt-0.5 text-xs text-dm-text-tertiary">
          {{
            editingQuote
              ? t('quotation.pages.create.subtitleEdit')
              : t('quotation.pages.create.subtitleCreate')
          }}
        </p>
      </div>
      <div class="text-right">
        <span class="block text-[10px] font-medium text-dm-text-tertiary">
          {{ t('quotation.pages.create.currentQuoteNo') }}
        </span>
        <span
          class="rounded-md px-3 py-1 font-mono text-sm font-bold"
          :class="quoteNoIsUnique ? 'bg-dm-primary-bg text-dm-primary' : 'bg-red-50 text-red-600'"
        >
          {{ quoteNo }}
        </span>
      </div>
    </div>

    <div ref="resizeContainerRef" class="flex flex-col gap-6 xl:flex-row xl:items-start xl:gap-0">
      <div
        data-testid="quote-form-pane"
        class="space-y-6 xl:min-w-[360px] xl:basis-[calc(var(--form-pane-width)-8px)] xl:pr-3"
        :style="{ '--form-pane-width': `${100 - previewWidthPercent}%` }"
      >
        <div class="space-y-6">
          <!-- Step 1 -->
          <div class="space-y-4 dm-card p-5 shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <Hash class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step1Title') }}</h3>
            </div>

            <div class="text-xs">
              <label class="mb-1 block font-semibold text-dm-text-tertiary">
                {{ t('quotation.pages.create.issuerCompany') }}
              </label>
              <input
                v-model="issuerCompanyName"
                type="text"
                :placeholder="t('quotation.pages.create.issuerCompanyPlaceholder')"
                class="w-full rounded-lg border border-dm-border p-2 focus:border-blue-500 focus:outline-hidden"
              />
            </div>

            <div class="grid grid-cols-1 gap-4 text-xs sm:grid-cols-2">
              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.quoteDate') }}
                </label>
                <BaseDatePicker
                  v-model="quoteDate"
                  :clearable="false"
                  input-class="w-full rounded-lg border border-dm-border p-2 text-dm-text focus:border-blue-500 focus:outline-hidden h-auto"
                />
              </div>
              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.expireDate') }}
                </label>
                <BaseDatePicker
                  v-model="expireDate"
                  :clearable="false"
                  input-class="w-full rounded-lg border border-dm-border p-2 text-dm-text focus:border-blue-500 focus:outline-hidden h-auto"
                />
              </div>
            </div>

            <div class="space-y-3 rounded-lg border border-dm-border-light bg-[#fafafa]/60 p-3 text-xs">
              <div class="flex items-center justify-between gap-3">
                <span class="text-[11px] font-bold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.numberingSettings') }}
                </span>
                <span v-if="editingQuote" class="text-[10px] font-semibold text-dm-primary">
                  {{ t('quotation.pages.create.revisionAutoSuffix') }}
                </span>
              </div>

              <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label class="mb-1 block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.productLine') }}
                  </label>
                  <div class="flex gap-2">
                    <FormSelect
                      test-id="quote-product-line-select"
                      class-name="min-w-0 flex-1"
                      :model-value="productLine"
                      :disabled="!!editingQuote && quoteNoMode === 'auto'"
                      :options="productLineSelectOptions"
                      @update:model-value="onProductLineSelect"
                    />
                    <button
                      type="button"
                      data-testid="quote-product-line-delete-button"
                      :disabled="productLineDeleteDisabled"
                      :title="productLineDeleteHint"
                      :aria-label="t('quotation.pages.create.deleteProductLine')"
                      class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-lg border transition"
                      :class="
                        productLineDeleteDisabled
                          ? 'cursor-not-allowed border-dm-border bg-[#fafafa] text-slate-300'
                          : 'cursor-pointer border-red-100 bg-white text-red-500 hover:border-red-200 hover:bg-red-50'
                      "
                      @click="handleDeleteProductLine"
                    >
                      <Trash2 class="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div>
                  <label class="mb-1 block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.numberingMode') }}
                  </label>
                  <div class="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      class="cursor-pointer rounded-lg border p-2 font-bold transition"
                      :class="
                        quoteNoMode === 'auto'
                          ? 'border-blue-500 bg-dm-primary-bg text-dm-primary'
                          : 'border-dm-border bg-white text-dm-text-secondary hover:bg-[#fafafa]'
                      "
                      @click="
                        () => {
                          quoteNoMode = 'auto'
                          regenerateQuoteNo()
                        }
                      "
                    >
                      {{ t('quotation.pages.create.numberingAuto') }}
                    </button>
                    <button
                      type="button"
                      class="cursor-pointer rounded-lg border p-2 font-bold transition"
                      :class="
                        quoteNoMode === 'custom'
                          ? 'border-blue-500 bg-dm-primary-bg text-dm-primary'
                          : 'border-dm-border bg-white text-dm-text-secondary hover:bg-[#fafafa]'
                      "
                      @click="quoteNoMode = 'custom'"
                    >
                      {{ t('quotation.pages.create.numberingCustom') }}
                    </button>
                  </div>
                </div>
              </div>

              <div
                v-if="isAddingProductLine"
                class="space-y-2 rounded-lg border border-[#91caff] bg-dm-primary-bg/40 p-3"
              >
                <div class="flex items-center justify-between gap-3">
                  <span class="text-[11px] font-bold text-blue-700">
                    {{ t('quotation.pages.create.addProductLine') }}
                  </span>
                  <button
                    type="button"
                    :aria-label="t('quotation.pages.create.closeAddProductLine')"
                    class="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-dm-text-tertiary hover:bg-white hover:text-dm-text-secondary"
                    @click="
                      () => {
                        isAddingProductLine = false
                        productLineError = ''
                      }
                    "
                  >
                    <X class="h-3.5 w-3.5" />
                  </button>
                </div>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.productLineName') }}
                    </label>
                    <input
                      v-model="newProductLineLabel"
                      type="text"
                      :placeholder="t('quotation.pages.create.productLineNamePlaceholder')"
                      class="w-full rounded-lg border border-dm-border bg-white p-2 text-dm-text focus:border-blue-500 focus:outline-hidden"
                    />
                  </div>
                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.productLinePrefix') }}
                    </label>
                    <input
                      v-model="newProductLinePrefix"
                      type="text"
                      :placeholder="t('quotation.pages.create.productLinePrefixPlaceholder')"
                      class="w-full rounded-lg border border-dm-border bg-white p-2 font-mono text-dm-text focus:border-blue-500 focus:outline-hidden"
                    />
                  </div>
                </div>
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p
                    class="text-[10px] font-medium"
                    :class="productLineError ? 'text-red-500' : 'text-dm-text-tertiary'"
                  >
                    {{
                      productLineError ||
                      t('quotation.pages.create.productLineRule')
                    }}
                  </p>
                  <button
                    type="button"
                    class="shrink-0 cursor-pointer rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-blue-700"
                    @click="handleAddProductLine"
                  >
                    {{ t('quotation.actions.saveProductLine') }}
                  </button>
                </div>
              </div>

              <div>
                <div class="mb-1 flex items-center justify-between gap-3">
                  <label class="block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.quoteNumber') }}
                  </label>
                  <button
                    v-if="quoteNoMode === 'auto'"
                    type="button"
                    class="cursor-pointer text-[10px] font-semibold text-dm-primary hover:text-blue-700"
                    @click="regenerateQuoteNo()"
                  >
                    {{ t('quotation.actions.regenerate') }}
                  </button>
                </div>
                <input
                  v-model="quoteNo"
                  data-testid="quote-number-input"
                  type="text"
                  :readonly="quoteNoMode === 'auto'"
                  class="w-full rounded-lg border p-2 font-mono focus:border-blue-500 focus:outline-hidden"
                  :class="[
                    quoteNoIsUnique
                      ? 'border-dm-border bg-white text-dm-text'
                      : 'border-red-400 bg-red-50/30 text-red-700',
                    quoteNoMode === 'auto' ? 'cursor-default' : '',
                  ]"
                />
                <p
                  class="mt-1 text-[10px] font-medium"
                  :class="quoteNoIsUnique ? 'text-dm-text-tertiary' : 'text-red-500'"
                >
                  {{
                    quoteNoIsUnique
                      ? t('quotation.pages.create.quoteNumberHintUnique')
                      : t('quotation.pages.create.quoteNumberHintDuplicate')
                  }}
                </p>
                <p v-if="errors.quoteNo" class="mt-1 text-[10px] text-red-500">{{ errors.quoteNo }}</p>
              </div>
            </div>
          </div>

          <!-- Step 2 -->
          <div class="space-y-4 dm-card p-5 shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <User class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step2Title') }}</h3>
            </div>

            <div class="grid grid-cols-1 gap-4 text-xs sm:grid-cols-2">
              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.customerCompany') }}
                  <span class="text-red-500">*</span>
                </label>
                <HistoryTextInput
                  test-id="customer-company-input"
                  :model-value="clientCompany"
                  :options="
                    customerCompanyOptions.map((record) => ({
                      value: record.clientCompany,
                      label: getCompanyOptionLabel(customerHistory, record.clientCompany),
                      key: record.clientCompany,
                      meta: record,
                    }))
                  "
                  :placeholder="t('quotation.pages.create.customerCompanyPlaceholder')"
                  :helper-text="t('quotation.pages.create.customerCompanyHelper')"
                  :error="errors.clientCompany"
                  @update:model-value="handleClientCompanyInput"
                  @select-option="handleClientCompanySelect"
                />
              </div>

              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.customerContact') }}
                  <span class="text-red-500">*</span>
                </label>
                <HistoryTextInput
                  test-id="customer-contact-input"
                  :model-value="contactPerson"
                  :options="
                    customerContactOptions.map((record) => ({
                      value: record.contactPerson,
                      label: record.email,
                      key: `${record.clientCompany}-${record.contactPerson}-${record.email}`,
                      meta: record,
                    }))
                  "
                  :placeholder="t('quotation.pages.create.customerContactPlaceholder')"
                  :error="errors.contactPerson"
                  @update:model-value="handleContactPersonInput"
                  @select-option="handleContactPersonSelect"
                />
              </div>

              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.customerEmail') }}
                  <span class="text-red-500">*</span>
                </label>
                <HistoryTextInput
                  test-id="customer-email-input"
                  type="email"
                  :model-value="email"
                  :options="
                    customerEmailOptions.map((record) => ({
                      value: record.email,
                      label: record.contactPerson,
                      key: `${record.clientCompany}-${record.contactPerson}-${record.email}`,
                      meta: record,
                    }))
                  "
                  :placeholder="t('quotation.pages.create.customerEmailPlaceholder')"
                  :error="errors.email"
                  @update:model-value="handleEmailInput"
                  @select-option="handleEmailSelect"
                />
              </div>

              <div
                class="grid grid-cols-1 gap-3 rounded-lg border border-dm-border-light bg-[#fafafa]/60 p-3 sm:col-span-2 sm:grid-cols-3"
              >
                <div class="flex items-center justify-between sm:col-span-3">
                  <span class="text-[11px] font-bold uppercase tracking-wider text-dm-text-tertiary">
                    {{ t('quotation.pages.create.billToSection') }}
                  </span>
                  <button
                    type="button"
                    class="cursor-pointer text-[10px] font-semibold text-dm-primary hover:text-blue-700"
                    @click="
                      () => {
                        billingCompany = clientCompany
                        billingContact = contactPerson
                        billingEmail = email
                      }
                    "
                  >
                    {{ t('quotation.actions.syncShipTo') }}
                  </button>
                </div>
                <div>
                  <label class="mb-1 block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.billToCompany') }}
                  </label>
                  <HistoryTextInput
                    test-id="billing-company-input"
                    :model-value="billingCompany"
                    :options="
                      billingCompanyOptions.map((record) => ({
                        value: record.billingCompany,
                        label: getBillingCompanyOptionLabel(billingHistory, record.billingCompany),
                        key: record.billingCompany,
                        meta: record,
                      }))
                    "
                    :placeholder="t('quotation.pages.create.billToCompanyPlaceholder')"
                    @update:model-value="handleBillingCompanyInput"
                    @select-option="handleBillingCompanySelect"
                  />
                </div>
                <div>
                  <label class="mb-1 block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.billToContact') }}
                  </label>
                  <HistoryTextInput
                    test-id="billing-contact-input"
                    :model-value="billingContact"
                    :options="
                      billingContactOptions.map((record) => ({
                        value: record.billingContact,
                        label: record.billingEmail,
                        key: `${record.billingCompany}-${record.billingContact}-${record.billingEmail}`,
                        meta: record,
                      }))
                    "
                    :placeholder="t('quotation.pages.create.billToContactPlaceholder')"
                    @update:model-value="handleBillingContactInput"
                    @select-option="handleBillingContactSelect"
                  />
                </div>
                <div>
                  <label class="mb-1 block font-semibold text-dm-text-tertiary">
                    {{ t('quotation.pages.create.billToEmail') }}
                  </label>
                  <HistoryTextInput
                    test-id="billing-email-input"
                    type="email"
                    :model-value="billingEmail"
                    :options="
                      billingEmailOptions.map((record) => ({
                        value: record.billingEmail,
                        label: `${record.billingCompany} / ${record.billingContact}`,
                        key: `${record.billingCompany}-${record.billingContact}-${record.billingEmail}`,
                        meta: record,
                      }))
                    "
                    :placeholder="t('quotation.pages.create.billToEmailPlaceholder')"
                    @update:model-value="handleBillingEmailInput"
                    @select-option="handleBillingEmailSelect"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Step 3 -->
          <div class="space-y-4 dm-card p-5 text-xs shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <Briefcase class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step3Title') }}</h3>
            </div>

            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.contactPerson') }}
                  <span class="text-red-500">*</span>
                </label>
                <input
                  :value="issuerContactName"
                  type="text"
                  :placeholder="currentUser?.name || t('quotation.pages.create.contactPersonPlaceholder')"
                  class="w-full rounded-lg border p-2 focus:border-blue-500 focus:outline-hidden"
                  :class="errors.issuerContactName ? 'border-red-400 bg-red-50/20' : 'border-dm-border'"
                  @input="
                    (e) => {
                      const value = (e.target as HTMLInputElement).value
                      issuerContactName = value
                      salesperson = value
                    }
                  "
                />
                <p class="mt-1 text-[10px] text-dm-text-tertiary">
                  {{ t('quotation.pages.create.contactPersonHelper') }}
                </p>
                <p v-if="errors.issuerContactName" class="mt-1 text-[10px] text-red-500">
                  {{ errors.issuerContactName }}
                </p>
              </div>

              <div>
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.issuerEmail') }}
                  <span class="text-red-500">*</span>
                </label>
                <input
                  v-model="issuerContactEmail"
                  type="email"
                  :placeholder="currentUser?.email || t('quotation.pages.create.issuerEmailPlaceholder')"
                  class="w-full rounded-lg border p-2 focus:border-blue-500 focus:outline-hidden"
                  :class="errors.issuerContactEmail ? 'border-red-400 bg-red-50/20' : 'border-dm-border'"
                />
                <p v-if="errors.issuerContactEmail" class="mt-1 text-[10px] text-red-500">
                  {{ errors.issuerContactEmail }}
                </p>
              </div>

              <div class="sm:col-span-2">
                <label class="mb-1 block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.projectName') }}
                  <span class="text-red-500">*</span>
                </label>
                <input
                  v-model="projectName"
                  type="text"
                  :placeholder="t('quotation.pages.create.projectNamePlaceholder')"
                  class="w-full rounded-lg border p-2 focus:border-blue-500 focus:outline-hidden"
                  :class="errors.projectName ? 'border-red-400 bg-red-50/20' : 'border-dm-border'"
                />
                <p v-if="errors.projectName" class="mt-1 text-[10px] text-red-500">{{ errors.projectName }}</p>
              </div>
            </div>

            <div>
              <label class="mb-1 block font-semibold text-dm-text-tertiary">
                {{ t('quotation.pages.create.paymentTerm') }}
              </label>
              <FormSelect
                test-id="payment-term-select"
                :model-value="paymentTermOption"
                :options="paymentTermSelectOptions"
                @update:model-value="(value) => (paymentTermOption = value as PaymentTermOption)"
              />
              <textarea
                v-if="paymentTermOption === 'Others'"
                v-model="paymentTermsCustom"
                data-testid="payment-term-custom-input"
                :placeholder="t('quotation.pages.create.paymentTermCustomPlaceholder')"
                rows="3"
                class="mt-2 w-full resize-y rounded-lg border p-2 focus:border-blue-500 focus:outline-hidden"
                :class="errors.paymentTerms ? 'border-red-400 bg-red-50/20' : 'border-dm-border'"
              />
              <p v-if="errors.paymentTerms" class="mt-1 text-[10px] text-red-500">{{ errors.paymentTerms }}</p>
            </div>

            <div>
              <label class="mb-1 block font-semibold text-dm-text-tertiary">
                {{ t('quotation.pages.create.currency') }}
              </label>
              <FormSelect
                test-id="currency-select"
                :model-value="currency"
                :options="currencyOptions"
                @update:model-value="(value) => (currency = value as 'CNY' | 'USD' | 'EUR')"
              />
            </div>
          </div>

          <!-- Step 4 -->
          <div class="space-y-4 dm-card p-5 shadow-xs">
            <div class="flex items-center justify-between border-b border-slate-50 pb-2">
              <div class="flex items-center gap-2">
                <Layers class="h-4 w-4 text-dm-text-tertiary" />
                <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step4Title') }}</h3>
              </div>
              <button
                type="button"
                class="flex cursor-pointer items-center gap-1 rounded-md border border-dashed border-blue-400 px-2.5 py-1.5 text-xs font-semibold text-dm-primary transition duration-150 hover:bg-dm-primary-bg/50"
                @click="handleAddLineItem"
              >
                <Plus class="h-3.5 w-3.5" />
                {{ t('quotation.actions.addLineItem') }}
              </button>
            </div>

            <div
              v-if="itemErrorEntries.length"
              class="space-y-1 rounded-lg border border-red-100 bg-red-50 p-3 text-xs text-red-600"
            >
              <p class="font-semibold">{{ t('quotation.pages.create.lineItemErrorsTitle') }}</p>
              <ul class="list-disc space-y-0.5 pl-4">
                <li v-for="[key, msg] in itemErrorEntries" :key="key">{{ msg }}</li>
              </ul>
            </div>

            <div class="space-y-4">
              <div
                v-for="(item, index) in items"
                :key="item.id"
                class="group relative space-y-3 rounded-xl border border-dm-border-light bg-[#fafafa]/40 p-4 transition duration-150 hover:bg-[#fafafa]"
              >
                <span
                  class="absolute -left-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full border border-white bg-slate-200 text-xs font-bold text-dm-text"
                >
                  {{ index + 1 }}
                </span>
                <button
                  type="button"
                  class="absolute right-2 top-2 cursor-pointer rounded-sm p-1.5 text-dm-text-tertiary transition duration-150 hover:bg-red-50 hover:text-red-500"
                  @click="handleRemoveLineItem(item.id)"
                >
                  <Trash2 class="h-4 w-4" />
                </button>

                <div class="grid grid-cols-1 gap-4 text-xs sm:grid-cols-2 2xl:grid-cols-4">
                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemCategory') }}
                    </label>
                    <FormSelect
                      test-id="line-item-category-select"
                      :model-value="item.type"
                      :options="[
                        { value: 'Software', label: t('quotation.pages.create.lineItemSoftware') },
                        { value: 'Other', label: t('quotation.pages.create.lineItemOthers') },
                      ]"
                      @update:model-value="
                        (nextType) => handleRowChange(item.id, { type: nextType as ItemType })
                      "
                    />
                  </div>

                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemNumber') }}
                    </label>
                    <div
                      data-testid="line-item-auto-number"
                      class="w-full rounded-lg border border-dm-border bg-slate-100 p-2 font-mono text-dm-text"
                    >
                      {{ autoItemNumber(index, item.type) }}
                    </div>
                    <p class="mt-1 text-[10px] text-dm-text-tertiary">
                      {{
                        t('quotation.pages.create.lineItemAutoNumberHint', {
                          type:
                            item.type === 'Software'
                              ? t('quotation.pages.create.lineItemSoftware')
                              : t('quotation.pages.create.lineItemOthers'),
                        })
                      }}
                    </p>
                  </div>

                  <div class="sm:col-span-2">
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemDescription') }}
                    </label>
                    <HistoryTextInput
                      multiline
                      :rows="2"
                      test-id="line-item-description-input"
                      :placeholder="t('quotation.pages.create.lineItemDescriptionPlaceholder')"
                      :model-value="item.description || ''"
                      :options="descriptionOptionsFor(item.type)"
                      :helper-text="t('quotation.pages.create.lineItemDescriptionHelper')"
                      @update:model-value="
                        (value) =>
                          handleRowChange(item.id, {
                            description: value,
                          })
                      "
                      @select-option="(option) => handleDescriptionSelect(item, option)"
                    />
                  </div>

                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemListPrice') }}
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      :value="item.listPrice || ''"
                      placeholder="0"
                      class="w-full rounded-lg border border-dm-border bg-white p-2 font-mono text-dm-text focus:border-blue-500 focus:outline-hidden"
                      @input="
                        (e) =>
                          handleRowChange(item.id, {
                            listPrice: parseFloat((e.target as HTMLInputElement).value) || 0,
                          })
                      "
                    />
                  </div>

                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemDiscount') }}
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.01"
                      :value="item.discountPercent || ''"
                      placeholder="0"
                      class="w-full rounded-lg border border-dm-border bg-white p-2 font-mono text-dm-text focus:border-blue-500 focus:outline-hidden"
                      @input="
                        (e) => {
                          const rawValue = parseFloat((e.target as HTMLInputElement).value)
                          const discountPercent = Number.isFinite(rawValue)
                            ? Math.min(100, Math.max(0, rawValue))
                            : 0
                          handleRowChange(item.id, { discountPercent })
                        }
                      "
                    />
                  </div>

                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemQty') }}
                    </label>
                    <input
                      type="number"
                      min="1"
                      :value="item.qty || ''"
                      class="w-full rounded-lg border border-dm-border bg-white p-2 font-mono text-dm-text focus:outline-hidden"
                      @input="
                        (e) =>
                          handleRowChange(item.id, {
                            qty: Math.max(1, parseInt((e.target as HTMLInputElement).value) || 1),
                          })
                      "
                    />
                  </div>

                  <div class="flex flex-col justify-end">
                    <span class="text-[10px] font-medium text-dm-text-tertiary">
                      {{ t('quotation.pages.create.lineItemSubtotal') }}
                    </span>
                    <p class="pt-2 font-mono text-sm font-bold text-dm-text">
                      {{ currencySymbol }}{{ item.extendedPrice.toLocaleString() }}
                    </p>
                    <p class="font-mono text-[10px] text-emerald-500">
                      {{
                        t('quotation.pages.create.lineItemNetUnit', {
                          amount: `${currencySymbol}${item.netUnitPrice.toLocaleString()}`,
                        })
                      }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-6">
          <!-- Step 5 -->
          <div class="relative space-y-4 overflow-hidden dm-card p-5 text-xs shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <DollarSign class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step5Title') }}</h3>
            </div>

            <div class="space-y-2 font-medium text-dm-text-secondary">
              <div class="flex justify-between">
                <span>{{ t('quotation.pages.create.summarySoftware') }}</span>
                <span class="font-mono font-bold text-dm-text">
                  {{ currencySymbol }}{{ softwareSubtotal.toLocaleString() }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>{{ t('quotation.pages.create.summaryOthers') }}</span>
                <span class="font-mono font-bold text-dm-text">
                  {{ currencySymbol }}{{ othersSubtotal.toLocaleString() }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>
                  {{
                    t('quotation.pages.create.summaryBeforeTax', {
                      taxLabel: resolveTaxLabel(taxLabel),
                    })
                  }}
                </span>
                <span class="font-mono font-bold text-dm-text">
                  {{ currencySymbol }}{{ subtotalBeforeVat.toLocaleString() }}
                </span>
              </div>
              <div
                class="grid grid-cols-1 items-end gap-3 rounded-lg border border-dm-border-light bg-[#fafafa]/70 p-3 sm:grid-cols-[1fr_auto]"
              >
                <div class="space-y-3">
                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{ t('quotation.pages.create.taxLabel') }}
                    </label>
                    <HistoryTextInput
                      test-id="quote-tax-label-input"
                      v-model="taxLabel"
                      :options="taxLabelHistory"
                      :placeholder="t('quotation.pages.create.taxLabelPlaceholder')"
                      :error="errors.taxLabel"
                      :helper-text="t('quotation.pages.create.taxLabelHelper')"
                    />
                  </div>
                  <div>
                    <label class="mb-1 block font-semibold text-dm-text-tertiary">
                      {{
                        t('quotation.pages.create.taxRate', {
                          taxLabel: resolveTaxLabel(taxLabel),
                        })
                      }}
                    </label>
                    <input
                      v-model="vatRateInput"
                      @input="handleVatRateInput"
                      data-testid="quote-vat-rate-input"
                      type="text"
                      inputmode="decimal"
                      pattern="[0-9]*[.]?[0-9]{0,2}"
                      maxlength="6"
                      :placeholder="t('quotation.pages.create.taxRatePlaceholder')"
                      class="w-full rounded-lg border bg-white p-2 font-mono text-dm-text placeholder:text-slate-300 focus:border-blue-500 focus:outline-hidden"
                      :class="errors.vatRate ? 'border-red-400 bg-red-50/20' : 'border-dm-border'"
                    />
                    <p v-if="errors.vatRate" class="mt-1 text-[10px] text-red-500">{{ errors.vatRate }}</p>
                    <p class="mt-1 text-[10px] font-medium text-dm-text-tertiary">
                      {{ t('quotation.pages.create.taxRateHelper') }}
                    </p>
                  </div>
                </div>
                <div class="text-right">
                  <span class="block text-[10px] font-semibold text-dm-text-tertiary">
                    {{
                      t('quotation.pages.create.taxAmount', {
                        taxLabel: resolveTaxLabel(taxLabel),
                      })
                    }}
                  </span>
                  <span class="font-mono font-bold text-dm-text">
                    {{ currencySymbol }}{{ vatAmount.toLocaleString() }}
                  </span>
                </div>
              </div>
              <div
                class="my-2 flex justify-between border-t border-dm-border-light pt-2 text-base font-extrabold text-dm-text"
              >
                <span class="text-dm-primary">{{ t('quotation.pages.create.grandTotal') }}</span>
                <span class="font-mono text-dm-primary">
                  {{ currencySymbol }}{{ grandTotal.toLocaleString() }}
                </span>
              </div>
            </div>
          </div>

          <!-- Step 6 -->
          <div class="space-y-4 dm-card p-5 text-xs shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <FileText class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step6Title') }}</h3>
            </div>
            <div>
              <div class="mb-1 flex items-center justify-between gap-3">
                <label class="block font-semibold text-dm-text-tertiary">
                  {{ t('quotation.pages.create.remarksLabel') }}
                </label>
                <button
                  type="button"
                  class="cursor-pointer text-[10px] font-semibold text-dm-primary hover:text-blue-700"
                  @click="remarksDisclaimer = DEFAULT_REMARKS_DISCLAIMER"
                >
                  {{ t('quotation.actions.showTemplate') }}
                </button>
              </div>
              <textarea
                v-model="remarksDisclaimer"
                rows="8"
                :placeholder="t('quotation.pages.create.remarksPlaceholder')"
                class="w-full rounded-lg border border-dm-border p-2 leading-relaxed text-dm-text focus:border-blue-500 focus:outline-hidden"
              />
              <p class="mt-1 text-[10px] font-medium text-dm-text-tertiary">
                {{ t('quotation.pages.create.remarksHint') }}
              </p>
            </div>
          </div>

          <div class="space-y-3 dm-card p-5 shadow-xs">
            <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
              <PenLine class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-bold text-dm-text">{{ t('quotation.pages.create.step7Title') }}</h3>
            </div>
            <SignaturePicker
              :model-value="issuerSignature"
              :user-email="currentUser?.email"
              @update:model-value="
                (signature) => {
                  issuerSignature = signature
                  if (currentUser?.email) {
                    rememberUserSignature(currentUser.email, signature)
                  }
                }
              "
            />
            <p class="text-[10px] font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.create.signatureHint') }}
            </p>
          </div>

          <div class="space-y-2 pt-2">
            <button
              type="button"
              class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-dm-primary py-3 text-xs font-bold text-white shadow-xs transition duration-150 hover:bg-dm-primary-hover active:bg-blue-700"
              @click="handleSubmit('Generated')"
            >
              <FileSpreadsheet class="h-4 w-4" />
              {{ t('quotation.actions.saveAndGenerate') }}
            </button>
            <button
              type="button"
              class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-dm-border bg-[#fafafa] py-2.5 text-xs font-semibold text-dm-text transition duration-150 hover:bg-slate-100"
              @click="handleSubmit('Draft')"
            >
              <Save class="h-4 w-4" />
              {{ t('quotation.actions.saveDraft') }}
            </button>
            <button
              type="button"
              class="block w-full cursor-pointer py-1 text-center text-[11px] font-semibold text-dm-text-tertiary transition duration-150 hover:text-dm-text-secondary"
              @click="emit('navigateToTab', 'list')"
            >
              {{ t('quotation.actions.cancelAndReturn') }}
            </button>
          </div>
        </div>
      </div>

      <button
        type="button"
        data-testid="quote-preview-resizer"
        class="group relative hidden w-6 shrink-0 cursor-col-resize items-center justify-center xl:sticky xl:top-6 xl:flex xl:h-[calc(100vh-3rem)] xl:self-start"
        :aria-label="t('quotation.pages.create.previewResizeLabel')"
        :title="t('quotation.pages.create.previewResizeTitle')"
        @pointerdown="handleResizeStart"
      >
        <span
          class="h-full w-0.5 rounded-full bg-slate-200 transition group-hover:bg-dm-primary group-active:bg-dm-primary"
        />
        <span
          class="absolute top-1/2 h-20 w-1.5 -translate-y-1/2 rounded-full bg-slate-400 shadow-sm transition group-hover:bg-dm-primary group-active:bg-dm-primary"
        />
      </button>

      <div
        data-testid="quote-preview-pane"
        class="xl:sticky xl:top-6 xl:flex xl:min-w-[520px] xl:basis-[calc(var(--preview-pane-width)-8px)] xl:self-start xl:pl-3"
        :style="{ '--preview-pane-width': `${previewWidthPercent}%` }"
      >
        <div class="flex w-full flex-col">
          <div
            class="max-h-[calc(100vh-96px)] overflow-x-auto overflow-y-auto rounded-xl border border-dm-border bg-slate-100 p-3 shadow-inner"
          >
            <QuotationPreview :quote="previewQuote" :current-user="currentUser" scale="compact" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
