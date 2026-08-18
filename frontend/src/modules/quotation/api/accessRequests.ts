import { apiRequest } from './client'

import type {
  ViewPermissionDocument,
  ViewPermissionFolder,
} from './viewPermissions'

export type AccessRequestType =
  | 'folder_view'
  | 'document_view'
  | 'folder_upload'

export type AccessRequestStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'revoked'
  | 'expired'

export interface AccessRequestRecord {
  id: number
  applicant_id: number
  applicant: string
  request_type: AccessRequestType
  target_id: string
  target_name: string
  reason: string
  status: AccessRequestStatus
  reviewer: string
  review_note: string
  expires_at: string | null
  created_at: string
  updated_at: string
  reviewed_at: string | null
  revoked_at: string | null
  expired_at: string | null
}

export interface AccessRequestContext {
  is_admin: boolean
  folders: Array<Pick<ViewPermissionFolder, 'token' | 'name'>>
  documents: ViewPermissionDocument[]
  requests: AccessRequestRecord[]
}

export function getAccessRequestContext(): Promise<AccessRequestContext> {
  return apiRequest<AccessRequestContext>('/access-requests')
}

export function submitAccessRequest(payload: {
  request_type: AccessRequestType
  target_id: string
  reason: string
}): Promise<AccessRequestRecord> {
  return apiRequest<AccessRequestRecord>('/access-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function decideAccessRequest(
  id: number,
  payload: {
    action: 'approve' | 'reject' | 'revoke' | 'expire'
    review_note?: string
    expires_at?: string | null
  },
): Promise<AccessRequestRecord> {
  return apiRequest<AccessRequestRecord>(`/access-requests/${id}/decision`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
