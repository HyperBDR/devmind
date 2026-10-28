<template><div ref="host" data-testid="agione-analysis" @click="click" @change="change" @keydown="keyboard" v-html="html"></div></template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState } from '@/utils/agioneOriginalWorkspace'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
import { enhanceSelects, closeSelectMenus } from './select-menu.mjs'
const { locale } = useI18n({ useScope: 'global' })
const props = defineProps({ state: { type: Object, required: true } })
const emit = defineEmits(['change', 'drill', 'clear'])
const host = ref(null)
const html = computed(() => DOMPurify.sanitize(renderOriginalWorkspace(originalWorkspaceState(props.state), 'aggregate', {locale:locale.value,transform:markup=>markup.replace('data-export-analysis','data-export-analysis disabled title="只读：导出未开放"')}), { USE_PROFILES: { html: true, svg: true, svgFilters: true } }))
watch(html, async () => { await nextTick(); if(host.value)enhanceSelects(host.value) }, { immediate: true })
onBeforeUnmount(() => closeSelectMenus(host.value))
function change(event) {
 const patch = { groupBy: event.target.id === 'groupBy' ? event.target.value : props.state.groupBy, secondary: event.target.id === 'secondary' ? event.target.value : props.state.secondary }
 if (patch.groupBy === patch.secondary) patch.secondary = ''
 if (['groupBy','secondary'].includes(event.target.id)) emit('change', patch)
 else if (event.target.id === 'measure') emit('change', {metric:event.target.value})
 else if (event.target.id === 'memberFilter') emit('change', {userId:event.target.value})
}
function click(event) {
 const row = event.target.closest('[data-group-detail]')
 if(row) { const selected=props.state.analysis?.rows?.[Number(row.dataset.groupDetail)]; if(selected)emit('drill',selected,null,{connectionId:props.state.connectionId,dataVersion:props.state.dataVersion,contextKey:props.state.contextKey}) }
 const page=event.target.closest('[data-page="analysis"]')
 if(page&&!page.disabled)emit('change',{analysisPage:Number(page.dataset.value)})
 if(event.target.closest('[data-clear-filters]'))emit('clear')
}
function keyboard(event) { if(['Enter',' '].includes(event.key)&&event.target.matches('[data-group-detail]')) { event.preventDefault();click(event) } }
</script>
