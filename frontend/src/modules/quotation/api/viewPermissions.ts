import { apiRequest } from './client'

export interface ViewPermissionUser {
  id: number
  username: string
  name: string
  email: string
}

export interface ViewPermissionFolder {
  token: string
  name: string
  path: unknown[]
}

export interface ViewPermissionDocument {
  id: string
  file_token: string
  file_name: string
  folder_token: string
  folder_name: string
  quotation_id: string | null
  quote_no: string
}

export interface ViewPermissionRecord {
  id: number
  user_id: number
  user_name: string
  target_type: 'folder' | 'document'
  target_id: string
  target_name: string
  folder_token: string
  document_id: string | null
  expires_at: string | null
  created_at: string
  granted_by: string
}

export interface ViewPermissionContext {
  users: ViewPermissionUser[]
  folders: ViewPermissionFolder[]
  documents: ViewPermissionDocument[]
  permissions: ViewPermissionRecord[]
}

export function getViewPermissionContext(): Promise<ViewPermissionContext> {
  return apiRequest<ViewPermissionContext>('/view-permissions')
}

export function grantViewPermission(payload: {
  user_id: number
  target_type: 'folder' | 'document'
  target_id: string
}): Promise<ViewPermissionRecord> {
  return apiRequest<ViewPermissionRecord>('/view-permissions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function revokeViewPermission(id: number): Promise<void> {
  return apiRequest<void>(`/view-permissions/${id}`, { method: 'DELETE' })
}
