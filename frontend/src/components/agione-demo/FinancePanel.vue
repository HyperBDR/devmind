<template><div style="display:contents" v-html="html"></div></template>
<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import { dashboardFinance } from './dashboard-finance.mjs'
import { originalFinanceDTO, readonlyWorkspaceMarkup } from '@/utils/agioneOriginalWorkspace'
const { locale }=useI18n({useScope:'global'})
const props=defineProps({value:{type:Object,default:null},isLive:Boolean,provenance:{type:Object,default:null}})
const html=computed(()=>DOMPurify.sanitize(readonlyWorkspaceMarkup(dashboardFinance(originalFinanceDTO(props.value,props),{locale:locale.value}),{finance:props.value,isLive:props.isLive,provenance:props.provenance,locale:locale.value}),{USE_PROFILES:{html:true,svg:true}}))
</script>
