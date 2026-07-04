import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export function useAgioneListingSelection({ rows }) {
  const { t } = useI18n()
  const listingStatusFilter = ref('all')
  const searchQuery = ref('')
  const pageSize = ref(10)
  const currentPage = ref(1)
  const selectedModelIds = ref(new Set())
  const pageSizeOptions = [10, 20, 50]

  const visibleListingRows = computed(() =>
    rows.listingRows.value.filter((row) => !isHiddenRow(row))
  )

  const filteredListingRows = computed(() => {
    const query = String(searchQuery.value || '')
      .trim()
      .toLowerCase()
    return visibleListingRows.value
      .filter((row) => {
        if (listingStatusFilter.value === 'actionable') {
          if (!isActionableRow(row)) return false
        } else if (listingStatusFilter.value === 'listed') {
          if (!row.is_listed) return false
        } else if (listingStatusFilter.value === 'all') {
          // visible rows only
        } else {
          return false
        }
        if (!query) return true
        const name = String(
          rows.modelDisplayName(row.model) || ''
        ).toLowerCase()
        const code = String(row.model?.code || '').toLowerCase()
        return name.includes(query) || code.includes(query)
      })
      .sort((left, right) => {
        if (listingStatusFilter.value !== 'all') return 0
        return String(left.model?.name || '').localeCompare(
          String(right.model?.name || '')
        )
      })
  })

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(filteredListingRows.value.length / pageSize.value))
  )

  const paginatedListingRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return filteredListingRows.value.slice(start, start + pageSize.value)
  })

  const selectableRows = computed(() =>
    paginatedListingRows.value.filter((row) => isSelectable(row))
  )

  const selectedRows = computed(() =>
    filteredListingRows.value.filter((row) =>
      selectedModelIds.value.has(rowSelectionKey(row))
    )
  )

  const exportableRows = computed(() =>
    filteredListingRows.value.filter(
      (row) => row.status_listing && !isHiddenRow(row)
    )
  )

  const selectedOfflineRows = computed(() =>
    selectedRows.value.filter(
      (row) => row.workflow_status === 'online' && !isHiddenRow(row)
    )
  )

  const canBatchOffline = computed(
    () =>
      selectedRows.value.length > 0 &&
      selectedRows.value.every(
        (row) => row.workflow_status === 'online' && !isHiddenRow(row)
      )
  )

  const allVisibleSelected = computed(
    () =>
      selectableRows.value.length > 0 &&
      selectableRows.value.every((row) =>
        selectedModelIds.value.has(rowSelectionKey(row))
      )
  )

  const listingEmptyText = computed(() => {
    if (listingStatusFilter.value === 'actionable') {
      return t('llmOps.listingBoard.empty.actionable')
    }
    if (listingStatusFilter.value === 'listed') {
      return t('llmOps.listingBoard.empty.listed')
    }
    return t('llmOps.listingBoard.empty.default')
  })

  function isHiddenRow(row) {
    return (
      row.is_removed ||
      row.workflow_status === 'deleted' ||
      row.publish_status === 'deleted'
    )
  }

  function isActionableRow(row) {
    if (isHiddenRow(row)) return false
    return [
      'draft',
      'pending_publish',
      'update_draft',
      'pending_update',
      'pending_offline',
      'offline_exception',
      'offline'
    ].includes(row.workflow_status)
  }

  function isSelectable(row) {
    return !isHiddenRow(row)
  }

  function rowSelectionKey(row) {
    return String(row.status_listing?.id || `model-${row.model.id}`)
  }

  function setSelectedModelIds(ids) {
    selectedModelIds.value = new Set(ids.map((id) => String(id)))
  }

  function toggleRow(row) {
    const next = new Set(selectedModelIds.value)
    const id = rowSelectionKey(row)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    selectedModelIds.value = next
  }

  function toggleAllVisible(event) {
    const next = new Set(selectedModelIds.value)
    if (event.target.checked) {
      selectableRows.value.forEach((row) => next.add(rowSelectionKey(row)))
    } else {
      selectableRows.value.forEach((row) => next.delete(rowSelectionKey(row)))
    }
    selectedModelIds.value = next
  }

  function goToPreviousPage() {
    currentPage.value = Math.max(1, currentPage.value - 1)
  }

  function goToNextPage() {
    currentPage.value = Math.min(totalPages.value, currentPage.value + 1)
  }

  watch(listingStatusFilter, () => {
    currentPage.value = 1
    selectedModelIds.value = new Set()
  })

  watch(searchQuery, () => {
    currentPage.value = 1
    selectedModelIds.value = new Set()
  })

  watch(pageSize, () => {
    currentPage.value = 1
    selectedModelIds.value = new Set()
  })

  watch(totalPages, (value) => {
    if (currentPage.value > value) {
      currentPage.value = value
    }
  })

  watch(
    () => rows.listingRows.value.map((row) => rowSelectionKey(row)).join(','),
    () => {
      const validIds = new Set(
        rows.listingRows.value.map((row) => rowSelectionKey(row))
      )
      setSelectedModelIds(
        Array.from(selectedModelIds.value).filter((id) => validIds.has(id))
      )
    }
  )

  return {
    allVisibleSelected,
    canBatchOffline,
    currentPage,
    exportableRows,
    filteredListingRows,
    goToNextPage,
    goToPreviousPage,
    isActionableRow,
    isHiddenRow,
    isSelectable,
    listingEmptyText,
    listingStatusFilter,
    pageSize,
    pageSizeOptions,
    paginatedListingRows,
    rowSelectionKey,
    selectableRows,
    selectedModelIds,
    selectedOfflineRows,
    selectedRows,
    setSelectedModelIds,
    searchQuery,
    toggleAllVisible,
    toggleRow,
    totalPages,
    visibleListingRows
  }
}
