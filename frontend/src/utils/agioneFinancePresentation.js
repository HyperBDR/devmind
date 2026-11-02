export function finiteFinance(value) {
  if (value == null || !['number', 'string'].includes(typeof value) || String(value).trim() === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function financeReason(reason) {
  const messages = {
    not_collected: '此范围没有可用的已缓存财务，不触发补采。',
    finance_scope_unverified: '财务客户归属尚未确认，已隔离，不能计入汇总。',
    operator_grant_required: '需要同平台 Operator 连接的显式查看授权，当前不展示财务。',
    customer_finance_not_available: '该客户暂无可用财务数据，可能未在 Operator 授权目录中，或上游未返回。',
    customer_finance_not_projected: '客户财务明细尚未投影；经营看板的已授权汇总仍可查看。',
    detail_not_projected: '客户财务明细尚未投影；不表示看板汇总未采集。'
  }
  const key = typeof reason === 'string' ? reason.toLowerCase() : ''
  return messages[key] || '没有可用的已授权客户财务缓存；不代表经营汇总未采集，不触发采集。'
}
