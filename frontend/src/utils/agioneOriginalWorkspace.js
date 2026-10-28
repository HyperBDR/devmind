import { escapeHTML } from '../components/agione-demo/core.mjs'
import { financeReason } from './agioneFinancePresentation.js'
import { localizeWorkspaceHtml } from './agioneWorkspaceLocale.js'

export function originalWorkspaceState(state) {
  let profile = null
  if (state.profile) {
    const p = state.profile
    const financeResult = p.value?.finance
    const finance = financeResult?.finance || {}
    const financeReadAt = finance.fetchedAt
    const fallbackSections = financeReadAt ? {
      accounts: { state: 'FRESH', read_at: financeReadAt },
      overview: { state: 'FRESH', read_at: financeReadAt }
    } : {}
    const originalFinance = finance.accounts || finance.overview ? {
      ...finance,
      summary_sections:
        finance.summarySections || finance.summary_sections || fallbackSections,
      finance_source: finance.financeSource || finance.finance_source
    } : {}
    profile = {
      ...p,
      name: p.name || p.customerTenantId || '名称未提供',
      identity: p.identity || {},
      summary: p.summary || {},
      signals: { ...p.signals, signals: p.signals?.signals || [] },
      rhythm: p.rhythm || {},
      participation: p.participation || {},
      members: (p.members || []).map(row => ({ ...row, label: row.label || '调用标识未提供', metrics: row.metrics || {}, groupKey: row.groupKey || {} })),
      models: p.models || [],
      value: { ...p.value, finance: originalFinance },
      financeUnavailableReason: financeResult?.available === false ? financeReason(financeResult.reason) : ''
    }
  }
  return {
    ...state,
    diagnosis: 'all', eventKind: 'all', eventPage: 1, thresholds: {inactivityDays:7,declinePercent:40,technicalFailurePercent:2,minTechnicalRequests:20},
    dashboard: state.dashboard ? {...state.dashboard,finance:originalFinanceDTO(state.dashboard.finance,state),comparison:state.dashboard.comparison || {state:'UNAVAILABLE',reason:state.isLive?'未返回可比较的前期数据':'没有可比较的已缓存前期'},customers:(state.dashboard.customers || []).map(x=>({...x,summary:x.summary || {},signals:Array.isArray(x.signals)?x.signals:x.signals?.signals || []}))} : null,
    data: state.analysis ? {...state.analysis,rows:(state.analysis.rows || []).map(row=>({...row,label:row.label || Object.values(row.groupKey || {}).join(' / ')})),topRows:(state.analysis.topRows || []).map(row=>({...row,label:row.label || Object.values(row.groupKey || {}).join(' / ')}))} : null,
    group: state.groupBy,
    member: state.userId,
    selected: state.selectedCustomerId,
    catalog: { customers: state.customerOptions, models: state.modelOptions },
    profile,
    version: state.dataVersion,
    busy: state.loading,
    previousLoading: false,
    financeLoading: ['queued', 'running'].includes(state.finance?.refreshState)
      ? state.selectedCustomerId : null,
    syncing: false,
    groupRows: []
  }
}

export function originalFinanceDTO(value, context = {}) {
 const finance = value?.finance || value?.data || value || {}
 return { ...finance, mode:context.isLive || finance.mode==='live' ? 'live' : finance.mode, fetchedAt:finance.fetchedAt || context.provenance?.fetchedAt, accountCount:finance.accountCount ?? '—', balanceCustomers:finance.balanceCustomers ?? '—',cycleCustomers:finance.cycleCustomers ?? '—', available:value?.available !== false && (!!finance.balances || !!finance.cycles), reason:value?.reason || finance.reason, scopeLabel:value?.scopeLabel || finance.scopeLabel, coverageBasis:value?.coverageBasis || finance.coverageBasis, latestObservations:value?.latestObservations ?? finance.latestObservations }
}
export function readonlyWorkspaceMarkup(html,state,locale) {
 return localizeWorkspaceHtml(readonlyMarkupBase(html,state),locale)
}
function readonlyMarkupBase(html,state) {
 let result=html.replace(/data-collect-finance=/g,'disabled title="只读：不触发财务采集" data-collect-finance=').replace(/data-sync(?=[\s>])/g,'disabled title="只读：不触发采集" data-sync')
 const f=originalFinanceDTO(state.finance || state.dashboard?.finance,state)
 if(state.isLive) return result.replace(/只读：仅使用已缓存前期，不补采/g,'只读：只显示本次上游返回的前期').replace(/只读：使用缓存既有规则/g,'只读：使用已验证业务规则').replace(/只读：不触发财务采集/g,'只读：本次直接读取上游，不修改财务').replace(/只读历史快照/g,'按需直连读取').replace(/已采集财务 · 非实时/g,'本次上游读取结果').replace(/已授权缓存汇总/g,'已授权直连范围').replace(/来源快照待更新/g,'上游返回数据有时效提示').replace(/财务快照/g,'上游财务数据').replace(/平台 Credit 快照/g,'平台 Credit 数据').replace(/已缓存账期数据/g,'本次上游账期数据').replace(/已缓存前期/g,'已读取前期').replace(/采集于 /g,'读取于 ').replace(/没有可比较的已缓存前期/g,'未返回可比较的前期数据')
 const label=f.coverageBasis==='pinned_confirmed_finance'||f.latestObservations===false?'仅固定版本中已确认客户的已缓存财务，不代表最新独立账本全量':f.scopeLabel || '同平台 Operator 已授权客户的已有缓存 · 独立财务口径，不随调用筛选变化'
 result=result.replace(/当前账号全部授权客户 · 独立财务口径，\s*不随上方日期、客户、模型及结果筛选变化/,escapeHTML(label))
 if(!f.available)result=result.replace(/已采集财务 · 非实时/g,escapeHTML(financeReason(f.reason)))
 return result.replace('点击补齐本月财务，读取全部授权客户；未知数据不补零。','当前展示已采集数据，未缓存的日序列不补采、不补零。')
}
