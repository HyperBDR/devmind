<template><dialog ref="dialog" id="agione-scope-dialog" data-agione-dialog-id="agione-scope-dialog" @close="release" class="scope-dialog" aria-labelledby="scopeDialogTitle" @click="click" @input="input" @change="change" @submit.prevent="apply" @cancel="close"><div class="dialog-head"><h2 id="scopeDialogTitle">{{ t('agione.scopeTitle') }}</h2><button :title="t('agione.close')" :aria-label="t('agione.closeFilters')" @click="close"><span aria-hidden="true">×</span></button></div><div id="agione-scope-dialog-body" data-agione-dialog-body ref="body" class="dialog-body" v-html="markup"></div></dialog></template>
<script setup>
import { nextTick, ref, watch, onBeforeUnmount } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { claimOriginalDialog, releaseOriginalDialog } from '@/utils/agioneDialog'
import { renderOriginalScopeDialog } from './original-workspace-renderers.mjs'
const { t, locale }=useI18n({useScope:'global'})
const props=defineProps({state:{type:Object,required:true}})
const emit=defineEmits(['apply','directory'])
const dialog=ref(null),body=ref(null),markup=ref('')
let draft={customerIds:[],modelIds:[],result:'ALL'},terms={customer:'',model:''},timer=null,directorySignal=''
const signals={inactive:'signalInactive',blocked:'signalBlocked',decline:'signalDecline',technical:'signalTechnical',growth:'signalGrowth',trial:'signalTrial',stable:'signalStable'}
function catalog(){const directory=props.state.directory;return {customers:props.state.view==='portrait'&&directory?(directory.items||[]).map(x=>({id:x.customerTenantId,label:x.name||x.customerTenantId,requestCount:x.summary?.requestCount})):props.state.customerOptions,models:props.state.modelOptions}}
async function update(){if(!dialog.value?.open)return;const active=body.value?.contains(document.activeElement)?document.activeElement.getAttribute('data-filter-options'):null
 let html=renderOriginalScopeDialog({catalog:catalog(),customerIds:draft.customerIds,modelIds:draft.modelIds,result:draft.result},{locale:locale.value})
 if(props.state.view==='portrait'){
  const d=props.state.directory,total=d?.total,page=d?.page||1,size=d?.pageSize||25
  const pager=`<div class="profile-customer-pagination"><div class="pager"><button type="button" data-directory-page="${page-1}" ${page<=1?'disabled':''}>${t('agione.previousPage')}</button><span>${t('agione.directoryPagination',{page,pages:typeof total==='number'?Math.max(1,Math.ceil(total/size)):'—',total:total??'—'})}</span><button type="button" data-directory-page="${page+1}" ${typeof total==='number'&&page*size>=total?'disabled':''}>${t('agione.nextPage')}</button></div></div>`
  const signal=`<details class="profile-customer-filter"><summary>${t('agione.customerSignals')}</summary><div class="profile-customer-filter-body"><label class="form-field">${t('agione.signalLabel')}<select id="customerSignal"><option value="">${t('agione.allSignals')}</option>${Object.entries(signals).map(([key,label])=>`<option value="${key}" ${directorySignal===key?'selected':''}>${t('agione.'+label)}</option>`).join('')}</select></label></div></details>`
  html=html.replace('<div class="scope-option-list" id="customer-options">',`<div class="scope-option-list" id="customer-options">${signal}`)
  html=html.replace('<p class="scope-no-options" data-no-options="customer-options"',`${pager}<p class="scope-no-options" data-no-options="customer-options"`)
 }
 markup.value=DOMPurify.sanitize(html)
 await nextTick();for(const kind of ['customer','model']){const input=body.value.querySelector(`[data-filter-options="${kind}-options"]`);if(input)input.value=terms[kind]}
 updateDraft();filterModels();if(active)body.value.querySelector(`[data-filter-options="${active}"]`)?.focus()
 const status=body.value.querySelector('[data-no-options="customer-options"]');if(status&&props.state.directoryLoading){status.textContent=t('agione.directoryLoading');status.hidden=false}else if(status&&props.state.directoryError){status.textContent=t('agione.errors.networkError');status.hidden=false}
}
function open(){draft={customerIds:[...props.state.customerIds],modelIds:[...props.state.filters.modelIds],result:props.state.filters.statuses[0]||'ALL'};terms={customer:'',model:''};directorySignal='';claimOriginalDialog(dialog.value);dialog.value.showModal();update()}
function release(){if(dialog.value?.open)return;releaseOriginalDialog(dialog.value)}
function close(){clearTimeout(timer);dialog.value?.close();release()}
watch(locale,update)
watch(()=>[props.state.customerOptions,props.state.modelOptions,props.state.directory,props.state.directoryLoading,props.state.directoryError],update)
onBeforeUnmount(()=>{clearTimeout(timer);releaseOriginalDialog(dialog.value,{force:true})})
function updateDraft(){const form=body.value.querySelector('form');if(!form)return;for(const name of ['customer','model']){const ids=name==='customer'?draft.customerIds:draft.modelIds;const target=form.querySelector(`[data-scope-count="${name}"]`);if(target)target.textContent=ids.length?t('agione.selectedCount',{count:ids.length}):t('agione.all')}const label=t('agione.'+({ALL:'allResults',SUCCESS:'successOnly',FAILURE:'failureOnly'}[draft.result]||'allResults'));const summary=form.querySelector('#scopeDraftSummary');if(summary)summary.textContent=t('agione.scopeSummary',{customers:draft.customerIds.length?t('agione.customerCount',{count:draft.customerIds.length}):t('agione.allCustomers'),models:draft.modelIds.length?t('agione.modelCount',{count:draft.modelIds.length}):t('agione.allModels'),result:label})}
function change(event){const input=event.target;if(input.name==='result')draft.result=input.value;else if(['customer','model'].includes(input.name)){const key=input.name==='customer'?'customerIds':'modelIds';const selected=new Set(draft[key]);if(input.checked)selected.add(input.value);else selected.delete(input.value);draft[key]=[...selected]}else if(input.id==='customerSignal'){directorySignal=input.value;emit('directory',{search:terms.customer,signal:directorySignal,page:1})}updateDraft()}
function filterModels(){const list=body.value.querySelector('#model-options');let visible=0;for(const label of list?.querySelectorAll('[data-option-label]')||[]){label.hidden=!(label.dataset.optionSearch||label.textContent).toLocaleLowerCase().includes(terms.model.toLocaleLowerCase());if(!label.hidden)visible++}const empty=list?.querySelector('[data-no-options]');if(empty)empty.hidden=visible>0}
function input(event){const id=event.target.dataset.filterOptions;if(!id)return;const kind=id==='customer-options'?'customer':'model';terms[kind]=event.target.value;if(kind==='customer'&&props.state.view==='portrait'){clearTimeout(timer);timer=setTimeout(()=>emit('directory',{search:terms.customer,signal:directorySignal,page:1}),250)}else if(kind==='model')filterModels();else{const list=body.value.querySelector('#customer-options');for(const label of list.querySelectorAll('[data-option-label]'))label.hidden=!(label.dataset.optionSearch||label.textContent).toLocaleLowerCase().includes(terms.customer.toLocaleLowerCase())}}
function click(event){const button=event.target.closest('button');if(!button||button.disabled)return;if(button.hasAttribute('data-cancel-scope'))close();if(button.hasAttribute('data-directory-page'))emit('directory',{search:terms.customer,signal:directorySignal,page:Number(button.dataset.directoryPage)});if(button.hasAttribute('data-clear-scope')){draft[button.dataset.clearScope==='customer'?'customerIds':'modelIds']=[];update()}if(button.hasAttribute('data-reset-scope-draft')){draft={customerIds:[],modelIds:[],result:'ALL'};update()}}
function apply(){emit('apply',{customerIds:draft.customerIds,filters:{modelIds:draft.modelIds,statuses:draft.result==='ALL'?[]:[draft.result],failureTypes:[]}});close()}
defineExpose({open,close})
</script>
