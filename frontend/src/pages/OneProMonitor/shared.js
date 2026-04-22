export function unwrap(response) {
  return response?.data?.data ?? response?.data ?? response
}

export function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function toNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function percentage(numerator, denominator) {
  const total = toNumber(denominator, 0)
  if (!total) return 0
  return Math.round((toNumber(numerator, 0) / total) * 100)
}

export function taskStatus(status) {
  const value = String(status || '').toLowerCase()
  if (value === 'completed') return 'completed'
  if (value === 'failed') return 'failed'
  if (value === 'running') return 'processing'
  if (value === 'pending') return 'pending'
  return 'disabled'
}

export function pillClass(status) {
  const value = String(status || '').toLowerCase()
  if (['active', 'activated', 'healthy', 'success', 'valid'].includes(value)) {
    return 'bg-green-100 text-green-700 border-green-200'
  }
  if (['running', 'warning', 'processing', 'pending'].includes(value)) {
    return 'bg-amber-100 text-amber-700 border-amber-200'
  }
  if (
    [
      'failed',
      'disabled',
      'error',
      'unhealthy',
      'disconnected',
      'invalid'
    ].includes(value)
  ) {
    return 'bg-red-100 text-red-700 border-red-200'
  }
  return 'bg-gray-100 text-gray-700 border-gray-200'
}

export const ONEPRO_HOST_STATUS_OPTIONS = [
  'sync_snapshot_done',
  'host_register_done',
  'sync_failed',
  'clean_failed',
  'sync_doing',
  'clean_doing',
  'boot_doing',
  'boot_failed',
  'boot_done',
  'sync_stopped',
  'sync_queued'
]

const ONEPRO_HOST_STATUS_TONES = {
  sync_snapshot_done: 'bg-green-100 text-green-700 border-green-200',
  host_register_done: 'bg-green-100 text-green-700 border-green-200',
  boot_done: 'bg-green-100 text-green-700 border-green-200',
  sync_failed: 'bg-red-100 text-red-700 border-red-200',
  clean_failed: 'bg-red-100 text-red-700 border-red-200',
  boot_failed: 'bg-red-100 text-red-700 border-red-200',
  sync_doing: 'bg-amber-100 text-amber-700 border-amber-200',
  clean_doing: 'bg-amber-100 text-amber-700 border-amber-200',
  boot_doing: 'bg-amber-100 text-amber-700 border-amber-200',
  sync_queued: 'bg-amber-100 text-amber-700 border-amber-200',
  sync_stopped: 'bg-gray-100 text-gray-700 border-gray-200'
}

const ONEPRO_BOOT_STATUS_TONES = {
  booted: 'bg-green-100 text-green-700 border-green-200',
  boot_done: 'bg-green-100 text-green-700 border-green-200',
  clean_done: 'bg-green-100 text-green-700 border-green-200',
  active: 'bg-green-100 text-green-700 border-green-200',
  not_boot: 'bg-gray-100 text-gray-700 border-gray-200',
  not_booted: 'bg-gray-100 text-gray-700 border-gray-200',
  boot_doing: 'bg-amber-100 text-amber-700 border-amber-200',
  boot_failed: 'bg-red-100 text-red-700 border-red-200'
}

const ONEPRO_HEALTH_STATUS_TONES = {
  healthy: 'bg-green-100 text-green-700 border-green-200',
  active: 'bg-green-100 text-green-700 border-green-200',
  warning: 'bg-amber-100 text-amber-700 border-amber-200',
  unhealthy: 'bg-red-100 text-red-700 border-red-200',
  disconnected: 'bg-red-100 text-red-700 border-red-200'
}

function translateStatus(t, path, value) {
  const normalized = String(value || '').toLowerCase()
  if (!normalized) return t('hyperbdrMonitor.labels.unknown')
  const translated = t(`${path}.${normalized}`)
  return translated === `${path}.${normalized}` ? value : translated
}

export function oneProHostStatusLabel(status, t) {
  return translateStatus(t, 'hyperbdrMonitor.statusText.host', status)
}

export function oneProBootStatusLabel(status, t) {
  return translateStatus(t, 'hyperbdrMonitor.statusText.boot', status)
}

export function oneProHealthStatusLabel(status, t) {
  return translateStatus(t, 'hyperbdrMonitor.statusText.health', status)
}

export function oneProHostStatusClass(status) {
  return (
    ONEPRO_HOST_STATUS_TONES[String(status || '').toLowerCase()] ||
    'bg-gray-100 text-gray-700 border-gray-200'
  )
}

export function oneProBootStatusClass(status) {
  return (
    ONEPRO_BOOT_STATUS_TONES[String(status || '').toLowerCase()] ||
    'bg-gray-100 text-gray-700 border-gray-200'
  )
}

export function oneProHealthStatusClass(status) {
  return (
    ONEPRO_HEALTH_STATUS_TONES[String(status || '').toLowerCase()] ||
    'bg-gray-100 text-gray-700 border-gray-200'
  )
}
