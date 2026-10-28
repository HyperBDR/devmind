export function applyRules(dashboard, thresholds) {
 const customers = dashboard.customers.map(customer => {
  const signals = customer.signals.filter(x => !['inactive','decline','technical'].includes(x))
  if (customer.inactivity?.state === 'READY' && customer.inactivity.daysWithoutCalls >= thresholds.inactivityDays) signals.push('inactive')
  if (customer.comparisonState === 'READY' && Number.isFinite(customer.changePercent) && customer.changePercent <= -thresholds.declinePercent) signals.push('decline')
  const s = customer.summary
  if (s.failureClassificationComplete && s.unknownCount === 0 && s.requestCount >= thresholds.minTechnicalRequests && Number.isFinite(s.technicalFailureCount) && s.technicalFailureCount > 0 && s.technicalFailureCount / s.requestCount * 100 >= thresholds.technicalFailurePercent) signals.push('technical')
  return {...customer, signals}
 })
 return {...dashboard, customers,
  decline: customers.filter(x => x.signals.includes('decline')),
  inactive: customers.filter(x => x.signals.includes('inactive')),
  technicalFailures: customers.filter(x => x.signals.includes('technical'))}
}
