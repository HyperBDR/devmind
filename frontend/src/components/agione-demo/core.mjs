export const FIXED_WINDOW = Object.freeze({start:'2026-10-01T00:00:00+08:00',endExclusive:'2026-10-14T10:53:09+08:00',timezone:'Asia/Shanghai'});
export function escapeHTML(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
export function fmt(value) { return value === null || value === undefined ? '—' : new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(value); }
export function percent(value) { return value === null || value === undefined ? '—' : fmt(value)+'%'; }
export function csvCell(value) {
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[\s\uFEFF]*[=+@-]/u.test(text) || /^[\t\r\n]/u.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"','""') + '"';
}
export function csvDocument(headers, rows) { return '\uFEFF' + [headers,...rows].map(r=>r.map(csvCell).join(',')).join('\r\n'); }
export function shanghaiDate(value=new Date()) {
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(value);
  return ['year','month','day'].map(k=>parts.find(p=>p.type===k).value).join('-');
}
export function recentWindow(now=new Date()) {
  const end=shanghaiDate(now)+'T00:00:00+08:00';
  return {start:shanghaiDate(new Date(new Date(end).getTime()-7*864e5))+'T00:00:00+08:00',endExclusive:end,timezone:'Asia/Shanghai'};
}
export function dateWindow(start, inclusiveEnd) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!/^\d{4}-\d{2}-\d{2}$/.test(inclusiveEnd)) throw Error('请完整填写起止日期');
  for(const day of [start,inclusiveEnd]) {
    const parsed=new Date(day+'T00:00:00+08:00');
    if(!Number.isFinite(parsed.getTime())||shanghaiDate(parsed)!==day)throw Error('日期不存在');
  }
  const end=shanghaiDate(new Date(new Date(inclusiveEnd+'T00:00:00+08:00').getTime()+864e5))+'T00:00:00+08:00';
  const window={start:start+'T00:00:00+08:00',endExclusive:end,timezone:'Asia/Shanghai'};
  const length=new Date(end)-new Date(window.start);
  if(!(length>0&&length<=31*864e5))throw Error('日期范围须为1～31天');
  if(new Date(end)>new Date()) throw Error('请选择已经结束的自然日');
  return window;
}
export function globalChanged(state) {
  state.version=null;state.member='';state.analysisPage=1;state.groupRows=[];state.selected=null;
  state.data=null;state.dashboard=null;state.trend=null;state.profile=null;state.customers=null;
  state.dialogContext=null;state.revision++;
}
export function exportFresh(status, version, expectedSource) {
  return Boolean(status && !status.sync_in_progress && status.data_version===version && status.source_id===expectedSource);
}

export function localChanged(state) {
  state.analysisPage=1;state.data=null;state.trend=null;state.groupRows=[];
  state.dialogContext=null;state.revision++;
}

export function trendMaximum(current, previous=[], field='requestCount') {
  return Math.max(1,...[...current,...(previous||[])].map(p=>p[field]).filter(Number.isFinite));
}

export function savedGroupPrompt(groups, status='READY') {
  if(status==='LOADING')return '正在读取已保存筛选方案…';
  if(status==='ERROR')return '筛选方案读取失败';
  return groups.length?'选择筛选方案':'暂无已保存筛选方案';
}

export function inclusiveWindowEnd(window) {
  return shanghaiDate(new Date(new Date(window.endExclusive).getTime()-1));
}

export function shiftDay(day, delta) {
  return shanghaiDate(new Date(new Date(day+'T00:00:00+08:00').getTime()+delta*864e5));
}
export function shiftMonth(month, delta) {
  const [year, number]=month.split('-').map(Number);
  return new Date(Date.UTC(year,number-1+delta,1)).toISOString().slice(0,7);
}
export function calendarMonth(month, locale='zh-CN') {
  const first=new Date(month+'-01T00:00:00Z');
  const offset=(first.getUTCDay()+6)%7;
  const count=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
  return {title:new Intl.DateTimeFormat(String(locale).startsWith('en')?'en-US':'zh-CN',{year:'numeric',month:'long',timeZone:'UTC'}).format(first),days:Array.from({length:42},(_,i)=>i>=offset&&i<offset+count?month+'-'+String(i-offset+1).padStart(2,'0'):null)};
}
export function selectRange(range, day) {
  return range.end||day<range.start?{start:day,end:null}:{start:range.start,end:day};
}

export function trendPlot(points, previous=[], field='requestCount', nice=false) {
  const knownMax=trendMaximum(points,previous,field);
  const raw=knownMax/4;
  const magnitude=10**Math.floor(Math.log10(raw));
  const niceStep=[1,2,2.5,5,10].find(value=>value*magnitude>=raw)*magnitude;
  const step=nice?Math.max(1,niceStep):Math.max(1,Math.ceil(raw));
  const max=Math.ceil(knownMax/step)*step;
  const segments=rows=>{
    const result=[];let segment=[];
    rows.forEach((point,index)=>{
      const value=point[field];
      if(Number.isFinite(value))segment.push({index,value,x:rows.length===1?50:100*index/(rows.length-1),y:100-100*value/max});
      else if(segment.length){result.push(segment);segment=[];}
    });
    if(segment.length)result.push(segment);
    return result;
  };
  return {max,ticks:Array.from({length:max/step+1},(_,i)=>i*step),current:segments(points),previous:segments(previous||[])};
}

export function tokenAxis(max, english=false) {
  const [unit, suffix] = [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']]
    .find(([value]) => max >= value) || [1, ''];
  return { unit, label: `${english?'Tokens':'Token'}${suffix?` (${suffix})`:''}` };
}
