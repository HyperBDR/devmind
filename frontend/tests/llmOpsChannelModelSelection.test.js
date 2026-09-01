import assert from 'node:assert/strict'
import test from 'node:test'

import { ref } from 'vue'

import { useChannelModelSelection } from '../src/composables/useChannelModelSelection.js'

function buildSelection(modelCount = 30) {
  const models = Array.from({ length: modelCount }, (_, index) => {
    const number = index + 1
    return {
      id: number,
      code: `provider-model-${number}`,
      name: `Provider Model ${number}`,
      meta_model: {
        code: `model-${number}`,
        name: `Model ${number}`,
        owner_code: 'vendor',
        owner_name: 'Vendor'
      }
    }
  })
  const modelSearch = ref('')
  const selection = useChannelModelSelection({
    baseAvailableModels: ref(models),
    fuzzyScore: (haystack, keyword) =>
      haystack.toLowerCase().includes(keyword) ? 1 : 0,
    metaModelDisplayName: (metaModel) => metaModel.name,
    metaModelForSourceModel: (model) => model.meta_model,
    metaModelIdentityKey: (metaModel) => metaModel.code,
    metaModelVendorKey: (group) => group.ownerCode,
    metaModelVendorName: (group) => group.ownerName,
    modalityLabel: (value) => value,
    modelOptionSearchText: (group) => `${group.code} ${group.name}`,
    modelSearch,
    modelSourceCategory: () => 'supplier',
    normalizeSearch: (value) =>
      String(value || '')
        .trim()
        .toLowerCase(),
    providerModelDescription: () => '',
    providerPriceSummary: () => [],
    purchaseSourceLabel: (model) => model.name,
    selectedModelKeys: ref(new Set()),
    selectedProviderByModelKey: ref({}),
    selectedVendorKey: ref(''),
    sourceCategoryBadge: () => '',
    t: (key) => key
  })
  return { modelSearch, selection }
}

test('keeps every addable model reachable when more than 24 exist', () => {
  const { selection } = buildSelection()

  assert.equal(selection.availableModelCount.value, 30)
  assert.equal(selection.availableModelOptions.value.length, 30)
})

test('searches models after the former first-page cutoff', () => {
  const { modelSearch, selection } = buildSelection()

  modelSearch.value = 'model-30'

  assert.deepEqual(
    selection.availableModelOptions.value.map((model) => model.code),
    ['model-30']
  )
})

test('requires a regional offer when one source has multiple regions', () => {
  const model = {
    id: 1,
    code: 'deepseek-v4-flash',
    name: 'DeepSeek V4 Flash',
    meta_model: 1,
    source: 10,
    source_name: 'Aliyun official'
  }
  const selectedModelKeys = ref(new Set(['deepseek-v4-flash']))
  const selectedProviderByModelKey = ref({ 'deepseek-v4-flash': 1 })
  const selectedSourceOfferingByModelKey = ref({})
  const priceItems = ref([])
  const selection = useChannelModelSelection({
    baseAvailableModels: ref([model]),
    fuzzyScore: () => 1,
    metaModelDisplayName: (value) => value.name,
    metaModelForSourceModel: () => ({
      code: 'deepseek-v4-flash',
      name: 'DeepSeek V4 Flash'
    }),
    metaModelIdentityKey: (value) => value.code,
    metaModelVendorKey: () => 'vendor',
    metaModelVendorName: () => 'Vendor',
    modalityLabel: (value) => value,
    modelOptionSearchText: () => '',
    modelSearch: ref(''),
    modelSourceCategory: () => 'supplier',
    normalizeSearch: (value) => String(value || '').toLowerCase(),
    providerModelDescription: () => '',
    priceItems,
    providerPriceSummary: () => [],
    purchaseSourceLabel: (value) => value.name,
    selectedModelKeys,
    selectedProviderByModelKey,
    selectedSourceOfferingByModelKey,
    selectedVendorKey: ref(''),
    sourceCategoryBadge: () => '',
    t: (key) => key
  })

  assert.equal(selection.canAddSelectedModels.value, true)

  priceItems.value = [
    { meta_model: 1, source: 10, offering: 20, sku_region: '' },
    { meta_model: 1, source: 10, offering: 21, sku_region: 'Japan' }
  ]

  assert.equal(selection.canAddSelectedModels.value, false)
  assert.equal(
    selection.selectedResolvedModels.value[0].sourceOfferingOptions.find(
      (option) => String(option.value) === '20'
    ).label,
    '全球'
  )
  selection.selectSourceOffering('deepseek-v4-flash', 21)
  assert.equal(selection.canAddSelectedModels.value, true)

  priceItems.value = [
    {
      meta_model: 1,
      source: 10,
      offering: 20,
      sku_region: 'Global',
      is_current: false
    },
    {
      meta_model: 1,
      source: 10,
      offering: 21,
      sku_region: 'Japan',
      is_current: true
    }
  ]

  selectedSourceOfferingByModelKey.value = {}
  assert.equal(
    selection.selectedResolvedModels.value[0].sourceOfferingOptions.length,
    1
  )
  assert.equal(
    selection.selectedResolvedModels.value[0].selectedSourceOfferingId,
    21
  )
  assert.equal(selection.canAddSelectedModels.value, true)
})
