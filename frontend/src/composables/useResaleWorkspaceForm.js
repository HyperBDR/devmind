import { ref, watch } from 'vue'

export function useResaleWorkspaceForm({ props }) {
  const form = ref({
    platformId: '',
    metaVendorId: '',
    modelId: '',
    supplierId: ''
  })

  const globalPricing = ref({
    exchangeRate: 7.23,
    creditRatio: 10
  })

  const isSupplyChainExpanded = ref(true)

  watch(
    () => props.agionePlatform,
    (next) => {
      if (next?.id) {
        form.value.platformId = String(next.id)
      }
    },
    { immediate: true }
  )

  watch(
    () => props.platforms,
    (list) => {
      if (!form.value.platformId && list?.length) {
        form.value.platformId = String(list[0].id)
      }
    },
    { immediate: true }
  )

  watch(
    () => props.pointConversion,
    (next) => {
      if (next?.points_per_currency_unit) {
        globalPricing.value.creditRatio = Number(next.points_per_currency_unit)
      }
    },
    { immediate: true }
  )

  watch(
    () => props.exchangeRate,
    (next) => {
      if (Number.isFinite(next)) {
        globalPricing.value.exchangeRate = next
      }
    },
    { immediate: true }
  )

  function onMetaVendorChange() {
    form.value.modelId = ''
    form.value.supplierId = ''
    isSupplyChainExpanded.value = true
  }

  function onModelChange() {
    form.value.supplierId = ''
    isSupplyChainExpanded.value = true
  }

  return {
    form,
    globalPricing,
    isSupplyChainExpanded,
    onMetaVendorChange,
    onModelChange
  }
}
