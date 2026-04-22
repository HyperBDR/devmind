import { computed, ref } from 'vue'

import { oneproMonitorApi } from '@/api/oneproMonitor'

import { unwrap } from './shared'

const STORAGE_KEY = 'onepro-monitor:selected-data-source'

function readStoredDataSource() {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(STORAGE_KEY) || ''
}

const selectedDataSource = ref(readStoredDataSource())
const dataSources = ref([])
const loadingDataSources = ref(false)

let loaded = false
let loadingPromise = null

function persistSelectedDataSource(value) {
  if (typeof window === 'undefined') return
  if (value) {
    window.localStorage.setItem(STORAGE_KEY, value)
    return
  }
  window.localStorage.removeItem(STORAGE_KEY)
}

function setSelectedDataSource(value) {
  const normalized = value ? String(value) : ''
  selectedDataSource.value = normalized
  persistSelectedDataSource(normalized)
}

async function loadDataSources(force = false) {
  if (!force && loaded) return dataSources.value
  if (!force && loadingPromise) return loadingPromise

  loadingDataSources.value = true
  loadingPromise = oneproMonitorApi.dataSources
    .list({ limit: 200 })
    .then((response) => {
      const payload = unwrap(response)
      dataSources.value = payload.items || []
      loaded = true

      if (
        selectedDataSource.value &&
        !dataSources.value.some(
          (source) => String(source.id) === String(selectedDataSource.value)
        )
      ) {
        setSelectedDataSource('')
      }

      return dataSources.value
    })
    .finally(() => {
      loadingDataSources.value = false
      loadingPromise = null
    })

  return loadingPromise
}

const selectedDataSourceName = computed(() => {
  const source = dataSources.value.find(
    (item) => String(item.id) === String(selectedDataSource.value)
  )
  return source?.name || ''
})

function appendDataSourceScope(params = {}) {
  return {
    ...params,
    data_source_id: selectedDataSource.value || undefined
  }
}

export function useOneProDataSourceScope() {
  return {
    dataSources,
    loadingDataSources,
    selectedDataSource,
    selectedDataSourceName,
    setSelectedDataSource,
    loadDataSources,
    appendDataSourceScope
  }
}
