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
  status: 'active' | 'expired' | 'revoked'
  created_at: string
  updated_at: string
  granted_by: string
}

export type QuotationMembershipRole = 'quotation_admin' | 'quotation_user'

export interface QuotationMembershipRecord {
  id: number | null
  user_id: number
  username: string
  name: string
  email: string
  role: QuotationMembershipRole | null
  assigned_by: string | null
  created_at: string | null
  updated_at: string | null
}

export interface QuotationMembershipContext {
  members: QuotationMembershipRecord[]
  role_options: Array<{
    value: QuotationMembershipRole
    label: string
  }>
}

export interface ViewPermissionContext {
  users: ViewPermissionUser[]
  folders: ViewPermissionFolder[]
  documents: ViewPermissionDocument[]
  permissions: ViewPermissionRecord[]
}

export interface GrantViewPermissionPayload {
  user_id: number
  target_type: 'folder' | 'document'
  target_id: string
  expires_at?: string | null
}

export function getViewPermissionContext(): Promise<ViewPermissionContext> {
  return apiRequest<ViewPermissionContext>('/view-permissions')
}

export function getMembershipContext(): Promise<QuotationMembershipContext> {
  return apiRequest<QuotationMembershipContext>('/memberships')
}

export function assignMembership(payload: {
  user_id: number
  role: QuotationMembershipRole
}): Promise<QuotationMembershipRecord> {
  return apiRequest<QuotationMembershipRecord>('/memberships', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateMembershipRole(
  id: number,
  role: QuotationMembershipRole
): Promise<QuotationMembershipRecord> {
  return apiRequest<QuotationMembershipRecord>(`/memberships/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ role })
  })
}

export function grantViewPermission(
  payload: GrantViewPermissionPayload
): Promise<ViewPermissionRecord> {
  return apiRequest<ViewPermissionRecord>('/view-permissions', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateViewPermissionExpiry(
  id: number,
  expiresAt: string | null
): Promise<ViewPermissionRecord> {
  return apiRequest<ViewPermissionRecord>(`/view-permissions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ expires_at: expiresAt })
  })
}

export function revokeViewPermission(id: number): Promise<void> {
  return apiRequest<void>(`/view-permissions/${id}`, { method: 'DELETE' })
}
