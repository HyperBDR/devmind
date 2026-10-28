import {escapeHTML as e} from './core.mjs'
import { isEnglishLocale, localizeWorkspaceHtml } from '../../utils/agioneWorkspaceLocale.js'

function finite(value) {
  if (value === null || value === undefined || typeof value === 'boolean' || String(value).trim() === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function money(value) {
  const number = finite(value)
  return number === null ? '—' : new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(number)
}

function readTime(value, locale = 'zh-CN') {
  const date = new Date(value || '')
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat(isEnglishLocale(locale) ? 'en-US' : 'zh-CN', {
      timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).format(date)
    : '时间未记录'
}

function adjustment(summary) {
  const values = [summary?.adjustment, summary?.roundOff]
    .map(finite).filter(value => value !== null)
  return values.length ? money(values.reduce((a, b) => a + b, 0)) : '—'
}

function metric(label, value, unit = '') {
  return `<div class="df-summary-metric"><span>${e(label)}</span><strong>${e(value)}</strong>${unit ? `<small>${e(unit)}</small>` : ''}</div>`
}

function coverage(trend, field) {
  const days = [...new Set((trend || []).filter(row =>
    /^\d{4}-\d{2}-\d{2}$/.test(row.date || '') && finite(row[field]) !== null
  ).map(row => row.date))].sort()
  const ranges = []
  for (const day of days) {
    const last = ranges.at(-1)
    if (last && Date.parse(`${day}T00:00:00Z`) - Date.parse(`${last[1]}T00:00:00Z`) === 86400000) last[1] = day
    else ranges.push([day, day])
  }
  return ranges.map(([first, last]) => first === last ? first : `${first} — ${last}`).join('、') || '暂无完整日数据'
}

function distributionView(distribution, finance) {
  if (!distribution) return `<div class="df-finance-empty"><strong>余额分层待采集</strong><span>当前没有可用于分层的账户余额。</span></div>`
  const total = ['healthyCustomers', 'normalCustomers', 'lowCustomers', 'zeroCustomers', 'negativeCustomers']
    .reduce((sum, key) => sum + (Number(distribution[key]) || 0), 0)
  const segments = [
    ['healthy', '余额充足', distribution.healthyCustomers],
    ['normal', '余额正常', distribution.normalCustomers],
    ['low', '低于阈值', distribution.lowCustomers],
    ['zero', '余额为 0', distribution.zeroCustomers],
    ['negative', '余额为负', distribution.negativeCustomers]
  ]
  return `<div class="df-distribution-lead"><strong>${e(distribution.belowThresholdCustomers ?? '—')} 位客户</strong><span>低于 ${e(money(distribution.threshold))} ${e(distribution.unit || '')}</span></div><div class="df-balance-bar" role="img" aria-label="${e(segments.map(([, label, count]) => `${label} ${count} 位客户`).join('，'))}">${segments.map(([kind, , count]) => count ? `<span class="is-${kind}" style="width:${total ? 100 * count / total : 0}%"></span>` : '').join('')}</div><div class="df-balance-legend">${segments.map(([kind, label, count]) => `<span><i class="is-${kind}"></i>${e(label)} <b>${e(count ?? '—')}</b></span>`).join('')}</div><p class="df-risk-note">负余额客户合计欠额 <strong>${e(money(distribution.negativeTotal))} ${e(distribution.unit || '')}</strong> · 覆盖 ${e(finance.balanceCustomers ?? '—')} / ${e(finance.totalCustomers ?? '—')} 位客户</p>`
}

function summaryView(summary, finance) {
  const unit = summary?.unit || 'Credit'
  if (!summary) return `<div class="df-finance-empty"><strong>账期摘要待采集</strong><span>当前没有可用的账期财务快照。</span></div>`
  return `<div class="df-summary-grid">${metric('Credit 入账', money(summary.topUp), unit)}${metric('Credit 消耗', money(summary.consumed), unit)}${metric('调账 / 舍入', adjustment(summary), unit)}${metric('产生消耗客户', `${summary.consumingCustomers ?? '—'} / ${finance.totalCustomers ?? '—'}`)}</div><p class="df-summary-note">入账日数据覆盖：${e(coverage(finance.trend, 'topUp'))}<br>消耗日数据覆盖：${e(coverage(finance.trend, 'value'))}</p><p class="df-summary-note">账期覆盖 ${e(summary.coveredCustomers ?? '—')} 位客户 · 有入账记录 ${e(summary.topUpCustomers ?? '—')} 位客户${summary.topUp == null ? ' · 所选日期入账数据尚未完整采集' : ''}${summary.adjustment == null && summary.roundOff == null ? ' · 日维度调账数据暂不可用' : ''}${summary.consumed == null ? ' · 所选日期消耗数据尚未完整采集' : ''}</p>`
}

function financeMessage(finance) {
  if (finance?.mode === 'live') return 'DevMind 按需直连同平台 Operator 已授权财务接口，不中转 Demo；不随调用筛选变化。'
  if (finance?.coverageBasis === 'pinned_confirmed_finance' || finance?.latestObservations === false) return '仅固定版本中已确认客户的已缓存财务，不代表最新独立账本全量。'
  return finance?.scopeLabel || 'Operator 已授权目录财务快照 · 独立于调用日期、模型和客户筛选。'
}

export function dashboardFinance(finance, options = {}) {
  return localizeWorkspaceHtml(financeMarkup(finance, options), options.locale)
}

function financeMarkup(finance, { starting = false, locale = 'zh-CN' } = {}) {
  if (!finance) return ''
  const distribution = (finance.balanceDistributions || []).find(item => item.unit === 'Credit') || finance.balanceDistributions?.[0]
  const summary = (finance.periodSummaries || []).find(item => item.period === finance.requestedMonth) || finance.periodSummaries?.at(-1)
  const live = finance.mode === 'live'
  const times = live ? readTime(finance.fetchedAt || finance.latestReadAt, locale) : finance.oldestReadAt === finance.latestReadAt ? readTime(finance.latestReadAt, locale) : `${readTime(finance.oldestReadAt, locale)} — ${readTime(finance.latestReadAt, locale)}`
  const warning = finance.staleCustomers > 0
  const available = finance.available !== false && (!!distribution || !!summary || !!finance.balances?.length || !!finance.cycles?.length)
  const status = ['queued', 'running'].includes(finance.refreshState)
    ? (available ? '财务更新中 · 显示上次数据' : '财务更新中')
    : finance.refreshState === 'failed'
      ? (available ? '财务更新失败 · 保留上次数据' : '财务更新失败')
      : live ? (!available ? (finance.reason || '本次上游未返回财务数据') : '本次上游读取结果') : !available ? (finance.reason || '已有缓存不可用') : warning ? '来源快照待更新' : '已采集财务 · 非实时'
  const readOnly = finance.readOnly !== false
  const pending = ['queued', 'running'].includes(finance.refreshState)
  const emptyReason = pending ? '正在后台采集财务数据。'
    : finance.refreshState === 'failed' ? '更新失败，请点击页面上方刷新数据重试。'
      : /^[A-Z_0-9]+$/.test(finance.reason || '')
        ? '没有可用的已授权财务数据。' : finance.reason || '缺失数据不补零。'
  return `<section class="panel dashboard-finance" data-panel="dashboard-finance" aria-label="财务与额度"><div class="df-head"><div><h2>财务与额度 <span class="df-scope">${available ? (live ? '已授权直连范围' : finance.partial ? '部分采集完成' : '全量采集完成') : '暂不可用'}</span></h2><p>${e(financeMessage(finance))}</p></div><div class="df-actions"><span class="df-badge ${warning ? 'is-warning' : ''}" role="status">${e(status)}</span></div></div><div class="df-body"><section class="df-balance-section"><div class="df-section-head"><div><h3>可用余额分层</h3><p>按客户的 USER_AVAILABLE 账户合计判断</p></div><button type="button" data-view="portrait">查看客户账户 →</button></div>${available ? distributionView(distribution, finance) : `<div class="df-finance-empty"><strong>财务快照不可用</strong><span>${e(emptyReason)}</span></div>`}</section><section class="df-period-section"><div class="df-section-head"><div><h3>${e(summary?.period || finance.requestedMonth || '当前')} 账期摘要</h3><p>平台 Credit 快照，不等同于实际收款与收入</p></div><button type="button" data-view="aggregate">分析客户消耗 →</button></div>${available ? summaryView(summary, finance) : '<div class="df-finance-empty"><strong>账期摘要不可用</strong><span>未返回可用的已缓存账期数据。</span></div>'}</section></div><div class="df-footer"><span>${live ? '读取于' : '采集于'} ${e(times)} · 北京时间</span><span>财务覆盖 ${e(finance.coveredCustomers ?? '—')} / ${e(finance.totalCustomers ?? '—')} 位客户${finance.coverageBasis === 'pinned_confirmed_finance' ? ' · 固定版本已确认范围' : ''}</span></div></section>`
}
