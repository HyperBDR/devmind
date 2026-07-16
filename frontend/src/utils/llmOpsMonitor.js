const OPERATIONAL_SCOPE = 'operational'
const MARKET_REFERENCE_SCOPE = 'market_reference'

export function operationScopeForRow(row = {}) {
  if (
    row.operation_scope === OPERATIONAL_SCOPE ||
    row.operation_scope === MARKET_REFERENCE_SCOPE
  ) {
    return row.operation_scope
  }
  if (Number(row.coverage_count || 0) > 0) return OPERATIONAL_SCOPE
  if (row.current_listing?.is_listed || row.is_agione_listed) {
    return OPERATIONAL_SCOPE
  }
  return MARKET_REFERENCE_SCOPE
}

export function isMonitorRowVisible(row, filter) {
  const scope = operationScopeForRow(row)
  if (filter === 'all' || filter === OPERATIONAL_SCOPE) {
    return scope === OPERATIONAL_SCOPE
  }
  if (filter === MARKET_REFERENCE_SCOPE) {
    return scope === MARKET_REFERENCE_SCOPE
  }
  if (filter === 'priority') {
    return scope === OPERATIONAL_SCOPE && Number(row.decision_priority || 8) < 8
  }
  return scope === OPERATIONAL_SCOPE && row.decision_status === filter
}

export function summarizeMonitorRows(rows = []) {
  const operationalRows = rows.filter(
    (row) => operationScopeForRow(row) === OPERATIONAL_SCOPE
  )
  return {
    lowYield: operationalRows.filter(
      (row) => row.decision_status === 'low_yield'
    ).length,
    missingChannel: operationalRows.filter(
      (row) => row.decision_status === 'no_supply'
    ).length,
    needsAction: operationalRows.filter(
      (row) => Number(row.decision_priority || 8) < 8
    ).length,
    operational: operationalRows.length,
    pendingListing: operationalRows.filter(
      (row) => row.decision_status === 'unlisted'
    ).length,
    ready: operationalRows.filter((row) => row.decision_status === 'ready')
      .length
  }
}
