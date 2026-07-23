import { apiRequest, getAccessToken, getApiBaseUrl } from './client';

export interface ImportedDocument {
  id: string;
  quotation_id?: string | null;
  doc_type: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  source: string;
  feishu_file_token?: string | null;
  feishu_url?: string | null;
  feishu_folder_path?: Array<{
    token: string;
    name: string;
  }>;
  remote_access_available?: boolean;
  parse_result_id?: string | null;
  parse_status?: string;
  parse_confidence?: number | string | null;
  parsed_quotation_id?: string | null;
  parsed_quote_no?: string | null;
  created_by_email?: string | null;
  created_at?: string | null;
}

export interface ParsedQuotationItem {
  line_no: number;
  type: 'Software' | 'Service' | 'Other' | string;
  item_id?: string | null;
  name?: string | null;
  description?: string | null;
  qty: number | string;
  list_price: number | string;
  discount_percent: number | string;
  net_unit_price: number | string;
  extended_price: number | string;
}

export interface ParsedQuotationCandidate {
  quote_no: string;
  product_line: string;
  project_name: string;
  currency: string;
  payment_term_option: string;
  payment_terms: string;
  quote_date?: string | null;
  expire_date?: string | null;
  tax_label: string;
  vat_rate: number | string;
  remarks_disclaimer?: string;
  issuer_company_name: string;
  issuer_contact_name: string;
  issuer_contact_email: string;
  issuer_contact_title?: string;
  client_company: string;
  contact_person: string;
  email: string;
  billing_company?: string;
  billing_contact?: string;
  billing_email?: string;
  items: ParsedQuotationItem[];
}

export interface DocumentParseIssue {
  field: string;
  code: string;
  detail: string;
}

export interface DocumentParseResult {
  id: string;
  asset_id: string;
  sync_job_id?: string | null;
  quotation_id?: string | null;
  status: string;
  parser_name: string;
  parser_version: string;
  content_hash: string;
  normalized_json: ParsedQuotationCandidate;
  source_totals_json: Record<string, string>;
  field_confidence_json: Record<string, number>;
  validation_errors_json: DocumentParseIssue[];
  validation_warnings_json: DocumentParseIssue[];
  confidence: number | string;
  reused?: boolean;
  version_created?: boolean;
}

export interface ConfirmDocumentParseResult {
  quotation: {
    id: string;
    quote_no: string;
  };
  parse_result: DocumentParseResult;
  reused: boolean;
}

export function listImportedFeishuDocuments(): Promise<ImportedDocument[]> {
  return apiRequest<ImportedDocument[]>('/documents?source=feishu');
}

export function parseImportedDocument(
  documentId: string,
): Promise<DocumentParseResult> {
  return apiRequest<DocumentParseResult>(
    `/documents/${encodeURIComponent(documentId)}/parse`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export function getDocumentParseResult(
  documentId: string,
): Promise<DocumentParseResult> {
  return apiRequest<DocumentParseResult>(
    `/documents/${encodeURIComponent(documentId)}/parse`,
  );
}

export function confirmDocumentParseResult(
  parseResultId: string,
  quotation: ParsedQuotationCandidate,
): Promise<ConfirmDocumentParseResult> {
  return apiRequest<ConfirmDocumentParseResult>(
    `/document-parse-results/${encodeURIComponent(parseResultId)}/confirm`,
    {
      method: 'POST',
      body: JSON.stringify({ quotation }),
    },
  );
}

async function fetchDocumentResponse(documentId: string): Promise<Response> {
  const token = getAccessToken();
  const response = await fetch(`${getApiBaseUrl()}/documents/${encodeURIComponent(documentId)}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    let detail = `Download failed (${response.status})`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response;
}

async function fetchRemoteDocumentResponse(
  documentId: string,
): Promise<Response> {
  const token = getAccessToken();
  const baseUrl = getApiBaseUrl();
  const path = `/feishu/documents/${encodeURIComponent(documentId)}/content`;
  const response = await fetch(`${baseUrl}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    let detail = `Remote download failed (${response.status})`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(
      typeof detail === 'string' ? detail : JSON.stringify(detail),
    );
  }
  return response;
}

/** Fetch file bytes for in-app preview (does not trigger browser download). */
export async function fetchImportedDocumentBlob(documentId: string): Promise<Blob> {
  const response = await fetchDocumentResponse(documentId);
  return response.blob();
}

export async function downloadImportedDocument(documentId: string, fileName: string): Promise<void> {
  const blob = await fetchImportedDocumentBlob(documentId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadRemoteDocument(
  documentId: string,
  fileName: string,
): Promise<void> {
  const response = await fetchRemoteDocumentResponse(documentId);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
