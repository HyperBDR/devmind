import apiClient from '@/api'

export type InvoiceAccessRole = 'invoice_user' | 'invoice_admin'

export interface InvoiceAccessUser {
  id: number
  username: string
  name: string
  email: string
}

export interface InvoiceAccessRecord {
  id: number
  user_id: number
  user_name: string
  username: string
  email: string
  role: InvoiceAccessRole
  capabilities: Array<'view' | 'edit' | 'import' | 'issue'>
  expires_at: string | null
  status: 'active' | 'expired'
  created_at: string
  updated_at: string
  granted_by: string
}

export interface InvoiceAccessContext {
  users: InvoiceAccessUser[]
  permissions: InvoiceAccessRecord[]
}

function responseData<T>(response: { data: unknown }): T {
  const payload = response.data as { data?: T }
  return payload?.data ?? (response.data as T)
}

export async function getInvoiceAccessContext(): Promise<
  InvoiceAccessContext
> {
  const response = await apiClient.get('/v1/invoice/access-permissions')
  return responseData<InvoiceAccessContext>(response)
}

export async function grantInvoiceAccess(payload: {
  user_id: number
  expires_at: string | null
  role: InvoiceAccessRole
}): Promise<InvoiceAccessRecord> {
  const response = await apiClient.post(
    '/v1/invoice/access-permissions',
    payload,
  )
  return responseData<InvoiceAccessRecord>(response)
}

export async function updateInvoiceAccess(
  permissionId: number,
  payload: {
    expires_at?: string | null
    role?: InvoiceAccessRole
  },
): Promise<InvoiceAccessRecord> {
  const response = await apiClient.patch(
    `/v1/invoice/access-permissions/${permissionId}`,
    payload,
  )
  return responseData<InvoiceAccessRecord>(response)
}

export async function revokeInvoiceAccess(
  permissionId: number,
): Promise<void> {
  await apiClient.delete(`/v1/invoice/access-permissions/${permissionId}`)
}
