<template>
 <div ref="host" style="display:contents" data-testid="agione-focus" @click="click"></div>
 <dialog ref="rulesDialog" class="rules-drawer">
  <form @submit.prevent="saveRules">
   <header><div><h2>规则设置</h2><p>配置客户诊断和运营通知</p></div><button type="button" aria-label="关闭" @click="rulesDialog.close()">×</button></header>
   <section class="rules-body"><h3>诊断规则</h3><p>沿用当前设置，用于判断客户线索</p>
   <div class="rules-fields">
   <label>分析周期（完整自然日）<input v-model.number="draft.analysisDays" type="number" min="1" max="15" step="1" required></label>
   <label>近期无调用提醒（完整自然日）<input v-model.number="draft.inactivityDays" type="number" min="1" max="31" step="1" required></label>
   <label>使用下降阈值（%）<input v-model.number="draft.declinePercent" type="number" min="1" max="100" step="0.1" required></label>
   <label>技术失败比例阈值（%）<input v-model.number="draft.technicalFailurePercent" type="number" min="0.1" max="100" step="0.1" required></label>
   <label>技术失败规则最少请求<input v-model.number="draft.minTechnicalRequests" type="number" min="1" step="1" required></label>
   </div>
   <p>缺少前期数据时无法判断下降。目前上游技术失败类型尚未确认，技术失败规则暂无法判断。</p>
   <section class="notify-settings">
    <div class="notify-heading"><div><h3>自动刷新</h3><p>增量更新调用数据并巡检紧急异常</p></div><label class="switch"><input v-model="draft.autoRefreshEnabled" type="checkbox"><span>{{ draft.autoRefreshEnabled ? '已开启' : '已关闭' }}</span></label></div>
    <div class="refresh-periods">
     <div class="refresh-field"><span>调用与巡检</span><AgioneSelect v-model="draft.autoRefreshHours" label="调用与巡检" :options="callPeriods" :disabled="!draft.autoRefreshEnabled" /></div>
     <div class="refresh-field"><span>财务数据</span><AgioneSelect v-model="draft.financeRefreshHours" label="财务数据" :options="dataPeriods" /></div>
     <div class="refresh-field"><span>租户信息</span><AgioneSelect v-model="draft.tenantRefreshHours" label="租户信息" :options="dataPeriods" /></div>
    </div>
    <p>自动刷新只发送紧急事件；持续异常到达重复提醒间隔时，会提前采集确认。运营日报仍只在下方设置的时间发送。</p>
    <div v-if="autoStatus" class="notify-status"><span>{{ autoStatus }}</span></div>
    <div v-if="inspectionStatus" class="notify-status"><span>{{ inspectionStatus }}</span></div>
    <details v-if="serverRules?.inspectionHistory?.length" class="recent-syncs">
     <summary>{{ locale.startsWith('en') ? 'Inspection and notification history (latest 20)' : '巡检与通知记录（最近 20 条）' }}</summary>
     <div v-for="item in serverRules.inspectionHistory" :key="item.runId" class="recent-sync-detail">
      <strong>{{ displayTime(item.createdAt) }} · {{ inspectionOutcome(item.outcome) }}</strong>
      <span>{{ locale.startsWith('en') ? 'Interval:' : '时间范围：' }} {{ displayTime(item.inspectionStart) }} — {{ displayTime(item.inspectionEnd) }} ({{ locale.startsWith('en') ? 'Beijing time' : '北京时间' }})</span>
      <span>{{ locale.startsWith('en') ? 'Current issues:' : '当前命中问题：' }} {{ item.issueCount }} · ID {{ item.runId }}</span>
      <span v-for="issue in item.issues" :key="`${issue.customerId}-${issue.reason}`">{{ locale.startsWith('en') ? 'Tenant' : '租户' }} {{ issue.customerId }} · {{ inspectionReason(issue.reason) }} · {{ inspectionIssueDecision(issue.decision) }}</span>
      <span v-if="item.issueCount > item.issues.length">{{ locale.startsWith('en') ? 'First 50 issues shown' : '仅显示前 50 条问题' }}</span>
      <span v-for="(delivery, index) in item.deliveries" :key="index">{{ locale.startsWith('en') ? 'Delivery:' : '通知发送：' }} {{ deliveryLabel(delivery.status) }} · {{ locale.startsWith('en') ? 'Attempts' : '尝试' }} {{ delivery.attempts }}<template v-if="delivery.nextRetryAt"> · {{ locale.startsWith('en') ? 'Next retry' : '下次重试' }} {{ displayTime(delivery.nextRetryAt) }}</template></span>
     </div>
    </details>
    <div v-if="serverRules?.inspectionGap && serverRules.inspectionGap.status !== 'acknowledged'" class="notify-status"><span>{{ locale.startsWith('en') ? 'Inspection gap requiring manual review:' : '巡检存在缺口，请人工核查：' }} {{ displayTime(serverRules.inspectionGap.start) }} — {{ displayTime(serverRules.inspectionGap.end) }} ({{ locale.startsWith('en') ? 'Beijing time' : '北京时间' }})</span><button type="button" :disabled="rulesLoading" @click="acknowledgeGap">{{ locale.startsWith('en') ? 'Confirm manual review' : '确认已人工核查' }}</button></div>
    <details v-if="serverRules?.inspectionGapHistory?.length"><summary>{{ locale.startsWith('en') ? 'Gap review history (latest 20)' : '缺口确认记录（最近 20 条）' }}</summary><div v-for="item in serverRules.inspectionGapHistory" :key="`${item.gapStart}-${item.acknowledgedAt}`" class="notify-status"><span>{{ displayTime(item.gapStart) }} — {{ displayTime(item.gapEnd) }} · {{ locale.startsWith('en') ? 'Skipped through' : '跳过至' }} {{ displayTime(item.skippedUntil) }} · {{ locale.startsWith('en') ? 'Confirmed' : '确认时间' }} {{ displayTime(item.acknowledgedAt) }} · ID {{ item.acknowledgedById }}</span></div></details>
    <div v-if="financeStatus" class="notify-status"><span>{{ financeStatus }}</span></div>
    <details v-if="recentRuns.length" class="recent-syncs">
     <summary class="recent-syncs-heading"><strong>{{ locale.startsWith('en') ? 'Recent collection tasks' : '最近采集任务' }}</strong><span>{{ locale.startsWith('en') ? 'Latest 5' : '最近 5 条' }}</span></summary>
     <div class="recent-sync-list">
      <details v-for="run in recentRuns" :key="run.runId" class="recent-sync">
       <summary class="recent-sync-row">
        <strong>{{ runType(run.trigger) }}</strong>
        <span class="recent-sync-status" :class="`status-${run.status}`">{{ runStatus(run.status) }}</span>
        <time>{{ displayShortTime(run.createdAt) }}</time>
        <span class="recent-sync-duration">{{ run.finishedAt ? runDuration(run.createdAt, run.finishedAt) : '—' }}</span>
        <span class="recent-sync-more"><span class="when-closed">{{ locale.startsWith('en') ? 'Details' : '查看详情' }} ⌄</span><span class="when-open">{{ locale.startsWith('en') ? 'Hide' : '收起详情' }} ⌃</span></span>
       </summary>
       <div class="recent-sync-detail">
        <span>{{ locale.startsWith('en') ? 'Started:' : '开始：' }} {{ displayTime(run.createdAt) }} · {{ locale.startsWith('en') ? 'Stage:' : '阶段：' }} {{ runPhase(run.phase) }}</span>
        <span>{{ locale.startsWith('en') ? 'Last heartbeat:' : '最后心跳：' }} {{ displayTime(run.heartbeatAt) }} · {{ locale.startsWith('en') ? 'Attempts:' : '尝试：' }} {{ run.attempt }}</span>
        <span v-if="run.finishedAt">{{ locale.startsWith('en') ? 'Duration:' : '耗时：' }} {{ runDuration(run.createdAt, run.finishedAt) }}</span>
        <span v-if="run.errorCode">{{ locale.startsWith('en') ? 'Reason:' : '原因：' }} {{ runError(run.errorCode) }} ({{ run.errorCode }})</span>
       </div>
      </details>
     </div>
    </details>
   </section>
   <section class="notify-settings">
    <div class="notify-heading"><div><h3>通知设置</h3><p>分析完成后，将需要处理的问题发送给运营</p></div><label class="switch"><input v-model="draft.enabled" type="checkbox"><span>{{ draft.enabled ? '已启用' : '未启用' }}</span></label></div>
    <div class="notify-preview" aria-label="通知规则预览">
     <label><input v-model="draft.continuousFailure" type="checkbox"> 持续调用失败</label>
     <label><input v-model="draft.balanceFailure" type="checkbox"> 余额不足导致调用失败</label>
     <label><input v-model="draft.decline" type="checkbox"> 客户使用下降（每日汇总）</label>
     <label><input v-model="draft.inactive" type="checkbox"> 客户长期无调用（每日汇总）</label>
    </div>
    <div class="notify-label">通知渠道<AgioneSelect v-model="draft.channelId" label="通知渠道" placeholder="请选择通知渠道" :options="channelOptions" /></div>
    <label class="notify-label schedule-time">每日自动采集时间（北京时间）<input v-model="draft.scheduleTime" type="time" required></label>
    <p>启用通知后，每天到达该时间自动采集；分析完成后按上述规则发送消息。</p>
    <p>没有渠道？ <a href="/management/notifier/channels">前往通知渠道管理 ↗</a></p>
    <div v-if="dailyStatus || analysisStatus || deliveryStatus" class="notify-status"><span v-if="dailyStatus">{{ dailyStatus }}</span><span v-if="analysisStatus">{{ analysisStatus }}</span><span v-if="deliveryStatus">{{ deliveryStatus }}</span></div>
    <details><summary>高级通知设置</summary><label>异常观察窗口（分钟）<input v-model.number="draft.eventWindowMinutes" type="number" min="5" max="1440" step="5" required></label><label>持续失败最少次数<input v-model.number="draft.minFailureCount" type="number" min="1" step="1" required></label><label>持续失败比例（%）<input v-model.number="draft.failureRatePercent" type="number" min="1" max="100" step="1" required></label><label>余额不足最少次数<input v-model.number="draft.minBalanceFailureCount" type="number" min="1" step="1" required></label><label>相同问题重复提醒间隔（小时）<input v-model.number="draft.repeatHours" type="number" min="1" max="168" step="1" required></label><label class="recovery"><input v-model="draft.sendRecovery" type="checkbox"> 问题恢复后发送通知</label><label class="recovery"><input v-model="draft.sendRecoveredHistory" type="checkbox"> 发送已恢复的历史异常</label><p>巡检会覆盖两次成功巡检之间的完整区间；观察窗口只用于判断持续失败。</p></details>
   </section></section>
   <p v-if="rulesError" role="alert">{{ rulesError }}</p><footer><button type="button" @click="rulesDialog.close()">取消</button><button type="submit" class="primary" :disabled="rulesLoading || !serverRules">保存诊断规则</button></footer>
  </form>
 </dialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import AgioneSelect from './AgioneSelect.vue'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState, readonlyWorkspaceMarkup } from '@/utils/agioneOriginalWorkspace'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
import { applyRules } from './rules.mjs'
import { updateWorkspaceDom } from './workspace-dom.js'
import { agioneOpsApi } from '@/api/agioneOps'
import { dailyReportLabel, notificationRuleDefaults, notificationRulePayload, resolveNotificationRules } from './notification-rules.mjs'
const { locale } = useI18n({ useScope: 'global' })
const props=defineProps({state:{type:Object,required:true},previousLoading:{type:Boolean,default:false}})
const emit=defineEmits(['customer','requests','analyze-model','clear','diagnosis','view','previous'])
const defaults=notificationRuleDefaults
const rulesDialog=ref(null),thresholds=ref({...defaults}),draft=ref({...defaults})
const rulesError=ref(''),rulesLoading=ref(false),serverRules=ref(null)
const channels=ref([])
const recentRuns=computed(()=>serverRules.value?.recentRuns || [])
const runType=value=>(locale.value.startsWith('en') ? {automatic:'Automatic refresh',scheduled:'Daily report',manual:'Manual refresh',finance:'Finance'} : {automatic:'自动刷新',scheduled:'日报采集',manual:'手动刷新',finance:'财务采集'})[value] || (locale.value.startsWith('en') ? 'Collection' : '数据采集')
const runStatus=value=>(locale.value.startsWith('en') ? {queued:'Queued',running:'Collecting',retrying:'Retrying',succeeded:'Collected',failed:'Failed',interrupted:'Interrupted',dispatch_failed:'Dispatch failed',revoked:'Access revoked'} : {queued:'排队中',running:'采集中',retrying:'重试中',succeeded:'采集完成',failed:'失败',interrupted:'已中断',dispatch_failed:'派发失败',revoked:'权限已撤销'})[value] || (locale.value.startsWith('en') ? 'Unknown' : '状态待确认')
const runPhase=value=>(locale.value.startsWith('en') ? {queued:'Queued',identity:'Verifying connection',calls:'Fetching requests',models:'Fetching models',staging:'Saving data',finance:'Processing finance',splitting:'Splitting periods',retrying:'Waiting to retry',succeeded:'Complete',failed:'Failed',interrupted:'Interrupted'} : {queued:'等待执行',identity:'验证连接',calls:'读取调用',models:'读取模型',staging:'保存数据',finance:'处理财务',splitting:'拆分时段',retrying:'等待重试',succeeded:'完成',failed:'失败',interrupted:'已中断'})[value] || value || (locale.value.startsWith('en') ? 'Unknown' : '待确认')
const runError=value=>(locale.value.startsWith('en') ? {FINANCE_REFRESH_TIMEOUT:'Finance collection timed out',LEASE_EXPIRED:'Heartbeat expired',NATIVE_SYNC_DEADLINE:'Collection timed out',SOURCE_TIMEOUT:'Upstream request timed out',SOURCE_UNREACHABLE:'Upstream connection failed',SOURCE_RATE_LIMITED:'Upstream rate limit',DISPATCH_FAILED:'Task dispatch failed',SYNC_FAILED:'Collection error',ACCESS_REVOKED:'Access revoked'} : {FINANCE_REFRESH_TIMEOUT:'财务采集超时',LEASE_EXPIRED:'任务心跳超时，等待恢复',NATIVE_SYNC_DEADLINE:'采集超时',SOURCE_TIMEOUT:'上游接口超时',SOURCE_UNREACHABLE:'上游连接失败',SOURCE_RATE_LIMITED:'上游请求受限',DISPATCH_FAILED:'任务派发失败',SYNC_FAILED:'采集异常',ACCESS_REVOKED:'访问权限已撤销'})[value] || (locale.value.startsWith('en') ? 'Collection incomplete' : '采集未完成')
const callPeriods=[{value:2,label:'每 2 小时'},{value:3,label:'每 3 小时'},{value:4,label:'每 4 小时'}]
const dataPeriods=[{value:6,label:'每 6 小时'},{value:12,label:'每 12 小时'},{value:24,label:'每 24 小时'}]
const channelOptions=computed(()=>[{value:null,label:'请选择通知渠道'},...channels.value.map(channel=>({value:channel.id,label:channel.name}))])
function displayTime(value){const none=locale.value.startsWith('en')?'Unavailable':'暂无';if(!value)return none;const date=new Date(value);return Number.isNaN(date.getTime())?none:date.toLocaleString(locale.value.startsWith('en')?'en-GB':'zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})}
function displayShortTime(value){if(!value)return '—';const date=new Date(value);if(Number.isNaN(date.getTime()))return '—';const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date).map(({type,value})=>[type,value]));return `${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`}
const autoStatus=computed(()=>{const value=serverRules.value?.refreshStatus?.calls;if(!value)return '';return `最近执行：${value.status || '未运行'}；下次常规刷新：${displayTime(value.nextAt)}`})
const inspectionStatus=computed(()=>{const value=serverRules.value?.lastAnalysis;if(value?.trigger!=='automatic'||!value.inspectionStart||!value.inspectionEnd)return '';return `${locale.value.startsWith('en')?'Last inspection':'最近巡检覆盖'}：${displayTime(value.inspectionStart)} — ${displayTime(value.inspectionEnd)} (${locale.value.startsWith('en')?'Beijing time':'北京时间'})`})
const inspectionOutcome=value=>(locale.value.startsWith('en')?{queued:'Notification created',repeat_interval:'Within repeat interval',no_qualifying_event:'No qualifying event',duplicate:'Duplicate notification',history_disabled:'Historical recovery alerts disabled',not_ready:'Insufficient data',notifications_disabled:'Notifications disabled',channel_missing:'Notification channel missing'}:{queued:'已创建通知',repeat_interval:'重复提醒间隔内',no_qualifying_event:'未发现符合条件的异常',duplicate:'通知已存在',history_disabled:'历史恢复提醒未启用',not_ready:'数据不足',notifications_disabled:'通知未启用',channel_missing:'未配置通知渠道'})[value] || value
const inspectionReason=value=>(locale.value.startsWith('en')?{continuous_failure:'Continuous failure',balance_failure:'Insufficient balance'}:{continuous_failure:'持续调用失败',balance_failure:'余额不足'})[value] || value
const inspectionIssueDecision=value=>(locale.value.startsWith('en')?{eligible:'Eligible for alert',repeat_interval:'Within repeat interval',notifications_disabled:'Notifications disabled',channel_missing:'Notification channel missing'}:{eligible:'符合提醒条件',repeat_interval:'重复提醒间隔内',notifications_disabled:'通知未启用',channel_missing:'未配置通知渠道'})[value] || value
const deliveryLabel=value=>(locale.value.startsWith('en')?{pending:'Pending',sending:'Sending',retrying:'Retrying',sent:'Sent',failed:'Failed',silenced:'Not sent'}:{pending:'等待发送',sending:'发送中',retrying:'重试中',sent:'已发送',failed:'发送失败',silenced:'未发送'})[value] || value
const financeStatus=computed(()=>{const value=serverRules.value?.refreshStatus?.finance;if(!value)return '';const en=locale.value.startsWith('en');const labels=en?{ready:'Ready',queued:'Queued',running:'Collecting',retrying:'Retrying',failed:'Failed',not_run:'Not collected'}:{ready:'已完成',queued:'等待执行',running:'采集中',retrying:'重试中',failed:'失败',not_run:'尚未采集'};return `${en?'Finance':'财务采集'}：${labels[value.status] || value.status}${value.updatedAt ? ` · ${displayTime(value.updatedAt)}` : ''}${value.errorCode ? ` · ${runError(value.errorCode)} (${value.errorCode})` : ''}`})
function runDuration(start,end){const seconds=Math.max(0,Math.round((new Date(end)-new Date(start))/1000));return Number.isFinite(seconds)?`${Math.floor(seconds/60)} ${locale.value.startsWith('en')?'min':'分'} ${seconds%60} ${locale.value.startsWith('en')?'sec':'秒'}`:'—'}
const dailyStatus=computed(()=>{const value=serverRules.value?.dailyReport;if(!value)return '';return `今日日报：${dailyReportLabel(value)}${value.updatedAt ? ` · ${displayTime(value.updatedAt)}` : ''}`})
const analysisStatus=computed(()=>{
 const value=serverRules.value?.lastAnalysis
 if(!value)return ''
 if(value.status==='insufficient_data')return '最近分析：数据不足，等待完整周期'
 return `最近分析：发现 ${value.alerts?.length || 0} 个待处理客户`
})
const deliveryStatus=computed(()=>{
 const value=serverRules.value?.deliveryStatus
 if(!value)return ''
 const labels={pending:'等待发送',sending:'发送中',retrying:`重试中（${value.attempts}/3）`,sent:'已发送',failed:'发送失败',silenced:'未发送'}
 return `最近通知：${labels[value.status] || value.status}`
})
let legacyRules=null, rulesRequest=0
try { legacyRules=JSON.parse(localStorage.getItem('agione-thresholds') || 'null') } catch { /* Ignore malformed legacy browser state. */ }
function applyLoadedRules(response){
 const resolved=resolveNotificationRules(response,legacyRules)
 serverRules.value=resolved;channels.value=response.channels || [];draft.value={...resolved}
 thresholds.value={...thresholds.value,inactivityDays:resolved.inactivityDays,declinePercent:resolved.declinePercent,technicalFailurePercent:resolved.technicalFailurePercent,minTechnicalRequests:resolved.minTechnicalRequests}
}
async function loadRules(connectionId,reportError=false){
 const request=++rulesRequest
 if(!connectionId){serverRules.value=null;channels.value=[];return}
 rulesLoading.value=true
 try { const response=await agioneOpsApi.notificationRules(connectionId);if(request===rulesRequest)applyLoadedRules(response.data.data) }
 catch { if(request===rulesRequest&&reportError)rulesError.value='规则读取失败，请检查连接权限后重试。' }
 finally { if(request===rulesRequest)rulesLoading.value=false }
}
async function saveRules(){
 rulesError.value=''; rulesLoading.value=true
 try {
  if(draft.value.enabled&&!draft.value.channelId){rulesError.value='启用消息推送前，请先选择通知渠道。';return}
  const response=await agioneOpsApi.saveNotificationRules(props.state.connectionId,notificationRulePayload(draft.value))
  serverRules.value={...serverRules.value,...response.data.data,configured:true}; thresholds.value={...thresholds.value,...draft.value}
  try { localStorage.removeItem('agione-thresholds') } catch { /* Storage cleanup is best effort. */ }
  eventPage.value=1; rulesDialog.value.close()
 } catch { rulesError.value='规则保存失败，请检查连接权限后重试。' }
 finally { rulesLoading.value=false }
}
async function acknowledgeGap(){
 const gap=serverRules.value?.inspectionGap
 if(!gap)return
 const message=locale.value.startsWith('en')
  ? 'Confirm manual review? Uninspected events through now will be skipped; automatic inspection will resume from now.'
  : '确认已人工核查？系统将跳过截至当前时间尚未巡检的历史事件，并从当前时间恢复自动巡检。'
 if(!window.confirm(message))return
 rulesLoading.value=true;rulesError.value=''
 try {
  await agioneOpsApi.acknowledgeInspectionGap(props.state.connectionId,{start:gap.start,end:gap.end})
  await loadRules(props.state.connectionId,true)
 } catch { rulesError.value='确认失败，缺口可能已变化，请刷新后重试。' }
 finally { rulesLoading.value=false }
}
async function openRules(){
 rulesError.value='';draft.value={...(serverRules.value || thresholds.value)};rulesDialog.value.showModal();await loadRules(props.state.connectionId,true)
}
const host=ref(null),eventKind=ref('all'),eventPage=ref(1),diagnosis=ref('all')
const chartView=ref('hourly'),hourMetric=ref('requests'),hourMode=ref('total')
watch(()=>[props.state.connectionId,props.state.dataVersion,props.state.window,props.state.filters,props.state.customerIds],()=>{eventKind.value='all';eventPage.value=1;diagnosis.value='all';emit('diagnosis','all')})
watch(()=>props.state.connectionId,(connectionId)=>loadRules(connectionId),{immediate:true})
const html=computed(()=>{
 const state={...originalWorkspaceState(props.state),previousLoading:props.previousLoading,thresholds:thresholds.value,eventKind:eventKind.value,eventPage:eventPage.value,diagnosis:diagnosis.value,chartView:chartView.value,hourMetric:hourMetric.value,hourMode:hourMode.value}
 if(state.dashboard) state.dashboard=applyRules(state.dashboard,thresholds.value)
 const result=renderOriginalWorkspace(state,'focus',{locale:locale.value,transform:markup=>{
  let result=markup
 if(diagnosis.value!=='all')result=`<div class="diagnostic-nav"><button class="primary diagnostic-back" data-diagnose="all"><span aria-hidden="true">←</span> 返回经营看板</button><nav class="diagnostic-tabs" aria-label="诊断分类">${Object.entries({decline:'使用下降',conversion:'接入受阻',failure:'失败原因'}).map(([key,label])=>`<button data-diagnose="${key}" aria-current="${diagnosis.value===key?'page':'false'}">${label}</button>`).join('')}</nav></div>`+result
  return readonlyWorkspaceMarkup(result,props.state)
 }})
 return DOMPurify.sanitize(result,{USE_PROFILES:{html:true,svg:true,svgFilters:true}})
})
watch([host, html], ([element, markup]) => {
 if (element) updateWorkspaceDom(element, markup)
}, { immediate: true, flush: 'post' })
function click(event){const button=event.target.closest('button');if(!button||button.disabled)return
 if(button.hasAttribute('data-chart-view'))chartView.value=button.dataset.chartView
 if(button.hasAttribute('data-hour-metric'))hourMetric.value=button.dataset.hourMetric
 if(button.hasAttribute('data-hour-mode'))hourMode.value=button.dataset.hourMode
 if(button.hasAttribute('data-open-rules'))openRules()
 if(button.hasAttribute('data-retry-previous'))emit('previous')
 if(button.hasAttribute('data-profile'))emit('customer',button.dataset.profile)
 if(button.hasAttribute('data-customer-requests'))emit('requests',button.dataset.customerRequests)
 if(button.hasAttribute('data-queue-evidence'))emit('requests',button.dataset.queueEvidence)
 if(button.hasAttribute('data-analyze-model'))emit('analyze-model',button.dataset.analyzeModel)
  if(button.hasAttribute('data-view'))emit('view',button.dataset.view)
 if(button.hasAttribute('data-event-kind')){eventKind.value=button.dataset.eventKind;eventPage.value=1}
 if(button.hasAttribute('data-event-page'))eventPage.value=Number(button.dataset.eventPage)
 if(button.hasAttribute('data-clear-filters'))emit('clear')
 if(button.hasAttribute('data-diagnose')){diagnosis.value=button.dataset.diagnose;emit('diagnosis',diagnosis.value)}
 if(button.hasAttribute('data-diagnostic-evidence'))host.value.querySelector(`[data-panel="${button.dataset.diagnosticEvidence}"]`)?.scrollIntoView({block:'start'})
}
</script>

<style scoped>
:global(.agione-demo dialog.rules-drawer) { position:fixed; inset:0; margin:auto; border:0; border-radius:12px; padding:0; width:min(550px,calc(100vw - 32px)); max-width:calc(100vw - 32px); height:min(760px,calc(100dvh - 32px)); max-height:calc(100dvh - 32px); overflow:hidden; box-shadow:0 24px 80px #15283f33; color:#1b304d; }
dialog::backdrop { background: #0006; }
form { display:flex; flex-direction:column; height:100%; }
header,footer { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:20px 28px; border-bottom:1px solid #e5ebf2; }
header h2 { margin:0; font-size:19px; } header p,.rules-body p { margin:6px 0; color:#73869f; font-size:12px; line-height:1.6; }
header button { border:0; background:none; color:#8190a4; font-size:24px; cursor:pointer; }
.rules-body { flex:1; min-height:0; overflow:auto; padding:22px 28px; } .rules-body h3 { margin:0 0 6px; font-size:15px; }
.rules-fields { border:1px solid #e2eaf3; border-radius:8px; margin:16px 0 10px; padding:0 15px; }
label { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:12px 0; border-bottom:1px solid #edf1f6; font-size:13px; } label:last-child { border:0; }
input { width:80px; border:1px solid #dce3ee; border-radius:6px; padding:8px; }
.notify-settings { margin-top:24px; padding-top:22px; border-top:1px solid #e9eef5; } .notify-settings a { display:inline-block; margin-top:10px; color:#2864ed; font-size:13px; }
.refresh-periods { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-top:12px; } .refresh-periods .refresh-field { display:grid; gap:7px; border:0; padding:0; color:#526883; } .refresh-periods select { min-width:0; padding:9px; border:1px solid #dce3ee; border-radius:6px; background:#fff; color:#1b304d; }
.notify-heading { display:flex; justify-content:space-between; align-items:center; gap:12px; } .switch { border:0; padding:0; justify-content:flex-end; color:#2864ed; white-space:nowrap; } .switch input,.recovery input { width:auto; }
.notify-preview { display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; margin-top:14px; } .notify-preview label { justify-content:flex-start; border:0; padding:6px 0; } .notify-preview input { width:auto; }
@media(max-width:560px) { .notify-preview,.refresh-periods { grid-template-columns:1fr; } }
.notify-label { display:grid; gap:8px; margin-top:16px; border:0; } .notify-label select { width:100%; padding:10px 12px; border:1px solid #dce3ee; border-radius:6px; color:#8797aa; background:#f8fafc; }
.schedule-time input { width:140px; padding:9px 12px; border:1px solid #dce3ee; border-radius:6px; color:#1b304d; background:#fff; }
.notify-settings details { margin-top:18px; border-top:1px solid #edf1f6; padding-top:16px; } .notify-settings summary { cursor:pointer; font-size:13px; }
.notify-status { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:14px; padding:10px 12px; border-radius:7px; background:#f4f7fb; color:#667b96; font-size:12px; } .recovery { justify-content:flex-start; }
.notify-settings .recent-syncs { margin-top:16px; padding:0; border:1px solid #dce5f1; border-radius:8px; overflow:hidden; }
.recent-syncs-heading { display:flex; align-items:center; gap:8px; padding:14px 16px; color:#1b304d; font-size:14px; cursor:pointer; }
.recent-syncs-heading::before { content:'▸'; color:#71849e; }
.recent-syncs[open] > .recent-syncs-heading::before { content:'▾'; }
.recent-syncs-heading > span { margin-left:auto; color:#71849e; font-size:12px; }
.recent-sync-list { border-top:1px solid #e6ecf4; }
.notify-settings .recent-sync { margin:0; padding:0; border:0; }
.notify-settings .recent-sync + .recent-sync { border-top:1px solid #edf1f6; }
.recent-sync-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:12px 15px; color:#253c59; font-size:12px; cursor:pointer; list-style:none; }
.recent-sync-row::-webkit-details-marker, .recent-syncs-heading::-webkit-details-marker { display:none; }
.recent-sync-row strong { flex:1 1 80px; color:#1b304d; font-size:13px; }
.recent-sync-status { padding:3px 7px; border-radius:4px; color:#657b96; background:#f1f4f8; white-space:nowrap; }
.status-succeeded { color:#258c6b; background:#eaf8f2; }
.status-failed, .status-interrupted, .status-revoked, .status-dispatch_failed { color:#d45454; background:#fff1f1; }
.recent-sync-duration, .recent-sync-row time, .recent-sync-more { white-space:nowrap; }
.recent-sync-more { color:#2864ed; }
.recent-sync-more .when-open, .recent-sync[open] .when-closed { display:none; }
.recent-sync[open] .when-open { display:inline; }
.recent-sync-detail { display:grid; gap:4px; margin:0 15px 12px; padding:12px; border-radius:6px; background:#f5f8fd; color:#617894; font-size:12px; line-height:1.6; }
footer { justify-content:flex-end; border-top:1px solid #e5ebf2; border-bottom:0; } footer button { padding:9px 14px; border:1px solid #dce3ee; border-radius:6px; background:#fff; cursor:pointer; } footer button.primary { background:#2864ed; border-color:#2864ed; color:#fff; }
</style>
