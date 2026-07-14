<template>
  <AppLayout :show-sidebar="false" :full-bleed="true">
    <div class="llm-ops-page h-full min-h-[calc(100vh-4rem)] bg-slate-50">
      <div class="flex h-full min-h-[calc(100vh-4rem)] w-full gap-0">
        <LLMOpsSidebar
          :active-section="activeSection"
          :collapsed="sidebarCollapsed"
          :expanded-group-keys="expandedNavGroupKeys"
          :nav-groups="navGroups"
          :toggle-label="sidebarToggleLabel"
          @select-item="selectNavItem"
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
            :exchange-rate-label="exchangeRateLabel"
            :loading="loading"
            :nav-groups="navGroups"
            :resale-platform-options="resalePlatformOptions"
            @open-platform="openPlatformModal"
            @refresh="handleRefreshAll"
          />

          <BaseLoading v-if="loading" class="py-20" />
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
              :operational-channel-count="operationalChannelCount"
              :simulation-status-options="simulationStatusOptions"
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
                :price-items="modelPriceItems"
                :listings="listings"
                :summary="summary"
                :platform-count="activeResalePlatforms.length"
                :point-conversion="pointConversion"
                :display-currency="summaryDisplayCurrency"
                :exchange-rate="exchangeRate"
                :focus-model-id="resaleWorkspaceFocusModelId"
                @refresh="refreshLight"
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
            />

            <ModelWorkbenchPanel
              v-else-if="activeSection === 'modelWorkbench'"
              :summary="summary"
              :models="models"
              :channels="channels"
              :price-items="modelPriceItems"
              :channel-price-items="channelPriceItems"
              :listings="listings"
              :records="records"
            />

            <ListingRiskPanel
              v-else-if="activeSection === 'listingRisk'"
              :summary="summary"
            />

            <PriceChangePanel
              v-else-if="activeSection === 'priceChanges'"
              :channel-history="channelPriceHistory"
              :listing-history="listingPriceHistory"
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
              @refresh="refreshProviderManagementData"
              @manual-price-saved="handleManualPriceSaved"
            />

            <MetaModelManagement
              v-else-if="activeSection === 'metaModels'"
              :meta-models="metaModels"
              :providers="providers"
              :models="models"
              :price-items="modelPriceItems"
              @refresh="refreshMetaModelManagementData"
            />

            <ChannelManagement
              v-else-if="activeSection === 'channels'"
              :channels="channels"
              :providers="providers"
              :meta-models="metaModels"
              :models="models"
              :channel-prices="channelPrices"
              :channel-price-items="channelPriceItems"
              :price-items="modelPriceItems"
              :display-currency="displayCurrency"
              :exchange-rate="exchangeRate"
              @refresh="refreshChannelManagementData"
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

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import AgioneListingStatusBoard from '@/components/llm-ops/AgioneListingStatusBoard.vue'
import AuditLogPanel from '@/components/llm-ops/AuditLogPanel.vue'
import ChannelManagement from '@/components/llm-ops/ChannelManagement.vue'
import ChannelPriceMatrixPanel from '@/components/llm-ops/ChannelPriceMatrixPanel.vue'
import CollectionHealthPanel from '@/components/llm-ops/CollectionHealthPanel.vue'
import CollectionRunLogPanel from '@/components/llm-ops/CollectionRunLogPanel.vue'
import GlobalConfigPanel from '@/components/llm-ops/GlobalConfigPanel.vue'
import ListingRiskPanel from '@/components/llm-ops/ListingRiskPanel.vue'
import LLMOpsHeader from '@/components/llm-ops/LLMOpsHeader.vue'
import LLMOpsMonitorDashboard from '@/components/llm-ops/LLMOpsMonitorDashboard.vue'
import LLMOpsSidebar from '@/components/llm-ops/LLMOpsSidebar.vue'
import ModelWorkbenchPanel from '@/components/llm-ops/ModelWorkbenchPanel.vue'
import MetaModelManagement from '@/components/llm-ops/MetaModelManagement.vue'
import PriceChangePanel from '@/components/llm-ops/PriceChangePanel.vue'
import ProviderManagement from '@/components/llm-ops/ProviderManagement.vue'
import ReconciliationPanel from '@/components/llm-ops/ReconciliationPanel.vue'
import ResalePlatformModal from '@/components/llm-ops/ResalePlatformModal.vue'
import ResalePublishingDrawer from '@/components/llm-ops/ResalePublishingDrawer.vue'
import ResalePublishingWorkspace from '@/components/llm-ops/ResalePublishingWorkspace.vue'
import ResaleWorkflowConfigPanel from '@/components/llm-ops/ResaleWorkflowConfigPanel.vue'
import { useToast } from '@/composables/useToast'
import { useLLMOpsData } from '@/composables/useLLMOpsData'
import { useLLMOpsMonitor } from '@/composables/useLLMOpsMonitor'
import {
  DATA_HEAVY_SECTIONS,
  LIGHT_CORE_SECTIONS,
  SECTION_KEYS,
  useLLMOpsNavigation
} from '@/composables/useLLMOpsNavigation'
import { useLLMOpsResalePublishing } from '@/composables/useLLMOpsResalePublishing'
import { errorMessage } from '@/utils/llmOpsPagination'

const { showError } = useToast()
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
  channelPriceHistory,
  channelPriceItems,
  channelPrices,
  channels,
  collectionRuns,
  displayCurrency,
  exchangeRate,
  exchangeRateLabel,
  listingPriceHistory,
  listings,
  loadResaleWorkflowConfig,
  loading,
  metaModels,
  modelPriceItems,
  models,
  normalizeDisplayCurrency,
  pointConversion,
  preloadResalePublishingData,
  procurementRows,
  providerCollectionSources,
  providers,
  records,
  refreshAll,
  refreshChannelPricingData,
  refreshChannelManagementData,
  refreshCollectionRuns,
  refreshCoreData,
  refreshLight,
  refreshMetaModelManagementData,
  refreshPlatformData,
  refreshProviderManagementData,
  refreshSectionData,
  refreshSummary,
  resalePlatforms,
  resaleWorkflowConfig,
  secondaryDataLoaded,
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
  operationalChannelCount,
  simulationStatus,
  simulationStatusOptions
} = useLLMOpsMonitor({
  channels,
  procurementRows,
  summary
})

const resaleWorkspaceFocusModelId = ref(null)
const resaleWorkspaceFocusAutoListing = ref(false)
const inlineWorkspacePayload = ref(null)
const inlineWorkspaceRef = ref(null)
const inlineSaving = ref(false)
const inlineWorkspaceKey = computed(
  () => `inline-${resaleWorkspaceFocusModelId.value || 'new'}`
)

const inlineCanPublish = computed(() => {
  if (!inlineWorkspacePayload.value) return false
  const { hasChanges, listings, platformId, modelId } =
    inlineWorkspacePayload.value
  if (!platformId || !modelId || !hasChanges || !listings.length) return false
  const changedListings = listings.filter((item) => item.hasChanges !== false)
  if (!changedListings.length) return false
  return changedListings.every(
    (listing) =>
      !listing.priceBelowReference &&
      Number.isFinite(Number(listing.priceIn)) &&
      Number.isFinite(Number(listing.priceOut)) &&
      Number(listing.priceIn) > 0 &&
      Number(listing.priceOut) > 0
  )
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
  refreshAll(activeSection.value)
}

watch(displayCurrency, (currency) => {
  const normalized = normalizeDisplayCurrency(currency)
  if (normalized !== currency) {
    displayCurrency.value = normalized
    return
  }
  localStorage.setItem('llm_ops_display_currency', normalized)
  if (!loading.value) {
    if (activeSection.value === 'monitor') {
      refreshSummary('monitor')
    } else {
      refreshLight()
    }
  }
})

watch(activeSection, (section) => {
  if (!SECTION_KEYS.has(section)) return
  if (
    DATA_HEAVY_SECTIONS.has(section) &&
    !secondaryDataLoaded.value &&
    !loading.value
  ) {
    refreshSectionData(section).catch((error) => {
      showError(errorMessage(error, t('llmOps.dataErrors.loadSection')))
    })
  }
  if (
    !LIGHT_CORE_SECTIONS.has(section) &&
    !models.value.length &&
    !loading.value
  ) {
    refreshCoreData(section).catch((error) => {
      showError(errorMessage(error, t('llmOps.dataErrors.loadCoreModels')))
    })
  }
})

onMounted(() => {
  document.body.classList.add('llm-ops-theme')
  handleRefreshAll()
})

onBeforeUnmount(() => {
  document.body.classList.remove('llm-ops-theme')
})
</script>
