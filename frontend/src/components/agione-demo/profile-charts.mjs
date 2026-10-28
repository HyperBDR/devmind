import {escapeHTML as e,fmt,percent,shanghaiDate,trendPlot} from './core.mjs';

const fields={totalTokens:'总 Token',inputTokens:'输入 Token',outputTokens:'输出 Token'};
const sampleField={totalTokens:'totalTokensSampleCount',inputTokens:'inputTokensSampleCount',outputTokens:'outputTokensSampleCount'};
const colors=['#2563eb','#8b7cf6','#16b8bd','#e6a23c','#ed7195','#a1afc2'];
const clock=value=>new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value));
const day=value=>shanghaiDate(new Date(value));
const short=value=>day(value).slice(5).replace('-','/');
export function grainOptions(window){
 const days=(Date.parse(window.endExclusive)-Date.parse(window.start))/864e5;
 return days<=1?['hour']:days<=7?['hour','day']:['day','week'];
}
export function chartBuckets(series,grain,field){
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
export function profileTrendView(profile,window,controls={}){
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
 const plot=trendPlot(points,previous,'value'),unit=plot.max>=10000?10000:1,unitName=unit===10000?'Token（万）':'Token';
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
 const indexes=[...new Set(Array.from({length:Math.min(grain==='hour'?7:5,points.length)},(_,i)=>Math.round(i*(points.length-1)/Math.max(1,Math.min(grain==='hour'?6:4,points.length-1)))))];
 if(grain==='hour'&&!multiDay&&points.length===24)indexes.splice(0,indexes.length,0,4,8,12,16,20,23);
 const grainName={hour:'小时',day:'日',week:'自然周'}[grain];
 const missing=points.filter(p=>p.requestCount>0&&p.knownCount===0).length;
 const partial=points.filter(p=>p.partial).length;
 const previousPartial=previous.some(p=>p.partial);
 const unavailable=unknown?`<div class="profile-chart-empty" role="status"><span aria-hidden="true">▥</span><strong>${multiDay?'所选期间':'当天'}暂无可用${field==='totalTokens'?' Token':fields[field]} 数据</strong><p>${fmt(requests)} 次请求均未返回${field==='totalTokens'?' Token':fields[field]}，用量未知不代表消耗为 0。</p><button class="link" data-customer-requests="${e(profile.customerTenantId||'')}">查看调用证据 →</button></div>`:'';
 return `<div class="profile-trend-head"><div><h3>Token 用量趋势</h3><p>已知用量 · 沿用页面筛选 · 北京时间</p></div><div class="profile-grain" role="group" aria-label="汇总粒度">${allowed.length===1?'<span class="profile-grain-static">按小时</span>':allowed.map(g=>`<button data-profile-grain="${g}" aria-pressed="${grain===g}">按${{hour:'小时',day:'日',week:'周'}[g]}</button>`).join('')}</div></div><div class="profile-trend-controls"><div role="group" aria-label="Token 指标">${Object.entries(fields).map(([k,v])=>`<button data-profile-metric="${k}" aria-pressed="${field===k}">${v}</button>`).join('')}</div><label><input type="checkbox" id="profileCompare" ${controls.compare&&!unknown?'checked':''} ${!priorSeries||unknown?'disabled':''}>对比等长前期${unknown?'（当前用量缺失）':!priorSeries?'（暂不可用）':''}</label></div><div class="trend-toolbar"><b>${unitName}</b><div class="trend-legend"><span class="trend-key">当前</span>${previous.length?'<span class="trend-key previous-key">等长前期</span>':''}</div></div><div class="profile-token-chart ${unknown?'is-unavailable':''}"><div class="trend-layout"><div class="trend-yaxis" aria-hidden="true">${(unknown?[]:plot.ticks).map(t=>`<span style="top:${100-100*t/plot.max}%">${fmt(t/unit)}</span>`).join('')}</div><div class="trend-visual" role="group" aria-label="${e(fields[field])}按${grainName}趋势"><svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-hidden="true">${plot.ticks.map(t=>`<path class="plot-grid" d="M0 ${180-180*t/plot.max}H600"/>`).join('')}${lines(plot.previous,previous,true)}${unknown?'':lines(plot.current,points,false)}</svg>${dots(plot.previous,previous,true)}${unknown?'':dots(plot.current,points,false)}${unavailable}</div></div><div class="trend-xaxis">${indexes.map(i=>`<span style="left:${points.length===1?50:100*i/(points.length-1)}%" class="${i===0?'first-tick':i===points.length-1?'last-tick':''}">${e(label(points[i],grain,multiDay))}</span>`).join('')}</div></div><div class="profile-chart-note"><span>${e(day(window.start))} — ${e(day(new Date(Date.parse(window.endExclusive)-1)))} · 按${grainName}汇总${grain==='week'?' · 首末周仅统计范围内日期':''}${points.length===1?' · 仅一个统计点，不绘制连线':''}</span>${!unknown?`<span class="profile-chart-status">● 完整用量${partial||previousPartial?' · ○ 部分已知，虚线连接':''}${partial?` · ${partial} 个时段仅展示已知用量，实际总量未知`:''}${missing?` · ${missing} 个时段用量缺失；虚线仅连接已知点，不代表缺失时段用量`:''}</span>`:''}</div>${!plot.current.length&&!unknown?'<p class="profile-usage-warning">当前指标暂无完整用量，请切换指标或查看用量覆盖情况。</p>':''}`;
}
export function compactUsage(value,token=false){
 if(!Number.isFinite(value))return '—';
 const units=token?[[1e9,'B'],[1e6,'M'],[1e3,'K']]:[[1e12,'兆'],[1e8,'亿'],[1e4,'万']];
 const unit=units.find(([scale])=>Math.abs(value)>=scale);
 if(!unit)return fmt(value);
 const scaled=value/unit[0];
 return new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2,useGrouping:false}).format(scaled)+(token?'':' ')+unit[1];
}
function donut(parts,total,center,caption,compact=false){
 let offset=0;
 return `<div class="usage-donut${compact?' usage-donut-compact':''}" role="img" aria-label="${e(caption)}：${parts.map(p=>`${e(p.label)} ${percent(total?100*p.value/total:0)}`).join('，')}"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="48" class="donut-track"/>${total>0?parts.filter(p=>p.value>0).map(p=>{const share=p.value/total*100;const mark=`<circle cx="60" cy="60" r="48" pathLength="100" stroke="${p.color}" stroke-dasharray="${share} ${100-share}" stroke-dashoffset="${-offset}"/>`;offset+=share;return mark;}).join(''):''}</svg><div><strong title="${e(center)} ${e(caption)}">${e(compact&&Number.isFinite(Number(String(center).replaceAll(',','')))?compactUsage(Number(String(center).replaceAll(',','')),caption==='Token'):center)}</strong><small>${e(caption)}</small></div></div>`;
}
export function usageComposition(profile,allModels=false){
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
