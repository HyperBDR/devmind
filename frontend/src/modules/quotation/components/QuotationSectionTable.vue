<script setup lang="ts">
import { computed } from 'vue'
import type { Quotation } from '../types'
import { getCurrencySymbol, type PreviewLineItem } from '../utils/quotationPreviewModel'

const props = defineProps<{
  title: string
  items: PreviewLineItem[]
  showDiscount: boolean
  subtotal: number
  currency: Quotation['currency']
  textSize: string
  sectionTitleSize: string
  totalsLabelSpan: number
  changedLineIds: Set<string>
}>()

const totalsSpacerSpan = computed(() => 6 - props.totalsLabelSpan)

function money(value: number): string {
  if (!value) return ''
  return `${getCurrencySymbol(props.currency)}${Number(value).toLocaleString(
    undefined,
    { maximumFractionDigits: 2 },
  )}`
}

function percent(value: number): string {
  return value ? `${value}%` : '0%'
}

function rowHasContent(item: PreviewLineItem): boolean {
  return Boolean(item.name || item.description)
}

function rowDescription(item: PreviewLineItem): string {
  return item.description || item.name || ''
}

function isLineChanged(id: string): boolean {
  return props.changedLineIds.has(id)
}

function highlightCellClass(changed: boolean): string {
  return changed ? 'bg-rose-50 text-rose-700 font-semibold' : ''
}

const moneyCellClass =
  'whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-mono tabular-nums align-middle'
const moneyTotalCellClass =
  'whitespace-nowrap border border-slate-300 px-1.5 py-1 text-right font-mono font-semibold tabular-nums align-middle'
const headerCellClass =
  'whitespace-normal break-normal border border-slate-300 px-1.5 py-1 text-center font-semibold leading-tight align-middle'
</script>

<template>
  <table class="w-full table-fixed border-collapse leading-snug" :class="textSize">
    <colgroup v-if="showDiscount">
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
      <tr>
        <td colspan="7" class="border border-slate-300 bg-slate-200 px-1.5 py-1 text-left font-semibold align-middle" :class="sectionTitleSize">
          {{ title }}
        </td>
      </tr>
      <tr class="bg-slate-50">
        <td :class="headerCellClass">Item</td>
        <td :class="headerCellClass">Description</td>
        <td :class="headerCellClass">Qty</td>
        <td :colspan="showDiscount ? 1 : 3" :class="headerCellClass">List Price</td>
        <td v-if="showDiscount" :class="headerCellClass">Discount (%)</td>
        <td v-if="showDiscount" :class="headerCellClass">Discounted Price</td>
        <td :class="headerCellClass">Extended Price</td>
      </tr>
      <tr
        v-for="item in items"
        :key="item.id"
        class="h-8"
        :class="isLineChanged(item.id) ? 'bg-rose-50' : ''"
      >
        <td class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle" :class="highlightCellClass(isLineChanged(item.id))">
          {{ rowHasContent(item) ? item.lineNo : '' }}
        </td>
        <td class="whitespace-pre-line break-words border border-slate-300 px-1.5 py-1 align-middle" :class="isLineChanged(item.id) ? 'bg-rose-50 font-semibold text-rose-700' : 'text-slate-900'">
          {{ rowDescription(item) }}
        </td>
        <td class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle" :class="highlightCellClass(isLineChanged(item.id))">
          {{ rowHasContent(item) ? item.qty : '' }}
        </td>
        <td :colspan="showDiscount ? 1 : 3" :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
          {{ rowHasContent(item) ? money(item.listPrice) : '' }}
        </td>
        <td v-if="showDiscount" class="border border-slate-300 px-1.5 py-1 text-center font-mono align-middle" :class="highlightCellClass(isLineChanged(item.id))">
          {{ rowHasContent(item) && Number(item.discountPercent) > 0 ? percent(item.discountPercent) : '' }}
        </td>
        <td v-if="showDiscount" :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
          {{ rowHasContent(item) ? money(item.netUnitPrice) : '' }}
        </td>
        <td :class="[moneyCellClass, highlightCellClass(isLineChanged(item.id))]">
          {{ rowHasContent(item) ? money(item.extendedPrice) : '' }}
        </td>
      </tr>
      <tr>
        <td :colspan="totalsSpacerSpan" class="px-1.5 py-1 align-middle" />
        <td :colspan="totalsLabelSpan" class="whitespace-normal break-words border border-slate-300 px-1.5 py-1 text-right font-semibold leading-tight align-middle">
          {{ title === 'Software' ? 'Software subscription subtotal:' : 'Others Subtotal:' }}
        </td>
        <td :class="moneyTotalCellClass">{{ money(subtotal) }}</td>
      </tr>
    </tbody>
  </table>
</template>
