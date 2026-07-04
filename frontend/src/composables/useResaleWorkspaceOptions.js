import { computed } from 'vue'

import { channelPriceItemKey } from '@/composables/useResaleChainRows'
import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'

export function useResaleWorkspaceOptions({ form, props, t }) {
  const metaModelRows = computed(() =>
    (props.metaModels || []).map((item) => {
      const vendor = resolveCanonicalMetaOwner(item, props.providers)
      return {
        ...item,
        owner_key: item.owner_code || vendor.code,
        owner_code: item.owner_code || vendor.code,
        owner_name: item.owner_name || vendor.name
      }
    })
  )

  const metaModelById = computed(() => {
    const map = new Map()
    metaModelRows.value.forEach((item) => {
      map.set(String(item.id), item)
    })
    return map
  })

  const modelById = computed(() => {
    const map = new Map()
    ;(props.models || []).forEach((model) => {
      map.set(String(model.id), model)
    })
    return map
  })

  const channelPriceItemsByKey = computed(() => {
    const map = new Map()
    ;(props.channelPriceItems || []).forEach((item) => {
      if (!item?.channel || !item?.model || !item?.dimension) return
      const key = channelPriceItemKey(item.channel, item.model, item.dimension)
      map.set(key, item)
    })
    return map
  })

  const procurementByMetaModel = computed(() => {
    const map = new Map()
    ;(props.procurementRows || []).forEach((row) => {
      const model = modelById.value.get(String(row.model_id))
      const metaModelId = model?.meta_model
      if (!metaModelId) return
      const key = String(metaModelId)
      if (!map.has(key)) {
        map.set(key, [])
      }
      map.get(key).push(row)
    })
    return map
  })

  const selectedMetaModel = computed(() => {
    if (!form.value.modelId) return null
    return metaModelById.value.get(String(form.value.modelId)) || null
  })

  const selectedMetaModelProcurements = computed(() => {
    if (!form.value.modelId) return []
    return procurementByMetaModel.value.get(String(form.value.modelId)) || []
  })

  const platformSelectOptions = computed(() =>
    (props.platforms || []).map((item) => ({
      value: String(item.id),
      label:
        item.name ||
        item.code ||
        t('llmOps.publishingWorkspace.fallback.platform', { id: item.id })
    }))
  )

  const metaVendorOptions = computed(() => {
    const map = new Map()
    metaModelRows.value.forEach((model) => {
      const id = model.owner_key
      if (!id) return
      const key = String(id)
      if (map.has(key)) return
      map.set(key, {
        id,
        name:
          model.owner_name ||
          t('llmOps.publishingWorkspace.fallback.uncategorized'),
        code: model.owner_code || ''
      })
    })
    return Array.from(map.values()).sort((left, right) =>
      String(left.name).localeCompare(String(right.name))
    )
  })

  const metaVendorSelectOptions = computed(() => [
    { value: '', label: t('llmOps.publishingWorkspace.filters.all') },
    ...metaVendorOptions.value.map((item) => ({
      value: String(item.id),
      label: item.name,
      description: item.code || ''
    }))
  ])

  const baseModelOptions = computed(() => {
    const metaVendorId = form.value.metaVendorId
    return metaModelRows.value
      .filter((item) => {
        if (!metaVendorId) return true
        return String(item.owner_key) === String(metaVendorId)
      })
      .map((item) => ({
        id: item.id,
        name: item.name || item.code,
        code: item.code,
        family: item.family,
        vendorName: item.owner_name
      }))
      .sort((left, right) =>
        String(left.name).localeCompare(String(right.name))
      )
  })

  const baseModelSelectOptions = computed(() => [
    {
      value: '',
      label: t('llmOps.publishingWorkspace.filters.selectMetaModel')
    },
    ...baseModelOptions.value.map((item) => ({
      value: String(item.id),
      label: item.name,
      description: [item.vendorName, item.family, item.code]
        .filter(Boolean)
        .join(' · '),
      searchText: [item.name, item.vendorName, item.family, item.code]
        .filter(Boolean)
        .join(' ')
    }))
  ])

  const supplierOptions = computed(() => {
    if (!form.value.modelId) return []
    const seen = new Map()
    selectedMetaModelProcurements.value.forEach((row) => {
      ;(row.options || []).forEach((opt) => {
        if (!opt?.channel_id || !opt?.channel_name) return
        const id = String(opt.channel_id)
        if (seen.has(id)) return
        seen.set(id, { id, name: opt.channel_name })
      })
    })
    return Array.from(seen.values()).sort((a, b) =>
      String(a.name).localeCompare(String(b.name))
    )
  })

  const supplierSelectOptions = computed(() => {
    if (!form.value.modelId) {
      return [
        {
          value: '',
          label: t('llmOps.publishingWorkspace.filters.selectMetaModelFirst'),
          disabled: true
        }
      ]
    }
    return [
      {
        value: '',
        label: t('llmOps.publishingWorkspace.filters.allSupportedChannels')
      },
      ...supplierOptions.value.map((item) => ({
        value: String(item.id),
        label: item.name
      }))
    ]
  })

  const supportedSupplierIds = computed(
    () => new Set(supplierOptions.value.map((item) => String(item.id)))
  )

  const pointUnitLabel = computed(
    () =>
      props.pointConversion?.point_name ||
      t('llmOps.publishingWorkspace.fallback.points')
  )

  const selectedPlatform = computed(() => {
    const id = String(form.value.platformId || '')
    return (
      (props.platforms || []).find((item) => String(item.id) === id) ||
      props.agionePlatform ||
      null
    )
  })

  const selectedPlatformLabel = computed(
    () =>
      selectedPlatform.value?.name ||
      t('llmOps.publishingWorkspace.fallback.currentPlatform')
  )

  const platformCurrencyLabel = computed(() =>
    String(
      selectedPlatform.value?.currency || props.displayCurrency || 'CNY'
    ).toUpperCase()
  )

  const selectedPlatformFeeRate = computed(() => {
    const value = Number(selectedPlatform.value?.fee_rate)
    return Number.isFinite(value) ? value : 0
  })

  const selectedPlatformServiceFeeRate = computed(() => {
    const value = Number(selectedPlatform.value?.service_fee_rate)
    return Number.isFinite(value) ? value : 0
  })

  const workflowAutoApproveEnabled = computed(() => {
    const value = props.workflowConfig?.policies?.auto_approve_enabled
    return value !== false
  })

  const selectedPlatformAutoApproveLimit = computed(() => {
    if (!workflowAutoApproveEnabled.value) return null
    const runtimeValue = Number(
      props.workflowConfig?.runtime?.auto_approve_max_margin_rate
    )
    if (Number.isFinite(runtimeValue)) return runtimeValue
    const value = Number(selectedPlatform.value?.auto_approve_max_margin_rate)
    return Number.isFinite(value) ? value : null
  })

  return {
    baseModelSelectOptions,
    channelPriceItemsByKey,
    metaModelById,
    metaModelRows,
    metaVendorSelectOptions,
    modelById,
    platformCurrencyLabel,
    platformSelectOptions,
    pointUnitLabel,
    selectedMetaModel,
    selectedMetaModelProcurements,
    selectedPlatform,
    selectedPlatformAutoApproveLimit,
    selectedPlatformFeeRate,
    selectedPlatformLabel,
    selectedPlatformServiceFeeRate,
    supplierOptions,
    supplierSelectOptions,
    supportedSupplierIds,
    workflowAutoApproveEnabled
  }
}
