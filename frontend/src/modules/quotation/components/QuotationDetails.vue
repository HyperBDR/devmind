<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  Ban,
  CheckCircle,
  Clock,
  Download,
  FileDown,
  FileSpreadsheet,
  FileText,
  Pencil,
  Send,
  Settings,
  XCircle,
} from 'lucide-vue-next'
import type { Quotation, QuoteStatus, QuoteVersion } from '../types'
import { listAuditEvents, type AuditEvent } from '../api/audit'
import { downloadQuotationExcel } from '../utils/excelGenerator'
import { downloadQuotationPdf } from '../utils/pdfExporter'
import { recordQuotationDownload } from '../api/quotations'
import { buildQuotationExportFileName } from '../utils/quotationFileName'
import type { PreviewUser } from '../utils/quotationPreviewModel'
import { getCurrencySymbol } from '../utils/quotationPreviewModel'
import {
  diffVersionAgainstCurrent,
  isFieldChanged,
  type VersionDiffFieldKey,
  type VersionDiffResult,
} from '../utils/versionDiff'
import QuotationPreview from './QuotationPreview.vue'
import StatusBadge from './StatusBadge.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const { t } = useQuotationI18n()

const props = defineProps<{
  quote: Quotation
  currentUser?: PreviewUser
}>()

const emit = defineEmits<{
  back: []
  updateQuoteStatus: [id: string, updatedFields: Partial<Quotation>, notes?: string]
  editQuote: [id: string]
}>()

const selectedVersionForModal = ref<QuoteVersion | null>(null)
const activityEvents = ref<AuditEvent[]>([])

async function loadActivity() {
  const response = await listAuditEvents({
    quotationId: props.quote.id,
    pageSize: 8,
  })
  activityEvents.value = response.items.filter(
    (event) => event.event_name !== 'audit.viewed',
  )
}

function activityActor(event: AuditEvent) {
  return event.actor_name || event.actor_email || t('quotation.pages.audit.system')
}

function activityTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

watch(() => props.quote.id, () => void loadActivity())
onMounted(() => void loadActivity())

const currencySymbol = computed(() => getCurrencySymbol(props.quote.currency))

const displayVersion = computed(() => {
  const ver = selectedVersionForModal.value
  if (!ver) return null
  const q = props.quote
  return {
    ...ver,
    projectName: ver.projectName || q.projectName,
    clientCompany: ver.clientCompany || q.clientCompany,
    contactPerson: ver.contactPerson || q.contactPerson,
    email: ver.email || q.email,
    productLine: ver.productLine || q.productLine,
    billingCompany: ver.billingCompany || q.billingCompany,
    billingContact: ver.billingContact || q.billingContact,
    billingEmail: ver.billingEmail || q.billingEmail,
    currency: ver.currency || q.currency,
    paymentTerms: ver.paymentTerms || q.paymentTerms,
    paymentTermOption: ver.paymentTermOption || q.paymentTermOption,
    remarksDisclaimer: ver.remarksDisclaimer ?? q.remarksDisclaimer,
    issuerCompanyName: ver.issuerCompanyName || q.issuerCompanyName,
    issuerContactName: ver.issuerContactName || q.issuerContactName,
    issuerContactEmail: ver.issuerContactEmail || q.issuerContactEmail,
    issuerContactTitle: ver.issuerContactTitle || q.issuerContactTitle,
    issuerSignature: ver.issuerSignature || q.issuerSignature,
    taxLabel: ver.taxLabel || q.taxLabel,
    quoteDate: ver.quoteDate || q.quoteDate,
    expireDate: ver.expireDate || q.expireDate,
  }
})

const versionCurrencySymbol = computed(() =>
  displayVersion.value
    ? getCurrencySymbol(displayVersion.value.currency)
    : currencySymbol.value,
)

const snapshotQuote = computed((): Quotation | null => {
  const ver = displayVersion.value
  if (!ver) return null
  return {
    ...props.quote,
    projectName: ver.projectName,
    clientCompany: ver.clientCompany,
    contactPerson: ver.contactPerson,
    email: ver.email,
    productLine: ver.productLine,
    billingCompany: ver.billingCompany,
    billingContact: ver.billingContact,
    billingEmail: ver.billingEmail,
    region: ver.region,
    industry: ver.industry,
    salesperson: ver.salesperson,
    currency: ver.currency,
    paymentTermOption: ver.paymentTermOption,
    paymentTerms: ver.paymentTerms,
    quoteDate: ver.quoteDate || props.quote.quoteDate,
    expireDate: ver.expireDate || props.quote.expireDate,
    remarksDisclaimer: ver.remarksDisclaimer ?? '',
    issuerCompanyName: ver.issuerCompanyName || props.quote.issuerCompanyName,
    issuerContactName: ver.issuerContactName || props.quote.issuerContactName,
    issuerContactEmail:
      ver.issuerContactEmail || props.quote.issuerContactEmail,
    issuerContactTitle:
      ver.issuerContactTitle || props.quote.issuerContactTitle,
    issuerSignature: ver.issuerSignature ?? '',
    status: ver.status,
    items: ver.items,
    softwareSubtotal: ver.softwareSubtotal,
    othersSubtotal: ver.othersSubtotal,
    subtotalBeforeVat: ver.subtotalBeforeVat,
    taxLabel: ver.taxLabel || props.quote.taxLabel,
    vatRate: ver.vatRate,
    vatAmount: ver.vatAmount,
    grandTotal: ver.grandTotal,
    versions: undefined,
  }
})

const cancelledVersion = computed(() => props.quote.versions?.find((v) => v.status === 'Cancelled'))
const cancelReason = computed(() =>
  cancelledVersion.value
    ? cancelledVersion.value.notes
    : t('quotation.pages.details.noCancelReason'),
)

const reversedVersions = computed(() =>
  props.quote.versions ? [...props.quote.versions].reverse() : [],
)

const FIELD_LABEL_KEYS: Record<VersionDiffFieldKey, string> = {
  projectName: 'quotation.pages.details.diffFieldProjectName',
  clientCompany: 'quotation.pages.details.diffFieldClientCompany',
  contactPerson: 'quotation.pages.details.diffFieldContactPerson',
  email: 'quotation.pages.details.diffFieldEmail',
  billingCompany: 'quotation.pages.details.diffFieldBillingCompany',
  billingContact: 'quotation.pages.details.diffFieldBillingContact',
  billingEmail: 'quotation.pages.details.diffFieldBillingEmail',
  currency: 'quotation.pages.details.diffFieldCurrency',
  paymentTerms: 'quotation.pages.details.diffFieldPaymentTerms',
  status: 'quotation.pages.details.diffFieldStatus',
  grandTotal: 'quotation.pages.details.diffFieldGrandTotal',
  taxLabel: 'quotation.pages.details.diffFieldTaxLabel',
  vatRate: 'quotation.pages.details.diffFieldVatRate',
  salesperson: 'quotation.pages.details.diffFieldSalesperson',
  quoteDate: 'quotation.pages.details.diffFieldQuoteDate',
  expireDate: 'quotation.pages.details.diffFieldExpireDate',
  remarksDisclaimer: 'quotation.pages.details.diffFieldRemarksDisclaimer',
}

function getVersionDiff(version: QuoteVersion): VersionDiffResult {
  return diffVersionAgainstCurrent(version, props.quote)
}

const activeVersionDiff = computed(() => {
  const ver = selectedVersionForModal.value
  if (!ver) return null
  return getVersionDiff(ver)
})

const activeDiffSummaryLabels = computed(() => {
  const diff = activeVersionDiff.value
  if (!diff) return []
  const labels = [...diff.changedFields].map((field) => t(FIELD_LABEL_KEYS[field]))
  if (diff.changedLineIds.size > 0 || diff.addedLineCount > 0) {
    labels.push(
      t('quotation.pages.details.diffFieldLineItems', {
        count: diff.changedLineIds.size + diff.addedLineCount,
      }),
    )
  }
  return labels
})

const versionDiffChips = computed(() => {
  const map = new Map<string, string>()
  ;(props.quote.versions || []).forEach((version) => {
    const chip = diffChipForVersion(version)
    if (chip) map.set(version.id, chip)
  })
  return map
})

function changedValueClass(field: VersionDiffFieldKey): string {
  return isFieldChanged(activeVersionDiff.value, field)
    ? 'font-bold text-rose-600'
    : 'font-bold text-dm-text'
}

function diffChipForVersion(version: QuoteVersion): string | null {
  const diff = getVersionDiff(version)
  if (!diff.hasChanges) return null
  const count =
    diff.changedFields.size + (diff.changedLineIds.size > 0 ? 1 : 0)
  return t('quotation.pages.details.diffChipVsCurrent', { count })
}

function formatNow() {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')} ${String(today.getHours()).padStart(2, '0')}:${String(today.getMinutes()).padStart(2, '0')}:${String(today.getSeconds()).padStart(2, '0')}`
}

async function handleGenerateExcel() {
  const success = await downloadQuotationExcel(props.quote, props.currentUser)
  if (success) {
    await recordQuotationDownload(props.quote.id, 'excel').catch(() => undefined)
    emit('updateQuoteStatus', props.quote.id, {
      status: 'Generated',
      excelGeneratedAt: formatNow(),
      excelFileName: buildQuotationExportFileName(props.quote, 'xlsx'),
    })
  }
}

async function handleDownloadExcel() {
  if (props.quote.status === 'Cancelled') {
    alert(t('quotation.pages.details.alertCancelledDownload'))
    return
  }
  const success = await downloadQuotationExcel(props.quote, props.currentUser)
  if (success) {
    await recordQuotationDownload(props.quote.id, 'excel').catch(() => undefined)
    const formattedDate = formatNow()
    const fileName = buildQuotationExportFileName(props.quote, 'xlsx')
    if (props.quote.status === 'Draft') {
      emit('updateQuoteStatus', props.quote.id, {
        status: 'Generated',
        excelGeneratedAt: formattedDate,
        excelFileName: fileName,
      })
    } else {
      emit('updateQuoteStatus', props.quote.id, {
        excelGeneratedAt: formattedDate,
        excelFileName: fileName,
      })
    }
  }
}

async function handleExportPdf() {
  if (props.quote.status === 'Cancelled') return
  const success = await downloadQuotationPdf(props.quote, props.currentUser)
  if (success) {
    await recordQuotationDownload(props.quote.id, 'pdf').catch(() => undefined)
  }
}

function setStatus(status: QuoteStatus) {
  emit('updateQuoteStatus', props.quote.id, { status })
}
</script>

<template>
  <div id="quote-details-root" class="mx-auto max-w-[1400px] space-y-6">
    <div
      v-if="quote.status === 'Cancelled'"
      class="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"
    >
      <Ban class="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
      <div class="flex-1 space-y-1.5">
        <h4 class="text-sm font-extrabold text-rose-800">{{ t('quotation.pages.details.cancelBannerTitle') }}</h4>
        <p class="font-medium leading-relaxed text-dm-text-secondary">
          {{ t('quotation.pages.details.cancelBannerBody', { time: cancelledVersion?.updateTime || quote.createdAt }) }}
        </p>
        <div
          v-if="cancelledVersion"
          class="mt-2 rounded-lg border border-rose-100/50 bg-white/80 p-2.5 font-medium text-rose-900"
        >
          <span class="font-bold text-rose-700">{{ t('quotation.pages.details.cancelReasonLabel') }}</span>
          <span class="italic">“ {{ cancelReason }} ”</span>
        </div>
      </div>
    </div>

    <div
      class="flex flex-col items-start justify-between gap-4 dm-card p-4 shadow-xs sm:flex-row sm:items-center"
    >
      <button
        type="button"
        class="flex cursor-pointer items-center gap-1.5 rounded-lg border border-dm-border px-3 py-1.5 text-sm font-semibold text-dm-text-secondary transition duration-150 hover:bg-[#fafafa]"
        @click="emit('back')"
      >
        <ArrowLeft class="h-4 w-4" />
        {{ t('quotation.pages.details.backToList') }}
      </button>

      <div class="flex flex-wrap items-center gap-2">
        <button
          v-if="
            quote.status !== 'Cancelled' &&
            quote.sourceType !== 'document_import'
          "
          type="button"
          class="flex cursor-pointer items-center gap-1.5 rounded-lg border border-dm-border bg-white px-3.5 py-2 text-sm font-semibold text-dm-text shadow-xs transition duration-150 hover:bg-[#fafafa]"
          @click="emit('editQuote', quote.id)"
        >
          <Pencil class="h-4 w-4 text-dm-text-tertiary" />
          {{ t('quotation.pages.details.editQuote') }}
        </button>

        <button
          v-if="quote.status === 'Draft'"
          type="button"
          class="dm-btn-primary cursor-pointer px-3.5 py-2 text-sm font-semibold"
          @click="handleGenerateExcel"
        >
          <FileSpreadsheet class="h-4 w-4" />
          {{ t('quotation.pages.details.generateExcel') }}
        </button>

        <button
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold shadow-xs transition duration-150"
          :class="
            quote.status === 'Cancelled'
              ? 'cursor-not-allowed border border-dm-border bg-slate-100 text-dm-text-tertiary'
              : 'cursor-pointer bg-emerald-500 text-white hover:bg-emerald-600 active:bg-emerald-700'
          "
          @click="handleDownloadExcel"
        >
          <Download class="h-4 w-4" />
          {{ t('quotation.pages.details.downloadQuote') }}
        </button>

        <button
          type="button"
          :disabled="quote.status === 'Cancelled'"
          class="flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold shadow-xs transition duration-150"
          :class="
            quote.status === 'Cancelled'
              ? 'cursor-not-allowed border border-dm-border bg-slate-100 text-dm-text-tertiary'
              : 'cursor-pointer bg-violet-500 text-white hover:bg-violet-600 active:bg-violet-700'
          "
          @click="handleExportPdf"
        >
          <FileDown class="h-4 w-4" />
          {{ t('quotation.pages.details.exportPdf') }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div class="min-w-0 overflow-x-auto overflow-y-auto rounded-xl border border-dm-border bg-slate-100 p-4">
        <QuotationPreview :quote="quote" :current-user="currentUser" />
      </div>

      <div class="min-w-0 space-y-6 xl:w-[300px]">
        <div
          v-if="
            quote.excelGeneratedAt ||
            quote.status === 'Generated' ||
            quote.status === 'Uploaded' ||
            quote.status === 'Sent' ||
            quote.status === 'Accepted'
          "
          class="space-y-4 dm-card p-5 shadow-xs"
        >
          <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
            <FileSpreadsheet class="h-4 w-4 text-emerald-500" />
            <h3 class="text-sm font-semibold text-dm-text">{{ t('quotation.pages.details.excelPropsTitle') }}</h3>
          </div>
          <div class="space-y-3 text-sm font-medium text-dm-text-secondary">
            <div>
              <span class="block text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
                {{ t('quotation.pages.details.excelFileName') }}
              </span>
              <span
                class="mt-1 block break-all rounded-md border border-emerald-100/50 bg-emerald-50/20 px-2.5 py-1.5 font-mono text-[11.5px] font-bold text-dm-text"
              >
                {{ quote.excelFileName || buildQuotationExportFileName(quote, 'xlsx') }}
              </span>
            </div>
            <div>
              <span class="block text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
                {{ t('quotation.pages.details.excelGeneratedAt') }}
              </span>
              <span class="mt-1 block font-mono text-xs text-dm-text">
                {{ quote.excelGeneratedAt || quote.createdAt || t('quotation.pages.details.autoGenerated') }}
              </span>
            </div>
            <div>
              <span class="block text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
                {{ t('quotation.pages.details.excelTemplateStatus') }}
              </span>
              <div class="mt-1.5 flex items-center gap-1.5 text-xs font-bold text-emerald-600">
                <CheckCircle class="h-3.5 w-3.5" />
                <span>{{ t('quotation.pages.details.excelTemplateReady') }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-4 dm-card p-5 shadow-xs">
          <div class="flex items-center justify-between border-b border-slate-50 pb-2">
            <div class="flex items-center gap-2">
              <Clock class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-semibold text-dm-text">{{ t('quotation.pages.details.activityTitle') }}</h3>
            </div>
          </div>
          <ol class="max-h-64 space-y-3 overflow-y-auto pr-1">
            <li v-for="event in activityEvents" :key="event.id" class="border-l-2 border-blue-200 pl-3">
              <p class="text-xs font-semibold text-dm-text">{{ t(`quotation.pages.audit.actions.${event.action}`) }}</p>
              <p class="mt-0.5 text-[11px] text-dm-text-tertiary">{{ activityActor(event) }} · {{ activityTime(event.created_at) }}</p>
              <p class="mt-0.5 truncate font-mono text-[10px] text-dm-text-tertiary" :title="event.request_id">{{ event.request_id }}</p>
            </li>
            <li v-if="!activityEvents.length" class="py-3 text-center text-xs text-dm-text-tertiary">{{ t('quotation.pages.details.noActivity') }}</li>
          </ol>
        </div>

        <div class="space-y-4 dm-card p-5 shadow-xs">
          <div class="flex items-center gap-2 border-b border-slate-50 pb-2">
            <Settings class="h-4 w-4 text-dm-text-tertiary" />
            <h3 class="text-sm font-semibold text-dm-text">{{ t('quotation.pages.details.statusCenterTitle') }}</h3>
          </div>

          <div class="space-y-3">
            <div
              class="flex items-center justify-between rounded-lg border border-dm-border-light bg-[#fafafa] p-2.5"
            >
              <span class="text-sm font-medium text-dm-text-tertiary">{{ t('quotation.pages.details.currentStatus') }}</span>
              <StatusBadge :status="quote.status" />
            </div>

            <div
              v-if="quote.sourceType !== 'document_import'"
              class="space-y-2 text-sm"
            >
              <span class="mb-1 block text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
                {{ t('quotation.pages.details.quickStatusChange') }}
              </span>

              <div
                v-if="quote.status === 'Cancelled'"
                class="select-none space-y-1 rounded-lg border border-dashed border-dm-border bg-[#fafafa] p-3.5 text-center font-medium text-dm-text-tertiary"
              >
                <p>{{ t('quotation.pages.details.statusFrozenTitle') }}</p>
                <p class="text-xs text-dm-text-tertiary">{{ t('quotation.pages.details.statusFrozenHint') }}</p>
              </div>

              <div v-else class="grid grid-cols-1 gap-2">
                <button
                  type="button"
                  :disabled="quote.status === 'Sent'"
                  class="flex w-full cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-left transition duration-150"
                  :class="
                    quote.status === 'Sent'
                      ? 'border-purple-200 bg-purple-50 font-bold text-purple-700'
                      : 'border-dm-border text-dm-text hover:bg-[#fafafa]'
                  "
                  @click="setStatus('Sent')"
                >
                  <div class="flex items-center gap-2">
                    <Send class="h-3.5 w-3.5 text-purple-500" />
                    <span>{{ t('quotation.pages.details.markSent') }}</span>
                  </div>
                  <span
                    v-if="quote.status === 'Sent'"
                    class="rounded-md bg-purple-100 px-1.5 py-0.5 text-xs font-medium"
                  >
                    {{ t('quotation.pages.details.currentBadge') }}
                  </span>
                </button>

                <button
                  type="button"
                  :disabled="quote.status === 'Accepted'"
                  class="flex w-full cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-left transition duration-150"
                  :class="
                    quote.status === 'Accepted'
                      ? 'border-emerald-200 bg-emerald-50 font-bold text-emerald-700'
                      : 'border-dm-border text-dm-text hover:bg-[#fafafa]'
                  "
                  @click="setStatus('Accepted')"
                >
                  <div class="flex items-center gap-2">
                    <CheckCircle class="h-3.5 w-3.5 text-emerald-500" />
                    <span>{{ t('quotation.pages.details.markAccepted') }}</span>
                  </div>
                  <span
                    v-if="quote.status === 'Accepted'"
                    class="rounded-md bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700"
                  >
                    {{ t('quotation.pages.details.currentBadge') }}
                  </span>
                </button>

                <button
                  type="button"
                  :disabled="quote.status === 'Rejected'"
                  class="flex w-full cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-left transition duration-150"
                  :class="
                    quote.status === 'Rejected'
                      ? 'border-red-200 bg-red-50 font-bold text-red-700'
                      : 'border-dm-border text-dm-text hover:bg-[#fafafa]'
                  "
                  @click="setStatus('Rejected')"
                >
                  <div class="flex items-center gap-2">
                    <XCircle class="h-3.5 w-3.5 text-red-500" />
                    <span>{{ t('quotation.pages.details.markRejected') }}</span>
                  </div>
                  <span
                    v-if="quote.status === 'Rejected'"
                    class="rounded-md bg-red-100 px-1.5 py-0.5 text-xs font-medium"
                  >
                    {{ t('quotation.pages.details.currentBadge') }}
                  </span>
                </button>

                <button
                  type="button"
                  :disabled="quote.status === 'Expired'"
                  class="flex w-full cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-left transition duration-150"
                  :class="
                    quote.status === 'Expired'
                      ? 'border-amber-200 bg-amber-50 font-bold text-amber-700'
                      : 'border-dm-border text-dm-text hover:bg-[#fafafa]'
                  "
                  @click="setStatus('Expired')"
                >
                  <div class="flex items-center gap-2">
                    <Clock class="h-3.5 w-3.5 text-amber-500" />
                    <span>{{ t('quotation.pages.details.markExpired') }}</span>
                  </div>
                  <span
                    v-if="quote.status === 'Expired'"
                    class="rounded-md bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700"
                  >
                    {{ t('quotation.pages.details.currentBadge') }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-4 dm-card p-5 shadow-xs">
          <div class="flex items-center justify-between border-b border-slate-50 pb-2">
            <div class="flex items-center gap-2">
              <Clock class="h-4 w-4 text-dm-text-tertiary" />
              <h3 class="text-sm font-semibold text-dm-text">{{ t('quotation.pages.details.versionHistoryTitle') }}</h3>
            </div>
            <span class="rounded-full bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-bold text-dm-text-secondary">
              {{ t('quotation.pages.details.versionCount', { count: quote.versions?.length || 0 }) }}
            </span>
          </div>

          <div class="max-h-[420px] space-y-3 overflow-y-auto pr-1">
            <div
              v-for="ver in reversedVersions"
              :key="ver.id"
              class="space-y-2.5 rounded-lg border border-dm-border-light bg-[#fafafa] p-3 text-sm font-medium transition duration-150 hover:bg-[#fafafa]"
            >
              <div class="flex items-center justify-between font-bold">
                <span class="rounded-md bg-dm-primary-bg px-2 py-0.5 font-mono text-sm text-dm-primary">
                  {{ ver.versionNo }}
                </span>
                <span class="font-mono text-xs text-dm-text-tertiary">{{ ver.updateTime ? ver.updateTime.substring(5, 16) : '' }}</span>
              </div>
              <div class="space-y-1 text-dm-text-secondary">
                <div class="flex justify-between font-medium">
                  <span class="text-dm-text-tertiary">{{ t('quotation.pages.details.operator') }}</span>
                  <span class="font-bold text-dm-text">{{ ver.operator }}</span>
                </div>
                <div class="flex justify-between font-medium">
                  <span class="text-dm-text-tertiary">{{ t('quotation.pages.details.quoteStatus') }}</span>
                  <StatusBadge :status="ver.status" />
                </div>
                <div class="flex justify-between font-medium">
                  <span class="text-dm-text-tertiary">{{ t('quotation.pages.details.versionTotal') }}</span>
                  <span class="font-mono font-bold text-dm-text">
                    {{ getCurrencySymbol(ver.currency) }}{{ ver.grandTotal.toLocaleString() }}
                  </span>
                </div>
                <p
                  class="mt-1 line-clamp-2 border-l-2 border-dm-border pl-1.5 text-xs font-medium italic text-dm-text-tertiary"
                  :title="ver.notes"
                >
                  {{ ver.notes || t('quotation.pages.details.noNotes') }}
                </p>
                <p
                  v-if="versionDiffChips.get(ver.id)"
                  class="mt-1 rounded-md bg-rose-50 px-1.5 py-0.5 text-xs font-bold text-rose-600"
                >
                  {{ versionDiffChips.get(ver.id) }}
                </p>
              </div>
              <button
                type="button"
                class="mt-1.5 flex w-full cursor-pointer items-center justify-center gap-1 rounded-md border border-dm-border py-1.5 text-xs font-extrabold text-dm-text transition duration-150 hover:bg-slate-100"
                @click="selectedVersionForModal = ver"
              >
                <FileText class="h-3.5 w-3.5 text-dm-text-tertiary" />
                <span>{{ t('quotation.pages.details.viewVersionSnapshot') }}</span>
              </button>
            </div>
            <p v-if="!reversedVersions.length" class="py-4 text-center font-medium text-dm-text-tertiary">
              {{ t('quotation.pages.details.noVersionHistory') }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="displayVersion && snapshotQuote"
      class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto dm-modal-overlay p-4 backdrop-blur-[2px]"
    >
      <div
        class="relative max-h-[90vh] w-full max-w-5xl space-y-4 overflow-y-auto dm-card p-6 shadow-2xl"
      >
        <div class="flex items-start justify-between border-b border-dm-border-light pb-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <span class="rounded-md bg-dm-primary-bg px-2 py-0.5 font-mono text-sm font-extrabold text-dm-primary">
                {{ displayVersion.versionNo }}
              </span>
              <h3 class="text-sm font-extrabold text-dm-text">{{ t('quotation.pages.details.snapshotTitle') }}</h3>
              <StatusBadge :status="displayVersion.status" />
            </div>
            <p class="text-sm font-medium text-dm-text-tertiary">
              {{
                t('quotation.pages.details.snapshotMeta', {
                  time: displayVersion.updateTime,
                  operator: displayVersion.operator,
                })
              }}
            </p>
            <p class="text-sm font-medium text-rose-600">
              {{ t('quotation.pages.details.versionChangeNote') }}
              <span class="font-bold italic">
                “ {{ displayVersion.notes || t('quotation.pages.details.noVersionNote') }} ”
              </span>
            </p>
            <p
              v-if="activeVersionDiff?.hasChanges"
              class="mt-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-xs font-semibold text-rose-700"
            >
              {{ t('quotation.pages.details.diffVsCurrentBanner') }}
              <span class="font-bold">{{ activeDiffSummaryLabels.join(' · ') }}</span>
            </p>
            <p
              v-else
              class="mt-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs font-semibold text-emerald-700"
            >
              {{ t('quotation.pages.details.diffVsCurrentSame') }}
            </p>
          </div>
          <button
            type="button"
            class="animate-none cursor-pointer rounded-lg px-2.5 py-1 text-sm font-semibold text-dm-text-tertiary transition duration-150 hover:bg-slate-100 hover:text-dm-text"
            @click="selectedVersionForModal = null"
          >
            {{ t('quotation.pages.details.closeModal') }}
          </button>
        </div>

        <div
          class="grid grid-cols-1 gap-4 rounded-xl border border-dm-border-light bg-[#fafafa] p-4 text-sm font-medium md:grid-cols-2"
        >
          <div class="space-y-1.5 font-medium">
            <p class="text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
              {{ t('quotation.pages.details.propertiesTitle') }}
            </p>
            <div>
              {{ t('quotation.pages.details.projectName') }}
              <span :class="changedValueClass('projectName')">
                {{ displayVersion.projectName }}
              </span>
              <span
                v-if="isFieldChanged(activeVersionDiff, 'projectName')"
                class="ml-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
              >
                {{ t('quotation.pages.details.diffBadge') }}
              </span>
            </div>
            <div>
              {{ t('quotation.pages.details.clientCompany') }}
              <span :class="changedValueClass('clientCompany')">
                {{ displayVersion.clientCompany }}
              </span>
              <span
                v-if="isFieldChanged(activeVersionDiff, 'clientCompany')"
                class="ml-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
              >
                {{ t('quotation.pages.details.diffBadge') }}
              </span>
            </div>
            <div>
              {{ t('quotation.pages.details.contactPerson') }}
              <span
                :class="
                  isFieldChanged(activeVersionDiff, 'contactPerson') ||
                  isFieldChanged(activeVersionDiff, 'email')
                    ? 'font-semibold text-rose-600'
                    : 'text-dm-text-secondary'
                "
              >
                {{ displayVersion.contactPerson }} ({{ displayVersion.email }})
              </span>
              <span
                v-if="
                  isFieldChanged(activeVersionDiff, 'contactPerson') ||
                  isFieldChanged(activeVersionDiff, 'email')
                "
                class="ml-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
              >
                {{ t('quotation.pages.details.diffBadge') }}
              </span>
            </div>
          </div>
          <div class="space-y-1.5 font-medium md:border-l md:border-dm-border md:pl-4">
            <p class="text-xs font-bold uppercase tracking-wider text-dm-text-tertiary">
              {{ t('quotation.pages.details.notesTitle') }}
            </p>
            <div>
              {{ t('quotation.pages.details.currency') }}
              <span
                :class="
                  isFieldChanged(activeVersionDiff, 'currency')
                    ? 'font-mono font-bold text-rose-600'
                    : 'font-mono font-bold text-dm-text'
                "
              >
                {{ displayVersion.currency }}
              </span>
              <span
                v-if="isFieldChanged(activeVersionDiff, 'currency')"
                class="ml-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
              >
                {{ t('quotation.pages.details.diffBadge') }}
              </span>
            </div>
            <div>
              {{ t('quotation.pages.details.paymentTerms') }}
              <span
                :class="
                  isFieldChanged(activeVersionDiff, 'paymentTerms')
                    ? 'font-semibold leading-relaxed text-rose-600'
                    : 'leading-relaxed text-dm-text-secondary'
                "
              >
                {{ displayVersion.paymentTerms || t('quotation.pages.details.defaultPaymentTerms') }}
              </span>
              <span
                v-if="isFieldChanged(activeVersionDiff, 'paymentTerms')"
                class="ml-1 rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
              >
                {{ t('quotation.pages.details.diffBadge') }}
              </span>
            </div>
            <div class="flex justify-between font-medium text-dm-text-secondary">
              <span>{{ t('quotation.pages.details.versionTotal') }}</span>
              <span class="flex items-center gap-1">
                <span
                  :class="
                    isFieldChanged(activeVersionDiff, 'grandTotal')
                      ? 'font-mono font-bold text-rose-600'
                      : 'font-mono font-bold text-dm-primary'
                  "
                >
                  {{ versionCurrencySymbol }}{{ (displayVersion.grandTotal || 0).toLocaleString() }}
                </span>
                <span
                  v-if="isFieldChanged(activeVersionDiff, 'grandTotal')"
                  class="rounded bg-rose-100 px-1 text-xs font-bold text-rose-600"
                >
                  {{ t('quotation.pages.details.diffBadge') }}
                </span>
              </span>
            </div>
          </div>
        </div>

        <div class="overflow-x-auto rounded-xl border border-dm-border bg-slate-100 p-3">
          <QuotationPreview
            :quote="snapshotQuote"
            :current-user="currentUser"
            scale="compact"
            :changed-line-ids="[...(activeVersionDiff?.changedLineIds || [])]"
            :changed-header-keys="[...(activeVersionDiff?.changedFields || [])]"
          />
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-dm-border-light pt-2">
          <button
            type="button"
            class="cursor-pointer rounded-lg border border-dm-border bg-slate-100 px-4 py-2 text-sm font-semibold text-dm-text transition duration-150 hover:bg-slate-200"
            @click="selectedVersionForModal = null"
          >
            {{ t('quotation.pages.details.closeSnapshot') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
