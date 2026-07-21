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

export async function deleteImportedDocument(documentId: string): Promise<void> {
  await apiRequest<void>(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });
}

export async function deleteImportedDocuments(
  documentIds: string[],
): Promise<{ deleted: string[]; failed: string[] }> {
  const deleted: string[] = [];
  const failed: string[] = [];
  await Promise.all(
    documentIds.map(async (documentId) => {
      try {
        await deleteImportedDocument(documentId);
        deleted.push(documentId);
      } catch {
        failed.push(documentId);
      }
    }),
  );
  return { deleted, failed };
}
