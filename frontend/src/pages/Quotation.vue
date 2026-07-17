<template>
  <AppLayout :full-bleed="true">
    <section class="quotation-devmind-shell">
      <QuotationApp />
    </section>
  </AppLayout>
</template>

<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'
import QuotationApp from '@/modules/quotation/App.vue'
import '@/modules/quotation/style.css'
</script>

<style scoped>
.quotation-devmind-shell {
  min-height: 100%;
  background: #f9fafb;
}

.quotation-devmind-shell :deep(#app-container) {
  min-height: calc(100vh - 4rem);
  height: auto;
  overflow: visible;
  background: #f9fafb;
}

.quotation-devmind-shell :deep(#app-sidebar) {
  display: none;
}

.quotation-devmind-shell :deep(#app-header) {
  display: none;
}

.quotation-devmind-shell :deep(#main-content-pane) {
  min-width: 0;
  overflow: visible;
}

.quotation-devmind-shell :deep(#app-scroll-stage) {
  overflow: visible;
  padding: 1.5rem;
  background: #f9fafb;
}
</style>
