function defaultBalanceValue(account) {
  const value = account?.balance ?? account?.display_funds ?? 0
  return Number(value || 0)
}

function defaultCostValue(account) {
  return Number(account?.cost || 0)
}

function hasDaysRemainingReference(account) {
  return Boolean(account?.has_days_remaining_reference)
}

function isKnownUnavailable(account) {
  return account?.is_available === false
}

function isKnownOverdrawn(account) {
  return (
    account?.type === 'prepaid' &&
    account?.balance != null &&
    Number(account.balance) <= 0
  )
}

function accountPriority(account) {
  if (isKnownUnavailable(account) || isKnownOverdrawn(account)) return 0
  if (account?.is_data_stale) return 1
  if (String(account?.risk || '').toLowerCase() === 'high') return 2
  if (hasDaysRemainingReference(account)) return 3
  return 4
}

function mustIncludeInTrend(account) {
  return accountPriority(account) <= 1
}

export function isCloudBillingAccountCritical(account) {
  return accountPriority(account) <= 2
}

export function hasCloudBillingBalance(account) {
  if (account?.balance == null) return false
  return Number(account.balance) > 0 || account?.type === 'prepaid'
}

export function compareCloudBillingAccounts(
  a,
  b,
  balanceValue = defaultBalanceValue,
  costValue = defaultCostValue
) {
  const priorityDifference = accountPriority(a) - accountPriority(b)
  if (priorityDifference) return priorityDifference

  const aHasReference = hasDaysRemainingReference(a)
  const bHasReference = hasDaysRemainingReference(b)
  if (aHasReference && bHasReference) {
    return (
      Number(a.days_remaining || 0) - Number(b.days_remaining || 0) ||
      costValue(b) - costValue(a)
    )
  }

  if (!aHasReference && !bHasReference) {
    return balanceValue(a) - balanceValue(b) || costValue(b) - costValue(a)
  }

  return aHasReference ? -1 : 1
}

export function selectCloudBillingTrendAccounts(
  accounts,
  softLimit = 5,
  balanceValue = defaultBalanceValue,
  costValue = defaultCostValue
) {
  const sorted = [...(accounts || [])].sort((a, b) =>
    compareCloudBillingAccounts(a, b, balanceValue, costValue)
  )
  const required = sorted.filter(mustIncludeInTrend)
  const remainingSlots = Math.max(softLimit - required.length, 0)
  const supplemental = sorted
    .filter((account) => !mustIncludeInTrend(account))
    .slice(0, remainingSlots)
  return [...required, ...supplemental]
}
