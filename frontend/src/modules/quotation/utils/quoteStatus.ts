import type { QuoteStatus } from '../types'

/**
 * Statuses still in the active sales pipeline (not closed).
 */
export const OPEN_QUOTE_STATUSES: QuoteStatus[] = [
  'Generated',
  'Uploaded',
  'Sent',
]

/**
 * Statuses that count toward "awaiting signature / follow-up".
 */
export const EXPIRING_SOON_STATUSES: QuoteStatus[] = [
  'Generated',
  'Uploaded',
  'Sent',
]

/**
 * Closed-won revenue statuses.
 */
export const WON_QUOTE_STATUSES: QuoteStatus[] = ['Accepted']

/**
 * Status order for dashboard amount-by-status chart.
 */
export const STATUS_CHART_ORDER: QuoteStatus[] = [
  'Draft',
  'Generated',
  'Uploaded',
  'Sent',
  'Accepted',
  'Rejected',
  'Expired',
  'Cancelled',
]

/**
 * Quotes counted in amount charts (exclude cancelled).
 */
export function isChartQuoteStatus(status: QuoteStatus): boolean {
  return status !== 'Cancelled'
}

export function isOpenQuoteStatus(status: QuoteStatus): boolean {
  return OPEN_QUOTE_STATUSES.includes(status)
}

export function isExpiringSoonStatus(status: QuoteStatus): boolean {
  return EXPIRING_SOON_STATUSES.includes(status)
}

export function isWonQuoteStatus(status: QuoteStatus): boolean {
  return WON_QUOTE_STATUSES.includes(status)
}

export function quoteStatusBadgeClass(status: QuoteStatus): string {
  const base =
    'inline-flex items-center gap-1 whitespace-nowrap rounded border px-2 py-0.5 text-sm'
  switch (status) {
    case 'Draft':
      return `${base} border-dm-border bg-[#fafafa] text-dm-text-secondary`
    case 'Generated':
      return `${base} border-[#91caff] bg-dm-primary-bg text-dm-primary`
    case 'Uploaded':
      return `${base} border-[#87e8de] bg-[#e6fffb] text-[#08979c]`
    case 'Sent':
      return `${base} border-[#d3adf7] bg-[#f9f0ff] text-[#722ed1]`
    case 'Accepted':
      return `${base} border-[#b7eb8f] bg-dm-success-bg text-[#389e0d]`
    case 'Rejected':
      return `${base} border-[#ffccc7] bg-dm-error-bg text-dm-error`
    case 'Expired':
      return `${base} border-[#ffe58f] bg-dm-warning-bg text-[#d48806]`
    case 'Cancelled':
      return `${base} border-dm-border bg-[#fafafa] text-dm-text-tertiary`
    default:
      return `${base} border-dm-border bg-[#fafafa] text-dm-text-secondary`
  }
}

export function quoteStatusBarClass(status: QuoteStatus): string {
  switch (status) {
    case 'Draft':
      return 'bg-[#8c8c8c]'
    case 'Generated':
      return 'bg-[#1677ff]'
    case 'Uploaded':
      return 'bg-[#08979c]'
    case 'Sent':
      return 'bg-[#722ed1]'
    case 'Accepted':
      return 'bg-[#389e0d]'
    case 'Rejected':
      return 'bg-[#cf1322]'
    case 'Expired':
      return 'bg-[#d48806]'
    case 'Cancelled':
      return 'bg-[#595959]'
    default:
      return 'bg-[#1677ff]'
  }
}

/**
 * Solid fill color for pie / chart.js datasets.
 */
export function quoteStatusChartColor(status: QuoteStatus): string {
  switch (status) {
    case 'Draft':
      return '#8c8c8c'
    case 'Generated':
      return '#1677ff'
    case 'Uploaded':
      return '#08979c'
    case 'Sent':
      return '#722ed1'
    case 'Accepted':
      return '#389e0d'
    case 'Rejected':
      return '#cf1322'
    case 'Expired':
      return '#d48806'
    case 'Cancelled':
      return '#595959'
    default:
      return '#1677ff'
  }
}
