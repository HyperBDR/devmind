<template>
  <AppLayout
    :content-scrollable="false"
    :full-bleed="true"
  >
    <section class="quotation-sales-shell">
      <SalesDashboard v-if="isDashboard" />
      <InvoiceCreate v-else-if="isEditor" />
      <InvoiceDetail v-else-if="isDetail" />
      <InvoiceList v-else />
    </section>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import AppLayout from '@/components/layout/AppLayout.vue'
import InvoiceCreate from '@/modules/quotation/components/sales/InvoiceCreate.vue'
import InvoiceDetail from '@/modules/quotation/components/sales/InvoiceDetail.vue'
import InvoiceList from '@/modules/quotation/components/sales/InvoiceList.vue'
import SalesDashboard from '@/modules/quotation/components/sales/SalesDashboard.vue'
import '@/modules/quotation/style.css'

const route = useRoute()
const isDashboard = computed(() => route.path.endsWith('/dashboard'))
const isEditor = computed(() =>
  ['QuoteDeskInvoiceCreate', 'QuoteDeskInvoiceEdit'].includes(
    String(route.name || ''),
  ),
)
const isDetail = computed(() => route.name === 'QuoteDeskInvoiceDetail')
const PAGE_SCROLL_LOCK_CLASS = 'quotation-page-scroll-locked'

onMounted(() => {
  document.documentElement.classList.add(PAGE_SCROLL_LOCK_CLASS)
  document.body.classList.add(PAGE_SCROLL_LOCK_CLASS)
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove(PAGE_SCROLL_LOCK_CLASS)
  document.body.classList.remove(PAGE_SCROLL_LOCK_CLASS)
})
</script>

<style scoped>
:global(html.quotation-page-scroll-locked),
:global(body.quotation-page-scroll-locked) {
  height: 100%;
  overflow: hidden;
}

.quotation-sales-shell {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  background: #f9fafb;
  font-family: Inter, "Noto Sans SC", system-ui, sans-serif;
  padding: 1.5rem;
}

</style>
