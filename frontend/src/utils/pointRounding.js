const MAX_POINT_DECIMAL_PLACES = 6

export function normalizePointDecimalPlaces(value) {
  const places = Number(value)
  if (!Number.isFinite(places)) return 0
  return Math.min(MAX_POINT_DECIMAL_PLACES, Math.max(0, Math.trunc(places)))
}

export function formatRoundedPoints(value, pointConversion = {}) {
  const points = Number(value)
  if (!Number.isFinite(points)) return '0'

  const decimalPlaces = normalizePointDecimalPlaces(
    pointConversion.decimal_places ?? pointConversion.point_decimal_places
  )
  const factor = 10 ** decimalPlaces
  const scaled = points * factor
  const mode =
    pointConversion.rounding_mode ||
    pointConversion.point_rounding_mode ||
    'half_up'
  let rounded

  if (mode === 'up') {
    rounded = Math.ceil(scaled)
  } else if (mode === 'down') {
    rounded = Math.floor(scaled)
  } else {
    rounded = Math.round(scaled)
  }

  return (rounded / factor).toFixed(decimalPlaces)
}
