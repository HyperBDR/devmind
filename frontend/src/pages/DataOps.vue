<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div class="flex min-h-[calc(100vh-4rem)] bg-slate-50 text-slate-900">
      <DataOpsSidebar
        :active-section="activeSection"
        :nav-items="navItems"
        @select="selectSection"
      />

      <main class="min-w-0 flex-1 overflow-auto">
        <div class="mx-auto max-w-[1440px] space-y-6 p-4 sm:p-6">
          <DataOpsHeader
            :active-nav="activeNav"
            :can-manage-sync="canManageSync"
            :loading="loading"
            :preflight-loading="preflightLoading"
            :sync-loading="syncLoading"
            @full-sync="triggerFullSync"
            @preflight="runPreflight"
            @refresh="refreshCurrentSection"
          />

          <section
            v-if="error"
            class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
          >
            {{ error }}
          </section>

          <DataOpsSyncBanner
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
            :opportunities="opportunities"
            :risks="risks"
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

          <KanbanSection
            v-else-if="activeSection === 'kanban'"
            :contract-cards="contractCards"
            :settlement-cards="settlementCards"
          />

          <SyncSection
            v-else-if="activeSection === 'sync'"
            :columns="syncColumns"
            :recent-jobs="recentJobs"
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
              :permissions-text="permissionsText"
              @preflight="runConfigPreflight"
              @save="saveSyncConfig"
              @trigger="triggerConfigSync"
              @update-config-field="updateConfigField"
              @update-permissions="updatePermissions"
            />
          </template>

        </div>
      </main>

      <AiAssistantSection
        v-model:input="aiInput"
        :context="aiContext"
        :loading="aiLoading"
        :messages="aiMessages"
        @ask="askAiQuestion"
        @send="sendAiMessage"
        @stop="stopAiStream"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import AppLayout from '@/components/layout/AppLayout.vue'
import AiAssistantSection from '@/components/data-ops/AiAssistantSection.vue'
import CollectionConfigSection from '@/components/data-ops/CollectionConfigSection.vue'
import ContractsSection from '@/components/data-ops/ContractsSection.vue'
import DataOpsHeader from '@/components/data-ops/DataOpsHeader.vue'
import DataOpsSidebar from '@/components/data-ops/DataOpsSidebar.vue'
import DataOpsSyncBanner from '@/components/data-ops/DataOpsSyncBanner.vue'
import ExecutiveSection from '@/components/data-ops/ExecutiveSection.vue'
import GlobalConfigPanel from '@/components/data-ops/GlobalConfigPanel.vue'
import KanbanSection from '@/components/data-ops/KanbanSection.vue'
import PipelineSection from '@/components/data-ops/PipelineSection.vue'
import SalesRecordsSection from '@/components/data-ops/SalesRecordsSection.vue'
import SyncSection from '@/components/data-ops/SyncSection.vue'
import {
  formatAmount,
  formatDateTime,
  useDataOpsConsole,
} from '@/composables/useDataOpsConsole'
import { useUserStore } from '@/store/user'

const activeSection = ref('executive')
const userStore = useUserStore()
const {
  aiContext,
  aiInput,
  aiLoading,
  aiMessages,
  askAiQuestion,
  collectionConfigs,
  contractCards,
  contractFilterOptions,
  contractFilters,
  contractPage,
  contractTotal,
  contracts,
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
  pageSize,
  permissionsText,
  pipelineInsights,
  pipelineProjects,
  pipelineSummary,
  preflightLoading,
  recentJobs,
  refreshActive,
  risks,
  runConfigPreflight,
  runPreflight,
  salesFilters,
  salesPage,
  salesRecords,
  salesTotal,
  saveGlobalConfig,
  saveSyncConfig,
  sendAiMessage,
  setContractPage,
  setSalesPage,
  settlementCards,
  stopAiStream,
  syncBannerClass,
  syncBannerText,
  syncBannerTitle,
  syncLoading,
  syncTables,
  triggerConfigSync,
  triggerFullSync,
  triggerIncrementalSync,
  updateGlobalConfigField,
  updatePermissions,
} = useDataOpsConsole()

const canManageSync = computed(
  () =>
    userStore.userInfo?.is_staff === true ||
    userStore.userHasFeature('data_ops')
)

const allNavItems = [
  {
    key: 'executive',
    icon: 'E',
    label: '经营驾驶舱',
    description: '合同、回款、风险和机会的经营概览',
  },
  {
    key: 'pipeline',
    icon: 'P',
    label: 'Pipeline 看板',
    description: '国内立项、海外落地和续约风险',
  },
  {
    key: 'contracts',
    icon: 'C',
    label: '合同台账',
    description: '合同记录、筛选、分页和导出',
  },
  {
    key: 'sales',
    icon: 'S',
    label: '海外销售记录',
    description: 'KooGallery 订单和海外销售明细',
  },
  {
    key: 'kanban',
    icon: 'K',
    label: '看板视图',
    description: '按状态分组查看合同和海外结算',
  },
  {
    key: 'sync',
    icon: 'Y',
    label: '同步状态',
    description: '飞书采集任务、权限检查和同步问题',
  },
  {
    key: 'config',
    icon: 'G',
    label: '采集配置',
    description: '配置飞书多维表格 ID、权限、频率和手动触发',
  },
]

const frequencyOptions = [
  { value: 'manual', label: '手动' },
  { value: 'hourly', label: '每小时' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
]

const navItems = computed(() =>
  allNavItems.filter((item) => item.key !== 'config' || canManageSync.value)
)

const activeNav = computed(() =>
  navItems.value.find((item) => item.key === activeSection.value)
)

const contractColumns = [
  { key: 'contract_number', label: '合同编号' },
  { key: 'customer_name', label: '客户名称' },
  { key: 'signing_entity', label: '签约主体' },
  { key: 'sales_person', label: '负责人' },
  { key: 'region', label: '地区' },
  { key: 'total_amount', label: '金额', format: amountCell },
  { key: 'currency', label: '币种' },
  { key: 'signing_date', label: '签订日期' },
  { key: 'service_end', label: '服务到期' },
  { key: 'status', label: '状态' },
]

const salesColumns = [
  { key: 'project_name', label: '项目名称' },
  { key: 'po_number', label: 'PO#' },
  { key: 'region', label: '地区' },
  { key: 'product_type', label: '产品类型' },
  { key: 'total_amount_usd', label: '金额(USD)', format: amountCell },
  { key: 'allocation_date', label: '分配时间' },
  { key: 'expiry_date', label: '到期时间' },
  { key: 'order_type', label: '订单类型' },
  { key: 'status', label: '状态' },
  { key: 'sales_person', label: '负责人' },
]

const syncColumns = [
  { key: 'source_key', label: '数据源' },
  { key: 'table_key', label: '表 Key' },
  { key: 'table_name', label: '表名' },
  { key: 'status', label: '状态' },
  { key: 'issue_code', label: '问题' },
  { key: 'record_count', label: '记录数' },
  { key: 'message', label: '提示' },
  { key: 'last_checked_at', label: '最近检查', format: formatDateTime },
]

function amountCell(value) {
  return formatAmount(value)
}

function refreshCurrentSection() {
  refreshActive(activeSection.value, canManageSync.value)
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

function updateConfigField(config, key, value) {
  config[key] = value
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
