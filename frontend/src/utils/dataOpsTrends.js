function parseCurrentMonth(currentMonth) {
  const [year, month] = String(currentMonth || '').split('-').map(Number)
  if (!year || month < 1 || month > 12) return null
  return { month, year }
}

function monthDescriptor(index) {
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  const key = `${year}-${String(month).padStart(2, '0')}`
  return { key, label: key, year }
}

function quarterDescriptor(index) {
  const year = Math.floor(index / 4)
  const quarter = (index % 4) + 1
  return {
    key: `${year}-Q${quarter}`,
    label: `${year} Q${quarter}`,
    year,
  }
}

function yearDescriptor(year) {
  const key = String(year)
  return { key, label: key, year }
}

function numericRangeDescriptors(period, count, current) {
  if (period === 'year') {
    return Array.from(
      { length: count },
      (_, index) => yearDescriptor(current.year - count + index)
    )
  }
  if (period === 'quarter') {
    const quarter = Math.floor((current.month - 1) / 3)
    const currentIndex = current.year * 4 + quarter
    return Array.from(
      { length: count },
      (_, index) => quarterDescriptor(currentIndex - count + index)
    )
  }
  const currentIndex = current.year * 12 + current.month - 1
  return Array.from(
    { length: count },
    (_, index) => monthDescriptor(currentIndex - count + index)
  )
}

function yearToDateDescriptors(period, current) {
  if (period === 'year') return []
  if (period === 'quarter') {
    const currentQuarter = Math.floor((current.month - 1) / 3)
    return Array.from(
      { length: currentQuarter },
      (_, index) => quarterDescriptor(current.year * 4 + index)
    )
  }
  return Array.from(
    { length: current.month - 1 },
    (_, index) => monthDescriptor(current.year * 12 + index)
  )
}

function completePeriodDescriptors(options) {
  const current = parseCurrentMonth(options.currentMonth)
  if (!current) return []
  if (options.range === 'ytd') {
    return yearToDateDescriptors(options.period, current)
  }
  const count = Math.max(0, Number(options.range || 0))
  return numericRangeDescriptors(options.period, count, current)
}

function periodKey(monthValue, period) {
  const current = parseCurrentMonth(monthValue)
  if (!current) return ''
  if (period === 'year') return String(current.year)
  if (period === 'quarter') {
    const quarter = Math.floor((current.month - 1) / 3) + 1
    return `${current.year}-Q${quarter}`
  }
  return `${current.year}-${String(current.month).padStart(2, '0')}`
}

function amountMap(items, valueKey, options) {
  const amounts = new Map()
  for (const item of items || []) {
    if ((item.currency || '') !== options.currency) continue
    const key = periodKey(item.month, options.period)
    if (!key) continue
    amounts.set(
      key,
      (amounts.get(key) || 0) + Number(item[valueKey] || 0)
    )
  }
  return amounts
}

function addDeltas(rows) {
  return rows.map((row, index) => {
    const previous = rows[index - 1]?.amount
    const delta = previous
      ? ((row.amount - previous) / previous) * 100
      : null
    return { ...row, delta }
  })
}

export function buildAmountTrendRows(
  items,
  options,
  valueKey = 'amount'
) {
  const amounts = amountMap(items, valueKey, options)
  const rows = completePeriodDescriptors(options).map((period) => ({
    ...period,
    amount: amounts.get(period.key) || 0,
  }))
  return addDeltas(rows)
}

export function buildCashTrendRows(receivedItems, expenseItems, options) {
  const received = amountMap(receivedItems, 'amount', options)
  const expense = amountMap(expenseItems, 'amount', options)
  return completePeriodDescriptors(options).map((period) => {
    const receivedAmount = received.get(period.key) || 0
    const expenseAmount = expense.get(period.key) || 0
    return {
      ...period,
      expense: expenseAmount,
      net: receivedAmount - expenseAmount,
      received: receivedAmount,
    }
  })
}

export function availableTrendCurrencies(...series) {
  const currencies = new Set()
  for (const items of series) {
    for (const item of items || []) {
      if (item.currency) currencies.add(item.currency)
    }
  }
  return [...currencies].sort((left, right) => {
    if (left === 'CNY') return -1
    if (right === 'CNY') return 1
    return left.localeCompare(right)
  })
}
