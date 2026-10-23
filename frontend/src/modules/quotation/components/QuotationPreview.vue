<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Quotation } from '../types'
import { paginateQuotation } from '../utils/paginateQuotation'
import oneProLogoUrl from '../assets/onepro-logo.png'
import QuotationAcceptanceRows from './QuotationAcceptanceRows.vue'
import QuotationSectionTable from './QuotationSectionTable.vue'
import {
  buildQuotationPreviewModel,
  type PreviewUser,
} from '../utils/quotationPreviewModel'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const { t, locale } = useQuotationI18n()

const props = withDefaults(
  defineProps<{
    quote: Quotation
    currentUser?: PreviewUser
    scale?: 'normal' | 'compact'
    changedLineIds?: string[]
    changedHeaderKeys?: string[]
  }>(),
  {
    scale: 'normal',
    changedLineIds: () => [],
    changedHeaderKeys: () => [],
  },
)

const changedLineIdSet = computed(() => new Set(props.changedLineIds || []))
const changedHeaderKeySet = computed(
  () => new Set(props.changedHeaderKeys || []),
)

function isLineChanged(id: string): boolean {
  return changedLineIdSet.value.has(id)
}

function isHeaderChanged(key: string): boolean {
  return changedHeaderKeySet.value.has(key)
}

function highlightCellClass(changed: boolean): string {
  return changed ? 'bg-rose-50 text-rose-700 font-semibold' : ''
}

const model = computed(() => buildQuotationPreviewModel(props.quote, { currentUser: props.currentUser }))
// Match the A4 printable width used by the XLSX-to-PDF renderer.
const previewFrameWidth = computed(() =>
  props.scale === 'compact' ? '697px' : '721px',
)
const previewFrameMinHeight = computed(() =>
  props.scale === 'compact' ? '986px' : '1020px',
)
const totalsLabelSpan = computed(() => {
  const labels = [
    'Software subscription subtotal:',
    'Others Subtotal:',
    `Subtotal before ${model.value.taxLabel}:`,
    `${model.value.taxLabel} Amount (${model.value.vatRate}%):`,
    t('quotation.pages.create.deductionAmount'),
    model.value.customTotalLabel
      ? `${model.value.customTotalLabel}(${model.value.customTotalCurrency || model.value.currency}):`
      : '',
    'Grand Total:',
  ]
  const length = Math.max(...labels.map((label) => label.length))
  if (length > 78) return 6
  if (length > 58) return 5
  if (length > 43) return 4
  if (length > 28) return 3
  return 2
})
const totalsSpacerSpan = computed(() => 6 - totalsLabelSpan.value)
const padding = computed(() =>
  props.scale === 'compact'
    ? 'pl-[63px] pr-[70px] py-[84px]'
    : 'pl-[65px] pr-[73px] py-[87px]',
)
const textSize = computed(() =>
  props.scale === 'compact' ? 'text-[9px]' : 'text-[9.3px]',
)
const metaHeaderSize = computed(() =>
  props.scale === 'compact' ? 'text-[8px]' : 'text-[8.3px]',
)
const sectionTitleSize = computed(() =>
  props.scale === 'compact' ? 'text-[9px]' : 'text-[9.3px]',
)
const logoClass = computed(() =>
  props.scale === 'compact'
    ? 'left-[63px] top-[84px] w-[86px]'
    : 'left-[65px] top-[87px] w-[89px]',
)
const titleSpacerClass = computed(() =>
  props.scale === 'compact' ? 'h-[53px]' : 'h-[55px]',
)
const source = ref<HTMLElement>()
const output = ref<HTMLElement>()
let frame = 0
let observer: ResizeObserver | undefined

function refreshPages(): void {
  if (!source.value || !output.value) return
  const staging = document.createElement('div')
  source.value.parentElement!.append(staging)
  try {
    paginateQuotation(source.value, staging, {
      height: props.scale === 'compact' ? 986 : 1020,
      continuationTop: props.scale === 'compact' ? 84 : 87,
      signatureTop: props.scale === 'compact' ? 79 : 81,
    })
    output.value.replaceChildren(...Array.from(staging.children))
  } catch (error) {
    // Keep all content visible if browser layout cannot be paginated.
    console.error('Quotation preview pagination failed', error)
    output.value.replaceChildren(source.value.cloneNode(true))
  } finally {
    staging.remove()
  }
}

function schedulePages(): void {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(refreshPages)
}

watch(
  [model, () => props.scale, changedLineIdSet, changedHeaderKeySet, locale],
  schedulePages,
  { flush: 'post' },
)
onMounted(() => {
  observer = new ResizeObserver(schedulePages)
  observer.observe(source.value!)
  document.fonts.addEventListener('loadingdone', schedulePages)
  schedulePages()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
  document.fonts.removeEventListener('loadingdone', schedulePages)
})

function money(value: number): string {
  if (!value) return ''
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function customMoney(value: number): string {
  if (!value) return ''
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  })
}

const moneyTotalCellClass =
  'whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold tabular-nums align-middle'
</script>

<template>
  <div>
    <div ref="output" class="space-y-4" data-quotation-pages />
    <div
      class="quotation-measurement"
      aria-hidden="true"
      inert
      @load.capture="schedulePages"
    >
    <section
    ref="source"
    :style="{
      width: previewFrameWidth,
      minHeight: previewFrameMinHeight,
      fontFamily: 'Arial, Helvetica, sans-serif',
    }"
    class="relative mx-auto w-fit max-w-none shrink-0 border border-slate-200 bg-white text-slate-900 shadow-sm"
    :class="padding"
  >
    <img
      :src="oneProLogoUrl"
      alt="OnePro"
      class="absolute h-auto object-contain"
      :class="logoClass"
    />
    <table
      class="quotation-pdf-table w-full table-fixed border-collapse leading-snug"
      :class="textSize"
    >
      <colgroup v-if="model.showDiscount">
        <col class="w-[12%]" />
        <col class="w-[24%]" />
        <col class="w-[8%]" />
        <col class="w-[12%]" />
        <col class="w-[10%]" />
        <col class="w-[17%]" />
        <col class="w-[17%]" />
      </colgroup>
      <colgroup v-else>
        <col class="w-[12%]" />
        <col class="w-[32%]" />
        <col class="w-[8%]" />
        <col class="w-[8%]" />
        <col class="w-[8%]" />
        <col class="w-[9%]" />
        <col class="w-[23%]" />
      </colgroup>
      <tbody>
        <tr :class="titleSpacerClass">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="7" class="break-words text-center text-[14px] font-semibold align-middle">
            {{ model.issuerCompanyName }}
          </td>
        </tr>
        <tr>
          <td colspan="7" class="text-center text-[17px] font-semibold underline align-middle">
            Quotation
          </td>
        </tr>
        <tr class="h-[13px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[13px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
          <td class="whitespace-nowrap px-1.5 py-1 pr-1 text-right font-semibold align-middle">
            Date:
          </td>
          <td
            class="whitespace-nowrap border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right align-middle"
          >
            {{ model.quoteDate }}
          </td>
        </tr>
        <tr>
          <td
            colspan="2"
            class="border border-slate-900 bg-slate-200 px-1.5 py-1 text-center font-semibold align-middle"
          >
            Ship to
          </td>
          <td colspan="3" class="px-1.5 py-1 align-middle" />
          <td class="whitespace-nowrap px-1.5 py-1 pr-1 text-right font-semibold align-middle">
            Quote No.:
          </td>
          <td
            class="whitespace-normal break-all border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right leading-tight align-middle"
          >
            {{ model.quoteNo }}
          </td>
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-words border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('clientCompany'))"
          >
            Company : {{ model.customerCompany || '' }}
          </td>
          <td colspan="3" class="px-1.5 py-1 align-middle" />
          <td class="whitespace-nowrap px-1.5 py-1 pr-1 text-right font-semibold align-middle">
            Quote Valid Till:
          </td>
          <td
            class="whitespace-nowrap border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right align-middle"
          >
            {{ model.validTill }}
          </td>
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-words border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('contactPerson'))"
          >
            Name : {{ model.contactPerson || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-all border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('email'))"
          >
            Email : {{ model.email || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[8px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="border border-slate-900 bg-slate-200 px-1.5 py-1 text-center font-semibold align-middle"
          >
            Bill to:
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-words border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('billingCompany'))"
          >
            Company : {{ model.billingCompany || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-words border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('billingContact'))"
          >
            Name : {{ model.billingContact || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-all border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('billingEmail'))"
          >
            Email : {{ model.billingEmail || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[10px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[10px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr
          class="relative z-10 bg-slate-200 font-semibold"
          :class="metaHeaderSize"
        >
          <td class="whitespace-normal break-normal border border-slate-300 px-1.5 py-1 align-middle">
            Contact Person
          </td>
          <td class="whitespace-normal break-normal border border-slate-300 px-1.5 py-1 align-middle">
            Email
          </td>
          <td
            colspan="3"
            class="whitespace-normal break-normal border border-slate-300 px-1.5 py-1 align-middle"
          >
            Project
          </td>
          <td class="whitespace-normal break-normal border border-slate-300 px-1.5 py-1 align-middle">
            Payment Terms
          </td>
          <td class="whitespace-normal break-normal border border-slate-300 px-1.5 py-1 align-middle">
            Currency
          </td>
        </tr>
        <tr>
          <td class="whitespace-normal break-words border border-slate-300 px-1.5 py-1 align-middle">
            {{ model.signer.name }}
          </td>
          <td class="break-all border border-slate-300 px-1.5 py-1 align-middle">
            {{ model.signer.email }}
          </td>
          <td
            colspan="3"
            class="whitespace-pre-line break-words border border-slate-300 px-1.5 py-1 leading-relaxed align-top"
            :class="highlightCellClass(isHeaderChanged('projectName'))"
          >
            {{ model.projectName || '-' }}
          </td>
          <td
            class="whitespace-pre-line break-words border border-slate-300 px-1.5 py-1 leading-relaxed align-top"
            :class="highlightCellClass(isHeaderChanged('paymentTerms'))"
          >
            {{ model.paymentTerms || '-' }}
          </td>
          <td
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('currency'))"
          >
            {{ model.currency }}
          </td>
        </tr>
        <tr class="h-[13px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="7" class="p-0 align-middle">
            <QuotationSectionTable
              title="Software"
              :items="model.softwareRows"
              :layout-show-discount="model.showDiscount"
              :show-discount="model.showSoftwareDiscount"
              :subtotal="model.softwareSubtotal"
              :currency="model.currency"
              :text-size="textSize"
              :section-title-size="sectionTitleSize"
              :totals-label-span="totalsLabelSpan"
              :changed-line-ids="changedLineIdSet"
            />
          </td>
        </tr>
        <tr class="h-[13px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="7" class="p-0 align-middle">
            <QuotationSectionTable
              title="Others"
              :items="model.othersRows"
              :layout-show-discount="model.showDiscount"
              :show-discount="model.showOthersDiscount"
              :subtotal="model.othersSubtotal"
              :currency="model.currency"
              :text-size="textSize"
              :section-title-size="sectionTitleSize"
              :totals-label-span="totalsLabelSpan"
              :changed-line-ids="changedLineIdSet"
            />
          </td>
        </tr>
        <tr class="h-[13px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
          <td
            :colspan="totalsLabelSpan"
            class="whitespace-normal break-words border border-slate-300 px-1.5 py-1 text-right font-semibold leading-tight align-middle"
          >
            Subtotal before {{ model.taxLabel }}:
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.subtotalBeforeVat) }}
          </td>
        </tr>
        <tr v-if="model.vatAmount !== 0">
          <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
          <td
            :colspan="totalsLabelSpan"
            class="whitespace-normal break-words border border-slate-300 px-1.5 py-1 text-right font-semibold leading-tight align-middle"
          >
            {{ model.taxLabel }} Amount ({{ model.vatRate }}%):
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.vatAmount) }}
          </td>
        </tr>
        <tr v-if="model.deductionAmount !== 0">
          <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
          <td
            :colspan="totalsLabelSpan"
            class="whitespace-normal break-words border border-slate-300 px-1.5 py-1 text-right font-semibold leading-tight align-middle"
          >
            {{ t('quotation.pages.create.deductionAmount') }}:
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.deductionAmount) }}
          </td>
        </tr>
        <tr v-if="model.customTotalLabel?.trim() || model.customTotalAmount">
          <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
          <td
            :colspan="totalsLabelSpan"
            class="min-h-7 whitespace-normal break-all border border-slate-300 px-1.5 py-1 text-right font-semibold leading-tight align-middle"
            style="overflow-wrap: anywhere;"
          >
            <template v-if="model.customTotalLabel?.trim()">
              {{ model.customTotalLabel }}({{ model.customTotalCurrency || model.currency }}):
            </template>
            <template v-else>&nbsp;</template>
          </td>
          <td class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold tabular-nums align-middle">
            {{
              customMoney(model.customTotalAmount || 0) || '\u00a0'
            }}
          </td>
        </tr>
        <tr>
          <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
          <td
            :colspan="totalsLabelSpan"
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold align-middle"
          >
            Grand Total:
          </td>
          <td
            :class="[
              moneyTotalCellClass,
              highlightCellClass(isHeaderChanged('grandTotal')),
            ]"
          >
            {{ money(model.grandTotal) }}
          </td>
        </tr>
        <tr class="h-[8px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[8px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr data-preview-notes-title>
          <td
            colspan="7"
            class="px-1.5 py-1 text-[8.25px] font-semibold align-middle"
            style="font-family: Arial, Helvetica, sans-serif;"
          >
            Additional Notes & Disclaimers:
          </td>
        </tr>
        <tr data-preview-notes>
          <td
            colspan="7"
            :class="[
              'whitespace-pre-wrap break-words border border-slate-300 px-1.5 py-1 text-[6.5px] leading-[9px] align-middle',
              isHeaderChanged('remarksDisclaimer')
                ? 'bg-rose-50 text-rose-700 font-semibold'
                : 'bg-slate-50 text-slate-700',
            ]"
            style="font-family: Arial, Helvetica, sans-serif;"
          >
            {{ model.remarksDisclaimer }}
          </td>
        </tr>
        <tr class="h-[10px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-[10px]">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <QuotationAcceptanceRows
          :issuer-company-name="model.issuerCompanyName"
          :issuer-signature="model.issuerSignature"
          :scale="scale"
          :signer="model.signer"
        />
      </tbody>
    </table>
    </section>
    </div>
  </div>
</template>

<style scoped>
.quotation-measurement {
  position: fixed;
  left: -100000px;
  top: 0;
  visibility: hidden;
  pointer-events: none;
}

.quotation-pdf-table > tbody > tr > td {
  padding: 2px 2px;
}

.quotation-pdf-table > tbody > tr > td.p-0 {
  padding: 0;
}

.quotation-pdf-table > tbody > tr > td.acceptance-copy {
  padding-top: 10px;
}
</style>
