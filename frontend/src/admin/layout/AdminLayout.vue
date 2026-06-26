<template>
  <div class="layout-admin h-screen flex w-full overflow-hidden bg-gray-50">
    <AdminSidebar
      :show-mobile-menu="showMobileMenu"
      :collapsed="sidebarCollapsed"
      @close="showMobileMenu = false"
      @toggle-collapse="toggleSidebarCollapse"
    />
    <div class="flex-1 flex flex-col min-w-0 w-0 h-full overflow-hidden">
      <AdminHeader @toggle-menu="showMobileMenu = !showMobileMenu" />
      <main class="flex-1 py-3 px-4 min-w-0 overflow-y-auto bg-gray-50">
        <div :key="route.path">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AdminHeader from './AdminHeader.vue'
import AdminSidebar from './AdminSidebar.vue'

const showMobileMenu = ref(false)
const sidebarCollapsed = ref(false)
const route = useRoute()

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'admin_sidebar_collapsed'

const toggleSidebarCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  if (typeof window !== 'undefined') {
    localStorage.setItem(
      SIDEBAR_COLLAPSED_STORAGE_KEY,
      JSON.stringify(sidebarCollapsed.value)
    )
  }
}

onMounted(() => {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY)
  if (saved !== null) {
    try {
      sidebarCollapsed.value = JSON.parse(saved)
    } catch {
      sidebarCollapsed.value = false
    }
  }
})
</script>
