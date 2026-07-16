<script setup lang="ts">
import { computed } from 'vue'
import type { Quotation } from '../types'
import oneProLogoUrl from '../assets/onepro-logo.png'
import {
  buildQuotationPreviewModel,
  type PreviewLineItem,
  type PreviewUser,
} from '../utils/quotationPreviewModel'

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
const padding = computed(() => (props.scale === 'compact' ? 'p-4' : 'p-7'))
const textSize = computed(() => (props.scale === 'compact' ? 'text-[10px]' : 'text-[11px]'))
const metaHeaderSize = computed(() =>
  props.scale === 'compact' ? 'text-[9px]' : 'text-[11px]',
)
const sectionTitleSize = computed(() =>
  props.scale === 'compact' ? 'text-[11px]' : 'text-[12px]',
)
const logoClass = computed(() =>
  props.scale === 'compact' ? 'left-4 top-4 w-[132px]' : 'left-7 top-7 w-[166px]',
)
const titleSpacerClass = computed(() => (props.scale === 'compact' ? 'h-20' : 'h-28'))

function money(value: number): string {
  if (!value) return ''
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function percent(value: number): string {
  return value ? `${value}%` : '0%'
}

function rowHasContent(item: PreviewLineItem) {
  return Boolean(item.name || item.description)
}

function rowDescription(item: PreviewLineItem) {
  return item.description || item.name || ''
}

const moneyCellClass =
  'whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-mono tabular-nums align-middle'
const moneyTotalCellClass =
  'whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-mono font-semibold tabular-nums align-middle'
const headerCellClass =
  'whitespace-normal break-normal border border-slate-300 px-1.5 py-1 text-center font-semibold leading-tight align-middle'
</script>

<template>
  <section
    class="relative mx-auto w-full max-w-[980px] border border-slate-200 bg-white text-slate-900 shadow-sm"
    :class="padding"
  >
    <img
      :src="oneProLogoUrl"
      alt="OnePro"
      class="absolute h-auto object-contain"
      :class="logoClass"
    />
    <table
      class="w-full table-fixed border-collapse leading-snug"
      :class="textSize"
    >
      <colgroup>
        <col class="w-[12%]" />
        <col class="w-[24%]" />
        <col class="w-[8%]" />
        <col class="w-[12%]" />
        <col class="w-[10%]" />
        <col class="w-[17%]" />
        <col class="w-[17%]" />
      </colgroup>
      <tbody>
        <tr :class="titleSpacerClass">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="7" class="px-1.5 py-1 text-center text-[18px] font-semibold align-middle">
            {{ model.issuerCompanyName }}
          </td>
        </tr>
        <tr>
          <td colspan="7" class="px-1.5 py-1 text-center text-[22px] font-semibold underline align-middle">
            Quotation
          </td>
        </tr>
        <tr class="h-5">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
          <td class="whitespace-nowrap px-1.5 py-1 pr-1 text-right font-semibold align-middle">
            Date:
          </td>
          <td
            class="whitespace-nowrap border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right font-mono align-middle"
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
            class="whitespace-nowrap border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right font-mono align-middle"
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
            <span class="font-semibold">Company :</span> {{ model.customerCompany || '' }}
          </td>
          <td colspan="3" class="px-1.5 py-1 align-middle" />
          <td class="whitespace-nowrap px-1.5 py-1 pr-1 text-right font-semibold align-middle">
            Quote Valid Till:
          </td>
          <td
            class="whitespace-nowrap border-b border-slate-900 px-1.5 py-1 pb-0.5 text-right font-mono align-middle"
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
            <span class="font-semibold">Name :</span> {{ model.contactPerson || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-all border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('email'))"
          >
            <span class="font-semibold">Email :</span> {{ model.email || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-3">
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
            <span class="font-semibold">Company :</span> {{ model.billingCompany || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-words border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('billingContact'))"
          >
            <span class="font-semibold">Name :</span> {{ model.billingContact || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="2"
            class="break-all border border-slate-900 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('billingEmail'))"
          >
            <span class="font-semibold">Email :</span> {{ model.billingEmail || '' }}
          </td>
          <td colspan="5" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="h-4">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr
          class="relative z-10 bg-slate-200 font-semibold shadow-[0_2px_10px_rgba(15,23,42,0.18)]"
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
          <td class="whitespace-nowrap border border-slate-300 px-1.5 py-1 align-middle">
            {{ model.signer.name }}
          </td>
          <td class="break-all border border-slate-300 px-1.5 py-1 align-middle">
            {{ model.signer.email }}
          </td>
          <td
            colspan="3"
            class="break-words border border-slate-300 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('projectName'))"
          >
            {{ model.projectName || '-' }}
          </td>
          <td
            class="break-words border border-slate-300 px-1.5 py-1 align-middle"
            :class="highlightCellClass(isHeaderChanged('paymentTerms'))"
          >
            {{ model.paymentTerms || '-' }}
          </td>
          <td
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 font-mono align-middle"
            :class="highlightCellClass(isHeaderChanged('currency'))"
          >
            {{ model.currency }}
          </td>
        </tr>
        <tr class="h-5">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="7"
            class="border border-slate-300 bg-slate-200 px-1.5 py-1 text-left font-semibold align-middle"
            :class="sectionTitleSize"
          >
            Software
          </td>
        </tr>
        <tr class="bg-slate-50">
          <td :class="headerCellClass">Item</td>
          <td :class="headerCellClass">Description</td>
          <td :class="headerCellClass">Qty</td>
          <td :class="headerCellClass">List Price</td>
          <td :class="headerCellClass">Discount (%)</td>
          <td :class="headerCellClass">Discounted Price</td>
          <td :class="headerCellClass">Extended Price</td>
        </tr>
        <tr
          v-for="item in model.softwareRows"
          :key="item.id"
          class="h-8"
          :class="isLineChanged(item.id) ? 'bg-rose-50' : ''"
        >
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? item.lineNo : '' }}
          </td>
          <td
            class="break-words border border-slate-300 px-1.5 py-1 align-middle"
            :class="
              isLineChanged(item.id)
                ? 'bg-rose-50 font-semibold text-rose-700'
                : 'text-slate-900'
            "
          >
            {{ rowDescription(item) }}
          </td>
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? item.qty : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.listPrice) : '' }}
          </td>
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? percent(item.discountPercent) : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.netUnitPrice) : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.extendedPrice) : '' }}
          </td>
        </tr>
        <tr>
          <td colspan="4" class="px-1.5 py-1 align-middle" />
          <td
            colspan="2"
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold align-middle"
          >
            Software subscription subtotal:
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.softwareSubtotal) }}
          </td>
        </tr>
        <tr class="h-5">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td
            colspan="7"
            class="border border-slate-300 bg-slate-200 px-1.5 py-1 text-left font-semibold align-middle"
            :class="sectionTitleSize"
          >
            Others
          </td>
        </tr>
        <tr class="bg-slate-50">
          <td :class="headerCellClass">Item</td>
          <td :class="headerCellClass">Description</td>
          <td :class="headerCellClass">Qty</td>
          <td :class="headerCellClass">List Price</td>
          <td :class="headerCellClass">Discount (%)</td>
          <td :class="headerCellClass">Discounted Price</td>
          <td :class="headerCellClass">Extended Price</td>
        </tr>
        <tr
          v-for="item in model.othersRows"
          :key="item.id"
          class="h-8"
          :class="isLineChanged(item.id) ? 'bg-rose-50' : ''"
        >
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? item.lineNo : '' }}
          </td>
          <td
            class="break-words border border-slate-300 px-1.5 py-1 align-middle"
            :class="
              isLineChanged(item.id)
                ? 'bg-rose-50 font-semibold text-rose-700'
                : 'text-slate-900'
            "
          >
            {{ rowDescription(item) }}
          </td>
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? item.qty : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.listPrice) : '' }}
          </td>
          <td
            class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle"
            :class="highlightCellClass(isLineChanged(item.id))"
          >
            {{ rowHasContent(item) ? percent(item.discountPercent) : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.netUnitPrice) : '' }}
          </td>
          <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
            {{ rowHasContent(item) ? money(item.extendedPrice) : '' }}
          </td>
        </tr>
        <tr>
          <td colspan="4" class="px-1.5 py-1 align-middle" />
          <td
            colspan="2"
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold align-middle"
          >
            Others Subtotal:
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.othersSubtotal) }}
          </td>
        </tr>
        <tr class="h-5">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="4" class="px-1.5 py-1 align-middle" />
          <td
            colspan="2"
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold align-middle"
          >
            Subtotal before {{ model.taxLabel }}:
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.subtotalBeforeVat) }}
          </td>
        </tr>
        <tr>
          <td colspan="4" class="px-1.5 py-1 align-middle" />
          <td
            colspan="2"
            class="whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-semibold align-middle"
          >
            {{ model.taxLabel }} Amount ({{ model.vatRate }}%):
          </td>
          <td :class="moneyTotalCellClass">
            {{ money(model.vatAmount) }}
          </td>
        </tr>
        <tr>
          <td colspan="4" class="px-1.5 py-1 align-middle" />
          <td
            colspan="2"
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
        <tr class="h-3">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr>
          <td colspan="7" class="px-1.5 py-1 font-semibold align-middle">Additional Notes & Disclaimers:</td>
        </tr>
        <tr>
          <td
            colspan="7"
            :class="[
              'whitespace-pre-line border border-slate-300 px-1.5 py-1 text-[9px] leading-relaxed align-middle',
              isHeaderChanged('remarksDisclaimer')
                ? 'bg-rose-50 text-rose-700 font-semibold'
                : 'bg-slate-50 text-slate-700',
            ]"
          >
            {{ model.remarksDisclaimer }}
          </td>
        </tr>
        <tr>
          <td colspan="7" class="px-1.5 py-1 pt-3 align-middle">
            To indicate Customer acceptance of this quotation, please sign below and return one copy of this
            quotation to OnePro Cloud.
          </td>
        </tr>
        <tr class="h-8">
          <td colspan="7" class="px-1.5 py-1 align-middle" />
        </tr>
        <tr class="font-semibold">
          <td colspan="3" class="px-1.5 py-1 align-middle" />
          <td colspan="1" class="px-1.5 py-1 align-middle" />
          <td colspan="3" class="px-1.5 py-1 align-middle">{{ model.issuerCompanyName }}</td>
        </tr>
        <tr>
          <td colspan="3" class="h-10 px-1.5 py-1 pb-1 align-bottom">
            <div class="border-b border-slate-900" />
          </td>
          <td colspan="1" class="px-1.5 py-1 align-middle" />
          <td colspan="3" class="relative h-10 px-1.5 py-1 pb-1 align-bottom">
            <img
              v-if="model.issuerSignature"
              :src="model.issuerSignature"
              alt="Issuer signature"
              class="absolute bottom-1 left-0 max-h-8 max-w-full object-contain object-left"
            />
            <div class="border-b border-slate-900" />
          </td>
        </tr>
        <tr>
          <td colspan="3" class="px-1.5 py-1 align-middle">Name :</td>
          <td colspan="1" class="px-1.5 py-1 align-middle" />
          <td colspan="3" class="px-1.5 py-1 align-middle">Name : {{ model.signer.name }}</td>
        </tr>
        <tr>
          <td colspan="3" class="px-1.5 py-1 align-middle">Title :</td>
          <td colspan="1" class="px-1.5 py-1 align-middle" />
          <td colspan="3" class="px-1.5 py-1 align-middle">Title : {{ model.signer.title }}</td>
        </tr>
        <tr>
          <td colspan="3" class="px-1.5 py-1 align-middle">Email :</td>
          <td colspan="1" class="px-1.5 py-1 align-middle" />
          <td colspan="3" class="break-all px-1.5 py-1 align-middle">
            Email :
            <a :href="`mailto:${model.signer.email}`" class="text-blue-600 no-underline">
              {{ model.signer.email }}
            </a>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
