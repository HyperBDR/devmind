// Merge current-window signals by customer; saved followups do not create events.
export function customerEvents(customers){
 return customers.map(row=>({...row,eventKinds:[
  ...(row.signals.includes('blocked')?['blocked']:[]),
  ...(row.signals.includes('inactive')?['inactive']:[]),
  ...(row.signals.includes('decline')?['decline']:[]),
  ...(row.summary.failureCount>0?['failure']:[]),
 ]})).filter(row=>row.eventKinds.length).sort((a,b)=>
  Math.min(...a.eventKinds.map(rank))-Math.min(...b.eventKinds.map(rank))||
  b.summary.failureCount-a.summary.failureCount||
  String(a.customerTenantId).localeCompare(String(b.customerTenantId)));
}
function rank(kind){return {blocked:0,inactive:1,decline:2,failure:3}[kind];}
export function eventPage(rows,kind,page,size=2){
 const filtered=rows.filter(row=>kind==='all'||row.eventKinds.includes(kind));
 const pages=Math.max(1,Math.ceil(filtered.length/size));
 const current=Math.max(1,Math.min(page,pages));
 return {items:filtered.slice((current-1)*size,current*size),total:filtered.length,page:current,pages};
}
