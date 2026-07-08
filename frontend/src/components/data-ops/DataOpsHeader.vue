<template>
  <header
    class="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between"
  >
    <div>
      <h2 class="text-2xl font-bold text-slate-950">
        {{ activeNav?.label || '经营驾驶舱' }}
      </h2>
      <p class="mt-1 text-sm text-slate-500">
        {{ activeNav?.description }}
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        :disabled="loading"
        @click="$emit('refresh')"
      >
        刷新
      </button>
      <button
        v-if="canManageSync"
        type="button"
        class="h-9 rounded-lg bg-slate-950 px-3 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        :disabled="preflightLoading"
        @click="$emit('preflight')"
      >
        {{ preflightLoading ? '检查中' : '检查飞书权限' }}
      </button>
      <button
        v-if="canManageSync"
        type="button"
        class="h-9 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        :disabled="syncLoading"
        @click="$emit('full-sync')"
      >
        {{ syncLoading ? '提交中' : '全量同步' }}
      </button>
    </div>
  </header>
</template>

<script setup>
defineProps({
  activeNav: { type: Object, default: null },
  canManageSync: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  preflightLoading: { type: Boolean, default: false },
  syncLoading: { type: Boolean, default: false },
})

defineEmits(['refresh', 'preflight', 'full-sync'])
</script>
