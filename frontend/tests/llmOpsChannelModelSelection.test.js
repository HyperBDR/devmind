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
