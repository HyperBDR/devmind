import {escapeHTML as e,fmt,percent} from './core.mjs';
import {compactUsage} from './profile-charts.mjs';

function paidTime(value){
 if(value==null||value==='')return null;
 const numeric=Number(value);
 const date=Number.isFinite(numeric)?new Date(numeric):new Date(typeof value==='string'?value.replace(' ','T')+(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$/.test(value)?'+08:00':''):value);
 return Number.isFinite(date.getTime())?date:null;
}
function timeLabel(value,locale='zh-CN'){
 const date=paidTime(value);
 return date?new Intl.DateTimeFormat(locale,{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date).replaceAll('/','-')+' · 北京时间':'未提供';
}
export function rechargeRecords(p){
 const data=p?.value?.finance?.recharge;
 if(!data)return '<p>充值记录尚未读取成功，请关闭后刷新账户数据。</p>';
 return `<p class="recharge-record-note">${e(p.name)} · 最近 5 条成功订单，包含系统赠送，不随调用日期变化。不同支付币种分别统计。</p><div class="table-wrap"><table><thead><tr><th>订单号</th><th>支付时间</th><th>实付金额</th><th>渠道</th><th>状态</th></tr></thead><tbody>${data.orders.map(row=>`<tr><td>${e(row.orderNo)}</td><td>${e(timeLabel(row.payTime))}</td><td>${e(row.payCurrency)} ${e(row.payAmt)}</td><td>${e(row.payChannel==='SystemGift'?'系统赠送':row.payChannel||'未提供')}</td><td>充值成功</td></tr>`).join('')||'<tr><td colspan="5">暂无成功线上充值记录</td></tr>'}</tbody></table></div><p>共 ${fmt(data.successfulCount)} 次成功订单</p>`;
}
function rechargeCard(p,loading,locale='zh-CN'){
 const fin=p.value?.finance,data=fin?.recharge,state=fin?.summary_sections?.recharge;
 const forbidden=state?.error?.code==='SOURCE_FORBIDDEN';
 const status=loading?'读取中…':forbidden?'此客户财务接口未授权':state?.state==='ERROR'?(data?'更新失败 · 保留上次值':'读取失败'):data?'读取成功':'尚未获取';
 const dated=data?.orders.filter(row=>paidTime(row.payTime)).sort((a,b)=>paidTime(b.payTime)-paidTime(a.payTime))||[];
 const total=data?(data.paidTotals.length?data.paidTotals.map(row=>`<strong>${e(row.currency)} ${e(row.amount)}</strong>`).join(''):'<strong>—</strong><small>暂无成功充值记录</small>'):'<strong>—</strong>';
 return `<section class="profile-recharge-card" aria-label="充值概况"><div class="recharge-heading"><h3>充值概况</h3><span class="recharge-status ${state?.state==='ERROR'?'is-warning':''}" role="status">${status}</span><button class="link" data-recharge-records ${data?'':'disabled'}>查看记录 →</button></div><div class="recharge-totals"><div><small>累计实付充值</small>${total}</div><div><small>成功订单次数</small><strong>${data?fmt(data.successfulCount)+' 次':'—'}</strong></div></div><div class="recharge-latest"><small>最近成功订单</small><strong>${data?.orders.length?e(timeLabel(dated[0]?.payTime,locale)):'—'}</strong></div><p class="recharge-footnote"><span>包含系统赠送，实付金额按币种统计 · 不随调用日期变化。</span>${state?.read_at?`<span title="${e(timeLabel(state.read_at,locale))}">${state.state==='ERROR'?'最近尝试':'采集于'} ${e(timeLabel(state.read_at,locale).slice(5))}</span>`:''}</p></section>`;
}

export function profileHeader(p,{range,loading,finance,locale='zh-CN'}){
 const s=p.summary,absence=p.signals.inactivity;
 const inactive=absence?.state==='READY';
 const tokens=compactUsage(s.totalTokens,true);
 return `<section class="panel profile-overview-card profile-account-layout" data-panel="identity">
 <div class="profile-identity-eyebrow"><span>客户档案</span><div class="profile-identity-tools"><small>当前范围 ${e(range)}</small><button data-refresh-finance ${loading?'disabled':''}>${loading?'正在刷新…':'↻ 刷新账户数据'}</button></div></div>
 <div class="profile-identity-main"><div class="profile-identity-name"><div class="avatar">${e(p.avatarInitial||p.name[0]||'客')}</div><div><h2>${e(p.name)}</h2><div class="profile-customer-facts" data-panel="value"><span title="${e(p.customerTenantId)}">租户 ID ${e(p.customerTenantId)}</span><span>组织 <b>${e(p.identity.organizationName||'未录入')}</b></span><span>行业 <b>${e(p.identity.industry||'未录入')}</b></span>${p.identity.channel?`<span>渠道 <b>${e(p.identity.channel)}</b></span>`:''}${p.identity.application?`<span>应用 <b>${e(p.identity.application)}</b></span>`:''}</div></div></div></div>
 <div class="profile-financial-overview">${rechargeCard(p,loading,locale)}${finance}</div>
 <div class="profile-call-overview"><h3>调用概况 <span>· 当前筛选</span></h3><div><strong>${fmt(s.requestCount)}</strong><span>范围内请求</span></div><div><strong>${percent(s.successRate)}</strong><span>请求成功率</span></div><div><strong>${inactive?fmt(absence.daysWithoutCalls)+' 天':fmt(p.rhythm.activeDays)}</strong><span>${inactive?'完整自然日无调用':'活跃自然日'}</span></div><div title="${s.totalTokens==null?'用量未知':fmt(s.totalTokens)+' Token'}"><strong>${tokens}</strong><span>已知 Token（覆盖 ${fmt(s.totalTokensSampleCount)} / ${fmt(s.requestCount)}）</span></div></div></section>`;
}
