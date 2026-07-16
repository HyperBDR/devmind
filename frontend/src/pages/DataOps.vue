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

      <main class="min-h-0 min-w-0 flex-1 overflow-y-auto">
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
            :insights="insights"
            :kpi-cards="kpiCards"
            :overview="overview"
            :opportunities="opportunities"
            :risks="risks"
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
            @load="loadContracts"
            @page-change="setContractPage"
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
            @load="loadSalesRecords"
            @page-change="setSalesPage"
            @update-filter="updateSalesFilter"
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
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppLayout from '@/components/layout/AppLayout.vue'
import CollectionConfigSection from '@/components/data-ops/CollectionConfigSection.vue'
import ContractsSection from '@/components/data-ops/ContractsSection.vue'
import DataOpsHeader from '@/components/data-ops/DataOpsHeader.vue'
import DataOpsSidebar from '@/components/data-ops/DataOpsSidebar.vue'
import DataOpsSyncBanner from '@/components/data-ops/DataOpsSyncBanner.vue'
import ExecutiveSection from '@/components/data-ops/ExecutiveSection.vue'
import GlobalConfigPanel from '@/components/data-ops/GlobalConfigPanel.vue'
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

const activeSection = ref('executive')
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
  loadContracts,
  loadSalesRecords,
  loading,
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
  runPreflight,
  salesFilters,
  salesPage,
  salesRecords,
  salesTotal,
  saveGlobalConfig,
  setContractPage,
  setSalesPage,
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
  ['executive', 'pipeline', 'contracts', 'sales', 'sync', 'config'].map(
    (key) => ({
      key,
      icon: key.slice(0, 1).toUpperCase(),
      label: t(`dataOps.nav.items.${key}.label`),
      description: t(`dataOps.nav.items.${key}.description`)
    })
  )
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
      items: ['executive', 'pipeline', 'contracts', 'sales']
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
  if (canManageSync.value) {
    await refreshFromFeishu(activeSection.value, canManageSync.value)
    return
  }
  await refreshActive(activeSection.value, false)
}

async function handlePreflight() {
  const ok = await runPreflight()
  if (ok) {
    activeSection.value = 'sync'
  }
}

function selectSection(key) {
  if (key === 'config' && !canManageSync.value) {
    return
  }
  activeSection.value = key
  refreshActive(key, canManageSync.value)
}

function updateContractFilter(key, value) {
  contractFilters.value[key] = value
}

function updateSalesFilter(key, value) {
  salesFilters.value[key] = value
}

onMounted(() => loadAll(canManageSync.value))
</script>

<style>
.field-sm {
  height: 2.25rem;
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
