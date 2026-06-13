<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div class="h-full min-h-[calc(100vh-4rem)] bg-slate-50">
      <div class="flex h-full min-h-[calc(100vh-4rem)] w-full gap-0">
        <aside
          class="hidden w-72 shrink-0 overflow-hidden bg-slate-950 text-white shadow-sm lg:block"
        >
          <div class="border-b border-slate-800 px-5 py-5">
            <p
              class="text-[11px] font-bold uppercase tracking-[0.18em] text-agione-300"
            >
              LLM OPS
            </p>
            <h1 class="mt-2 text-lg font-semibold">大模型运营管理</h1>
            <p class="mt-2 text-xs leading-5 text-slate-400">
              价格、渠道、转售与对账的独立运营视图
            </p>
          </div>

          <nav class="space-y-1 px-3 py-4">
            <button
              v-for="item in navItems"
              :key="item.key"
              type="button"
              class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition"
              :class="
                activeSection === item.key
                  ? 'bg-agione-600 text-white shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-white'
              "
              @click="activeSection = item.key"
            >
              <span class="nav-icon">{{ item.icon }}</span>
              <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
              <span
                v-if="item.badge"
                class="rounded-full border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[10px] text-slate-300"
              >
                {{ item.badge }}
              </span>
            </button>
          </nav>

          <div
            class="border-t border-slate-800 px-5 py-4 text-xs text-slate-500"
          >
            <p>默认平台：Agione</p>
            <p class="mt-1">
              模型价格源：{{ providerCollectionSources.length }}
            </p>
          </div>
        </aside>

        <main
          class="min-w-0 flex-1 overflow-y-auto border-l border-slate-200 bg-white shadow-sm"
        >
          <header class="border-b border-slate-200 px-5 py-4 lg:px-7">
            <div
              class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between"
            >
              <div>
                <div class="flex flex-wrap gap-2 lg:hidden">
                  <button
                    v-for="item in navItems"
                    :key="item.key"
                    type="button"
                    class="rounded-lg px-3 py-2 text-xs font-semibold"
                    :class="
                      activeSection === item.key
                        ? 'bg-agione-600 text-white'
                        : 'bg-slate-100 text-slate-600'
                    "
                    @click="activeSection = item.key"
                  >
                    {{ item.label }}
                  </button>
                </div>
                <p
                  class="mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-agione-600 lg:mt-0"
                >
                  {{ activeNav.eyebrow }}
                </p>
                <h2 class="mt-2 text-2xl font-semibold text-slate-900">
                  {{ activeNav.label }}
                </h2>
                <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  {{ activeNav.description }}
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <div v-if="showPlatformControl" class="currency-control">
                  <span>挂售平台</span>
                  <CompactSelect
                    v-model="selectedResalePlatformId"
                    :options="resalePlatformOptions"
                    class-name="w-40"
                    size="sm"
                  />
                </div>
                <button
                  v-if="showPlatformControl"
                  type="button"
                  class="btn-secondary"
                  @click="openPlatformModal(agionePlatform)"
                >
                  平台配置
                </button>
                <button
                  v-if="showPlatformControl"
                  type="button"
                  class="btn-secondary"
                  @click="openPlatformModal(null)"
                >
                  新增平台
                </button>
                <div class="currency-control">
                  <span>显示货币</span>
                  <CompactSelect
                    v-model="displayCurrency"
                    :options="displayCurrencyOptions"
                    class-name="w-32"
                    size="sm"
                  />
                </div>
                <span
                  v-if="exchangeRateLabel"
                  class="rounded-[12px] border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500"
                >
                  {{ exchangeRateLabel }}
                </span>
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="loading"
                  @click="refreshAll"
                >
                  <span class="icon-mark" />
                  刷新
                </button>
              </div>
            </div>
          </header>

          <BaseLoading v-if="loading" class="py-20" />
          <div v-else class="space-y-6 px-5 py-5 lg:px-7">
            <section v-if="activeSection === 'monitor'" class="space-y-6">
              <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <div
                  v-for="item in kpiCards"
                  :key="item.label"
                  class="kpi-card"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <p class="text-xs font-medium text-slate-500">
                        {{ item.label }}
                      </p>
                      <p class="mt-2 text-2xl font-semibold text-slate-900">
                        {{ item.value }}
                      </p>
                    </div>
                    <span :class="['kpi-tone', item.tone]">
                      {{ item.badge }}
                    </span>
                  </div>
                  <div
                    class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200"
                  >
                    <div
                      class="h-full rounded-full"
                      :class="item.barClass"
                      :style="{ width: `${item.progress}%` }"
                    />
                  </div>
                  <p class="mt-2 text-xs text-slate-500">
                    {{ item.hint }}
                  </p>
                </div>
              </div>

              <div
                class="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
              >
                <div class="panel space-y-4">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p
                        class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
                      >
                        Action Queue
                      </p>
                      <h3 class="mt-2 text-lg font-semibold text-slate-900">
                        今日优先处理
                      </h3>
                    </div>
                    <button
                      type="button"
                      class="btn-secondary"
                      @click="activeSection = 'reseller'"
                    >
                      去挂售
                    </button>
                  </div>
                  <div class="space-y-3">
                    <button
                      v-for="item in actionItems"
                      :key="item.label"
                      type="button"
                      class="action-row"
                      @click="activeSection = item.section"
                    >
                      <span :class="['action-dot', item.tone]" />
                      <span class="min-w-0 flex-1">
                        <span class="block text-sm font-medium text-slate-900">
                          {{ item.label }}
                        </span>
                        <span class="mt-1 block text-xs text-slate-500">
                          {{ item.hint }}
                        </span>
                      </span>
                      <span
                        class="font-mono text-lg font-semibold text-slate-900"
                      >
                        {{ item.value }}
                      </span>
                    </button>
                  </div>
                </div>

                <div class="panel space-y-4">
                  <div
                    class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p
                        class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
                      >
                        Channel Coverage
                      </p>
                      <h3 class="mt-2 text-lg font-semibold text-slate-900">
                        渠道覆盖与最低价命中
                      </h3>
                    </div>
                    <span class="text-sm text-slate-500">
                      {{ channels.length }} 个渠道
                    </span>
                  </div>
                  <div class="space-y-3">
                    <div
                      v-for="channel in channelCoverageRows"
                      :key="channel.id"
                      class="coverage-row"
                    >
                      <div class="flex items-center justify-between gap-4">
                        <div class="min-w-0">
                          <p
                            class="truncate text-sm font-medium text-slate-900"
                          >
                            {{ channel.name }}
                          </p>
                          <p class="mt-1 text-xs text-slate-500">
                            覆盖 {{ channel.covered }} 个模型 · 最低价命中
                            {{ channel.best_count }} 个
                          </p>
                        </div>
                        <span class="font-mono text-sm text-slate-700">
                          {{ channel.coverage_rate }}%
                        </span>
                      </div>
                      <div
                        class="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
                      >
                        <div
                          class="h-full rounded-full bg-agione-500"
                          :style="{ width: `${channel.coverage_rate}%` }"
                        />
                      </div>
                    </div>
                    <div
                      v-if="!channelCoverageRows.length"
                      class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500"
                    >
                      暂无渠道覆盖数据。
                    </div>
                  </div>
                </div>
              </div>

              <div class="panel space-y-4">
                <div
                  class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p
                      class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
                    >
                      Provider Matrix
                    </p>
                    <h3 class="mt-2 text-lg font-semibold text-slate-900">
                      厂商模型运营覆盖
                    </h3>
                  </div>
                  <button
                    type="button"
                    class="btn-secondary"
                    @click="activeSection = 'providers'"
                  >
                    管理厂商
                  </button>
                </div>
                <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <div
                    v-for="provider in providerCoverageRows"
                    :key="provider.name"
                    class="provider-card"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <p
                          class="truncate text-sm font-semibold text-slate-900"
                        >
                          {{ provider.name }}
                        </p>
                        <p class="mt-1 text-xs text-slate-500">
                          {{ provider.model_count }} 个模型
                        </p>
                      </div>
                      <span
                        :class="
                          provider.ready_rate >= 80 ? 'badge-ok' : 'badge-muted'
                        "
                      >
                        {{ provider.ready_rate }}%
                      </span>
                    </div>
                    <div class="mt-3 space-y-2">
                      <div class="metric-line">
                        <span>渠道覆盖</span>
                        <strong>{{ provider.procured_count }}</strong>
                      </div>
                      <div class="metric-line">
                        <span>Agione 已挂售</span>
                        <strong>{{ provider.listed_count }}</strong>
                      </div>
                      <div class="metric-line">
                        <span>待处理</span>
                        <strong>{{ provider.todo_count }}</strong>
                      </div>
                    </div>
                    <div
                      class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100"
                    >
                      <div
                        class="h-full rounded-full bg-emerald-500"
                        :style="{ width: `${provider.ready_rate}%` }"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div class="panel overflow-hidden p-0">
                <div class="table-toolbar">
                  <div>
                    <h3 class="panel-title">重点模型运营表</h3>
                    <p class="mt-1 text-xs text-slate-500">
                      优先展示缺渠道价、未挂售、非最低价和覆盖偏少的模型
                    </p>
                  </div>
                  <div class="flex flex-col gap-2 sm:flex-row">
                    <CompactSelect
                      v-model="simulation.channel"
                      :options="simulationChannelOptions"
                      class-name="w-36"
                      size="sm"
                    />
                    <CompactSelect
                      v-model="simulation.status"
                      :options="simulationStatusOptions"
                      class-name="w-32"
                      size="sm"
                    />
                  </div>
                </div>
                <div class="overflow-x-auto">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th class="table-head">模型</th>
                        <th class="table-head">服务商</th>
                        <th class="table-head text-right">渠道覆盖</th>
                        <th class="table-head">
                          {{ simulation.channel ? '筛选渠道' : '最低采购渠道' }}
                        </th>
                        <th class="table-head">Agione</th>
                        <th class="table-head text-right">
                          {{ simulation.channel ? '输入价' : '最低输入' }}
                        </th>
                        <th class="table-head text-right">
                          {{ simulation.channel ? '输出价' : '最低输出' }}
                        </th>
                        <th class="table-head">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in monitorTableRows" :key="row.model_id">
                        <td class="table-cell">
                          <p class="font-medium text-slate-900">
                            {{ row.model_name }}
                          </p>
                          <p
                            v-if="monitorModelSubtitle(row)"
                            class="mt-1 font-mono text-xs text-slate-500"
                          >
                            {{ monitorModelSubtitle(row) }}
                          </p>
                        </td>
                        <td class="table-cell">{{ row.provider_name }}</td>
                        <td class="table-cell text-right font-mono">
                          {{ row.coverage_count }} / {{ channels.length }}
                        </td>
                        <td class="table-cell">
                          {{ row.display_channel?.channel_name || '无供应' }}
                        </td>
                        <td class="table-cell">
                          <span
                            :class="
                              row.is_agione_listed ? 'badge-ok' : 'badge-muted'
                            "
                          >
                            {{ row.is_agione_listed ? '已挂售' : '未挂售' }}
                          </span>
                        </td>
                        <td class="table-cell text-right font-mono">
                          {{
                            money(
                              row.display_channel?.input_price_per_million,
                              row.display_channel?.currency
                            )
                          }}
                        </td>
                        <td class="table-cell text-right font-mono">
                          {{
                            money(
                              row.display_channel?.output_price_per_million,
                              row.display_channel?.currency
                            )
                          }}
                        </td>
                        <td class="table-cell">
                          <span :class="['status-pill', row.status_tone]">
                            {{ row.status_label }}
                          </span>
                        </td>
                      </tr>
                      <tr v-if="!monitorTableRows.length">
                        <td class="table-cell text-slate-500" colspan="8">
                          当前筛选条件下没有需要展示的模型。
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            <AgioneListingStatusBoard
              v-else-if="activeSection === 'reseller'"
              :agione-platform="agionePlatform"
              :providers="providers"
              :models="models"
              :price-items="modelPriceItems"
              :listings="listings"
              :listing-exclusions="listingExclusions"
              :summary="summary"
              :platform-count="activeResalePlatforms.length"
              :point-conversion="pointConversion"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshLight"
              @action="openListingActionDrawer"
              @open-workspace="openResalePublishingWorkspace"
            />

            <ProviderManagement
              v-else-if="activeSection === 'providers'"
              :providers="providers"
              :models="models"
              :sources="providerCollectionSources"
              :collection-runs="collectionRuns"
              :price-items="modelPriceItems"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshAll"
            />

            <ChannelManagement
              v-else-if="activeSection === 'channels'"
              :channels="channels"
              :providers="providers"
              :models="models"
              :channel-prices="channelPrices"
              :channel-price-items="channelPriceItems"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshAll"
            />

            <ReconciliationPanel
              v-else-if="activeSection === 'reconciler'"
              :channels="channels"
              :models="models"
              :records="records"
              @refresh="refreshLight"
            />
          </div>
        </main>
      </div>
    </div>
    <ResalePlatformModal
      :open="showPlatformModal"
      :platform="editingPlatform"
      @close="closePlatformModal"
      @saved="handlePlatformSaved"
    />
    <AgioneListingActionDrawer
      v-model:open="listingDrawerOpen"
      :model-id="listingDrawerModelId"
      :agione-platform="agionePlatform"
      :providers="providers"
      :models="models"
      :price-items="modelPriceItems"
      :listings="listings"
      :listing-exclusions="listingExclusions"
      :summary="summary"
      :point-conversion="pointConversion"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      @saved="handleListingDrawerSaved"
    />
    <ResalePublishingDrawer
      v-model:open="resalePublishingDrawerOpen"
      :agione-platform="agionePlatform"
      :platforms="activeResalePlatforms"
      :providers="providers"
      :models="models"
      :channels="channels"
      :procurement-rows="procurementRows"
      :price-items="modelPriceItems"
      :listings="listings"
      :point-conversion="pointConversion"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      @saved="handleResaleWorkspacePublished"
      @draft="handleResaleWorkspaceDraft"
    />
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import AgioneListingStatusBoard from '@/components/llm-ops/AgioneListingStatusBoard.vue'
import AgioneListingActionDrawer from '@/components/llm-ops/AgioneListingActionDrawer.vue'
import ChannelManagement from '@/components/llm-ops/ChannelManagement.vue'
import ProviderManagement from '@/components/llm-ops/ProviderManagement.vue'
import ReconciliationPanel from '@/components/llm-ops/ReconciliationPanel.vue'
import ResalePlatformModal from '@/components/llm-ops/ResalePlatformModal.vue'
import ResalePublishingDrawer from '@/components/llm-ops/ResalePublishingDrawer.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { useToast } from '@/composables/useToast'
import { llmOpsApi } from '@/api/llmOps'

const FULL_LIST_PARAMS = { page_size: 10000 }
const sectionKeys = new Set([
  'monitor',
  'providers',
  'channels',
  'reseller',
  'reconciler'
])
const activeSection = ref(initialActiveSection())
const loading = ref(false)

const sources = ref([])
const collectionRuns = ref([])
const providers = ref([])
const metaModels = ref([])
const models = ref([])
const channels = ref([])
const channelPrices = ref([])
const channelPriceItems = ref([])
const modelPriceItems = ref([])
const resalePlatforms = ref([])
const listings = ref([])
const listingExclusions = ref([])
const records = ref([])
const summary = ref({})
const supportedDisplayCurrencies = new Set(['CNY', 'USD'])
const displayCurrency = ref(
  normalizeDisplayCurrency(localStorage.getItem('llm_ops_display_currency'))
)
const selectedResalePlatformId = ref(
  localStorage.getItem('llm_ops_resale_platform') || ''
)
const showPlatformModal = ref(false)
const editingPlatform = ref(null)
const listingDrawerOpen = ref(false)
const listingDrawerModelId = ref(null)
const resalePublishingDrawerOpen = ref(false)
const { showSuccess, showError, showInfo } = useToast()

const simulation = ref({
  channel: '',
  status: 'priority'
})

const displayCurrencyOptions = [
  { label: '人民币 CNY', value: 'CNY' },
  { label: '美元 USD', value: 'USD' }
]

const simulationStatusOptions = [
  { label: '优先处理', value: 'priority' },
  { label: '全部模型', value: 'all' },
  { label: '需要汇率', value: 'currency_mismatch' },
  { label: '缺渠道价', value: 'missing_channel' },
  { label: '未挂售', value: 'unlisted' },
  { label: '非最低价', value: 'not_lowest' },
  { label: '已就绪', value: 'ready' }
]

const navItems = computed(() => [
  {
    key: 'monitor',
    label: '运营总览',
    eyebrow: 'Monitor',
    description: '汇总模型价格、渠道覆盖、采购路径和关键运营指标。',
    icon: 'M'
  },
  {
    key: 'providers',
    label: '模型价格源',
    eyebrow: 'Sources',
    description: '维护原厂、供货商、人工等模型价格源，并查看对应模型定价。',
    icon: 'P',
    badge: providerCollectionSources.value.length
  },
  {
    key: 'channels',
    label: '转发渠道',
    eyebrow: 'Channels',
    description: '维护渠道，并在渠道内管理可启用转发的服务商模型和价格策略。',
    icon: 'C',
    badge: channels.value.length
  },
  {
    key: 'reseller',
    label: '挂售平台',
    eyebrow: 'Reseller',
    description: '维护 Agione 类平台挂售价格、积分换算和渠道选择。',
    icon: 'R',
    badge: agioneListingRows.value.length
  },
  {
    key: 'reconciler',
    label: '用量对账',
    eyebrow: 'Reconciliation',
    description: '录入生产用量和账单金额，自动计算应付金额与差异。',
    icon: 'A'
  }
])

const activeNav = computed(
  () =>
    navItems.value.find((item) => item.key === activeSection.value) ||
    navItems.value[0]
)

const activeResalePlatforms = computed(() =>
  resalePlatforms.value.filter((item) => item.is_active !== false)
)

const resalePlatformOptions = computed(() =>
  activeResalePlatforms.value.map((platform) => ({
    label: platform.name,
    value: String(platform.id)
  }))
)

const simulationChannelOptions = computed(() => [
  { label: '全部渠道', value: '' },
  ...channels.value.map((channel) => ({
    label: channel.name,
    value: channel.id
  }))
])

const agionePlatform = computed(
  () =>
    activeResalePlatforms.value.find(
      (item) => String(item.id) === String(selectedResalePlatformId.value)
    ) ||
    activeResalePlatforms.value.find((item) => item.code === 'agione') ||
    activeResalePlatforms.value[0] ||
    null
)

const showPlatformControl = computed(() =>
  ['monitor', 'reseller'].includes(activeSection.value)
)

const providerCollectionSources = computed(() =>
  sources.value.filter((item) => item.source_type !== 'agione')
)

const procurementRows = computed(() => summary.value.procurement || [])
const agioneDiagnostics = computed(
  () => summary.value.agione?.diagnostics || []
)
const exchangeRate = computed(() =>
  Number(summary.value.currency?.usd_to_cny_rate || 7.15)
)
const exchangeRateLabel = computed(() => {
  const currency = summary.value.currency
  if (!currency) return ''
  const rate = Number(currency.usd_to_cny_rate || 0).toFixed(4)
  const source = currency.rate_source_label || '汇率'
  return `1 USD = ${rate} CNY · ${source}`
})
const pointConversion = computed(() => summary.value.point_conversion || null)

const activeModels = computed(() =>
  models.value.filter((model) => model.is_active !== false)
)

const activeModelIds = computed(
  () => new Set(activeModels.value.map((model) => String(model.id)))
)

const agioneListingRows = computed(() => {
  const agioneId = agionePlatform.value?.id
  if (!agioneId) return []
  return listings.value.filter(
    (listing) =>
      listing.is_active !== false &&
      String(listing.platform) === String(agioneId)
  )
})

const agioneListingModelIds = computed(() => {
  return new Set(
    agioneListingRows.value
      .filter((listing) => activeModelIds.value.has(String(listing.model)))
      .map((listing) => String(listing.model))
  )
})

const agioneListingsByModel = computed(() => {
  const rowsByModel = new Map()
  agioneListingRows.value.forEach((listing) => {
    const key = String(listing.model)
    const rows = rowsByModel.get(key) || []
    rows.push(listing)
    rowsByModel.set(key, rows)
  })
  return rowsByModel
})

const enrichedProcurementRows = computed(() =>
  (agioneDiagnostics.value.length
    ? agioneDiagnostics.value
    : procurementRows.value
  ).map((row) => {
    if (row.status) {
      return {
        ...row,
        best_channel: row.best_channel || null,
        display_channel: row.best_channel || null,
        coverage_count: row.coverage_count ?? (row.options || []).length,
        is_agione_listed: Boolean(row.is_agione_listed),
        has_lowest_listing: Boolean(row.has_lowest_listing),
        requires_currency_conversion: Boolean(row.requires_currency_conversion),
        status_priority: row.status_priority || 5,
        status_label: row.status_label || '就绪',
        status_tone: monitorStatusTone(row.status)
      }
    }
    const options = row.options || []
    const bestChannel = row.best_channel || null
    const coverageCount = options.length
    const agioneListings =
      agioneListingsByModel.value.get(String(row.model_id)) || []
    const isAgioneListed = agioneListingModelIds.value.has(String(row.model_id))
    const hasLowestListing = agioneListings.some((listing) =>
      isLowestListing(listing, bestChannel, options)
    )
    const status = resolveMonitorStatus({
      bestChannel,
      coverageCount,
      isAgioneListed,
      hasLowestListing,
      requiresCurrencyConversion: row.requires_currency_conversion || false
    })
    return {
      ...row,
      best_channel: bestChannel,
      display_channel: bestChannel,
      coverage_count: coverageCount,
      is_agione_listed: isAgioneListed,
      has_lowest_listing: hasLowestListing,
      requires_currency_conversion: row.requires_currency_conversion || false,
      ...status
    }
  })
)

const listedCount = computed(() => agioneListingModelIds.value.size)
const procuredCount = computed(
  () => enrichedProcurementRows.value.filter((row) => row.best_channel).length
)
const missingChannelRows = computed(() =>
  enrichedProcurementRows.value.filter((row) => !row.best_channel)
)
const currencyMismatchRows = computed(() =>
  enrichedProcurementRows.value.filter(
    (row) => row.requires_currency_conversion
  )
)
const unlistedRows = computed(() =>
  enrichedProcurementRows.value.filter((row) => !row.is_agione_listed)
)
const readyRows = computed(() =>
  enrichedProcurementRows.value.filter((row) => row.status_priority === 5)
)
const nonLowestRows = computed(() =>
  enrichedProcurementRows.value.filter(
    (row) => row.best_channel && row.is_agione_listed && !row.has_lowest_listing
  )
)
const lowCoverageRows = computed(() =>
  enrichedProcurementRows.value.filter((row) => row.status_priority === 4)
)

const kpiCards = computed(() => {
  const modelCount = activeModels.value.length
  const channelCount = channels.value.length
  const procurementRate = percentage(procuredCount.value, modelCount)
  const listingRate = percentage(listedCount.value, modelCount)
  const readyRate = percentage(readyRows.value.length, modelCount)
  return [
    {
      label: '运营就绪',
      value: `${readyRows.value.length}/${modelCount}`,
      badge: `${readyRate}%`,
      hint: `${readyRows.value.length} 个模型渠道覆盖、挂售和最低价状态均就绪`,
      progress: readyRate,
      tone: readyRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-emerald-500'
    },
    {
      label: '渠道覆盖',
      value: `${procuredCount.value}/${modelCount}`,
      badge: `${procurementRate}%`,
      hint: `${missingChannelRows.value.length} 个缺渠道价 · ${currencyMismatchRows.value.length} 个需要汇率`,
      progress: procurementRate,
      tone: procurementRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-agione-500'
    },
    {
      label: '平台挂售',
      value: `${listedCount.value}/${modelCount}`,
      badge: `${listingRate}%`,
      hint: `${unlistedRows.value.length} 个未上架 · ${nonLowestRows.value.length} 个非最低价`,
      progress: listingRate,
      tone: listingRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-cyan-500'
    },
    {
      label: '渠道数',
      value: channelCount,
      badge: `${providerCollectionSources.value.length} 源`,
      hint: '转发渠道和模型价格源配置情况',
      progress: channelCount ? 100 : 0,
      tone: channelCount ? 'good' : 'danger',
      barClass: 'bg-violet-500'
    },
    {
      label: '对账异常',
      value: summary.value.kpis?.reconciliation_anomalies || 0,
      badge:
        summary.value.kpis?.reconciliation_anomalies || 0 ? '需处理' : '正常',
      hint: '生产用量与账单金额的差异记录',
      progress: summary.value.kpis?.reconciliation_anomalies || 0 ? 100 : 0,
      tone:
        summary.value.kpis?.reconciliation_anomalies || 0 ? 'danger' : 'good',
      barClass:
        summary.value.kpis?.reconciliation_anomalies || 0
          ? 'bg-rose-500'
          : 'bg-emerald-500'
    }
  ]
})

const actionItems = computed(() => [
  {
    label: '补齐渠道采购价',
    hint: '没有渠道价的模型无法进行可靠挂售和成本计算',
    value: missingChannelRows.value.length,
    tone: missingChannelRows.value.length ? 'danger' : 'good',
    section: 'channels'
  },
  {
    label: '配置汇率',
    hint: '同一模型存在不同采购币种，需要汇率后才能判断最低价',
    value: currencyMismatchRows.value.length,
    tone: currencyMismatchRows.value.length ? 'warn' : 'good',
    section: 'channels'
  },
  {
    label: '上架挂售平台',
    hint: '已有模型主数据但尚未进入当前挂售平台',
    value: unlistedRows.value.length,
    tone: unlistedRows.value.length ? 'warn' : 'good',
    section: 'reseller'
  },
  {
    label: '切换最低价渠道',
    hint: '已上架但当前渠道不是最低采购价，需要评估切换',
    value: nonLowestRows.value.length,
    tone: nonLowestRows.value.length ? 'warn' : 'good',
    section: 'reseller'
  },
  {
    label: '补充渠道覆盖',
    hint: '只有一个可用渠道的模型缺少采购备选，价格稳定性较弱',
    value: lowCoverageRows.value.length,
    tone: lowCoverageRows.value.length ? 'warn' : 'good',
    section: 'channels'
  },
  {
    label: '检查模型价格源',
    hint: latestCollectionRun.value
      ? `${latestCollectionRun.value.status || '-'} · ${formatDateTime(
          latestCollectionRun.value.finished_at ||
            latestCollectionRun.value.started_at
        )}`
      : '还没有模型价格源记录',
    value: collectionAttentionCount.value,
    tone: collectionAttentionCount.value ? 'danger' : 'good',
    section: 'providers'
  },
  {
    label: '处理对账差异',
    hint: '对账异常会影响渠道结算和毛利判断',
    value: summary.value.kpis?.reconciliation_anomalies || 0,
    tone: summary.value.kpis?.reconciliation_anomalies || 0 ? 'danger' : 'good',
    section: 'reconciler'
  }
])

const latestCollectionRun = computed(
  () =>
    collectionRuns.value
      .slice()
      .sort(
        (left, right) =>
          new Date(
            right.finished_at || right.started_at || right.created_at || 0
          ).getTime() -
          new Date(
            left.finished_at || left.started_at || left.created_at || 0
          ).getTime()
      )[0] || null
)

const collectionAttentionCount = computed(
  () =>
    collectionRuns.value.filter((run) =>
      ['failed', 'running', 'pending', 'processing'].includes(run.status)
    ).length
)

const channelCoverageRows = computed(() =>
  channels.value
    .map((channel) => {
      const covered = procurementRows.value.filter((row) =>
        (row.options || []).some(
          (option) => String(option.channel_id) === String(channel.id)
        )
      ).length
      const bestCount = procurementRows.value.filter(
        (row) => String(row.best_channel?.channel_id) === String(channel.id)
      ).length
      return {
        ...channel,
        covered,
        best_count: bestCount,
        coverage_rate: percentage(covered, activeModels.value.length)
      }
    })
    .sort((left, right) => right.covered - left.covered)
)

const providerCoverageRows = computed(() =>
  providers.value.map((provider) => {
    const providerModels = activeModels.value.filter(
      (model) => String(model.provider) === String(provider.id)
    )
    const modelIds = new Set(providerModels.map((model) => String(model.id)))
    const providerRows = enrichedProcurementRows.value.filter((row) =>
      modelIds.has(String(row.model_id))
    )
    const procured = providerRows.filter((row) => row.best_channel).length
    const listed = providerRows.filter((row) => row.is_agione_listed).length
    const ready = providerRows.filter((row) => row.status_priority === 5).length
    return {
      name: provider.name,
      model_count: providerModels.length,
      procured_count: procured,
      listed_count: listed,
      todo_count: Math.max(providerModels.length - ready, 0),
      ready_rate: percentage(ready, providerModels.length)
    }
  })
)

const filteredProcurementRows = computed(() => {
  const rows = enrichedProcurementRows.value
  if (!simulation.value.channel) {
    return rows.map((row) => ({ ...row, display_channel: row.best_channel }))
  }
  return rows
    .map((row) => {
      const option = row.options?.find(
        (item) => String(item.channel_id) === String(simulation.value.channel)
      )
      return { ...row, display_channel: option || null }
    })
    .filter((row) => row.display_channel)
})

const monitorTableRows = computed(() => {
  const rows = filteredProcurementRows.value.filter((row) => {
    if (simulation.value.status === 'all') return true
    if (simulation.value.status === 'currency_mismatch') {
      return row.requires_currency_conversion
    }
    if (simulation.value.status === 'missing_channel') return !row.best_channel
    if (simulation.value.status === 'unlisted') return !row.is_agione_listed
    if (simulation.value.status === 'not_lowest') {
      return row.is_agione_listed && !row.has_lowest_listing
    }
    if (simulation.value.status === 'ready') {
      return row.best_channel && row.is_agione_listed && row.has_lowest_listing
    }
    return (
      !row.best_channel ||
      !row.is_agione_listed ||
      !row.has_lowest_listing ||
      row.coverage_count <= 1
    )
  })
  return rows.slice().sort((left, right) => {
    if (left.status_priority !== right.status_priority) {
      return left.status_priority - right.status_priority
    }
    return String(left.provider_name).localeCompare(String(right.provider_name))
  })
})

function extract(response) {
  const data = response?.data?.data || response?.data || []
  return Array.isArray(data.results) ? data.results : data
}

function monitorModelSubtitle(row) {
  const name = String(row.model_name || '').trim()
  const code = String(row.model_code || '').trim()
  if (code && code !== name) return code
  return ''
}

async function refreshAll() {
  loading.value = true
  try {
    const [
      sourceRes,
      runRes,
      providerRes,
      metaModelRes,
      modelRes,
      channelRes,
      priceRes,
      channelPriceItemRes,
      priceItemRes,
      platformRes,
      listingRes,
      exclusionRes,
      recordRes,
      summaryRes
    ] = await Promise.all([
      llmOpsApi.listCollectionSources(FULL_LIST_PARAMS),
      llmOpsApi.listCollectionRuns(FULL_LIST_PARAMS),
      llmOpsApi.listProviders(FULL_LIST_PARAMS),
      llmOpsApi.listMetaModels(FULL_LIST_PARAMS),
      llmOpsApi.listModels(FULL_LIST_PARAMS),
      llmOpsApi.listChannels(FULL_LIST_PARAMS),
      llmOpsApi.listChannelModelPrices(FULL_LIST_PARAMS),
      llmOpsApi.listChannelPriceItems({
        ...FULL_LIST_PARAMS,
        is_current: 'true'
      }),
      llmOpsApi.listModelPriceItems({
        ...FULL_LIST_PARAMS,
        is_current: 'true'
      }),
      llmOpsApi.listResalePlatforms(FULL_LIST_PARAMS),
      llmOpsApi.listResaleListings(FULL_LIST_PARAMS),
      llmOpsApi.listResaleListingExclusions(FULL_LIST_PARAMS),
      llmOpsApi.listReconciliationRecords(FULL_LIST_PARAMS),
      llmOpsApi.getSummary(summaryParams())
    ])
    sources.value = extract(sourceRes)
    collectionRuns.value = extract(runRes)
    providers.value = extract(providerRes)
    metaModels.value = extract(metaModelRes)
    models.value = extract(modelRes)
    channels.value = extract(channelRes)
    channelPrices.value = extract(priceRes)
    channelPriceItems.value = extract(channelPriceItemRes)
    modelPriceItems.value = extract(priceItemRes)
    resalePlatforms.value = extract(platformRes)
    listings.value = extract(listingRes)
    listingExclusions.value = extract(exclusionRes)
    records.value = extract(recordRes)
    summary.value = extract(summaryRes)
  } finally {
    loading.value = false
  }
}

async function refreshLight() {
  const [
    priceRes,
    channelPriceItemRes,
    listingRes,
    exclusionRes,
    recordRes,
    summaryRes
  ] = await Promise.all([
    llmOpsApi.listChannelModelPrices(FULL_LIST_PARAMS),
    llmOpsApi.listChannelPriceItems({
      ...FULL_LIST_PARAMS,
      is_current: 'true'
    }),
    llmOpsApi.listResaleListings(FULL_LIST_PARAMS),
    llmOpsApi.listResaleListingExclusions(FULL_LIST_PARAMS),
    llmOpsApi.listReconciliationRecords(FULL_LIST_PARAMS),
    llmOpsApi.getSummary(summaryParams())
  ])
  channelPrices.value = extract(priceRes)
  channelPriceItems.value = extract(channelPriceItemRes)
  listings.value = extract(listingRes)
  listingExclusions.value = extract(exclusionRes)
  records.value = extract(recordRes)
  summary.value = extract(summaryRes)
}

function percentage(value, total) {
  if (!total) return 0
  return Math.round((Number(value || 0) / Number(total)) * 100)
}

function isLowestListing(listing, bestChannel, options) {
  if (!bestChannel) return false
  if (!listing.channel) return true
  const option = options.find(
    (item) => String(item.channel_id) === String(listing.channel)
  )
  return String(option?.channel_id) === String(bestChannel.channel_id)
}

function resolveMonitorStatus({
  bestChannel,
  coverageCount,
  isAgioneListed,
  hasLowestListing,
  requiresCurrencyConversion
}) {
  if (requiresCurrencyConversion) {
    return {
      status_label: '需要汇率',
      status_tone: 'info',
      status_priority: 1
    }
  }
  if (!bestChannel) {
    return {
      status_label: '缺渠道价',
      status_tone: 'danger',
      status_priority: 1
    }
  }
  if (!isAgioneListed) {
    return {
      status_label: '可上架',
      status_tone: 'warn',
      status_priority: 2
    }
  }
  if (!hasLowestListing) {
    return {
      status_label: '非最低价',
      status_tone: 'warn',
      status_priority: 3
    }
  }
  if (coverageCount <= 1) {
    return {
      status_label: '覆盖偏少',
      status_tone: 'info',
      status_priority: 4
    }
  }
  return {
    status_label: '已就绪',
    status_tone: 'success',
    status_priority: 5
  }
}

function monitorStatusTone(status) {
  const tones = {
    currency_mismatch: 'info',
    missing_channel: 'danger',
    unlisted: 'warn',
    not_lowest: 'warn',
    low_coverage: 'info',
    ready: 'success'
  }
  return tones[status] || 'success'
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || 'USD'} ${Number(value).toFixed(4)}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

watch(displayCurrency, (currency) => {
  const normalized = normalizeDisplayCurrency(currency)
  if (normalized !== currency) {
    displayCurrency.value = normalized
    return
  }
  localStorage.setItem('llm_ops_display_currency', normalized)
  if (!loading.value) {
    refreshLight()
  }
})

watch(activeSection, (section) => {
  if (!sectionKeys.has(section)) return
  localStorage.setItem('llm_ops_active_section', section)
  if (typeof window === 'undefined') return
  const url = new URL(window.location.href)
  url.searchParams.set('section', section)
  window.history.replaceState({}, '', `${url.pathname}${url.search}`)
})

watch(selectedResalePlatformId, (platformId) => {
  if (platformId) {
    localStorage.setItem('llm_ops_resale_platform', platformId)
  }
  if (!loading.value) {
    refreshLight()
  }
})

watch(
  activeResalePlatforms,
  (platforms) => {
    if (!platforms.length) {
      selectedResalePlatformId.value = ''
      return
    }
    const exists = platforms.some(
      (platform) =>
        String(platform.id) === String(selectedResalePlatformId.value)
    )
    if (!exists) {
      const fallback =
        platforms.find((platform) => platform.code === 'agione') || platforms[0]
      selectedResalePlatformId.value = String(fallback.id)
    }
  },
  { immediate: true }
)

function normalizeDisplayCurrency(value) {
  const currency = String(value || '')
    .trim()
    .toUpperCase()
  return supportedDisplayCurrencies.has(currency) ? currency : 'CNY'
}

function summaryParams() {
  return {
    display_currency: displayCurrency.value,
    resale_platform: selectedResalePlatformId.value || ''
  }
}

function openPlatformModal(platform) {
  editingPlatform.value = platform ? { ...platform } : null
  showPlatformModal.value = true
}

function closePlatformModal() {
  showPlatformModal.value = false
  editingPlatform.value = null
}

function handlePlatformSaved() {
  closePlatformModal()
  refreshAll()
}

function openListingActionDrawer({ modelId, kind }) {
  if (kind === 'configure-channel') {
    activeSection.value = 'channels'
    showError('请先在转发渠道中为该模型配置采购价，再返回挂售平台。')
    return
  }
  if (!agionePlatform.value) {
    showError('请先配置挂售平台后再编辑挂售。')
    return
  }
  // Direct row actions (remove / restore / offline) are handled by
  // StatusBoard itself. Create / view / edit flows open the drawer.
  if (!['create', 'view', 'edit'].includes(kind)) return
  listingDrawerModelId.value = kind === 'create' ? null : modelId
  listingDrawerOpen.value = true
}

function openResalePublishingWorkspace() {
  resalePublishingDrawerOpen.value = true
}

function mapWorkspaceListingToPayload(item) {
  const inApi = Number(item.priceIn) || 0
  const outApi = Number(item.priceOut) || 0
  return {
    platform: agionePlatform.value?.id,
    model: item.modelId,
    channel: item.channelId,
    currency: 'USD',
    retail_input_price_per_million: inApi.toFixed(6),
    retail_output_price_per_million: outApi.toFixed(6),
    is_active: true
  }
}

async function handleResaleWorkspacePublished(payload) {
  if (!payload || !payload.listings || !payload.listings.length) {
    showInfo('没有需要上架的链路')
    return
  }
  const items = payload.listings
    .filter((item) => Number(item.priceIn) > 0 && Number(item.priceOut) > 0)
    .map(mapWorkspaceListingToPayload)
  if (!items.length) {
    showError('请为每条链路填写有效的 In/Out 售价后再发布')
    return
  }
  try {
    await llmOpsApi.bulkUpsertResaleListings(items)
    showSuccess(`已上架 ${items.length} 条链路`)
    refreshLight()
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || '上架失败')
  }
}

function handleResaleWorkspaceDraft() {
  // Drafts are held in the workspace component for now.
  // Reserved for future localStorage draft persistence.
}

function handleListingDrawerSaved() {
  listingDrawerOpen.value = false
  refreshLight()
}

function initialActiveSection() {
  if (typeof window !== 'undefined') {
    const querySection = new URLSearchParams(window.location.search).get(
      'section'
    )
    if (sectionKeys.has(querySection)) return querySection
  }
  const storedSection = localStorage.getItem('llm_ops_active_section')
  if (sectionKeys.has(storedSection)) return storedSection
  return 'monitor'
}

onMounted(refreshAll)
</script>

<style scoped>
/* === Base utility classes (hardcoded, Tailwind fallback) === */
.bg-white {
  background-color: #ffffff;
}
.bg-slate-50 {
  background-color: #f8fafc;
}
.bg-slate-100 {
  background-color: #f1f5f9;
}
.bg-slate-200 {
  background-color: #e2e8f0;
}
.bg-slate-950 {
  background-color: #020617;
}
.bg-transparent {
  background-color: transparent;
}
.bg-emerald-50 {
  background-color: #ecfdf5;
}
.bg-emerald-500 {
  background-color: #10b981;
}
.bg-amber-50 {
  background-color: #fffbeb;
}
.bg-amber-500 {
  background-color: #f59e0b;
}
.bg-rose-50 {
  background-color: #fff1f2;
}
.bg-rose-500 {
  background-color: #f43f5e;
}
.bg-violet-500 {
  background-color: #8b5cf6;
}
.bg-sky-500 {
  background-color: #0ea5e9;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-agione-50 {
  background-color: #ece9f9;
}
.bg-agione-100 {
  background-color: #d8d2f0;
}
.bg-agione-200 {
  background-color: #b3a8e2;
}
.bg-agione-300 {
  background-color: #8b7dd1;
}
.bg-agione-400 {
  background-color: #7a6ac4;
}
.bg-agione-500 {
  background-color: #6a5ac7;
}
.bg-agione-600 {
  background-color: #5f4ecf;
}
.bg-agione-700 {
  background-color: #4a3eb0;
}
.bg-agione-800 {
  background-color: #3d3399;
}
.bg-agione-900 {
  background-color: #312870;
}
.text-white {
  color: #ffffff;
}
.text-slate-500 {
  color: #64748b;
}
.text-slate-600 {
  color: #475569;
}
.text-slate-700 {
  color: #334155;
}
.text-slate-900 {
  color: #0f172a;
}
.text-emerald-600 {
  color: #059669;
}
.text-emerald-700 {
  color: #047857;
}
.text-amber-600 {
  color: #d97706;
}
.text-amber-700 {
  color: #b45309;
}
.text-rose-500 {
  color: #f43f5e;
}
.text-rose-600 {
  color: #e11d48;
}
.text-rose-700 {
  color: #be123c;
}
.text-agione-50 {
  color: #ece9f9;
}
.text-agione-100 {
  color: #d8d2f0;
}
.text-agione-300 {
  color: #8b7dd1;
}
.text-agione-500 {
  color: #6a5ac7;
}
.text-agione-600 {
  color: #5f4ecf;
}
.text-agione-700 {
  color: #4a3eb0;
}
.text-agione-800 {
  color: #3d3399;
}
.border-slate-200 {
  border-color: #e2e8f0;
}
.border-slate-300 {
  border-color: #cbd5e1;
}
.border-emerald-100 {
  border-color: #d1fae5;
}
.border-emerald-200 {
  border-color: #a7f3d0;
}
.border-amber-100 {
  border-color: #fef3c7;
}
.border-amber-200 {
  border-color: #fde68a;
}
.border-rose-100 {
  border-color: #ffe4e6;
}
.border-rose-200 {
  border-color: #fecdd3;
}
.border-agione-100 {
  border-color: #d8d2f0;
}
.border-agione-200 {
  border-color: #b3a8e2;
}
.border-agione-300 {
  border-color: #8b7dd1;
}
.border-agione-400 {
  border-color: #7a6ac4;
}
.border-agione-500 {
  border-color: #6a5ac7;
}
.focus\:border-agione-300:focus {
  border-color: #8b7dd1;
}
.focus\:border-agione-400:focus {
  border-color: #7a6ac4;
}
.focus\:ring-2:focus {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}
.focus\:ring-4:focus {
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.3);
}
.focus\:ring-agione-100:focus {
  box-shadow: 0 0 0 2px #d8d2f0;
}
.focus\:ring-agione-200:focus {
  box-shadow: 0 0 0 2px #b3a8e2;
}
.hover\:bg-slate-50:hover {
  background-color: #f8fafc;
}
.hover\:bg-agione-600:hover {
  background-color: #5f4ecf;
}
.hover\:bg-agione-700:hover {
  background-color: #4a3eb0;
}
.hover\:border-slate-300:hover {
  border-color: #cbd5e1;
}
.hover\:text-agione-700:hover {
  color: #4a3eb0;
}
.hover\:text-slate-500:hover {
  color: #64748b;
}
.disabled\:cursor-not-allowed:disabled {
  cursor: not-allowed;
}
.disabled\:opacity-50:disabled {
  opacity: 0.5;
}
.disabled\:opacity-60:disabled {
  opacity: 0.6;
}
.text-xs {
  font-size: 0.75rem;
  line-height: 1rem;
}
.text-sm {
  font-size: 0.875rem;
  line-height: 1.25rem;
}
.text-base {
  font-size: 1rem;
  line-height: 1.5rem;
}
.text-lg {
  font-size: 1.125rem;
  line-height: 1.75rem;
}
.text-xl {
  font-size: 1.25rem;
  line-height: 1.75rem;
}
.text-2xl {
  font-size: 1.5rem;
  line-height: 2rem;
}
.text-3xl {
  font-size: 1.875rem;
  line-height: 2.25rem;
}
.text-4xl {
  font-size: 2.25rem;
  line-height: 2.5rem;
}
.text-\[10px\] {
  font-size: 10px;
}
.text-\[11px\] {
  font-size: 11px;
}
.text-\[12px\] {
  font-size: 12px;
}
.text-\[13px\] {
  font-size: 13px;
}
.text-\[14px\] {
  font-size: 14px;
}
.text-\[15px\] {
  font-size: 15px;
}
.text-\[18px\] {
  font-size: 18px;
}
.text-\[24px\] {
  font-size: 24px;
}
.top-0 {
  top: 0;
}
.z-10 {
  z-index: 10;
}
.z-20 {
  z-index: 20;
}
.z-50 {
  z-index: 50;
}
.max-w-\[20rem\] {
  max-width: 20rem;
}
.w-60 {
  width: 15rem;
}
.w-72 {
  width: 18rem;
}
.w-80 {
  width: 20rem;
}
.w-36 {
  width: 9rem;
}
.w-32 {
  width: 8rem;
}
.h-9 {
  height: 2.25rem;
}
.h-7 {
  height: 1.75rem;
}
.h-8 {
  height: 2rem;
}
.text-left {
  text-align: left;
}
.text-right {
  text-align: right;
}
.text-center {
  text-align: center;
}
.border {
  border-width: 1px;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-indigo-500 {
  background-color: #6366f1;
}
.bg-indigo-600 {
  background-color: #4f46e5;
}
.bg-indigo-700 {
  background-color: #4338ca;
}
.text-indigo-300 {
  color: #a5b4fc;
}
.text-indigo-500 {
  color: #6366f1;
}
.text-indigo-600 {
  color: #4f46e5;
}
.text-indigo-700 {
  color: #4338ca;
}
.border-indigo-200 {
  border-color: #c7d2fe;
}
.border-indigo-300 {
  border-color: #a5b4fc;
}
.border-indigo-400 {
  border-color: #818cf8;
}
.focus\:border-indigo-300:focus {
  border-color: #a5b4fc;
}
.focus\:ring-indigo-100:focus {
  box-shadow: 0 0 0 2px #e0e7ff;
}

.panel {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding: 1rem;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.kpi-card {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
}

.kpi-tone {
  border-radius: 9999px;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
}

.kpi-tone.good {
  background-color: #ecfdf5;
  color: #047857;
}

.kpi-tone.warn {
  background-color: #fffbeb;
  color: #b45309;
}

.kpi-tone.danger {
  background-color: #fff1f2;
  color: #be123c;
}

.panel-title {
  font-weight: 600;
  color: #0f172a;
}

.table-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-bottom-width: 1px;
  border-color: #e2e8f0;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.field-sm {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  color: #334155;
  outline: none;
  border-color: #8b7dd1;
  box-shadow: 0 0 0 2px #ece9f955;
}

.currency-control {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  font-weight: 500;
  color: #64748b;
}

.currency-control select {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  color: #1e293b;
  outline: none;
}

.action-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.75rem;
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #b3a8e2;
  background-color: #ece9f9;
}

.action-dot {
  height: 0.625rem;
  width: 0.625rem;
  flex-shrink: 0;
  border-radius: 9999px;
}

.action-dot.good {
  background-color: #10b981;
}

.action-dot.warn {
  background-color: #f59e0b;
}

.action-dot.danger {
  background-color: #f43f5e;
}

.coverage-row,
.provider-card {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
}

.metric-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #64748b;
}

.metric-line strong {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  color: #0f172a;
}

.nav-icon {
  display: flex;
  height: 1.25rem;
  width: 1.25rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background-color: #1e293b;
  font-size: 10px;
  font-weight: 700;
  color: #cbd5e1;
}

.icon-mark {
  display: inline-block;
  height: 0.875rem;
  width: 0.875rem;
  flex-shrink: 0;
  border-radius: 2px;
}

.data-table {
  --tw-divide-y-reverse: 0;
  border-top-width: calc(1px * calc(1 - var(--tw-divide-y-reverse)));
  border-bottom-width: calc(1px * var(--tw-divide-y-reverse));
  --tw-divide-opacity: 1;
  border-color: rgb(226 232 240 / var(--tw-divide-opacity));
}

.data-table tbody {
  --tw-divide-y-reverse: 0;
  border-top-width: calc(1px * calc(1 - var(--tw-divide-y-reverse)));
  border-bottom-width: calc(1px * var(--tw-divide-y-reverse));
  --tw-divide-opacity: 1;
  border-color: rgb(241 245 249 / var(--tw-divide-opacity));
}

.data-table tr {
  background-color: #f8fafc;
}

.table-head {
  white-space: nowrap;
  background-color: #f8fafc;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  color: #64748b;
}

.table-cell {
  white-space: nowrap;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  color: #475569;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 8px;
  background-color: #5f4ecf;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  font-weight: 500;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  background-color: #4a3eb0;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  font-weight: 500;
  color: #334155;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  background-color: #f8fafc;
}

.badge-ok {
  border-radius: 9999px;
  border-width: 1px;
  border-color: #d1fae5;
  background-color: #ecfdf5;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
  color: #047857;
}

.badge-muted {
  border-radius: 9999px;
  border-width: 1px;
  border-color: #e2e8f0;
  background-color: #f1f5f9;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
  color: #475569;
}

.status-pill {
  border-radius: 9999px;
  padding-left: 0.625rem;
  padding-right: 0.625rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
}

.status-pill.success {
  background-color: #ecfdf5;
  color: #047857;
}

.status-pill.info {
  background-color: #000;
  color: #000;
}

.status-pill.warn {
  background-color: #fffbeb;
  color: #b45309;
}

.status-pill.danger {
  background-color: #fff1f2;
  color: #be123c;
}
</style>
