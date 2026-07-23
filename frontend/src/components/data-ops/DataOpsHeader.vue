<template>
  <header
    class="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between"
  >
    <div>
      <h1 class="text-2xl font-bold text-slate-950">
        {{ activeNav?.label || t('dataOps.nav.items.executive.label') }}
      </h1>
      <div
        v-if="activeNav?.key === 'executive'"
        class="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500"
      >
        <span class="inline-flex items-center gap-1.5">
          <svg
            aria-hidden="true"
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.8"
            viewBox="0 0 24 24"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6h4" />
          </svg>
          {{
            t('dataOps.header.dataMonth', {
              month: activeNav?.currentMonth || '—'
            })
          }}
        </span>
        <span>{{ activeNav?.note || activeNav?.description }}</span>
      </div>
      <p v-else class="mt-1 text-sm text-slate-500">
        {{ activeNav?.description }}
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-medium text-white transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-wait disabled:bg-slate-800 disabled:opacity-100"
        :aria-busy="loading"
        :disabled="loading || syncLoading"
        @click="$emit('refresh')"
      >
        <svg
          aria-hidden="true"
          class="h-4 w-4"
          :class="{ 'animate-spin': loading }"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.8"
          viewBox="0 0 24 24"
        >
          <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
          <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
          <path d="M16 16h5v5" />
        </svg>
        {{
          loading ? t('dataOps.header.refreshing') : t('dataOps.header.refresh')
        }}
      </button>
      <button
        v-if="canManageSync && showSyncActions"
        type="button"
        class="inline-flex h-11 items-center justify-center rounded-lg bg-white px-4 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:cursor-wait disabled:text-slate-400"
        :disabled="preflightLoading || loading || syncLoading"
        @click="$emit('preflight')"
      >
        {{
          preflightLoading
            ? t('dataOps.header.checking')
            : t('dataOps.header.checkPermissions')
        }}
      </button>
      <button
        v-if="canManageSync && showSyncActions"
        type="button"
        class="inline-flex h-11 min-w-28 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 disabled:cursor-wait disabled:bg-indigo-500 disabled:opacity-100"
        :aria-busy="syncLoading"
        :disabled="syncLoading || loading || preflightLoading"
        @click="$emit('full-sync')"
      >
        <svg
          aria-hidden="true"
          class="h-4 w-4"
          :class="{ 'animate-spin': syncLoading }"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.8"
          viewBox="0 0 24 24"
        >
          <path d="M20 12a8 8 0 1 1-2.34-5.66" />
          <path d="M20 4v6h-6" />
        </svg>
        {{
          syncLoading
            ? t('dataOps.header.syncing')
            : t('dataOps.header.fullSync')
        }}
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  activeNav: { type: Object, default: null },
  canManageSync: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  preflightLoading: { type: Boolean, default: false },
  syncLoading: { type: Boolean, default: false }
})

const showSyncActions = computed(() =>
  ['sync', 'config'].includes(props.activeNav?.key)
)

defineEmits(['refresh', 'preflight', 'full-sync'])
</script>
