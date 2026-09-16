<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeft, FileText } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { getInvoice, type InvoiceRecord } from '../../api/invoices'
import InvoicePreview, {
  type InvoicePreviewData,
} from './InvoicePreview.vue'

const { locale, t } = useI18n()
const route = useRoute()
const props = withDefaults(defineProps<{
  invoiceId?: string
  embedded?: boolean
}>(), {
  invoiceId: '',
  embedded: false,
})
const invoice = ref<InvoiceRecord | null>(null)
const loading = ref(false)
const error = ref('')
const resolvedInvoiceId = computed(() =>
  props.invoiceId || String(route.params.invoiceId || ''),
)

const previewInvoice = computed<InvoicePreviewData | null>(() => {
  const record = invoice.value
  if (!record) return null
  return {
    invoiceNumber: record.invoice_no,
    documentKind: record.document_kind,
    invoiceDate: record.invoice_date || '',
    currency: record.currency,
    sellerName: record.seller_name,
    sellerAddress: record.seller_address,
    sellerWebsite: record.seller_website,
    sellerEmail: record.seller_email,
    customerName: record.customer_name,
    customerTaxId: record.customer_tax_id,
    customerAddress: record.customer_address,
    customerContactPerson:
      record.customer_contact_person || record.contact_person,
    customerContactEmail:
      record.customer_contact_email || record.contact_email,
    customerContactPhone: record.customer_contact_phone,
    contactPerson: record.contact_person,
    contactEmail: record.contact_email,
    purchaseOrderNo: record.purchase_order_no,
    paymentTerms: record.payment_terms,
    additionalNotes: record.additional_notes,
    remarks: record.remarks,
    bankAccountName: record.bank_account_name,
    bankName: record.bank_name,
    bankAddress: record.bank_address,
    bankAccountNumber: record.bank_account_number,
    bankCode: record.bank_code,
    bankBranchCode: record.bank_branch_code,
    bankSwiftCode: record.bank_swift_code,
    remittanceInstruction: record.remittance_instruction,
    signatoryName: record.signatory_name,
    signatoryTitle: record.signatory_title,
    signature: record.issuer_signature,
    items: record.items.map((item) => ({
      id: item.id,
      description: item.description,
      quantity: Number(item.quantity),
      unitPrice: Number(item.unit_price),
    })),
  }
})

const formattedAmount = computed(() => {
  const record = invoice.value
  if (!record) return '—'
  return new Intl.NumberFormat(locale.value, {
    style: 'currency',
    currency: record.currency,
    currencyDisplay: 'narrowSymbol',
  }).format(Number(record.total_amount || 0))
})

async function loadInvoice() {
  loading.value = true
  error.value = ''
  try {
    invoice.value = await getInvoice(resolvedInvoiceId.value)
  } catch (loadError: unknown) {
    error.value =
      loadError instanceof Error
        ? loadError.message
        : t('quotation.sales.detail.loadFailed')
  } finally {
    loading.value = false
  }
}

watch(resolvedInvoiceId, loadInvoice, { immediate: true })
</script>

<template>
  <div
    class="mx-auto w-full space-y-5"
    :class="embedded ? 'max-w-none' : 'max-w-[1500px]'"
  >
    <router-link
      v-if="!embedded"
      to="/quotation/sales/invoices"
      class="inline-flex items-center gap-1 text-sm font-medium text-dm-primary hover:underline"
    >
      <ArrowLeft class="h-4 w-4" />
      {{ t('quotation.sales.detail.back') }}
    </router-link>

    <div
      v-if="error"
      class="rounded-dm border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="loading"
      class="dm-card flex min-h-64 items-center justify-center text-sm text-dm-text-tertiary"
    >
      {{ t('quotation.sales.loading') }}
    </div>

    <template v-else-if="invoice && previewInvoice">
      <template v-if="!embedded">
        <header class="dm-card flex flex-wrap items-start justify-between gap-4 p-5">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-dm-primary">
            {{ t('quotation.sales.detail.title') }}
          </p>
          <div class="mt-1 flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-semibold text-dm-text">
              {{ invoice.invoice_no }}
            </h1>
            <span class="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              {{ t(`quotation.sales.statuses.${invoice.status}`) }}
            </span>
          </div>
          <p class="mt-1 text-sm text-dm-text-tertiary">
            {{ t('quotation.sales.detail.subtitle') }}
          </p>
        </div>
        </header>

        <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="dm-card p-4">
          <p class="text-xs text-dm-text-tertiary">
            {{ t('quotation.sales.customer') }}
          </p>
          <p class="mt-1 font-semibold text-dm-text">
            {{ invoice.customer_name }}
          </p>
        </div>
        <div class="dm-card p-4">
          <p class="text-xs text-dm-text-tertiary">
            {{ t('quotation.sales.invoiceDate') }}
          </p>
          <p class="mt-1 font-semibold text-dm-text">
            {{ invoice.invoice_date }}
          </p>
        </div>
        <div class="dm-card p-4">
          <p class="text-xs text-dm-text-tertiary">
            {{ t('quotation.sales.total') }}
          </p>
          <p class="mt-1 font-semibold text-dm-text">
            {{ formattedAmount }}
          </p>
        </div>
        <div class="dm-card p-4">
          <p class="text-xs text-dm-text-tertiary">
            {{ t('quotation.sales.source') }}
          </p>
          <p class="mt-1 font-semibold text-dm-text">
            {{ t(`quotation.sales.sources.${invoice.source_type}`) }}
          </p>
        </div>
        </section>
      </template>

      <section class="dm-card p-4">
        <div class="mb-3 flex items-center gap-2">
          <FileText class="h-4 w-4 text-dm-primary" />
          <h2 class="text-sm font-semibold text-dm-text">
            {{ t('quotation.sales.detail.document') }}
          </h2>
        </div>
        <div class="overflow-auto rounded-xl border border-dm-border bg-slate-200 p-3">
          <InvoicePreview :invoice="previewInvoice" />
        </div>
      </section>
    </template>
  </div>
</template>
