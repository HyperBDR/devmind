<template><div ref="host" style="display:contents" data-testid="agione-focus" @click="click" v-html="html"></div></template>
<script setup>
import { computed, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState, readonlyWorkspaceMarkup } from '@/utils/agioneOriginalWorkspace'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
const { locale } = useI18n({ useScope: 'global' })
const props=defineProps({state:{type:Object,required:true}})
const emit=defineEmits(['customer','requests','analyze-model','clear','diagnosis','view'])
const host=ref(null),eventKind=ref('all'),eventPage=ref(1),diagnosis=ref('all')
watch(()=>[props.state.connectionId,props.state.dataVersion,props.state.window,props.state.filters,props.state.customerIds],()=>{eventKind.value='all';eventPage.value=1;diagnosis.value='all';emit('diagnosis','all')})
const html=computed(()=>{
 const state={...originalWorkspaceState(props.state),eventKind:eventKind.value,eventPage:eventPage.value,diagnosis:diagnosis.value}
 const result=renderOriginalWorkspace(state,'focus',{locale:locale.value,transform:markup=>{
  let result=markup
 if(diagnosis.value!=='all')result=`<button class="primary diagnostic-back" data-diagnose="all"><span aria-hidden="true">←</span> 返回经营看板</button><nav class="diagnostic-tabs" aria-label="诊断分类">${Object.entries({decline:'使用下降',conversion:'接入受阻',failure:'失败原因'}).map(([key,label])=>`<button data-diagnose="${key}" aria-current="${diagnosis.value===key?'page':'false'}">${label}</button>`).join('')}</nav>`+result
  return readonlyWorkspaceMarkup(result,props.state)
 }})
 return DOMPurify.sanitize(result,{USE_PROFILES:{html:true,svg:true,svgFilters:true}})
})
function click(event){const button=event.target.closest('button');if(!button||button.disabled)return
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
