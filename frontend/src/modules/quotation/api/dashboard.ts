import type { Quotation } from '../types'
import { apiRequest } from './client'

export type DashboardTrendGrain = 'weekly' | 'monthly'
export type DashboardCurrency = string

function normalizeAnalyticsCurrency(currency: string): string {
  const code = String(currency || '').trim().toUpperCase()
  if (code === 'RMB') return 'CNY'
  if (code === 'EURO' || code === 'EUROS' || code === '€') return 'EUR'
  return code || currency
}

export interface DashboardSummary {
  currency: DashboardCurrency
  availableCurrencies: string[]
  availablePeriods: string[]
  currentPeriod: string
  previousPeriod: string
  monthQuoteCount: number
  previousMonthQuoteCount: number
  monthQuoteAmount: number
  previousMonthQuoteAmount: number
  monthWonAmount: number
  successRate: number
  successRateNumerator: number
  successRateDenominator: number
  followUpCount: number
  activeCount: number
  draftCount: number
  generatedAt: string
}

export interface DashboardBreakdownItem {
  quotationId: string
  quoteNo: string
  amount: number
  currency: DashboardCurrency
  status: Quotation['status']
}

export interface DashboardTrendPoint {
  period: string
  quoteAmount: number
  quoteCount: number
  createdAmount: number
  wonAmount: number
}

export interface DashboardAnalytics {
  currency: DashboardCurrency
  availableCurrencies: string[]
  amountBreakdown: DashboardBreakdownItem[]
  breakdownTotalAmount: number
  breakdownOmittedCount: number
  breakdownOmittedAmount: number
  trends: Record<DashboardTrendGrain, DashboardTrendPoint[]>
  generatedAt: string
}

export interface DashboardRecentQuotation {
  id: string
  quoteNo: string
  projectName: string
  clientCompany: string
  salesperson: string
  createdAt: string
  updatedAt: string
  currency: DashboardCurrency
  grandTotal: number
  status: Quotation['status']
}

interface ApiSummary {
  currency: DashboardCurrency
  available_currencies: string[]
  available_periods: string[]
  current_period: string
  previous_period: string
  month_quote_count: number
  previous_month_quote_count: number
  month_quote_amount: string
  previous_month_quote_amount: string
  month_won_amount: string
  success_rate: number
  success_rate_numerator: number
  success_rate_denominator: number
  follow_up_count: number
  active_count: number
  draft_count: number
  generated_at: string
}

interface ApiTrendPoint {
  period: string
  quote_amount: string
  quote_count: number
  created_amount: string
  won_amount: string
}

interface ApiAnalytics {
  currency: DashboardCurrency
  available_currencies: string[]
  amount_breakdown: Array<{
    quotation_id: string
    quote_no: string
    amount: string
    currency: DashboardCurrency
    status: string
  }>
  breakdown_total_amount: string
  breakdown_omitted_count: number
  breakdown_omitted_amount: string
  trends: Record<DashboardTrendGrain, ApiTrendPoint[]>
  generated_at: string
}

interface ApiRecentQuotation {
  id: string
  quote_no: string
  project_name: string
  client_company: string
  salesperson: string
  created_at: string
  updated_at: string
  currency: DashboardCurrency
  grand_total: string
  status: string
}

const API_TO_STATUS: Record<string, Quotation['status']> = {
  draft: 'Draft',
  generated: 'Generated',
  uploaded: 'Uploaded',
  sent: 'Sent',
  accepted: 'Accepted',
  rejected: 'Rejected',
  expired: 'Expired',
  cancelled: 'Cancelled'
}

function mapStatus(value: string): Quotation['status'] {
  return API_TO_STATUS[value.toLowerCase()] || 'Draft'
}

function dashboardQuery(
  currency: string,
  dateFrom = '',
  dateTo = ''
): string {
  const params = new URLSearchParams({ currency })
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  return params.toString()
}

export async function getDashboardSummary(
  period = '',
  dateFrom = '',
  dateTo = '',
  currency = 'USD'
): Promise<DashboardSummary> {
  const params = new URLSearchParams({ currency })
  if (period) params.set('period', period)
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const query = params.toString()
  const data = await apiRequest<ApiSummary>(
    query ? `/dashboard/summary?${query}` : '/dashboard/summary'
  )
  return {
    currency: data.currency,
    availableCurrencies: data.available_currencies,
    availablePeriods: data.available_periods,
    currentPeriod: data.current_period,
    previousPeriod: data.previous_period,
    monthQuoteCount: data.month_quote_count,
    previousMonthQuoteCount: data.previous_month_quote_count,
    monthQuoteAmount: Number(data.month_quote_amount || 0),
    previousMonthQuoteAmount: Number(data.previous_month_quote_amount || 0),
    monthWonAmount: Number(data.month_won_amount || 0),
    successRate: data.success_rate,
    successRateNumerator: data.success_rate_numerator,
    successRateDenominator: data.success_rate_denominator,
    followUpCount: data.follow_up_count,
    activeCount: data.active_count,
    draftCount: data.draft_count,
    generatedAt: data.generated_at
  }
}

export async function getDashboardAnalytics(
  currency = 'USD',
  dateFrom = '',
  dateTo = ''
): Promise<DashboardAnalytics> {
  const data = await apiRequest<ApiAnalytics>(
    `/dashboard/analytics?${dashboardQuery(currency, dateFrom, dateTo)}`
  )
  const mapTrend = (row: ApiTrendPoint): DashboardTrendPoint => ({
    period: row.period,
    quoteAmount: Number(row.quote_amount || 0),
    quoteCount: row.quote_count || 0,
    createdAmount: Number(row.created_amount || 0),
    wonAmount: Number(row.won_amount || 0)
  })
  return {
    currency: data.currency,
    availableCurrencies: data.available_currencies,
    amountBreakdown: data.amount_breakdown.map((row) => ({
      quotationId: row.quotation_id,
      quoteNo: row.quote_no,
      amount: Number(row.amount || 0),
      currency: normalizeAnalyticsCurrency(row.currency),
      status: mapStatus(row.status)
    })),
    breakdownTotalAmount: Number(data.breakdown_total_amount || 0),
    breakdownOmittedCount: data.breakdown_omitted_count,
    breakdownOmittedAmount: Number(data.breakdown_omitted_amount || 0),
    trends: {
      monthly: data.trends.monthly.map(mapTrend),
      weekly: data.trends.weekly.map(mapTrend)
    },
    generatedAt: data.generated_at
  }
}

export async function getDashboardRecent(
  limit = 5
): Promise<DashboardRecentQuotation[]> {
  const data = await apiRequest<{ items: ApiRecentQuotation[] }>(
    `/dashboard/recent?limit=${limit}`
  )
  return data.items.map((row) => ({
    id: row.id,
    quoteNo: row.quote_no,
    projectName: row.project_name,
    clientCompany: row.client_company,
    salesperson: row.salesperson,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    currency: row.currency,
    grandTotal: Number(row.grand_total || 0),
    status: mapStatus(row.status)
  }))
}
