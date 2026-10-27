<template>
 <div ref="host" style="display:contents" data-testid="agione-focus" @click="click" v-html="html"></div>
 <dialog ref="rulesDialog">
  <form @submit.prevent="saveRules">
   <h2>诊断阈值</h2>
   <label>近期无调用提醒（完整自然日）<input v-model.number="draft.inactivityDays" type="number" min="1" max="365" step="1" required></label>
   <label>使用下降阈值（%）<input v-model.number="draft.declinePercent" type="number" min="1" max="100" step="0.1" required></label>
   <label>技术失败比例阈值（%）<input v-model.number="draft.technicalFailurePercent" type="number" min="0.1" max="100" step="0.1" required></label>
   <label>技术失败规则最少请求<input v-model.number="draft.minTechnicalRequests" type="number" min="1" step="1" required></label>
   <p>缺少前期数据时无法判断下降。目前上游技术失败类型尚未确认，技术失败规则暂无法判断。</p>
   <div><button type="button" @click="rulesDialog.close()">取消</button><button type="submit">应用阈值</button></div>
  </form>
 </dialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState, readonlyWorkspaceMarkup } from '@/utils/agioneOriginalWorkspace'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
import { applyRules } from './rules.mjs'
const { locale } = useI18n({ useScope: 'global' })
const props=defineProps({state:{type:Object,required:true},previousLoading:{type:Boolean,default:false}})
const emit=defineEmits(['customer','requests','analyze-model','clear','diagnosis','view','previous'])
const defaults={inactivityDays:7,declinePercent:40,technicalFailurePercent:2,minTechnicalRequests:20}
const rulesDialog=ref(null),thresholds=ref({...defaults}),draft=ref({...defaults})
try { const saved=JSON.parse(localStorage.getItem('agione-thresholds') || 'null'); if(saved && Object.keys(defaults).every(k=>Number.isFinite(saved[k]) && saved[k]>0)) thresholds.value={...defaults,...saved} } catch {}
function saveRules(){ thresholds.value={...draft.value}; try { localStorage.setItem('agione-thresholds',JSON.stringify(thresholds.value)) } catch {} eventPage.value=1; rulesDialog.value.close() }
const host=ref(null),eventKind=ref('all'),eventPage=ref(1),diagnosis=ref('all')
watch(()=>[props.state.connectionId,props.state.dataVersion,props.state.window,props.state.filters,props.state.customerIds],()=>{eventKind.value='all';eventPage.value=1;diagnosis.value='all';emit('diagnosis','all')})
const html=computed(()=>{
 const state={...originalWorkspaceState(props.state),previousLoading:props.previousLoading,thresholds:thresholds.value,eventKind:eventKind.value,eventPage:eventPage.value,diagnosis:diagnosis.value}
 if(state.dashboard) state.dashboard=applyRules(state.dashboard,thresholds.value)
 const result=renderOriginalWorkspace(state,'focus',{locale:locale.value,transform:markup=>{
  let result=markup
 if(diagnosis.value!=='all')result=`<button class="primary diagnostic-back" data-diagnose="all"><span aria-hidden="true">←</span> 返回经营看板</button><nav class="diagnostic-tabs" aria-label="诊断分类">${Object.entries({decline:'使用下降',conversion:'接入受阻',failure:'失败原因'}).map(([key,label])=>`<button data-diagnose="${key}" aria-current="${diagnosis.value===key?'page':'false'}">${label}</button>`).join('')}</nav>`+result
  return readonlyWorkspaceMarkup(result,props.state)
 }})
 return DOMPurify.sanitize(result,{USE_PROFILES:{html:true,svg:true,svgFilters:true}})
})
function click(event){const button=event.target.closest('button');if(!button||button.disabled)return
 if(button.hasAttribute('data-open-rules')){draft.value={...thresholds.value};rulesDialog.value.showModal()}
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
dialog { border: 0; border-radius: 8px; padding: 24px; width: min(440px, 90vw); box-shadow: 0 8px 30px #0003; }
dialog::backdrop { background: #0006; }
form { display: grid; gap: 12px; }
label { display: grid; gap: 4px; }
input { border: 1px solid #dce3ee; border-radius: 4px; padding: 8px; }
form div { display: flex; justify-content: flex-end; gap: 8px; }
form button { padding: 8px 14px; border: 1px solid #dce3ee; border-radius: 4px; }
</style>
