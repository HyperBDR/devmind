import apiClient from '@/api'

export const InvoiceStatus = {
  DRAFT: 'draft',
  ISSUED: 'issued',
  PAID: 'paid',
  VOID: 'void',
  CANCELLED: 'cancelled',
} as const

export type InvoiceStatus =
  (typeof InvoiceStatus)[keyof typeof InvoiceStatus]

export const InvoiceNumberingMode = {
  AUTO: 'auto',
  CUSTOM: 'custom',
} as const

export type InvoiceNumberingMode =
  (typeof InvoiceNumberingMode)[keyof typeof InvoiceNumberingMode]

export type InvoiceSourceType = 'manual' | 'pdf_upload' | 'feishu'

export type InvoiceDocumentKind =
  | 'invoice'
  | 'delivery_note'
  | 'withholding_tax'
  | 'proforma_invoice'
  | 'refund'

export interface InvoiceItem {
  id: string
  line_no: number
  product_code: string
  product_name: string
  description: string
  quantity: string
  unit_price: string
  discount_amount: string
  net_amount: string
  tax_rate: string
  tax_amount: string
  total_amount: string
}

export interface InvoiceRecord {
  id: string
  invoice_no: string
  document_kind: InvoiceDocumentKind
  numbering_mode: InvoiceNumberingMode
  product_line: string
  invoice_date: string | null
  due_date: string | null
  status: InvoiceStatus
  source_type: InvoiceSourceType
  currency: string
  seller_name: string
  seller_tax_id: string
  seller_address: string
  seller_website: string
  seller_email: string
  customer_name: string
  customer_tax_id: string
  customer_address: string
  customer_contact_person: string
  customer_contact_email: string
  customer_contact_phone: string
  contact_person: string
  contact_email: string
  purchase_order_no: string
  payment_terms: string
  region: string
  sales_owner: string
  tax_rate: string
  subtotal_amount: string
  tax_amount: string
  total_amount: string
  notes: string
  additional_notes: string
  remarks: string
  bank_account_name: string
  bank_name: string
  bank_address: string
  bank_account_number: string
  bank_code: string
  bank_branch_code: string
  bank_swift_code: string
  remittance_instruction: string
  signatory_name: string
  signatory_title: string
  issuer_signature: string
  pdf_available: boolean
  feishu_url: string
  created_by_email: string
  created_at: string
  updated_at: string
  items: InvoiceItem[]
}

export interface InvoiceListParams {
  search?: string
  customer?: string
  invoiceContact?: string
  invoiceContactEmail?: string
  region?: string
  salesOwner?: string
  status?: InvoiceStatus
  sourceType?: InvoiceSourceType
  currency?: string
  invoiceFrom?: string
  invoiceTo?: string
  page?: number
  pageSize?: 10 | 20 | 50
}

export interface InvoiceContactFacet {
  name: string
  email: string
}

export interface InvoiceListResult {
  items: InvoiceRecord[]
  currencies: string[]
  salesOwners: string[]
  invoiceContacts: InvoiceContactFacet[]
  page: number
  pageSize: 10 | 20 | 50
  total: number
  totalPages: number
}

export interface InvoiceFormContextResult {
  items: InvoiceRecord[]
  page: number
  pageSize: 20 | 50
  total: number
  totalPages: number
}

export interface InvoiceCreateItem {
  line_no: number
  product_code?: string
  product_name: string
  description: string
  quantity: number
  unit_price: number
}

export interface InvoiceCreatePayload {
  invoice_no: string
  numbering_mode: InvoiceNumberingMode
  product_line: string
  invoice_date: string
  status: 'draft' | 'issued' | 'paid'
  currency: string
  seller_name: string
  seller_tax_id: string
  seller_address: string
  seller_website: string
  seller_email: string
  customer_name: string
  customer_tax_id: string
  customer_address: string
  customer_contact_person: string
  customer_contact_email: string
  contact_person: string
  contact_email: string
  purchase_order_no: string
  payment_terms: string
  region: string
  sales_owner: string
  tax_rate: string
  additional_notes: string
  remarks: string
  bank_account_name: string
  bank_name: string
  bank_address: string
  bank_account_number: string
  bank_code: string
  bank_branch_code: string
  bank_swift_code: string
  remittance_instruction: string
  signatory_name: string
  signatory_title: string
  issuer_signature: string
  items: InvoiceCreateItem[]
}

export interface SalesAmountRow {
  amount: string
  invoice_count: number
}

export interface SalesPeriodRow extends SalesAmountRow {
  period: string
}

export interface SalesDimensionRow extends SalesAmountRow {
  name: string
  region?: string
}

export interface SalesDashboardData {
  as_of: string
  start_date: string
  end_date: string
  currency: string | null
  available_currencies: string[]
  granularity: 'month' | 'quarter' | 'year'
  series: SalesPeriodRow[]
  quarter_to_date: SalesPeriodRow[]
  year_to_date: SalesPeriodRow[]
  by_region: SalesDimensionRow[]
  by_product: SalesDimensionRow[]
  top_customers: SalesDimensionRow[]
  comparison: Array<{
    year: number
    series: SalesPeriodRow[]
    period_amount: string
    quarter_to_date_amount: string
    year_to_date_amount: string
  }>
  year_over_year: {
    amount: string
    previous_amount: string
    start_date: string
    end_date: string
    previous_start_date: string
    previous_end_date: string
  }
}

export interface InvoiceSyncRun {
  id: string
  status: 'pending' | 'queued' | 'running' | 'success' | 'failed'
  trigger: 'manual' | 'periodic'
  discovered_count: number
  created_count: number
  reused_count: number
  skipped_count: number
  failed_count: number
  error_message: string
  started_at: string | null
  finished_at: string | null
  created_at: string
  reused?: boolean
}

export interface InvoiceFeishuTarget {
  token: string
  name: string
}

export interface InvoiceFeishuFolderListing {
  current: InvoiceFeishuTarget
  items: InvoiceFeishuTarget[]
}

function responseData<T>(response: { data: unknown }): T {
  const payload = response.data as { data?: T }
  return payload?.data ?? (response.data as T)
}

export async function listInvoices(
  params: InvoiceListParams = {},
): Promise<InvoiceListResult> {
  const response = await apiClient.get('/v1/invoice/invoices', {
    params: {
      search: params.search,
      customer: params.customer,
      invoice_contact: params.invoiceContact,
      invoice_contact_email: params.invoiceContactEmail,
      region: params.region,
      sales_owner: params.salesOwner,
      status: params.status,
      source_type: params.sourceType,
      currency: params.currency,
      invoice_from: params.invoiceFrom,
      invoice_to: params.invoiceTo,
      page: params.page,
      page_size: params.pageSize,
    },
  })
  const payload = responseData<{
    items: InvoiceRecord[]
    page: number
    page_size: 10 | 20 | 50
    total: number
    total_pages: number
    facets?: {
      sales_owners?: string[]
      currencies?: string[]
      invoice_contacts?: InvoiceContactFacet[]
    }
  }>(response)
  return {
    items: payload.items,
    currencies: payload.facets?.currencies || [],
    salesOwners: payload.facets?.sales_owners || [],
    invoiceContacts: payload.facets?.invoice_contacts || [],
    page: payload.page,
    pageSize: payload.page_size,
    total: payload.total,
    totalPages: payload.total_pages,
  }
}

export async function getInvoice(invoiceId: string): Promise<InvoiceRecord> {
  const response = await apiClient.get(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}`,
  )
  return responseData<InvoiceRecord>(response)
}

export async function getInvoiceFormContext(
  page = 1,
): Promise<InvoiceFormContextResult> {
  const response = await apiClient.get('/v1/invoice/invoices/form-context', {
    params: { page, page_size: 50 },
  })
  const payload = responseData<{
    items: InvoiceRecord[]
    page: number
    page_size: 20 | 50
    total: number
    total_pages: number
  }>(response)
  return {
    items: payload.items,
    page: payload.page,
    pageSize: payload.page_size,
    total: payload.total,
    totalPages: payload.total_pages,
  }
}

export async function createInvoice(
  payload: InvoiceCreatePayload,
): Promise<InvoiceRecord> {
  const response = await apiClient.post('/v1/invoice/invoices', payload)
  return responseData<InvoiceRecord>(response)
}

export async function updateInvoice(
  invoiceId: string,
  payload: Partial<InvoiceCreatePayload>,
): Promise<InvoiceRecord> {
  const response = await apiClient.patch(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}`,
    payload,
  )
  return responseData<InvoiceRecord>(response)
}

export async function deleteInvoice(invoiceId: string): Promise<void> {
  await apiClient.delete(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}`,
  )
}

export async function uploadInvoiceToFeishu(
  invoiceId: string,
  folderToken: string,
): Promise<InvoiceRecord> {
  const response = await apiClient.post(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}/feishu`,
    { folder_token: folderToken },
  )
  return responseData<InvoiceRecord>(response)
}

export async function getInvoiceFeishuTargets(
  invoiceId: string,
  folderToken?: string,
): Promise<InvoiceFeishuFolderListing> {
  const response = await apiClient.get(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}/feishu`,
    { params: { folder_token: folderToken || undefined } },
  )
  return responseData<InvoiceFeishuFolderListing>(response)
}

export async function startInvoiceSync(): Promise<InvoiceSyncRun> {
  const response = await apiClient.post('/v1/invoice/feishu/sync')
  return responseData<InvoiceSyncRun>(response)
}

export async function getInvoiceSyncStatus(): Promise<InvoiceSyncRun | null> {
  const response = await apiClient.get('/v1/invoice/feishu/sync')
  return responseData<InvoiceSyncRun | null>(response)
}

export async function downloadInvoicePdf(
  invoiceId: string,
  invoiceNumber: string,
): Promise<void> {
  const response = await apiClient.get(
    `/v1/invoice/invoices/${encodeURIComponent(invoiceId)}/pdf`,
    { responseType: 'blob' },
  )
  const url = URL.createObjectURL(response.data as Blob)
  const safeNumber = invoiceNumber.replace(/[^A-Za-z0-9._-]+/g, '-')
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${safeNumber || invoiceId}.pdf`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export async function getSalesDashboard(params: {
  granularity: 'month' | 'quarter' | 'year'
  currency?: string
  start_date?: string
  end_date?: string
  comparison_years?: 1 | 2
  dimension?: 'region' | 'product' | 'customer'
}): Promise<SalesDashboardData> {
  const response = await apiClient.get('/v1/invoice/dashboard/analytics', {
    params,
  })
  return responseData<SalesDashboardData>(response)
}
