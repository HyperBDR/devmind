<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div class="h-full min-h-[calc(100vh-4rem)] bg-slate-50">
      <div class="flex h-full min-h-[calc(100vh-4rem)] w-full gap-0">
        <aside
          class="fixed bottom-0 left-0 top-16 z-20 hidden w-72 flex-col overflow-hidden bg-slate-950 text-white shadow-sm lg:flex"
        >
          <div class="border-b border-slate-800 px-5 py-5">
            <p
              class="text-[11px] font-bold uppercase tracking-[0.18em] text-agione-300"
            >
              LLM OPS
            </p>
            <h1 class="mt-2 text-lg font-semibold">
              {{ t('llmOps.shell.title') }}
            </h1>
            <p class="mt-2 text-xs leading-5 text-slate-400">
              {{ t('llmOps.shell.subtitle') }}
            </p>
          </div>

          <nav class="flex-1 space-y-5 overflow-y-auto px-3 py-4">
            <section v-for="group in navGroups" :key="group.key">
              <p
                class="px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500"
              >
                {{ group.label }}
              </p>
              <div class="mt-2 space-y-1">
                <button
                  v-for="item in group.items"
                  :key="item.key"
                  type="button"
                  class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition"
                  :class="
                    activeSection === item.key
                      ? 'bg-agione-600 text-white shadow-sm'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                  "
                  @click="activeSection = item.key"
                >
                  <svg
                    class="nav-icon"
                    aria-hidden="true"
                    fill="none"
                    stroke="currentColor"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    viewBox="0 0 24 24"
                  >
                    <path v-for="path in item.icon" :key="path" :d="path" />
                  </svg>
                  <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
                </button>
              </div>
            </section>
          </nav>
        </aside>

        <main
          class="min-w-0 flex-1 border-l border-slate-200 bg-white shadow-sm lg:ml-72"
        >
          <header class="border-b border-slate-200 px-5 py-3 lg:px-7">
            <div class="page-hero">
              <div class="page-hero-copy">
                <div class="space-y-3 lg:hidden">
                  <section v-for="group in navGroups" :key="group.key">
                    <p
                      class="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400"
                    >
                      {{ group.label }}
                    </p>
                    <div class="flex flex-wrap gap-2">
                      <button
                        v-for="item in group.items"
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
                  </section>
                </div>
                <p
                  class="page-hero-eyebrow mt-4 text-xs font-semibold uppercase tracking-[0.18em] text-agione-600 lg:mt-0"
                >
                  {{ activeNav.eyebrow }}
                </p>
                <h2
                  class="page-hero-title mt-1 text-2xl font-semibold text-slate-900"
                >
                  {{ activeNav.label }}
                </h2>
                <p
                  class="page-hero-description mt-1.5 max-w-3xl text-sm leading-6 text-slate-500"
                >
                  {{ activeNav.description }}
                </p>
              </div>
              <div v-if="showHeroActions" class="page-hero-actions">
                <div v-if="showGlobalToolbar" class="page-hero-group">
                  <div class="currency-control page-toolbar-control">
                    <span>{{ t('llmOps.toolbar.displayCurrency') }}</span>
                    <CompactSelect
                      v-model="displayCurrency"
                      :options="displayCurrencyOptions"
                      class-name="w-28"
                      size="sm"
                    />
                  </div>
                  <span v-if="exchangeRateLabel" class="page-toolbar-chip">
                    {{ exchangeRateLabel }}
                  </span>
                  <button
                    type="button"
                    class="btn-secondary page-toolbar-button refresh-action-button btn-action-refresh"
                    :disabled="loading"
                    @click="refreshAll"
                  >
                    <svg
                      aria-hidden="true"
                      :class="[
                        'refresh-action-icon',
                        { 'is-spinning': loading }
                      ]"
                      fill="none"
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
                      <path d="M3 16v5h5" />
                      <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
                      <path d="M21 3v5h-5" />
                    </svg>
                    {{ t('common.refresh') }}
                  </button>
                </div>
                <div v-if="showPlatformControl" class="page-hero-group">
                  <div class="currency-control page-toolbar-control">
                    <span>{{ t('llmOps.toolbar.resalePlatform') }}</span>
                    <CompactSelect
                      v-model="selectedResalePlatformId"
                      :options="resalePlatformOptions"
                      class-name="w-56"
                      :menu-min-width="260"
                      size="sm"
                    />
                  </div>
                  <button
                    type="button"
                    class="btn-secondary page-toolbar-button btn-action-config"
                    @click="openPlatformModal(agionePlatform)"
                  >
                    {{ t('llmOps.toolbar.platformConfig') }}
                  </button>
                  <button
                    type="button"
                    class="btn-primary page-toolbar-button btn-action-create"
                    @click="openPlatformModal(null)"
                  >
                    {{ t('llmOps.toolbar.createPlatform') }}
                  </button>
                </div>
              </div>
            </div>
          </header>

          <BaseLoading v-if="loading" class="py-20" />
          <div
            v-else
            :class="[
              'px-5 py-5 lg:px-7',
              activeSection === 'audit'
                ? 'flex h-[calc(100vh-10.75rem)] min-h-0 flex-col'
                : 'space-y-6'
            ]"
          >
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
                        {{ t('llmOps.monitor.actionQueueTitle') }}
                      </h3>
                    </div>
                    <button
                      type="button"
                      class="btn-secondary btn-action-view"
                      @click="activeSection = 'reseller'"
                    >
                      {{ t('llmOps.actions.goResale') }}
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
                        {{ t('llmOps.monitor.channelCoverageTitle') }}
                      </h3>
                    </div>
                    <span class="text-sm text-slate-500">
                      {{
                        t('llmOps.monitor.channelCount', {
                          count: channels.length
                        })
                      }}
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
                            {{
                              t('llmOps.monitor.channelCoverageMeta', {
                                covered: channel.covered,
                                best: channel.best_count
                              })
                            }}
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
                      {{ t('llmOps.monitor.emptyChannelCoverage') }}
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
                      {{ t('llmOps.monitor.providerMatrixTitle') }}
                    </h3>
                  </div>
                  <button
                    type="button"
                    class="btn-secondary btn-action-config"
                    @click="activeSection = 'providers'"
                  >
                    {{ t('llmOps.actions.manageProviders') }}
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
                          {{
                            t('llmOps.monitor.modelCount', {
                              count: provider.model_count
                            })
                          }}
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
                        <span>{{ t('llmOps.monitor.channelCoverage') }}</span>
                        <strong>{{ provider.procured_count }}</strong>
                      </div>
                      <div class="metric-line">
                        <span>{{ t('llmOps.monitor.agioneListed') }}</span>
                        <strong>{{ provider.listed_count }}</strong>
                      </div>
                      <div class="metric-line">
                        <span>{{ t('llmOps.monitor.todo') }}</span>
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
                    <h3 class="panel-title">
                      {{ t('llmOps.monitor.focusTableTitle') }}
                    </h3>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ t('llmOps.monitor.focusTableSubtitle') }}
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
                        <th class="table-head">
                          {{ t('llmOps.fields.model') }}
                        </th>
                        <th class="table-head">
                          {{ t('llmOps.fields.provider') }}
                        </th>
                        <th class="table-head text-right">
                          {{ t('llmOps.monitor.channelCoverage') }}
                        </th>
                        <th class="table-head">
                          {{
                            simulation.channel
                              ? t('llmOps.monitor.filteredChannel')
                              : t('llmOps.monitor.lowestProcurementChannel')
                          }}
                        </th>
                        <th class="table-head">Agione</th>
                        <th class="table-head text-right">
                          {{
                            simulation.channel
                              ? t('llmOps.price.input')
                              : t('llmOps.price.lowestInput')
                          }}
                        </th>
                        <th class="table-head text-right">
                          {{
                            simulation.channel
                              ? t('llmOps.price.output')
                              : t('llmOps.price.lowestOutput')
                          }}
                        </th>
                        <th class="table-head">
                          {{ t('llmOps.fields.status') }}
                        </th>
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
                          {{
                            row.display_channel?.channel_name ||
                            t('llmOps.status.noSupply')
                          }}
                        </td>
                        <td class="table-cell">
                          <span
                            :class="
                              row.is_agione_listed ? 'badge-ok' : 'badge-muted'
                            "
                          >
                            {{
                              row.is_agione_listed
                                ? t('llmOps.status.listed')
                                : t('llmOps.status.unlisted')
                            }}
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
                          {{ t('llmOps.monitor.emptyFocusRows') }}
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
              :summary="summary"
              :platform-count="activeResalePlatforms.length"
              :point-conversion="pointConversion"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshLight"
              @listings-updated="mergeResaleListings"
              @action="openListingActionDrawer"
              @open-workspace="openResalePublishingWorkspace"
            />

            <ResaleWorkflowConfigPanel
              v-else-if="activeSection === 'workflow'"
              v-model:platform-id="selectedResalePlatformId"
              :platforms="activeResalePlatforms"
              @saved="handleWorkflowConfigSaved"
            />

            <GlobalConfigPanel
              v-else-if="activeSection === 'globalConfig'"
              :sources="providerCollectionSources"
              @saved="refreshLight"
            />

            <CollectionRunLogPanel
              v-else-if="activeSection === 'taskLogs'"
              :runs="collectionRuns"
              :sources="sources"
              @refresh="refreshCollectionRuns"
            />

            <ProviderManagement
              v-else-if="activeSection === 'providers'"
              :providers="providers"
              :meta-models="metaModels"
              :models="models"
              :sources="providerCollectionSources"
              :collection-runs="collectionRuns"
              :price-items="modelPriceItems"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshAll"
            />

            <MetaModelManagement
              v-else-if="activeSection === 'metaModels'"
              :meta-models="metaModels"
              :providers="providers"
              :models="models"
              :price-items="modelPriceItems"
              @refresh="refreshAll"
            />

            <ChannelManagement
              v-else-if="activeSection === 'channels'"
              :channels="channels"
              :providers="providers"
              :models="models"
              :channel-prices="channelPrices"
              :channel-price-items="channelPriceItems"
              :price-items="modelPriceItems"
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

            <AuditLogPanel
              v-else-if="activeSection === 'audit'"
              :channels="channels"
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
    <ResalePublishingDrawer
      v-model:open="resalePublishingDrawerOpen"
      :initial-model-id="resalePublishingInitialModelId"
      :agione-platform="agionePlatform"
      :platforms="activeResalePlatforms"
      :providers="providers"
      :meta-models="metaModels"
      :models="models"
      :channels="channels"
      :procurement-rows="procurementRows"
      :price-items="modelPriceItems"
      :channel-price-items="channelPriceItems"
      :listings="listings"
      :point-conversion="pointConversion"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      :workflow-config="workflowConfigForWorkspace"
      @saved="handleResaleWorkspacePublished"
      @draft="handleResaleWorkspaceDraft"
    />
  </AppLayout>
</template>

<script setup>
import '@/components/llm-ops/llmOpsButtons.css'
import '@/components/llm-ops/llmOpsModals.css'
import '@/components/llm-ops/llmOpsTables.css'

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import AgioneListingStatusBoard from '@/components/llm-ops/AgioneListingStatusBoard.vue'
import AuditLogPanel from '@/components/llm-ops/AuditLogPanel.vue'
import ChannelManagement from '@/components/llm-ops/ChannelManagement.vue'
import CollectionRunLogPanel from '@/components/llm-ops/CollectionRunLogPanel.vue'
import GlobalConfigPanel from '@/components/llm-ops/GlobalConfigPanel.vue'
import MetaModelManagement from '@/components/llm-ops/MetaModelManagement.vue'
import ProviderManagement from '@/components/llm-ops/ProviderManagement.vue'
import ReconciliationPanel from '@/components/llm-ops/ReconciliationPanel.vue'
import ResalePlatformModal from '@/components/llm-ops/ResalePlatformModal.vue'
import ResalePublishingDrawer from '@/components/llm-ops/ResalePublishingDrawer.vue'
import ResaleWorkflowConfigPanel from '@/components/llm-ops/ResaleWorkflowConfigPanel.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { useToast } from '@/composables/useToast'
import { llmOpsApi } from '@/api/llmOps'
import { DEFAULT_WORKFLOW_POLICIES } from '@/constants/llmOpsWorkflow'

const FULL_LIST_PARAMS = { page_size: 10000 }
const DATA_HEAVY_SECTIONS = new Set([
  'channels',
  'metaModels',
  'providers',
  'reconciler',
  'reseller'
])
const sectionKeys = new Set([
  'monitor',
  'metaModels',
  'providers',
  'taskLogs',
  'channels',
  'globalConfig',
  'reseller',
  'workflow',
  'reconciler',
  'audit'
])
const activeSection = ref(initialActiveSection())
const loading = ref(false)
const backgroundLoading = ref(false)
const secondaryDataLoaded = ref(false)
const secondaryRefreshQueued = ref(false)

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
const resaleWorkflowConfig = ref(null)
const listings = ref([])
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
const resalePublishingDrawerOpen = ref(false)
const resalePublishingInitialModelId = ref(null)
const { showSuccess, showError, showInfo } = useToast()
const { t } = useI18n()

const simulation = ref({
  channel: '',
  status: 'priority'
})

const displayCurrencyOptions = computed(() => [
  { label: t('llmOps.currency.cny'), value: 'CNY' },
  { label: t('llmOps.currency.usd'), value: 'USD' }
])

const simulationStatusOptions = computed(() => [
  { label: t('llmOps.filters.priority'), value: 'priority' },
  { label: t('llmOps.filters.allModels'), value: 'all' },
  { label: t('llmOps.status.currencyMismatch'), value: 'currency_mismatch' },
  { label: t('llmOps.status.missingChannel'), value: 'missing_channel' },
  { label: t('llmOps.status.unlisted'), value: 'unlisted' },
  { label: t('llmOps.status.ready'), value: 'ready' }
])

const monitorStatusLabelKeys = {
  currency_mismatch: 'llmOps.status.currencyMismatch',
  low_coverage: 'llmOps.status.lowCoverage',
  missing_channel: 'llmOps.status.missingChannel',
  not_lowest: 'llmOps.status.notLowest',
  ready: 'llmOps.status.readyShort',
  unlisted: 'llmOps.status.unlisted'
}

const navIcons = {
  audit: ['M4 5h16', 'M4 12h16', 'M4 19h10'],
  channels: ['M4 7h16', 'M7 7v10', 'M17 7v10', 'M4 17h16'],
  globalConfig: ['M4 7h16', 'M7 7v10', 'M17 7v10', 'M4 17h16', 'M9 12h6'],
  metaModels: ['M12 3l8 4-8 4-8-4 8-4Z', 'M4 12l8 4 8-4', 'M4 17l8 4 8-4'],
  monitor: ['M4 19V5', 'M8 19v-6', 'M12 19v-9', 'M16 19v-4', 'M20 19V8'],
  providers: ['M5 5h14v14H5Z', 'M9 9h6', 'M9 13h6', 'M9 17h3'],
  reconciler: [
    'M4 7h16',
    'M7 7v12',
    'M17 7v12',
    'M4 13h16',
    'M9 17h1',
    'M14 17h1'
  ],
  reseller: ['M6 8h12l-1 12H7L6 8Z', 'M9 8a3 3 0 0 1 6 0'],
  taskLogs: ['M5 4h14v16H5Z', 'M8 8h8', 'M8 12h8', 'M8 16h5'],
  workflow: [
    'M4 6h7',
    'M13 6h7',
    'M11 6l2 2-2 2',
    'M4 18h7',
    'M13 18h7',
    'M11 18l2-2-2-2',
    'M6 8v8',
    'M18 8v8'
  ]
}

const navItems = computed(() => [
  {
    key: 'monitor',
    label: t('llmOps.nav.monitor.label'),
    eyebrow: 'Monitor',
    description: t('llmOps.nav.monitor.description'),
    icon: navIcons.monitor
  },
  {
    key: 'metaModels',
    label: t('llmOps.nav.metaModels.label'),
    eyebrow: 'Meta Models',
    description: t('llmOps.nav.metaModels.description'),
    icon: navIcons.metaModels
  },
  {
    key: 'providers',
    label: t('llmOps.nav.providers.label'),
    eyebrow: 'Sources',
    description: t('llmOps.nav.providers.description'),
    icon: navIcons.providers
  },
  {
    key: 'taskLogs',
    label: t('llmOps.nav.taskLogs.label'),
    eyebrow: 'Task Logs',
    description: t('llmOps.nav.taskLogs.description'),
    icon: navIcons.taskLogs
  },
  {
    key: 'channels',
    label: t('llmOps.nav.channels.label'),
    eyebrow: 'Channels',
    description: t('llmOps.nav.channels.description'),
    icon: navIcons.channels
  },
  {
    key: 'reseller',
    label: t('llmOps.nav.reseller.label'),
    eyebrow: 'Reseller',
    description: t('llmOps.nav.reseller.description'),
    icon: navIcons.reseller
  },
  {
    key: 'workflow',
    label: t('llmOps.nav.workflow.label'),
    eyebrow: 'Workflow',
    description: t('llmOps.nav.workflow.description'),
    icon: navIcons.workflow
  },
  {
    key: 'globalConfig',
    label: t('llmOps.nav.globalConfig.label'),
    eyebrow: 'Global Config',
    description: t('llmOps.nav.globalConfig.description'),
    icon: navIcons.globalConfig
  },
  {
    key: 'reconciler',
    label: t('llmOps.nav.reconciler.label'),
    eyebrow: 'Reconciliation',
    description: t('llmOps.nav.reconciler.description'),
    icon: navIcons.reconciler
  },
  {
    key: 'audit',
    label: t('llmOps.nav.audit.label'),
    eyebrow: 'Audit',
    description: t('llmOps.nav.audit.description'),
    icon: navIcons.audit
  }
])

function findNavItem(key) {
  return navItems.value.find((item) => item.key === key)
}

function createNavGroup(key, labelKey, itemKeys) {
  return {
    key,
    label: t(labelKey),
    items: itemKeys.map(findNavItem).filter(Boolean)
  }
}

const navGroups = computed(() =>
  [
    createNavGroup('overview', 'llmOps.navGroups.overview', ['monitor']),
    createNavGroup('catalog', 'llmOps.navGroups.catalog', [
      'metaModels',
      'providers',
      'taskLogs'
    ]),
    createNavGroup('distribution', 'llmOps.navGroups.distribution', [
      'channels',
      'reseller',
      'workflow'
    ]),
    createNavGroup('governance', 'llmOps.navGroups.governance', [
      'reconciler',
      'audit',
      'globalConfig'
    ])
  ].filter((group) => group.items.length > 0)
)

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
    label: resalePlatformOptionLabel(platform),
    value: String(platform.id)
  }))
)

const platformTypeLabelKeys = {
  agione: 'llmOps.resalePlatform.types.agione',
  api_gateway: 'llmOps.resalePlatform.types.apiGateway',
  cloud_marketplace: 'llmOps.resalePlatform.types.cloudMarketplace',
  internal: 'llmOps.resalePlatform.types.internal',
  other: 'llmOps.resalePlatform.types.other',
  reseller: 'llmOps.resalePlatform.types.reseller'
}

const environmentLabelKeys = {
  production: 'llmOps.resalePlatform.environments.production',
  sandbox: 'llmOps.resalePlatform.environments.sandbox',
  staging: 'llmOps.resalePlatform.environments.staging',
  test: 'llmOps.resalePlatform.environments.test'
}

function resalePlatformOptionLabel(platform) {
  const typeLabelKey = platformTypeLabelKeys[platform.platform_type]
  const typeLabel = typeLabelKey ? t(typeLabelKey) : platform.platform_type
  const environmentLabelKey = environmentLabelKeys[platform.environment]
  const regionLabel = platform.region_name || platform.region_code
  const environmentLabel = environmentLabelKey ? t(environmentLabelKey) : ''
  const meta = [typeLabel, regionLabel, environmentLabel]
    .filter(Boolean)
    .join(' · ')
  return meta ? `${platform.name} · ${meta}` : platform.name
}

const simulationChannelOptions = computed(() => [
  { label: t('llmOps.filters.allChannels'), value: '' },
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
const showGlobalToolbar = computed(() => activeSection.value !== 'workflow')
const showHeroActions = computed(
  () => showGlobalToolbar.value || showPlatformControl.value
)

const workflowConfigForWorkspace = computed(
  () => resaleWorkflowConfig.value?.config || null
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
  return `1 USD = ${rate} CNY`
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
        status_label: localizedMonitorStatusLabel(row.status),
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
      label: t('llmOps.kpi.ready.label'),
      value: `${readyRows.value.length}/${modelCount}`,
      badge: `${readyRate}%`,
      hint: t('llmOps.kpi.ready.hint', { count: readyRows.value.length }),
      progress: readyRate,
      tone: readyRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-emerald-500'
    },
    {
      label: t('llmOps.kpi.procurement.label'),
      value: `${procuredCount.value}/${modelCount}`,
      badge: `${procurementRate}%`,
      hint: t('llmOps.kpi.procurement.hint', {
        missing: missingChannelRows.value.length,
        currency: currencyMismatchRows.value.length
      }),
      progress: procurementRate,
      tone: procurementRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-agione-500'
    },
    {
      label: t('llmOps.kpi.listing.label'),
      value: `${listedCount.value}/${modelCount}`,
      badge: `${listingRate}%`,
      hint: t('llmOps.kpi.listing.hint', {
        unlisted: unlistedRows.value.length,
        nonLowest: nonLowestRows.value.length
      }),
      progress: listingRate,
      tone: listingRate >= 80 ? 'good' : 'warn',
      barClass: 'bg-cyan-500'
    },
    {
      label: t('llmOps.kpi.channels.label'),
      value: channelCount,
      badge: t('llmOps.kpi.channels.badge', {
        count: providerCollectionSources.value.length
      }),
      hint: t('llmOps.kpi.channels.hint'),
      progress: channelCount ? 100 : 0,
      tone: channelCount ? 'good' : 'danger',
      barClass: 'bg-violet-500'
    },
    {
      label: t('llmOps.kpi.reconciliation.label'),
      value: summary.value.kpis?.reconciliation_anomalies || 0,
      badge:
        summary.value.kpis?.reconciliation_anomalies || 0
          ? t('llmOps.status.needsHandling')
          : t('llmOps.status.normal'),
      hint: t('llmOps.kpi.reconciliation.hint'),
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
    label: t('llmOps.queue.fillChannelPrice.label'),
    hint: t('llmOps.queue.fillChannelPrice.hint'),
    value: missingChannelRows.value.length,
    tone: missingChannelRows.value.length ? 'danger' : 'good',
    section: 'channels'
  },
  {
    label: t('llmOps.queue.configureExchange.label'),
    hint: t('llmOps.queue.configureExchange.hint'),
    value: currencyMismatchRows.value.length,
    tone: currencyMismatchRows.value.length ? 'warn' : 'good',
    section: 'channels'
  },
  {
    label: t('llmOps.queue.publishToPlatform.label'),
    hint: t('llmOps.queue.publishToPlatform.hint'),
    value: unlistedRows.value.length,
    tone: unlistedRows.value.length ? 'warn' : 'good',
    section: 'reseller'
  },
  {
    label: t('llmOps.queue.switchLowestChannel.label'),
    hint: t('llmOps.queue.switchLowestChannel.hint'),
    value: nonLowestRows.value.length,
    tone: nonLowestRows.value.length ? 'warn' : 'good',
    section: 'reseller'
  },
  {
    label: t('llmOps.queue.addChannelCoverage.label'),
    hint: t('llmOps.queue.addChannelCoverage.hint'),
    value: lowCoverageRows.value.length,
    tone: lowCoverageRows.value.length ? 'warn' : 'good',
    section: 'channels'
  },
  {
    label: t('llmOps.queue.checkPriceSource.label'),
    hint: latestCollectionRun.value
      ? t('llmOps.queue.checkPriceSource.latestRun', {
          status: latestCollectionRun.value.status || '-',
          time: formatDateTime(
            latestCollectionRun.value.finished_at ||
              latestCollectionRun.value.started_at
          )
        })
      : t('llmOps.queue.checkPriceSource.empty'),
    value: collectionAttentionCount.value,
    tone: collectionAttentionCount.value ? 'danger' : 'good',
    section: 'taskLogs'
  },
  {
    label: t('llmOps.queue.handleReconciliation.label'),
    hint: t('llmOps.queue.handleReconciliation.hint'),
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

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}

function monitorModelSubtitle(row) {
  const name = String(row.model_name || '').trim()
  const code = String(row.model_code || '').trim()
  if (code && code !== name) return code
  return ''
}

async function refreshAll() {
  loading.value = true
  const section = activeSection.value
  try {
    await refreshCoreData()
    await refreshSectionData(section)
  } finally {
    loading.value = false
  }

  refreshSecondaryData({ force: true, silent: true })
}

async function refreshCoreData() {
  const [
    sourceRes,
    runRes,
    providerRes,
    modelRes,
    channelRes,
    platformRes,
    summaryRes
  ] = await Promise.all([
    llmOpsApi.listCollectionSources(FULL_LIST_PARAMS),
    llmOpsApi.listCollectionRuns(FULL_LIST_PARAMS),
    llmOpsApi.listProviders(FULL_LIST_PARAMS),
    llmOpsApi.listModels(FULL_LIST_PARAMS),
    llmOpsApi.listChannels(FULL_LIST_PARAMS),
    llmOpsApi.listResalePlatforms(FULL_LIST_PARAMS),
    llmOpsApi.getSummary(summaryParams())
  ])
  sources.value = extract(sourceRes)
  collectionRuns.value = extract(runRes)
  providers.value = extract(providerRes)
  models.value = extract(modelRes)
  channels.value = extract(channelRes)
  resalePlatforms.value = extract(platformRes)
  summary.value = extract(summaryRes)
  await loadResaleWorkflowConfig()
}

async function refreshSecondaryData({ force = false, silent = false } = {}) {
  if (backgroundLoading.value) {
    if (force) {
      secondaryDataLoaded.value = false
      secondaryRefreshQueued.value = true
    }
    return
  }
  if (force) {
    secondaryDataLoaded.value = false
  }
  backgroundLoading.value = true
  try {
    await Promise.all([
      refreshMetaModels(),
      refreshChannelPricingData(),
      refreshModelPriceItems(),
      refreshResaleListings(),
      refreshReconciliationRecords()
    ])
    secondaryDataLoaded.value = true
  } catch (error) {
    if (!silent) {
      showError(errorMessage(error, '加载 LLM Ops 扩展数据失败。'))
    }
  } finally {
    backgroundLoading.value = false
    if (secondaryRefreshQueued.value) {
      secondaryRefreshQueued.value = false
      refreshSecondaryData({ force: true, silent: true })
    }
  }
}

async function refreshSectionData(section) {
  if (!DATA_HEAVY_SECTIONS.has(section)) return
  if (section === 'providers' || section === 'metaModels') {
    await Promise.all([refreshMetaModels(), refreshModelPriceItems()])
    return
  }
  if (section === 'channels') {
    await Promise.all([refreshChannelPricingData(), refreshModelPriceItems()])
    return
  }
  if (section === 'reseller') {
    await Promise.all([refreshModelPriceItems(), refreshResaleListings()])
    return
  }
  if (section === 'reconciler') {
    await refreshReconciliationRecords()
  }
}

async function refreshMetaModels() {
  const response = await llmOpsApi.listMetaModels(FULL_LIST_PARAMS)
  metaModels.value = extract(response)
}

async function refreshChannelPricingData() {
  const [priceRes, itemRes] = await Promise.all([
    llmOpsApi.listChannelModelPrices(FULL_LIST_PARAMS),
    llmOpsApi.listChannelPriceItems({
      ...FULL_LIST_PARAMS,
      is_current: 'true'
    })
  ])
  channelPrices.value = extract(priceRes)
  channelPriceItems.value = extract(itemRes)
}

async function refreshModelPriceItems() {
  const response = await llmOpsApi.listModelPriceItems({
    ...FULL_LIST_PARAMS,
    is_current: 'true'
  })
  modelPriceItems.value = extract(response)
}

async function refreshResaleListings() {
  const response = await llmOpsApi.listResaleListings(FULL_LIST_PARAMS)
  listings.value = extract(response)
}

async function refreshReconciliationRecords() {
  const response = await llmOpsApi.listReconciliationRecords(FULL_LIST_PARAMS)
  records.value = extract(response)
}

async function refreshLight() {
  const [priceRes, channelPriceItemRes, listingRes, recordRes, summaryRes] =
    await Promise.all([
      llmOpsApi.listChannelModelPrices(FULL_LIST_PARAMS),
      llmOpsApi.listChannelPriceItems({
        ...FULL_LIST_PARAMS,
        is_current: 'true'
      }),
      llmOpsApi.listResaleListings(FULL_LIST_PARAMS),
      llmOpsApi.listReconciliationRecords(FULL_LIST_PARAMS),
      llmOpsApi.getSummary(summaryParams())
    ])
  channelPrices.value = extract(priceRes)
  channelPriceItems.value = extract(channelPriceItemRes)
  listings.value = extract(listingRes)
  records.value = extract(recordRes)
  summary.value = extract(summaryRes)
}

async function refreshCollectionRuns() {
  const [sourceRes, runRes] = await Promise.all([
    llmOpsApi.listCollectionSources(FULL_LIST_PARAMS),
    llmOpsApi.listCollectionRuns(FULL_LIST_PARAMS)
  ])
  sources.value = extract(sourceRes)
  collectionRuns.value = extract(runRes)
}

async function loadResaleWorkflowConfig(
  platformId = selectedResalePlatformId.value
) {
  if (!platformId) {
    resaleWorkflowConfig.value = null
    return
  }
  try {
    const response = await llmOpsApi.getResaleWorkflowConfig(platformId)
    if (String(platformId) === String(selectedResalePlatformId.value)) {
      resaleWorkflowConfig.value = response.data?.data || response.data
    }
  } catch (error) {
    resaleWorkflowConfig.value = null
  }
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
      status_label: t('llmOps.status.currencyMismatch'),
      status_tone: 'info',
      status_priority: 1
    }
  }
  if (!bestChannel) {
    return {
      status_label: t('llmOps.status.missingChannel'),
      status_tone: 'danger',
      status_priority: 1
    }
  }
  if (!isAgioneListed) {
    return {
      status_label: t('llmOps.status.readyToList'),
      status_tone: 'warn',
      status_priority: 2
    }
  }
  if (!hasLowestListing) {
    return {
      status_label: t('llmOps.status.notLowest'),
      status_tone: 'warn',
      status_priority: 3
    }
  }
  if (coverageCount <= 1) {
    return {
      status_label: t('llmOps.status.lowCoverage'),
      status_tone: 'info',
      status_priority: 4
    }
  }
  return {
    status_label: t('llmOps.status.ready'),
    status_tone: 'success',
    status_priority: 5
  }
}

function monitorStatusTone(status) {
  const tones = {
    currency_mismatch: 'info',
    not_lowest: 'warn',
    missing_channel: 'danger',
    unlisted: 'warn',
    low_coverage: 'info',
    ready: 'success'
  }
  return tones[status] || 'success'
}

function localizedMonitorStatusLabel(status) {
  const labelKey = monitorStatusLabelKeys[status]
  return labelKey ? t(labelKey) : t('llmOps.status.readyShort')
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
  if (
    DATA_HEAVY_SECTIONS.has(section) &&
    !secondaryDataLoaded.value &&
    !loading.value
  ) {
    refreshSectionData(section).catch((error) => {
      showError(errorMessage(error, '加载当前页面数据失败。'))
    })
  }
})

watch(selectedResalePlatformId, (platformId) => {
  if (platformId) {
    localStorage.setItem('llm_ops_resale_platform', platformId)
  }
  loadResaleWorkflowConfig(platformId)
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

function handleWorkflowConfigSaved(payload) {
  resaleWorkflowConfig.value = payload
}

function handlePlatformSaved() {
  closePlatformModal()
  refreshAll()
}

function mergeResaleListings(updatedItems) {
  if (!Array.isArray(updatedItems) || !updatedItems.length) return
  const byId = new Map(listings.value.map((item) => [String(item.id), item]))
  updatedItems.forEach((item) => {
    if (item?.id) byId.set(String(item.id), item)
  })
  listings.value = Array.from(byId.values())
}

function openListingActionDrawer({ modelId, kind }) {
  if (kind === 'configure-channel') {
    activeSection.value = 'channels'
    showError(t('llmOps.messages.configureChannelFirst'))
    return
  }
  if (!agionePlatform.value) {
    showError(t('llmOps.messages.configurePlatformFirst'))
    return
  }
  // Direct row actions (remove / restore / offline) are handled by
  // StatusBoard itself. Create / view / edit flows open the workspace.
  if (!['create', 'view', 'edit'].includes(kind)) return
  resalePublishingInitialModelId.value = modelId || null
  resalePublishingDrawerOpen.value = true
}

function openResalePublishingWorkspace(payload = {}) {
  resalePublishingInitialModelId.value = payload?.modelId || null
  resalePublishingDrawerOpen.value = true
}

function mapWorkspaceListingToPayload(item) {
  const inApi = Number(item.priceIn) || 0
  const outApi = Number(item.priceOut) || 0
  return {
    platform: agionePlatform.value?.id,
    model: item.modelId,
    channel: item.channelId,
    currency: displayCurrency.value,
    retail_input_price_per_million: inApi.toFixed(6),
    retail_output_price_per_million: outApi.toFixed(6),
    retail_cache_input_price_per_million:
      item.priceCacheIn === null || item.priceCacheIn === undefined
        ? null
        : (Number(item.priceCacheIn) || 0).toFixed(6),
    is_active: true
  }
}

async function handleResaleWorkspacePublished(payload) {
  if (!payload || !payload.listings || !payload.listings.length) {
    showInfo(t('llmOps.messages.noListingsToPublish'))
    return
  }
  const publishListings = payload.listings.filter(
    (item) => Number(item.priceIn) > 0 && Number(item.priceOut) > 0
  )
  const items = publishListings.map(mapWorkspaceListingToPayload)
  if (!items.length) {
    showError(t('llmOps.messages.invalidListingPrices'))
    return
  }
  try {
    const response = await llmOpsApi.bulkUpsertResaleListings(items)
    const submittedListings = extract(response)
    const autoConfirmedCount = await confirmAutoApprovedListings(
      submittedListings,
      publishListings
    )
    const messageKey = autoConfirmedCount
      ? 'llmOps.messages.publishAutoConfirmed'
      : 'llmOps.messages.publishSubmitted'
    showSuccess(
      t(messageKey, {
        count: items.length,
        confirmed: autoConfirmedCount
      })
    )
    resalePublishingDrawerOpen.value = false
    refreshLight()
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || t('llmOps.messages.submitFailed'))
  }
}

async function confirmAutoApprovedListings(submittedListings, sourceListings) {
  const policies = currentWorkflowPolicies()
  if (!policies.auto_approve_enabled || !policies.auto_apply_after_approval) {
    return 0
  }
  const limit = Number(
    resaleWorkflowConfig.value?.config?.runtime?.auto_approve_max_margin_rate
  )
  if (!Number.isFinite(limit)) return 0

  const publishIds = []
  const updateIds = []
  submittedListings.forEach((listing, index) => {
    const source = sourceListings[index]
    const margin = Number(source?.margin)
    if (!Number.isFinite(margin) || margin > limit) return
    if (listing.workflow_status === 'pending_publish') {
      publishIds.push(listing.id)
    } else if (listing.workflow_status === 'pending_update') {
      updateIds.push(listing.id)
    }
  })

  const actions = [
    { ids: publishIds, action: 'confirm_publish' },
    { ids: updateIds, action: 'confirm_update' }
  ].filter((item) => item.ids.length)

  await Promise.all(
    actions.map((item) =>
      llmOpsApi.bulkTransitionResaleListings({
        platform: agionePlatform.value?.id,
        listings: item.ids,
        action: item.action
      })
    )
  )
  return publishIds.length + updateIds.length
}

function currentWorkflowPolicies() {
  return {
    ...DEFAULT_WORKFLOW_POLICIES,
    ...(resaleWorkflowConfig.value?.config?.policies || {})
  }
}

async function handleResaleWorkspaceDraft(payload) {
  if (!payload || !payload.listings || !payload.listings.length) {
    showInfo(t('llmOps.messages.noDraftsToSave'))
    return
  }
  if (!payload.hasChanges) {
    showInfo(t('llmOps.messages.noChangesToSave'))
    return
  }
  const items = payload.listings
    .filter((item) => item.hasChanges !== false)
    .map(mapWorkspaceListingToPayload)
  if (!items.length) {
    showInfo(t('llmOps.messages.noChangesToSave'))
    return
  }
  try {
    await llmOpsApi.bulkDraftResaleListings(items)
    showSuccess(t('llmOps.messages.draftsSaved', { count: items.length }))
    resalePublishingDrawerOpen.value = false
    refreshLight()
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || t('llmOps.messages.saveFailed'))
  }
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

onMounted(() => {
  document.body.classList.add('llm-ops-theme')
  refreshAll()
})

onBeforeUnmount(() => {
  document.body.classList.remove('llm-ops-theme')
})
</script>

<style scoped>
:global(body.llm-ops-theme) {
  padding: 0 !important;
}

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

.page-hero {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.page-hero-copy {
  min-width: 0;
}

.page-hero-eyebrow {
  margin-top: 0;
}

.page-hero-title {
  font-size: 2rem;
  line-height: 1.1;
}

.page-hero-description {
  max-width: 30rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.5;
}

.page-hero-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
  max-width: 100%;
}

.page-hero-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem;
}

.page-toolbar-control {
  min-height: 2.5rem;
  gap: 0.5rem;
  border-radius: 10px;
  padding: 0.375rem 0.5rem;
  white-space: nowrap;
}

.page-toolbar-control > span {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #475569;
}

.page-toolbar-button {
  min-height: 2.5rem;
  border-radius: 10px;
  padding: 0.375rem 0.625rem;
  white-space: nowrap;
}

.refresh-action-button {
  min-width: 5.5rem;
  border-color: #cbd5e1;
  background-color: #ffffff;
  color: #334155;
  font-weight: 700;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.refresh-action-button:hover:not(:disabled) {
  border-color: #a5b4fc;
  background-color: #eef2ff;
  color: #4338ca;
  box-shadow: 0 8px 18px rgba(79, 70, 229, 0.12);
  transform: translateY(-1px);
}

.refresh-action-button:disabled {
  cursor: wait;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  color: #94a3b8;
  box-shadow: none;
}

.refresh-action-icon {
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
}

.refresh-action-icon.is-spinning {
  animation: llm-ops-refresh-spin 900ms linear infinite;
}

@keyframes llm-ops-refresh-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.page-toolbar-chip {
  display: inline-flex;
  max-width: 10.75rem;
  min-height: 2.5rem;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background-color: #f8fafc;
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (min-width: 1280px) {
  .page-hero {
    flex-direction: row;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .page-hero-copy {
    max-width: 26rem;
  }

  .page-hero-actions {
    align-items: flex-end;
    flex: 0 0 auto;
    max-width: 31rem;
  }

  .page-hero-group {
    justify-content: flex-end;
  }
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
  height: 1rem;
  width: 1rem;
  flex-shrink: 0;
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
