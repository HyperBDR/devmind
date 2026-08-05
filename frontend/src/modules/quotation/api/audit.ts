import { apiRequest, getAccessToken, getApiBaseUrl } from './client'

export interface AuditEvent {
  id: number
  actor_email: string
  actor_name: string
  actor_type: 'user' | 'system' | 'task'
  actor_role_snapshot: string
  event_name: string
  module: string
  action: string
  result: 'succeeded' | 'denied' | 'failed'
  reason_code: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  target_type: string
  target_id: string
  target_label: string
  summary: string
  changes: {
    fields?: string[]
    [field: string]: unknown
  }
  metadata: {
    status_code?: number
    version_no?: number
    created_count?: number
    skipped_count?: number
    parsed_count?: number
    queued_parse_count?: number
    created_quotation_count?: number
    updated_quotation_count?: number
    error_count?: number
    folder_count?: number
    folder_names?: string[]
  }
  request_id: string
  trace_id: string
  quotation_id_snapshot: string
  document_id_snapshot: string
  workspace_id: string
  error_code: string
  ip_address?: string | null
  user_agent: string
  created_at: string
}

export interface AuditEventFilters {
  search?: string
  actor?: string
  module?: string
  action?: string
  result?: string
  eventName?: string
  requestId?: string
  quotationId?: string
  documentId?: string
  dateFrom?: string
  dateTo?: string
  page?: number
  pageSize?: number
}

export interface AuditEventPage {
  items: AuditEvent[]
  total: number
  page: number
  page_size: number
  can_export: boolean
}

export async function listAuditEvents(
  filters: AuditEventFilters = {},
): Promise<AuditEventPage> {
  const params = new URLSearchParams()
  const values: Record<string, string | number | undefined> = {
    search: filters.search,
    actor: filters.actor,
    module: filters.module,
    action: filters.action,
    result: filters.result,
    event_name: filters.eventName,
    request_id: filters.requestId,
    quotation_id: filters.quotationId,
    document_id: filters.documentId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    page: filters.page,
    page_size: filters.pageSize,
  }
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      params.set(key, String(value))
    }
  })
  return apiRequest<AuditEventPage>(`/audit-events?${params.toString()}`)
}

function auditQuery(filters: AuditEventFilters): string {
  const params = new URLSearchParams()
  const values: Record<string, string | number | undefined> = {
    search: filters.search,
    actor: filters.actor,
    module: filters.module,
    action: filters.action,
    result: filters.result,
    event_name: filters.eventName,
    request_id: filters.requestId,
    quotation_id: filters.quotationId,
    document_id: filters.documentId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  }
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.toString()
}

export async function downloadAuditExport(
  filters: AuditEventFilters = {},
): Promise<void> {
  const headers = new Headers()
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(
    `${getApiBaseUrl()}/audit-events/export?${auditQuery(filters)}`,
    { headers },
  )
  if (!response.ok) throw new Error(`Audit export failed (${response.status})`)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'quote-desk-audit.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}
