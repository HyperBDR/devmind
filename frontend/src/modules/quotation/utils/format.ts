export function formatMoney(value: number | string | null | undefined, currency = 'USD'): string {
  const num = Number(value || 0)
  try {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(num)
  } catch {
    return `${currency} ${num.toFixed(2)}`
  }
}

export function formatBytes(size: number): string {
  if (!size || size < 0) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

/**
 * Fallback Chinese labels for legacy call sites.
 * Prefer quoteStatusLabel() from useQuotationI18n for UI.
 */
export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    generated: '已生成',
    uploaded: '已上传',
    sent: '已发送',
    accepted: '已成交',
    rejected: '已拒绝',
    expired: '已过期',
    cancelled: '已作废',
    Draft: '草稿',
    Generated: '已生成',
    Uploaded: '已上传',
    Sent: '已发送',
    Accepted: '已成交',
    Rejected: '已拒绝',
    Expired: '已过期',
    Cancelled: '已作废',
  }
  return map[status] || status
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function plusDaysISO(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}
