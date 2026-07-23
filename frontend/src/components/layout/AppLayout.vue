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
        v-if="showHeader"
        :show-menu-button="resolvedShowSidebar"
        @toggle-menu="showMobileMenu = !showMobileMenu"
      />

      <!-- Main content - scrollable -->
      <main
        class="flex-1 min-w-0 bg-gray-50"
        :class="
          [
            contentScrollable ? 'overflow-y-auto' : 'overflow-hidden',
            fullBleed
              ? 'p-0'
              : resolvedShowSidebar
                ? 'py-3 px-4'
                : 'px-6 py-6 sm:px-8 lg:px-10'
          ]
        "
      >
        <div :key="contentKey" :class="fullBleed ? 'h-full' : ''">
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
  },
  showHeader: {
    type: Boolean,
    default: true
  },
  contentScrollable: {
    type: Boolean,
    default: true
  }
})

const showMobileMenu = ref(false)
const sidebarCollapsed = ref(false)
const route = useRoute()
const contentKey = computed(() =>
  route.path.startsWith('/quotation') ? 'quotation' : route.path
)
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
    sessionStorage.setItem(
      SIDEBAR_COLLAPSED_STORAGE_KEY,
      JSON.stringify(sidebarCollapsed.value)
    )
  }
}

onMounted(() => {
  if (typeof window === 'undefined') return
  const saved = sessionStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY)
  if (saved !== null) {
    try {
      sidebarCollapsed.value = JSON.parse(saved)
    } catch {
      sidebarCollapsed.value = false
    }
  }
})
</script>
