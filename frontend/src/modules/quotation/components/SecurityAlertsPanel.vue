<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Diamond,
  Info,
  RefreshCw,
  Search,
  X,
} from 'lucide-vue-next'

import {
  getSecurityAlert,
  listSecurityAlerts,
  updateSecurityAlert,
  type SecurityAlert,
  type SecurityAlertSummary,
} from '../api/audit'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import FormSelect from './FormSelect.vue'

const emit = defineEmits<{ count: [value: number] }>()
const { locale, t } = useQuotationI18n()
const alerts = ref<SecurityAlert[]>([])
const summary = ref<SecurityAlertSummary>({
  open: 0,
  critical: 0,
  high: 0,
  new_last_24_hours: 0,
  immediate_review: 0,
  affected_users_last_24_hours: 0,
})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const canManage = ref(false)
const selected = ref<SecurityAlert | null>(null)
const resolveOpen = ref(false)
const errorMessage = ref('')
const search = ref('')
const severity = ref('')
const status = ref('')
const rule = ref('')
const days = ref('30')
const resolution = ref('authorized_activity')
const resolutionNote = ref('')
const notifyUser = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const pageCount = computed(() => Math.max(Math.ceil(total.value / pageSize), 1))
const rangeStart = computed(() =>
  total.value ? (page.value - 1) * pageSize + 1 : 0,
)
const rangeEnd = computed(() => Math.min(page.value * pageSize, total.value))
const selectClass = `${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`
const severityOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.security.allSeverities') },
  ...['critical', 'high', 'medium'].map((value) => ({
    value,
    label: t(`quotation.pages.audit.security.severities.${value}`),
  })),
])
const statusOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.security.allStatuses') },
  ...['open', 'acknowledged', 'resolved', 'false_positive'].map((value) => ({
    value,
    label: t(`quotation.pages.audit.security.statuses.${value}`),
  })),
])
const ruleOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.security.allRules') },
  ...[
    'repeated_access_denials',
    'unusual_bulk_downloads',
    'new_device_sensitive_action',
    'repeated_feishu_access_failures',
    'object_id_enumeration',
    'configuration_change',
    'credential_refresh_failure',
    'sync_failure_backlog',
  ].map((value) => ({
    value,
    label: t(`quotation.pages.audit.security.rules.${value}`),
  })),
])
const dateOptions = computed(() =>
  ['1', '7', '30', '90', 'all'].map((value) => ({
    value,
    label: t(`quotation.pages.audit.security.dateRanges.${value}`),
  })),
)
const resolutionOptions = computed(() =>
  [
    'authorized_activity',
    'policy_violation',
    'false_positive',
    'other',
  ].map((value) => ({
    value,
    label: t(`quotation.pages.audit.security.resolutions.${value}`),
  })),
)

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(
    locale.value.startsWith('zh') ? 'zh-CN' : 'en-US',
    {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    },
  ).format(date)
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(
    locale.value.startsWith('zh') ? 'zh-CN' : 'en-US',
    { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false },
  ).format(date)
}

function subjectLabel(alert: SecurityAlert) {
  return alert.subject_name || alert.subject_email || t('quotation.pages.audit.system')
}

function alertTitle(alert: SecurityAlert) {
  return t(`quotation.pages.audit.security.rules.${alert.rule}`)
}

function alertReason(alert: SecurityAlert) {
  return t(`quotation.pages.audit.security.reasons.${alert.rule}`, {
    count: alert.trigger_count,
  })
}

function alertRecommendation(alert: SecurityAlert) {
  return t(`quotation.pages.audit.security.recommendations.${alert.rule}`)
}

function evidenceLabel(event: NonNullable<SecurityAlert['evidence']>[number]) {
  const target = event.target_label || event.target_id
  const actionKey = `quotation.pages.audit.actions.${event.action}`
  return target ? `${t(actionKey)} ${target}` : t(actionKey)
}

function severityClass(value: string) {
  return {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    medium: 'bg-amber-100 text-amber-700',
  }[value] || 'bg-slate-100 text-slate-600'
}

function statusClass(value: string) {
  return {
    open: 'bg-red-50 text-red-700',
    acknowledged: 'bg-blue-50 text-blue-700',
    resolved: 'bg-emerald-50 text-emerald-700',
    false_positive: 'bg-slate-100 text-slate-600',
  }[value] || 'bg-slate-100 text-slate-600'
}

function metricIconClass(value: 'danger' | 'warning' | 'info') {
  return {
    danger: 'border-red-100 bg-white text-red-500',
    warning: 'border-orange-100 bg-white text-orange-500',
    info: 'border-blue-100 bg-white text-blue-500',
  }[value]
}

async function loadAlerts() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listSecurityAlerts({
      search: search.value.trim(),
      severity: severity.value,
      status: status.value,
      rule: rule.value,
      days: days.value,
      page: page.value,
      pageSize,
    })
    alerts.value = response.items
    summary.value = response.summary
    total.value = response.total
    canManage.value = response.can_manage
    emit('count', response.summary.open)
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('quotation.pages.audit.security.loadFailed')
  } finally {
    loading.value = false
  }
}

async function openDetails(alert: SecurityAlert) {
  selected.value = alert
  detailLoading.value = true
  errorMessage.value = ''
  try {
    const response = await getSecurityAlert(alert.id)
    selected.value = response.alert
    canManage.value = response.can_manage
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('quotation.pages.audit.security.loadFailed')
  } finally {
    detailLoading.value = false
  }
}

async function acknowledge() {
  if (!selected.value || saving.value) return
  saving.value = true
  try {
    const response = await updateSecurityAlert(selected.value.id, {
      action: 'acknowledge',
    })
    selected.value = response.alert
    await loadAlerts()
  } finally {
    saving.value = false
  }
}

function beginResolve() {
  resolution.value = 'authorized_activity'
  resolutionNote.value = ''
  notifyUser.value = false
  resolveOpen.value = true
}

async function resolveAlert() {
  if (!selected.value || !resolutionNote.value.trim() || saving.value) return
  saving.value = true
  try {
    const response = await updateSecurityAlert(selected.value.id, {
      action: 'resolve',
      resolution: resolution.value,
      resolution_note: resolutionNote.value.trim(),
      notify_affected_user: notifyUser.value,
    })
    selected.value = response.alert
    resolveOpen.value = false
    await loadAlerts()
  } finally {
    saving.value = false
  }
}

function resetFilters() {
  search.value = ''
  severity.value = ''
  status.value = ''
  rule.value = ''
  days.value = '30'
  page.value = 1
  void loadAlerts()
}

watch([severity, status, rule, days], () => {
  page.value = 1
  void loadAlerts()
})
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void loadAlerts()
  }, 300)
})
watch(page, () => void loadAlerts())
onMounted(() => void loadAlerts())
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <article class="flex items-center justify-between gap-4 rounded-xl border border-dm-border bg-white p-4 shadow-sm">
        <div class="min-w-0"><p class="text-xs font-semibold text-dm-text-secondary">{{ t('quotation.pages.audit.security.openAlerts') }}</p><p class="mt-1 text-3xl font-semibold text-dm-text">{{ summary.open }}</p><p class="mt-1 text-xs text-dm-text-tertiary">{{ t('quotation.pages.audit.security.immediateReview', { count: summary.immediate_review }) }}</p></div>
        <span :class="['inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border shadow-[0_1px_2px_rgba(15,23,42,0.04)]', metricIconClass('danger')]"><CircleAlert class="h-4 w-4" /></span>
      </article>
      <article class="flex items-center justify-between gap-4 rounded-xl border border-dm-border bg-white p-4 shadow-sm">
        <div class="min-w-0"><p class="text-xs font-semibold text-dm-text-secondary">{{ t('quotation.pages.audit.security.critical') }}</p><p class="mt-1 text-3xl font-semibold text-dm-text">{{ summary.critical }}</p><p class="mt-1 text-xs text-dm-text-tertiary">{{ t('quotation.pages.audit.security.criticalHint') }}</p></div>
        <span :class="['inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border shadow-[0_1px_2px_rgba(15,23,42,0.04)]', metricIconClass('danger')]"><Diamond class="h-4 w-4 fill-current" /></span>
      </article>
      <article class="flex items-center justify-between gap-4 rounded-xl border border-dm-border bg-white p-4 shadow-sm">
        <div class="min-w-0"><p class="text-xs font-semibold text-dm-text-secondary">{{ t('quotation.pages.audit.security.highSeverity') }}</p><p class="mt-1 text-3xl font-semibold text-dm-text">{{ summary.high }}</p><p class="mt-1 text-xs text-dm-text-tertiary">{{ t('quotation.pages.audit.security.highHint') }}</p></div>
        <span :class="['inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border shadow-[0_1px_2px_rgba(15,23,42,0.04)]', metricIconClass('warning')]"><AlertTriangle class="h-4 w-4" /></span>
      </article>
      <article class="flex items-center justify-between gap-4 rounded-xl border border-dm-border bg-white p-4 shadow-sm">
        <div class="min-w-0"><p class="text-xs font-semibold text-dm-text-secondary">{{ t('quotation.pages.audit.security.newLastDay') }}</p><p class="mt-1 text-3xl font-semibold text-dm-text">{{ summary.new_last_24_hours }}</p><p class="mt-1 text-xs text-dm-text-tertiary">{{ t('quotation.pages.audit.security.acrossUsers', { count: summary.affected_users_last_24_hours }) }}</p></div>
        <span :class="['inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border shadow-[0_1px_2px_rgba(15,23,42,0.04)]', metricIconClass('info')]"><Clock3 class="h-4 w-4" /></span>
      </article>
    </div>

    <div class="grid gap-3 rounded-xl border border-dm-border bg-white p-3 shadow-sm lg:grid-cols-2 min-[1360px]:grid-cols-[minmax(260px,1.5fr)_repeat(4,minmax(145px,.8fr))_auto]">
      <label class="relative">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
        <input v-model="search" type="search" :placeholder="t('quotation.pages.audit.security.searchPlaceholder')" class="h-10 w-full rounded-dm border border-dm-border bg-white pl-9 pr-3 text-sm outline-none focus:border-dm-primary">
      </label>
      <FormSelect v-model="severity" :options="severityOptions" :trigger-class-name="selectClass" />
      <FormSelect v-model="status" :options="statusOptions" :trigger-class-name="selectClass" />
      <FormSelect v-model="rule" :options="ruleOptions" :trigger-class-name="selectClass" />
      <FormSelect v-model="days" :options="dateOptions" :trigger-class-name="selectClass" />
      <button type="button" class="dm-btn-default inline-flex h-10 items-center justify-center gap-2 px-4 text-sm" @click="resetFilters"><RefreshCw class="h-4 w-4" />{{ t('quotation.common.reset') }}</button>
    </div>

    <p v-if="errorMessage" class="rounded-dm border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{{ errorMessage }}</p>

    <div class="overflow-hidden rounded-xl border border-dm-border bg-white shadow-sm">
      <div class="overflow-x-auto">
        <table class="min-w-[980px] w-full table-fixed text-left">
          <thead class="border-b border-dm-border bg-[#fafafa] text-xs font-semibold uppercase tracking-wide text-dm-text-tertiary">
            <tr><th class="w-36 px-4 py-3">{{ t('quotation.pages.audit.security.detectedAt') }}</th><th class="w-28 px-4 py-3">{{ t('quotation.pages.audit.security.severity') }}</th><th class="px-4 py-3">{{ t('quotation.pages.audit.security.alert') }}</th><th class="w-48 px-4 py-3">{{ t('quotation.pages.audit.security.userSource') }}</th><th class="w-28 px-4 py-3">{{ t('quotation.pages.audit.security.evidence') }}</th><th class="w-36 px-4 py-3">{{ t('quotation.pages.audit.security.status') }}</th><th class="w-16 px-4 py-3"><span class="sr-only">{{ t('quotation.pages.audit.viewDetails') }}</span></th></tr>
          </thead>
          <tbody class="divide-y divide-dm-border-light">
            <tr v-if="loading"><td colspan="7" class="px-4 py-14 text-center text-sm text-dm-text-tertiary">{{ t('quotation.pages.audit.security.loading') }}</td></tr>
            <tr v-else-if="alerts.length === 0"><td colspan="7" class="px-4 py-14 text-center text-sm text-dm-text-tertiary">{{ t('quotation.pages.audit.security.empty') }}</td></tr>
            <tr v-for="alert in alerts" v-else :key="alert.id" class="hover:bg-slate-50/70">
              <td class="px-4 py-4 text-sm text-dm-text-secondary">{{ formatDateTime(alert.first_detected_at) }}</td>
              <td class="px-4 py-4"><span :class="severityClass(alert.severity)" class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"><span class="h-1.5 w-1.5 rounded-full bg-current" />{{ t(`quotation.pages.audit.security.severities.${alert.severity}`) }}</span></td>
              <td class="px-4 py-4"><p class="font-semibold text-dm-text">{{ alertTitle(alert) }}</p><p class="mt-1 truncate text-xs text-dm-text-tertiary">{{ alertReason(alert) }}</p></td>
              <td class="px-4 py-4"><p class="truncate text-sm font-semibold text-dm-text">{{ subjectLabel(alert) }}</p><p class="truncate text-xs text-dm-text-tertiary">{{ alert.source_ip || t('quotation.pages.audit.notAvailable') }}</p></td>
              <td class="px-4 py-4 text-sm font-semibold text-blue-600">{{ t('quotation.pages.audit.security.eventCount', { count: alert.evidence_count }) }}</td>
              <td class="px-4 py-4"><span :class="statusClass(alert.status)" class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"><span class="h-1.5 w-1.5 rounded-full bg-current" />{{ t(`quotation.pages.audit.security.statuses.${alert.status}`) }}</span></td>
              <td class="px-4 py-4"><button type="button" :aria-label="t('quotation.pages.audit.viewDetails')" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border text-dm-text-secondary hover:border-dm-primary hover:text-dm-primary" @click="openDetails(alert)"><ChevronRight class="h-4 w-4" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3 border-t border-dm-border-light px-4 py-3 text-xs text-dm-text-tertiary"><span>{{ t('quotation.pages.audit.security.showing', { from: rangeStart, to: rangeEnd, total }) }}</span><div class="flex items-center gap-2"><button type="button" :disabled="page <= 1" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border disabled:opacity-40" @click="page -= 1"><ChevronLeft class="h-4 w-4" /></button><span>{{ t('quotation.pages.audit.page', { current: page, total: pageCount }) }}</span><button type="button" :disabled="page >= pageCount" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border disabled:opacity-40" @click="page += 1"><ChevronRight class="h-4 w-4" /></button></div></div>
    </div>
  </div>

  <div v-if="selected" class="fixed inset-x-0 bottom-0 top-12 z-50 flex justify-end bg-slate-950/30" @click.self="selected = null">
    <aside class="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
      <div class="border-b border-dm-border-light p-6"><div class="flex items-start justify-between gap-4"><div><span :class="severityClass(selected.severity)" class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold">{{ t(`quotation.pages.audit.security.severities.${selected.severity}`) }}</span><h2 class="mt-3 text-xl font-semibold text-dm-text">{{ alertTitle(selected) }}</h2><p class="mt-1 text-sm text-dm-text-tertiary">{{ selected.alert_number }} · {{ formatDateTime(selected.first_detected_at) }}</p></div><button type="button" :aria-label="t('quotation.common.close')" class="rounded-dm p-2 text-dm-text-tertiary hover:bg-slate-100" @click="selected = null"><X class="h-5 w-5" /></button></div></div>
      <div class="flex-1 space-y-4 overflow-y-auto p-5">
        <p v-if="detailLoading" class="py-10 text-center text-sm text-dm-text-tertiary">{{ t('quotation.pages.audit.security.loadingEvidence') }}</p>
        <template v-else>
          <section><h3 class="text-xs font-bold uppercase tracking-wide text-dm-text">{{ t('quotation.pages.audit.security.whyTriggered') }}</h3><p class="mt-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm leading-6 text-orange-800">{{ alertReason(selected) }}</p></section>
          <section><h3 class="text-xs font-bold uppercase tracking-wide text-dm-text">{{ t('quotation.pages.audit.security.context') }}</h3><dl class="mt-2 grid grid-cols-2 gap-2"><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.user') }}</dt><dd class="mt-1 text-sm font-semibold text-dm-text">{{ subjectLabel(selected) }}</dd></div><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.sourceIp') }}</dt><dd class="mt-1 text-sm font-semibold text-dm-text">{{ selected.source_ip || t('quotation.pages.audit.notAvailable') }}</dd></div><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.device') }}</dt><dd class="mt-1 text-sm font-semibold text-dm-text">{{ selected.device || t('quotation.pages.audit.security.deviceDetailsHidden') }}</dd></div><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.currentStatus') }}</dt><dd class="mt-1"><span :class="statusClass(selected.status)" class="inline-flex rounded-full px-2 py-0.5 text-xs font-semibold">{{ t(`quotation.pages.audit.security.statuses.${selected.status}`) }}</span></dd></div><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.owner') }}</dt><dd class="mt-1 text-sm font-semibold text-dm-text">{{ selected.owner || t('quotation.pages.audit.notAvailable') }}</dd></div><div class="rounded-lg border border-dm-border p-2"><dt class="text-[11px] uppercase text-dm-text-tertiary">{{ t('quotation.pages.audit.security.triggerPolicy') }}</dt><dd class="mt-1 text-sm font-semibold text-dm-text">{{ t('quotation.pages.audit.security.triggerPolicyValue', { threshold: selected.threshold, minutes: selected.window_minutes }) }}</dd></div></dl><a v-if="selected.runbook" :href="selected.runbook" target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex text-sm font-semibold text-blue-600 hover:underline">{{ t('quotation.pages.audit.security.runbook') }} →</a></section>
          <section><h3 class="text-xs font-bold uppercase tracking-wide text-dm-text">{{ t('quotation.pages.audit.security.evidenceTimeline', { count: selected.evidence_count }) }}</h3><ol class="mt-2 ml-2 border-l border-slate-300"><li v-for="event in selected.evidence?.slice(0, 3)" :key="event.id" class="relative pb-3 pl-5"><span class="absolute -left-2 top-0.5 h-4 w-4 rounded-full border-2 border-orange-500 bg-white" /><p class="text-xs text-dm-text-tertiary">{{ formatTime(event.created_at) }}</p><p class="mt-0.5 text-sm font-semibold text-dm-text">{{ evidenceLabel(event) }}</p><p class="text-xs text-dm-text-tertiary">{{ t('quotation.pages.audit.security.requestEvidence', { request: event.request_id || t('quotation.pages.audit.notAvailable'), ip: event.ip_address || t('quotation.pages.audit.notAvailable') }) }}</p></li></ol><p v-if="(selected.evidence?.length || 0) > 3" class="ml-7 text-sm font-semibold text-blue-600">{{ t('quotation.pages.audit.security.viewAllEvidence', { count: selected.evidence_count }) }}</p></section>
          <section><h3 class="text-xs font-bold uppercase tracking-wide text-dm-text">{{ t('quotation.pages.audit.security.recommendedAction') }}</h3><div class="mt-2 flex gap-3 rounded-lg bg-blue-50 p-3 text-sm leading-5 text-blue-700"><Info class="mt-0.5 h-4 w-4 shrink-0" /><p>{{ alertRecommendation(selected) }}</p></div></section>
          <section v-if="selected.resolution_note" class="rounded-lg border border-emerald-100 bg-emerald-50 p-4"><h3 class="text-xs font-bold uppercase tracking-wide text-emerald-800">{{ t('quotation.pages.audit.security.resolutionRecorded') }}</h3><p class="mt-2 text-sm text-emerald-800">{{ selected.resolution_note }}</p></section>
        </template>
      </div>
      <div v-if="canManage && ['open', 'acknowledged'].includes(selected.status)" class="flex justify-end gap-2 border-t border-dm-border-light p-4"><button v-if="selected.status === 'open'" type="button" :disabled="saving" class="dm-btn-default px-4 py-2 text-sm" @click="acknowledge">{{ t('quotation.pages.audit.security.acknowledge') }}</button><button type="button" :disabled="saving" class="dm-btn-primary px-4 py-2 text-sm" @click="beginResolve">{{ t('quotation.pages.audit.security.resolveAlert') }}</button></div>
    </aside>
  </div>

  <div v-if="resolveOpen && selected" class="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-4" @click.self="resolveOpen = false">
    <form class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl" @submit.prevent="resolveAlert"><h2 class="text-xl font-semibold text-dm-text">{{ t('quotation.pages.audit.security.resolveTitle') }}</h2><p class="mt-1 text-sm text-dm-text-secondary">{{ t('quotation.pages.audit.security.resolveSubtitle') }}</p><label class="mt-5 block"><span class="mb-2 block text-xs font-semibold text-dm-text">{{ t('quotation.pages.audit.security.resolution') }}</span><FormSelect v-model="resolution" :options="resolutionOptions" /></label><label class="mt-4 block"><span class="mb-2 block text-xs font-semibold text-dm-text">{{ t('quotation.pages.audit.security.resolutionNote') }}</span><textarea v-model="resolutionNote" rows="4" required :placeholder="t('quotation.pages.audit.security.resolutionNotePlaceholder')" class="w-full rounded-lg border border-dm-border p-3 text-sm outline-none focus:border-dm-primary" /></label><label class="mt-4 flex items-center gap-2 text-sm text-dm-text-secondary"><input v-model="notifyUser" type="checkbox" class="h-4 w-4 rounded border-dm-border text-dm-primary">{{ t('quotation.pages.audit.security.notifyUser') }}</label><div class="mt-6 flex justify-end gap-2"><button type="button" class="dm-btn-default px-4 py-2 text-sm" @click="resolveOpen = false">{{ t('quotation.common.cancel') }}</button><button type="submit" :disabled="!resolutionNote.trim() || saving" class="dm-btn-primary px-4 py-2 text-sm disabled:opacity-50">{{ t('quotation.pages.audit.security.resolveAlert') }}</button></div></form>
  </div>
</template>
