<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Folder,
  FolderInput,
  Loader2,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
} from 'lucide-vue-next'
import {
  deleteImportedDocuments,
  downloadImportedDocument,
  listImportedFeishuDocuments,
  type ImportedDocument,
} from '../api/documents'
import {
  checkFeishuFileAccess,
  syncFeishuArchiveFolder,
  type FeishuArchiveFolder,
} from '../api/feishu'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import FormSelect from './FormSelect.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const emit = defineEmits<{
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const props = defineProps<{
  embedded?: boolean
}>()

const { t } = useQuotationI18n()

const docs = ref<ImportedDocument[]>([])
const archiveFolders = ref<FeishuArchiveFolder[]>([])
const archiveFileFolders = ref<Record<string, string>>({})
const collapsedFolderTokens = ref<Set<string>>(new Set())
const loading = ref(false)
const search = ref('')
const typeFilter = ref('ALL')
const downloadingId = ref<string | null>(null)
const deleting = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const deleteConfirmIds = ref<string[]>([])
const selectAllCheckbox = ref<HTMLInputElement | null>(null)
let reconcileTimer: number | undefined

function scheduleFeishuDocReconcile() {
  window.clearTimeout(reconcileTimer)
  reconcileTimer = window.setTimeout(() => {
    void refresh()
  }, 250)
}

function handlePageVisible() {
  if (document.visibilityState !== 'visible') return
  scheduleFeishuDocReconcile()
}

onMounted(() => {
  document.addEventListener('visibilitychange', handlePageVisible)
  window.addEventListener('focus', handlePageVisible)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handlePageVisible)
  window.removeEventListener('focus', handlePageVisible)
  window.clearTimeout(reconcileTimer)
})

const typeFilterOptions = computed(() => [
  { value: 'ALL', label: t('quotation.pages.imports.typeAll') },
  { value: 'excel', label: t('quotation.pages.imports.typeExcel') },
  { value: 'pdf', label: t('quotation.pages.imports.typePdf') },
])

function formatBytes(size: number): string {
  if (!size || size < 0) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function notify(message: string, type: 'success' | 'info' | 'error' = 'info') {
  emit('toast', message, type)
}

function rebuildArchiveTree(items: ImportedDocument[]) {
  const folders = new Map<string, FeishuArchiveFolder>()
  const locations: Record<string, string> = {}

  items.forEach((doc) => {
    const path = Array.isArray(doc.feishu_folder_path)
      ? doc.feishu_folder_path
      : []
    let parentToken: string | null = null
    path.forEach((entry) => {
      const token = String(entry?.token || '').trim()
      const name = String(entry?.name || '').trim()
      if (!token || !name) return
      folders.set(token, {
        token,
        name,
        parent_token: parentToken,
      })
      parentToken = token
    })
    if (parentToken) locations[doc.id] = parentToken
  })

  archiveFolders.value = [...folders.values()]
  archiveFileFolders.value = locations
}

async function refresh(options: {
  syncRemote?: boolean
  syncSource?: 'automatic' | 'user'
} = {}) {
  loading.value = true
  try {
    if (options.syncRemote) {
      try {
        await syncFeishuArchiveFolder({
          source: options.syncSource || 'user',
        })
      } catch (err: unknown) {
        if (options.syncSource !== 'automatic') {
          notify(
            err instanceof Error ? err.message : t('quotation.pages.imports.syncFailed'),
            'error',
          )
        }
      }
    }
    const items = await listImportedFeishuDocuments()
    docs.value = items
    rebuildArchiveTree(items)
  } catch (err: unknown) {
    notify(
      err instanceof Error ? err.message : t('quotation.pages.imports.loadFailed'),
      'error',
    )
    docs.value = []
  } finally {
    loading.value = false
  }
}

void refresh({ syncRemote: true, syncSource: 'automatic' })

const folderSearchState = computed(() => {
  const query = search.value.trim().toLowerCase()
  const branchTokens = new Set<string>()
  const contentTokens = new Set<string>()
  const matchedTokens = new Set<string>()
  if (!query) return { branchTokens, contentTokens, matchedTokens }

  const foldersByToken = new Map(
    archiveFolders.value.map((folder) => [folder.token, folder]),
  )
  const childrenByParent = new Map<string, FeishuArchiveFolder[]>()
  archiveFolders.value.forEach((folder) => {
    if (!folder.parent_token) return
    const children = childrenByParent.get(folder.parent_token) || []
    children.push(folder)
    childrenByParent.set(folder.parent_token, children)
  })

  const addDescendants = (folderToken: string) => {
    if (contentTokens.has(folderToken)) return
    contentTokens.add(folderToken)
    branchTokens.add(folderToken)
    ;(childrenByParent.get(folderToken) || []).forEach((child) => {
      addDescendants(child.token)
    })
  }

  archiveFolders.value
    .filter((folder) => folder.name.toLowerCase().includes(query))
    .forEach((folder) => {
      matchedTokens.add(folder.token)
      addDescendants(folder.token)
      const visited = new Set<string>()
      let parentToken = folder.parent_token
      while (parentToken && !visited.has(parentToken)) {
        visited.add(parentToken)
        branchTokens.add(parentToken)
        parentToken = foldersByToken.get(parentToken)?.parent_token || null
      }
    })
  return { branchTokens, contentTokens, matchedTokens }
})

const directFileMatches = computed(() => {
  const q = search.value.trim().toLowerCase()
  return docs.value.filter((doc) => {
    if (!archiveFileFolders.value[doc.id]) return false
    if (typeFilter.value !== 'ALL' && (doc.doc_type || '').toLowerCase() !== typeFilter.value) {
      return false
    }
    if (!q) return true
    return doc.file_name.toLowerCase().includes(q)
  })
})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  const directIds = new Set(directFileMatches.value.map((doc) => doc.id))
  return docs.value.filter((doc) => {
    if (!archiveFileFolders.value[doc.id]) return false
    if (typeFilter.value !== 'ALL' && (doc.doc_type || '').toLowerCase() !== typeFilter.value) {
      return false
    }
    if (!q || directIds.has(doc.id)) return true
    const folderToken = archiveFileFolders.value[doc.id]
    return Boolean(
      folderToken
      && folderSearchState.value.contentTokens.has(folderToken)
    )
  })
})

const hasActiveFilters = computed(
  () => search.value.trim().length > 0 || typeFilter.value !== 'ALL',
)

type ArchiveTreeRow =
  | {
      kind: 'folder'
      key: string
      token: string
      name: string
      depth: number
      fileCount: number
    }
  | {
      kind: 'file'
      key: string
      doc: ImportedDocument
      depth: number
    }

const treeRows = computed<ArchiveTreeRow[]>(() => {
  const folders = [...archiveFolders.value]
  const folderTokens = new Set(folders.map((folder) => folder.token))
  const docsByFolder = new Map<string, ImportedDocument[]>()

  filtered.value.forEach((doc) => {
    const folderToken = archiveFileFolders.value[doc.id]
    if (!folderToken || !folderTokens.has(folderToken)) {
      return
    }
    const folderDocs = docsByFolder.get(folderToken) || []
    folderDocs.push(doc)
    docsByFolder.set(folderToken, folderDocs)
  })

  const children = new Map<string | null, FeishuArchiveFolder[]>()
  folders.forEach((folder) => {
    const parentToken = folder.parent_token && folderTokens.has(folder.parent_token)
      ? folder.parent_token
      : null
    const siblings = children.get(parentToken) || []
    siblings.push(folder)
    children.set(parentToken, siblings)
  })
  children.forEach((items) => items.sort((a, b) => a.name.localeCompare(b.name)))

  const folderFileCounts = new Map<string, number>()
  const countFolderFiles = (folderToken: string, visiting = new Set<string>()): number => {
    if (folderFileCounts.has(folderToken)) return folderFileCounts.get(folderToken) || 0
    if (visiting.has(folderToken)) return 0
    const nextVisiting = new Set(visiting).add(folderToken)
    const count = (docsByFolder.get(folderToken) || []).length
      + (children.get(folderToken) || []).reduce(
        (total, child) => total + countFolderFiles(child.token, nextVisiting),
        0,
      )
    folderFileCounts.set(folderToken, count)
    return count
  }

  const rows: ArchiveTreeRow[] = []
  const visited = new Set<string>()
  const renderedDocIds = new Set<string>()
  const appendFolder = (folder: FeishuArchiveFolder, depth: number) => {
    if (visited.has(folder.token)) return
    visited.add(folder.token)
    const fileCount = countFolderFiles(folder.token)
    if (
      hasActiveFilters.value
      && fileCount === 0
      && !folderSearchState.value.branchTokens.has(folder.token)
    ) return
    const folderDocs = (docsByFolder.get(folder.token) || [])
      .sort((a, b) => a.file_name.localeCompare(b.file_name))
    rows.push({
      kind: 'folder',
      key: `folder:${folder.token}`,
      token: folder.token,
      name: folder.name,
      depth,
      fileCount,
    })
    if (collapsedFolderTokens.value.has(folder.token)) return
    folderDocs.forEach((doc) => {
      renderedDocIds.add(doc.id)
      rows.push({ kind: 'file', key: `file:${doc.id}`, doc, depth: depth + 1 })
    })
    ;(children.get(folder.token) || []).forEach((child) => {
      appendFolder(child, depth + 1)
    })
  }

  const query = search.value.trim()
  if (query) {
    folders
      .filter((folder) => folderSearchState.value.matchedTokens.has(folder.token))
      .forEach((folder) => appendFolder(folder, 0))
    directFileMatches.value.forEach((doc) => {
      if (renderedDocIds.has(doc.id)) return
      renderedDocIds.add(doc.id)
      rows.push({ kind: 'file', key: `file:${doc.id}`, doc, depth: 0 })
    })
  } else {
    ;(children.get(null) || []).forEach((folder) => appendFolder(folder, 0))
  }

  return rows
})

const selectedVisibleCount = computed(
  () => filtered.value.filter((doc) => selectedIds.value.has(doc.id)).length,
)

const allVisibleSelected = computed(
  () =>
    filtered.value.length > 0 &&
    selectedVisibleCount.value === filtered.value.length,
)

const someVisibleSelected = computed(
  () => selectedVisibleCount.value > 0 && !allVisibleSelected.value,
)

const selectedCount = computed(() => selectedIds.value.size)

const deleteConfirmDocs = computed(() =>
  docs.value.filter((doc) => deleteConfirmIds.value.includes(doc.id)),
)

const rootClass = computed(() =>
  props.embedded
    ? 'space-y-6'
    : 'flex h-[calc(100vh-7.5rem)] flex-col gap-4 overflow-hidden',
)

function isSelected(docId: string): boolean {
  return selectedIds.value.has(docId)
}

function toggleSelect(docId: string) {
  const next = new Set(selectedIds.value)
  if (next.has(docId)) {
    next.delete(docId)
  } else {
    next.add(docId)
  }
  selectedIds.value = next
}

function toggleSelectAllVisible() {
  const next = new Set(selectedIds.value)
  if (allVisibleSelected.value) {
    filtered.value.forEach((doc) => next.delete(doc.id))
  } else {
    filtered.value.forEach((doc) => next.add(doc.id))
  }
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

function handleResetFilters() {
  search.value = ''
  typeFilter.value = 'ALL'
}

function toggleFolder(folderToken: string) {
  const next = new Set(collapsedFolderTokens.value)
  if (next.has(folderToken)) {
    next.delete(folderToken)
  } else {
    next.add(folderToken)
  }
  collapsedFolderTokens.value = next
}

watch(search, () => {
  collapsedFolderTokens.value = new Set()
})

watchEffect(() => {
  if (selectAllCheckbox.value) {
    selectAllCheckbox.value.indeterminate = someVisibleSelected.value
  }
})

function handleOpenFeishu(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  const directUrl = String(doc.feishu_url || '').trim()
  if (!doc.remote_access_available || !directUrl) {
    notify(t('quotation.pages.imports.missingFeishuLink'), 'error')
    return
  }
  window.open(directUrl, '_blank', 'noopener,noreferrer')
  void checkFeishuFileAccess(doc.id).catch(() => {})
}

async function handleDownload(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  downloadingId.value = doc.id
  try {
    await downloadImportedDocument(doc.id, doc.file_name)
    notify(t('quotation.pages.imports.downloadStarted', { fileName: doc.file_name }), 'success')
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t('quotation.pages.imports.downloadFailed'), 'error')
  } finally {
    downloadingId.value = null
  }
}

function handleBatchDelete() {
  if (selectedIds.value.size === 0) return
  deleteConfirmIds.value = [...selectedIds.value]
}

async function confirmDelete() {
  if (!deleteConfirmIds.value.length) return
  const ids = [...deleteConfirmIds.value]
  deleteConfirmIds.value = []
  deleting.value = true
  try {
    const { deleted, failed } = await deleteImportedDocuments(ids)
    if (deleted.length) {
      docs.value = docs.value.filter((item) => !deleted.includes(item.id))
      const next = new Set(selectedIds.value)
      deleted.forEach((id) => next.delete(id))
      selectedIds.value = next
    }
    if (failed.length === 0) {
      notify(
        t('quotation.pages.imports.batchDeleteSuccess', { count: deleted.length }),
        'success',
      )
    } else if (deleted.length > 0) {
      notify(
        t('quotation.pages.imports.batchDeletePartial', {
          deleted: deleted.length,
          failed: failed.length,
        }),
        'error',
      )
    } else {
      notify(t('quotation.pages.imports.deleteFailed'), 'error')
    }
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t('quotation.pages.imports.deleteFailed'), 'error')
  } finally {
    deleting.value = false
  }
}

</script>

<template>
  <div :class="rootClass">
    <div
      id="import-filter-panel"
      v-show="false"
      data-filter-toolbar
      aria-label="Imported file filters"
      class="rounded-xl border border-dm-border-light bg-white p-3 shadow-xs"
    >
      <div class="flex flex-col gap-2 lg:flex-row lg:items-center">
        <div class="relative min-w-0 flex-1">
          <label class="sr-only">
            {{ t('quotation.pages.imports.keywordLabel') }}
          </label>
          <input
            v-model="search"
            type="text"
            :placeholder="t('quotation.pages.imports.searchPlaceholder')"
            class="h-10 w-full rounded-lg border border-dm-border-light bg-slate-50/70 py-2 pl-9 pr-3 text-sm text-dm-text transition placeholder:text-slate-400 hover:bg-white focus:border-blue-300 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-100"
          />
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>

        <div class="grid grid-cols-2 gap-2 sm:flex sm:items-center">
          <div class="min-w-0 sm:w-44">
            <label class="sr-only">
              {{ t('quotation.pages.imports.typeLabel') }}
            </label>
            <FormSelect
              v-model="typeFilter"
              class-name="w-full"
              :trigger-class-name="`${FORM_SELECT_COMPACT_TRIGGER_CLASS} rounded-lg border-dm-border-light bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100`"
              :options="typeFilterOptions"
            />
          </div>

          <div class="flex h-10 items-center justify-center rounded-lg bg-slate-50 px-3 text-xs font-semibold text-dm-text-tertiary sm:min-w-24">
            {{ t('quotation.pages.imports.filterResultsCount', { count: filtered.length }) }}
          </div>

          <button
            v-if="hasActiveFilters"
            type="button"
            class="col-span-2 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-blue-700 transition hover:bg-blue-50 sm:col-span-1"
            @click="handleResetFilters"
          >
            <RotateCcw class="h-3.5 w-3.5" />
            {{ t('quotation.actions.resetFilters') }}
          </button>

          <button
            type="button"
            class="dm-btn-primary col-span-2 h-10 px-3.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 sm:col-span-1"
            :disabled="loading"
            @click="refresh({ syncRemote: true, syncSource: 'user' })"
          >
            <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': loading }" />
            {{ t('quotation.pages.imports.syncButton') }}
          </button>
        </div>
      </div>
    </div>

    <div
      id="import-table-panel"
      v-show="false"
      :class="[
        'overflow-hidden rounded-xl border border-dm-border-light bg-white shadow-xs',
        props.embedded ? '' : 'min-h-0 flex-1',
      ]"
    >
      <div
        v-if="loading && docs.length === 0 && archiveFolders.length === 0"
        class="flex items-center justify-center gap-2 py-16 text-sm text-dm-text-tertiary"
      >
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('quotation.pages.imports.loading') }}
      </div>

      <div
        v-else-if="docs.length === 0 && archiveFolders.length === 0"
        class="flex flex-col items-center justify-center px-4 py-16 text-center"
      >
        <FolderInput class="mx-auto h-8 w-8 text-slate-300" />
        <p class="mt-3 text-sm font-semibold text-dm-text">
          {{ t('quotation.pages.imports.emptyTitle') }}
        </p>
        <p class="mt-1 text-xs text-dm-text-tertiary">
          {{ t('quotation.pages.imports.emptyDesc') }}
        </p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse text-left">
          <thead>
            <tr
              class="border-b border-dm-border-light bg-[#fafafa] text-xs font-bold tracking-wider text-dm-text-tertiary"
            >
              <th class="w-10 px-4 py-3">
                <input
                  ref="selectAllCheckbox"
                  type="checkbox"
                  class="h-3.5 w-3.5 rounded border-dm-border text-blue-600 focus:ring-blue-400"
                  :checked="allVisibleSelected"
                  @change="toggleSelectAllVisible"
                />
              </th>
              <th class="px-4 py-3">{{ t('quotation.pages.imports.tableFileName') }}</th>
              <th class="px-4 py-3">{{ t('quotation.pages.imports.tableSize') }}</th>
              <th class="min-w-[120px] px-4 py-3 text-center">
                {{ t('quotation.pages.imports.tableActions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-sm">
            <tr v-if="treeRows.length === 0">
              <td colspan="4" class="px-4 py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.pages.imports.emptyResults') }}
              </td>
            </tr>
            <template v-for="row in treeRows" v-else :key="row.key">
              <tr
                v-if="row.kind === 'folder'"
                class="cursor-pointer bg-slate-50/80 transition hover:bg-blue-50/70"
                @click="toggleFolder(row.token)"
              >
                <td colspan="4" class="px-4 py-2.5">
                  <div
                    class="flex items-center gap-2 font-semibold text-dm-text-secondary"
                    :style="{ paddingLeft: `${row.depth * 20}px` }"
                  >
                    <ChevronRight
                      v-if="collapsedFolderTokens.has(row.token)"
                      class="h-4 w-4 shrink-0 text-slate-400"
                    />
                    <ChevronDown v-else class="h-4 w-4 shrink-0 text-slate-400" />
                    <Folder class="h-4 w-4 shrink-0 text-blue-500" />
                    <span class="truncate">{{ row.name }}</span>
                    <span class="ml-1 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-dm-text-tertiary ring-1 ring-slate-200">
                      {{ t('quotation.pages.imports.folderFileCount', { count: row.fileCount }) }}
                    </span>
                  </div>
                </td>
              </tr>
              <tr
                v-else
                :class="[
                  'transition duration-150',
                  isSelected(row.doc.id) ? 'bg-blue-50/50' : 'hover:bg-[#fafafa]',
                ]"
              >
                <td class="px-4 py-3.5">
                  <input
                    type="checkbox"
                    class="h-3.5 w-3.5 rounded border-dm-border text-blue-600 focus:ring-blue-400"
                    :checked="isSelected(row.doc.id)"
                    @change="toggleSelect(row.doc.id)"
                  />
                </td>
                <td class="px-4 py-3.5">
                  <div
                    class="flex max-w-[360px] items-center gap-2"
                    :style="{ paddingLeft: `${row.depth * 20}px` }"
                  >
                    <FileText
                      v-if="(row.doc.doc_type || '').toLowerCase() === 'pdf'"
                      class="h-4 w-4 shrink-0 text-rose-500"
                    />
                    <FileSpreadsheet v-else class="h-4 w-4 shrink-0 text-emerald-600" />
                    <span class="truncate font-semibold text-dm-text" :title="row.doc.file_name">
                      {{ row.doc.file_name }}
                    </span>
                  </div>
                </td>
                <td class="px-4 py-3.5 font-mono text-dm-text-tertiary">
                  {{ formatBytes(row.doc.size_bytes) }}
                </td>
                <td class="px-4 py-3.5">
                  <div class="flex items-center justify-center gap-1.5">
                    <button
                      v-if="row.doc.remote_access_available && row.doc.feishu_url"
                      type="button"
                      class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-dm-primary-bg hover:text-blue-700"
                      :title="t('quotation.pages.imports.openFeishu')"
                      @click="handleOpenFeishu(row.doc, $event)"
                    >
                      <ExternalLink class="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary transition duration-100 hover:bg-slate-100 hover:text-dm-text"
                      :title="t('quotation.common.download')"
                      @click="handleDownload(row.doc, $event)"
                    >
                      <Loader2 v-if="downloadingId === row.doc.id" class="h-4 w-4 animate-spin" />
                      <Download v-else class="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="selectedCount > 0"
        class="fixed bottom-6 left-1/2 z-40 flex w-[min(92vw,28rem)] -translate-x-1/2 items-center justify-between gap-3 rounded-xl border border-blue-200 bg-white px-4 py-3 shadow-lg ring-1 ring-black/5"
      >
        <span class="text-sm font-semibold text-blue-800">
          {{ t('quotation.pages.imports.selectedCount', { count: selectedCount }) }}
        </span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-lg border border-dm-border bg-white px-2.5 py-1.5 text-xs font-semibold text-dm-text-secondary hover:bg-[#fafafa]"
            @click="clearSelection"
          >
            {{ t('quotation.common.cancel') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-lg bg-red-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            :disabled="deleting"
            @click="handleBatchDelete"
          >
            <Loader2 v-if="deleting" class="h-3 w-3 animate-spin" />
            <Trash2 v-else class="h-3 w-3" />
            {{ t('quotation.pages.imports.batchDelete') }}
          </button>
        </div>
      </div>
    </Teleport>

    <div
      v-if="deleteConfirmIds.length"
      class="fixed inset-0 z-50 flex items-center justify-center dm-modal-overlay p-4"
    >
      <div class="w-full max-w-md dm-card p-5 shadow-xl">
        <h3 class="text-sm font-bold text-dm-text">
          {{
            deleteConfirmIds.length === 1
              ? t('quotation.pages.imports.deleteModalTitle')
              : t('quotation.pages.imports.batchDeleteModalTitle')
          }}
        </h3>
        <p class="mt-2 text-sm text-dm-text-tertiary">
          {{
            deleteConfirmIds.length === 1
              ? t('quotation.pages.imports.deleteModalDesc', {
                  fileName: deleteConfirmDocs[0]?.file_name || '',
                })
              : t('quotation.pages.imports.batchDeleteModalDesc', {
                  count: deleteConfirmIds.length,
                })
          }}
        </p>
        <div class="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            class="rounded-lg border border-dm-border px-3 py-1.5 text-sm font-semibold text-dm-text-secondary hover:bg-[#fafafa]"
            @click="deleteConfirmIds = []"
          >
            {{ t('quotation.common.cancel') }}
          </button>
          <button
            type="button"
            :disabled="deleting"
            class="inline-flex items-center gap-1 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40"
            @click="confirmDelete"
          >
            <Loader2 v-if="deleting" class="h-3.5 w-3.5 animate-spin" />
            {{ t('quotation.actions.confirmDelete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
