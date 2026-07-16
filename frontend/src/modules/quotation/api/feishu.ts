import { apiRequest, getAccessToken, getApiBaseUrl, ApiError } from './client';

export interface FeishuStatus {
  configured: boolean;
  connected: boolean;
  feishu_user_name?: string | null;
  feishu_open_id?: string | null;
  expires_at?: string | null;
  preferred_folder_token?: string | null;
  preferred_folder_name?: string | null;
  fallback_folder_token?: string | null;
  redirect_uri: string;
}

export interface FeishuFileItem {
  token: string;
  name: string;
  type: string;
  parent_token?: string | null;
  url?: string | null;
  created_time?: string | null;
  modified_time?: string | null;
  shortcut_info?: {
    target_type?: string | null;
    target_token?: string | null;
  } | null;
  open_token?: string | null;
  owner_id?: string | null;
}

export interface FeishuFolderList {
  folder_token: string;
  folder_name?: string | null;
  is_root?: boolean;
  files: FeishuFileItem[];
  has_more: boolean;
  next_page_token?: string | null;
}

export interface FeishuSearchResult {
  query: string;
  files: FeishuFileItem[];
  has_more: boolean;
  total?: number | null;
  offset: number;
}

export interface FeishuDriveTreeNode {
  token: string;
  name: string;
  type?: string;
}

export interface FeishuDriveTree {
  my_root: FeishuDriveTreeNode;
  my_folders: FeishuDriveTreeNode[];
  my_files: FeishuFileItem[];
  shared_folders: FeishuDriveTreeNode[];
  can_discover_shared?: boolean;
}

export interface FeishuImportResult {
  file_token: string;
  file_name: string;
  mime_type?: string | null;
  size_bytes: number;
  storage_key: string;
  document_id: string;
  doc_type: string;
  url?: string | null;
}

export interface FeishuUploadResult {
  file_token: string;
  file_name: string;
  folder_token: string;
  url?: string | null;
  size_bytes: number;
  reused_existing?: boolean;
  renamed_from?: string | null;
}

export interface FeishuUploadConflict {
  code: 'feishu_name_conflict';
  detail: string;
  folder_token: string;
  file_name: string;
  size_bytes: number;
  existing: {
    file_token: string;
    file_name: string;
    url?: string | null;
    size_bytes?: number | null;
  };
  suggested_file_name: string;
  actions: Array<'reuse' | 'rename' | 'cancel'>;
}

export type FeishuUploadConflictAction = 'reuse' | 'rename';

export class FeishuUploadConflictError extends Error {
  conflict: FeishuUploadConflict;

  constructor(conflict: FeishuUploadConflict) {
    super(conflict.detail || 'same file name already exists in folder');
    this.conflict = conflict;
  }
}

export interface FeishuPreferredFolder {
  preferred_folder_token: string;
  preferred_folder_name?: string | null;
}

export function getFeishuStatus(): Promise<FeishuStatus> {
  return apiRequest<FeishuStatus>('/feishu/status');
}

export async function startFeishuOAuth(returnTo?: string): Promise<string> {
  const params = new URLSearchParams();
  if (returnTo) params.set('return_to', returnTo);
  const query = params.toString() ? `?${params}` : '';
  const data = await apiRequest<{ authorize_url: string }>(`/feishu/oauth/start${query}`);
  return data.authorize_url;
}

export function listFeishuFolder(folder?: string): Promise<FeishuFolderList> {
  const query = folder ? `?folder=${encodeURIComponent(folder)}` : '';
  return apiRequest<FeishuFolderList>(`/feishu/folder${query}`);
}

export function searchFeishuDocuments(
  query: string,
  options?: { offset?: number; count?: number },
): Promise<FeishuSearchResult> {
  const params = new URLSearchParams({ q: query });
  if (options?.offset != null) params.set('offset', String(options.offset));
  if (options?.count != null) params.set('count', String(options.count));
  return apiRequest<FeishuSearchResult>(`/feishu/search?${params}`);
}

export function getFeishuDriveTree(): Promise<FeishuDriveTree> {
  return apiRequest<FeishuDriveTree>('/feishu/drive-tree');
}

export function bookmarkFeishuSharedFolder(
  folderToken: string,
  folderName?: string,
): Promise<{ shared_folders: FeishuDriveTreeNode[] }> {
  return apiRequest<{ shared_folders: FeishuDriveTreeNode[] }>('/feishu/drive-tree', {
    method: 'POST',
    body: JSON.stringify({
      folder_token: folderToken,
      folder_name: folderName || null,
    }),
  });
}

export function setPreferredFeishuFolder(
  folderToken: string,
  folderName?: string,
): Promise<FeishuPreferredFolder> {
  return apiRequest<FeishuPreferredFolder>('/feishu/preferred-folder', {
    method: 'PUT',
    body: JSON.stringify({
      folder_token: folderToken,
      folder_name: folderName || null,
    }),
  });
}

export interface FeishuFileAccessResult {
  exists: boolean;
  cleared?: boolean;
  file_token?: string;
  url?: string | null;
  name?: string | null;
}

export function checkFeishuFileAccess(
  fileToken: string,
  options?: {
    quotationId?: string;
    docType?: 'excel' | 'pdf';
    documentId?: string;
  },
): Promise<FeishuFileAccessResult> {
  const params = new URLSearchParams();
  if (options?.quotationId) params.set('quotation_id', options.quotationId);
  if (options?.docType) params.set('doc_type', options.docType);
  if (options?.documentId) params.set('document_id', options.documentId);
  const query = params.toString() ? `?${params}` : '';
  return apiRequest<FeishuFileAccessResult>(
    `/feishu/files/${encodeURIComponent(fileToken)}/access${query}`,
  );
}

export interface FeishuFileAccessBatchItem {
  file_token: string;
  quotation_id?: string;
  doc_type?: 'excel' | 'pdf';
  document_id?: string;
}

export interface FeishuFileAccessBatchResultItem {
  file_token: string;
  exists: boolean;
  cleared?: boolean;
  quotation_id?: string | null;
  doc_type?: 'excel' | 'pdf' | null;
  document_id?: string | null;
}

export function batchCheckFeishuFileAccess(
  items: FeishuFileAccessBatchItem[],
): Promise<{
  results: FeishuFileAccessBatchResultItem[];
  cleared_count: number;
}> {
  return apiRequest<{
    results: FeishuFileAccessBatchResultItem[];
    cleared_count: number;
  }>('/feishu/files/access/batch', {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

export function importFeishuFile(
  fileToken: string,
  fileName?: string,
  fileType?: string,
  fileUrl?: string | null,
): Promise<FeishuImportResult> {
  const params = new URLSearchParams();
  if (fileName) params.set('file_name', fileName);
  if (fileType) params.set('file_type', fileType);
  if (fileUrl) params.set('file_url', fileUrl);
  const query = params.toString() ? `?${params}` : '';
  return apiRequest<FeishuImportResult>(`/feishu/import/${encodeURIComponent(fileToken)}${query}`, {
    method: 'POST',
  });
}

export async function downloadFeishuFileToBrowser(
  fileToken: string,
  fileName: string,
  fileType?: string,
): Promise<void> {
  const token = getAccessToken();
  const params = new URLSearchParams();
  if (fileName) params.set('file_name', fileName);
  if (fileType) params.set('file_type', fileType);
  const response = await fetch(
    `${getApiBaseUrl()}/feishu/files/${encodeURIComponent(fileToken)}/content?${params}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    },
  );
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
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName || `${fileToken}.bin`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function uploadBlobToFeishu(
  blob: Blob,
  fileName: string,
  options?: {
    folder?: string;
    quotationId?: string;
    conflictAction?: FeishuUploadConflictAction;
  },
): Promise<FeishuUploadResult> {
  const form = new FormData();
  form.append('file', blob, fileName);
  if (options?.folder) form.append('folder', options.folder);
  if (options?.quotationId) form.append('quotation_id', options.quotationId);
  if (options?.conflictAction) form.append('conflict_action', options.conflictAction);

  try {
    return await apiRequest<FeishuUploadResult>('/feishu/upload', {
      method: 'POST',
      body: form,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const payload = error.data as Partial<FeishuUploadConflict> | undefined;
      if (payload?.code === 'feishu_name_conflict' && payload.existing && payload.suggested_file_name) {
        throw new FeishuUploadConflictError({
          code: 'feishu_name_conflict',
          detail: String(payload.detail || error.message),
          folder_token: String(payload.folder_token || options?.folder || ''),
          file_name: String(payload.file_name || fileName),
          size_bytes: Number(payload.size_bytes || blob.size),
          existing: {
            file_token: String(payload.existing.file_token || ''),
            file_name: String(payload.existing.file_name || fileName),
            url: payload.existing.url,
            size_bytes: payload.existing.size_bytes,
          },
          suggested_file_name: String(payload.suggested_file_name),
          actions: (payload.actions as FeishuUploadConflict['actions']) || ['reuse', 'rename', 'cancel'],
        });
      }
    }
    throw error;
  }
}

export function isFeishuFolderItem(file: FeishuFileItem): boolean {
  const type = (file.type || '').toLowerCase();
  if (type === 'folder' || type === 'drive#folder') return true;
  if (type === 'shortcut') {
    const target = (file.shortcut_info?.target_type || '').toLowerCase();
    return target === 'folder' || target === 'drive#folder';
  }
  return false;
}

export function resolveFeishuOpenToken(file: FeishuFileItem): string {
  if (file.open_token) return file.open_token;
  if (isFeishuFolderItem(file) && file.shortcut_info?.target_token) {
    return file.shortcut_info.target_token;
  }
  return file.token;
}
