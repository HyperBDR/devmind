<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileSearch,
  FileText,
  Folder,
  FolderInput,
  Loader2,
  RefreshCw,
  RotateCcw,
  Search,
  CheckCircle2,
  X,
} from 'lucide-vue-next'
import {
  downloadImportedDocument,
  listImportedFeishuDocuments,
  parseImportedDocument,
  type DocumentParseResult,
  type ImportedDocument,
} from '../api/documents'
import {
  checkFeishuFileAccess,
  getFeishuSyncJob,
  syncFeishuArchiveFolder,
  type FeishuArchiveFolder,
} from '../api/feishu'
import { FORM_SELECT_COMPACT_TRIGGER_CLASS } from '../utils/formFieldClasses'
import FormSelect from './FormSelect.vue'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const emit = defineEmits<{
  toast: [message: string, type?: 'success' | 'info' | 'error']
  quotationCreated: [quotationId: string]
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
const parsingIds = ref<Set<string>>(new Set())
let reconcileTimer: number | undefined

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

async function waitForSyncJob(jobId: string) {
  const deadline = Date.now() + 10 * 60 * 1000
  while (Date.now() < deadline) {
    const job = await getFeishuSyncJob(jobId)
    if (job.status === 'success') return job.result
    if (job.status === 'failed') {
      throw new Error(job.error_message || t('quotation.pages.imports.syncFailed'))
    }
    await wait(1000)
  }
  throw new Error(t('quotation.pages.imports.syncFailed'))
}

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
    let createdQuotationIds: string[] = []
    if (options.syncRemote) {
      const cachedItems = await listImportedFeishuDocuments().catch(
        () => null,
      )
      if (cachedItems) {
        docs.value = cachedItems
        rebuildArchiveTree(cachedItems)
      }
      try {
        let syncResult = await syncFeishuArchiveFolder({
          source: options.syncSource || 'user',
        })
        if (syncResult.sync_job_id && syncResult.sync_status !== 'success') {
          const completed = await waitForSyncJob(syncResult.sync_job_id)
          syncResult = {
            ...syncResult,
            ...(completed as Partial<typeof syncResult>),
          }
        }
        createdQuotationIds = [
          ...(syncResult.created_quotation_ids || []),
          ...(syncResult.updated_quotation_ids || []),
        ]
        if (
          options.syncSource !== 'automatic'
          && (syncResult.created_quotation_count || 0) > 0
        ) {
          notify(
            t('quotation.pages.imports.autoImportComplete', {
              count: syncResult.created_quotation_count || 0,
            }),
            'success',
          )
        }
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
    if (createdQuotationIds.length) {
      emit('quotationCreated', createdQuotationIds[0])
    }
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

function applyParseResult(documentId: string, result: DocumentParseResult) {
  docs.value = docs.value.map((item) =>
    item.id === documentId
      ? {
          ...item,
          parse_result_id: result.id,
          parse_status: result.status,
          parse_confidence: result.confidence,
          parsed_quotation_id: result.quotation_id || null,
        }
      : item,
  )
}

async function handleParse(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  parsingIds.value = new Set(parsingIds.value).add(doc.id)
  try {
    const result = await parseImportedDocument(doc.id)
    applyParseResult(doc.id, result)
    if (result.quotation_id) {
      notify(t('quotation.pages.imports.parseCreated'), 'success')
      emit('quotationCreated', result.quotation_id)
    } else {
      notify(t('quotation.pages.imports.parseNeedsAttention'), 'info')
    }
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t('quotation.pages.imports.parseFailed'), 'error')
    const items = await listImportedFeishuDocuments().catch(() => null)
    if (items) {
      docs.value = items
      rebuildArchiveTree(items)
    }
  } finally {
    const next = new Set(parsingIds.value)
    next.delete(doc.id)
    parsingIds.value = next
  }
}

async function handleReviewParse(doc: ImportedDocument, event?: Event) {
  event?.stopPropagation()
  if (doc.parse_status === 'confirmed' && doc.parsed_quotation_id) {
    emit('quotationCreated', doc.parsed_quotation_id)
  }
}

function canParse(doc: ImportedDocument): boolean {
  return !isTemporaryFile(doc)
    && ['excel', 'pdf'].includes((doc.doc_type || '').toLowerCase())
}

function isTemporaryFile(doc: ImportedDocument): boolean {
  return String(doc.file_name || '').toLowerCase().startsWith('~$')
}

function parseStatusLabel(doc: ImportedDocument): string {
  if (isTemporaryFile(doc)) return t('quotation.pages.imports.statusTemporary')
  if (!canParse(doc)) return t('quotation.pages.imports.parseUnsupported')
  const labels: Record<string, string> = {
    unparsed: t('quotation.pages.imports.statusUnparsed'),
    pending: t('quotation.pages.imports.statusParsePending'),
    running: t('quotation.pages.imports.statusParsing'),
    ready: t('quotation.pages.imports.statusParseReady'),
    review_required: t('quotation.pages.imports.statusParseReview'),
    confirmed: t('quotation.pages.imports.statusParseConfirmed'),
    not_quotation: t('quotation.pages.imports.statusNotQuotation'),
    failed: t('quotation.pages.imports.statusParseFailed'),
  }
  return labels[doc.parse_status || 'unparsed'] || labels.unparsed
}

function parseStatusClass(doc: ImportedDocument): string {
  if (isTemporaryFile(doc)) return 'bg-violet-50 text-violet-700 ring-violet-200'
  if (doc.parse_status === 'confirmed') return 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  if (doc.parse_status === 'ready') return 'bg-blue-50 text-blue-700 ring-blue-200'
  if (doc.parse_status === 'review_required') return 'bg-amber-50 text-amber-700 ring-amber-200'
  if (doc.parse_status === 'not_quotation') return 'bg-slate-100 text-slate-600 ring-slate-300'
  if (doc.parse_status === 'failed') return 'bg-red-50 text-red-700 ring-red-200'
  return 'bg-slate-50 text-slate-500 ring-slate-200'
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
    return [doc.file_name, doc.parsed_quote_no]
      .some((value) => String(value || '').toLowerCase().includes(q))
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

const rootClass = computed(() =>
  props.embedded
    ? 'space-y-6'
    : 'flex h-[calc(100vh-7.5rem)] flex-col gap-4 overflow-hidden',
)

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
            class="h-10 w-full rounded-lg border border-dm-border-light bg-slate-50/70 py-2 pl-9 pr-9 text-sm text-dm-text transition placeholder:text-slate-400 hover:bg-white focus:border-blue-300 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-100"
          />
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <button
            v-if="search"
            type="button"
            class="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-200 hover:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-blue-200"
            :aria-label="t('quotation.pages.imports.clearSearch')"
            :title="t('quotation.pages.imports.clearSearch')"
            @click="search = ''"
          >
            <X class="h-4 w-4" />
          </button>
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
              <th class="px-4 py-3">{{ t('quotation.pages.imports.tableFileName') }}</th>
              <th class="px-4 py-3">{{ t('quotation.pages.imports.tableSize') }}</th>
              <th class="min-w-[120px] px-4 py-3 text-center">
                {{ t('quotation.pages.imports.tableActions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-sm">
            <tr v-if="treeRows.length === 0">
              <td colspan="3" class="px-4 py-12 text-center text-dm-text-tertiary">
                {{ t('quotation.pages.imports.emptyResults') }}
              </td>
            </tr>
            <template v-for="row in treeRows" v-else :key="row.key">
              <tr
                v-if="row.kind === 'folder'"
                class="cursor-pointer bg-slate-50/80 transition hover:bg-blue-50/70"
                @click="toggleFolder(row.token)"
              >
                <td colspan="3" class="px-4 py-2.5">
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
              <tr v-else class="transition duration-150 hover:bg-[#fafafa]">
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
                    <div class="min-w-0">
                      <span class="block truncate font-semibold text-dm-text" :title="row.doc.file_name">
                        {{ row.doc.file_name }}
                      </span>
                      <span
                        class="mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset"
                        :class="parseStatusClass(row.doc)"
                      >
                        {{ parseStatusLabel(row.doc) }}
                      </span>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3.5 font-mono text-dm-text-tertiary">
                  {{ formatBytes(row.doc.size_bytes) }}
                </td>
                <td class="px-4 py-3.5">
                  <div class="flex items-center justify-center gap-1.5">
                    <button
                      v-if="canParse(row.doc) && (!row.doc.parse_result_id || row.doc.parse_status === 'failed')"
                      type="button"
                      class="cursor-pointer rounded-sm p-1 text-blue-600 transition duration-100 hover:bg-blue-50 hover:text-blue-800 disabled:cursor-wait disabled:opacity-50"
                      :disabled="parsingIds.has(row.doc.id)"
                      :title="t('quotation.pages.imports.parseAction')"
                      @click="handleParse(row.doc, $event)"
                    >
                      <Loader2 v-if="parsingIds.has(row.doc.id)" class="h-4 w-4 animate-spin" />
                      <FileSearch v-else class="h-4 w-4" />
                    </button>
                    <button
                      v-else-if="canParse(row.doc) && row.doc.parse_result_id && row.doc.parse_status === 'confirmed'"
                      type="button"
                      class="cursor-pointer rounded-sm p-1 text-blue-600 transition duration-100 hover:bg-blue-50 hover:text-blue-800"
                      :title="t('quotation.pages.imports.viewQuotation')"
                      @click="handleReviewParse(row.doc, $event)"
                    >
                      <CheckCircle2 class="h-4 w-4 text-emerald-600" />
                    </button>
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

  </div>
</template>
