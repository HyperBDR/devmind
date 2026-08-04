const DIMENSIONS = [
  ['input', 'text_input'],
  ['output', 'text_output'],
  ['cache', 'cache_input']
]

const BILLING_UNIT = 'per_1m_tokens'
const FLAT = 'flat'
const USAGE_RANGE = 'usage_range'

function decimal(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function stringValue(value) {
  if (value === null || value === undefined || value === '') return null
  return String(value)
}

function sortRows(rows) {
  return [...rows].sort((left, right) => {
    const leftStart = decimal(left.start) ?? Number.POSITIVE_INFINITY
    const rightStart = decimal(right.start) ?? Number.POSITIVE_INFINITY
    return leftStart - rightStart
  })
}

function isFlatRows(rows) {
  return rows.length === 1 && (rows[0].flat || rows[0].start === null)
}

function itemForRow(row, dimension, currency, tierType) {
  return {
    billing_unit: BILLING_UNIT,
    currency: String(currency || '').toUpperCase(),
    dimension,
    spec: {},
    tier_end: tierType === FLAT ? null : stringValue(row.end),
    tier_start: tierType === FLAT ? null : stringValue(row.start),
    tier_type: tierType,
    unit_price: String(row.price ?? '')
  }
}

/** Build the legacy one-row price table without changing flat behavior. */
export function buildFlatResalePriceItems(values, currency) {
  return DIMENSIONS.map(([key, dimension]) =>
    itemForRow({ flat: true, price: values?.[key] }, dimension, currency, FLAT)
  )
}

/** Convert the editable UI schedule into the normalized resale API payload. */
export function normalizeResalePriceDraft(draft, currency) {
  return DIMENSIONS.flatMap(([key, dimension]) => {
    const rows = Array.isArray(draft?.[key]) ? draft[key] : []
    if (isFlatRows(rows)) {
      return [itemForRow(rows[0], dimension, currency, FLAT)]
    }
    return sortRows(rows).map((row) =>
      itemForRow(row, dimension, currency, USAGE_RANGE)
    )
  })
}

/** Return whether a draft uses the tiered API representation. */
export function hasTieredResalePrices(draft) {
  return DIMENSIONS.some(([key]) =>
    (draft?.[key] || []).some((row) => row.flat === false)
  )
}

/** Return stable field error codes keyed by ``dimension:row:field``. */
export function validateResalePriceDraft(draft) {
  const errors = {}
  DIMENSIONS.forEach(([key]) => {
    const rows = Array.isArray(draft?.[key]) ? draft[key] : []
    if (!rows.length) {
      errors[`${key}:0:price`] = 'price_table.items_required'
      return
    }
    if (isFlatRows(rows)) {
      if (decimal(rows[0].price) === null || decimal(rows[0].price) < 0) {
        errors[`${key}:0:price`] = 'price_table.invalid_price'
      }
      return
    }
    let previousEnd = null
    rows.forEach((row, index) => {
      const start = decimal(row.start)
      const end = decimal(row.end)
      const price = decimal(row.price)
      if (price === null || price < 0) {
        errors[`${key}:${index}:price`] = 'price_table.invalid_price'
      }
      if (start === null || start < 0) {
        errors[`${key}:${index}:start`] = 'price_table_invalid_boundary'
        return
      }
      if (index === 0 && start !== 0) {
        errors[`${key}:${index}:start`] = 'price_table_missing_zero_start'
      }
      if (previousEnd !== null) {
        if (start < previousEnd) {
          errors[`${key}:${index}:start`] = 'price_table_overlap'
        } else if (start > previousEnd) {
          errors[`${key}:${index}:start`] = 'price_table_gap'
        }
      }
      if (end !== null && end <= start) {
        errors[`${key}:${index}:end`] = 'price_table_invalid_boundary'
      }
      if (index < rows.length - 1 && end === null) {
        errors[`${key}:${index}:end`] = 'price_table_missing_terminal'
      }
      previousEnd = end
    })
    const last = rows[rows.length - 1]
    if (last && decimal(last.end) !== null) {
      errors[`${key}:${rows.length - 1}:end`] = 'price_table_missing_terminal'
    }
  })
  return errors
}

/** Restore editable rows from a revision while retaining flat-mode ergonomics. */
export function resaleTierDraftFromItems(items = []) {
  return Object.fromEntries(
    DIMENSIONS.map(([key, dimension]) => {
      const rows = items
        .filter((item) => item.dimension === dimension)
        .sort(
          (left, right) =>
            Number(left.tier_start || 0) - Number(right.tier_start || 0)
        )
        .map((item) => ({
          end: item.tier_end === null ? null : String(item.tier_end),
          flat: item.tier_type === FLAT,
          price: String(item.unit_price ?? ''),
          start: item.tier_start === null ? null : String(item.tier_start)
        }))
      return [key, rows]
    })
  )
}
