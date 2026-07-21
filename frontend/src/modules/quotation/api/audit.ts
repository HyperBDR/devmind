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
  changes: { fields?: string[] }
  metadata: { status_code?: number; version_no?: number }
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
  riskLevel?: string
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
    risk_level: filters.riskLevel,
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
    risk_level: filters.riskLevel,
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

export type SecurityAlertSeverity = 'medium' | 'high' | 'critical'
export type SecurityAlertStatus =
  | 'open'
  | 'acknowledged'
  | 'resolved'
  | 'false_positive'

export interface SecurityAlertEvidence {
  id: number
  action: string
  module: string
  target_id: string
  target_label: string
  request_id: string
  ip_address?: string | null
  created_at: string
}

export interface SecurityAlert {
  id: number
  alert_number: string
  rule: string
  severity: SecurityAlertSeverity
  status: SecurityAlertStatus
  title: string
  reason: string
  recommendation: string
  runbook: string
  owner: string
  threshold: number
  window_minutes: number
  subject_email: string
  subject_name: string
  source_ip?: string | null
  device: string
  trigger_count: number
  evidence_count: number
  first_detected_at: string
  last_detected_at: string
  acknowledged_at?: string | null
  resolved_at?: string | null
  resolution: string
  resolution_note: string
  notify_affected_user: boolean
  evidence?: SecurityAlertEvidence[]
}

export interface SecurityAlertSummary {
  open: number
  critical: number
  high: number
  new_last_24_hours: number
  immediate_review: number
  affected_users_last_24_hours: number
}

export interface SecurityAlertPage {
  items: SecurityAlert[]
  summary: SecurityAlertSummary
  total: number
  page: number
  page_size: number
  can_manage: boolean
}

export interface SecurityAlertFilters {
  search?: string
  severity?: string
  status?: string
  rule?: string
  days?: string
  page?: number
  pageSize?: number
}

export interface SecurityAlertDetailResponse {
  alert: SecurityAlert
  can_manage: boolean
}

export interface SecurityAlertUpdate {
  action: 'acknowledge' | 'resolve'
  resolution?: string
  resolution_note?: string
  notify_affected_user?: boolean
}

export async function listSecurityAlerts(
  filters: SecurityAlertFilters = {},
): Promise<SecurityAlertPage> {
  const params = new URLSearchParams()
  const values: Record<string, string | number | undefined> = {
    search: filters.search,
    severity: filters.severity,
    status: filters.status,
    rule: filters.rule,
    days: filters.days,
    page: filters.page,
    page_size: filters.pageSize,
  }
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      params.set(key, String(value))
    }
  })
  return apiRequest<SecurityAlertPage>(
    `/security-alerts?${params.toString()}`,
  )
}

export async function getSecurityAlert(
  alertId: number,
): Promise<SecurityAlertDetailResponse> {
  return apiRequest<SecurityAlertDetailResponse>(
    `/security-alerts/${alertId}`,
  )
}

export async function updateSecurityAlert(
  alertId: number,
  values: SecurityAlertUpdate,
): Promise<SecurityAlertDetailResponse> {
  return apiRequest<SecurityAlertDetailResponse>(
    `/security-alerts/${alertId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(values),
    },
  )
}
