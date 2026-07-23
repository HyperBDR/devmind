<template>
  <AppLayout :content-scrollable="false" :full-bleed="true">
    <section class="quotation-devmind-shell">
      <QuotationApp />
    </section>
  </AppLayout>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import AppLayout from '@/components/layout/AppLayout.vue'
import QuotationApp from '@/modules/quotation/App.vue'
import '@/modules/quotation/style.css'

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

.quotation-devmind-shell {
  height: 100%;
  min-height: 0;
  background: #f9fafb;
}

.quotation-devmind-shell :deep(#app-container) {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: #f9fafb;
}

.quotation-devmind-shell :deep(#app-sidebar) {
  display: none;
}

.quotation-devmind-shell :deep(#app-header) {
  display: none;
}

.quotation-devmind-shell :deep(#main-content-pane) {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.quotation-devmind-shell :deep(#app-scroll-stage) {
  min-height: 0;
  overscroll-behavior: contain;
  overflow-y: auto;
  padding: 1.5rem;
  background: #f9fafb;
}
</style>
