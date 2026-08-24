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
  ScrollText,
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
import QuotationDetailsDrawer from './components/QuotationDetailsDrawer.vue'
import AuditLogPage from './components/AuditLogPage.vue'
import ViewPermissionPage from './components/ViewPermissionPage.vue'
import ProductServiceManager from './components/ProductServiceManager.vue'
import CustomerCenter from './components/CustomerCenter.vue'
import { isFeishuLinkOnlyUpdate, reconcileFeishuQuotationLinks } from './utils/feishuLinkState'
import {
  loadProductLineOptions,
  saveCustomProductLineOptions,
} from './utils/quotationNumbering'
import { ensureQuoteOwnership } from './utils/quoteOwnership'
import { clearCreateQuoteDraft } from './utils/createDraftStorage'
import {
  upsertDescriptionsToCatalog,
  type LineItemDescriptionHistory,
} from './utils/descriptionCatalog'
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
  getQuotation as getQuotationApi,
  getQuotationFormContext,
  listQuotations,
  type QuotationListParams,
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
  catalog: '/quotation/catalog',
  audit: '/quotation/audit',
  permissions: '/quotation/permissions',
  customers: '/quotation/customers',
}

type ListDateFilters = {
  createdFrom?: string
  createdTo?: string
}

function listDateFiltersFromRoute(
  query: typeof route.query,
): ListDateFilters {
  const createdFrom =
    typeof query.created_from === 'string' ? query.created_from : undefined
  const createdTo =
    typeof query.created_to === 'string' ? query.created_to : undefined
  return { createdFrom, createdTo }
}

function listRouteLocation(listFilters?: ListDateFilters, page = 1) {
  const createdFrom = listFilters?.createdFrom
  const createdTo = listFilters?.createdTo
  if (!createdFrom && !createdTo && page <= 1) {
    return { path: TAB_ROUTES.list }
  }
  return {
    path: TAB_ROUTES.list,
    query: {
      ...(createdFrom ? { created_from: createdFrom } : {}),
      ...(createdTo ? { created_to: createdTo } : {}),
      ...(page > 1 ? { page: String(page) } : {}),
    },
  }
}

function applyListDateFilters(listFilters?: ListDateFilters) {
  const routePage = Number(route.query.page)
  const page = Number.isInteger(routePage) && routePage > 0 ? routePage : 1
  quotationListQuery.value = {
    page,
    pageSize: quotationListQuery.value.pageSize || 10,
    createdFrom: listFilters?.createdFrom,
    createdTo: listFilters?.createdTo,
  }
}

async function handleQuotationListQueryChange(query: QuotationListParams) {
  if (currentTab.value === 'list') {
    await router.replace(
      listRouteLocation(
        {
          createdFrom: query.createdFrom,
          createdTo: query.createdTo,
        },
        query.page || 1,
      ),
    )
  }
  await refreshQuotations(query)
}

function tabFromRoutePath(path: string): string {
  if (path.startsWith('/quotation/details/')) return 'details'
  if (path.startsWith('/quotation/list')) return 'list'
  if (path.startsWith('/quotation/create')) return 'create'
  if (path.startsWith('/quotation/imports')) return 'list'
  if (path.startsWith('/quotation/catalog')) return 'catalog'
  if (path.startsWith('/quotation/audit')) return 'audit'
  if (path.startsWith('/quotation/permissions')) return 'permissions'
  if (path.startsWith('/quotation/customers')) return 'customers'
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

  if (nextTab === 'list') {
    applyListDateFilters(listDateFiltersFromRoute(route.query))
  }

  if (nextTab === 'create') {
    const editId = route.query.edit
    editingQuoteId.value = typeof editId === 'string' ? editId : null
    return
  }

  editingQuoteId.value = null
}

const quotations = ref<Quotation[]>([])
const quotationListLoading = ref(false)
const quotationListQuery = ref<QuotationListParams>({
  page: 1,
  pageSize: 10,
})
const quotationListTotal = ref(0)
const quotationListTotalPages = ref(0)
const quotationListProductLines = ref<string[]>([])
const quotationListCurrencies = ref<string[]>([])
const activeQuote = ref<Quotation | null>(null)
const activeQuoteLoading = ref(false)
const drawerQuoteId = ref<string | null>(null)
const editingQuote = ref<Quotation | null>(null)
const quotationFormContext = ref<Quotation[]>([])
const quotationFormContextQuoteNumbers = ref<string[]>([])
const lineItemDescriptionHistory = ref<LineItemDescriptionHistory[]>([])
const quotationFormContextPage = ref(0)
const quotationFormContextHasMore = ref(false)
const quotationFormContextLoading = ref(false)
let quotationListRequestId = 0

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
const customerPrefill = ref<{
  company: string
  contact: string
  email: string
} | null>(null)

const toastMessage = ref<string | null>(null)
const toastType = ref<'success' | 'info' | 'error'>('success')

function triggerToast(msg: string, type: 'success' | 'info' | 'error' = 'success') {
  toastMessage.value = msg
  toastType.value = type
  setTimeout(() => {
    toastMessage.value = null
  }, 4000)
}

async function refreshQuotations(
  query: QuotationListParams = quotationListQuery.value,
) {
  const requestId = ++quotationListRequestId
  quotationListQuery.value = { ...query }
  quotationListLoading.value = true
  try {
    const result = await listQuotations(query)
    if (requestId !== quotationListRequestId) return
    quotations.value = result.items
    quotationListProductLines.value = result.productLines
    quotationListCurrencies.value = result.currencies
    quotationListTotal.value = result.total
    quotationListTotalPages.value = result.totalPages
    quotationListQuery.value = {
      ...query,
      page: result.page,
      pageSize: result.pageSize,
    }
  } catch (error: unknown) {
    if (requestId !== quotationListRequestId) return
    console.error(error)
    const message = error instanceof Error ? error.message : t('quotation.app.loadFailed')
    triggerToast(message, 'error')
    quotations.value = []
    quotationListProductLines.value = []
    quotationListCurrencies.value = []
    quotationListTotal.value = 0
    quotationListTotalPages.value = 0
  } finally {
    if (requestId === quotationListRequestId) {
      quotationListLoading.value = false
    }
  }
}

async function loadActiveQuote(id: string) {
  activeQuoteLoading.value = true
  try {
    activeQuote.value = await getQuotationApi(id)
  } catch (error) {
    activeQuote.value = null
    triggerToast(
      error instanceof Error ? error.message : t('quotation.app.loadFailed'),
      'error',
    )
  } finally {
    activeQuoteLoading.value = false
  }
}

async function loadEditingQuote(id: string | null) {
  if (!id) {
    editingQuote.value = null
    return
  }
  try {
    editingQuote.value = await getQuotationApi(id)
  } catch (error) {
    editingQuote.value = null
    triggerToast(
      error instanceof Error ? error.message : t('quotation.app.loadFailed'),
      'error',
    )
  }
}

async function loadQuotationFormContext(reset = true) {
  if (quotationFormContextLoading.value) return
  const nextPage = reset ? 1 : quotationFormContextPage.value + 1
  if (!reset && !quotationFormContextHasMore.value) return
  quotationFormContextLoading.value = true
  try {
    const context = await getQuotationFormContext(nextPage)
    quotationFormContext.value = reset
      ? context.quotations
      : [...quotationFormContext.value, ...context.quotations]
    lineItemDescriptionHistory.value = reset
      ? context.lineItemHistory
      : [
          ...lineItemDescriptionHistory.value,
          ...context.lineItemHistory,
        ]
    quotationFormContextQuoteNumbers.value = context.quoteNumbers
    quotationFormContextPage.value = context.page
    quotationFormContextHasMore.value = context.hasMore
  } catch (error) {
    if (reset) {
      quotationFormContext.value = []
      quotationFormContextQuoteNumbers.value = []
      lineItemDescriptionHistory.value = []
    }
    triggerToast(
      error instanceof Error ? error.message : t('quotation.app.loadFailed'),
      'error',
    )
  } finally {
    quotationFormContextLoading.value = false
  }
}

function loadMoreQuotationFormContext() {
  void loadQuotationFormContext(false)
}

async function loadCurrentQuotationTab() {
  if (currentTab.value === 'list') {
    await refreshQuotations()
    return
  }
  if (currentTab.value === 'details' && selectedQuotationId.value) {
    if (activeQuote.value?.id !== selectedQuotationId.value) {
      await loadActiveQuote(selectedQuotationId.value)
    }
    return
  }
  if (currentTab.value === 'create') {
    const tasks: Promise<unknown>[] = [loadQuotationFormContext()]
    if (editingQuote.value?.id !== editingQuoteId.value) {
      tasks.push(loadEditingQuote(editingQuoteId.value))
    }
    await Promise.all(tasks)
  }
  if (currentTab.value === 'customers') {
    await loadQuotationFormContext()
  }
}

onMounted(async () => {
  await auth.bootstrap()
  if (auth.isAuthenticated) {
    const tasks: Promise<unknown>[] = [
      hydrateUserCatalog(),
      loadCurrentQuotationTab(),
    ]
    await Promise.all(tasks)
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
  async () => {
    syncTabFromRoute()
    if (auth.isAuthenticated) {
      await loadCurrentQuotationTab()
    }
  },
  { immediate: true },
)

async function handleLoginSuccess() {
  const me = await auth.fetchCurrentUser()
  const tasks: Promise<unknown>[] = [
    hydrateUserCatalog(),
    loadCurrentQuotationTab(),
  ]
  await Promise.all(tasks)
  triggerToast(t('quotation.app.welcomeBack', { name: me.name }), 'success')
}

async function handleLogout() {
  if (auth.embeddedAuth) return
  catalogReady.value = false
  await auth.logout()
  quotations.value = []
  quotationListTotal.value = 0
  quotationListTotalPages.value = 0
  activeQuote.value = null
  drawerQuoteId.value = null
  editingQuote.value = null
  quotationFormContext.value = []
  quotationFormContextQuoteNumbers.value = []
  lineItemDescriptionHistory.value = []
  quotationFormContextPage.value = 0
  quotationFormContextHasMore.value = false
  currentTab.value = 'dashboard'
  selectedQuotationId.value = null
  editingQuoteId.value = null
}

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

function goTab(tab: string, listFilters?: ListDateFilters) {
  selectedQuotationId.value = null
  drawerQuoteId.value = null
  if (tab === 'create') editingQuoteId.value = null
  if (tab === 'create') void loadQuotationFormContext()
  if (tab === 'list') {
    applyListDateFilters(listFilters)
  }

  if (auth.embeddedAuth) {
    currentTab.value = tab
    if (tab === 'list') {
      router.push(listRouteLocation(listFilters))
      return
    }
    const target = TAB_ROUTES[tab]
    if (target) {
      router.push(target)
    }
    return
  }

  currentTab.value = tab
  if (tab === 'list') {
    void refreshQuotations(quotationListQuery.value)
  }
}

function handleCustomerQuote(payload: {
  company: string
  name: string
  email: string
} | undefined) {
  if (!payload) {
    goTab('create')
    return
  }
  customerPrefill.value = {
    company: payload.company,
    contact: payload.name,
    email: payload.email,
  }
  goTab('create')
}

async function handleDeleteQuote(id: string) {
  if (selectedQuotationId.value === id) {
    selectedQuotationId.value = null
    if (currentTab.value === 'details') {
      currentTab.value = 'list'
    }
  }
  try {
    await deleteQuotationApi(id)
    const currentPage = quotationListQuery.value.page || 1
    const nextPage =
      quotations.value.length === 1 && currentPage > 1
        ? currentPage - 1
        : currentPage
    await refreshQuotations({
      ...quotationListQuery.value,
      page: nextPage,
    })
    triggerToast(t('quotation.app.quoteDeleted'), 'info')
  } catch (err) {
    triggerToast(
      err instanceof Error ? err.message : t('quotation.app.saveFailed'),
      'error',
    )
  }
}

async function handleViewQuoteDetails(id: string) {
  activeQuote.value = null
  selectedQuotationId.value = id
  currentTab.value = 'details'
  if (auth.embeddedAuth) {
    router.push(`/quotation/details/${id}`)
    return
  }
  void loadActiveQuote(id)
}

function handleOpenDetailDrawer(id: string) {
  drawerQuoteId.value = id
}

function handleCloseDetailDrawer() {
  drawerQuoteId.value = null
}

async function handleSaveQuotation(newQuote: Quotation) {
  if (!auth.currentUser) {
    triggerToast(t('quotation.app.loginRequired'), 'error')
    return
  }

  const ownedQuote = ensureQuoteOwnership(newQuote, auth.currentUser)

  try {
    const wasCreate = !editingQuoteId.value
    const exists = Boolean(editingQuoteId.value)
    const willGenerate = ownedQuote.status === 'Generated'
    const usesQuoteRevisions = [
      'Uploaded',
      'Sent',
      'Accepted',
      'Rejected',
      'Expired',
      'Cancelled',
    ].includes(ownedQuote.status)
    let saved = exists
      ? await updateQuotationApi(ownedQuote, {
          notes: t('quotation.app.versionNotesEditQuote'),
          skipVersion: !usesQuoteRevisions,
        })
      : await createQuotationApi(ownedQuote)

    const catalogSync = upsertDescriptionsToCatalog(
      ownedQuote.items,
      products.value,
      services.value,
      productLineOptions.value.find(
        (option) => option.value === ownedQuote.productLine,
      )?.label || ownedQuote.productLine || 'HyperBDR',
      ownedQuote.currency,
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
    await refreshQuotations(quotationListQuery.value)
    if (wasCreate) await loadQuotationFormContext()
  } catch (error: unknown) {
    console.error(error)
    const message = error instanceof Error ? error.message : t('quotation.app.saveFailed')
    triggerToast(message, 'error')
  }
}

async function handleFeishuUploadDone(_id: string) {
  await refreshQuotations()
}

async function handleRefreshCustomers() {
  await loadQuotationFormContext()
}

async function handleReconcileFeishuLinks() {
  const staleLinks = await reconcileFeishuQuotationLinks(quotations.value)
  if (staleLinks) {
    await refreshQuotations(quotationListQuery.value)
  }
}

async function handleUpdateQuote(
  id: string,
  updatedFields: Partial<Quotation>,
  notes?: string,
) {
  const previousListQuote = quotations.value.find((q) => q.id === id)
  if (!previousListQuote) return

  const statusChanged = Boolean(
    updatedFields.status &&
      updatedFields.status !== previousListQuote.status,
  )
  const isExcelGenerated =
    updatedFields.status === 'Generated' &&
    previousListQuote.status === 'Draft'

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
    q.id === id ? { ...q, ...updatedFields } : q,
  )

  if (isFeishuLinkOnlyUpdate(updatedFields)) {
    return
  }

  if (statusChanged || notes || isExcelGenerated) {
    try {
      const detail = await getQuotationApi(id)
      const saved = await updateQuotationApi({
        ...detail,
        ...updatedFields,
      }, {
        notes: computedNotes,
      })
      quotations.value = quotations.value.map((q) =>
        q.id === id
          ? {
              ...q,
              status: saved.status,
              region: q.region,
              industry: q.industry,
            }
          : q,
      )
    } catch (err) {
      quotations.value = quotations.value.map((q) =>
        q.id === id ? previousListQuote : q,
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

async function handleEditQuote(id: string) {
  editingQuoteId.value = id
  await loadEditingQuote(id)
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

function handleNavigateToTab(
  payload:
    | string
    | { tab: string; createdFrom?: string; createdTo?: string },
) {
  if (typeof payload === 'string') {
    goTab(payload)
    return
  }
  goTab(payload.tab, {
    createdFrom: payload.createdFrom,
    createdTo: payload.createdTo,
  })
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
      <p class="max-w-md text-sm text-dm-text-tertiary">
        {{ auth.authError || t('quotation.app.authFailedHint') }}
      </p>
      <button
        type="button"
        class="mt-2 dm-btn-default px-3 py-1.5 text-sm"
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
          <h1 class="text-sm font-semibold tracking-tight text-dm-text">
            {{ t('quotation.app.title') }}
          </h1>
          <span class="text-xs font-medium uppercase tracking-wider text-dm-text-tertiary"
            >{{ t('quotation.app.subtitle') }}</span
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
          id="nav-tab-catalog"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('catalog')}`"
          @click="goTab('catalog')"
        >
          <Settings class="h-4 w-4 shrink-0" />
          <span>业务目录要素配置</span>
        </button>

        <button
          id="nav-tab-audit"
          type="button"
          :class="`flex w-full cursor-pointer items-center gap-3 rounded-dm py-2.5 pr-3 text-left transition-colors ${navClass('audit')}`"
          @click="goTab('audit')"
        >
          <ScrollText class="h-4 w-4 shrink-0" />
          <span>{{ t('quotation.pages.audit.menuLabel') }}</span>
        </button>

      </nav>

      <div class="flex items-center gap-3 border-t border-dm-border-light px-4 py-3">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#ff4d4f] text-sm font-semibold text-white"
        >
          {{ userInitials }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-dm-text">{{ auth.currentUser.name }}</p>
          <p class="truncate text-sm text-dm-text-tertiary">{{ auth.currentUser.title }}</p>
        </div>
      </div>
    </aside>

    <div
      id="main-content-pane"
      class="flex min-w-0 w-0 flex-1 flex-col overflow-hidden"
    >
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
            <template v-else-if="currentTab === 'catalog'">商务目录要素及政策配置</template>
            <template v-else-if="currentTab === 'audit'">{{ t('quotation.pages.audit.title') }}</template>
            <template v-else-if="currentTab === 'permissions'">{{ t('quotation.pages.permissions.title') }}</template>
            <template v-else-if="currentTab === 'customers'">客户中心</template>
          </span>
        </div>

        <div class="flex items-center gap-4">
          <div
            class="hidden items-center gap-1.5 rounded-dm border border-[#b7eb8f] bg-dm-success-bg px-2.5 py-1 md:flex"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-dm-success" />
            <span class="text-sm text-[#389e0d]">报价模板与本地生成引擎就绪</span>
          </div>

          <div class="hidden h-4 w-px bg-dm-border md:block" />

          <div class="flex items-center gap-3">
            <div class="hidden text-right sm:block">
              <div class="flex items-center justify-end gap-1.5">
                <span class="text-sm font-medium text-dm-text">{{ auth.currentUser.name }}</span>
                <span
                  class="rounded border border-[#91caff] bg-dm-primary-bg px-1.5 py-0.5 text-xs font-medium text-dm-primary"
                  >{{ auth.currentUser.role }}</span
                >
              </div>
              <div class="mt-0.5 text-sm text-dm-text-tertiary">
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
        class="min-w-0 w-full flex-1 overflow-x-hidden overflow-y-auto scroll-smooth bg-dm-page p-6"
      >
        <Dashboard
          v-if="currentTab === 'dashboard'"
          @view-quote="handleViewQuoteDetails"
          @navigate-to-tab="handleNavigateToTab"
        />

        <div
          v-if="currentTab === 'list'"
          class="flex flex-col"
        >
          <QuotationList
            :quotations="quotations"
            :product-lines="quotationListProductLines"
            :currencies="quotationListCurrencies"
            :loading="quotationListLoading"
            :page="quotationListQuery.page || 1"
            :page-size="quotationListQuery.pageSize || 10"
            :total="quotationListTotal"
            :total-pages="quotationListTotalPages"
            :initial-created-from="quotationListQuery.createdFrom"
            :initial-created-to="quotationListQuery.createdTo"
            :current-user="auth.currentUser"
            @view-quote="handleViewQuoteDetails"
            @open-detail-drawer="handleOpenDetailDrawer"
            @delete-quote="handleDeleteQuote"
            @update-quote-status="handleUpdateQuote"
            @feishu-upload-done="handleFeishuUploadDone"
            @reconcile-feishu-links="handleReconcileFeishuLinks"
            @edit-quote="handleEditQuote"
            @toast="triggerToast"
            @query-change="handleQuotationListQueryChange"
          />

        </div>

        <QuotationCreate
          v-if="currentTab === 'create'"
          :products="products"
          :services="services"
          :discounts="discounts"
          :quotations="quotationFormContext"
          :existing-quote-numbers="quotationFormContextQuoteNumbers"
          :history-quotations="quotationFormContext"
          :line-item-history="lineItemDescriptionHistory"
          :history-has-more="quotationFormContextHasMore"
          :history-loading="quotationFormContextLoading"
          :editing-quote="editingQuote"
          :customer-prefill="customerPrefill"
          :current-user="auth.currentUser"
          :product-line-options="productLineOptions"
          @save-quote="handleSaveQuotation"
          @navigate-to-tab="handleNavigateToTab"
          @add-product-line="handleAddProductLine"
          @delete-product-line="handleDeleteProductLine"
          @load-history-more="loadMoreQuotationFormContext"
        />

        <QuotationDetails
          v-if="currentTab === 'details' && activeQuote"
          :quote="activeQuote"
          :current-user="auth.currentUser"
          @back="handleBackToList"
          @update-quote-status="handleUpdateQuote"
          @edit-quote="handleEditQuote"
        />

        <div
          v-else-if="currentTab === 'details' && activeQuoteLoading"
          class="flex min-h-[420px] items-center justify-center rounded-xl bg-white"
          aria-busy="true"
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

        <AuditLogPage v-if="currentTab === 'audit'" />

        <ViewPermissionPage v-if="currentTab === 'permissions'" />

        <CustomerCenter
          v-if="currentTab === 'customers'"
          :quotations="quotationFormContext"
          @navigate-to-create="handleCustomerQuote"
          @toast="triggerToast"
          @refresh="handleRefreshCustomers"
        />
      </main>

      <QuotationDetailsDrawer
        :quote-id="drawerQuoteId"
        :current-user="auth.currentUser"
        @close="handleCloseDetailDrawer"
        @edit-quote="handleEditQuote"
        @update-quote-status="handleUpdateQuote"
      />
    </div>
  </div>
</template>
