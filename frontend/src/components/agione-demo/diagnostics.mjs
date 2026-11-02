import {fmt} from './core.mjs';

export function diagnosticSummary(d,kind) {
 const s=d.summary;
 if(kind==='conversion'){
  if(d.signalState!=='APPLICABLE')return {
   title:'请先切换至全部结果，再判断接入是否受阻',
   evidence:'仅查看成功或失败请求，会遗漏判断所需的另一部分记录。',
   advice:'保留当前日期，清除筛选条件后重新查看。',
   action:'clear-filters',label:'清除筛选，查看全部结果',
  };
  const count=d.blocked.length;
  const sum=field=>d.blocked.reduce((total,x)=>total+x.summary[field],0);
  return {
   title:count?`${fmt(count)} 位客户多次尝试，仍未成功调用`:'当前范围未发现接入受阻客户',
   evidence:count?`相关请求共 ${fmt(sum('requestCount'))} 次，其中已确认余额不足 ${fmt(sum('balanceFailureCount'))} 次。`:'按至少 3 次尝试且所选期间无成功请求的条件判断。',
   advice:count?(sum('balanceFailureCount')?'优先核对客户余额及充值状态，再复查调用是否恢复成功。':'先查看失败证据，核对接入配置与具体错误。'):'可继续查看客户的实际调用情况。',
   target:'blocked',label:'查看客户与失败证据',
  };
 }
 if(kind==='decline'){
  if(d.comparison.state!=='READY')return {
   title:'前期暂不可比较，暂不能判断使用下降',
   evidence:d.comparison.reason||'尚无可比较的等长前期记录。',
   advice:'调整日期范围，或重新获取所选日期的数据。',
   action:'sync',label:'重新获取所选日期',
  };
  return {
   title:d.decline.length?`${fmt(d.decline.length)} 位客户的调用量下降，建议核实`:'当前阈值下未发现调用下降客户',
   evidence:`当前范围前期 ${fmt(d.comparison.summary.requestCount)} 次请求，本期 ${fmt(s.requestCount)} 次；按同一筛选条件比较。`,
   advice:d.decline.length?'先查看下降客户的请求变化和失败样本，再判断是否需要跟进。':'可调整观察范围，继续查看客户的使用变化。',
   target:'decline-diagnosis',label:'查看下降客户与证据',
  };
 }
 return {
  title:!s.requestCount?'当前范围没有调用记录':s.failureCount?`${fmt(d.affectedCustomers.length)} 位客户出现失败请求，建议排查`:'当前范围未发现失败请求',
  evidence:s.requestCount?`已确认失败 ${fmt(s.failureCount)} 次：余额不足 ${fmt(s.balanceFailureCount)} 次，已知技术失败 ${fmt(s.knownTechnicalFailureCount??s.technicalFailureCount)} 次，原因待分类 ${fmt(s.unmappedFailureCount)} 次。`:'可调整日期或筛选条件后查看。',
  advice:!s.failureCount?'有新调用后，可继续查看请求结果。':s.balanceFailureCount?'先核对余额不足的请求，再排查其他失败原因。':s.unmappedFailureCount?'部分失败原因待分类，请先查看请求证据。':'优先查看技术失败的具体错误和受影响客户。',
  target:'failure-customers',label:'查看受影响客户与证据',
 };
}
