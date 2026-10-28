<template><div ref="host" data-testid="agione-customers" @click="click" @change="change" @keydown="keyboard" v-html="html"></div></template>
<script setup>
import { computed, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState } from '@/utils/agioneOriginalWorkspace'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
const { locale } = useI18n({ useScope: 'global' })
const props = defineProps({ state: { type: Object, required: true } })
const emit = defineEmits(['change', 'select', 'requests', 'drill', 'clear', 'analyze-model'])
const host = ref(null)
const controls = ref({ field:'totalTokens',grain:'',compare:false,allModels:false })
watch(()=>props.state.selectedCustomerId,()=>{controls.value={field:'totalTokens',grain:'',compare:false,allModels:false}})
const html = computed(() => {
 const result = renderOriginalWorkspace(originalWorkspaceState(props.state), 'portrait', {...controls.value,locale:locale.value,transform:markup=>{
  let content=markup.replace(/data-refresh-finance/g,'data-refresh-finance disabled title="只读：请使用页面刷新读取已有快照，不采集"')
  const reason=originalWorkspaceState(props.state).profile?.financeUnavailableReason
  if(reason)content=content.replace('余额为最近采集值，非实时；账期消耗不随调用日期变化。','余额为最近采集值，非实时；账期消耗不随调用日期变化。'+reason)
  return content
 }})
  return DOMPurify.sanitize(result,{USE_PROFILES:{html:true,svg:true,svgFilters:true}})
})
function click(event) {
 const button=event.target.closest('button,[data-profile-user]')
 if(!button||button.disabled)return
 if(button.hasAttribute('data-customer-requests'))emit('requests',button.dataset.customerRequests)
 if(button.hasAttribute('data-clear-filters'))emit('clear')
 if(button.hasAttribute('data-profile-grain'))controls.value={...controls.value,grain:button.dataset.profileGrain}
 if(button.hasAttribute('data-profile-metric'))controls.value={...controls.value,field:button.dataset.profileMetric}
 if(button.hasAttribute('data-profile-models'))controls.value={...controls.value,allModels:!controls.value.allModels}
 if(button.hasAttribute('data-analyze-model'))emit('analyze-model',button.dataset.analyzeModel,props.state.selectedCustomerId)
 if(button.hasAttribute('data-profile-user')) { const row=props.state.profile?.members?.[Number(button.dataset.profileUser)];if(row)emit('drill',{row,customerId:props.state.selectedCustomerId,origin:{connectionId:props.state.connectionId,dataVersion:props.state.dataVersion,contextKey:props.state.contextKey}}) }
}
function change(event) { if(event.target.id==='profileCompare')controls.value={...controls.value,compare:event.target.checked} }
function keyboard(event) {if(['Enter',' '].includes(event.key)&&event.target.matches('[data-profile-user]')){event.preventDefault();click(event)}}
</script>
