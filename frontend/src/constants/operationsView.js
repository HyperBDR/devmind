import { getAllTimezones, getTimezoneOffset } from '@/utils/timezones'

const defaultTimezone = 'Asia/Shanghai'

function normalizeOffsetLabel(offset) {
  const normalized = String(offset || 'GMT+00:00')
    .replace('GMT', 'UTC')
    .replace(/UTC([+-])(\d):/, 'UTC$10$2:')
    .replace('UTC+0:00', 'UTC+00:00')
    .replace('UTC-0:00', 'UTC-00:00')

  return normalized === 'UTC' ? 'UTC+00:00' : normalized
}

function offsetToMinutes(offsetLabel) {
  const match = /^UTC([+-])(\d{2}):(\d{2})$/.exec(offsetLabel)
  if (!match) {
    return 0
  }
  const [, sign, hours, minutes] = match
  const totalMinutes = Number(hours) * 60 + Number(minutes)
  return sign === '-' ? -totalMinutes : totalMinutes
}

const timezoneOptionsByOffset = new Map()

timezoneOptionsByOffset.set('UTC+08:00', {
  value: defaultTimezone,
  label: 'UTC+08:00'
})

for (const timezone of getAllTimezones()) {
  const offsetLabel = normalizeOffsetLabel(getTimezoneOffset(timezone.value))
  if (!timezoneOptionsByOffset.has(offsetLabel)) {
    timezoneOptionsByOffset.set(offsetLabel, {
      value: timezone.value,
      label: offsetLabel
    })
  }
}

export const OPERATIONS_TIMEZONES = Array.from(
  timezoneOptionsByOffset.values()
).sort(
  (left, right) => offsetToMinutes(left.label) - offsetToMinutes(right.label)
)

export const OPERATIONS_DEFAULT_TIMEZONE = defaultTimezone

export const OPERATIONS_CURRENCIES = ['CNY', 'USD']
