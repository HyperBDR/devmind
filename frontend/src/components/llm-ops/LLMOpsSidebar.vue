<template>
  <aside
    :class="[
      'llm-ops-sidebar fixed bottom-0 left-0 top-16 z-20 hidden',
      'flex-col overflow-hidden text-white lg:flex',
      collapsed ? 'is-collapsed w-20' : 'w-72'
    ]"
  >
    <div class="llm-ops-sidebar-brand px-5 py-5">
      <div
        :class="[
          'flex gap-3',
          collapsed ? 'flex-col items-center' : 'items-start justify-between'
        ]"
      >
        <div :class="['min-w-0', collapsed ? 'text-center' : '']">
          <p
            class="text-[11px] font-bold uppercase tracking-[0.18em] text-agione-300"
          >
            {{ collapsed ? 'LLM' : 'LLM OPS' }}
          </p>
          <h1 v-if="!collapsed" class="mt-2 text-lg font-semibold">
            {{ t('llmOps.shell.title') }}
          </h1>
        </div>
        <button
          type="button"
          class="sidebar-toggle-button"
          :aria-expanded="!collapsed"
          :aria-label="toggleLabel"
          :title="toggleLabel"
          @click="$emit('toggle-sidebar')"
        >
          <svg
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path :d="collapsed ? 'M9 6l6 6-6 6' : 'M15 6l-6 6 6 6'" />
          </svg>
        </button>
      </div>
      <p v-if="!collapsed" class="mt-2 text-xs leading-5 text-slate-400">
        {{ t('llmOps.shell.subtitle') }}
      </p>
    </div>

    <nav
      :class="[
        'flex-1 overflow-y-auto py-4',
        collapsed ? 'space-y-3 px-2' : 'space-y-5 px-3'
      ]"
    >
      <section v-for="group in navGroups" :key="group.key">
        <button
          type="button"
          class="llm-nav-group-button flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm font-semibold"
          :class="{ 'is-expanded': isExpanded(group.key) }"
          :aria-expanded="!collapsed && isExpanded(group.key)"
          :title="collapsed ? group.label : ''"
          @click="$emit('toggle-group', group.key)"
        >
          <svg
            class="nav-icon"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path v-for="path in group.icon" :key="path" :d="path" />
          </svg>
          <span v-if="!collapsed" class="min-w-0 flex-1 truncate">
            {{ group.label }}
          </span>
          <svg
            v-if="!collapsed"
            class="nav-group-chevron"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>
        <div
          v-if="!collapsed && isExpanded(group.key)"
          class="nav-group-items mt-1 space-y-1"
        >
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            class="llm-nav-item flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm font-medium"
            :class="{ 'is-active': activeSection === item.key }"
            :title="collapsed ? item.label : ''"
            @click="$emit('select-item', group.key, item.key)"
          >
            <svg
              class="nav-icon"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              viewBox="0 0 24 24"
            >
              <path v-for="path in item.icon" :key="path" :d="path" />
            </svg>
            <span v-if="!collapsed" class="min-w-0 flex-1 truncate">
              {{ item.label }}
            </span>
          </button>
        </div>
      </section>
    </nav>
  </aside>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  activeSection: {
    type: String,
    required: true
  },
  collapsed: {
    type: Boolean,
    required: true
  },
  expandedGroupKeys: {
    type: Array,
    required: true
  },
  navGroups: {
    type: Array,
    required: true
  },
  toggleLabel: {
    type: String,
    required: true
  }
})

defineEmits(['select-item', 'toggle-group', 'toggle-sidebar'])

const { t } = useI18n()

function isExpanded(key) {
  return props.expandedGroupKeys.includes(key)
}
</script>
