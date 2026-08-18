import { apiRequest } from './client'

import type {
  ViewPermissionFolder,
  ViewPermissionUser,
} from './viewPermissions'

export interface UploadPermissionRecord {
  id: number
  user_id: number
  user_name: string
  folder_token: string
  folder_name: string
  expires_at: string | null
  created_at: string
  granted_by: string
}

export interface UploadPermissionContext {
  users: ViewPermissionUser[]
  folders: ViewPermissionFolder[]
  permissions: UploadPermissionRecord[]
}

export function getUploadPermissionContext(): Promise<UploadPermissionContext> {
  return apiRequest<UploadPermissionContext>('/upload-permissions')
}

export function grantUploadPermission(payload: {
  user_id: number
  folder_token: string
  expires_at?: string | null
}): Promise<UploadPermissionRecord> {
  return apiRequest<UploadPermissionRecord>('/upload-permissions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateUploadPermission(
  id: number,
  expiresAt: string | null,
): Promise<UploadPermissionRecord> {
  return apiRequest<UploadPermissionRecord>(`/upload-permissions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ expires_at: expiresAt }),
  })
}

export function revokeUploadPermission(id: number): Promise<void> {
  return apiRequest<void>(`/upload-permissions/${id}`, {
    method: 'DELETE',
  })
}
