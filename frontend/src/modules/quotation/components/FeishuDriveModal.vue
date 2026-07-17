<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Cloud,
  FileText,
  FolderOpen,
  Link2,
  Loader2,
  RefreshCw,
  Users,
  X,
} from 'lucide-vue-next'
import {
  getFeishuDriveTree,
  getFeishuStatus,
  importFeishuFile,
  isFeishuFolderItem,
  listFeishuFolder,
  resolveFeishuOpenToken,
  setPreferredFeishuFolder,
  startFeishuOAuth,
  type FeishuDriveTree,
  type FeishuDriveTreeNode,
  type FeishuFileItem,
} from '../api/feishu'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import FeishuDriveNavNode from './FeishuDriveNavNode.vue'

const { t } = useQuotationI18n()
const NS = 'quotation.components.feishuDrive'
const route = useRoute()

const props = defineProps<{
  open: boolean
  mode?: 'default' | 'pickUploadFolder'
  pickIntent?: 'upload' | 'setFolder'
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  close: []
  toast: [message: string, type?: 'success' | 'info' | 'error']
  folderPick: [folder: { token: string; name: string }]
}>()

interface BreadcrumbItem {
  token: string
  name: string
}

const loading = ref(false)
const connecting = ref(false)
const connected = ref(false)
const configured = ref(false)
const feishuUser = ref<string | null>(null)
const preferredToken = ref<string | null>(null)
const preferredName = ref<string | null>(null)
const path = ref<BreadcrumbItem[]>([])
const currentToken = ref<string | null>(null)
const currentName = ref('')
const files = ref<FeishuFileItem[]>([])
const selected = ref<Record<string, boolean>>({})
const error = ref('')
const driveTree = ref<FeishuDriveTree | null>(null)
const myFoldersExpanded = ref(true)
const sharedFoldersExpanded = ref(true)
const navExpandedMap = ref<Record<string, boolean>>({})
const navChildrenMap = ref<Record<string, FeishuDriveTreeNode[]>>({})
const navLoadingMap = ref<Record<string, boolean>>({})

const selectedFiles = computed(() =>
  files.value.filter((file) => selected.value[file.token] && !isFeishuFolderItem(file)),
)

const isCurrentPreferred = computed(() =>
  Boolean(preferredToken.value && currentToken.value && preferredToken.value === currentToken.value),
)

const isPickUploadMode = computed(() => props.mode === 'pickUploadFolder')

const isRootUploadTarget = computed(() =>
  props.pickIntent === 'upload' &&
  Boolean(
    currentToken.value &&
    driveTree.value?.my_root?.token &&
    currentToken.value === driveTree.value.my_root.token,
  ),
)

const pickConfirmLabel = computed(() =>
  props.pickIntent === 'upload'
    ? t(`${NS}.selectAndUpload`)
    : t(`${NS}.selectFolder`),
)

const modalTitle = computed(() => {
  if (!isPickUploadMode.value) return t(`${NS}.title`)
  return props.pickIntent === 'upload'
    ? t(`${NS}.titlePickStep1`)
    : t(`${NS}.pickFolderTitle`)
})

function mySpaceLabel() {
  return t(`${NS}.mySpace`)
}

function currentFolderLabel() {
  return t(`${NS}.currentFolder`)
}

function selectedFolderLabel() {
  return t(`${NS}.selectedFolder`)
}

function folderLabel() {
  return t(`${NS}.folder`)
}

function resolveFolderName(
  folderName?: string | null,
  isRoot?: boolean,
  fallback?: 'mySpace' | 'current' | 'selected' | 'folder',
) {
  if (isRoot) return mySpaceLabel()
  if (folderName) return folderName
  if (fallback === 'selected') return selectedFolderLabel()
  if (fallback === 'folder') return folderLabel()
  return currentFolderLabel()
}

const headerSubtitle = computed(() => {
  if (isPickUploadMode.value) {
    return connected.value
      ? t(`${NS}.subtitlePickConnected`)
      : t(`${NS}.subtitlePickDisconnected`)
  }
  if (!connected.value) {
    return t(`${NS}.subtitleDisconnected`)
  }
  return feishuUser.value
    ? t(`${NS}.subtitleConnectedWithUser`, { user: feishuUser.value })
    : t(`${NS}.subtitleConnected`)
})

function notify(message: string, type: 'success' | 'info' | 'error' = 'info') {
  emit('toast', message, type)
}

function closeModal() {
  emit('update:open', false)
  emit('close')
}

async function loadFolder(folderToken?: string | null, folderName?: string) {
  const folder = await listFeishuFolder(folderToken || undefined)
  currentToken.value = folder.folder_token
  currentName.value = resolveFolderName(
    folderName || folder.folder_name,
    folder.is_root,
    folder.is_root ? 'mySpace' : 'current',
  )
  files.value = folder.files || []
  selected.value = {}
  return folder
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const status = await getFeishuStatus()
    configured.value = status.configured
    connected.value = status.connected
    feishuUser.value = status.feishu_user_name || null
    preferredToken.value = status.preferred_folder_token || null
    preferredName.value = status.preferred_folder_name || null

    if (!status.configured) {
      error.value = t(`${NS}.errorNotConfigured`)
      files.value = []
      return
    }
    if (!status.connected) {
      files.value = []
      path.value = []
      currentToken.value = null
      return
    }

    const startToken =
      currentToken.value || status.preferred_folder_token || undefined
    const folder = await loadFolder(
      startToken,
      currentName.value || status.preferred_folder_name || undefined,
    )
    if (!path.value.length) {
      if (status.preferred_folder_token && startToken === status.preferred_folder_token) {
        path.value = [{
          token: folder.folder_token,
          name: resolveFolderName(
            status.preferred_folder_name,
            false,
            'selected',
          ),
        }]
      } else {
        path.value = [{
          token: folder.folder_token,
          name: t(`${NS}.myFolders`),
        }]
      }
    }
    await loadDriveTree()
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t(`${NS}.errorLoadFailed`)
    files.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) void refresh()
  },
)

async function handleConnect() {
  connecting.value = true
  try {
    const url = await startFeishuOAuth(route.fullPath)
    window.location.href = url
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t(`${NS}.errorOAuthFailed`), 'error')
    connecting.value = false
  }
}

async function loadDriveTree() {
  if (!connected.value) {
    driveTree.value = null
    return
  }
  try {
    driveTree.value = await getFeishuDriveTree()
  } catch (err: unknown) {
    // Keep browsing usable even if nav discovery fails.
    if (!driveTree.value) {
      notify(
        err instanceof Error ? err.message : t(`${NS}.errorLoadTreeFailed`),
        'error',
      )
    }
  }
}

async function toggleNavExpand(
  token: string,
  node: FeishuDriveTreeNode,
  section: 'my' | 'shared',
  ancestors: FeishuDriveTreeNode[] = [],
) {
  const next = !navExpandedMap.value[token]
  if (!next) {
    navExpandedMap.value = { ...navExpandedMap.value, [token]: false }
    return
  }
  // Expanding also opens the folder so the right pane shows its files.
  await openNavFolder(node, section, ancestors)
}

async function openNavFolder(
  node: FeishuDriveTreeNode,
  section: 'my' | 'shared',
  ancestors: FeishuDriveTreeNode[] = [],
) {
  loading.value = true
  error.value = ''
  try {
    const folder = await loadFolder(node.token, node.name)
    const name = resolveFolderName(
      folder.folder_name || node.name,
      false,
      'folder',
    )
    path.value = [
      {
        token: section === 'my'
          ? (driveTree.value?.my_root.token || 'root')
          : 'shared-root',
        name: section === 'my'
          ? t(`${NS}.myFolders`)
          : t(`${NS}.sharedFolders`),
      },
      ...ancestors.map((item) => ({
        token: item.token,
        name: item.name,
      })),
      { token: folder.folder_token, name },
    ]
    currentName.value = name
    if (!navChildrenMap.value[node.token]) {
      const children = (folder.files || [])
        .filter((file) => isFeishuFolderItem(file))
        .map((file) => ({
          token: resolveFeishuOpenToken(file),
          name: file.name || resolveFeishuOpenToken(file),
          type: 'folder',
        }))
      navChildrenMap.value = {
        ...navChildrenMap.value,
        [node.token]: children,
      }
    }
    navExpandedMap.value = {
      ...navExpandedMap.value,
      [node.token]: true,
    }
  } catch (err: unknown) {
    error.value =
      err instanceof Error ? err.message : t(`${NS}.errorOpenFolderFailed`)
  } finally {
    loading.value = false
  }
}

async function openMyFoldersRoot() {
  await openRoot()
  if (driveTree.value?.my_root) {
    path.value = [{
      token: driveTree.value.my_root.token,
      name: t(`${NS}.myFolders`),
    }]
    currentName.value = t(`${NS}.myFolders`)
  }
}

async function openRoot() {
  loading.value = true
  error.value = ''
  try {
    const folder = await listFeishuFolder('root')
    path.value = [{
      token: folder.folder_token,
      name: resolveFolderName(folder.folder_name, folder.is_root, 'mySpace'),
    }]
    currentToken.value = folder.folder_token
    currentName.value = resolveFolderName(
      folder.folder_name,
      folder.is_root,
      'mySpace',
    )
    files.value = folder.files || []
    selected.value = {}
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t(`${NS}.errorOpenRootFailed`)
  } finally {
    loading.value = false
  }
}

async function enterFolder(file: FeishuFileItem) {
  if (!isFeishuFolderItem(file)) return
  loading.value = true
  error.value = ''
  try {
    const openToken = resolveFeishuOpenToken(file)
    await loadFolder(openToken, file.name)
    path.value = [...path.value, {
      token: openToken,
      name: file.name || folderLabel(),
    }]
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t(`${NS}.errorOpenFolderFailed`)
  } finally {
    loading.value = false
  }
}

async function jumpToBreadcrumb(index: number) {
  const target = path.value[index]
  if (!target) return
  if (target.token === 'shared-root') {
    files.value = []
    currentToken.value = null
    currentName.value = t(`${NS}.sharedFolders`)
    path.value = path.value.slice(0, 1)
    selected.value = {}
    return
  }
  if (
    driveTree.value?.my_root?.token
    && target.token === driveTree.value.my_root.token
    && index === 0
  ) {
    await openMyFoldersRoot()
    return
  }
  loading.value = true
  error.value = ''
  try {
    await loadFolder(target.token, target.name)
    path.value = path.value.slice(0, index + 1)
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t(`${NS}.errorOpenPathFailed`)
  } finally {
    loading.value = false
  }
}

async function goBackOneLevel() {
  if (path.value.length <= 1) {
    await openRoot()
    return
  }
  await jumpToBreadcrumb(path.value.length - 2)
}

const visibleFiles = computed(() => {
  const list = isPickUploadMode.value
    ? files.value.filter((file) => isFeishuFolderItem(file))
    : files.value.slice()
  return list.sort((a, b) => {
    const af = isFeishuFolderItem(a) ? 0 : 1
    const bf = isFeishuFolderItem(b) ? 0 : 1
    if (af !== bf) return af - bf
    return (a.name || '').localeCompare(b.name || '', 'zh')
  })
})

const visibleFileCount = computed(
  () => visibleFiles.value.filter((file) => !isFeishuFolderItem(file)).length,
)

const visibleFolderCount = computed(
  () => visibleFiles.value.filter((file) => isFeishuFolderItem(file)).length,
)

async function handleSetPreferred() {
  if (!currentToken.value) {
    notify(t(`${NS}.toastInvalidFolder`), 'error')
    return
  }
  loading.value = true
  try {
    const result = await setPreferredFeishuFolder(currentToken.value, currentName.value)
    preferredToken.value = result.preferred_folder_token
    preferredName.value = result.preferred_folder_name || currentName.value
    notify(
      t(`${NS}.toastPreferredSet`, {
        name: result.preferred_folder_name || currentName.value,
      }),
      'success',
    )
  } catch (err: unknown) {
    notify(
      err instanceof Error ? err.message : t(`${NS}.toastSetPreferredFailed`),
      'error',
    )
  } finally {
    loading.value = false
  }
}

function toggleFile(token: string) {
  selected.value = { ...selected.value, [token]: !selected.value[token] }
}

async function handleImportSelected() {
  if (!selectedFiles.value.length) {
    notify(t(`${NS}.toastSelectImport`), 'info')
    return
  }
  loading.value = true
  try {
    for (const file of selectedFiles.value) {
      await importFeishuFile(file.token, file.name, file.type, file.url)
    }
    notify(
      t(`${NS}.toastImportSuccess`, { count: selectedFiles.value.length }),
      'success',
    )
  } catch (err: unknown) {
    notify(err instanceof Error ? err.message : t(`${NS}.toastImportFailed`), 'error')
  } finally {
    loading.value = false
  }
}

function handleConfirmUploadFolder() {
  if (!currentToken.value) {
    notify(t(`${NS}.toastSelectUploadFolder`), 'error')
    return
  }
  if (isRootUploadTarget.value) {
    notify(t(`${NS}.toastSelectUploadFolder`), 'error')
    return
  }
  if (props.pickIntent === 'setFolder') {
    void handleSetPreferred().then(() => closeModal())
    return
  }
  emit('folderPick', {
    token: currentToken.value,
    name: currentName.value || currentFolderLabel(),
  })
  closeModal()
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center dm-modal-overlay p-4"
  >
    <div
      class="flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
    >
      <div class="flex flex-col gap-3 border-b border-slate-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <Cloud class="h-4 w-4" />
          </div>
          <div class="min-w-0">
            <h3 class="truncate text-[15px] font-semibold text-slate-900">
              {{ modalTitle }}
            </h3>
            <p class="mt-0.5 truncate text-[11px] text-slate-500">
              {{ headerSubtitle }}
            </p>
          </div>
        </div>

        <div class="flex w-full shrink-0 items-center justify-end gap-2 sm:w-auto">
          <button
            v-if="!isPickUploadMode"
            type="button"
            class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            :disabled="!connected || !currentToken || loading || isCurrentPreferred"
            @click="handleSetPreferred"
          >
            <Check class="h-3.5 w-3.5" />
            {{ isCurrentPreferred ? t(`${NS}.alreadyPreferred`) : t(`${NS}.setPreferred`) }}
          </button>
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            :disabled="loading"
            @click="refresh"
          >
            <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': loading }" />
            {{ t(`${NS}.refresh`) }}
          </button>
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1 rounded-md bg-blue-600 px-3 text-[11px] font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="connecting || !configured"
            :title="connected ? t(`${NS}.reconnectTitle`) : t(`${NS}.connectTitle`)"
            @click="handleConnect"
          >
            <Loader2 v-if="connecting" class="h-3.5 w-3.5 animate-spin" />
            <Link2 v-else class="h-3.5 w-3.5" />
            {{ connected ? t(`${NS}.reconnect`) : t(`${NS}.connect`) }}
          </button>
          <button
            type="button"
            class="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-slate-50 hover:text-slate-700"
            @click="closeModal"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-auto bg-slate-50/40 px-6 py-5">
        <div
          v-if="error"
          class="mb-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-[11px] text-red-600"
        >
          {{ error }}
        </div>

        <div
          v-if="!connected"
          class="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-12 text-center"
        >
          <p class="text-sm font-semibold text-slate-900">{{ t(`${NS}.notConnectedTitle`) }}</p>
          <p class="mt-1 text-[11px] text-slate-500">
            {{ t(`${NS}.notConnectedHint`) }}
          </p>
        </div>

        <template v-else>
          <div class="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
            <aside class="h-fit rounded-lg border border-slate-200 bg-white p-3 text-[12px] shadow-sm">
              <p class="px-1 pb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {{ t(`${NS}.driveNavTitle`) }}
              </p>
              <button
                type="button"
                class="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left font-semibold text-slate-800 hover:bg-slate-50"
                @click="myFoldersExpanded = !myFoldersExpanded; openMyFoldersRoot()"
              >
                <ChevronRight
                  class="h-3.5 w-3.5 shrink-0 transition-transform"
                  :class="myFoldersExpanded ? 'rotate-90' : ''"
                />
                <FolderOpen class="h-3.5 w-3.5 shrink-0 text-amber-500" />
                <span class="truncate">{{ t(`${NS}.myFolders`) }}</span>
              </button>
              <div
                v-if="myFoldersExpanded"
                class="ml-2 space-y-0.5 border-l border-slate-100 pl-1"
              >
                <FeishuDriveNavNode
                  v-for="folder in driveTree?.my_folders || []"
                  :key="`my-${folder.token}`"
                  :node="folder"
                  section="my"
                  :active-token="currentToken"
                  :ancestors="[]"
                  :expanded-map="navExpandedMap"
                  :children-map="navChildrenMap"
                  :loading-map="navLoadingMap"
                  @toggle="toggleNavExpand"
                  @select="openNavFolder"
                />
                <p
                  v-if="!(driveTree?.my_folders || []).length"
                  class="px-2 py-1 text-[10px] text-slate-400"
                >
                  {{ t(`${NS}.myFoldersEmpty`) }}
                </p>
              </div>

              <button
                type="button"
                class="mt-2 flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left font-semibold text-slate-800 hover:bg-slate-50"
                @click="sharedFoldersExpanded = !sharedFoldersExpanded"
              >
                <ChevronRight
                  class="h-3.5 w-3.5 shrink-0 transition-transform"
                  :class="sharedFoldersExpanded ? 'rotate-90' : ''"
                />
                <Users class="h-3.5 w-3.5 shrink-0 text-sky-600" />
                <span class="truncate">{{ t(`${NS}.sharedFolders`) }}</span>
              </button>
              <div
                v-if="sharedFoldersExpanded"
                class="ml-2 space-y-0.5 border-l border-slate-100 pl-1"
              >
                <FeishuDriveNavNode
                  v-for="folder in driveTree?.shared_folders || []"
                  :key="`shared-${folder.token}`"
                  :node="folder"
                  section="shared"
                  :active-token="currentToken"
                  :ancestors="[]"
                  :expanded-map="navExpandedMap"
                  :children-map="navChildrenMap"
                  :loading-map="navLoadingMap"
                  @toggle="toggleNavExpand"
                  @select="openNavFolder"
                />
                <p
                  v-if="!(driveTree?.shared_folders || []).length"
                  class="px-2 py-1 text-[10px] text-slate-400"
                >
                  {{
                    driveTree?.can_discover_shared
                      ? t(`${NS}.sharedFoldersEmpty`)
                      : t(`${NS}.sharedFoldersNeedReconnect`)
                  }}
                </p>
              </div>
            </aside>

            <section class="min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm">
              <div class="border-b border-slate-100 px-4 py-3">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                      {{ t(`${NS}.currentPathTitle`) }}
                    </p>
                    <div class="mt-1 flex min-w-0 flex-wrap items-center gap-1 text-[12px]">
                      <button
                        v-for="(item, index) in path"
                        :key="`${item.token}-${index}`"
                        type="button"
                        class="inline-flex max-w-[180px] items-center gap-1 truncate rounded-md px-1.5 py-1 font-medium text-slate-700 hover:bg-slate-50"
                        @click="jumpToBreadcrumb(index)"
                      >
                        <ChevronRight
                          v-if="index > 0"
                          class="h-3 w-3 shrink-0 text-slate-300"
                        />
                        <span class="truncate">{{ item.name }}</span>
                      </button>
                    </div>
                  </div>
                  <button
                    v-if="isPickUploadMode"
                    type="button"
                    class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 px-3 text-[11px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                    :disabled="!connected || loading"
                    @click="goBackOneLevel"
                  >
                    <ArrowLeft class="h-3.5 w-3.5" />
                    {{ t(`${NS}.goBack`) }}
                  </button>
                </div>
              </div>

              <div class="px-4 py-3">
                <div
                  v-if="!isPickUploadMode && (visibleFolderCount || visibleFileCount)"
                  class="mb-2 text-[10px] text-slate-400"
                >
                  {{
                    t(`${NS}.listingSummary`, {
                      folders: visibleFolderCount,
                      files: visibleFileCount,
                    })
                  }}
                </div>

                <div
                  v-if="loading && !visibleFiles.length"
                  class="flex items-center justify-center gap-2 py-14 text-sm text-slate-400"
                >
                  <Loader2 class="h-4 w-4 animate-spin" />
                  {{ t(`${NS}.loading`) }}
                </div>
                <div
                  v-else-if="!visibleFiles.length"
                  class="rounded-md border border-dashed border-slate-200 bg-slate-50/60 px-4 py-14 text-center text-[12px] text-slate-400"
                >
                  {{
                    isPickUploadMode
                      ? t(`${NS}.emptyPick`)
                      : t(`${NS}.emptyDefault`)
                  }}
                </div>
                <div v-else class="space-y-1.5">
                  <div
                    v-for="file in visibleFiles"
                    :key="file.token"
                    class="flex items-center gap-3 rounded-md border border-slate-100 px-3 py-2.5 hover:border-blue-100 hover:bg-blue-50/30"
                  >
                    <button
                      v-if="isFeishuFolderItem(file)"
                      type="button"
                      class="flex min-w-0 flex-1 items-center gap-3 text-left"
                      @click="enterFolder(file)"
                    >
                      <FolderOpen class="h-4 w-4 shrink-0 text-amber-500" />
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-[12px] font-semibold text-slate-800">
                          {{ file.name || file.token }}
                        </div>
                        <div class="mt-0.5 text-[10px] text-slate-400">
                          {{ t(`${NS}.folderEnterHint`) }}
                        </div>
                      </div>
                      <ChevronRight class="h-4 w-4 shrink-0 text-slate-300" />
                    </button>
                    <label v-else class="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-300 text-blue-600"
                        :checked="Boolean(selected[file.token])"
                        @change="toggleFile(file.token)"
                      />
                      <FileText class="h-4 w-4 shrink-0 text-slate-500" />
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-[12px] font-medium text-slate-800">
                          {{ file.name || file.token }}
                        </div>
                        <div class="mt-0.5 text-[9px] text-slate-400">
                          {{ file.type || 'file'
                          }}{{ file.modified_time ? ` · ${file.modified_time}` : '' }}
                        </div>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </template>
      </div>

      <div class="border-t border-slate-100 bg-white px-6 py-4">
        <template v-if="isPickUploadMode">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {{ t(`${NS}.uploadTargetLabel`) }}
              </p>
              <p class="mt-0.5 max-w-[360px] truncate text-[13px] font-semibold text-slate-900">
                {{ currentName || '—' }}
              </p>
              <p
                v-if="isRootUploadTarget"
                class="mt-1 max-w-[420px] text-[11px] font-medium text-amber-600"
              >
                {{ t(`${NS}.uploadRootDisabledHint`) }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 min-w-[140px] items-center justify-center rounded-md border border-slate-200 px-4 text-[12px] font-medium text-slate-600 hover:bg-slate-50"
                @click="closeModal"
              >
                {{ t(`${NS}.cancel`) }}
              </button>
              <button
                type="button"
                class="inline-flex h-9 min-w-[180px] items-center justify-center gap-1 rounded-md bg-blue-600 px-4 text-[12px] font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
                :disabled="!connected || !currentToken || isRootUploadTarget || loading"
                @click="handleConfirmUploadFolder"
              >
                <Check class="h-3.5 w-3.5 shrink-0" />
                {{ pickConfirmLabel }}
              </button>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="flex items-center justify-between gap-3">
            <span class="text-[11px] text-slate-400">
              {{ t(`${NS}.selectedCount`, { count: selectedFiles.length }) }}
            </span>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
                @click="closeModal"
              >
                {{ t(`${NS}.close`) }}
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
                :disabled="!selectedFiles.length || loading || !connected"
                @click="handleImportSelected"
              >
                {{ t(`${NS}.importSelected`) }}
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
