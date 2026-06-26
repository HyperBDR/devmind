<template>
  <div class="h-screen bg-gray-50 flex w-full overflow-hidden">
    <!-- Sidebar -->
    <AppSidebar
      v-if="resolvedShowSidebar"
      :show-mobile-menu="showMobileMenu"
      :collapsed="sidebarCollapsed"
      @close="showMobileMenu = false"
      @toggle-collapse="toggleSidebarCollapse"
    />

    <!-- Main content area -->
    <div class="flex-1 flex flex-col min-w-0 w-0 h-full overflow-hidden">
      <!-- Header -->
      <AppHeader
        :show-menu-button="resolvedShowSidebar"
        @toggle-menu="showMobileMenu = !showMobileMenu"
      />

      <!-- Main content - scrollable -->
      <main
        class="flex-1 min-w-0 overflow-y-auto bg-gray-50"
        :class="
          fullBleed
            ? 'p-0'
            : resolvedShowSidebar
              ? 'py-3 px-4'
              : 'px-6 py-6 sm:px-8 lg:px-10'
        "
      >
        <div :key="route.path" :class="fullBleed ? 'h-full' : ''">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'

const props = defineProps({
  showSidebar: {
    type: Boolean,
    default: true
  },
  fullBleed: {
    type: Boolean,
    default: false
  }
})

const showMobileMenu = ref(false)
const sidebarCollapsed = ref(false)
const route = useRoute()
const resolvedShowSidebar = computed(() => {
  if (
    route.path.startsWith('/settings') &&
    route.query.from_platform === 'operations_console'
  ) {
    return false
  }
  return props.showSidebar
})

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'app_sidebar_collapsed'

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
