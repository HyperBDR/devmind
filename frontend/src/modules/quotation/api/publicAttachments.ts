import { apiRequest } from './client'

export type PublicAttachmentStatus = 'active' | 'archived'

export interface PublicAttachment {
  id: string
  asset_id: string
  file_name: string
  mime_type: string
  file_type?: string
  size_bytes: number
  scope: string
  product_line: string
  service_name: string
  status: PublicAttachmentStatus
  uploaded_by: string
  created_at: string
}

export function listPublicAttachments(): Promise<PublicAttachment[]> {
  return apiRequest<PublicAttachment[]>('/public-attachments')
}

export function uploadPublicAttachment(
  file: File,
  metadata: { scope: string; productLine?: string; serviceName?: string },
): Promise<PublicAttachment> {
  const body = new FormData()
  body.append('file', file)
  body.append('scope', metadata.scope)
  body.append('product_line', metadata.productLine || '')
  body.append('service_name', metadata.serviceName || '')
  return apiRequest<PublicAttachment>('/public-attachments', {
    method: 'POST',
    body,
  })
}

export function updatePublicAttachmentStatus(
  id: string,
  status: PublicAttachmentStatus,
): Promise<PublicAttachment> {
  return apiRequest<PublicAttachment>(
    `/public-attachments/${encodeURIComponent(id)}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    },
  )
}
