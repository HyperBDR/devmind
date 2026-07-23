<template>
  <div class="border-b border-slate-200 bg-slate-950 text-white lg:hidden">
    <div class="flex items-center gap-3 px-4 py-4">
      <div
        class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-sm font-bold"
      >
        T
      </div>
      <div>
        <div class="text-sm font-bold">Tower</div>
        <p class="text-[10px] text-slate-400">
          {{ t('dataOps.brand.subtitle') }}
        </p>
      </div>
    </div>
    <nav class="px-4 pb-4" :aria-label="t('dataOps.nav.mobileLabel')">
      <label
        class="block text-xs font-semibold text-slate-300"
        for="data-ops-mobile-section"
      >
        {{ t('dataOps.nav.mobileLabel') }}
      </label>
      <select
        id="data-ops-mobile-section"
        class="mt-1 h-11 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm font-semibold text-white outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/30"
        :value="activeSection"
        @change="emit('select', $event.target.value)"
      >
        <optgroup
          v-for="group in resolvedNavGroups"
          :key="group.key"
          :label="group.label"
        >
          <option v-for="item in group.items" :key="item.key" :value="item.key">
            {{ item.label }}
          </option>
        </optgroup>
      </select>
    </nav>
  </div>

  <aside
    class="hidden w-60 shrink-0 bg-slate-950 text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col"
  >
    <div class="shrink-0 border-b border-slate-800 px-5 py-6">
      <div class="flex items-center gap-3">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-sm font-bold"
        >
          T
        </div>
        <div>
          <div class="text-sm font-bold">Tower</div>
          <p class="text-[10px] text-slate-400">
            {{ t('dataOps.brand.subtitle') }}
          </p>
        </div>
      </div>
    </div>

    <nav class="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-4">
      <div
        v-for="group in resolvedNavGroups"
        :key="group.key"
        class="space-y-1"
      >
        <p
          class="px-3 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
        >
          {{ group.label }}
        </p>
        <button
          v-for="item in group.items"
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
          <span class="flex h-4 w-4 items-center justify-center">
            <svg
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              viewBox="0 0 24 24"
            >
              <path :d="iconPath(item.key)" />
            </svg>
          </span>
          <span class="min-w-0 flex-1 truncate">
            {{ item.label }}
          </span>
        </button>
      </div>
    </nav>

    <div
      class="shrink-0 border-t border-slate-800 px-5 py-4 text-[10px] text-slate-500"
    >
      Tower v0.1.0
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  activeSection: { type: String, required: true },
  navGroups: { type: Array, default: () => [] },
  navItems: { type: Array, required: true }
})

const emit = defineEmits(['select'])

const resolvedNavGroups = computed(() => {
  if (props.navGroups.length) {
    return props.navGroups
  }
  return [
    {
      key: 'default',
      label: t('dataOps.nav.fallback'),
      items: props.navItems
    }
  ]
})

function iconPath(key) {
  const paths = {
    executive: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
    pipeline: 'M4 7h16 M4 12h10 M4 17h16',
    contracts: 'M6 3h9l3 3v15H6z M14 3v4h4 M8 12h8 M8 16h8',
    sales:
      'M12 3a9 9 0 100 18 9 9 0 000-18z M3 12h18 M12 3c2 3 2 15 0 18 M12 3c-2 3-2 15 0 18',
    observations: 'M4 5h16v14H4z M8 9h8 M8 13h5 M16 16l2 2 3-4',
    sync: 'M6 7h9a3 3 0 010 6H9a3 3 0 000 6h9 M6 7l3-3 M6 7l3 3 M18 17l-3-3 M18 17l-3 3',
    config:
      'M12 8a4 4 0 100 8 4 4 0 000-8z M12 2v3 M12 19v3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M2 12h3 M19 12h3 M4.9 19.1L7 17 M17 7l2.1-2.1'
  }
  return paths[key] || paths.executive
}
</script>
