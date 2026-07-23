<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  Download,
  LockKeyhole,
  RefreshCw,
  Search,
  X,
} from 'lucide-vue-next'
import BaseDatePicker from '@/components/ui/BaseDatePicker.vue'

import {
  downloadAuditExport,
  listAuditEvents,
  type AuditEvent,
} from '../api/audit'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import FormSelect from './FormSelect.vue'
import SecurityAlertsPanel from './SecurityAlertsPanel.vue'

const { locale, t } = useQuotationI18n()
const events = ref<AuditEvent[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const exporting = ref(false)
const canExport = ref(false)
const selected = ref<AuditEvent | null>(null)
const activeTab = ref<'activity' | 'security'>('activity')
const securityAlertCount = ref(0)
const search = ref('')
const moduleFilter = ref('')
const actionFilter = ref('')
const resultFilter = ref('')
const riskFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const pageCount = computed(() => Math.max(Math.ceil(total.value / pageSize), 1))
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize + 1 : 0)
const rangeEnd = computed(() => Math.min(page.value * pageSize, total.value))

const moduleOptions = ['quotation', 'document', 'feishu', 'catalog']
const moduleAliases: Record<string, string> = {
  quote: 'quotation',
}
const actionOptions = [
  'create',
  'view',
  'update',
  'delete',
  'generate',
  'upload',
  'download',
  'sync',
  'import',
  'open',
  'connect',
]
const moduleFilterOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.allModules') },
  ...moduleOptions.map((value) => ({ value, label: moduleLabel(value) })),
])
const actionFilterOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.allActions') },
  ...actionOptions.map((value) => ({ value, label: actionLabel(value) })),
])
const resultFilterOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.allResults') },
  { value: 'succeeded', label: t('quotation.pages.audit.succeeded') },
  { value: 'denied', label: t('quotation.pages.audit.denied') },
  { value: 'failed', label: t('quotation.pages.audit.failed') },
])
const riskFilterOptions = computed(() => [
  { value: '', label: t('quotation.pages.audit.allRiskLevels') },
  ...['critical', 'high', 'medium', 'low'].map((value) => ({
    value,
    label: t(`quotation.pages.audit.riskLevels.${value}`),
  })),
])

async function loadEvents() {
  loading.value = true
  try {
    const response = await listAuditEvents({
      search: search.value.trim(),
      module: moduleFilter.value,
      action: actionFilter.value,
      result: resultFilter.value,
      riskLevel: riskFilter.value,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
      page: page.value,
      pageSize,
    })
    events.value = response.items
    total.value = response.total
    canExport.value = response.can_export
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  search.value = ''
  moduleFilter.value = ''
  actionFilter.value = ''
  resultFilter.value = ''
  riskFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  page.value = 1
  void loadEvents()
}

async function exportEvents() {
  if (exporting.value) return
  exporting.value = true
  try {
    await downloadAuditExport({
      search: search.value.trim(),
      module: moduleFilter.value,
      action: actionFilter.value,
      result: resultFilter.value,
      riskLevel: riskFilter.value,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
    })
  } finally {
    exporting.value = false
  }
}

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

function actorLabel(event: AuditEvent) {
  return event.actor_name || event.actor_email || t('quotation.pages.audit.system')
}

const targetFallbackByOperation: Record<string, string> = {
  'audit.view': 'auditLog',
  'audit.export': 'auditLog',
  'feishu.sync': 'archiveFolder',
  'feishu.connect': 'feishuAccount',
  'feishu.disconnect': 'feishuAccount',
  'feishu.refresh': 'feishuAccount',
}

const targetFallbackByType: Record<string, string> = {
  audit_log: 'auditLog',
  folder: 'archiveFolder',
  document: 'document',
  quotation: 'quotation',
  request: 'request',
  account: 'feishuAccount',
  catalog: 'catalog',
  storage_connection: 'storageConnection',
  storage_mount: 'storageMount',
  document_replica: 'documentReplica',
  security_alert: 'securityAlert',
}

function targetLabel(event: AuditEvent) {
  if (event.target_label || event.target_id) {
    return event.target_label || event.target_id
  }
  const operationKey = `${normalizedModule(event.module)}.${event.action}`
  const fallbackKey = targetFallbackByOperation[operationKey]
    || targetFallbackByType[event.target_type]
    || 'recordedOperation'
  return t(`quotation.pages.audit.targets.${fallbackKey}`)
}

function fallbackLabel(value: string) {
  const cleaned = value.replace(/[_-]+/g, ' ').trim()
  if (!cleaned) return t('quotation.pages.audit.notAvailable')
  return cleaned.replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function translatedLabel(key: string, fallback: string) {
  const label = t(key)
  return label === key ? fallback : label
}

function normalizedModule(value: string) {
  return moduleAliases[value] || value
}

function moduleLabel(value: string) {
  const key = normalizedModule(value)
  return translatedLabel(
    `quotation.pages.audit.modules.${key}`,
    fallbackLabel(value),
  )
}

function actionLabel(value: string, module = '') {
  const moduleKey = normalizedModule(module)
  if (value === 'view' && moduleKey === 'audit') {
    return t('quotation.pages.audit.actions.viewedAuditLog')
  }
  if (value === 'delete' && moduleKey === 'quotation') {
    return t('quotation.pages.audit.actions.deletedQuote')
  }
  if (value === 'delete' && moduleKey === 'document') {
    return t('quotation.pages.audit.actions.deletedFile')
  }
  if (value === 'update' && moduleKey === 'quotation') {
    return t('quotation.pages.audit.actions.updatedQuote')
  }
  if (moduleKey === 'catalog') {
    const catalogActions: Record<string, string> = {
      create: 'addedCatalogItem',
      update: 'updatedCatalogItem',
      delete: 'deletedCatalogItem',
    }
    const key = catalogActions[value]
    if (key) return t(`quotation.pages.audit.actions.${key}`)
  }
  return translatedLabel(
    `quotation.pages.audit.actions.${value}`,
    fallbackLabel(value),
  )
}

function targetTypeLabel(event: AuditEvent) {
  if (normalizedModule(event.module) !== 'catalog' || !event.target_type) return ''
  return translatedLabel(
    `quotation.pages.audit.catalogItemTypes.${event.target_type}`,
    fallbackLabel(event.target_type),
  )
}

watch([moduleFilter, actionFilter, resultFilter, riskFilter, dateFrom, dateTo], () => {
  page.value = 1
  void loadEvents()
})

watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void loadEvents()
  }, 300)
})

watch(page, () => void loadEvents())
onMounted(() => void loadEvents())
</script>

<template>
  <section class="space-y-5">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-dm-text">
          {{ t('quotation.pages.audit.title') }}
        </h1>
        <p class="mt-1 text-sm text-dm-text-tertiary">
          {{ t('quotation.pages.audit.subtitle') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button v-if="canExport" type="button" :disabled="exporting" class="dm-btn-default inline-flex h-10 items-center gap-2 px-4 text-sm" @click="exportEvents">
          <Download class="h-4 w-4" />
          {{ t('quotation.pages.audit.exportCsv') }}
        </button>
        <div class="flex items-center gap-2 rounded-dm border border-dm-border bg-white px-3 py-2 text-xs text-dm-text-secondary">
          <LockKeyhole class="h-3.5 w-3.5" />
          {{ t('quotation.pages.audit.readOnly') }}
        </div>
      </div>
    </div>

    <div class="flex gap-7 border-b border-dm-border-light">
      <button
        type="button"
        :class="activeTab === 'activity' ? 'border-dm-primary text-dm-text' : 'border-transparent text-dm-text-secondary'"
        class="border-b-2 px-0.5 pb-3 text-sm font-semibold"
        @click="activeTab = 'activity'"
      >
        {{ t('quotation.pages.audit.activityLog') }}
      </button>
      <button
        type="button"
        :class="activeTab === 'security' ? 'border-dm-primary text-dm-text' : 'border-transparent text-dm-text-secondary'"
        class="inline-flex items-center gap-2 border-b-2 px-0.5 pb-3 text-sm font-semibold"
        @click="activeTab = 'security'"
      >
        {{ t('quotation.pages.audit.securityAlerts') }}
        <span v-if="securityAlertCount" class="inline-flex min-w-5 items-center justify-center rounded-full bg-red-100 px-1.5 py-0.5 text-xs text-red-600">
          {{ securityAlertCount }}
        </span>
      </button>
    </div>

    <div v-if="activeTab === 'activity'" class="grid gap-3 rounded-xl border border-dm-border bg-white p-4 shadow-sm lg:grid-cols-3 min-[1360px]:grid-cols-[minmax(220px,1.4fr)_repeat(4,minmax(130px,.7fr))_minmax(230px,1fr)_auto]">
      <label class="relative">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
        <input
          v-model="search"
          type="search"
          :placeholder="t('quotation.pages.audit.searchPlaceholder')"
          class="h-10 w-full rounded-dm border border-dm-border bg-white pl-9 pr-3 text-sm outline-none focus:border-dm-primary"
        >
      </label>
      <FormSelect
        v-model="moduleFilter"
        class-name="w-full"
        :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
        :options="moduleFilterOptions"
      />
      <FormSelect
        v-model="actionFilter"
        class-name="w-full"
        :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
        :options="actionFilterOptions"
      />
      <FormSelect
        v-model="resultFilter"
        class-name="w-full"
        :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
        :options="resultFilterOptions"
      />
      <FormSelect
        v-model="riskFilter"
        class-name="w-full"
        :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
        :options="riskFilterOptions"
      />
      <div class="grid grid-cols-2 gap-2">
        <BaseDatePicker
          v-model="dateFrom"
          :placeholder="t('quotation.pages.audit.dateFrom')"
          input-class="h-10 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-2 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
        />
        <BaseDatePicker
          v-model="dateTo"
          :placeholder="t('quotation.pages.audit.dateTo')"
          input-class="h-10 w-full min-w-0 rounded-lg border border-dm-border-light bg-white px-3 py-2 text-sm text-dm-text transition placeholder:text-slate-400 focus:border-blue-300 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
        />
      </div>
      <button type="button" class="dm-btn-default inline-flex h-10 items-center justify-center gap-2 px-4 text-sm" @click="resetFilters">
        <RefreshCw class="h-4 w-4" />
        {{ t('quotation.common.reset') }}
      </button>
    </div>

    <div v-if="activeTab === 'activity'" class="overflow-hidden rounded-xl border border-dm-border bg-white shadow-sm">
      <div class="overflow-x-auto">
        <table class="min-w-[900px] w-full table-fixed text-left">
          <thead class="border-b border-dm-border bg-[#fafafa] text-xs font-semibold uppercase tracking-wide text-dm-text-tertiary">
            <tr>
              <th class="w-36 px-4 py-3">{{ t('quotation.pages.audit.time') }}</th>
              <th class="w-48 px-4 py-3">{{ t('quotation.pages.audit.performedBy') }}</th>
              <th class="w-28 px-4 py-3">{{ t('quotation.pages.audit.module') }}</th>
              <th class="w-40 px-4 py-3">{{ t('quotation.pages.audit.action') }}</th>
              <th class="px-4 py-3">{{ t('quotation.pages.audit.target') }}</th>
              <th class="w-28 px-4 py-3">{{ t('quotation.pages.audit.result') }}</th>
              <th class="w-16 px-4 py-3"><span class="sr-only">{{ t('quotation.pages.audit.viewDetails') }}</span></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-dm-border-light">
            <tr v-if="loading">
              <td colspan="7" class="px-4 py-14 text-center text-sm text-dm-text-tertiary">
                {{ t('quotation.pages.audit.loading') }}
              </td>
            </tr>
            <tr v-else-if="events.length === 0">
              <td colspan="7" class="px-4 py-14 text-center text-sm text-dm-text-tertiary">
                {{ t('quotation.pages.audit.empty') }}
              </td>
            </tr>
            <tr v-for="event in events" v-else :key="event.id" class="hover:bg-slate-50/70">
              <td class="px-4 py-4 text-sm text-dm-text-secondary">{{ formatDateTime(event.created_at) }}</td>
              <td class="px-4 py-4">
                <p class="truncate text-sm font-medium text-dm-text">{{ actorLabel(event) }}</p>
                <p class="truncate text-xs text-dm-text-tertiary">{{ event.actor_email }}</p>
              </td>
              <td class="px-4 py-4"><span class="inline-flex max-w-full truncate rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">{{ moduleLabel(event.module) }}</span></td>
              <td class="px-4 py-4 text-sm font-medium text-dm-text">{{ actionLabel(event.action, event.module) }}</td>
              <td class="truncate px-4 py-4 text-sm font-medium text-dm-primary" :title="targetLabel(event)">{{ targetLabel(event) }}</td>
              <td class="px-4 py-4">
                <span :class="event.result === 'succeeded' ? 'bg-emerald-50 text-emerald-700' : event.result === 'denied' ? 'bg-orange-50 text-orange-700' : 'bg-red-50 text-red-600'" class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold">
                  <span class="h-1.5 w-1.5 rounded-full bg-current" />
                  {{ t(`quotation.pages.audit.${event.result}`) }}
                </span>
              </td>
              <td class="px-4 py-4">
                <button type="button" :aria-label="t('quotation.pages.audit.viewDetails')" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border text-dm-text-secondary hover:border-dm-primary hover:text-dm-primary" @click="selected = event">
                  <ChevronRight class="h-4 w-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3 border-t border-dm-border-light px-4 py-3 text-xs text-dm-text-tertiary">
        <span>{{ t('quotation.pages.audit.showing', { from: rangeStart, to: rangeEnd, total }) }}</span>
        <div class="flex items-center gap-2">
          <button type="button" :disabled="page <= 1" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border disabled:cursor-not-allowed disabled:opacity-40" @click="page -= 1"><ChevronLeft class="h-4 w-4" /></button>
          <span>{{ t('quotation.pages.audit.page', { current: page, total: pageCount }) }}</span>
          <button type="button" :disabled="page >= pageCount" class="inline-flex h-8 w-8 items-center justify-center rounded-dm border border-dm-border disabled:cursor-not-allowed disabled:opacity-40" @click="page += 1"><ChevronRight class="h-4 w-4" /></button>
        </div>
      </div>
    </div>

    <SecurityAlertsPanel
      v-if="activeTab === 'security'"
      @count="securityAlertCount = $event"
    />
  </section>

  <div v-if="selected && activeTab === 'activity'" class="fixed inset-0 z-50 flex justify-end bg-slate-950/30" @click.self="selected = null">
    <aside class="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-2xl">
      <div class="flex items-start justify-between gap-4 border-b border-dm-border-light pb-4">
        <div><h2 class="text-lg font-semibold text-dm-text">{{ t('quotation.pages.audit.detailsTitle') }}</h2><p class="mt-1 text-sm text-dm-text-tertiary">{{ formatDateTime(selected.created_at) }}</p></div>
        <button type="button" :aria-label="t('quotation.common.close')" class="rounded-dm p-2 text-dm-text-tertiary hover:bg-slate-100" @click="selected = null"><X class="h-5 w-5" /></button>
      </div>
      <dl class="mt-5 grid grid-cols-[130px_1fr] gap-x-4 gap-y-4 text-sm">
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.performedBy') }}</dt><dd class="font-medium text-dm-text">{{ actorLabel(selected) }}<div class="font-normal text-dm-text-tertiary">{{ selected.actor_email }}</div></dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.module') }}</dt><dd>{{ moduleLabel(selected.module) }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.action') }}</dt><dd>{{ actionLabel(selected.action, selected.module) }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.target') }}</dt><dd class="break-all">{{ targetLabel(selected) }}</dd>
        <template v-if="targetTypeLabel(selected)">
          <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.itemType') }}</dt><dd>{{ targetTypeLabel(selected) }}</dd>
        </template>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.result') }}</dt><dd>{{ t(`quotation.pages.audit.${selected.result}`) }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.eventName') }}</dt><dd class="break-all font-mono text-xs">{{ selected.event_name }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.riskLevel') }}</dt><dd>{{ t(`quotation.pages.audit.riskLevels.${selected.risk_level}`) }}</dd>
        <template v-if="selected.reason_code">
          <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.reasonCode') }}</dt><dd class="break-all font-mono text-xs">{{ selected.reason_code }}</dd>
        </template>
        <template v-if="selected.changes.fields?.length">
          <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.changedFields') }}</dt><dd>{{ selected.changes.fields.join(', ') }}</dd>
        </template>
        <template v-if="selected.module === 'quotation' && selected.target_id && ['update', 'generate'].includes(selected.action)">
          <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.relatedVersion') }}</dt>
          <dd>
            <span v-if="selected.metadata.version_no !== undefined" class="mr-2">
              {{ t('quotation.pages.audit.versionValue', { version: selected.metadata.version_no }) }}
            </span>
            <RouterLink :to="`/quotation/details/${selected.target_id}`" class="font-medium text-dm-primary hover:underline" @click="selected = null">
              {{ t('quotation.pages.audit.viewVersionHistory') }}
            </RouterLink>
          </dd>
        </template>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.ipAddress') }}</dt><dd>{{ selected.ip_address || t('quotation.pages.audit.notAvailable') }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.requestId') }}</dt><dd class="break-all font-mono text-xs">{{ selected.request_id || t('quotation.pages.audit.notAvailable') }}</dd>
        <dt class="text-dm-text-tertiary">{{ t('quotation.pages.audit.traceId') }}</dt><dd class="break-all font-mono text-xs">{{ selected.trace_id || t('quotation.pages.audit.notAvailable') }}</dd>
      </dl>
      <div v-if="selected.summary" class="mt-6 rounded-dm border border-red-100 bg-red-50 p-4 text-sm text-red-700">{{ selected.summary }}</div>
    </aside>
  </div>
</template>
