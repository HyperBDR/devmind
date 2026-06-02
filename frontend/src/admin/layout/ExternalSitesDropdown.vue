<template>
  <div v-if="visibleSites.length > 0" class="relative" ref="menuRef">
    <button
      @click="toggle"
      class="flex items-center gap-1.5 px-2 py-1.5 text-sm text-slate-300 hover:text-slate-100 rounded-md hover:bg-slate-700 transition-colors"
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
          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M3.6 9h16.8M3.6 15h16.8M12 3a15.3 15.3 0 010 18M12 3a15.3 15.3 0 000 18"
        />
      </svg>
      <span class="hidden sm:inline">{{
        t('management.externalSiteProxy')
      }}</span>
      <svg
        class="w-3 h-3 transition-transform"
        :class="{ 'rotate-180': open }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </button>

    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-64 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200"
      >
        <button
          v-for="site in visibleSites"
          :key="site.id"
          @click="openSite(site)"
          class="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3 transition-colors"
        >
          <span class="flex-1 truncate">{{ site.name }}</span>
          <span class="text-xs text-gray-400 font-mono">{{
            site.access_mode
          }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { externalProxyAdminApi } from '@/admin/api'

const { t } = useI18n()
const userStore = useUserStore()
const open = ref(false)
const sites = ref([])
const menuRef = ref(null)
const loaded = ref(false)

const visibleSites = computed(() =>
  sites.value.filter((s) => {
    if (!s.is_active) return false
    const feature = s.required_feature || 'admin_console'
    return userStore.userHasFeature(feature)
  })
)

function toggle() {
  open.value = !open.value
  if (open.value && !loaded.value) {
    loadSites()
  }
}

async function loadSites() {
  try {
    sites.value = (await externalProxyAdminApi.getSites()) || []
    loaded.value = true
  } catch {
    sites.value = []
  }
}

function openSite(site) {
  open.value = false
  if (site.access_mode === 'proxy') {
    window.open(`/proxy/${site.slug}/`, '_blank', 'noopener')
  } else if (site.access_mode === 'iframe') {
    window.open(
      `/management/external-sites/frame/${site.id}`,
      '_blank',
      'noopener'
    )
  } else {
    window.open(
      `/management/external-sites/open/${site.id}`,
      '_blank',
      'noopener'
    )
  }
}

function handleClickOutside(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>
