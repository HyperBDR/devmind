// Pure rendering extracted from AGIone/static/app.mjs; no application bootstrap.
import { escapeHTML as e, fmt, percent, shanghaiDate, tokenAxis, trendPlot, inclusiveWindowEnd } from './core.mjs'
import { profileHeader } from './profile-header.mjs'
import { customerEvents, eventPage } from './dashboard.mjs'
import { dashboardFinance } from './dashboard-finance.mjs'
import { diagnosticSummary } from './diagnostics.mjs'

import { isEnglishLocale, localizeWorkspaceHtml, protectWorkspaceData } from '../../utils/agioneWorkspaceLocale.js'

export function renderOriginalWorkspace(S, view, controls = {}) {
  if (!isEnglishLocale(controls.locale)) {
    const data = protectWorkspaceData({source:S,controls}, false).value
    const html = renderWorkspaceBase(data.source, view, data.controls)
    return controls.transform ? controls.transform(html) : html
  }
  const source = { ...S, profile: S.profile ? { ...S.profile, avatarInitial: S.profile.name?.[0] } : S.profile }
  const protectedData = protectWorkspaceData({ source, controls })
  let html = renderWorkspaceBase(protectedData.value.source, view, protectedData.value.controls)
  if (controls.transform) html = controls.transform(html)
  return protectedData.restore(localizeWorkspaceHtml(html, controls.locale))
}

function renderWorkspaceBase(S, view, controls = {}) {
const english = isEnglishLocale(controls.locale);
const formatLocale = english ? 'en-US' : 'zh-CN';
const fmt = value => Number.isFinite(value) ? new Intl.NumberFormat(formatLocale, {maximumFractionDigits:2}).format(value) : '—';
const globalThis = { location: { port: '18000' } };
const location=globalThis.location;
const diagnosisNames={decline:'使用下降',conversion:'接入受阻',failure:'失败原因'};
const profileOrigin = null;
const profileChart = { field: 'totalTokens', grain: '', compare: false, allModels: false, ...controls };
const chevron='<svg class="ui-chevron" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false"><path d="m5 7.5 5 5 5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const dims={date:'日期',customerTenantId:'客户',modelId:'模型',userId:'调用主体',status:'结果',failureType:'失败原因'};
const metrics={requestCount:'请求量',successCount:'成功请求',successRate:'成功率',totalTokens:'已知 Token',inputTokens:'输入 Token',outputTokens:'输出 Token'};
const signals={inactive:'近期无调用',blocked:'窗口内接入受阻',decline:'使用下降线索',technical:'技术失败偏高',growth:'增长机会',trial:'少量探索',stable:'窗口内稳定用量',no_requests:'窗口内无请求'};
const stages={PENDING:'待核实',IN_PROGRESS:'排查处理中',CONTACT_RECORDED_PENDING_VERIFICATION:'待复核',COMPLETED:'已完成'};

const fields={totalTokens:'总 Token',inputTokens:'输入 Token',outputTokens:'输出 Token'};
const sampleField={totalTokens:'totalTokensSampleCount',inputTokens:'inputTokensSampleCount',outputTokens:'outputTokensSampleCount'};
const colors=['#2563eb','#8b7cf6','#16b8bd','#e6a23c','#ed7195','#a1afc2'];
const clock=value=>new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value));
const day=value=>shanghaiDate(new Date(value));
const short=value=>day(value).slice(5).replace('-','/');
function grainOptions(window){
 const days=(Date.parse(window.endExclusive)-Date.parse(window.start))/864e5;
 return days<=1?['hour']:days<=7?['hour','day']:['day','week'];
}
function chartBuckets(series,grain,field){
 const rows=series?.[0]?.points||[],groups=new Map();
 for(const row of rows){
  let key=row.bucketStart;
  if(grain==='week'){
   const at=new Date(day(row.bucketStart)+'T00:00:00+08:00');
   const weekday=(at.getUTCDay()+7)%7;
   // Shanghai midnight is the previous UTC day; UTC Sunday means local Monday.
   key=new Date(at.getTime()-weekday*864e5).toISOString();
  }
  if(!groups.has(key))groups.set(key,{bucketStart:row.bucketStart,bucketEndExclusive:row.bucketEndExclusive,requestCount:0,knownCount:0,knownValue:0});
  const b=groups.get(key);b.bucketEndExclusive=row.bucketEndExclusive;
  b.requestCount+=row.requestCount||0;b.knownCount+=row[sampleField[field]]||0;
  if(Number.isFinite(row[field]))b.knownValue+=row[field];
 }
 return [...groups.values()].map(b=>({...b,partial:b.knownCount>0&&b.knownCount<b.requestCount,value:b.requestCount===0?0:b.knownCount>0?b.knownValue:null}));
}
function label(b,grain,multiDay=false){
 if(grain==='hour')return (multiDay?short(b.bucketStart)+' ':'')+clock(b.bucketStart);
 if(grain==='week')return short(b.bucketStart)+'–'+short(new Date(Date.parse(b.bucketEndExclusive)-1));
 return short(b.bucketStart);
}
function profileTrendView(profile,window,controls={}){
 const allowed=grainOptions(window),grain=allowed.includes(controls.grain)?controls.grain:allowed[0]==='hour'&&allowed.length===1?'hour':'day';
 const field=Object.hasOwn(fields,controls.field)?controls.field:'totalTokens';
 const series=grain==='hour'?profile.rhythm.hourlyTrend:profile.rhythm.trend;
 const priorSeries=grain==='hour'?profile.rhythm.previousHourlyTrend:profile.rhythm.previousTrend;
 const points=chartBuckets(series,grain,field),multiDay=(Date.parse(window.endExclusive)-Date.parse(window.start))>864e5;
 // Align prior dates to the current calendar buckets before grouping partial weeks.
 const offset=Date.parse(window.endExclusive)-Date.parse(window.start);
 const aligned=priorSeries?.map(s=>({...s,points:s.points.map(p=>({...p,bucketStart:new Date(Date.parse(p.bucketStart)+offset).toISOString(),bucketEndExclusive:new Date(Date.parse(p.bucketEndExclusive)+offset).toISOString()}))}));
 const requests=points.reduce((n,p)=>n+p.requestCount,0);
 const known=points.reduce((n,p)=>n+p.knownCount,0);
 const unknown=requests>0&&known===0;
 const previous=controls.compare&&!unknown&&priorSeries?chartBuckets(aligned,grain,field):[];
 const plot=trendPlot(points,previous,'value',true),{unit,label:unitName}=tokenAxis(plot.max,english);
 const dots=(segments,rows,old)=>segments.flat().map(p=>{
  const b=rows[p.index],start=old?new Date(Date.parse(b.bucketStart)-offset):b.bucketStart,end=old?new Date(Date.parse(b.bucketEndExclusive)-offset):b.bucketEndExclusive;
  const coverage=b.requestCount?`用量覆盖 ${fmt(b.knownCount)} / ${fmt(b.requestCount)} 条请求`:'当前已获取记录中无调用';
  const text=`${old?'前期':'当前'} ${day(start)} ${clock(start)} — ${day(end)} ${clock(end)}：${b.partial?'已知用量 ':''}${fmt(p.value)} Token；${coverage}${b.partial?`；另有 ${fmt(b.requestCount-b.knownCount)} 条未返回用量，实际总量未知`:''}`;
  return `<span class="trend-dot ${old?'previous-dot':''} ${b.partial?'partial-dot':''}" style="left:${p.x}%;top:${p.y}%" tabindex="0" role="img" aria-label="${e(text)}" title="${e(text)}"></span>`;
 }).join('');
 // Bridge internal missing buckets without inventing values or extrapolating edges.
 const lines=(segments,rows,old)=>{
  const edges=segments.flatMap(s=>s.slice(1).map((p,i)=>{
   const before=s[i],partial=rows[before.index].partial||rows[p.index].partial;
   return `<polyline class="${old?'plot-previous':'plot-current'}${partial?' partial-line':''}" points="${before.x*6},${before.y*1.8} ${p.x*6},${p.y*1.8}"/>`;
  }));
  const bridges=segments.slice(1).map((segment,i)=>{
   const before=segments[i].at(-1),after=segment[0];
   const start=new Date(Date.parse(rows[before.index+1].bucketStart)-(old?offset:0));
   const end=new Date(Date.parse(rows[after.index-1].bucketEndExclusive)-(old?offset:0));
   const text=`${old?'前期':'当前'} ${day(start)} ${clock(start)} — ${day(end)} ${clock(end)} 用量缺失；仅连接已知点，不代表缺失时段用量。`;
   return `<polyline class="${old?'plot-previous':'plot-current'} missing-bridge" points="${before.x*6},${before.y*1.8} ${after.x*6},${after.y*1.8}"><title>${e(text)}</title></polyline>`;
  });
  return [...edges,...bridges].join('');
 };
 const indexes=[...new Set(Array.from({length:Math.min(7,points.length)},(_,i)=>Math.round(i*(points.length-1)/Math.max(1,Math.min(6,points.length-1)))))];
 if(grain==='hour'&&!multiDay&&points.length===24)indexes.splice(0,indexes.length,0,4,8,12,16,20,23);
 const grainName={hour:'小时',day:'日',week:'自然周'}[grain];
 const missing=points.filter(p=>p.requestCount>0&&p.knownCount===0).length;
 const partial=points.filter(p=>p.partial).length;
 const previousPartial=previous.some(p=>p.partial);
 const unavailable=unknown?`<div class="profile-chart-empty" role="status"><span aria-hidden="true">▥</span><strong>${multiDay?'所选期间':'当天'}暂无可用${field==='totalTokens'?' Token':fields[field]} 数据</strong><p>${fmt(requests)} 次请求均未返回${field==='totalTokens'?' Token':fields[field]}，用量未知不代表消耗为 0。</p><button class="link" data-customer-requests="${e(profile.customerTenantId||'')}">查看调用证据 →</button></div>`:'';
 return `<div class="profile-trend-head"><div><h3>Token 用量趋势</h3><p>已知用量 · 沿用页面筛选 · 北京时间</p></div><div class="profile-grain" role="group" aria-label="汇总粒度">${allowed.length===1?'<span class="profile-grain-static">按小时</span>':allowed.map(g=>`<button data-profile-grain="${g}" aria-pressed="${grain===g}">按${{hour:'小时',day:'日',week:'周'}[g]}</button>`).join('')}</div></div><div class="profile-trend-controls"><div role="group" aria-label="Token 指标">${Object.entries(fields).map(([k,v])=>`<button data-profile-metric="${k}" aria-pressed="${field===k}">${v}</button>`).join('')}</div><label><input type="checkbox" id="profileCompare" ${controls.compare&&!unknown?'checked':''} ${!priorSeries||unknown?'disabled':''}>对比等长前期${unknown?'（当前用量缺失）':!priorSeries?'（暂不可用）':''}</label></div><div class="trend-toolbar"><b>${unitName}</b><div class="trend-legend"><span class="trend-key">当前</span>${previous.length?'<span class="trend-key previous-key">等长前期</span>':''}</div></div><div class="profile-token-chart ${unknown?'is-unavailable':''}"><div class="trend-layout"><div class="trend-yaxis" aria-hidden="true">${(unknown?[]:plot.ticks).map(t=>`<span style="top:${100-100*t/plot.max}%">${fmt(t/unit)}</span>`).join('')}</div><div class="trend-visual" role="group" aria-label="${e(fields[field])}按${grainName}趋势"><svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-hidden="true">${plot.ticks.map(t=>`<path class="plot-grid" d="M0 ${180-180*t/plot.max}H600"/>`).join('')}${lines(plot.previous,previous,true)}${unknown?'':lines(plot.current,points,false)}</svg>${dots(plot.previous,previous,true)}${unknown?'':dots(plot.current,points,false)}${unavailable}</div></div><div class="trend-xaxis">${indexes.map(i=>`<span style="left:${points.length===1?50:100*i/(points.length-1)}%" class="${i===0?'first-tick':i===points.length-1?'last-tick':''}">${e(label(points[i],grain,multiDay))}</span>`).join('')}</div></div><div class="profile-chart-note"><span>${e(day(window.start))} — ${e(day(new Date(Date.parse(window.endExclusive)-1)))} · 按${grainName}汇总${grain==='week'?' · 首末周仅统计范围内日期':''}${points.length===1?' · 仅一个统计点，不绘制连线':''}</span>${!unknown?`<span class="profile-chart-status">● 完整用量${partial||previousPartial?' · ○ 部分已知，虚线连接':''}${partial?` · ${partial} 个时段仅展示已知用量，实际总量未知`:''}${missing?` · ${missing} 个时段用量缺失；虚线仅连接已知点，不代表缺失时段用量`:''}</span>`:''}</div>${!plot.current.length&&!unknown?'<p class="profile-usage-warning">当前指标暂无完整用量，请切换指标或查看用量覆盖情况。</p>':''}`;
}
function compactUsage(value,token=false){
 if(!Number.isFinite(value))return '—';
 const units=token||english?[[1e12,'T'],[1e9,'B'],[1e6,'M'],[1e3,'K']]:[[1e12,'兆'],[1e8,'亿'],[1e4,'万']];
 const unit=units.find(([scale])=>Math.abs(value)>=scale);
 if(!unit)return fmt(value);
 const scaled=value/unit[0];
 return new Intl.NumberFormat(formatLocale,{maximumFractionDigits:2,useGrouping:false}).format(scaled)+(token?'':' ')+unit[1];
}
function donut(parts,total,center,caption,compact=false){
 let offset=0;
 return `<div class="usage-donut${compact?' usage-donut-compact':''}" role="img" aria-label="${e(caption)}：${parts.map(p=>`${e(p.label)} ${percent(total?100*p.value/total:0)}`).join('，')}"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="48" class="donut-track"/>${total>0?parts.filter(p=>p.value>0).map(p=>{const share=p.value/total*100;const mark=`<circle cx="60" cy="60" r="48" pathLength="100" stroke="${p.color}" stroke-dasharray="${share} ${100-share}" stroke-dashoffset="${-offset}"/>`;offset+=share;return mark;}).join(''):''}</svg><div><strong title="${e(center)} ${e(caption)}">${e(compact&&Number.isFinite(Number(String(center).replaceAll(',','')))?compactUsage(Number(String(center).replaceAll(',','')),caption==='Token'):center)}</strong><small>${e(caption)}</small></div></div>`;
}
function usageComposition(profile,allModels=false){
 const compact=true;
 const summary=profile.summary,models=profile.models||[],total=summary.requestCount||0;
 const top=models.slice(0,5).map((m,i)=>({label:m.label,value:m.metrics.requestCount,color:colors[i],id:m.groupKey.modelId}));
 const rest=models.slice(5).reduce((n,m)=>n+m.metrics.requestCount,0);
 if(rest)top.push({label:'其他',value:rest,color:colors[5]});
 const legend=allModels?models.map((m,i)=>({label:m.label,value:m.metrics.requestCount,color:colors[Math.min(i,5)],id:m.groupKey.modelId})):top;
 const input=summary.pairedInputTokens,output=summary.pairedOutputTokens;
 const paired=Number.isFinite(input)&&Number.isFinite(output)?input+output:0;
 const io=[{label:'输入 Token',value:input||0,color:colors[0]},{label:'输出 Token',value:output||0,color:colors[2]}];
 return `<div class="panel profile-composition-card profile-usage-bottom"><section data-panel="dependency"><h3>模型调用分布</h3><p class="composition-unit">按请求量统计</p><div class="composition-body">${donut(top,total,fmt(total),'次请求',compact)}<div class="composition-legend" tabindex="0" aria-label="模型请求占比">${legend.map(m=>`<div><i style="background:${m.color}"></i>${m.id&&m.id!=='UNKNOWN'?`<button class="model-analysis-link" data-analyze-model="${e(m.id)}">${e(m.label)} ↗</button>`:`<span>${e(m.label)}</span>`}<b title="${fmt(m.value)} 次">${compact?compactUsage(m.value):fmt(m.value)} 次</b><span>${percent(total?100*m.value/total:0)}</span></div>`).join('')||'<p>当前范围无请求</p>'}${models.length>5?`<button class="link" data-profile-models>${allModels?'收起':'查看全部模型（'+models.length+'）'} ${allModels?'↑':'→'}</button>`:''}</div></div></section><section class="profile-token-summary"><h3>输入与输出</h3><div class="composition-body">${donut(io,paired,paired?fmt(paired):'—','Token',compact)}<div class="composition-legend">${io.map(m=>`<div><i style="background:${m.color}"></i><span>${m.label}</span><b title="${Number.isFinite(input)&&Number.isFinite(output)?fmt(m.value):'—'} Token">${Number.isFinite(input)&&Number.isFinite(output)?(compact?compactUsage(m.value,true):fmt(m.value)):'—'}</b><span>${paired?percent(100*m.value/paired):'—'}</span></div>`).join('')}${!paired?'<p>暂无可计算占比的用量</p>':''}</div></div><p class="composition-footnote" tabindex="0" title="按输入、输出均已知的同一批请求统计；缺失用量不补 0，Token 占比不代表 Credit 扣费占比。">用量覆盖 ${fmt(summary.inputOutputPairSampleCount)} / ${fmt(total)} 条 · 输入输出均已知 ⓘ</p></section></div>`;
}

function metric(label,value,sub='',title=''){return `<div${title?` title="${e(title)}"`:''}><small>${e(label)}</small><strong>${e(value)}</strong><p>${e(sub)}</p></div>`;}

function infoHint(text){return `<span class="info-hint" tabindex="0" role="note" aria-label="${e(text)}" data-help="${e(text)}">ⓘ</span>`;}

function callerParts(value){
 const [tenant,user,project]=String(value||'UNKNOWN').split(':');
 return project&&user==='PROJECT'?{tenant,user:project,project:true}:user?{tenant,user,project:false}:{tenant:'UNKNOWN',user:tenant,project:false};
}

function identityIcon(kind){
 const drawing=kind==='project'?'<path d="M3 7V5h7l2 2h9v13H3z"/>':kind==='user'?'<circle cx="12" cy="8" r="3.2"/><path d="M5.5 20v-2a6.5 6.5 0 0 1 13 0v2"/>':'<path d="M5 21V4h11v17M16 9h4v12M2 21h21M9 8h3M9 12h3M9 16h3"/>';
 return `<span class="identity-icon identity-icon-${kind}" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">${drawing}</svg></span>`;
}

function groupIdentity(row){
 const details=Object.entries(row.groupKey).map(([key,value])=>{
  const label=key==='userId'?(callerParts(value).project?'项目 ID':'调用用户 ID'):key==='customerTenantId'?'租户 ID':(dims[key]||key)+' ID';
  const id=key==='userId'?callerParts(value).user:value;
  return `<small class="workspace-row-id">${e(label)}：${e(id==='UNKNOWN'?'未归属':id)}</small>`;
 }).join('');
 return `${row.groupKey.userId?`<span class="identity-name">${identityIcon(callerParts(row.groupKey.userId).project?'project':'user')}<b>${e(row.label)}</b><span class="identity-tag ${callerParts(row.groupKey.userId).project?'identity-tag-project':'identity-tag-user'}">${callerParts(row.groupKey.userId).project?'项目调用':callerParts(row.groupKey.userId).user==='UNKNOWN'?'标识缺失':'成员调用'}</span></span>`:`<b>${e(row.label)}</b>`}${details}`;
}

function groupOwner(row){
 const {tenant}=callerParts(row.groupKey.userId);
 const customer=S.catalog?.customers?.find(x=>x.id===tenant);
 return `<span class="identity-name identity-owner">${identityIcon('customer')}<b>${e(customer?.label|| (tenant==='UNKNOWN'?'未归属':tenant))}</b><span class="identity-tag identity-tag-customer">客户</span></span><small class="workspace-row-id">租户 ID：${e(tenant==='UNKNOWN'?'未归属':tenant)}</small>`;
}

function callerOption(option){
 const {tenant,user}=callerParts(option.id);
 const customer=S.catalog?.customers?.find(x=>x.id===tenant);
 return `${option.label} · ${callerParts(option.id).project?'项目':'用户'} ID ${user==='UNKNOWN'?'未归属':user} · 客户 ${customer?.label||tenant}`;
}

function financeTime(value){
 const date=new Date(value||'');
 return Number.isFinite(date.getTime())?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date)+' · 北京时间':'采集时间未记录';
}

function financeView(profile){
 const fin=profile.value.finance,overview=fin?.overview,sections=fin?.summary_sections||{};
 const loading=S.financeLoading===profile.customerTenantId;
 const status=(key,hasValue)=>loading?'读取中…':sections[key]?.error?.code==='SOURCE_FORBIDDEN'?'此客户财务接口未授权':sections[key]?.state==='ERROR'?(hasValue?'更新失败 · 保留上次值':'读取失败'):hasValue?'读取成功':sections[key]?.state==='READY'?(key==='accounts'?'暂无账户':'平台未提供消耗'):'尚未获取';
 const time=key=>{
  const readAt=sections[key]?.read_at||fin?.fetchedAt;
  return readAt?`${sections[key]?.state==='ERROR'?'最近尝试':'采集于'} ${financeTime(readAt)}`:'采集时间未记录';
 };
 const accounts=fin?.accounts||[],cycleAccount=accounts.find(x=>String(x.id)===String(overview?.accountId));
 const unit=cycleAccount?.currency||cycleAccount?.currencyCode||(accounts.length===1?(accounts[0].currency||accounts[0].currencyCode):null)||'单位未标明';
 const balance=accounts.length?accounts.map(x=>`<strong>${e(x.balance??x.availableBalance??'—')} ${e(x.currency||x.currencyCode||'单位未标明')}</strong>${accounts.length>1?`<small>账户 ${e(x.id)}</small>`:''}`).join(''):'<strong>—</strong>';
 const hasCycle=overview?.cycleConsumedCredit!=null;
 return `<section class="profile-finance-card" data-panel="finance" aria-label="账户与消耗"><div class="finance-card-grid"><section class="finance-balance"><div class="finance-field-head"><h3>账户余额</h3><span class="finance-state ${sections.accounts?.state==='ERROR'?'is-warning':''}" role="status">${status('accounts',accounts.length>0)}</span></div><div class="finance-amount">${balance}</div><div class="finance-field-footer"><span>${e(time('accounts'))}</span>${accounts.length&&accounts.every(x=>Number(x.balance??x.availableBalance)===0)?'<span class="finance-warning">余额为 0</span>':''}</div></section><section class="finance-cycle"><div class="finance-field-head"><h3>账期消耗</h3><span class="finance-period">平台账期 ${e(overview?.currentCycle||'—')}</span></div><div class="finance-amount"><strong>${hasCycle?e(overview.cycleConsumedCredit)+' '+e(unit):'—'}</strong></div><p class="finance-cycle-status">${!hasCycle&&sections.overview?.state!=='ERROR'?'消耗数据未获取':''}</p><div class="finance-field-footer"><span>${e(time('overview'))}</span><span class="${overview?.snapshotStale===true||sections.overview?.state==='ERROR'?'finance-warning':'finance-state'}" role="status">${overview?.snapshotStale===true?'平台快照待更新':status('overview',hasCycle)}</span></div></section></div><p class="finance-reading-note">余额为最近采集值，非实时；账期消耗不随调用日期变化。${fin?.finance_source?`<span class="finance-source-label" title="${e(fin.finance_source.host)} · 按同平台客户租户 ID 对应">财务来源：${e(fin.finance_source.account==='operator'?'Operator':fin.finance_source.account)}</span>`:''}${infoHint('读取成功不代表平台快照已更新；平台标记财务数据待更新时，数值仅供参考。')}</p></section>`;
}

function bars(rows){if(!rows?.length)return '<div class="empty">当前范围无记录</div>';const max=Math.max(1,...rows.map(x=>x.metrics.requestCount));return rows.map(x=>`<div class="chart-bar"><span class="label">${e(x.label)}<small> ${Object.entries(x.groupKey).map(([k,v])=>e(k==='userId'?(callerParts(v).project?'项目 ID：':'调用用户 ID：')+callerParts(v).user:v)).join(' / ')}</small></span><div class="track"><div class="fill" style="width:${100*x.metrics.requestCount/max}%"></div></div><b>${fmt(x.metrics.requestCount)}${Number.isFinite(x.requestShare)?`<small> 请求占比 ${percent(x.requestShare*100)}</small>`:''}</b></div>`).join('');}

function trendDate(value,withTime=false){
 const date=new Date(value);if(!Number.isFinite(date.getTime()))return '—';
 const day=shanghaiDate(date).slice(5).replace('-','/');
 return withTime?day+' '+new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(date):day;
}

function trendView(series,previous,field='requestCount'){
 if(!series?.length)return '<div class="empty">当前局部范围无请求</div>';
 return series.map(line=>{
  const points=line.points;if(!points.length)return '<div class="empty">当前范围无时间序列</div>';
  const prior=previous?.find(x=>x.seriesKey===line.seriesKey),plot=trendPlot(points,prior?.points,field);
  const hourly=new Date(points[0].bucketEndExclusive)-new Date(points[0].bucketStart)<864e5;
  const indexes=[...new Set(Array.from({length:Math.min(4,points.length)},(_,i)=>points.length===1?0:Math.round(i*(points.length-1)/Math.min(3,points.length-1))))];
  const lines=(segments,old=false)=>segments.map(segment=>`<polyline class="${old?'plot-previous':'plot-current'}" points="${segment.map(p=>`${p.x*6},${p.y*1.8}`).join(' ')}"/>`).join('');
  const dots=(segments,rows,old=false)=>segments.flat().map(p=>{const text=`${old?'等长前期':'当前'} ${trendDate(rows[p.index].bucketStart,hourly)}：${fmt(p.value)}`;return `<span class="trend-dot ${old?'previous-dot':''}" style="left:${p.x}%;top:${p.y}%" tabindex="0" role="img" aria-label="${e(text)}" title="${e(text)}"></span>`;}).join('');
  return `<div class="trend-chart"><div class="trend-toolbar"><b>${e(line.label||'全部')} · ${e(metrics[field]||field)}</b><div class="trend-legend"><span class="trend-key">当前</span>${prior?'<span class="trend-key previous-key">等长前期</span>':S.previousLoading?'<span>前期读取中…</span>':'<span>前期不可用</span>'}</div></div>
  <div class="trend-layout"><div class="trend-yaxis" aria-hidden="true">${plot.ticks.map(t=>`<span style="top:${100-100*t/plot.max}%">${fmt(t)}</span>`).join('')}</div><div class="trend-visual" role="group" aria-label="${e(line.label||'全部')}的${e(metrics[field]||field)}趋势"><svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-hidden="true">${plot.ticks.map(t=>`<path class="plot-grid" d="M0 ${180-180*t/plot.max}H600"/>`).join('')}${lines(plot.previous,true)}${lines(plot.current)}</svg>${dots(plot.previous,prior?.points||[],true)}${dots(plot.current,points)}</div></div>
  <div class="trend-xaxis" aria-hidden="true">${indexes.map((index,i)=>`<span class="${i===0?'first-tick':i===indexes.length-1?'last-tick':''}" style="left:${points.length===1?50:100*index/(points.length-1)}%">${e(trendDate(points[index].bucketStart,hourly))}</span>`).join('')}</div>
  <div class="trend-footnote"><span>${e(trendDate(points[0].bucketStart))} — ${e(trendDate(new Date(new Date(points.at(-1).bucketEndExclusive).getTime()-1)))} · 北京时间</span><span>${!plot.current.length?'当前指标暂无数据 ':''}${infoHint(prior?'前期曲线按等长日期对齐；未返回的数据保留为空。':'未返回的数据保留为空，不按零计算。')}</span></div></div>`;
 }).join('');
}

function rangeLabel(window){return `${shanghaiDate(new Date(window.start))} — ${inclusiveWindowEnd(window)}`;}

function pendingView(name){return `<div class="empty" role="status">${S.syncing?'正在获取所选日期的数据，完成后自动显示。':S.error?'所选日期的数据读取未完成，请使用上方重试或返回最近完整7天。':`正在读取${e(name)}…`}</div>`;}

function emptyScope(summary){return summary.requestCount===0?'<div class="callout" role="status"><b>当前日期与筛选组合下没有调用记录</b><p>这不表示接口失效，也不表示客户从未使用。可以清除客户/模型/结果条件，或调整日期。</p><button data-clear-filters>清除筛选，保留日期</button></div>':'';}

function pager(id,page,total,size){return `<div class="pager"><button data-page="${id}" data-value="${page-1}" ${page<=1?'disabled':''}>上一页</button><span>${page} / ${Math.max(1,Math.ceil(total/size))} · 共${fmt(total)}${id==='requests'?'条':id==='customers'?'个客户':'组'}</span><button data-page="${id}" data-value="${page+1}" ${page*size>=total?'disabled':''}>下一页</button></div>`;}

function analysisView(){
 const a=S.data;if(!a)return pendingView('自由组合分析');S.groupRows=a.rows;
 const select=(id,options,value)=>`<select id="${id}">${Object.entries(options).map(([key,label])=>`<option value="${e(key)}" ${value===key?'selected':''}>${e(label)}</option>`).join('')}</select>`;
 const g=a.globalSummary,hasCaller=S.group==='userId'||S.secondary==='userId';
 return emptyScope(g)+`<div class="analysis-workspace"><section class="panel workspace-baseline" data-panel="aggregate-summary"><h2>当前范围概览</h2><div class="workspace-kpis">${metric('请求量',fmt(g.requestCount),`${fmt(g.successCount)} 成功 / ${fmt(g.failureCount)} 失败`)}${metric('调用客户',fmt(g.distinctCustomers))}${metric('请求成功率',percent(g.successRate))}${metric('已知 Token',fmt(g.totalTokens),`${fmt(g.totalTokensSampleCount)} / ${fmt(g.requestCount)} 条用量已知`)}</div><details class="workspace-baseline-details"><summary>范围详情 ${chevron}</summary><div>全局范围，不受工作台成员筛选影响。<dl><div><dt>未知结果</dt><dd>${fmt(g.unknownCount)}</dd></div><div><dt>输入 / 输出 Token</dt><dd>${fmt(g.inputTokens)} / ${fmt(g.outputTokens)}</dd></div><div><dt>调用用户</dt><dd>${fmt(g.distinctUsers)}</dd></div><div><dt>期间活跃模型</dt><dd>${fmt(g.distinctModels)}</dd></div></dl></div></details></section>
 <section class="panel analysis-workbench" data-panel="aggregation"><div class="workspace-section-head"><div><small>组合条件与比较结果</small><h2>组合分析工作台</h2></div><button class="link" data-export-analysis>导出当前聚合 ↗</button></div>
 <div class="workspace-tools"><label>主维度 ${select('groupBy',dims,S.group)}</label><label>第二维度 ${select('secondary',{'':'不拆分',...Object.fromEntries(Object.entries(dims).filter(([k])=>k!==S.group))},S.secondary)}</label><label>观察指标 ${select('measure',metrics,S.metric)}</label><label>调用主体 <select id="memberFilter"><option value="">全部调用主体</option>${S.memberOptions.map(x=>`<option value="${e(x.id)}" ${S.member===x.id?'selected':''}>${e(callerOption(x))}</option>`).join('')}</select></label></div>
 <div class="workspace-local" id="localSummary"><span>工作台 <b>${fmt(a.summary.requestCount)}</b> 次请求 · <b>${fmt(a.total)}</b> 个分组 · ${fmt(a.summary.totalTokens)} 已知 Token</span><span>${infoHint('调用主体筛选只影响下方分析结果，上方范围概览保持不变。')}</span></div>
 <div class="analysis-viz"><section class="analysis-time" data-panel="aggregation-trend"><div class="workspace-section-head"><h3>时间变化</h3><small>${e(metrics[S.metric])} · 按日</small></div><div class="workspace-trend-scroll" tabindex="0" role="region" aria-label="当前范围趋势，可滚动查看全部序列">${trendView(S.trend?.series,S.trend?.previousSeries,S.metric)}</div></section><section class="analysis-rank"><div class="workspace-section-head"><h3>分组贡献</h3><small>${e(metrics[S.metric])} · 前 8 组</small></div><div class="workspace-rank-scroll" tabindex="0" role="region" aria-label="分组贡献">${bars(a.topRows.map(x=>({...x,requestShare:S.metric==='requestCount'?x.requestShare:null,metrics:{requestCount:x.metrics[S.metric]}})))}</div><small>完整结果见下表 ${infoHint('未返回的数值显示为 —。')}</small></section></div>
 <div class="workspace-section-head workspace-results-head"><div><h2>聚合结果</h2><small>核对分组数值，点击任意一行查看详情。</small></div><span class="workspace-scope-badge">调用主体：${e(S.memberOptions.find(x=>x.id===S.member)?.label||'全部')}</span></div><div class="table-wrap workspace-table ${hasCaller?'has-caller-identities':''}" tabindex="0" role="region" aria-label="聚合明细，可滚动查看"><table><thead><tr><th>${hasCaller?`${identityIcon('user')}${e(dims[S.group])} <span class="identity-column-hint">谁发起调用</span>`:`${e(dims[S.group])} / ID`}</th>${hasCaller?`<th>${identityIcon('customer')}所属客户 <span class="identity-column-hint">归属于谁</span></th>`:''}<th>请求</th><th>成功率</th><th>输入 / 输出 Token</th><th>P95 耗时 ${infoHint('平台耗时单位尚未确认，暂不计算 P95。记录数为带有耗时字段的成功请求数。')}</th></tr></thead><tbody>${a.rows.map((x,i)=>`<tr data-group-detail="${i}" tabindex="0" aria-haspopup="dialog" aria-label="查看${e(x.label)}分组详情"><td>${groupIdentity(x)}</td>${hasCaller?`<td>${groupOwner(x)}</td>`:''}<td>${fmt(x.metrics.requestCount)}</td><td>${percent(x.metrics.successRate)}</td><td>${fmt(x.metrics.inputTokens)} / ${fmt(x.metrics.outputTokens)}<small>${fmt(x.metrics.totalTokensSampleCount)} / ${fmt(x.metrics.requestCount)} 条用量已知</small></td><td>暂不可用<small>${fmt(x.metrics.successfulLatencySamples)} 条耗时记录</small></td></tr>`).join('')||`<tr><td colspan="${hasCaller?6:5}" class="empty">当前组合无请求；全局基线仍保留。</td></tr>`}</tbody></table></div>${hasCaller?'<p class="caller-identity-note">成员与项目按各自 ID 分别统计；调用主体数量不等于实际人数。</p>':''}<div class="workspace-table-footer"><small>分组合计 ${fmt(a.reconciliation.groupedRequestCount)} 次请求 ${infoHint('汇总基于全部分组，不随翻页变化。')}</small>${pager('analysis',a.page,a.total,a.pageSize)}</div></section><div class="workspace-bottom-note"><span>统计说明 ${infoHint('分组结果展示调用事实；是否需要处理，请结合客户线索和请求证据判断。')}</span><button class="link" data-view="focus">回经营看板核实客户线索 →</button></div></div>`;
}

function profileView(){
 const p=S.profile;
 const origin=profileOrigin?'<div class="profile-return"><button class="primary" data-return-dashboard>← 返回经营看板事件列表</button><span>沿用当前日期与筛选，返回原浏览位置</span></div>':'';
 if(!p)return origin+`<div id="portraitDetail" class="panel empty">${S.busy?'正在读取客户…':'请选择当前范围中的客户；无匹配时不保留上个客户。'}</div>`;
 const summary=p.summary,absence=p.signals.inactivity;
 const knownAbsence=absence?.state==='READY';
 const signalKinds=p.signals.signals,hasIssue=signalKinds.some(x=>['blocked','inactive','decline','technical'].includes(x))||summary.failureCount>0;
 const issueTitle=signalKinds.includes('blocked')?'接入受阻':signalKinds.includes('inactive')?'近期无调用':signalKinds.includes('decline')?'调用量下降':signalKinds.includes('technical')?'技术失败偏高':'存在失败请求';
 return origin+emptyScope(summary)+`<div id="portraitDetail" class="profile-overview-layout">${true?profileHeader(p,{locale:formatLocale,range:rangeLabel(S.window),loading:S.financeLoading===p.customerTenantId,finance:financeView(p)}):`<section class="panel profile-overview-card" data-panel="identity"><div class="profile-identity-eyebrow"><span>客户档案</span><div class="profile-identity-tools"><small>当前范围 ${e(rangeLabel(S.window))}</small><button data-refresh-finance ${S.financeLoading===p.customerTenantId?'disabled':''}>${S.financeLoading===p.customerTenantId?'正在刷新…':'↻ 刷新账户数据'}</button></div></div><div class="profile-identity-main"><div class="profile-identity-name"><div class="avatar">${e(p.name[0])}</div><div><h2>${e(p.name)}</h2><small title="${e(p.customerTenantId)}">租户 ID ${e(p.customerTenantId)}</small><div class="profile-customer-facts" data-panel="value"><span>组织 <b>${e(p.identity.organizationName||'未录入')}</b></span><span>行业 <b>${e(p.identity.industry||'未录入')}</b></span>${p.identity.channel?`<span>渠道 <b>${e(p.identity.channel)}</b></span>`:''}${p.identity.application?`<span>应用 <b>${e(p.identity.application)}</b></span>`:''}</div></div></div>${financeView(p)}</div><div class="profile-identity-metrics">${metric('范围内请求',fmt(summary.requestCount))}${metric('请求成功率',percent(summary.successRate))}${metric(knownAbsence?'完整自然日无调用':'活跃自然日',knownAbsence?fmt(absence.daysWithoutCalls)+' 天':fmt(p.rhythm.activeDays))}${metric('已知 Token',fmt(summary.totalTokens),`用量覆盖 ${fmt(summary.totalTokensSampleCount)} / ${fmt(summary.requestCount)}`)}</div></section>`}
 ${hasIssue?`<section class="profile-issue-banner" role="status"><span class="profile-alert-icon" aria-hidden="true">!</span><div><h3>${e(issueTitle)}${summary.failureCount?` · ${fmt(summary.failureCount)} 次失败`:""}</h3><p>${summary.balanceFailureCount?`余额不足 ${fmt(summary.balanceFailureCount)} 次 · `:""}${summary.technicalFailureCount?`技术失败 ${fmt(summary.technicalFailureCount)} 次 · `:""}${summary.unmappedFailureCount?`原因待分类 ${fmt(summary.unmappedFailureCount)} 次`:"请结合调用证据核实"}</p></div><button class="primary" data-customer-requests="${e(p.customerTenantId)}">查看调用证据 →</button></section>`:`<div class="profile-quiet-note">当前范围${signalKinds.includes('stable')?'存在稳定用量线索':'未触发可判断的异常线索'}。<button class="link" data-customer-requests="${e(p.customerTenantId)}">查看调用证据 →</button></div>`}
 <section class="panel profile-usage-card"><section data-panel="rhythm" class="profile-rhythm">${profileTrendView(p,S.window,profileChart)}</section></section>
 ${usageComposition(p,profileChart.allModels)}
 <section data-panel="participation" class="panel profile-member-summary profile-members-compact"><div class="workspace-section-head"><h3>调用主体 ${infoHint('按客户及成员或项目 ID 分别统计，主体数量不等于实际人数；仅包含有调用记录的主体。')}</h3><span class="profile-member-total">${fmt(p.participation.activeUserCount)} 条调用标识</span></div><div class="profile-member-list" tabindex="0" role="region" aria-label="调用主体列表，可滚动查看">${p.members.map((x,i)=>`<div class="profile-member-row" data-profile-user="${i}" role="button" tabindex="0" aria-haspopup="dialog" aria-label="查看${e(x.label)}的调用详情"><span class="profile-member-avatar" aria-hidden="true">${e(x.label[0])}</span><div class="profile-member-identity"><b>${e(x.label)}</b><small>${callerParts(x.groupKey.userId).project?'项目':'用户'} ID：${e(callerParts(x.groupKey.userId).user)}</small></div><div class="profile-member-facts"><span class="profile-member-role">${e({TENANT:'租户账号',MEMBER:'成员账号',PROJECT:'项目调用'}[x.subjectType]||'类型未确认')}</span><span><b>${fmt(x.metrics.requestCount)}</b> 次请求</span><span>占比 <b>${Number.isFinite(x.requestShare)?percent(x.requestShare*100):'未知'}</b></span></div></div>`).join('')||'<p class="muted">当前范围无调用主体记录</p>'}</div>${p.members.length>3?'<p class="profile-member-scroll-hint">向下滚动查看更多调用主体 ↓</p>':''}</section>
 <section data-panel="experience" class="workspace-bottom-note"><span>响应耗时暂不可用 ${infoHint('平台耗时单位尚未确认，暂不展示 P95 和首 Token 耗时。')}</span><span>统计说明 ${infoHint('请求成功表示平台记录的调用结果，业务任务是否完成仍需核实；下降和无调用仅作为待核实线索。')}</span></section></div>`;
}
function panel(id,title,subtitle,html,{classes=''}={}){return `<section class="panel ${classes}" data-panel="${e(id)}"><div class="panel-head"><div class="panel-title"><h2>${e(title)}</h2>${subtitle?`<p>${e(subtitle)}</p>`:''}</div></div>${html}</section>`;}
function modelUseView(rows){
 if(!rows?.length)return '<div class="empty">当前范围无模型调用记录</div>';
 return `<div class="model-list" tabindex="0" role="region" aria-label="模型调用列表，可滚动查看全部模型">${rows.map(x=>{const share=Number.isFinite(x.requestShare)&&x.requestShare>=0&&x.requestShare<=1?x.requestShare:null;return `<div class="model-item"><div class="model-row"><button class="model-analysis-link" data-analyze-model="${e(x.groupKey.modelId)}" title="模型 ID ${e(x.groupKey.modelId)}" aria-label="分析${e(x.label)}的模型调用，ID ${e(x.groupKey.modelId)}">${e(x.label)} <span aria-hidden="true">↗</span></button><span><b>${fmt(x.metrics.requestCount)}</b> 次请求</span></div><small class="model-id">ID ${e(Object.values(x.groupKey).join(' / '))}</small><p class="model-outcomes">成功 ${fmt(x.metrics.successCount)} · 失败 ${fmt(x.metrics.failureCount)} · 未知 ${fmt(x.metrics.unknownCount)}</p><div class="model-share"><div class="model-track" aria-hidden="true">${share===null?'':`<span style="width:${100*share}%"></span>`}</div><span>${share===null?'占比未知':percent(share*100)}</span></div></div>`;}).join('')}</div><p class="model-note">请求占比 ${infoHint('按当前筛选范围的请求数计算，仅反映调用分布。')}</p>`;
}
function eventPanel(d){
 const rows=customerEvents(d.customers),page=eventPage(rows,S.eventKind,S.eventPage),lead=rows[0];
 const labels={all:'全部客户',inactive:'近期无调用',failure:'请求失败',blocked:'接入受阻',decline:'使用下降',technical:'技术失败'};
 const declineUnknown=d.comparison.state!=='READY';
 const inactiveUnknown=d.inactivityState&&d.inactivityState!=='READY';
 const evidence=x=>`<button class="link" data-queue-evidence="${e(x.customerTenantId)}">查看调用证据 →</button><button class="link" data-profile="${e(x.customerTenantId)}">查看客户 →</button>`;
 const tags=x=>x.eventKinds.map(k=>`<span class="event-chip kind-${k}">${labels[k]}</span>`).join('');
 const absence=x=>`连续 ${fmt(x.inactivity?.daysWithoutCalls)} 天无调用${x.inactivity?.limitedSample?' · 此前仅少量调用，样本较少':''}`;
 const description=x=>x.eventKinds.includes('blocked')?'多次尝试且窗口内无成功调用。':x.eventKinds.includes('inactive')?absence(x):x.eventKinds.includes('decline')?'本期请求量较等长前期下降。':'当前窗口存在失败请求，需区分原因与影响。';
 const warning=declineUnknown?`<div class="event-rule-warning ${S.previousLoading?'previous-loading':''}" role="status">${declineUnknown?`<b>${S.previousLoading?'正在计算所选日期的调用变化':d.comparison.state==='EMPTY'?'前期无调用基数':S.previousError?'前期比较未完成':'正在准备前期比较'}</b><p>${S.previousLoading?'正在读取对应的等长前期，完成后自动更新；本期数据可继续查看。':e(S.previousError?.message||d.comparison.reason||'缺少可比较的前期记录')}</p>${d.comparison.state==='UNAVAILABLE'?`<div class="previous-actions"><small>${S.previousLoading?'比较完成前不生成使用下降结论':'前期未齐，不能判断是否下降'}</small><button data-retry-previous ${S.previousLoading||S.syncing||S.refreshing?'disabled':''}>${S.previousLoading?'获取中…':'↻ 重新获取前期'}</button></div>`:''}`:''}<small>其他可判断的线索继续展示。</small></div>`:'';
 const comparisonReady=d.comparison.state==='READY'?`<div class="event-comparison-ready"><span>✓ 调用变化已完成比较</span><span>${d.decline.length?fmt(d.decline.length)+' 位客户调用量下降':'未发现达到阈值的下降客户'}</span></div>`:'';
 const leadView=lead?`<div class="event-priority"><div class="event-eyebrow">● 优先核实</div><h3>${e(lead.name)}</h3><div class="event-tags">${tags(lead)}</div><p class="event-lead-fact">${lead.eventKinds[0]==='inactive'?`连续 <b>${fmt(lead.inactivity.daysWithoutCalls)}</b> 天无调用`:`<b>${fmt(lead.summary.requestCount)}</b> 次请求 · ${fmt(lead.summary.successCount)} 次成功`}</p><p>${e(lead.eventKinds.includes('blocked')?'先核对余额与接入，再检查成功调用。':lead.eventKinds.includes('inactive')?'核实是否暂停使用、需求变化或遇到接入障碍。':lead.eventKinds.includes('decline')?'核实调用下降原因及当前使用需求。':'区分余额与技术失败，核对影响与请求证据。')}</p><div class="event-actions">${evidence(lead)}</div></div>`:`<div class="empty">${unknown?'当前可判断的规则未触发线索；部分规则暂无法判断。':'当前范围未触发已配置的线索规则。'}</div>`;
 const eventCard=x=>`<article class="event-item ${x.eventKinds.includes('inactive')?'has-inactivity':''}" data-event-customer="${e(x.customerTenantId)}"><div class="event-tags">${tags(x)}</div><h3>${e(x.name)}</h3><p>${e(description(x))}</p><div class="event-facts">${x.eventKinds.includes('inactive')?`<span>末次调用 ${e(trendDate(x.inactivity.lastObservedAt,true))}</span><span>${fmt(x.summary.successCount)} 次成功 · ${fmt(x.summary.failureCount)} 次失败</span>`:''}${x.eventKinds.includes('decline')&&x.previous?`<span><b>${fmt(x.previous.requestCount)} → ${fmt(x.summary.requestCount)}</b> 次请求</span><span>变化 ${percent(x.changePercent)}</span>`:x.summary.failureCount&&!x.eventKinds.includes('inactive')?`<span>失败 <b>${fmt(x.summary.failureCount)}</b> 次</span><span>余额不足 ${fmt(x.summary.balanceFailureCount)} 次</span>`:''}</div>${!declineUnknown&&x.comparisonState==='NO_BASELINE'?'<p class="event-comparison-note">此前无调用记录，无法计算使用下降比例。</p>':''}<div class="event-actions">${evidence(x)}</div></article>`;
 const items=page.items.map((x,i)=>eventCard(x).replace('<article ',`<article style="grid-row:${i+1}" `)).join('');
 const stable=true;
 // Measure every category in both slots so filtering and last pages stay stable.
 const samples=stable?rows.flatMap(x=>[0,1].map(slot=>({x,slot}))):rows.filter(x=>S.eventKind==='all'||x.eventKinds.includes(S.eventKind)).map((x,i)=>({x,slot:i%2}));
 const sizing=stable||page.pages>1?samples.map(({x,slot})=>eventCard(x).replace('<article class="event-item',`<div inert aria-hidden="true" style="grid-row:${slot+1}" class="event-item event-size-sample`).replace(/ data-event-customer="[^"]*"/,'').replace(/ data-[\w-]+="[^"]*"/g,'').replace('</article>','</div>')).join(''):'';
 const kindUnknown=(S.eventKind==='decline'&&declineUnknown)||(S.eventKind==='inactive'&&inactiveUnknown&&!page.total);
 return `<section class="panel event-column" data-panel="events"><div class="event-heading">${stable?'<div class="event-title-group">':''}<h2>待核实线索</h2><small>${S.previousLoading?'已发现 ':''}${fmt(rows.length)} 位客户 · ${fmt(rows.reduce((n,x)=>n+x.eventKinds.length,0))} 条线索${S.previousLoading?' · 比较中':''}</small>${stable?'</div><button class="event-rule-settings" data-open-rules><span aria-hidden="true">⚙</span> 规则设置</button>':''}</div>${warning}${comparisonReady}${leadView}<div class="event-tabs" role="group" aria-label="线索类型">${Object.entries(labels).map(([k,v])=>`<button data-event-kind="${k}" aria-pressed="${S.eventKind===k}" ${((k==='decline'&&declineUnknown)||(k==='inactive'&&inactiveUnknown))?'class="rule-unavailable"':''}>${v} ${((k==='decline'&&declineUnknown)||(k==='inactive'&&inactiveUnknown))?(k==='decline'&&S.previousLoading?'计算中':k==='inactive'&&d.inactivityState==='PARTIAL'?fmt(rows.filter(x=>x.eventKinds.includes(k)).length)+' · 部分待判断':'待判断'):fmt(k==='all'?rows.length:rows.filter(x=>x.eventKinds.includes(k)).length)}</button>`).join('')}</div><div class="event-list ${stable?'is-paginated event-stable-list':page.pages>1?'is-paginated':''}">${sizing}${items||`<div class="empty">${kindUnknown?'该规则暂无法判断，请核实数据或调整筛选条件。':'当前分类未触发线索，可查看其他分类。'}</div>`}</div><div class="event-bottom"><div class="event-pagination"><span>${kindUnknown?'该规则暂无法判断':`共 ${fmt(page.total)} 位客户<small>${page.total?`${(page.page-1)*2+1}–${(page.page-1)*2+page.items.length} 位 · `:''}第 ${page.page} / ${page.pages} 页 · 每页 2 位</small>`}</span><div>${page.page>1?`<button data-event-page="${page.page-1}">上一页</button>`:''}${page.page<page.pages?`<button data-event-page="${page.page+1}">下一页</button>`:''}</div></div><div class="event-diagnostics">${['decline','conversion','failure'].map(k=>`<button class="link" data-diagnose="${k}">${diagnosisNames[k]} →</button>`).join('')}</div><details class="event-help"><summary>判断依据与数据边界</summary><p>颜色区分线索类型，不代表严重程度。同一客户多条线索合并；失败需要区分偶发、持续、余额与技术原因。</p><p>近期无调用：距所选窗口末端至少 ${fmt(S.thresholds.inactivityDays)} 个完整自然日；按当前客户和模型范围的已获取记录判断，不随今天推进。样本较少不认定流失。仅筛选部分请求结果或当前记录不完整时不推断无调用。</p><p>使用下降：与等长前期比较，默认阈值可在诊断阈值中调整。${e(d.comparison.reason||'前期按已获取记录比较，不认定源历史无遗漏。')}</p></details></div></section>`;
}
function dashboardView(){
 const d=S.dashboard;if(!d)return pendingView('经营看板');if(S.diagnosis!=='all')return diagnosticView(d);
 const s=d.summary,models=d.models||[];
 const overview=panel('summary','经营概览','',`<div class="dashboard-metrics">${metric('有调用客户',fmt(s.distinctCustomers))}${metric('请求量',fmt(s.requestCount),`${fmt(s.successCount)} 成功 / ${fmt(s.failureCount)} 失败 / ${fmt(s.unknownCount)} 未知`)}${metric('请求成功率',percent(s.successRate))}${metric('已知 Token',fmt(s.totalTokens),`${fmt(s.totalTokensSampleCount)}/${fmt(s.requestCount)} 个已知样本`)}</div>`,{classes:'dashboard-overview'});
 const modelsPanel=panel('model-use','模型调用分布',`${fmt(models.length)} 个模型 · 按请求量排序${models.length>3?' · 滚动查看更多':''}`,`${models.length>3?'<div class="model-scroll-hint"><span aria-hidden="true">↕</span> 上下滚动查看全部模型</div>':''}${modelUseView(models)}`,{classes:'dashboard-models'});
 const finance=true
  ?dashboardFinance(d.finance,{starting:S.financeStarting}):'';
 return finance+emptyScope(s)+`<div class="dashboard-columns"><div class="dashboard-data">${overview}${panel('trend','调用趋势','请求量 · 与等长前期比较',trendView(S.trend?.series||d.trend,S.trend?.previousSeries),{classes:'dashboard-trend'})}${modelsPanel}</div>${eventPanel(d)}</div>`;
}
function diagnosticCustomer(row,kind){
 const stats=row.summary;
 const facts=kind==='decline'?[["前期请求",fmt(row.previous?.requestCount)],["本期请求",fmt(stats.requestCount)],["请求变化",percent(row.changePercent)]]:kind==='conversion'?[["尝试请求",fmt(stats.requestCount)],["成功请求",fmt(stats.successCount)],["余额不足",fmt(stats.balanceFailureCount)]]:[["失败请求",fmt(stats.failureCount)],["全部请求",fmt(stats.requestCount)],["失败率",percent(stats.failureRate)]];
 return `<article class="diagnostic-customer"><div class="diagnostic-identity"><h3>${e(row.name)}</h3><small>客户 ID ${e(row.customerTenantId)}</small></div><dl class="diagnostic-facts">${facts.map(([label,value])=>`<div><dt>${e(label)}</dt><dd>${e(value)}</dd></div>`).join('')}</dl><div class="diagnostic-actions">${kind==='failure'?`<button data-customer-requests="${e(row.customerTenantId)}" aria-label="查看${e(row.name)}的失败证据">查看失败证据 <span aria-hidden="true">→</span></button>`:`<button data-profile="${e(row.customerTenantId)}" aria-label="查看${e(row.name)}的客户画像">客户画像 <span aria-hidden="true">→</span></button>`}</div>${kind==='decline'&&row.comparisonReason?`<p class="diagnostic-row-note">${e(row.comparisonReason)}</p>`:''}</article>`;
}
function diagnosticView(d){
 const kind=S.diagnosis,s=d.summary,applicable=d.signalState==='APPLICABLE';
 let stats,body;
 if(kind==='decline'){
  stats=[['下降客户',d.comparison.state==='READY'?fmt(d.decline.length):'—','达到当前下降阈值的客户'],['前期请求',fmt(d.comparison.summary?.requestCount),'紧邻的等长日期范围'],['本期请求',fmt(s.requestCount),'当前日期与筛选条件']];
  const note=d.comparison.reason||'按相同筛选条件，比较紧邻等长前期的请求量。';
  body=panel('decline-diagnosis','下降客户与证据','按客户查看前期、本期和变化幅度',`<p class="diagnostic-note">${e(note)}</p><div class="diagnostic-list">${d.decline.map(x=>diagnosticCustomer(x,kind)).join('')||`<div class="empty">${d.comparison.state==='READY'?'当前阈值下未发现调用下降客户。':d.comparison.state==='EMPTY'?'前期无调用，请调整日期或筛选条件后再比较。':'前期数据暂不可比较，可重新获取所选日期或调整范围。'}</div>`}</div>`,{classes:'diagnostic-panel'});
 }else if(kind==='conversion'){
  const sum=field=>applicable?fmt(d.blocked.reduce((total,x)=>total+x.summary[field],0)):'—';
  stats=[['受阻客户',applicable?fmt(d.blocked.length):'—','至少3次尝试且窗口内无成功'],['受阻请求',sum('requestCount'),'以上受阻客户的请求合计'],['余额不足',sum('balanceFailureCount'),'受阻客户中已确认的失败']];
  body=panel('blocked','窗口内接入受阻的客户','按本期请求结果筛选客户',`<p class="diagnostic-note">${applicable?'先核对余额与接入配置，处理后复查成功调用。':'当前结果筛选不适用受阻判断，请切回全部结果后查看。'}</p><div class="diagnostic-list">${d.blocked.map(x=>diagnosticCustomer(x,kind)).join('')||'<div class="empty">当前范围未发现适用的受阻客户。</div>'}</div>`,{classes:'diagnostic-panel'});
 }else{
  stats=[['失败请求',fmt(s.failureCount),'当前范围中已确认失败的请求'],['请求失败率',percent(s.failureRate),'分母为当前范围全部请求'],['受影响客户',fmt(d.affectedCustomers.length),'窗口内出现失败请求的客户']];
  const reasons=d.failureBreakdown.map(x=>{const count=x.metrics.requestCount,share=s.failureCount>0?100*count/s.failureCount:null;return `<div class="diagnostic-reason"><div><strong>${e(x.label)}</strong><span><b>${fmt(count)}</b> 次 · ${percent(share)}</span></div><div class="diagnostic-track" aria-hidden="true"><span style="width:${share??0}%"></span></div></div>`;}).join('')||'<div class="empty">当前范围没有失败请求。</div>';
  body=`<div class="diagnostic-split">${panel('failure-summary','失败原因分布','占比以当前范围的全部失败请求为分母',`<div class="diagnostic-reasons">${reasons}</div><div class="diagnostic-measurements">${metric('已确认余额不足',fmt(s.balanceFailureCount))}${metric('已分类技术失败',fmt(s.technicalFailureCount))}</div><p class="diagnostic-note">技术失败已确认 ${fmt(s.knownTechnicalFailureCount)} 次；原因待分类 ${fmt(s.unmappedFailureCount)} 次。响应耗时单位待确认，暂不可用。</p>`,{classes:'diagnostic-panel'})}${panel('failure-customers','受影响客户','查看每位客户的失败请求，进一步定位原因',`<div class="diagnostic-list">${d.affectedCustomers.map(x=>diagnosticCustomer(x,kind)).join('')||'<div class="empty">当前范围没有受影响客户。</div>'}</div>`,{classes:'diagnostic-panel'})}</div>`;
 }
 const conclusion=diagnosticSummary(d,kind);
 const rule=kind==='conversion'?'受阻条件：至少 3 次尝试，且所选期间没有成功请求。':kind==='decline'?`判断条件：同一筛选下与等长前期比较，请求量下降至少 ${fmt(S.thresholds.declinePercent)}%。`:'失败率以当前范围的全部请求为分母；未知结果不归为成功或失败。';
 const action=conclusion.action==='sync'?'data-sync':conclusion.action==='clear-filters'?'data-clear-filters':`data-diagnostic-evidence="${e(conclusion.target)}"`;
 return `<div class="diagnostic-content">${panel('diagnostic-overview',diagnosisNames[kind]+'诊断','',`<div class="diagnostic-conclusion"><h3>${e(conclusion.title)}</h3><p>${e(conclusion.evidence)}</p><div class="diagnostic-next"><p><span>建议下一步</span>${e(conclusion.advice)}</p><button class="primary" ${action}>${e(conclusion.label)} <span aria-hidden="true">→</span></button></div></div><div class="baseline-metrics diagnostic-metrics">${stats.map(([label,value,sub])=>metric(label,value+(value==='—'||label.includes('率')?'':label.includes('客户')?' 位':' 次'),sub)).join('')}</div><p class="diagnostic-rule">${e(rule)} ${infoHint(kind==='conversion'?'只根据所选期间的请求生成线索，不判断客户历史上是否曾成功调用。':kind==='decline'?'请求量下降是待核实线索，需结合业务情况判断原因。':'失败率按当前范围全部请求计算；未知结果单独统计。')}</p>`,{classes:'baseline-panel diagnostic-overview'})}${body}</div>`;
}
function failureLabel(record){return record.result==='SUCCESS'?'':record.result==='FAILURE'?(record.raw.failureTypeName||(String(record.raw.failureType)==='3'?'余额不足':'原因待确认')):'结果待确认';}
function requestTime(value){
 const date=new Date(value);
 return Number.isNaN(date.getTime())?String(value||'时间未知'):new Intl.DateTimeFormat(formatLocale,{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date);
}
function requestRows(items){
 return `<div class="table-wrap request-table"><table><thead><tr><th>时间 / 客户</th><th>模型 / 调用主体</th><th>结果 / 原因</th><th>Token 输入 / 输出</th><th>操作</th></tr></thead><tbody>${items.map((x,i)=>`<tr><td data-label="时间 / 客户"><strong>${e(requestTime(x.occurred_at))}</strong><small>${e(x.customerName)}</small></td><td data-label="模型 / 调用主体"><strong>${e(x.raw.modelName||x.raw.metaModelName||x.model_id||'模型未归属')}</strong><small>${e(x.raw.keyType==='PROJECT'?(x.raw.projectName||x.raw.projectId||'项目标识缺失'):(x.raw.userName||x.user_id||'成员标识未提供'))}</small></td><td data-label="结果 / 原因"><span class="request-status status-${e(x.result)}">${e({SUCCESS:'成功',FAILURE:'失败',UNKNOWN:'未知'}[x.result]||'未知')}</span><small>${e(failureLabel(x))}</small></td><td data-label="Token 输入 / 输出">${fmt(x.input_tokens)} / ${fmt(x.output_tokens)}</td><td data-label="操作"><button class="link" data-record="${i}">查看详情 →</button></td></tr>`).join('')||'<tr><td colspan="5" class="empty">当前条件无请求</td></tr>'}</tbody></table></div>`;
}
if(view==='groupHeader'){const captured=controls;return captured.drawer?`<div class="drawer-group-summary"><small>${captured.body.groupKey?.userId?(callerParts(captured.body.groupKey.userId).project?'项目调用':callerParts(captured.body.groupKey.userId).user==='UNKNOWN'?'主体信息缺失':'成员调用'):'聚合分组'} · ${e(rangeLabel(captured.body.window))}</small><h3>${e(captured.groupLabel||'分组详情')}</h3><div class="drawer-group-identity">${groupIdentity({label:'',groupKey:captured.body.groupKey||{}})}${captured.body.groupKey?.userId?`${callerParts(captured.body.groupKey.userId).project?'<p class="muted">平台未提供成员标识，按项目统计。</p>':''}<p>所属客户</p>${groupOwner({groupKey:captured.body.groupKey})}`:''}</div>${captured.groupSummary?`<div class="drawer-group-kpis">${metric('请求量',fmt(captured.groupSummary.requestCount))}${metric('成功率',percent(captured.groupSummary.successRate))}${metric('输入 / 输出 Token',true?compactUsage(captured.groupSummary.inputTokens,true)+' / '+compactUsage(captured.groupSummary.outputTokens,true):fmt(captured.groupSummary.inputTokens)+' / '+fmt(captured.groupSummary.outputTokens),'',fmt(captured.groupSummary.inputTokens)+' / '+fmt(captured.groupSummary.outputTokens)+' Token')}</div>`:''}</div>`:'';}
if(view==='requestRows')return requestRows(controls.items || []);
return view === 'focus' ? dashboardView() : view === 'aggregate' ? analysisView() : profileView();
}

export function renderOriginalScopeDialog(S, options = 'zh-CN') {
  const locale = typeof options === 'string' ? options : options?.locale || 'zh-CN'
  if (!isEnglishLocale(locale)) return renderScopeBase(S)
  const protectedData = protectWorkspaceData(S)
  return protectedData.restore(localizeWorkspaceHtml(renderScopeBase(protectedData.value), locale))
}

function renderScopeBase(S){
const choices=(list,name,selected)=>list.map(x=>`<label class="scope-option" data-option-label data-option-search="${e(x.label+' '+x.id)}"><input type="checkbox" name="${name}" value="${e(x.id)}" ${selected.includes(x.id)?'checked':''}><span class="scope-option-copy"><strong>${e(x.label)}</strong><small title="${e(x.id)}">ID ${e(x.id)}</small></span><span class="scope-request-count ${x.requestCount?'has-requests':''}">${x.requestCount?fmt(x.requestCount)+' 次请求':'暂无调用'}</span></label>`).join('');
const column=(title,name,id,list,selected)=>`<section class="scope-choice-panel" aria-labelledby="${id}-title"><div class="scope-choice-heading"><h3 id="${id}-title">${title}<span data-scope-count="${name}"></span></h3><button type="button" data-clear-scope="${name}">清空选择</button></div><input type="search" data-filter-options="${id}" aria-label="搜索${title}名称或ID" placeholder="搜索名称或 ID"><div class="scope-option-list" id="${id}">${choices(list,name,selected)}<p class="scope-no-options" data-no-options="${id}" ${list.length?'hidden':''}>没有匹配项，试试其他名称或 ID</p></div></section>`;
return `<form id="scopeForm"><div class="scope-modal-content"><p class="scope-modal-intro">未选择表示全部；调用次数按当前日期与已应用的筛选条件统计。</p><div class="scope-columns">${column('客户','customer','customer-options',S.catalog.customers,S.customerIds)}${column('模型','model','model-options',S.catalog.models,S.modelIds)}</div><fieldset class="scope-result"><legend>请求结果</legend><div class="scope-result-options">${Object.entries({ALL:'全部结果',SUCCESS:'仅成功',FAILURE:'仅失败'}).map(([key,label])=>`<label><input type="radio" name="result" value="${key}" ${S.result===key?'checked':''}><span>${label}</span></label>`).join('')}</div></fieldset><details class="scope-availability"><summary>筛选范围说明</summary><p>有调用记录的客户和模型优先显示；暂无调用仅指当前统计范围。行业、应用、项目、Key与渠道暂未开放筛选。</p></details></div><div class="scope-modal-footer"><div class="scope-draft-readout"><span>当前选择</span><strong id="scopeDraftSummary" role="status" aria-live="polite"></strong></div><div class="scope-modal-actions"><button type="button" class="scope-draft-reset" data-reset-scope-draft>重置条件</button><button type="button" data-cancel-scope>取消</button><button type="submit" class="primary">应用筛选</button></div></div></form>`;
}
