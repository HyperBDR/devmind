import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import { DEFAULT_WORKFLOW_POLICIES } from '@/constants/llmOpsWorkflow'
import { useToast } from '@/composables/useToast'
import { asArray, errorMessage, extract } from '@/utils/llmOpsPagination'

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

export function useLLMOpsResalePublishing({
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
  refreshLight,
  refreshPlatformData,
  refreshProviderManagementData,
  refreshSummary,
  resalePlatforms,
  resaleWorkflowConfig,
  selectedResalePlatformId,
  sources
}) {
  const { t } = useI18n()
  const { showSuccess, showError, showInfo } = useToast()
  const showPlatformModal = ref(false)
  const editingPlatform = ref(null)
  const resalePublishingDrawerOpen = ref(false)
  const resalePublishingInitialModelId = ref(null)

  const activeResalePlatforms = computed(() =>
    asArray(resalePlatforms.value).filter((item) => item.is_active !== false)
  )

  const resalePlatformOptions = computed(() =>
    activeResalePlatforms.value.map((platform) => ({
      label: resalePlatformOptionLabel(platform),
      value: String(platform.id)
    }))
  )

  const agionePlatform = computed(
    () =>
      activeResalePlatforms.value.find(
        (item) => String(item.id) === String(selectedResalePlatformId.value)
      ) ||
      activeResalePlatforms.value.find((item) => item.code === 'agione') ||
      activeResalePlatforms.value[0] ||
      null
  )

  const workflowConfigForWorkspace = computed(
    () => resaleWorkflowConfig.value?.config || null
  )

  watch(selectedResalePlatformId, (platformId) => {
    if (platformId) {
      localStorage.setItem('llm_ops_resale_platform', platformId)
    }
    loadResaleWorkflowConfig(platformId)
    if (!loading.value) {
      if (activeSection.value === 'monitor') {
        refreshSummary()
      } else {
        refreshLight()
      }
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
          platforms.find((platform) => platform.code === 'agione') ||
          platforms[0]
        selectedResalePlatformId.value = String(fallback.id)
      }
    },
    { immediate: true }
  )

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
    refreshPlatformData()
  }

  function mergeResaleListings(updatedItems) {
    if (!Array.isArray(updatedItems) || !updatedItems.length) return
    const byId = new Map(
      asArray(listings.value).map((item) => [String(item.id), item])
    )
    updatedItems.forEach((item) => {
      if (item?.id) byId.set(String(item.id), item)
    })
    listings.value = Array.from(byId.values())
  }

  async function handleManualPriceSaved(payload) {
    if (!payload || !Array.isArray(payload.price_items)) {
      await refreshProviderManagementData()
      return
    }

    if (payload.source?.id) {
      sources.value = mergeById(sources.value, [payload.source])
    }
    collectionRuns.value = mergeById(
      collectionRuns.value,
      payload.collection_runs || []
    )
    metaModels.value = mergeById(metaModels.value, payload.meta_models || [])
    models.value = mergeById(models.value, payload.models || [])
    modelPriceItems.value = removeById(
      modelPriceItems.value,
      payload.deactivated_price_item_ids || []
    )
    modelPriceItems.value = mergeById(
      modelPriceItems.value,
      payload.price_items || []
    )

    try {
      await refreshSummary()
    } catch (error) {
      showError(errorMessage(error, '刷新汇总数据失败。'))
    }
  }

  function mergeById(currentItems, updatedItems) {
    if (!Array.isArray(updatedItems) || !updatedItems.length) {
      return currentItems
    }
    const byId = new Map(
      asArray(currentItems).map((item) => [String(item.id), item])
    )
    updatedItems.forEach((item) => {
      if (item?.id) byId.set(String(item.id), item)
    })
    return Array.from(byId.values())
  }

  function removeById(currentItems, ids) {
    if (!Array.isArray(ids) || !ids.length) return currentItems
    const idSet = new Set(ids.map((id) => String(id)))
    return asArray(currentItems).filter((item) => !idSet.has(String(item.id)))
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
    if (!['create', 'view', 'edit'].includes(kind)) return
    resalePublishingInitialModelId.value = modelId || null
    resalePublishingDrawerOpen.value = true
    preloadResalePublishingData()
  }

  function openResalePublishingWorkspace(payload = {}) {
    resalePublishingInitialModelId.value = payload?.modelId || null
    resalePublishingDrawerOpen.value = true
    preloadResalePublishingData()
  }

  function mapWorkspaceListingToPayload(item) {
    const inApi = Number(item.priceIn) || 0
    const outApi = Number(item.priceOut) || 0
    return {
      platform: agionePlatform.value?.id,
      model: item.modelId,
      channel: item.channelId,
      currency: normalizeDisplayCurrency(
        item.currency || displayCurrency.value
      ),
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
      return false
    }
    if (!payload.hasChanges) {
      showInfo(t('llmOps.messages.noChangesToSave'))
      return false
    }
    const changedListings = payload.listings.filter(
      (item) => item.hasChanges !== false
    )
    if (!changedListings.length) {
      showInfo(t('llmOps.messages.noChangesToSave'))
      return false
    }
    const publishListings = changedListings.filter(
      (item) =>
        !item.priceBelowReference &&
        Number(item.priceIn) > 0 &&
        Number(item.priceOut) > 0
    )
    const items = publishListings.map(mapWorkspaceListingToPayload)
    if (!items.length) {
      showError(t('llmOps.messages.invalidListingPrices'))
      return false
    }
    try {
      const response = await llmOpsApi.bulkUpsertResaleListings(items)
      const submittedListings = asArray(extract(response))
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
      return true
    } catch (error) {
      const message =
        error?.response?.data?.detail ||
        error?.response?.data?.message ||
        error?.message ||
        ''
      showError(message || t('llmOps.messages.submitFailed'))
      return false
    }
  }

  async function confirmAutoApprovedListings(
    submittedListings,
    sourceListings
  ) {
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
      return false
    }
    if (!payload.hasChanges) {
      showInfo(t('llmOps.messages.noChangesToSave'))
      return false
    }
    const items = payload.listings
      .filter((item) => item.hasChanges !== false)
      .map(mapWorkspaceListingToPayload)
    if (!items.length) {
      showInfo(t('llmOps.messages.noChangesToSave'))
      return false
    }
    try {
      await llmOpsApi.bulkDraftResaleListings(items)
      showSuccess(t('llmOps.messages.draftsSaved', { count: items.length }))
      resalePublishingDrawerOpen.value = false
      refreshLight()
      return true
    } catch (error) {
      const message =
        error?.response?.data?.detail ||
        error?.response?.data?.message ||
        error?.message ||
        ''
      showError(message || t('llmOps.messages.saveFailed'))
      return false
    }
  }

  return {
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
  }
}
