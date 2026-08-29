<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  listPublicAttachments,
  type PublicAttachment,
} from '../api/publicAttachments'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  close: []
  confirm: [ids: string[]]
}>()
const items = ref<PublicAttachment[]>([])
const selected = ref<string[]>([])
const loading = ref(false)
const draggingId = ref<string | null>(null)
const dragHandleId = ref<string | null>(null)
const orderedItems = computed(() => [
  ...selected.value
    .map((id) => items.value.find((item) => item.id === id))
    .filter((item): item is PublicAttachment => Boolean(item)),
  ...items.value.filter((item) => !selected.value.includes(item.id)),
])

async function load() {
  loading.value = true
  try {
    items.value = (await listPublicAttachments()).filter(
      (item) => item.status === 'active',
    )
    selected.value = []
  } finally {
    loading.value = false
  }
}

function toggle(id: string) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id]
}

function prepareDragging(id: string) {
  dragHandleId.value = id
}

function startDragging(id: string, event: DragEvent) {
  if (dragHandleId.value !== id) {
    event.preventDefault()
    return
  }
  draggingId.value = id
  event.dataTransfer?.setData('text/plain', id)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    const row = event.currentTarget as HTMLElement
    event.dataTransfer.setDragImage(row, 24, row.offsetHeight / 2)
  }
}

function dropOn(id: string) {
  if (!draggingId.value || draggingId.value === id) return
  const from = selected.value.indexOf(draggingId.value)
  const to = selected.value.indexOf(id)
  if (from < 0 || to < 0) return
  const next = [...selected.value]
  next.splice(from, 1)
  next.splice(to, 0, draggingId.value)
  selected.value = next
  draggingId.value = null
}

function stopDragging() {
  draggingId.value = null
  dragHandleId.value = null
}

function confirm() {
  emit('confirm', selected.value)
}

watch(() => props.open, (open) => {
  if (open) void load()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
      <div class="w-full max-w-xl overflow-hidden rounded-xl bg-white shadow-2xl">
        <div class="flex items-start justify-between border-b border-dm-border-light px-5 py-4">
          <div><h2 class="text-lg font-bold text-dm-text">下载报价单</h2><p class="mt-1 text-sm text-dm-text-tertiary">选择需要一起下载的公共附件</p></div>
          <button type="button" class="text-xl text-dm-text-tertiary" @click="emit('close')">×</button>
        </div>
        <div class="space-y-3 p-5">
          <div class="rounded-lg border border-dm-border-light px-4 py-3 text-sm font-semibold">报价单 PDF</div>
          <p class="text-xs font-bold uppercase tracking-wide text-dm-text-tertiary">公共附件</p>
          <div v-if="loading" class="py-5 text-sm text-dm-text-tertiary">加载中…</div>
          <div v-else class="divide-y rounded-lg border border-dm-border-light">
            <div
              v-for="item in orderedItems"
              :key="item.id"
              :data-attachment-row="item.id"
              :draggable="selected.includes(item.id)"
              class="flex items-center gap-3 px-4 py-3 transition"
              :class="draggingId === item.id ? 'opacity-40' : 'hover:bg-slate-50'"
              @dragstart="startDragging(item.id, $event)"
              @dragend="stopDragging"
              @dragover.prevent
              @drop="dropOn(item.id)"
            >
              <span
                v-if="selected.includes(item.id)"
                class="cursor-grab select-none text-lg leading-none text-dm-text-tertiary active:cursor-grabbing"
                aria-label="拖动调整附件顺序"
                title="拖动调整顺序"
                @pointerdown.stop="prepareDragging(item.id)"
                @pointerup="dragHandleId = null"
              >⋮⋮</span>
              <span v-else class="w-4 shrink-0" aria-hidden="true" />
              <input type="checkbox" class="h-5 w-5 shrink-0 cursor-pointer accent-blue-600" :aria-label="`${item.file_name} ${selected.includes(item.id) ? '已选择' : '未选择'}`" :checked="selected.includes(item.id)" @change="toggle(item.id)" />
              <span class="min-w-0 flex-1"><b class="block truncate text-sm text-dm-text">{{ item.file_name }}</b><small class="text-xs text-dm-text-tertiary">{{ item.scope }}</small></span>
              <span class="text-xs font-semibold" :class="selected.includes(item.id) ? 'text-emerald-600' : 'text-dm-text-tertiary'">{{ selected.includes(item.id) ? '已选择' : '未选择' }}</span>
            </div>
            <div v-if="!items.length" class="px-4 py-5 text-sm text-dm-text-tertiary">暂无可用公共附件</div>
          </div>
        </div>
        <div class="flex items-center justify-end gap-2 border-t border-dm-border-light bg-slate-50 px-5 py-4"><button type="button" class="rounded-md border border-dm-border bg-white px-4 py-2 text-sm font-semibold" @click="emit('close')">取消</button><button type="button" class="dm-btn-primary px-4 py-2 text-sm font-semibold" @click="confirm">{{ selected.length ? '合并并下载' : '直接下载' }}</button></div>
      </div>
    </div>
  </Teleport>
</template>
