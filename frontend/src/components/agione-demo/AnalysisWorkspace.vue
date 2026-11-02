<template><div ref="host" data-testid="agione-analysis" @click="click" @change="change" @keydown="keyboard"></div></template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { originalWorkspaceState } from '@/utils/agioneOriginalWorkspace'
import { csvDocument } from './core.mjs'
import { renderOriginalWorkspace } from './original-workspace-renderers.mjs'
import { enhanceSelects, closeSelectMenus } from './select-menu.mjs'
import { updateWorkspaceDom } from './workspace-dom.js'
const { locale } = useI18n({ useScope: 'global' })
const props = defineProps({ state: { type: Object, required: true }, exportRows: { type: Function, required: true } })
const emit = defineEmits(['change', 'drill', 'clear'])
const host = ref(null)
const html = computed(() => DOMPurify.sanitize(renderOriginalWorkspace(originalWorkspaceState(props.state), 'aggregate', {locale:locale.value}), { USE_PROFILES: { html: true, svg: true, svgFilters: true } }))
watch([host, html], ([element, markup]) => {
 if(element) updateWorkspaceDom(element, markup, target =>
   enhanceSelects(target, { restoreFocus: target.isConnected }))
}, { immediate: true, flush: 'post' })
watch(() => props.state.stale, async stale => {
 if (!stale) { await nextTick(); if (host.value) enhanceSelects(host.value) }
})
onBeforeUnmount(() => closeSelectMenus(host.value))
function change(event) {
 const patch = { groupBy: event.target.id === 'groupBy' ? event.target.value : props.state.groupBy, secondary: event.target.id === 'secondary' ? event.target.value : props.state.secondary }
 if (patch.groupBy === patch.secondary) patch.secondary = ''
 if (['groupBy','secondary'].includes(event.target.id)) emit('change', patch)
 else if (event.target.id === 'measure') emit('change', {metric:event.target.value})
 else if (event.target.id === 'memberFilter') emit('change', {userId:event.target.value})
}
async function exportAnalysis() {
 try {
  const rows = await props.exportRows()
  const groups = [...new Set(rows.flatMap(row => Object.keys(row.groupKey || {})))]
  const keys = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))]
  const csv = csvDocument(['分组', ...groups, ...keys], rows.map(row => [
   row.label, ...groups.map(key => row.groupKey?.[key]),
   ...keys.map(key => row.metrics?.[key])
  ]))
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'agione-aggregate.csv'
  link.click()
  URL.revokeObjectURL(url)
 } catch (error) { window.alert(error.message || '导出失败，请重试') }
}
function click(event) {
 if(event.target.closest('[data-export-analysis]')) void exportAnalysis()
 const row = event.target.closest('[data-group-detail]')
 if(row) { const selected=props.state.analysis?.rows?.[Number(row.dataset.groupDetail)]; if(selected)emit('drill',selected,null,{connectionId:props.state.connectionId,dataVersion:props.state.dataVersion,contextKey:props.state.contextKey}) }
 const page=event.target.closest('[data-page="analysis"]')
 if(page&&!page.disabled)emit('change',{analysisPage:Number(page.dataset.value)})
 if(event.target.closest('[data-clear-filters]'))emit('clear')
}
function keyboard(event) { if(['Enter',' '].includes(event.key)&&event.target.matches('[data-group-detail]')) { event.preventDefault();click(event) } }
</script>
