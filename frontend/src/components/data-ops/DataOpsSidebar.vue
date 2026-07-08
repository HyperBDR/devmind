<template>
  <aside class="hidden w-60 shrink-0 bg-slate-950 text-white lg:flex lg:flex-col">
    <div class="border-b border-slate-800 px-5 py-6">
      <div class="flex items-center gap-3">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-sm font-bold"
        >
          D
        </div>
        <div>
          <h1 class="text-sm font-bold">Data Ops</h1>
          <p class="text-[10px] text-slate-400">数据运营控制台</p>
        </div>
      </div>
    </div>

    <nav class="flex-1 space-y-1 px-3 py-4">
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors"
        :class="
          activeSection === item.key
            ? 'bg-indigo-600 text-white'
            : 'text-slate-300 hover:bg-slate-800 hover:text-white'
        "
        @click="$emit('select', item.key)"
      >
        <span class="w-4 text-center text-[11px] font-bold">
          {{ item.icon }}
        </span>
        {{ item.label }}
      </button>
    </nav>

    <div class="border-t border-slate-800 px-5 py-4 text-[10px] text-slate-500">
      DevMind Data Ops
    </div>
  </aside>
</template>

<script setup>
defineProps({
  activeSection: { type: String, required: true },
  navItems: { type: Array, required: true },
})

defineEmits(['select'])
</script>
