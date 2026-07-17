<script setup lang="ts">
/**
 * Thin router wrapper around ProductServiceManager.
 * Prefer App.vue tab wiring (`catalog`) for full feature parity.
 */
import { ref, watch } from 'vue'
import ProductServiceManager from '../components/ProductServiceManager.vue'
import {
  MOCK_CATALOG_VERSION,
  MOCK_DISCOUNTS,
  MOCK_PRODUCTS,
  MOCK_SERVICES,
} from '../data'
import type { DiscountOption, Product, Service } from '../types'
import { loadProductLineOptions } from '../utils/quotationNumbering'

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

const productLineOptions = loadProductLineOptions()

watch(
  products,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_products', JSON.stringify(value))
  },
  { deep: true },
)

watch(
  services,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_services', JSON.stringify(value))
  },
  { deep: true },
)

watch(
  discounts,
  (value) => {
    localStorage.setItem('qmp_catalog_version', MOCK_CATALOG_VERSION)
    localStorage.setItem('qmp_discounts', JSON.stringify(value))
  },
  { deep: true },
)

function handleAddProduct(prod: Product) {
  products.value = [prod, ...products.value]
}

function handleDeleteProduct(id: string) {
  products.value = products.value.filter((item) => item.id !== id)
}

function handleAddService(serv: Service) {
  services.value = [serv, ...services.value]
}

function handleDeleteService(id: string) {
  services.value = services.value.filter((item) => item.id !== id)
}

function handleAddDiscount(disc: DiscountOption) {
  discounts.value = [...discounts.value, disc]
}

function handleDeleteDiscount(id: string) {
  discounts.value = discounts.value.filter((item) => item.id !== id)
}
</script>

<template>
  <ProductServiceManager
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
</template>
