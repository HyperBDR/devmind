<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  DiscountOption,
  Product,
  ProductLineOption,
  Service,
} from '../types'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import { formatCatalogPrice } from '../utils/templateCatalogs'
import FormSelect from './FormSelect.vue'
import {
  ChevronDown,
  FolderOpen,
  Settings,
  Percent,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-vue-next'

function buildAutoCode(prefix: string): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase().slice(-7)}`
}

const props = withDefaults(
  defineProps<{
    products: Product[]
    services: Service[]
    discounts: DiscountOption[]
    productLineOptions?: ProductLineOption[]
  }>(),
  {
    productLineOptions: () => [],
  },
)

const emit = defineEmits<{
  addProduct: [prod: Product]
  deleteProduct: [id: string]
  addService: [serv: Service]
  deleteService: [id: string]
  addDiscount: [disc: DiscountOption]
  deleteDiscount: [id: string]
}>()

const { t } = useQuotationI18n()

const subTab = ref<'products' | 'services' | 'discounts'>('products')
const searchQuery = ref('')
const isFormOpen = ref(false)
const quoteDescriptionsExpanded = ref(true)
const discountSettingsExpanded = ref(true)
const systemSettingsExpanded = ref(true)

function setSubTab(next: 'products' | 'services' | 'discounts') {
  subTab.value = next
  pendingDelete.value = null
  searchQuery.value = ''
  isFormOpen.value = false
}

const normalizedSearch = computed(() => searchQuery.value.trim().toLowerCase())
const filteredProducts = computed(() => props.products.filter((item) =>
  !normalizedSearch.value || [item.name, item.description, item.category]
    .some((value) => String(value || '').toLowerCase().includes(normalizedSearch.value)),
))
const filteredServices = computed(() => props.services.filter((item) =>
  !normalizedSearch.value || [item.name, item.description]
    .some((value) => String(value || '').toLowerCase().includes(normalizedSearch.value)),
))
const filteredDiscounts = computed(() => props.discounts.filter((item) =>
  !normalizedSearch.value || item.name.toLowerCase().includes(normalizedSearch.value),
))

const pName = ref('')
const pPrice = ref(0)
const pCategory = ref('')
const pDesc = ref('')

const sName = ref('')
const sPrice = ref(0)
const sDesc = ref('')

const dName = ref('')
const dPercent = ref(0)

type PendingDelete =
  | { kind: 'product'; id: string; name: string }
  | { kind: 'service'; id: string; name: string }
  | { kind: 'discount'; id: string; name: string }

const pendingDelete = ref<PendingDelete | null>(null)

function requestDeleteProduct(product: Product) {
  pendingDelete.value = {
    kind: 'product',
    id: product.id,
    name: product.name,
  }
}

function requestDeleteService(service: Service) {
  pendingDelete.value = {
    kind: 'service',
    id: service.id,
    name: service.name,
  }
}

function requestDeleteDiscount(discount: DiscountOption) {
  pendingDelete.value = {
    kind: 'discount',
    id: discount.id,
    name: discount.name,
  }
}

function cancelPendingDelete() {
  pendingDelete.value = null
}

function confirmPendingDelete() {
  const pending = pendingDelete.value
  if (!pending) return
  if (pending.kind === 'product') {
    emit('deleteProduct', pending.id)
  } else if (pending.kind === 'service') {
    emit('deleteService', pending.id)
  } else {
    emit('deleteDiscount', pending.id)
  }
  pendingDelete.value = null
}

function handleCreateProduct(e: Event) {
  e.preventDefault()
  if (!pName.value.trim() || pPrice.value <= 0) {
    alert(t('quotation.pages.catalog.validationProductIncomplete'))
    return
  }
  emit('addProduct', {
    id: `prod-${Date.now()}`,
    name: pName.value,
    code: buildAutoCode('SW'),
    listPrice: pPrice.value,
    category: pCategory.value,
    description: pDesc.value || t('quotation.pages.catalog.noDescription'),
  })
  pName.value = ''
  pPrice.value = 0
  pDesc.value = ''
  isFormOpen.value = false
}

function handleCreateService(e: Event) {
  e.preventDefault()
  if (!sName.value.trim() || sPrice.value <= 0) {
    alert(t('quotation.pages.catalog.validationServiceIncomplete'))
    return
  }
  emit('addService', {
    id: `serv-${Date.now()}`,
    name: sName.value,
    code: buildAutoCode('OT'),
    listPrice: sPrice.value,
    unit: 'item',
    description: sDesc.value || t('quotation.pages.catalog.noServiceDetails'),
  })
  sName.value = ''
  sPrice.value = 0
  sDesc.value = ''
  isFormOpen.value = false
}

function handleCreateDiscount(e: Event) {
  e.preventDefault()
  if (!dName.value.trim() || dPercent.value < 0 || dPercent.value > 100) {
    alert(t('quotation.pages.catalog.validationDiscountInvalid'))
    return
  }
  emit('addDiscount', {
    id: `disc-${Date.now()}`,
    name: dName.value,
    percent: dPercent.value,
  })
  dName.value = ''
  dPercent.value = 0
  isFormOpen.value = false
}

/**
 * Catalog Category must match New Quote Product Line options 1:1.
 */
const categoryOptions = computed(() => {
  const seen = new Set<string>()
  const options: { value: string; label: string }[] = []

  props.productLineOptions.forEach((option) => {
    const label = (option.label || option.value || '').trim()
    if (!label) return
    const key = label.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    options.push({ value: label, label })
  })

  return options
})

watch(
  categoryOptions,
  (options) => {
    if (!options.length) return
    if (!options.some((option) => option.value === pCategory.value)) {
      pCategory.value = options[0].value
    }
  },
  { immediate: true },
)
</script>


<template>
  <div id="catalog-manager-root" class="space-y-5">
    <header>
      <h2 class="text-xl font-bold text-dm-text">{{ t('quotation.pages.catalog.catalogTitle') }}</h2>
      <p class="mt-1 text-sm text-dm-text-tertiary">{{ t('quotation.pages.catalog.catalogSubtitle') }}</p>
    </header>

    <div data-catalog-layout class="grid min-h-[520px] min-w-0 grid-cols-1 overflow-hidden rounded-lg border border-dm-border-light bg-white lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside data-catalog-tree class="border-b border-dm-border-light p-3 lg:border-b-0 lg:border-r" :aria-label="t('quotation.pages.catalog.configuration')">
        <p class="px-1 pb-2 text-xs font-semibold text-dm-text">{{ t('quotation.pages.catalog.configuration') }}</p>

        <div data-catalog-parent="quote-descriptions" class="space-y-1">
          <button type="button" class="flex h-8 w-full items-center gap-2 rounded-md px-1 text-left text-xs font-semibold text-dm-text hover:bg-slate-50" :aria-expanded="quoteDescriptionsExpanded" @click="quoteDescriptionsExpanded = !quoteDescriptionsExpanded">
            <ChevronDown class="h-3.5 w-3.5 text-dm-text-tertiary transition-transform" :class="quoteDescriptionsExpanded ? '' : '-rotate-90'" />
            <FolderOpen class="h-4 w-4 text-dm-text-tertiary" />
            <span class="min-w-0 flex-1 truncate">{{ t('quotation.pages.catalog.quoteDescriptions') }}</span>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-dm-text-tertiary">{{ products.length + services.length }}</span>
          </button>
          <div v-show="quoteDescriptionsExpanded" class="ml-4 space-y-1 border-l border-dm-border-light pl-2">
            <button data-catalog-child="products" type="button" class="catalog-tree-item" :class="subTab === 'products' ? 'catalog-tree-item-active' : ''" :aria-current="subTab === 'products' ? 'page' : undefined" @click="setSubTab('products')">
              <span class="min-w-0 flex-1 truncate">{{ t('quotation.pages.catalog.software') }}</span><span>{{ products.length }}</span>
            </button>
            <button data-catalog-child="services" type="button" class="catalog-tree-item" :class="subTab === 'services' ? 'catalog-tree-item-active' : ''" :aria-current="subTab === 'services' ? 'page' : undefined" @click="setSubTab('services')">
              <span class="min-w-0 flex-1 truncate">{{ t('quotation.pages.catalog.others') }}</span><span>{{ services.length }}</span>
            </button>
          </div>
        </div>

        <div data-catalog-parent="discount-settings" class="mt-2 space-y-1">
          <button type="button" class="flex h-8 w-full items-center gap-2 rounded-md px-1 text-left text-xs font-semibold text-dm-text hover:bg-slate-50" :aria-expanded="discountSettingsExpanded" @click="discountSettingsExpanded = !discountSettingsExpanded">
            <ChevronDown class="h-3.5 w-3.5 text-dm-text-tertiary transition-transform" :class="discountSettingsExpanded ? '' : '-rotate-90'" /><Percent class="h-4 w-4 text-dm-text-tertiary" />
            <span class="min-w-0 flex-1 truncate">{{ t('quotation.pages.catalog.discountSettings') }}</span>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-dm-text-tertiary">{{ discounts.length }}</span>
          </button>
          <div v-show="discountSettingsExpanded" class="ml-4 border-l border-dm-border-light pl-2">
            <button type="button" class="catalog-tree-item" :class="subTab === 'discounts' ? 'catalog-tree-item-active' : ''" :aria-current="subTab === 'discounts' ? 'page' : undefined" @click="setSubTab('discounts')">
              <span class="min-w-0 flex-1 truncate">{{ t('quotation.pages.catalog.volumeDiscounts') }}</span><span>{{ discounts.length }}</span>
            </button>
          </div>
        </div>

        <div data-catalog-parent="system-settings" class="mt-2">
          <button type="button" class="flex h-8 w-full items-center gap-2 rounded-md px-1 text-left text-xs font-semibold text-dm-text hover:bg-slate-50" :aria-expanded="systemSettingsExpanded" @click="systemSettingsExpanded = !systemSettingsExpanded">
            <ChevronDown class="h-3.5 w-3.5 text-dm-text-tertiary transition-transform" :class="systemSettingsExpanded ? '' : '-rotate-90'" /><Settings class="h-4 w-4 text-dm-text-tertiary" />
            <span>{{ t('quotation.pages.catalog.systemSettings') }}</span>
          </button>
          <div v-show="systemSettingsExpanded" class="ml-4 space-y-0.5 border-l border-dm-border-light pl-2">
            <span v-for="key in ['productCategories', 'currenciesPricing', 'paymentTerms', 'quoteNumbering']" :key="key" class="flex h-8 items-center px-3 text-xs text-dm-text-tertiary">
              {{ t(`quotation.pages.catalog.${key}`) }}
            </span>
          </div>
        </div>
      </aside>

      <section data-catalog-content class="min-w-0">
        <div class="flex flex-col gap-3 border-b border-dm-border-light px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <h3 class="text-base font-bold text-dm-text">{{ t(`quotation.pages.catalog.${subTab}Title`) }}</h3>
            <p class="mt-0.5 text-xs text-dm-text-tertiary">{{ t(`quotation.pages.catalog.${subTab}Subtitle`) }}</p>
          </div>
          <div class="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
            <label class="relative block min-w-0 sm:w-48">
              <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary" />
              <input data-catalog-search v-model="searchQuery" type="search" :aria-label="t('quotation.pages.catalog.search')" :placeholder="t(`quotation.pages.catalog.${subTab}Search`)" class="h-9 w-full rounded-lg border border-dm-border bg-white pl-9 pr-3 text-xs text-dm-text outline-none focus:border-dm-primary" />
            </label>
            <button data-catalog-add type="button" class="flex h-9 shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-dm-primary px-4 text-xs font-semibold text-white hover:bg-dm-primary-hover" @click="isFormOpen = true">
              <Plus class="h-4 w-4" />{{ t(`quotation.pages.catalog.${subTab}Add`) }}
            </button>
          </div>
        </div>

        <div
          v-if="pendingDelete"
          class="flex flex-wrap items-center justify-between gap-3 border-b border-rose-100 bg-rose-50 px-4 py-3 text-xs"
        >
          <p class="font-medium text-rose-700">
            <template v-if="pendingDelete.kind === 'product'">
              {{
                t('quotation.pages.catalog.confirmDeleteProduct', {
                  name: pendingDelete.name,
                })
              }}
            </template>
            <template v-else-if="pendingDelete.kind === 'service'">
              {{
                t('quotation.pages.catalog.confirmDeleteService', {
                  name: pendingDelete.name,
                })
              }}
            </template>
            <template v-else>
              {{
                t('quotation.pages.catalog.confirmDeleteDiscount', {
                  name: pendingDelete.name,
                })
              }}
            </template>
          </p>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="cursor-pointer rounded-md border border-dm-border bg-white px-3 py-1.5 font-semibold text-dm-text hover:bg-slate-50"
              @click="cancelPendingDelete"
            >
              {{ t('quotation.common.cancel') }}
            </button>
            <button
              type="button"
              class="cursor-pointer rounded-md bg-rose-600 px-3 py-1.5 font-semibold text-white hover:bg-rose-700"
              @click="confirmPendingDelete"
            >
              {{ t('quotation.pages.catalog.confirmDeleteAction') }}
            </button>
          </div>
        </div>
        <div class="overflow-x-auto text-xs">
          <table v-if="subTab === 'products'" class="w-full text-left">
            <thead>
              <tr class="border-b border-dm-border-light bg-[#fafafa] text-[10px] font-bold uppercase text-dm-text-tertiary">
                <th class="px-4 py-2.5">{{ t('quotation.pages.catalog.tableProductName') }}</th>
                <th class="px-4 py-2.5">{{ t('quotation.pages.catalog.tableCategory') }}</th>
                <th class="px-4 py-2.5 text-right">{{ t('quotation.pages.catalog.tableListPrice') }}</th>
                <th class="px-4 py-2.5 text-center">{{ t('quotation.pages.catalog.tableActions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="p in filteredProducts"
                :key="p.id"
                class="hover:bg-[#fafafa]/40"
                :class="
                  pendingDelete?.kind === 'product' && pendingDelete.id === p.id
                    ? 'bg-rose-50/70'
                    : ''
                "
              >
                <td class="px-4 py-3">
                  <div>
                    <p class="font-semibold text-dm-text">{{ p.name }}</p>
                    <p class="mt-0.5 max-w-xs truncate text-[10px] text-dm-text-tertiary">{{ p.description }}</p>
                  </div>
                </td>
                <td class="px-4 py-3 text-dm-text-tertiary">{{ p.category }}</td>
                <td class="px-4 py-3 text-right font-mono font-bold text-dm-text">{{ formatCatalogPrice(p.listPrice, p.pricingNote) }}</td>
                <td class="px-4 py-3 text-center">
                  <button
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary hover:bg-red-50 hover:text-red-500"
                    :aria-label="t('quotation.pages.catalog.deleteProduct', { name: p.name })"
                    :title="t('quotation.pages.catalog.deleteProduct', { name: p.name })"
                    @click.stop="requestDeleteProduct(p)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>

          <table v-else-if="subTab === 'services'" class="w-full text-left">
            <thead>
              <tr class="border-b border-dm-border-light bg-[#fafafa] text-[10px] font-bold uppercase text-dm-text-tertiary">
                <th class="px-4 py-2.5">{{ t('quotation.pages.catalog.tableServiceName') }}</th>
                <th class="px-4 py-2.5 text-right">{{ t('quotation.pages.catalog.tableRefPrice') }}</th>
                <th class="px-4 py-2.5 text-center">{{ t('quotation.pages.catalog.tableActions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="s in filteredServices"
                :key="s.id"
                class="hover:bg-[#fafafa]/40"
                :class="
                  pendingDelete?.kind === 'service' && pendingDelete.id === s.id
                    ? 'bg-rose-50/70'
                    : ''
                "
              >
                <td class="px-4 py-3">
                  <div>
                    <p class="font-semibold text-dm-text">{{ s.name }}</p>
                    <p class="mt-0.5 max-w-xs truncate text-[10px] text-dm-text-tertiary">{{ s.description }}</p>
                  </div>
                </td>
                <td class="px-4 py-3 text-right font-mono font-bold text-dm-text">{{ formatCatalogPrice(s.listPrice, s.pricingNote) }}</td>
                <td class="px-4 py-3 text-center">
                  <button
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary hover:bg-red-50 hover:text-red-500"
                    :aria-label="t('quotation.pages.catalog.deleteService', { name: s.name })"
                    :title="t('quotation.pages.catalog.deleteService', { name: s.name })"
                    @click.stop="requestDeleteService(s)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>

          <table v-else class="w-full text-left">
            <thead>
              <tr class="border-b border-dm-border-light bg-[#fafafa] text-[10px] font-bold uppercase text-dm-text-tertiary">
                <th class="px-4 py-2.5">{{ t('quotation.pages.catalog.tableDiscountId') }}</th>
                <th class="px-4 py-2.5">{{ t('quotation.pages.catalog.tableDiscountLabel') }}</th>
                <th class="px-4 py-2.5 text-right">{{ t('quotation.pages.catalog.tableDiscountPercent') }}</th>
                <th class="px-4 py-2.5 text-center">{{ t('quotation.pages.catalog.tableActions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="d in filteredDiscounts"
                :key="d.id"
                class="hover:bg-[#fafafa]/40"
                :class="
                  pendingDelete?.kind === 'discount' && pendingDelete.id === d.id
                    ? 'bg-rose-50/70'
                    : ''
                "
              >
                <td class="px-4 py-3 font-mono text-dm-text-tertiary">{{ d.id }}</td>
                <td class="px-4 py-3 font-semibold text-dm-text">{{ d.name }}</td>
                <td class="px-4 py-3 text-right font-mono font-bold text-emerald-600">{{ d.percent }}%</td>
                <td class="px-4 py-3 text-center">
                  <span v-if="d.percent === 0" class="select-none text-[10px] font-bold text-slate-300">{{ t('quotation.pages.catalog.systemLocked') }}</span>
                  <button
                    v-else
                    type="button"
                    class="cursor-pointer rounded-sm p-1 text-dm-text-tertiary hover:bg-red-50 hover:text-red-500"
                    :aria-label="t('quotation.pages.catalog.deleteDiscount', { name: d.name })"
                    :title="t('quotation.pages.catalog.deleteDiscount', { name: d.name })"
                    @click.stop="requestDeleteDiscount(d)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="(subTab === 'products' && !filteredProducts.length) || (subTab === 'services' && !filteredServices.length) || (subTab === 'discounts' && !filteredDiscounts.length)" class="flex h-52 items-center justify-center text-xs text-dm-text-tertiary">
            {{ searchQuery ? t('quotation.pages.catalog.noSearchResults') : t(`quotation.pages.catalog.${subTab}Empty`) }}
          </div>
        </div>
      </section>
    </div>

    <div v-if="isFormOpen" data-catalog-form-modal class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/35 p-4" @click.self="isFormOpen = false">
      <div class="w-full max-w-md overflow-hidden rounded-lg bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-dm-border-light px-5 py-4">
          <h3 class="text-sm font-bold text-dm-text">{{ t(`quotation.pages.catalog.${subTab}Add`) }}</h3>
          <button type="button" class="rounded-md p-1 text-dm-text-tertiary hover:bg-slate-100 hover:text-dm-text" :aria-label="t('quotation.common.close')" @click="isFormOpen = false"><X class="h-4 w-4" /></button>
        </div>
        <form v-if="subTab === 'products'" class="space-y-4 p-5 text-xs" @submit="handleCreateProduct">
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.productName') }} *</span><input v-model="pName" required :placeholder="t('quotation.pages.catalog.productNamePlaceholder')" class="catalog-input" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.productPrice') }} *</span><input v-model.number="pPrice" type="number" min="0.01" step="0.01" required class="catalog-input font-mono" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.productCategory') }}</span><FormSelect v-model="pCategory" :options="categoryOptions" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.productDesc') }}</span><textarea v-model="pDesc" rows="3" :placeholder="t('quotation.pages.catalog.productDescPlaceholder')" class="catalog-input h-auto resize-y" /></label>
          <button type="submit" class="catalog-save-button">{{ t('quotation.actions.saveSoftware') }}</button>
        </form>
        <form v-else-if="subTab === 'services'" class="space-y-4 p-5 text-xs" @submit="handleCreateService">
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.serviceName') }} *</span><input v-model="sName" required :placeholder="t('quotation.pages.catalog.serviceNamePlaceholder')" class="catalog-input" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.servicePrice') }} *</span><input v-model.number="sPrice" type="number" min="0.01" step="0.01" required class="catalog-input font-mono" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.serviceDesc') }}</span><textarea v-model="sDesc" rows="3" :placeholder="t('quotation.pages.catalog.serviceDescPlaceholder')" class="catalog-input h-auto resize-y" /></label>
          <button type="submit" class="catalog-save-button">{{ t('quotation.actions.saveService') }}</button>
        </form>
        <form v-else class="space-y-4 p-5 text-xs" @submit="handleCreateDiscount">
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.discountName') }} *</span><input v-model="dName" required :placeholder="t('quotation.pages.catalog.discountNamePlaceholder')" class="catalog-input" /></label>
          <label class="block"><span class="mb-1 block font-semibold text-dm-text-tertiary">{{ t('quotation.pages.catalog.discountPercent') }} *</span><input v-model.number="dPercent" type="number" min="0" max="100" required class="catalog-input font-mono" /><span class="mt-1 block text-[10px] text-dm-text-tertiary">{{ t('quotation.pages.catalog.discountHint') }}</span></label>
          <button type="submit" class="catalog-save-button">{{ t('quotation.actions.saveDiscount') }}</button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.catalog-tree-item { @apply flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-3 text-left text-xs text-dm-text-secondary transition-colors hover:bg-slate-50 hover:text-dm-text focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500; }
.catalog-tree-item-active { @apply bg-blue-50 font-medium text-dm-primary hover:bg-blue-50 hover:text-dm-primary; box-shadow: inset 2px 0 0 #1677ff; }
.catalog-input { @apply h-9 w-full rounded-lg border border-dm-border bg-white px-3 text-xs text-dm-text outline-none focus:border-dm-primary; }
.catalog-save-button { @apply h-9 w-full cursor-pointer rounded-lg bg-dm-primary font-semibold text-white hover:bg-dm-primary-hover; }
</style>
