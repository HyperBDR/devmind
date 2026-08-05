import type { Quotation, QuotationLineItem, QuoteVersion } from '../types';
import { apiRequest } from './client';

interface ApiQuotationItem {
  id?: string;
  line_no: number;
  type: string;
  item_id?: string | null;
  name?: string | null;
  description?: string | null;
  qty: number | string;
  list_price: number | string;
  discount_percent: number | string;
  net_unit_price: number | string;
  extended_price: number | string;
}

interface ApiQuotationVersion {
  id: string;
  version_no: number;
  status: string;
  notes: string;
  operator_email?: string | null;
  created_at: string;
  snapshot?: Record<string, unknown> | null;
}

interface ApiQuotation {
  id: string;
  quote_no: string;
  display_quote_no?: string;
  source_quote_no?: string;
  status: string;
  version_current: number;
  source_type: 'manual' | 'document_import';
  source_document_type?: 'excel' | 'pdf' | null;
  product_line: string;
  product_line_name?: string;
  project_name: string;
  currency: string;
  payment_term_option: string;
  payment_terms: string;
  quote_date: string;
  expire_date: string;
  tax_label: string;
  vat_rate: number | string;
  vat_amount: number | string;
  software_subtotal: number | string;
  others_subtotal: number | string;
  subtotal_before_vat: number | string;
  grand_total: number | string;
  remarks_disclaimer?: string | null;
  issuer_company_name: string;
  issuer_contact_name: string;
  issuer_contact_email: string;
  issuer_contact_title: string;
  issuer_signature?: string | null;
  client_company: string;
  contact_person: string;
  email: string;
  billing_company: string;
  billing_contact: string;
  billing_email: string;
  created_by_email?: string | null;
  feishu_file_token?: string | null;
  feishu_url?: string | null;
  feishu_path?: string | null;
  feishu_uploaded_at?: string | null;
  feishu_document_id?: string | null;
  feishu_excel_file_token?: string | null;
  feishu_excel_url?: string | null;
  feishu_excel_document_id?: string | null;
  feishu_excel_path?: string | null;
  feishu_excel_uploaded_at?: string | null;
  feishu_pdf_file_token?: string | null;
  feishu_pdf_url?: string | null;
  feishu_pdf_document_id?: string | null;
  feishu_pdf_path?: string | null;
  feishu_pdf_uploaded_at?: string | null;
  created_at: string;
  updated_at: string;
  items: ApiQuotationItem[];
  versions?: ApiQuotationVersion[];
}

interface ApiQuotationListItem {
  id: string;
  quote_no: string;
  display_quote_no: string;
  project_name: string;
  client_company: string;
  contact_person: string;
  quote_date?: string | null;
  issuer_contact_name?: string | null;
  created_at: string;
  currency: string;
  grand_total: number | string;
  status: string;
  source_type: 'manual' | 'document_import';
  source_document_type?: 'excel' | 'pdf' | null;
  source_document?: {
    id: string;
    doc_type: 'excel' | 'pdf';
    file_name: string;
    version_no: number;
  } | null;
  available_versions?: Array<{
    version_no: number;
    status: string;
    created_at: string;
  }>;
  product_line: string;
  product_line_name?: string;
  item_count: number;
  latest_excel_document_id?: string | null;
  latest_pdf_document_id?: string | null;
}

interface ApiQuotationFormContextItem {
  id: string;
  quote_no: string;
  display_quote_no: string;
  project_name: string;
  client_company: string;
  contact_person: string;
  email: string;
  product_line: string;
  product_line_name?: string;
  billing_company: string;
  billing_contact: string;
  billing_email: string;
  currency: string;
  tax_label: string;
  issuer_contact_name: string;
  issuer_contact_email: string;
  created_by_email?: string | null;
  created_at: string;
}

export interface QuotationListParams {
  page?: number;
  pageSize?: 10 | 20 | 50;
  search?: string;
  status?: Quotation['status'];
  productLine?: string;
  sourceType?: 'manual' | 'document_import';
  createdFrom?: string;
  createdTo?: string;
}

export interface QuotationListResult {
  items: Quotation[];
  productLines: string[];
  total: number;
  page: number;
  pageSize: 10 | 20 | 50;
  totalPages: number;
}

function toNumber(value: unknown): number {
  return Number(value || 0);
}

const STATUS_TO_API: Record<Quotation['status'], string> = {
  Draft: 'draft',
  Generated: 'generated',
  Uploaded: 'uploaded',
  Sent: 'sent',
  Accepted: 'accepted',
  Rejected: 'rejected',
  Expired: 'expired',
  Cancelled: 'cancelled',
};

const API_TO_STATUS: Record<string, Quotation['status']> = {
  draft: 'Draft',
  generated: 'Generated',
  uploaded: 'Uploaded',
  sent: 'Sent',
  accepted: 'Accepted',
  rejected: 'Rejected',
  expired: 'Expired',
  cancelled: 'Cancelled',
};

function mapStatus(status: string): Quotation['status'] {
  return API_TO_STATUS[status.toLowerCase()] || 'Draft';
}

function mapStatusToApi(status: Quotation['status']): string {
  return STATUS_TO_API[status] || 'draft';
}

function formatVersionTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  const ss = String(date.getSeconds()).padStart(2, '0');
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}

function mapApiItem(item: ApiQuotationItem | Record<string, unknown>): QuotationLineItem {
  const row = item as Record<string, unknown>;
  const typeValue = String(row.type || 'Software');
  return {
    id: String(row.id || row.line_no || ''),
    type: (typeValue as QuotationLineItem['type']) || 'Software',
    itemId: String(row.item_id || row.itemId || ''),
    name: String(row.name || ''),
    description: String(row.description || ''),
    listPrice: toNumber(row.list_price ?? row.listPrice),
    discountPercent: toNumber(row.discount_percent ?? row.discountPercent),
    qty: toNumber(row.qty),
    netUnitPrice: toNumber(row.net_unit_price ?? row.netUnitPrice),
    extendedPrice: toNumber(row.extended_price ?? row.extendedPrice),
  };
}

function snapText(
  snap: Record<string, unknown>,
  snake: string,
  camel: string,
): string {
  const value = snap[snake] ?? snap[camel];
  if (value == null) return '';
  return String(value);
}

function snapNumber(
  snap: Record<string, unknown>,
  snake: string,
  camel: string,
): number {
  return toNumber(snap[snake] ?? snap[camel]);
}

function totalsFromItems(
  items: QuotationLineItem[],
  vatRate: number,
): Pick<
  QuoteVersion,
  | 'softwareSubtotal'
  | 'othersSubtotal'
  | 'subtotalBeforeVat'
  | 'vatAmount'
  | 'grandTotal'
> {
  const softwareSubtotal = items
    .filter((item) => item.type === 'Software')
    .reduce((sum, item) => sum + item.extendedPrice, 0);
  const othersSubtotal = items
    .filter((item) => item.type !== 'Software')
    .reduce((sum, item) => sum + item.extendedPrice, 0);
  const subtotalBeforeVat = softwareSubtotal + othersSubtotal;
  const vatAmount = (subtotalBeforeVat * vatRate) / 100;
  return {
    softwareSubtotal,
    othersSubtotal,
    subtotalBeforeVat,
    vatAmount,
    grandTotal: subtotalBeforeVat + vatAmount,
  };
}

function mapApiVersion(version: ApiQuotationVersion): QuoteVersion {
  const snap = (version.snapshot || {}) as Record<string, unknown>;
  const rawItems = snap.items;
  const items = Array.isArray(rawItems)
    ? rawItems.map((item) => mapApiItem(item as ApiQuotationItem))
    : [];
  const vatRate = snapNumber(snap, 'vat_rate', 'vatRate');
  const storedTotals = {
    softwareSubtotal: snapNumber(snap, 'software_subtotal', 'softwareSubtotal'),
    othersSubtotal: snapNumber(snap, 'others_subtotal', 'othersSubtotal'),
    subtotalBeforeVat: snapNumber(
      snap,
      'subtotal_before_vat',
      'subtotalBeforeVat',
    ),
    vatAmount: snapNumber(snap, 'vat_amount', 'vatAmount'),
    grandTotal: snapNumber(snap, 'grand_total', 'grandTotal'),
  };
  const derivedTotals = totalsFromItems(items, vatRate);
  const useDerived =
    items.length > 0 &&
    storedTotals.grandTotal === 0 &&
    derivedTotals.grandTotal > 0;
  const totals = useDerived ? derivedTotals : storedTotals;

  return {
    id: version.id,
    versionNo: `V${version.version_no}`,
    updateTime: formatVersionTime(version.created_at),
    operator: version.operator_email || '',
    status: mapStatus(
      String(version.status || snap.status || 'draft'),
    ),
    notes: version.notes || '',
    items,
    projectName: snapText(snap, 'project_name', 'projectName'),
    clientCompany: snapText(snap, 'client_company', 'clientCompany'),
    contactPerson: snapText(snap, 'contact_person', 'contactPerson'),
    email: snapText(snap, 'email', 'email'),
    productLine: snapText(snap, 'product_line', 'productLine'),
    productLineName: snapText(
      snap,
      'product_line_name',
      'productLineName',
    ),
    billingCompany: snapText(snap, 'billing_company', 'billingCompany'),
    billingContact: snapText(snap, 'billing_contact', 'billingContact'),
    billingEmail: snapText(snap, 'billing_email', 'billingEmail'),
    region: '',
    industry: '',
    salesperson: snapText(snap, 'issuer_contact_name', 'issuerContactName'),
    createdByEmail:
      snapText(snap, 'created_by_email', 'createdByEmail') || undefined,
    currency:
      (snapText(snap, 'currency', 'currency') as Quotation['currency']) ||
      'USD',
    paymentTermOption: snapText(
      snap,
      'payment_term_option',
      'paymentTermOption',
    ) as Quotation['paymentTermOption'],
    paymentTerms: snapText(snap, 'payment_terms', 'paymentTerms'),
    quoteDate: snapText(snap, 'quote_date', 'quoteDate') || undefined,
    expireDate: snapText(snap, 'expire_date', 'expireDate') || undefined,
    remarksDisclaimer: snapText(
      snap,
      'remarks_disclaimer',
      'remarksDisclaimer',
    ),
    issuerCompanyName: snapText(
      snap,
      'issuer_company_name',
      'issuerCompanyName',
    ),
    issuerContactName: snapText(
      snap,
      'issuer_contact_name',
      'issuerContactName',
    ),
    issuerContactEmail: snapText(
      snap,
      'issuer_contact_email',
      'issuerContactEmail',
    ),
    issuerContactTitle: snapText(
      snap,
      'issuer_contact_title',
      'issuerContactTitle',
    ),
    issuerSignature: snapText(snap, 'issuer_signature', 'issuerSignature'),
    taxLabel: snapText(snap, 'tax_label', 'taxLabel'),
    vatRate,
    ...totals,
  };
}

export function mapApiQuotation(api: ApiQuotation): Quotation {
  return {
    id: api.id,
    quoteNo: api.display_quote_no || api.source_quote_no || api.quote_no,
    sourceType: api.source_type || 'manual',
    sourceDocumentType: api.source_document_type || undefined,
    versionCurrent: api.version_current || 0,
    projectName: api.project_name,
    clientCompany: api.client_company,
    contactPerson: api.contact_person,
    email: api.email,
    productLine: api.product_line,
    productLineName: api.product_line_name,
    billingCompany: api.billing_company,
    billingContact: api.billing_contact,
    billingEmail: api.billing_email,
    region: '',
    industry: '',
    salesperson: api.issuer_contact_name,
    createdByEmail: api.created_by_email || undefined,
    currency: (api.currency as Quotation['currency']) || 'USD',
    paymentTermOption: api.payment_term_option as Quotation['paymentTermOption'],
    paymentTerms: api.payment_terms,
    quoteDate: api.quote_date,
    expireDate: api.expire_date,
    remarksDisclaimer: api.remarks_disclaimer ?? '',
    issuerCompanyName: api.issuer_company_name,
    issuerContactName: api.issuer_contact_name,
    issuerContactEmail: api.issuer_contact_email,
    issuerContactTitle: api.issuer_contact_title,
    issuerSignature: api.issuer_signature ?? '',
    status: mapStatus(api.status),
    items: (api.items || []).map(mapApiItem),
    softwareSubtotal: toNumber(api.software_subtotal),
    othersSubtotal: toNumber(api.others_subtotal),
    subtotalBeforeVat: toNumber(api.subtotal_before_vat),
    taxLabel: api.tax_label,
    vatRate: toNumber(api.vat_rate),
    vatAmount: toNumber(api.vat_amount),
    grandTotal: toNumber(api.grand_total),
    createdAt: api.created_at,
    updatedAt: api.updated_at,
    feishuFileToken: api.feishu_file_token || undefined,
    feishuUrl: api.feishu_url || undefined,
    feishuPath: api.feishu_path || undefined,
    feishuUploadedAt: api.feishu_uploaded_at || undefined,
    feishuDocumentId: api.feishu_document_id || undefined,
    feishuExcelFileToken: api.feishu_excel_file_token || undefined,
    feishuExcelUrl: api.feishu_excel_url || undefined,
    feishuExcelDocumentId: api.feishu_excel_document_id || undefined,
    feishuExcelPath: api.feishu_excel_path || undefined,
    feishuExcelUploadedAt: api.feishu_excel_uploaded_at || undefined,
    feishuPdfFileToken: api.feishu_pdf_file_token || undefined,
    feishuPdfUrl: api.feishu_pdf_url || undefined,
    feishuPdfDocumentId: api.feishu_pdf_document_id || undefined,
    feishuPdfPath: api.feishu_pdf_path || undefined,
    feishuPdfUploadedAt: api.feishu_pdf_uploaded_at || undefined,
    versions: (api.versions || []).map(mapApiVersion),
  };
}

function mapApiQuotationListItem(api: ApiQuotationListItem): Quotation {
  return {
    id: api.id,
    quoteNo: api.display_quote_no || api.quote_no,
    sourceType: api.source_type || 'manual',
    sourceDocumentType: api.source_document_type || undefined,
    sourceDocument: api.source_document
      ? {
          id: api.source_document.id,
          docType: api.source_document.doc_type,
          fileName: api.source_document.file_name,
          versionNo: api.source_document.version_no,
        }
      : undefined,
    availableVersions: (api.available_versions || []).map((version) => ({
      versionNo: version.version_no,
      status: version.status,
      createdAt: version.created_at,
    })),
    projectName: api.project_name,
    clientCompany: api.client_company,
    contactPerson: api.contact_person,
    email: '',
    productLine: api.product_line,
    productLineName: api.product_line_name,
    region: '',
    industry: '',
    salesperson: api.issuer_contact_name || '',
    currency: (api.currency as Quotation['currency']) || 'USD',
    paymentTerms: '',
    status: mapStatus(api.status),
    items: [],
    itemCount: Number(api.item_count || 0),
    softwareSubtotal: 0,
    othersSubtotal: 0,
    subtotalBeforeVat: 0,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: toNumber(api.grand_total),
    quoteDate: api.quote_date || undefined,
    createdAt: api.created_at,
    feishuExcelDocumentId:
      api.latest_excel_document_id || undefined,
    feishuPdfDocumentId: api.latest_pdf_document_id || undefined,
  };
}

function mapApiQuotationFormContextItem(
  api: ApiQuotationFormContextItem,
): Quotation {
  return {
    id: api.id,
    quoteNo: api.display_quote_no || api.quote_no,
    projectName: api.project_name,
    clientCompany: api.client_company,
    contactPerson: api.contact_person,
    email: api.email,
    productLine: api.product_line,
    productLineName: api.product_line_name,
    billingCompany: api.billing_company,
    billingContact: api.billing_contact,
    billingEmail: api.billing_email,
    region: '',
    industry: '',
    salesperson: api.issuer_contact_name,
    issuerContactEmail: api.issuer_contact_email,
    createdByEmail: api.created_by_email || undefined,
    sourceType: 'manual',
    currency: (api.currency as Quotation['currency']) || 'USD',
    paymentTerms: '',
    taxLabel: api.tax_label,
    status: 'Draft',
    items: [],
    softwareSubtotal: 0,
    othersSubtotal: 0,
    subtotalBeforeVat: 0,
    vatRate: 0,
    vatAmount: 0,
    grandTotal: 0,
    createdAt: api.created_at,
  };
}

export function mapQuotationToCreatePayload(quote: Quotation) {
  return {
    quote_no: quote.quoteNo,
    product_line: quote.productLine || 'BDR',
    product_line_name: quote.productLineName || '',
    project_name: quote.projectName,
    currency: quote.currency,
    payment_term_option: quote.paymentTermOption || 'CIA',
    payment_terms: quote.paymentTerms,
    quote_date: quote.quoteDate,
    expire_date: quote.expireDate,
    tax_label: quote.taxLabel || 'VAT',
    vat_rate: quote.vatRate ?? 0,
    remarks_disclaimer: quote.remarksDisclaimer || '',
    issuer_company_name: quote.issuerCompanyName || 'OnePro Cloud Limited',
    issuer_contact_name: quote.issuerContactName || quote.salesperson,
    issuer_contact_email: quote.issuerContactEmail || '',
    issuer_contact_title: quote.issuerContactTitle || '',
    issuer_signature: quote.issuerSignature || '',
    client_company: quote.clientCompany,
    contact_person: quote.contactPerson,
    email: quote.email,
    billing_company: quote.billingCompany || quote.clientCompany,
    billing_contact: quote.billingContact || quote.contactPerson,
    billing_email: quote.billingEmail || quote.email,
    created_by_email: quote.createdByEmail,
    status: mapStatusToApi(quote.status),
    items: quote.items.map((item, index) => ({
      line_no: index + 1,
      type: item.type,
      item_id: item.itemId || null,
      name: item.name || null,
      description: item.description || null,
      qty: item.qty,
      list_price: item.listPrice,
      discount_percent: item.discountPercent,
      net_unit_price: item.netUnitPrice,
      extended_price: item.extendedPrice,
    })),
  };
}

export async function listQuotations(
  params: QuotationListParams = {},
): Promise<QuotationListResult> {
  const query = new URLSearchParams();
  query.set('page', String(params.page || 1));
  query.set('page_size', String(params.pageSize || 10));
  if (params.search?.trim()) query.set('search', params.search.trim());
  if (params.status) query.set('status', mapStatusToApi(params.status));
  if (params.productLine) {
    query.set('product_line_name', params.productLine);
  }
  if (params.sourceType) query.set('source_type', params.sourceType);
  if (params.createdFrom) query.set('created_from', params.createdFrom);
  if (params.createdTo) query.set('created_to', params.createdTo);
  const data = await apiRequest<{
    items: ApiQuotationListItem[];
    total: number;
    page: number;
    page_size: 10 | 20 | 50;
    total_pages: number;
    facets?: {
      product_lines?: string[];
    };
  }>(`/quotations?${query.toString()}`);
  return {
    items: data.items.map(mapApiQuotationListItem),
    productLines: data.facets?.product_lines || [],
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
    totalPages: data.total_pages,
  };
}

export async function getQuotation(quoteId: string): Promise<Quotation> {
  const data = await apiRequest<ApiQuotation>(`/quotations/${quoteId}`);
  return mapApiQuotation(data);
}

export async function getQuotationFormContext(): Promise<Quotation[]> {
  const data = await apiRequest<{
    items: ApiQuotationFormContextItem[];
  }>('/quotations/form-context');
  return data.items.map(mapApiQuotationFormContextItem);
}

export async function createQuotation(quote: Quotation): Promise<Quotation> {
  const created = await apiRequest<ApiQuotation>('/quotations', {
    method: 'POST',
    body: JSON.stringify(mapQuotationToCreatePayload(quote)),
  });
  return mapApiQuotation(created);
}

export async function updateQuotation(
  quote: Quotation,
  options?: { notes?: string; skipVersion?: boolean },
): Promise<Quotation> {
  const payload = {
    ...mapQuotationToCreatePayload(quote),
    ...(options?.notes ? { notes: options.notes } : {}),
    ...(options?.skipVersion ? { skip_version: true } : {}),
  };
  const updated = await apiRequest<ApiQuotation>(`/quotations/${quote.id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  return mapApiQuotation(updated);
}

export async function generateQuotation(quoteId: string, operatorEmail?: string): Promise<Quotation> {
  const generated = await apiRequest<ApiQuotation>(`/quotations/${quoteId}/generate`, {
    method: 'POST',
    body: JSON.stringify({
      operator_email: operatorEmail,
      notes: 'Generated quotation',
    }),
  });
  return mapApiQuotation(generated);
}

export async function deleteQuotation(quoteId: string): Promise<void> {
  await apiRequest<void>(`/quotations/${quoteId}`, {
    method: 'DELETE',
  });
}

export { mapStatusToApi };
