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
  created_by_email?: string | null;
  created_at?: string | null;
}

export function listImportedFeishuDocuments(): Promise<ImportedDocument[]> {
  return apiRequest<ImportedDocument[]>('/documents?source=feishu');
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

export async function deleteImportedDocument(documentId: string): Promise<void> {
  await apiRequest<void>(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });
}
