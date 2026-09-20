function normalizeSearchValue(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
}

export function buildCloudBillingAccountSearchText(account, context = {}) {
  const tags = Array.isArray(account?.tags) ? account.tags : []
  const providerAliases = Array.isArray(context.providerAliases)
    ? context.providerAliases
    : []

  return [
    context.accountLabel,
    context.providerLabel,
    context.paymentTypeLabel,
    account?.name,
    account?.provider,
    account?.provider_type,
    account?.account_id,
    account?.notes,
    account?.category,
    account?.type,
    ...providerAliases,
    ...tags
  ]
    .map(normalizeSearchValue)
    .filter(Boolean)
    .join(' ')
}

export function cloudBillingAccountMatchesQuery(account, query, context = {}) {
  const tokens = normalizeSearchValue(query).split(/\s+/).filter(Boolean)
  if (tokens.length === 0) {
    return true
  }

  const haystack = buildCloudBillingAccountSearchText(account, context)
  return tokens.every((token) => haystack.includes(token))
}
