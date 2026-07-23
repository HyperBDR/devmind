import { apiRequest, ApiError } from './client';

export interface FeishuStatus {
  configured: boolean;
  connected: boolean;
  mode?: 'system_archive_folder' | string;
  feishu_user_name?: string | null;
  feishu_open_id?: string | null;
  expires_at?: string | null;
  preferred_folder_token?: string | null;
  preferred_folder_name?: string | null;
  fallback_folder_token?: string | null;
  redirect_uri: string;
}

export interface FeishuUploadResult {
  document_id: string;
  file_name: string;
  folder_token: string;
  size_bytes: number;
  reused_existing?: boolean;
  renamed_from?: string | null;
  direct_access_allowed: boolean;
  file_token?: string;
  url?: string;
  replica_id?: string;
  replica_pending?: boolean;
  storage_connection_id?: string;
}

export interface FeishuUploadConflict {
  code: 'feishu_name_conflict';
  detail: string;
  folder_token: string;
  file_name: string;
  size_bytes: number;
  existing: {
    file_token?: string;
    file_name: string;
    size_bytes?: number | null;
    url?: string | null;
  };
  suggested_file_name: string;
  actions: Array<'reuse' | 'rename' | 'cancel'>;
}

export type FeishuUploadConflictAction = 'reuse' | 'rename';

export interface FeishuFileItem {
  token: string;
  open_token?: string;
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
}

export interface FeishuFolderListing {
  folder_token: string;
  folder_name: string;
  root_folder_token?: string;
  is_root: boolean;
  files: FeishuFileItem[];
  has_more: boolean;
  next_page_token?: string | null;
}

export interface FeishuArchiveFolder {
  token: string;
  name: string;
  parent_token: string | null;
}

export interface FeishuArchiveFileLocation {
  document_id: string;
  folder_token: string;
}

export class FeishuUploadConflictError extends Error {
  conflict: FeishuUploadConflict;

  constructor(conflict: FeishuUploadConflict) {
    super(conflict.detail || 'same file name already exists in folder');
    this.conflict = conflict;
  }
}

export function getFeishuStatus(): Promise<FeishuStatus> {
  return apiRequest<FeishuStatus>('/feishu/status');
}

export function syncFeishuArchiveFolder(options: {
  source?: 'automatic' | 'user';
} = {}): Promise<{
  created_count: number;
  skipped_count: number;
  errors?: Array<{ file?: string; detail?: string }>;
  folders: FeishuArchiveFolder[];
  file_locations: FeishuArchiveFileLocation[];
  sync_job_id?: string;
  storage_connection_id?: string | null;
}> {
  return apiRequest<{
    created_count: number;
    skipped_count: number;
    errors?: Array<{ file?: string; detail?: string }>;
    folders: FeishuArchiveFolder[];
    file_locations: FeishuArchiveFileLocation[];
    sync_job_id?: string;
    storage_connection_id?: string | null;
  }>('/feishu/sync-folder', {
    method: 'POST',
    headers: {
      'X-Quotation-Audit-Source': options.source || 'user',
    },
    body: JSON.stringify({}),
  });
}

export function listFeishuFolder(folderToken?: string): Promise<FeishuFolderListing> {
  const params = new URLSearchParams();
  if (folderToken) params.set('folder_token', folderToken);
  const query = params.toString() ? `?${params}` : '';
  return apiRequest<FeishuFolderListing>(`/feishu/folder${query}`);
}

export function isFeishuFolderItem(item: FeishuFileItem): boolean {
  const type = String(item.type || '').toLowerCase();
  if (type === 'folder' || type === 'drive#folder') return true;
  if (type !== 'shortcut') return false;
  const target = String(item.shortcut_info?.target_type || '').toLowerCase();
  return target === 'folder' || target === 'drive#folder';
}

export function feishuFolderOpenToken(item: FeishuFileItem): string {
  return item.open_token || item.shortcut_info?.target_token || item.token;
}

export interface FeishuFileAccessResult {
  exists: boolean;
  cleared?: boolean;
  document_id: string;
  direct_access_allowed?: boolean;
  url?: string;
  content_url?: string;
}

export function checkFeishuFileAccess(
  documentId: string,
): Promise<FeishuFileAccessResult> {
  return apiRequest<FeishuFileAccessResult>(
    `/feishu/documents/${encodeURIComponent(documentId)}/access`,
  );
}

export interface FeishuFileAccessBatchItem {
  document_id: string;
}

export interface FeishuFileAccessBatchResultItem {
  exists: boolean;
  cleared?: boolean;
  document_id: string;
  direct_access_allowed?: false;
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

export async function uploadBlobToFeishu(
  blob: Blob,
  fileName: string,
  options?: {
    quotationId?: string;
    conflictAction?: FeishuUploadConflictAction;
    folderToken?: string;
  },
): Promise<FeishuUploadResult> {
  const form = new FormData();
  form.append('file', blob, fileName);
  if (options?.quotationId) form.append('quotation_id', options.quotationId);
  if (options?.conflictAction) form.append('conflict_action', options.conflictAction);
  if (options?.folderToken) form.append('folder_token', options.folderToken);

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
          folder_token: String(payload.folder_token || ''),
          file_name: String(payload.file_name || fileName),
          size_bytes: Number(payload.size_bytes || blob.size),
          existing: {
            file_name: String(payload.existing.file_name || fileName),
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
