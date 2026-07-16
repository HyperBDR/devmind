<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight, FolderOpen, Loader2, Users } from 'lucide-vue-next'
import type { FeishuDriveTreeNode } from '../api/feishu'

const props = defineProps<{
  node: FeishuDriveTreeNode
  section: 'my' | 'shared'
  depth?: number
  activeToken: string | null
  ancestors: FeishuDriveTreeNode[]
  expandedMap: Record<string, boolean>
  childrenMap: Record<string, FeishuDriveTreeNode[]>
  loadingMap: Record<string, boolean>
}>()

const emit = defineEmits<{
  toggle: [
    token: string,
    node: FeishuDriveTreeNode,
    section: 'my' | 'shared',
    ancestors: FeishuDriveTreeNode[],
  ]
  select: [
    node: FeishuDriveTreeNode,
    section: 'my' | 'shared',
    ancestors: FeishuDriveTreeNode[],
  ]
}>()

const depth = computed(() => props.depth ?? 0)
const expanded = computed(() => Boolean(props.expandedMap[props.node.token]))
const loading = computed(() => Boolean(props.loadingMap[props.node.token]))
const children = computed(
  () => props.childrenMap[props.node.token] || [],
)
const isActive = computed(() => props.activeToken === props.node.token)
const childAncestors = computed(() => [...props.ancestors, props.node])
</script>

<template>
  <div>
    <div
      class="flex w-full items-center gap-0.5 rounded-md text-left"
      :class="
        isActive
          ? 'bg-indigo-50 font-semibold text-indigo-700'
          : 'text-dm-text hover:bg-white'
      "
    >
      <button
        type="button"
        class="inline-flex h-7 w-5 shrink-0 items-center justify-center rounded text-dm-text-tertiary hover:text-dm-text"
        :aria-label="expanded ? 'Collapse' : 'Expand'"
        @click.stop="emit('toggle', node.token, node, section, ancestors)"
      >
        <Loader2 v-if="loading" class="h-3 w-3 animate-spin" />
        <ChevronRight
          v-else
          class="h-3.5 w-3.5 transition-transform"
          :class="expanded ? 'rotate-90' : ''"
        />
      </button>
      <button
        type="button"
        class="flex min-w-0 flex-1 items-center gap-1.5 py-1.5 pr-2 text-left"
        @click="emit('select', node, section, ancestors)"
      >
        <Users
          v-if="section === 'shared'"
          class="h-3.5 w-3.5 shrink-0 text-sky-600"
        />
        <FolderOpen
          v-else
          class="h-3.5 w-3.5 shrink-0 text-amber-500"
        />
        <span class="truncate text-[12px]">{{ node.name }}</span>
      </button>
    </div>
    <div
      v-if="expanded"
      class="ml-2 space-y-0.5 border-l border-dm-border-light pl-1"
    >
      <FeishuDriveNavNode
        v-for="child in children"
        :key="`${section}-${child.token}`"
        :node="child"
        :section="section"
        :depth="depth + 1"
        :active-token="activeToken"
        :ancestors="childAncestors"
        :expanded-map="expandedMap"
        :children-map="childrenMap"
        :loading-map="loadingMap"
        @toggle="(token, n, s, a) => emit('toggle', token, n, s, a)"
        @select="(n, s, a) => emit('select', n, s, a)"
      />
    </div>
  </div>
</template>
