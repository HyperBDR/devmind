<script setup lang="ts">
/**
 * Thin router wrapper around QuotationCreate.
 * Prefer App.vue tab wiring for full feature parity (catalog, product lines, history).
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuotationCreate from '../components/QuotationCreate.vue'
import {
  MOCK_DISCOUNTS,
  MOCK_PRODUCTS,
  MOCK_SERVICES,
} from '../data'
import type {
  DiscountOption,
  Product,
  ProductLineOption,
  Quotation,
  QuoteProductLine,
  Service,
} from '../types'
import { listQuotations, createQuotation, updateQuotation } from '../api/quotations'
import { useAuthStore } from '../stores/auth'
import { clearCreateQuoteDraft } from '../utils/createDraftStorage'
import { loadProductLineOptions, saveCustomProductLineOptions } from '../utils/quotationNumbering'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const products = ref<Product[]>([...MOCK_PRODUCTS])
const services = ref<Service[]>([...MOCK_SERVICES])
const discounts = ref<DiscountOption[]>([...MOCK_DISCOUNTS])
const quotations = ref<Quotation[]>([])
const productLineOptions = ref<ProductLineOption[]>(loadProductLineOptions())

const editingQuote = computed(() => {
  const editId = typeof route.query.edit === 'string' ? route.query.edit : null
  if (!editId) return null
  return quotations.value.find((q) => q.id === editId) || null
})

const currentUser = computed(() => auth.currentUser || undefined)

onMounted(async () => {
  try {
    quotations.value = await listQuotations()
  } catch {
    quotations.value = []
  }
})

async function handleSaveQuote(quote: Quotation) {
  if (editingQuote.value) {
    await updateQuotation(quote, { notes: 'Quote edited' })
  } else {
    await createQuotation(quote)
    clearCreateQuoteDraft(auth.currentUser?.email)
  }
  await router.push('/quotations')
}

function handleNavigateToTab(tab: string) {
  if (tab === 'list') void router.push('/quotations')
  else if (tab === 'create') void router.push('/quotations/new')
  else void router.push('/')
}

function handleAddProductLine(option: ProductLineOption) {
  productLineOptions.value = [...productLineOptions.value, option]
  saveCustomProductLineOptions(productLineOptions.value)
}

function handleDeleteProductLine(productLine: QuoteProductLine) {
  productLineOptions.value = productLineOptions.value.filter((item) => item.value !== productLine)
  saveCustomProductLineOptions(productLineOptions.value)
}
</script>

<template>
  <QuotationCreate
    :products="products"
    :services="services"
    :discounts="discounts"
    :quotations="quotations"
    :history-quotations="quotations"
    :editing-quote="editingQuote"
    :current-user="currentUser"
    :product-line-options="productLineOptions"
    @save-quote="handleSaveQuote"
    @navigate-to-tab="handleNavigateToTab"
    @add-product-line="handleAddProductLine"
    @delete-product-line="handleDeleteProductLine"
  />
</template>
