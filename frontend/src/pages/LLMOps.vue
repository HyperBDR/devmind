<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div class="llm-ops-page h-full min-h-[calc(100vh-4rem)] bg-slate-50">
      <div class="flex h-full min-h-[calc(100vh-4rem)] w-full gap-0">
        <LLMOpsSidebar
          :active-section="activeSection"
          :collapsed="sidebarCollapsed"
          :expanded-group-keys="expandedNavGroupKeys"
          :mobile-open="mobileNavigationOpen"
          :nav-groups="navGroups"
          :toggle-label="sidebarToggleLabel"
          @close-mobile="mobileNavigationOpen = false"
          @select-item="selectSidebarNavItem"
          @toggle-group="toggleNavGroup"
          @toggle-sidebar="toggleSidebar"
        />

        <main
          :class="[
            'llm-ops-content min-w-0 flex-1',
            sidebarCollapsed ? 'lg:ml-20' : 'lg:ml-72'
          ]"
        >
          <LLMOpsHeader
            v-model:active-section="activeSection"
            v-model:display-currency="displayCurrency"
            v-model:selected-resale-platform-id="selectedResalePlatformId"
            :active-nav="activeNav"
            :agione-platform="agionePlatform"
            :actions-disabled="Boolean(pageError) || loading"
            :exchange-rate-label="exchangeRateLabel"
            :loading="loading"
            :mobile-navigation-open="mobileNavigationOpen"
            :resale-platform-options="resalePlatformOptions"
            @open-navigation="mobileNavigationOpen = true"
            @open-platform="openPlatformModal"
            @refresh="handleRefreshAll"
          />

          <div
            v-if="loading"
            class="llm-ops-loading-skeleton px-5 py-6 lg:px-7"
            role="status"
            aria-live="polite"
          >
            <div class="mb-4 flex items-center gap-3 text-sm text-slate-600">
              <span
                class="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
                aria-hidden="true"
              />
              <span>{{ loadingSectionLabel }}</span>
            </div>
            <div class="grid animate-pulse gap-4 md:grid-cols-3">
              <div
                v-for="index in 3"
                :key="index"
                class="h-28 rounded-xl border border-slate-200 bg-white"
              />
            </div>
            <div
              class="mt-4 h-72 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          </div>
          <LLMOpsErrorState
            v-else-if="pageError"
            class="my-6"
            :message="pageError"
            @retry="handleRefreshAll"
          />
          <div
            v-else
            :class="[
              'llm-ops-body px-5 py-5 lg:px-7',
              activeSection === 'audit'
                ? 'flex h-[calc(100vh-10.75rem)] min-h-0 flex-col'
                : 'space-y-6'
            ]"
          >
            <LLMOpsMonitorDashboard
              v-if="activeSection === 'monitor'"
              v-model:simulation-status="simulationStatus"
              :kpi-cards="kpiCards"
              :monitor-model-subtitle="monitorModelSubtitle"
              :monitor-table-rows="monitorTableRows"
              :simulation-status-options="simulationStatusOptions"
              @navigate-to-section="onNavigateToSection"
              @navigate-to-workspace="onNavigateToWorkspace"
            />

            <template v-else-if="activeSection === 'reseller'">
              <section
                v-if="resaleWorkspaceFocusModelId"
                class="panel overflow-hidden p-0"
              >
                <header
                  class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-4"
                >
                  <div class="min-w-0">
                    <p
                      class="text-[11px] font-bold uppercase tracking-[0.18em] text-agione-600"
                    >
                      Model Publishing Workspace
                    </p>
                    <h2 class="mt-0.5 text-base font-bold text-slate-900">
                      {{ t('llmOps.publishingDrawer.title') }}
                    </h2>
                  </div>
                  <div class="flex items-center gap-2">
                    <button
                      type="button"
                      class="btn-secondary"
                      @click="closeInlineWorkspace"
                    >
                      {{ t('llmOps.publishingDrawer.back') }}
                    </button>
                    <button
                      type="button"
                      class="btn-secondary btn-action-save"
                      :disabled="!inlineCanDraft || inlineSaving"
                      @click="handleInlineSaveDraft"
                    >
                      {{ t('llmOps.publishingDrawer.saveDraft') }}
                    </button>
                    <button
                      type="button"
                      class="btn-primary btn-action-submit"
                      :disabled="!inlineCanPublish || inlineSaving"
                      @click="handleInlinePublish"
                    >
                      {{
                        inlineSaving
                          ? t('llmOps.publishingDrawer.submitting')
                          : t('llmOps.publishingDrawer.submit')
                      }}
                    </button>
                  </div>
                </header>
                <div class="px-5 py-5">
                  <ResalePublishingWorkspace
                    :key="inlineWorkspaceKey"
                    ref="inlineWorkspaceRef"
                    :initial-model-id="resaleWorkspaceFocusModelId"
                    :initial-auto-listing="resaleWorkspaceFocusAutoListing"
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
                    :display-currency="summaryDisplayCurrency"
                    :exchange-rate="exchangeRate"
                    :workflow-config="workflowConfigForWorkspace"
                    @change="onInlineWorkspaceChange"
                  />
                </div>
              </section>

              <AgioneListingStatusBoard
                :agione-platform="agionePlatform"
                :providers="providers"
                :models="models"
                :listings="listings"
                :summary="summary"
                :platform-count="activeResalePlatforms.length"
                :point-conversion="pointConversion"
                :display-currency="summaryDisplayCurrency"
                :exchange-rate="exchangeRate"
                :focus-model-id="resaleWorkspaceFocusModelId"
                @refresh="handleRefreshAll"
                @listings-updated="mergeResaleListings"
                @action="openListingActionDrawer"
                @open-workspace="openResalePublishingWorkspace"
              />
            </template>

            <CollectionHealthPanel
              v-else-if="activeSection === 'collectionHealth'"
              :sources="providerCollectionSources"
              :runs="collectionRuns"
            />

            <ChannelPriceMatrixPanel
              v-else-if="activeSection === 'channelMatrix'"
              :summary="summary"
              :channels="channels"
              @navigate-to-detail="openChannelListingDetail"
              @navigate-to-section="onNavigateToSection"
            />

            <ModelWorkbenchPanel
              v-else-if="activeSection === 'modelWorkbench'"
              :focus-model-id="operationTargetModelId"
              :summary="summary"
              :models="models"
              :channels="channels"
              :channel-offerings="channelOfferings"
              :price-items="modelPriceItems"
              :channel-price-items="channelPriceItems"
              :listings="listings"
              :records="records"
              @refresh="refreshAll(activeSection)"
            />

            <ListingRiskPanel
              v-else-if="activeSection === 'listingRisk'"
              :summary="summary"
            />

            <PriceChangePanel
              v-else-if="activeSection === 'priceChanges'"
              :focus-model-id="operationTargetModelId"
              :channel-history="channelPriceHistory"
              :channel-versions="channelPriceVersions"
              :listing-history="listingPriceHistory"
              :official-history="officialPriceHistory"
              :price-items="modelPriceItems"
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
              @saved="handleRefreshAll"
            />

            <CollectionRunLogPanel
              v-else-if="activeSection === 'taskLogs'"
              :runs="collectionRuns"
              :sources="sources"
              @refresh="handleRefreshAll"
            />

            <ProviderManagement
              v-else-if="activeSection === 'providers'"
              :focus-source-id="operationTargetSourceId"
              :providers="providers"
              :sources="providerCollectionSources"
              :collection-runs="collectionRuns"
              @refresh="refreshProviderManagementData"
              @manual-price-saved="handleManualPriceSaved"
            />

            <MetaModelManagement
              v-else-if="activeSection === 'metaModels'"
              :providers="providers"
              @refresh="refreshMetaModelManagementData"
            />

            <ChannelManagement
              v-else-if="activeSection === 'channels'"
              :focus-model-id="operationTargetModelId"
              :channels="channels"
              :providers="providers"
              :meta-models="metaModels"
              :models="models"
              :channel-prices="channelPrices"
              :channel-offerings="channelOfferings"
              :channel-price-items="channelPriceItems"
              :price-items="modelPriceItems"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              :prepare-model-management="preloadChannelModelData"
              @refresh="refreshChannelManagementData"
            />

            <ReconciliationPanel
              v-else-if="activeSection === 'reconciler'"
              :focus-model-id="operationTargetModelId"
              :channels="channels"
              :models="models"
              :records="records"
              @refresh="handleRefreshAll"
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
      :display-currency="summaryDisplayCurrency"
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
import '@/components/llm-ops/llmOpsSelects.css'
import '@/components/llm-ops/llmOpsTables.css'
import '@/components/llm-ops/llmOpsShell.css'

import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from 'vue'
import { useI18n } from 'vue-i18n'

import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import LLMOpsErrorState from '@/components/llm-ops/LLMOpsErrorState.vue'
import LLMOpsHeader from '@/components/llm-ops/LLMOpsHeader.vue'
import LLMOpsSidebar from '@/components/llm-ops/LLMOpsSidebar.vue'
import { useLLMOpsData } from '@/composables/useLLMOpsData'
import { useLLMOpsMonitor } from '@/composables/useLLMOpsMonitor'
import {
  SECTION_KEYS,
  useLLMOpsNavigation
} from '@/composables/useLLMOpsNavigation'
import { useLLMOpsResalePublishing } from '@/composables/useLLMOpsResalePublishing'
import { parseLLMOpsOperationTarget } from '@/utils/llmOpsOperationEntry'

const asyncPanel = (loader) =>
  defineAsyncComponent({
    loader,
    loadingComponent: BaseLoading,
    delay: 120,
    timeout: 30000
  })

const AgioneListingStatusBoard = asyncPanel(
  () => import('@/components/llm-ops/AgioneListingStatusBoard.vue')
)
const AuditLogPanel = asyncPanel(
  () => import('@/components/llm-ops/AuditLogPanel.vue')
)
const ChannelManagement = asyncPanel(
  () => import('@/components/llm-ops/ChannelManagement.vue')
)
const ChannelPriceMatrixPanel = asyncPanel(
  () => import('@/components/llm-ops/ChannelPriceMatrixPanel.vue')
)
const CollectionHealthPanel = asyncPanel(
  () => import('@/components/llm-ops/CollectionHealthPanel.vue')
)
const CollectionRunLogPanel = asyncPanel(
  () => import('@/components/llm-ops/CollectionRunLogPanel.vue')
)
const GlobalConfigPanel = asyncPanel(
  () => import('@/components/llm-ops/GlobalConfigPanel.vue')
)
const ListingRiskPanel = asyncPanel(
  () => import('@/components/llm-ops/ListingRiskPanel.vue')
)
const LLMOpsMonitorDashboard = asyncPanel(
  () => import('@/components/llm-ops/LLMOpsMonitorDashboard.vue')
)
const ModelWorkbenchPanel = asyncPanel(
  () => import('@/components/llm-ops/ModelWorkbenchPanel.vue')
)
const MetaModelManagement = asyncPanel(
  () => import('@/components/llm-ops/MetaModelManagement.vue')
)
const PriceChangePanel = asyncPanel(
  () => import('@/components/llm-ops/PriceChangePanel.vue')
)
const ProviderManagement = asyncPanel(
  () => import('@/components/llm-ops/ProviderManagement.vue')
)
const ReconciliationPanel = asyncPanel(
  () => import('@/components/llm-ops/ReconciliationPanel.vue')
)
const ResalePlatformModal = asyncPanel(
  () => import('@/components/llm-ops/ResalePlatformModal.vue')
)
const ResalePublishingDrawer = asyncPanel(
  () => import('@/components/llm-ops/ResalePublishingDrawer.vue')
)
const ResalePublishingWorkspace = asyncPanel(
  () => import('@/components/llm-ops/ResalePublishingWorkspace.vue')
)
const ResaleWorkflowConfigPanel = asyncPanel(
  () => import('@/components/llm-ops/ResaleWorkflowConfigPanel.vue')
)

const { t } = useI18n()

const {
  activeNav,
  activeSection,
  expandedNavGroupKeys,
  navGroups,
  selectNavItem,
  sidebarCollapsed,
  sidebarToggleLabel,
  toggleNavGroup,
  toggleSidebar
} = useLLMOpsNavigation()

const {
  channelOfferings,
  channelPriceHistory,
  channelPriceItems,
  channelPrices,
  channels,
  collectionRuns,
  displayCurrency,
  exchangeRate,
  exchangeRateLabel,
  invalidateSectionCache,
  listingPriceHistory,
  listings,
  loadResaleWorkflowConfig,
  loading,
  metaModels,
  modelPriceItems,
  officialPriceHistory,
  models,
  normalizeDisplayCurrency,
  pageError,
  pointConversion,
  preloadChannelModelData,
  preloadResalePublishingData,
  procurementRows,
  providerCollectionSources,
  providers,
  records,
  refreshAll,
  refreshChannelPricingData,
  refreshChannelManagementData,
  refreshLight,
  refreshMetaModelManagementData,
  refreshPlatformData,
  refreshProviderManagementData,
  refreshResalePlatformSelection,
  refreshSummary,
  resalePlatforms,
  resaleWorkflowConfig,
  selectedResalePlatformId,
  sources,
  summary,
  summaryDisplayCurrency
} = useLLMOpsData()

const {
  activeResalePlatforms,
  agionePlatform,
  closePlatformModal,
  editingPlatform,
  handleManualPriceSaved,
  handlePlatformSaved,
  handleResaleWorkspaceDraft,
  handleResaleWorkspacePublished,
  handleWorkflowConfigSaved,
  mergeResaleListings,
  openListingActionDrawer,
  openPlatformModal,
  openResalePublishingWorkspace,
  resalePlatformOptions,
  resalePublishingDrawerOpen,
  resalePublishingInitialModelId,
  showPlatformModal,
  workflowConfigForWorkspace
} = useLLMOpsResalePublishing({
  activeSection,
  collectionRuns,
  displayCurrency,
  listings,
  loading,
  loadResaleWorkflowConfig,
  metaModels,
  modelPriceItems,
  models,
  normalizeDisplayCurrency,
  preloadResalePublishingData,
  refreshChannelPricingData,
  refreshLight,
  refreshPlatformData,
  refreshProviderManagementData,
  refreshResalePlatformSelection,
  refreshSummary,
  resalePlatforms,
  resaleWorkflowConfig,
  selectedResalePlatformId,
  sources
})

const {
  kpiCards,
  monitorModelSubtitle,
  monitorTableRows,
  simulationStatus,
  simulationStatusOptions
} = useLLMOpsMonitor({
  summary
})

const resaleWorkspaceFocusModelId = ref(null)
const operationTargetModelId = ref(null)
const operationTargetSourceId = ref(null)
const operationTargetSection = ref('')
const resaleWorkspaceFocusAutoListing = ref(false)
const inlineWorkspacePayload = ref(null)
const inlineWorkspaceRef = ref(null)
const inlineSaving = ref(false)
const mobileNavigationOpen = ref(false)
let desktopMediaQuery = null
const inlineWorkspaceKey = computed(
  () => `inline-${resaleWorkspaceFocusModelId.value || 'new'}`
)
const loadingSectionLabel = computed(() =>
  t('llmOps.loading.section', {
    section: activeNav.value?.label || t('llmOps.shell.title')
  })
)

const inlineCanPublish = computed(() => {
  if (!inlineWorkspacePayload.value) return false
  const { hasChanges, listings, platformId, modelId } =
    inlineWorkspacePayload.value
  if (!platformId || !modelId || !hasChanges || !listings.length) return false
  const changedListings = listings.filter((item) => item.hasChanges !== false)
  if (!changedListings.length) return false
  return changedListings.every((listing) => {
    if (listing.hasTieredPrices) {
      return !Object.keys(listing.tierErrors || {}).length
    }
    return (
      !Object.keys(listing.tierErrors || {}).length &&
      !listing.priceBelowReference &&
      Number.isFinite(Number(listing.priceIn)) &&
      Number.isFinite(Number(listing.priceOut)) &&
      Number(listing.priceIn) > 0 &&
      Number(listing.priceOut) > 0
    )
  })
})

const inlineCanDraft = computed(() => {
  return Boolean(
    inlineWorkspacePayload.value?.platformId &&
      inlineWorkspacePayload.value?.listings?.length &&
      inlineWorkspacePayload.value?.hasChanges
  )
})

function onNavigateToWorkspace(payload) {
  const modelId =
    payload && typeof payload === 'object' ? payload.modelId : payload
  resaleWorkspaceFocusModelId.value = modelId || null
  resaleWorkspaceFocusAutoListing.value = Boolean(payload?.autoListing)
  activeSection.value = 'reseller'
}

function selectSidebarNavItem(groupKey, itemKey) {
  selectNavItem(groupKey, itemKey)
  mobileNavigationOpen.value = false
}

function handleDesktopViewportChange(event) {
  if (event.matches) mobileNavigationOpen.value = false
}

function onNavigateToSection(target) {
  const section = typeof target === 'object' ? target.section : target
  if (!SECTION_KEYS.has(section)) return
  if (target && typeof target === 'object' && target.modelId) {
    operationTargetModelId.value = target.modelId
    operationTargetSection.value = section
  }
  if (target && typeof target === 'object' && target.sourceId) {
    operationTargetSourceId.value = target.sourceId
  }
  activeSection.value = section
}

function openChannelListingDetail(modelId) {
  operationTargetModelId.value = modelId || null
  operationTargetSection.value = 'modelWorkbench'
  activeSection.value = 'modelWorkbench'
}

function onInlineWorkspaceChange(payload) {
  inlineWorkspacePayload.value = payload
}

function closeInlineWorkspace() {
  resaleWorkspaceFocusModelId.value = null
  resaleWorkspaceFocusAutoListing.value = false
  inlineWorkspacePayload.value = null
}

async function handleInlineSaveDraft() {
  if (!inlineCanDraft.value || inlineSaving.value) return
  inlineSaving.value = true
  try {
    const saved = await handleResaleWorkspaceDraft(inlineWorkspacePayload.value)
    if (saved) closeInlineWorkspace()
  } finally {
    inlineSaving.value = false
  }
}

async function handleInlinePublish() {
  if (!inlineCanPublish.value || inlineSaving.value) return
  inlineSaving.value = true
  try {
    const saved = await handleResaleWorkspacePublished(
      inlineWorkspacePayload.value
    )
    if (saved) closeInlineWorkspace()
  } finally {
    inlineSaving.value = false
  }
}

function handleRefreshAll() {
  return refreshAll(activeSection.value, {
    modelId: operationTargetModelId.value,
    force: true
  })
}

watch(displayCurrency, (currency) => {
  const normalized = normalizeDisplayCurrency(currency)
  if (normalized !== currency) {
    displayCurrency.value = normalized
    return
  }
  localStorage.setItem('llm_ops_display_currency', normalized)
  if (!loading.value) {
    invalidateSectionCache()
    handleRefreshAll()
  }
})

watch(activeSection, (section) => {
  if (!SECTION_KEYS.has(section)) return
  if (section !== operationTargetSection.value) {
    operationTargetModelId.value = null
  }
  refreshAll(section, {
    force: false,
    modelId:
      section === operationTargetSection.value
        ? operationTargetModelId.value
        : null
  })
})

onMounted(() => {
  document.body.classList.add('llm-ops-theme')
  desktopMediaQuery = window.matchMedia('(min-width: 1024px)')
  desktopMediaQuery.addEventListener('change', handleDesktopViewportChange)
  const operationTarget = parseLLMOpsOperationTarget(window.location.search)
  if (
    operationTarget.section === 'reseller' &&
    operationTarget.modelId !== null
  ) {
    resaleWorkspaceFocusModelId.value = operationTarget.modelId
  }
  const modelScopedSections = [
    'channels',
    'modelWorkbench',
    'priceChanges',
    'reconciler'
  ]
  if (
    modelScopedSections.includes(operationTarget.section) &&
    operationTarget.modelId !== null
  ) {
    operationTargetModelId.value = operationTarget.modelId
    operationTargetSection.value = operationTarget.section
  }
  if (
    operationTarget.section === 'providers' &&
    operationTarget.sourceId !== null
  ) {
    operationTargetSourceId.value = operationTarget.sourceId
  }
  handleRefreshAll().then((loaded) => {
    if (!loaded || !operationTarget.openPlatformConfig) return
    const platform = resalePlatforms.value.find(
      (item) => String(item.id) === String(operationTarget.platformId)
    )
    openPlatformModal(platform || agionePlatform.value)
  })
})

onBeforeUnmount(() => {
  if (desktopMediaQuery) {
    const mediaQuery = desktopMediaQuery
    mediaQuery.removeEventListener('change', handleDesktopViewportChange)
  }
  document.body.classList.remove('llm-ops-theme')
})
</script>
