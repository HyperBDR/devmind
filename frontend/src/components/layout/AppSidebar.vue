<template>
  <!-- Mobile overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="showMobileMenu && isMobile"
      @click="$emit('close')"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40 lg:hidden"
    />
  </Transition>

  <!-- Sidebar -->
  <aside
    :class="[
      'bg-white border-r border-gray-200 flex flex-col transition-transform duration-300 ease-in-out w-64 flex-shrink-0 h-full',
      isMobile ? 'fixed inset-y-0 left-0 z-50' : 'static',
      isMobile && !showMobileMenu ? '-translate-x-full' : 'translate-x-0'
    ]"
  >
    <!-- Logo and close button -->
    <div
      class="flex items-center justify-between h-16 px-4 border-b border-gray-200"
    >
      <router-link
        :to="homePath"
        class="flex items-center space-x-2 flex-1"
        @click="isMobile && $emit('close')"
      >
        <img
          src="/android-chrome-192x192.png"
          alt="DevMind Logo"
          class="w-8 h-8"
        />
        <span class="text-xl font-semibold text-gray-900">{{
          t('common.appName')
        }}</span>
      </router-link>
      <button
        v-if="isMobile"
        @click="$emit('close')"
        class="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
      >
        <svg
          class="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto flex flex-col">
      <div class="flex-1 space-y-1">
        <router-link
          v-if="userStore.userHasFeature('workspace')"
          to="/dashboard"
          class="nav-item"
          :class="isActive('/dashboard') ? 'nav-item-active' : ''"
          @click="isMobile && $emit('close')"
          @mouseenter="preloadRoute('/dashboard')"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
            />
          </svg>
          <span>{{ t('dashboard.title') }}</span>
        </router-link>

        <!-- Cloud Billing Menu with Submenu -->
        <div
          v-if="userStore.userHasFeature('operations_console')"
          class="menu-group"
        >
          <button
            @click="toggleCloudBillingMenu"
            class="nav-item nav-item-parent w-full"
          >
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
              />
            </svg>
            <span class="flex-1 text-left">{{
              t('cloudBilling.menuTitle')
            }}</span>
            <svg
              class="w-4 h-4 transition-transform"
              :class="cloudBillingMenuOpen ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div v-if="cloudBillingMenuOpen" class="submenu">
              <router-link
                to="/cloud-billing/billing"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/billing') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/billing')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>{{ t('cloudBilling.billing.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/tasks"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/tasks') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/tasks')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  />
                </svg>
                <span>{{ t('cloudBilling.tasks.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/alerts"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/alerts') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/alerts')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <span>{{ t('cloudBilling.alerts.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/settings"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/settings') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/settings')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span>{{ t('cloudBilling.settings.title') }}</span>
              </router-link>
            </div>
          </Transition>
        </div>

        <!-- Data Collector Menu with Submenu -->
        <div
          v-if="userStore.userHasFeature('operations_console')"
          class="menu-group"
        >
          <button
            @click="toggleDataCollectorMenu"
            class="nav-item nav-item-parent w-full"
          >
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
              />
            </svg>
            <span class="flex-1 text-left">{{
              t('dataCollector.menuTitle')
            }}</span>
            <svg
              class="w-4 h-4 transition-transform"
              :class="dataCollectorMenuOpen ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div v-if="dataCollectorMenuOpen" class="submenu">
              <router-link
                to="/data-collector/stats"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/stats') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/stats')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <span>{{ t('dataCollector.stats.title') }}</span>
              </router-link>
              <router-link
                to="/data-collector/records"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/records') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/records')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>{{ t('dataCollector.records.pageTitle') }}</span>
              </router-link>
              <router-link
                to="/data-collector/tasks"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/tasks') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/tasks')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  />
                </svg>
                <span>{{ t('dataCollector.tasks.title') }}</span>
              </router-link>
              <router-link
                to="/data-collector/settings"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/settings') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/settings')"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span>{{ t('dataCollector.settings.title') }}</span>
              </router-link>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Settings Menu -->
      <div class="mt-auto pt-4 border-t border-gray-200">
        <router-link
          :to="{ name: 'SettingsNotifications' }"
          class="nav-item"
          :class="isActive('/settings/notifications') ? 'nav-item-active' : ''"
          @mouseenter="preloadRoute('/settings/notifications')"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <span>{{ t('common.settings') }}</span>
        </router-link>
      </div>
    </nav>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'

const props = defineProps({
  showMobileMenu: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const homePath = computed(() => userStore.getUserLandingPath())

// Menu expand/collapse state - default to expanded
const cloudBillingMenuOpen = ref(true)
const dataCollectorMenuOpen = ref(true)

// Load expanded state from localStorage
const loadExpandedState = () => {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem('sidebar_cloud_billing_expanded')
  if (saved !== null) {
    try {
      cloudBillingMenuOpen.value = JSON.parse(saved)
    } catch (e) {
      // Ignore parse errors
    }
  }
  const savedDC = localStorage.getItem('sidebar_data_collector_expanded')
  if (savedDC !== null) {
    try {
      dataCollectorMenuOpen.value = JSON.parse(savedDC)
    } catch (e) {
      // Ignore parse errors
    }
  }
}

// Save expanded state to localStorage
const saveExpandedState = () => {
  if (typeof window === 'undefined') return
  localStorage.setItem(
    'sidebar_cloud_billing_expanded',
    JSON.stringify(cloudBillingMenuOpen.value)
  )
  localStorage.setItem(
    'sidebar_data_collector_expanded',
    JSON.stringify(dataCollectorMenuOpen.value)
  )
}

const MOBILE_BREAKPOINT = 1024

const isMobile = computed(() => {
  if (typeof window === 'undefined') return false
  return window.innerWidth < MOBILE_BREAKPOINT
})

const isActive = (path) => {
  if (path === '/dashboard') {
    return route.path === '/dashboard' || route.path === '/'
  }
  // For submenu items, use exact match or starts with
  return route.path === path || route.path.startsWith(path + '/')
}

const toggleCloudBillingMenu = () => {
  cloudBillingMenuOpen.value = !cloudBillingMenuOpen.value
  saveExpandedState()
}

const toggleDataCollectorMenu = () => {
  dataCollectorMenuOpen.value = !dataCollectorMenuOpen.value
  saveExpandedState()
}

// Auto-expand menu if current route is in that section
watch(
  () => route.path,
  (newPath) => {
    if (newPath.startsWith('/cloud-billing')) {
      cloudBillingMenuOpen.value = true
      saveExpandedState()
    }
    if (newPath.startsWith('/data-collector')) {
      dataCollectorMenuOpen.value = true
      saveExpandedState()
    }
  },
  { immediate: true }
)

// Preload route component on link hover for faster navigation
// Use a cache to avoid duplicate preloads
const preloadCache = new Set()

const preloadRoute = (path) => {
  // Skip if already preloaded
  if (preloadCache.has(path)) {
    return
  }

  try {
    const route = router.resolve(path)
    if (route.matched.length > 0) {
      const matched = route.matched[0]
      // Preload the component if it's lazy-loaded
      if (matched.components) {
        Object.values(matched.components).forEach((component) => {
          if (typeof component === 'function') {
            // Mark as preloading
            preloadCache.add(path)
            component().catch(() => {
              // Remove from cache on error so we can retry
              preloadCache.delete(path)
            })
          }
        })
      }
    }
  } catch (error) {
    // Ignore preload errors silently
  }
}

onMounted(() => {
  loadExpandedState()
})
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all duration-200;
}

.nav-item-active {
  @apply bg-primary-50 text-primary-600;
}

.nav-item-parent {
  @apply w-full cursor-pointer font-semibold text-gray-800;
}

.nav-item-parent:hover {
  @apply bg-gray-50;
}

.nav-item-child {
  @apply relative pl-10 py-2 text-sm font-normal text-gray-600;
  margin-left: 0.75rem;
  border-radius: 0.375rem;
}

.nav-item-child:hover {
  @apply bg-gray-50;
}

.nav-item-child.nav-item-active {
  @apply bg-primary-50 text-primary-600 font-medium;
}

.menu-group {
  @apply space-y-0 mb-1.5;
}

.submenu {
  @apply overflow-hidden pl-0 mt-1 space-y-0.5;
  transition: all 0.2s ease-in-out;
}

.submenu .nav-item {
  @apply ml-0;
}

/* Add a subtle left border indicator for child items */
.nav-item-child::before {
  content: '';
  @apply absolute left-6 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-gray-300 rounded;
  transition: all 0.2s;
}

.nav-item-child.nav-item-active::before {
  @apply bg-primary-500 w-1;
}

/* Improve icon spacing in parent items */
.nav-item-parent svg:first-child {
  @apply flex-shrink-0;
}

.nav-item-parent span {
  @apply flex-shrink-0;
}

.nav-item-parent svg:last-child {
  @apply flex-shrink-0 ml-1 opacity-70;
  transition:
    transform 0.2s ease-in-out,
    opacity 0.2s;
}

.nav-item-parent:hover svg:last-child {
  @apply opacity-100;
}
</style>
