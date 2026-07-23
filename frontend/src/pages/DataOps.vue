<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div
      class="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900 lg:flex-row"
    >
      <DataOpsSidebar
        :active-section="activeSection"
        :nav-groups="navGroups"
        :nav-items="navItems"
        @select="selectSection"
      />

      <main
        ref="scrollContainer"
        class="min-h-0 min-w-0 flex-1 overflow-y-auto"
      >
        <div class="mx-auto max-w-[1440px] space-y-6 p-4 sm:p-6">
          <DataOpsHeader
            :active-nav="activeNav"
            :can-manage-sync="canManageSync"
            :loading="loading"
            :preflight-loading="preflightLoading"
            :sync-loading="syncLoading"
            @full-sync="triggerFullSync"
            @preflight="handlePreflight"
            @refresh="refreshCurrentSection"
          />

          <SyncFailureDetails v-if="syncFailure" :failure="syncFailure" />

          <section
            v-else-if="error"
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
          >
            {{ error }}
          </section>

          <section
            v-if="preflightFeedback"
            class="rounded-lg border px-4 py-3 text-sm"
            :class="preflightFeedbackClass"
          >
            {{ preflightFeedback }}
          </section>

          <section
            v-if="refreshFeedback"
            class="rounded-lg border px-4 py-3 text-sm"
            :class="refreshFeedbackClass"
            role="status"
          >
            {{ refreshFeedback }}
          </section>

          <DataOpsSyncBanner
            v-if="activeSection === 'sync' || activeSection === 'config'"
            :banner-class="syncBannerClass"
            :can-manage-sync="canManageSync"
            :sync-loading="syncLoading"
            :text="syncBannerText"
            :title="syncBannerTitle"
            @incremental-sync="triggerIncrementalSync"
          />

          <ExecutiveSection
            v-if="activeSection === 'executive'"
            :data-quality="dataQuality"
            :insights="insights"
            :kpi-cards="kpiCards"
            :overview="overview"
            :opportunities="opportunities"
            :risks="risks"
            :recent-jobs="recentJobs"
            :summary="summary"
            :top-customers="topCustomers"
            :top-sales="topSales"
            :trends="trends"
          />

          <PipelineSection
            v-else-if="activeSection === 'pipeline'"
            :insights="pipelineInsights"
            :projects="pipelineProjects"
            :summary="pipelineSummary"
          />

          <ContractsSection
            v-else-if="activeSection === 'contracts'"
            :columns="contractColumns"
            :can-export="canManageSync"
            :contracts="contracts"
            :filter-options="contractFilterOptions"
            :filters="contractFilters"
            :page="contractPage"
            :page-size="pageSize"
            :total="contractTotal"
            @download="downloadContracts"
            @load="handleContractLoad"
            @page-change="handleContractPageChange"
            @update-filter="updateContractFilter"
          />

          <SalesRecordsSection
            v-else-if="activeSection === 'sales'"
            :columns="salesColumns"
            :can-export="canManageSync"
            :filters="salesFilters"
            :page="salesPage"
            :page-size="pageSize"
            :records="salesRecords"
            :total="salesTotal"
            @download="downloadSales"
            @load="handleSalesLoad"
            @page-change="handleSalesPageChange"
            @update-filter="updateSalesFilter"
          />

          <ObservationSection
            v-else-if="activeSection === 'observations'"
            :can-run="canManageSync"
            :detail-loading="observationDetailLoading"
            :error="observationError"
            :feedback="observationFeedback"
            :filters="observationFilters"
            :observations="observations"
            :page="observationPage"
            :page-size="pageSize"
            :production="observationProduction"
            :run-loading="observationRunLoading"
            :selected-observation="selectedObservation"
            :total="observationTotal"
            @load="handleObservationLoad"
            @page-change="handleObservationPageChange"
            @run="runObservationProducer"
            @select="selectObservation"
            @update-filter="updateObservationFilter"
          />

          <SyncSection
            v-else-if="activeSection === 'sync'"
            :columns="syncColumns"
            :data-quality="dataQuality"
            :recent-jobs="recentJobs"
            :summary="summary"
            :tables="syncTables"
          />

          <template v-else-if="activeSection === 'config'">
            <GlobalConfigPanel
              :config="globalConfig"
              @save="saveGlobalConfig"
              @update-field="updateGlobalConfigField"
            />

            <CollectionConfigSection
              :configs="collectionConfigs"
              :frequency-options="frequencyOptions"
              @preflight="runConfigPreflight"
              @trigger="triggerConfigSync"
            />
          </template>
        </div>
      </main>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import AppLayout from '@/components/layout/AppLayout.vue'
import CollectionConfigSection from '@/components/data-ops/CollectionConfigSection.vue'
import ContractsSection from '@/components/data-ops/ContractsSection.vue'
import DataOpsHeader from '@/components/data-ops/DataOpsHeader.vue'
import DataOpsSidebar from '@/components/data-ops/DataOpsSidebar.vue'
import DataOpsSyncBanner from '@/components/data-ops/DataOpsSyncBanner.vue'
import ExecutiveSection from '@/components/data-ops/ExecutiveSection.vue'
import GlobalConfigPanel from '@/components/data-ops/GlobalConfigPanel.vue'
import ObservationSection from '@/components/data-ops/ObservationSection.vue'
import PipelineSection from '@/components/data-ops/PipelineSection.vue'
import SalesRecordsSection from '@/components/data-ops/SalesRecordsSection.vue'
import SyncFailureDetails from '@/components/data-ops/SyncFailureDetails.vue'
import SyncSection from '@/components/data-ops/SyncSection.vue'
import {
  formatAmount,
  formatDateTime,
  useDataOpsConsole
} from '@/composables/useDataOpsConsole'
import { useUserStore } from '@/store/user'
import {
  dataOpsSectionPath,
  resolveDataOpsSection
} from '@/utils/dataOpsNavigation'

const route = useRoute()
const router = useRouter()
const scrollContainer = ref(null)
const originalDocumentTitle = document.title
const activeSection = computed(() =>
  resolveDataOpsSection(route.params.section)
)
const userStore = useUserStore()
const { locale, t } = useI18n()
const {
  collectionConfigs,
  contractFilterOptions,
  contractFilters,
  contractPage,
  contractTotal,
  contracts,
  dataQuality,
  downloadContracts,
  downloadSales,
  error,
  globalConfig,
  insights,
  kpiCards,
  loadAll,
  loading,
  observationDetailLoading,
  observationError,
  observationFeedback,
  observationFilters,
  observationPage,
  observationProduction,
  observationRunLoading,
  observations,
  observationTotal,
  opportunities,
  overview,
  pageSize,
  preflightFeedback,
  preflightFeedbackClass,
  pipelineInsights,
  pipelineProjects,
  pipelineSummary,
  preflightLoading,
  recentJobs,
  refreshFeedback,
  refreshFeedbackClass,
  refreshActive,
  refreshFromFeishu,
  risks,
  runConfigPreflight,
  runObservationProducer,
  runPreflight,
  salesFilters,
  salesPage,
  salesRecords,
  salesTotal,
  saveGlobalConfig,
  selectObservation,
  selectedObservation,
  summary,
  syncBannerClass,
  syncBannerText,
  syncBannerTitle,
  syncFailure,
  syncLoading,
  topCustomers,
  topSales,
  trends,
  syncTables,
  triggerConfigSync,
  triggerFullSync,
  triggerIncrementalSync,
  updateGlobalConfigField
} = useDataOpsConsole()

const canManageSync = computed(
  () =>
    userStore.userInfo?.is_staff === true ||
    userStore.userHasFeature('data_ops')
)

const allNavItems = computed(() =>
  [
    'executive',
    'pipeline',
    'contracts',
    'sales',
    'observations',
    'sync',
    'config'
  ].map((key) => ({
    key,
    icon: key.slice(0, 1).toUpperCase(),
    label: t(`dataOps.nav.items.${key}.label`),
    description: t(`dataOps.nav.items.${key}.description`)
  }))
)

const frequencyOptions = computed(() =>
  ['manual', 'hourly', 'daily', 'weekly'].map((value) => ({
    value,
    label: t(`dataOps.common.${value}`)
  }))
)

const navItems = computed(() =>
  allNavItems.value.filter(
    (item) => item.key !== 'config' || canManageSync.value
  )
)

const navGroups = computed(() => {
  const grouped = [
    {
      key: 'business',
      label: t('dataOps.nav.groups.business'),
      items: ['executive', 'pipeline', 'contracts', 'sales', 'observations']
    },
    {
      key: 'global-config',
      label: t('dataOps.nav.groups.global'),
      items: ['sync', 'config']
    }
  ]
  const visibleItems = new Map(navItems.value.map((item) => [item.key, item]))
  return grouped
    .map((group) => ({
      ...group,
      items: group.items.map((key) => visibleItems.get(key)).filter(Boolean)
    }))
    .filter((group) => group.items.length)
})

const activeNav = computed(() =>
  normalizeActiveNav(
    navItems.value.find((item) => item.key === activeSection.value)
  )
)

watch(
  () => activeNav.value?.label,
  (label) => {
    document.title = label ? `${label} · Tower` : 'Tower'
  },
  { immediate: true }
)

const contractColumns = computed(() => [
  { key: 'contract_number', label: t('dataOps.columns.contractNumber') },
  { key: 'customer_name', label: t('dataOps.columns.customerName') },
  { key: 'signing_entity', label: t('dataOps.columns.signingEntity') },
  { key: 'sales_person', label: t('dataOps.columns.owner') },
  { key: 'region', label: t('dataOps.columns.region') },
  {
    key: 'total_amount',
    label: t('dataOps.columns.amount'),
    format: amountCell
  },
  { key: 'currency', label: t('dataOps.columns.currency') },
  { key: 'signing_date', label: t('dataOps.columns.signingDate') },
  { key: 'service_end', label: t('dataOps.columns.serviceEnd') },
  { key: 'status', label: t('dataOps.columns.status') }
])

const salesColumns = computed(() => [
  { key: 'project_name', label: t('dataOps.columns.projectName') },
  { key: 'po_number', label: 'PO#' },
  { key: 'region', label: t('dataOps.columns.region') },
  { key: 'product_type', label: t('dataOps.columns.productType') },
  {
    key: 'total_amount_usd',
    label: `${t('dataOps.columns.amount')} (USD)`,
    format: amountCell
  },
  { key: 'allocation_date', label: t('dataOps.columns.allocationDate') },
  { key: 'expiry_date', label: t('dataOps.columns.expiryDate') },
  { key: 'order_type', label: t('dataOps.columns.orderType') },
  { key: 'status', label: t('dataOps.columns.status') },
  { key: 'sales_person', label: t('dataOps.columns.owner') }
])

const syncColumns = computed(() => [
  { key: 'source_key', label: t('dataOps.columns.source') },
  { key: 'table_key', label: t('dataOps.columns.tableKey') },
  { key: 'table_name', label: t('dataOps.columns.tableName') },
  { key: 'status', label: t('dataOps.columns.status') },
  { key: 'issue_code', label: t('dataOps.columns.issue') },
  { key: 'record_count', label: t('dataOps.columns.records') },
  { key: 'message', label: t('dataOps.columns.message') },
  {
    key: 'last_checked_at',
    label: t('dataOps.columns.lastChecked'),
    format: (value) => formatDateTime(value, locale.value)
  }
])

function amountCell(value) {
  return formatAmount(value, '', { locale: locale.value })
}

function normalizeActiveNav(item) {
  if (!item || item.key !== 'executive') {
    return item
  }
  const month = overview.value?.meta?.current_month || '—'
  return {
    ...item,
    currentMonth: month,
    note: t('dataOps.header.currencyNote'),
    description: `${t('dataOps.header.dataMonth', { month })}  ${t(
      'dataOps.header.currencyNote'
    )}`
  }
}

async function refreshCurrentSection() {
  if (activeSection.value === 'observations') {
    await refreshActive(activeSection.value, canManageSync.value)
    return
  }
  if (canManageSync.value) {
    await refreshFromFeishu(activeSection.value, canManageSync.value)
    return
  }
  await refreshActive(activeSection.value, false)
}

async function handlePreflight() {
  const ok = await runPreflight()
  if (ok) {
    selectSection('sync')
  }
}

function selectSection(key) {
  if (key === 'config' && !canManageSync.value) {
    return
  }
  router.push(dataOpsSectionPath(key))
}

function updateContractFilter(key, value) {
  contractFilters.value[key] = value
}

function updateSalesFilter(key, value) {
  salesFilters.value[key] = value
}

function updateObservationFilter(key, value) {
  observationFilters.value[key] = value
}

function handleObservationLoad() {
  observationPage.value = 1
  commitSectionQuery('observations')
}

function handleContractLoad() {
  contractPage.value = 1
  commitSectionQuery('contracts')
}

function handleSalesLoad() {
  salesPage.value = 1
  commitSectionQuery('sales')
}

function handleContractPageChange(page) {
  contractPage.value = page
  commitSectionQuery('contracts')
}

function handleSalesPageChange(page) {
  salesPage.value = page
  commitSectionQuery('sales')
}

function handleObservationPageChange(page) {
  observationPage.value = page
  commitSectionQuery('observations')
}

function sectionQuery(section) {
  if (section === 'contracts') {
    return compactQuery({
      ...contractFilters.value,
      page: contractPage.value > 1 ? contractPage.value : ''
    })
  }
  if (section === 'sales') {
    return compactQuery({
      ...salesFilters.value,
      page: salesPage.value > 1 ? salesPage.value : ''
    })
  }
  if (section === 'observations') {
    return compactQuery({
      ...observationFilters.value,
      status:
        observationFilters.value.status === 'active'
          ? ''
          : observationFilters.value.status,
      page: observationPage.value > 1 ? observationPage.value : ''
    })
  }
  return {}
}

async function commitSectionQuery(section) {
  const query = sectionQuery(section)
  if (sameQuery(route.query, query)) {
    await refreshActive(section, canManageSync.value)
    return
  }
  await router.replace({ path: dataOpsSectionPath(section), query })
}

function hydrateSectionQuery(section) {
  const query = route.query
  if (section === 'contracts') {
    Object.assign(contractFilters.value, {
      customer_name: queryValue(query.customer_name),
      signing_entity: queryValue(query.signing_entity),
      sales_person: queryValue(query.sales_person),
      status: queryValue(query.status)
    })
    contractPage.value = queryPage(query.page)
  } else if (section === 'sales') {
    Object.assign(salesFilters.value, {
      status: queryValue(query.status),
      region: queryValue(query.region),
      product_type: queryValue(query.product_type)
    })
    salesPage.value = queryPage(query.page)
  } else if (section === 'observations') {
    Object.assign(observationFilters.value, {
      observation_type: queryValue(query.observation_type),
      severity: queryValue(query.severity),
      status: queryValue(query.status) || 'active'
    })
    observationPage.value = queryPage(query.page)
  }
}

function compactQuery(values) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== '' && value != null)
  )
}

function queryValue(value) {
  return Array.isArray(value) ? String(value[0] || '') : String(value || '')
}

function queryPage(value) {
  const page = Number(queryValue(value))
  return Number.isInteger(page) && page > 0 ? page : 1
}

function sameQuery(left, right) {
  const normalize = (value) =>
    JSON.stringify(
      Object.entries(value)
        .map(([key, item]) => [key, queryValue(item)])
        .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
    )
  return normalize(left) === normalize(right)
}

let routeReady = false

watch(
  () => route.fullPath,
  async () => {
    if (!routeReady) return
    hydrateSectionQuery(activeSection.value)
    await nextTick()
    scrollContainer.value?.scrollTo({ top: 0 })
    await refreshActive(activeSection.value, canManageSync.value)
  }
)

onMounted(async () => {
  hydrateSectionQuery(activeSection.value)
  await loadAll(canManageSync.value)
  routeReady = true
})

onBeforeUnmount(() => {
  document.title = originalDocumentTitle
})
</script>

<style>
.field-sm {
  height: 2.75rem;
  border-radius: 0.5rem;
  border: 1px solid rgb(226 232 240);
  background: white;
  padding: 0 0.75rem;
  font-size: 0.75rem;
  outline: none;
}

.field-sm:focus {
  border-color: rgb(165 180 252);
}

.btn-primary,
.btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  padding: 0 0.75rem;
  font-weight: 600;
}

.btn-primary {
  background: rgb(15 23 42);
  color: white;
}

.btn-secondary {
  border: 1px solid rgb(226 232 240);
  background: white;
  color: rgb(51 65 85);
}

.btn-secondary:hover {
  background: rgb(248 250 252);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 700;
}

.pager-btn {
  border-radius: 0.375rem;
  padding: 0.25rem 0.5rem;
  font-weight: 600;
}

.pager-btn:hover:not(:disabled) {
  background: rgb(241 245 249);
}

.pager-btn:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}
</style>
