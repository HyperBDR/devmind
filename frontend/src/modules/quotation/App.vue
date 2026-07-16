<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  PlusCircle,
  Settings,
  Search,
  CheckCircle,
  LogOut,
  FolderInput,
} from 'lucide-vue-next'
import type {
  DiscountOption,
  Product,
  ProductLineOption,
  Quotation,
  QuoteProductLine,
  Service,
} from './types'
import {
  MOCK_CATALOG_VERSION,
  MOCK_DISCOUNTS,
  MOCK_PRODUCTS,
  MOCK_SERVICES,
} from './data'
import Dashboard from './components/Dashboard.vue'
import LoginPage from './components/LoginPage.vue'
import QuotationList from './components/QuotationList.vue'
import QuotationCreate from './components/QuotationCreate.vue'
import QuotationDetails from './components/QuotationDetails.vue'
import ImportedDocumentsPage from './components/ImportedDocumentsPage.vue'
import ProductServiceManager from './components/ProductServiceManager.vue'
import { downloadQuotationExcel } from './utils/excelGenerator'
import { isFeishuLinkOnlyUpdate, reconcileFeishuQuotationLinks } from './utils/feishuLinkState'
import {
  loadProductLineOptions,
  saveCustomProductLineOptions,
} from './utils/quotationNumbering'
import { filterQuotationsByUser, ensureQuoteOwnership } from './utils/quoteOwnership'
import { clearCreateQuoteDraft } from './utils/createDraftStorage'
import { upsertDescriptionsToCatalog } from './utils/descriptionCatalog'
import { PAYMENT_TERM_OPTIONS } from './utils/paymentTerms'
import {
  getCatalog,
  importLegacyCatalog,
  updateCatalog,
  type UserQuotationCatalog,
  type UserQuotationCatalogPayload,
} from './api/catalog'
import {
  createQuotation as createQuotationApi,
  deleteQuotation as deleteQuotationApi,
  generateQuotation as generateQuotationApi,
  listQuotations,
  updateQuotation as updateQuotationApi,
} from './api/quotations'
import { useAuthStore } from './stores/auth'
import { useQuotationI18n } from './composables/useQuotationI18n'

const auth = useAuthStore()
const { t, quoteStatusLabel } = useQuotationI18n()
const route = useRoute()
const router = useRouter()

const TAB_ROUTES: Record<string, string> = {
  dashboard: '/quotation/dashboard',
  list: '/quotation/list',
  create: '/quotation/create',
  imports: '/quotation/imports',
  catalog: '/quotation/catalog',
}

function tabFromRoutePath(path: string): string {
  if (path.startsWith('/quotation/details/')) return 'details'
  if (path.startsWith('/quotation/list')) return 'list'
  if (path.startsWith('/quotation/create')) return 'create'
  if (path.startsWith('/quotation/imports')) return 'imports'
  if (path.startsWith('/quotation/catalog')) return 'catalog'
  return 'dashboard'
}

function syncTabFromRoute() {
  if (!auth.embeddedAuth) return

  const path = route.path
  const nextTab = tabFromRoutePath(path)
  currentTab.value = nextTab

  if (nextTab === 'details' && typeof route.params.id === 'string') {
    selectedQuotationId.value = route.params.id
    return
  }

  if (nextTab !== 'details') {
    selectedQuotationId.value = null
  }

  if (nextTab === 'create') {
    const editId = route.query.edit
    editingQuoteId.value = typeof editId === 'string' ? editId : null
    return
  }

  editingQuoteId.value = null
}

const quotations = ref<Quotation[]>([])

function shouldUseStoredCatalog() {
  return localStorage.getItem('qmp_catalog_version') === MOCK_CATALOG_VERSION
}

const products = ref<Product[]>((() => {
  const saved = localStorage.getItem('qmp_products')
  return saved && shouldUseStoredCatalog()
    ? JSON.parse(saved)
    : MOCK_PRODUCTS.map((item) => ({ ...item }))
})())

const services = ref<Service[]>((() => {
  const saved = localStorage.getItem('qmp_services')
  return saved && shouldUseStoredCatalog()
    ? JSON.parse(saved)
    : MOCK_SERVICES.map((item) => ({ ...item }))
})())

const discounts = ref<DiscountOption[]>((() => {
  const saved = localStorage.getItem('qmp_discounts')
  return saved && shouldUseStoredCatalog()
    ? JSON.parse(saved)
    : MOCK_DISCOUNTS.map((item) => ({ ...item }))
})())

const productLineOptions = ref<ProductLineOption[]>(loadProductLineOptions())
const catalogReady = ref(false)
let catalogSaveTimer: ReturnType<typeof setTimeout> | null = null
let catalogSaveQueue = Promise.resolve()

function catalogPayload(): UserQuotationCatalogPayload {
  return {
    version: MOCK_CATALOG_VERSION,
    products: products.value,
    services: services.value,
    discounts: discounts.value,
    product_lines: productLineOptions.value,
    payment_terms: PAYMENT_TERM_OPTIONS,
  }
}

function applyCatalog(catalog: UserQuotationCatalog) {
  products.value = catalog.products
  services.value = catalog.services
  discounts.value = catalog.discounts
  productLineOptions.value = catalog.product_lines
}

async function hydrateUserCatalog() {
  catalogReady.value = false
  try {
    const serverCatalog = await getCatalog()
    if (serverCatalog.initialized) {
      applyCatalog(serverCatalog)
      localStorage.setItem('qmp_catalog_migrated_v1', '1')
      await nextTick()
      catalogReady.value = true
      return
    }

    const result = await importLegacyCatalog(catalogPayload())
    applyCatalog(result.catalog)
    localStorage.setItem('qmp_catalog_migrated_v1', '1')
    await nextTick()
    catalogReady.value = true
  } catch (error) {
    console.error('Unable to load quotation catalog', error)
    const message = error instanceof Error ? error.message : t('quotation.app.loadFailed')
    triggerToast(message, 'error')
  }
}

function queueCatalogSave() {
  if (!catalogReady.value) return
  if (catalogSaveTimer) clearTimeout(catalogSaveTimer)
  catalogSaveTimer = setTimeout(() => {
    const payload = catalogPayload()
    catalogSaveQueue = catalogSaveQueue
      .then(() => updateCatalog(payload))
      .then(() => undefined)
      .catch((error) => {
        console.error('Unable to save quotation catalog', error)
      })
  }, 250)
}

watch(
  products,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_products', JSON.stringify(value))
    queueCatalogSave()
  },
  { deep: true },
)

watch(
  services,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_services', JSON.stringify(value))
    queueCatalogSave()
  },
  { deep: true },
)

watch(
  discounts,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_discounts', JSON.stringify(value))
    queueCatalogSave()
  },
  { deep: true },
)

watch(
  productLineOptions,
  (value) => {
    saveCustomProductLineOptions(value)
    queueCatalogSave()
  },
  { deep: true },
)

const initialTab = tabFromRoutePath(route.path)
const currentTab = ref(initialTab)
const selectedQuotationId = ref<string | null>(
  initialTab === 'details' && typeof route.params.id === 'string'
    ? route.params.id
    : null,
)
const editingQuoteId = ref<string | null>(
  initialTab === 'create' && typeof route.query.edit === 'string'
    ? route.query.edit
    : null,
)

const toastMessage = ref<string | null>(null)
const toastType = ref<'success' | 'info' | 'error'>('success')

function triggerToast(msg: string, type: 'success' | 'info' | 'error' = 'success') {
  toastMessage.value = msg
  toastType.value = type
  setTimeout(() => {
    toastMessage.value = null
  }, 4000)
}

async function refreshQuotations() {
  try {
    quotations.value = await listQuotations()
    const staleLinks = await reconcileFeishuQuotationLinks(quotations.value)
    if (staleLinks) {
      quotations.value = await listQuotations()
    }
  } catch (error: unknown) {
    console.error(error)
    const message = error instanceof Error ? error.message : t('quotation.app.loadFailed')
    triggerToast(message, 'error')
  }
}

onMounted(async () => {
  await auth.bootstrap()
  if (auth.isAuthenticated) {
    await Promise.all([refreshQuotations(), hydrateUserCatalog()])
  }

  const params = new URLSearchParams(window.location.search)
  if (params.get('feishu') === 'connected') {
    triggerToast(t('quotation.app.feishuConnected'), 'success')
    if (auth.embeddedAuth) {
      await router.replace('/quotation/list')
    } else {
      currentTab.value = 'list'
    }
    params.delete('feishu')
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}${window.location.hash}`
    window.history.replaceState({}, '', next)
  }
})

watch(
  () => route.fullPath,
  () => {
    syncTabFromRoute()
  },
  { immediate: true },
)

async function handleLoginSuccess() {
  const me = await auth.fetchCurrentUser()
  await Promise.all([refreshQuotations(), hydrateUserCatalog()])
  triggerToast(t('quotation.app.welcomeBack', { name: me.name }), 'success')
}

async function handleLogout() {
  if (auth.embeddedAuth) return
  catalogReady.value = false
  await auth.logout()
  quotations.value = []
  currentTab.value = 'dashboard'
  selectedQuotationId.value = null
  editingQuoteId.value = null
}

const userQuotations = computed(() =>
  auth.currentUser ? filterQuotationsByUser(quotations.value, auth.currentUser) : [],
)

const activeQuote = computed(() =>
  quotations.value.find((q) => q.id === selectedQuotationId.value),
)

const editingQuote = computed(() =>
  editingQuoteId.value
    ? quotations.value.find((q) => q.id === editingQuoteId.value) || null
    : null,
)

const userInitials = computed(() => {
  if (!auth.currentUser) return ''
  return auth.currentUser.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
})

function navClass(tab: string) {
  return currentTab.value === tab
    ? 'bg-dm-primary-bg text-dm-primary font-medium border-l-[3px] border-l-dm-primary pl-[9px]'
    : 'text-dm-text-secondary hover:bg-[#f5f5f5] hover:text-dm-text border-l-[3px] border-l-transparent pl-[9px]'
}

function goTab(tab: string) {
  selectedQuotationId.value = null
  if (tab === 'create') editingQuoteId.value = null

  if (auth.embeddedAuth) {
    currentTab.value = tab
    const target = TAB_ROUTES[tab]
    if (target) {
      router.push(target)
    }
    return
  }

  currentTab.value = tab
}

async function handleDeleteQuote(id: string) {
  const previous = quotations.value
  quotations.value = quotations.value.filter((q) => q.id !== id)
  if (selectedQuotationId.value === id) {
    selectedQuotationId.value = null
    if (currentTab.value === 'details') {
      currentTab.value = 'list'
    }
  }
  try {
    await deleteQuotationApi(id)
    triggerToast(t('quotation.app.quoteDeleted'), 'info')
  } catch (err) {
    quotations.value = previous
    triggerToast(
      err instanceof Error ? err.message : t('quotation.app.saveFailed'),
      'error',
    )
  }
}

function handleViewQuoteDetails(id: string) {
  if (auth.embeddedAuth) {
    currentTab.value = 'details'
    selectedQuotationId.value = id
    router.push(`/quotation/details/${id}`)
    return
  }
  selectedQuotationId.value = id
  currentTab.value = 'details'
}

async function handleSaveQuotation(newQuote: Quotation) {
  if (!auth.currentUser) {
    triggerToast(t('quotation.app.loginRequired'), 'error')
    return
  }

  const ownedQuote = ensureQuoteOwnership(newQuote, auth.currentUser)

  try {
    const wasCreate = !editingQuoteId.value
    const exists = quotations.value.some((q) => q.id === ownedQuote.id)
    const willGenerate = ownedQuote.status === 'Generated'
    let saved = exists
      ? await updateQuotationApi(ownedQuote, {
          notes: t('quotation.app.versionNotesEditQuote'),
          skipVersion: willGenerate,
        })
      : await createQuotationApi(ownedQuote)

    const catalogSync = upsertDescriptionsToCatalog(
      ownedQuote.items,
      products.value,
      services.value,
      productLineOptions.value.find(
        (option) => option.value === ownedQuote.productLine,
      )?.label || ownedQuote.productLine || 'HyperBDR',
    )
    if (catalogSync.added > 0) {
      products.value = catalogSync.products
      services.value = catalogSync.services
      triggerToast(
        t('quotation.app.catalogDescriptionsSynced', {
          count: catalogSync.added,
        }),
        'info',
      )
    }

    if (wasCreate) {
      clearCreateQuoteDraft(auth.currentUser.email)
    }

    if (willGenerate) {
      saved = await generateQuotationApi(saved.id, auth.currentUser.email)
      downloadQuotationExcel(
        {
          ...ownedQuote,
          ...saved,
          issuerSignature: ownedQuote.issuerSignature,
          remarksDisclaimer:
            ownedQuote.remarksDisclaimer ?? saved.remarksDisclaimer,
        },
        auth.currentUser
          ? {
              name: auth.currentUser.name,
              title: auth.currentUser.title,
              email: auth.currentUser.email,
              role: auth.currentUser.role,
            }
          : undefined,
      )
      triggerToast(t('quotation.app.quoteGenerated', { quoteNo: saved.quoteNo }), 'success')
      selectedQuotationId.value = saved.id
      if (auth.embeddedAuth) {
        await router.push(`/quotation/details/${saved.id}`)
      } else {
        currentTab.value = 'details'
      }
    } else {
      triggerToast(t('quotation.app.draftSaved', { quoteNo: saved.quoteNo }), 'info')
      if (auth.embeddedAuth) {
        await router.push('/quotation/list')
      } else {
        currentTab.value = 'list'
      }
    }

    editingQuoteId.value = null
    await refreshQuotations()
  } catch (error: unknown) {
    console.error(error)
    const message = error instanceof Error ? error.message : t('quotation.app.saveFailed')
    triggerToast(message, 'error')
  }
}

async function handleFeishuUploadDone(_id: string) {
  await refreshQuotations()
}

async function handleReconcileFeishuLinks() {
  await refreshQuotations()
}

async function handleUpdateQuote(
  id: string,
  updatedFields: Partial<Quotation>,
  notes?: string,
) {
  const previous = quotations.value.find((q) => q.id === id)
  if (!previous) return

  const nextQuote = { ...previous, ...updatedFields }
  const statusChanged = Boolean(
    updatedFields.status && updatedFields.status !== previous.status,
  )
  const isExcelGenerated =
    updatedFields.status === 'Generated' && previous.status === 'Draft'

  let computedNotes = notes || ''
  if (!computedNotes) {
    if (isExcelGenerated) {
      computedNotes = t('quotation.app.versionNotesExcelGenerated')
    } else if (statusChanged && updatedFields.status) {
      computedNotes = t('quotation.app.versionNotesStatusUpdated', {
        status: quoteStatusLabel(updatedFields.status),
      })
    } else {
      computedNotes = t('quotation.app.versionNotesPropertiesUpdated')
    }
  }

  quotations.value = quotations.value.map((q) =>
    q.id === id ? nextQuote : q,
  )

  if (isFeishuLinkOnlyUpdate(updatedFields)) {
    return
  }

  if (statusChanged || notes || isExcelGenerated) {
    try {
      const saved = await updateQuotationApi(nextQuote, {
        notes: computedNotes,
      })
      quotations.value = quotations.value.map((q) =>
        q.id === id
          ? {
              ...saved,
              region: q.region,
              industry: q.industry,
            }
          : q,
      )
    } catch (err) {
      quotations.value = quotations.value.map((q) =>
        q.id === id ? previous : q,
      )
      triggerToast(
        err instanceof Error ? err.message : t('quotation.app.saveFailed'),
        'error',
      )
      return
    }
  }

  if (updatedFields.status) {
    switch (updatedFields.status) {
      case 'Sent':
        triggerToast(t('quotation.app.statusSent'), 'success')
        break
      case 'Accepted':
        triggerToast(t('quotation.app.statusAccepted'), 'success')
        break
      case 'Rejected':
        triggerToast(t('quotation.app.statusRejected'), 'info')
        break
      case 'Expired':
        triggerToast(t('quotation.app.statusExpired'), 'info')
        break
      case 'Cancelled':
        triggerToast(
          notes
            ? t('quotation.app.statusCancelledWithReason', { reason: notes })
            : t('quotation.app.statusCancelledDefault'),
          'info',
        )
        break
      default:
        break
    }
  }
}

function handleAddProduct(prod: Product) {
  products.value = [prod, ...products.value]
  triggerToast(t('quotation.app.productAdded', { name: prod.name }), 'success')
}

function handleDeleteProduct(id: string) {
  products.value = products.value.filter((p) => p.id !== id)
  triggerToast(t('quotation.app.productRemoved'), 'info')
}

function handleAddService(serv: Service) {
  services.value = [serv, ...services.value]
  triggerToast(t('quotation.app.serviceAdded', { name: serv.name }), 'success')
}

function handleDeleteService(id: string) {
  services.value = services.value.filter((s) => s.id !== id)
  triggerToast(t('quotation.app.serviceRemoved'), 'info')
}

function handleAddDiscount(disc: DiscountOption) {
  discounts.value = [...discounts.value, disc]
  triggerToast(t('quotation.app.discountAdded', { name: disc.name }), 'success')
}

function handleDeleteDiscount(id: string) {
  discounts.value = discounts.value.filter((d) => d.id !== id)
  triggerToast(t('quotation.app.discountRemoved'), 'info')
}

function handleAddProductLine(option: ProductLineOption) {
  productLineOptions.value = [...productLineOptions.value, option]
  triggerToast(
    t('quotation.app.productLineAdded', { label: option.label, prefix: option.value }),
    'success',
  )
}

function handleDeleteProductLine(productLine: QuoteProductLine) {
  const option = productLineOptions.value.find((item) => item.value === productLine)
  productLineOptions.value = productLineOptions.value.filter((item) => item.value !== productLine)
  triggerToast(
    t('quotation.app.productLineRemoved', { label: option?.label || productLine }),
    'info',
  )
}

function handleEditQuote(id: string) {
  editingQuoteId.value = id
  if (auth.embeddedAuth) {
    router.push({ path: '/quotation/create', query: { edit: id } })
    return
  }
  currentTab.value = 'create'
}

function handleBackToList() {
  if (auth.embeddedAuth) {
    router.push('/quotation/list')
    return
  }
  currentTab.value = 'list'
}

function handleNavigateToTab(tab: string) {
  goTab(tab)
}

function reloadPage() {
  window.location.reload()
}
</script>

<template>
  <div
    v-if="!auth.authReady"
    class="flex min-h-screen items-center justify-center bg-dm-page text-sm text-dm-text-tertiary"
  >
    {{ auth.embeddedAuth ? t('quotation.app.authLoadingEmbedded') : t('quotation.app.authLoading') }}
  </div>

  <div
    v-else-if="!auth.isAuthenticated || !auth.currentUser"
  >
    <div
      v-if="auth.embeddedAuth"
      class="flex min-h-screen flex-col items-center justify-center gap-3 bg-dm-page px-4 text-center"
    >
      <p class="text-sm font-medium text-dm-text">{{ t('quotation.app.authFailedTitle') }}</p>
      <p class="max-w-md text-xs text-dm-text-tertiary">
        {{ auth.authError || t('quotation.app.authFailedHint') }}
      </p>
      <button
        type="button"
        class="mt-2 dm-btn-default px-3 py-1.5 text-xs"
        @click="reloadPage"
      >
        {{ t('quotation.app.retry') }}
      </button>
    </div>
    <LoginPage v-else @login-success="handleLoginSuccess" />
  </div>

  <div
    v-else
    id="app-container"
    class="flex h-screen overflow-hidden bg-dm-page font-sans text-dm-text antialiased"
  >
    <div
      v-if="toastMessage"
      id="toast-notification"
      :class="`fixed right-4 top-14 z-50 flex items-center gap-2 rounded-dm border px-4 py-3 text-sm shadow-dm transition-all ${
        toastType === 'success'
          ? 'border-[#b7eb8f] bg-dm-success-bg text-[#389e0d]'
          : toastType === 'info'
            ? 'border-[#91caff] bg-dm-primary-bg text-dm-primary'
            : 'border-[#ffccc7] bg-dm-error-bg text-dm-error'
      }`"
    >
      <CheckCircle
        :class="`h-4 w-4 shrink-0 ${toastType === 'success' ? 'text-dm-success' : toastType === 'info' ? 'text-dm-primary' : 'text-dm-error'}`"
      />
      <span class="font-medium">{{ toastMessage }}</span>
    </div>

    <aside
      v-if="!auth.embeddedAuth"
      id="app-sidebar"
      class="flex w-[220px] shrink-0 flex-col border-r border-dm-border bg-white"
    >
      <div class="flex items-center gap-2.5 border-b border-dm-border-light px-5 py-4">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-dm bg-dm-primary text-sm font-bold text-white"
        >
          Q
        </div>
        <div>
          <h1 class="text-sm font-semibold tracking-tight text-dm-text">Quote Desk</h1>
          <span class="text-[10px] font-medium uppercase tracking-wider text-dm-text-tertiary"
            >Quotation</span
          >
        </div>
      </div>

      <nav class="flex-1 space-y-0.5 p-3 text-sm">
        <button
          id="nav-tab-dashboard"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('dashboard')}`"
          @click="goTab('dashboard')"
        >
          <LayoutDashboard class="h-4 w-4 shrink-0" />
          <span>Dashboard 看板</span>
        </button>

        <button
          id="nav-tab-list"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('list')}`"
          @click="goTab('list')"
        >
          <Search class="h-4 w-4 shrink-0" />
          <span>报价查询中心</span>
        </button>

        <button
          id="nav-tab-create"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('create')}`"
          @click="goTab('create')"
        >
          <PlusCircle class="h-4 w-4 shrink-0" />
          <span>在线创建报价单</span>
        </button>

        <button
          id="nav-tab-imports"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('imports')}`"
          @click="goTab('imports')"
        >
          <FolderInput class="h-4 w-4 shrink-0" />
          <span>导入资料 / 待分析</span>
        </button>

        <button
          id="nav-tab-catalog"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('catalog')}`"
          @click="goTab('catalog')"
        >
          <Settings class="h-4 w-4 shrink-0" />
          <span>业务目录要素配置</span>
        </button>
      </nav>

      <div class="flex items-center gap-3 border-t border-dm-border-light px-4 py-3">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#ff4d4f] text-xs font-semibold text-white"
        >
          {{ userInitials }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-dm-text">{{ auth.currentUser.name }}</p>
          <p class="truncate text-xs text-dm-text-tertiary">{{ auth.currentUser.title }}</p>
        </div>
      </div>
    </aside>

    <div id="main-content-pane" class="flex flex-1 flex-col overflow-hidden">
      <header
        id="app-header"
        class="flex h-12 shrink-0 items-center justify-between border-b border-dm-border-light bg-white px-6"
      >
        <div class="flex items-center gap-2">
          <span class="text-sm text-dm-text-tertiary">销售协同工具集</span>
          <span class="text-sm text-dm-text-tertiary">/</span>
          <span class="text-sm font-medium text-dm-text">
            <template v-if="currentTab === 'dashboard'">控制面板 Dashboard</template>
            <template v-else-if="currentTab === 'list'">报价查询及管理中心</template>
            <template v-else-if="currentTab === 'create'">拟定报价方案方案</template>
            <template v-else-if="currentTab === 'details'">报价方案单据详情预览</template>
            <template v-else-if="currentTab === 'imports'">导入资料 / 待分析</template>
            <template v-else-if="currentTab === 'catalog'">商务目录要素及政策配置</template>
          </span>
        </div>

        <div class="flex items-center gap-4">
          <div
            class="hidden items-center gap-1.5 rounded-dm border border-[#b7eb8f] bg-dm-success-bg px-2.5 py-1 md:flex"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-dm-success" />
            <span class="text-xs text-[#389e0d]">报价模板与本地生成引擎就绪</span>
          </div>

          <div class="hidden h-4 w-px bg-dm-border md:block" />

          <div class="flex items-center gap-3">
            <div class="hidden text-right sm:block">
              <div class="flex items-center justify-end gap-1.5">
                <span class="text-sm font-medium text-dm-text">{{ auth.currentUser.name }}</span>
                <span
                  class="rounded border border-[#91caff] bg-dm-primary-bg px-1.5 py-0.5 text-[10px] font-medium text-dm-primary"
                  >{{ auth.currentUser.role }}</span
                >
              </div>
              <div class="mt-0.5 text-xs text-dm-text-tertiary">
                {{ auth.currentUser.title }} •
                <span class="font-mono">{{ auth.currentUser.email }}</span>
              </div>
            </div>

            <button
              v-if="!auth.embeddedAuth"
              type="button"
              class="dm-btn-default inline-flex cursor-pointer items-center gap-1.5 px-2.5 py-1.5 text-sm"
              @click="handleLogout"
            >
              <LogOut class="h-3.5 w-3.5" />
              退出登录
            </button>
          </div>
        </div>
      </header>

      <main
        id="app-scroll-stage"
        class="flex-1 overflow-y-auto scroll-smooth bg-dm-page p-6"
      >
        <Dashboard
          v-if="currentTab === 'dashboard'"
          :quotations="quotations"
          @view-quote="handleViewQuoteDetails"
          @navigate-to-tab="handleNavigateToTab"
        />

        <QuotationList
          v-if="currentTab === 'list'"
          :quotations="quotations"
          :current-user="auth.currentUser"
          @view-quote="handleViewQuoteDetails"
          @delete-quote="handleDeleteQuote"
          @update-quote-status="handleUpdateQuote"
          @feishu-upload-done="handleFeishuUploadDone"
          @reconcile-feishu-links="handleReconcileFeishuLinks"
          @edit-quote="handleEditQuote"
          @toast="triggerToast"
        />

        <QuotationCreate
          v-if="currentTab === 'create'"
          :products="products"
          :services="services"
          :discounts="discounts"
          :quotations="quotations"
          :history-quotations="userQuotations"
          :editing-quote="editingQuote"
          :current-user="auth.currentUser"
          :product-line-options="productLineOptions"
          @save-quote="handleSaveQuotation"
          @navigate-to-tab="handleNavigateToTab"
          @add-product-line="handleAddProductLine"
          @delete-product-line="handleDeleteProductLine"
        />

        <QuotationDetails
          v-if="currentTab === 'details' && activeQuote"
          :quote="activeQuote"
          :current-user="auth.currentUser"
          @back="handleBackToList"
          @update-quote-status="handleUpdateQuote"
          @edit-quote="handleEditQuote"
        />

        <ImportedDocumentsPage
          v-if="currentTab === 'imports'"
          @toast="triggerToast"
        />

        <ProductServiceManager
          v-if="currentTab === 'catalog'"
          :products="products"
          :services="services"
          :discounts="discounts"
          :product-line-options="productLineOptions"
          @add-product="handleAddProduct"
          @delete-product="handleDeleteProduct"
          @add-service="handleAddService"
          @delete-service="handleDeleteService"
          @add-discount="handleAddDiscount"
          @delete-discount="handleDeleteDiscount"
        />
      </main>
    </div>
  </div>
</template>
