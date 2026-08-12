const DIMENSIONS = [
  ['input', 'text_input'],
  ['output', 'text_output'],
  ['cache', 'cache_input']
]

const BILLING_UNIT = 'per_1m_tokens'
const FLAT = 'flat'
const USAGE_RANGE = 'usage_range'

function decimal(value) {
  if (value === null || value === undefined || value === '') return null
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

function stableObjectKey(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableObjectKey).join(',')}]`
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableObjectKey(value[key])}`)
      .join(',')}}`
  }
  return JSON.stringify(value)
}

function tierBoundaryKey(item) {
  return [
    item.dimension,
    item.billing_unit,
    item.currency,
    item.tier_type,
    comparableDecimal(item.tier_start),
    comparableDecimal(item.tier_end)
  ].join(':')
}

function priceAtUsage(rows, usage) {
  const flatRow = rows.find((row) => row.flat || row.start === null)
  if (flatRow) return String(flatRow.price ?? '')
  const match = sortRows(rows).find((row) => {
    const start = decimal(row.start)
    const end = decimal(row.end)
    return start !== null && start <= usage && (end === null || usage < end)
  })
  return String(match?.price ?? '')
}

/** Keep one complete pricing variant when stale current specs overlap. */
export function selectPreferredChannelPriceItems(items = []) {
  const groups = new Map()
  items.forEach((item) => {
    const key = stableObjectKey(item?.spec || {})
    const group = groups.get(key) || []
    group.push(item)
    groups.set(key, group)
  })
  const ranked = [...groups.entries()].sort(
    ([leftKey, left], [rightKey, right]) => {
      const leftDimensions = new Set(left.map((item) => item.dimension)).size
      const rightDimensions = new Set(right.map((item) => item.dimension)).size
      const dimensionScore = rightDimensions - leftDimensions
      if (dimensionScore) return dimensionScore
      const emptySpecScore =
        Number(rightKey === '{}') - Number(leftKey === '{}')
      if (emptySpecScore) return emptySpecScore
      if (right.length !== left.length) return right.length - left.length
      const leftId = Math.min(...left.map((item) => Number(item.id || 0)))
      const rightId = Math.min(...right.map((item) => Number(item.id || 0)))
      return leftId - rightId
    }
  )
  const selected = ranked[0]?.[1] || []
  const boundaries = new Set()
  return selected.filter((item) => {
    const key = tierBoundaryKey(item)
    if (boundaries.has(key)) return false
    boundaries.add(key)
    return true
  })
}

/** Merge dimension-specific ranges into AGIOne-style shared tier cards. */
export function buildResaleTierCards(draft = {}) {
  const rowsByKey = Object.fromEntries(
    DIMENSIONS.map(([key]) => [
      key,
      Array.isArray(draft?.[key]) ? draft[key] : []
    ])
  )
  const hasTieredRows = DIMENSIONS.some(([key]) =>
    rowsByKey[key].some((row) => !row.flat && row.start !== null)
  )
  if (!hasTieredRows) {
    return [
      {
        end: null,
        flat: true,
        prices: Object.fromEntries(
          DIMENSIONS.map(([key]) => [
            key,
            String(rowsByKey[key][0]?.price ?? '')
          ])
        ),
        start: null
      }
    ]
  }

  const boundaries = new Set([0])
  let hasUnboundedTier = false
  DIMENSIONS.forEach(([key]) => {
    rowsByKey[key].forEach((row) => {
      if (row.flat || row.start === null) return
      const start = decimal(row.start)
      const end = decimal(row.end)
      if (start !== null) boundaries.add(start)
      if (end === null) hasUnboundedTier = true
      else boundaries.add(end)
    })
  })
  const sortedBoundaries = [...boundaries].sort((left, right) => left - right)
  const intervals = sortedBoundaries.slice(0, -1).map((start, index) => ({
    end: sortedBoundaries[index + 1],
    start
  }))
  if (hasUnboundedTier) {
    intervals.push({ end: null, start: sortedBoundaries.at(-1) })
  }

  return intervals.map(({ end, start }) => ({
    end: end === null ? null : String(end),
    flat: false,
    prices: Object.fromEntries(
      DIMENSIONS.map(([key]) => [key, priceAtUsage(rowsByKey[key], start)])
    ),
    start: String(start)
  }))
}

/** Convert shared tier cards back to the editable dimension draft. */
export function buildResaleTierDraftFromCards(cards = []) {
  return Object.fromEntries(
    DIMENSIONS.map(([key]) => [
      key,
      cards.map((card) => ({
        end: card.flat ? null : stringValue(card.end),
        flat: Boolean(card.flat),
        price: String(card.prices?.[key] ?? ''),
        start: card.flat ? null : stringValue(card.start)
      }))
    ])
  )
}

/** Add a shared tier while keeping the terminal range unbounded. */
export function addResaleTierCard(cards = [], step = 1000000) {
  const nextCards = cards.map((card) => ({
    ...card,
    prices: { ...card.prices }
  }))
  if (!nextCards.length) return nextCards
  if (nextCards.length === 1 && nextCards[0].flat) {
    const prices = { ...nextCards[0].prices }
    return [
      { end: String(step), flat: false, prices, start: '0' },
      { end: null, flat: false, prices: { ...prices }, start: String(step) }
    ]
  }
  const last = nextCards.at(-1)
  if (last.end !== null) {
    nextCards.push({
      end: null,
      flat: false,
      prices: { ...last.prices },
      start: String(last.end)
    })
    return nextCards
  }
  const split = String((decimal(last.start) || 0) + step)
  nextCards[nextCards.length - 1] = { ...last, end: split }
  nextCards.push({
    end: null,
    flat: false,
    prices: { ...last.prices },
    start: split
  })
  return nextCards
}

/** Update one shared boundary or price and preserve adjacent continuity. */
export function updateResaleTierCard(cards = [], index, field, value) {
  const nextCards = cards.map((card) => ({
    ...card,
    prices: { ...card.prices }
  }))
  const card = nextCards[index]
  if (!card) return nextCards
  if (DIMENSIONS.some(([key]) => key === field)) {
    card.prices[field] = value
    return nextCards
  }
  if (field === 'end') {
    const amount = decimal(value)
    const start = decimal(card.start)
    const nextCard = nextCards[index + 1]
    const nextEnd = decimal(nextCard?.end)
    if (nextCard && amount === null) return nextCards
    if (amount !== null && start !== null && amount <= start) return nextCards
    if (amount !== null && nextEnd !== null && amount >= nextEnd) {
      return nextCards
    }
  }
  card[field] = value
  if (field === 'end' && nextCards[index + 1]) {
    nextCards[index + 1].start = value
  }
  if (field === 'start' && nextCards[index - 1]) {
    nextCards[index - 1].end = value
  }
  return nextCards
}

/** Remove a shared tier and bridge the remaining interval cards. */
export function removeResaleTierCard(cards = [], index) {
  const nextCards = cards
    .filter((_, cardIndex) => cardIndex !== index)
    .map((card) => ({ ...card, prices: { ...card.prices } }))
  if (!nextCards.length) return nextCards
  if (index === 0) {
    nextCards[0].start = '0'
  } else if (index < cards.length - 1) {
    nextCards[index - 1].end = cards[index].end
  } else {
    nextCards[nextCards.length - 1].end = null
  }
  return nextCards
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

/** Keep adjacent editable usage ranges connected after a boundary edit. */
export function updateResaleTierRows(rows, index, field, value) {
  const nextRows = rows.map((row) => ({ ...row }))
  const current = nextRows[index]
  if (!current) return nextRows

  nextRows[index] = { ...current, [field]: value }

  if (field === 'end' && nextRows[index + 1] && !nextRows[index + 1].flat) {
    nextRows[index + 1] = {
      ...nextRows[index + 1],
      start: value
    }
  }

  if (field === 'start' && index > 0 && !nextRows[index - 1].flat) {
    nextRows[index - 1] = {
      ...nextRows[index - 1],
      end: value
    }
  }

  return nextRows
}

/** Remove one tier and bridge the remaining ranges without creating a gap. */
export function removeResaleTierRow(rows, index) {
  const nextRows = rows.filter((_, rowIndex) => rowIndex !== index)
  if (!nextRows.length) return nextRows

  const followingRow = rows[index + 1]
  if (index === 0 && !nextRows[0].flat) {
    nextRows[0] = { ...nextRows[0], start: '0' }
  } else if (followingRow && index > 0 && !nextRows[index - 1].flat) {
    nextRows[index - 1] = {
      ...nextRows[index - 1],
      end: followingRow.start ?? null
    }
  } else {
    const lastIndex = nextRows.length - 1
    if (!nextRows[lastIndex].flat) {
      nextRows[lastIndex] = { ...nextRows[lastIndex], end: null }
    }
  }

  return nextRows
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

/** Return whether two drafts expose the same upstream-controlled ranges. */
export function resaleTierDraftRangesMatch(left = {}, right = {}) {
  return DIMENSIONS.every(([key]) => {
    const leftRows = Array.isArray(left?.[key]) ? left[key] : []
    const rightRows = Array.isArray(right?.[key]) ? right[key] : []
    if (leftRows.length !== rightRows.length) return false
    return leftRows.every((row, index) => {
      const other = rightRows[index]
      return (
        Boolean(row.flat) === Boolean(other?.flat) &&
        comparableDecimal(row.start) === comparableDecimal(other?.start) &&
        comparableDecimal(row.end) === comparableDecimal(other?.end)
      )
    })
  })
}

/** Restore explicit draft work even when upstream boundaries changed later. */
export function shouldRestoreSavedResalePriceDraft(
  listing = {},
  savedDraft = {},
  upstreamDraft = {}
) {
  const pendingItems = Array.isArray(listing.pending_price_items)
    ? listing.pending_price_items
    : []
  if (pendingItems.length) return true
  return resaleTierDraftRangesMatch(savedDraft, upstreamDraft)
}

/** Prefer an unapproved draft when restoring a listing for further editing. */
export function resalePriceItemsForListing(listing = {}) {
  const pending = Array.isArray(listing.pending_price_items)
    ? listing.pending_price_items
    : []
  if (pending.length) return pending
  return Array.isArray(listing.current_price_items)
    ? listing.current_price_items
    : []
}

function comparableDecimal(value) {
  const parsed = decimal(value)
  return parsed === null ? null : parsed.toFixed(12)
}

function comparablePriceItem(item = {}) {
  return {
    billing_unit: item.billing_unit || BILLING_UNIT,
    currency: String(item.currency || '').toUpperCase(),
    dimension: item.dimension || '',
    tier_end: comparableDecimal(item.tier_end),
    tier_start: comparableDecimal(item.tier_start),
    tier_type: item.tier_type || FLAT,
    unit_price: comparableDecimal(item.unit_price)
  }
}

/** Compare API revision items while ignoring decimal formatting differences. */
export function resalePriceItemsMatch(left = [], right = []) {
  const normalize = (items) =>
    items
      .map(comparablePriceItem)
      .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)))
  return JSON.stringify(normalize(left)) === JSON.stringify(normalize(right))
}
