function hasValue(value) {
  return value !== null && value !== undefined && String(value).trim() !== ''
}

const rawFieldAliases = {
  amount: 'amount',
  '付款金额': 'amount',
  '充值金额': 'amount',
  currency: 'currency',
  '币种': 'currency',
  current_balance: 'current_balance',
  '当前余额': 'current_balance',
  '提交时余额': 'current_balance',
  balance_threshold: 'balance_threshold',
  '余额阈值': 'balance_threshold',
  days_remaining_threshold: 'days_remaining_threshold',
  '剩余天数阈值': 'days_remaining_threshold',
  '预计使用天数阈值': 'days_remaining_threshold'
}

function normalizeRawFieldName(value) {
  const label = String(value || '')
    .replaceAll('*', '')
    .trim()
  return rawFieldAliases[label] || rawFieldAliases[label.toLowerCase()]
}

function parseKeyValueRechargeInfo(text) {
  const result = {}
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const pair = line.match(/^(.+?)[：:=]\s*(.*)$/)
    let field
    let value
    if (pair) {
      field = normalizeRawFieldName(pair[1])
      value = pair[2].trim()
    } else {
      field = normalizeRawFieldName(line)
      if (field && index + 1 < lines.length) {
        value = lines[index + 1]
        index += 1
      }
    }
    if (field && hasValue(value)) result[field] = value
    if (!result.currency && /^[A-Za-z]{3,5}$/.test(line)) {
      result.currency = line.toUpperCase()
    }
  }

  if (hasValue(result.amount) && !hasValue(result.currency)) {
    const currency = String(result.amount).match(/\b([A-Za-z]{3,5})$/)
    if (currency) result.currency = currency[1].toUpperCase()
  }
  return result
}

function parseRawRechargeInfo(value) {
  if (value && typeof value === 'object') return value
  const text = String(value || '').trim()
  if (!text) return {}
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return parseKeyValueRechargeInfo(text)
  }
}

function firstValue(...values) {
  return values.find(hasValue)
}

function withCurrency(value, currency) {
  if (!hasValue(value)) return '-'
  const text = String(value).trim()
  const currencyText = String(currency || '')
    .trim()
    .toUpperCase()
  if (!currencyText) return text
  if (text.toUpperCase().endsWith(` ${currencyText}`)) return text
  return `${text} ${currencyText}`
}

export function getRechargeApprovalSnapshot(item, options = {}) {
  const context = item?.context_payload || {}
  const request = item?.request_payload || {}
  const raw = parseRawRechargeInfo(item?.raw_recharge_info)
  const currency = firstValue(request.currency, context.currency, raw.currency)
  const balance = firstValue(
    context.current_balance,
    request.current_balance,
    raw.current_balance
  )
  const balanceThreshold = firstValue(
    context.balance_threshold,
    request.balance_threshold,
    raw.balance_threshold
  )
  const daysThreshold = firstValue(
    context.days_remaining_threshold,
    request.days_remaining_threshold,
    raw.days_remaining_threshold
  )
  const amount = firstValue(request.amount, context.amount, raw.amount)

  let threshold = '-'
  if (hasValue(balanceThreshold)) {
    threshold = withCurrency(balanceThreshold, currency)
  } else if (hasValue(daysThreshold)) {
    const daysUnit = String(options.daysUnit || 'days').trim()
    threshold = `${String(daysThreshold).trim()} ${daysUnit}`
  }

  return {
    submittedBalance: withCurrency(balance, currency),
    threshold,
    rechargeAmount: withCurrency(amount, currency)
  }
}
