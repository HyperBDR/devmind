<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  LoaderCircle,
  MessageSquareText,
  Pencil,
  Send,
  Trash2,
  X
} from 'lucide-vue-next'

import {
  createQuotationNote,
  deleteQuotationNote,
  listQuotationNotes,
  updateQuotationNote,
  type QuotationNote
} from '../api/notes'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import type { Quotation } from '../types'

const props = withDefaults(
  defineProps<{
    quotation: Quotation | null
    displayMode?: 'trigger' | 'panel'
    guideUserKey?: string
  }>(),
  { displayMode: 'trigger', guideUserKey: 'default' }
)

const { locale, t } = useQuotationI18n()
const root = ref<HTMLElement | null>(null)
const open = ref(false)
const panelVisible = ref(true)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const draft = ref('')
const notes = ref<QuotationNote[]>([])
const editingId = ref<string | null>(null)
const editingContent = ref('')
const triggerGuideVisible = ref(false)
const floatingPosition = ref({ left: 0, top: 96 })
const viewport = ref({ width: 0, height: 0 })
let requestId = 0
let dragStart: { x: number; y: number; left: number; top: number } | null = null
let dragHandle: HTMLElement | null = null
let dragPointerId: number | null = null
let dragged = false

const TRIGGER_POSITION_STORAGE_KEY = 'quotation-notes-trigger-position'
const PANEL_POSITION_STORAGE_KEY = 'quotation-notes-panel-position'
const TRIGGER_GUIDE_VERSION = 'quotation-notes-trigger-guide-v1'
const VIEWPORT_MARGIN = 12

const enabled = computed(() => Boolean(props.quotation?.id))
const panelMode = computed(() => props.displayMode === 'panel')
const positionStorageKey = computed(() =>
  panelMode.value ? PANEL_POSITION_STORAGE_KEY : TRIGGER_POSITION_STORAGE_KEY
)
const triggerGuideStorageKey = computed(
  () => `${TRIGGER_GUIDE_VERSION}:${props.guideUserKey}`
)
const floatingStyle = computed(() => ({
  left: `${floatingPosition.value.left}px`,
  top: `${floatingPosition.value.top}px`
}))
const popoverOpensLeft = computed(
  () => floatingPosition.value.left > Math.min(430, viewport.value.width - 32)
)
const popoverOpensUp = computed(
  () => floatingPosition.value.top > viewport.value.height / 2
)

function clampPosition(left: number, top: number) {
  const width = root.value?.offsetWidth || 96
  const height = root.value?.offsetHeight || 36
  return {
    left: Math.max(
      VIEWPORT_MARGIN,
      Math.min(left, window.innerWidth - width - VIEWPORT_MARGIN)
    ),
    top: Math.max(
      VIEWPORT_MARGIN,
      Math.min(top, window.innerHeight - height - VIEWPORT_MARGIN)
    )
  }
}

function updateViewport() {
  viewport.value = {
    width: window.innerWidth,
    height: window.innerHeight
  }
  floatingPosition.value = clampPosition(
    floatingPosition.value.left,
    floatingPosition.value.top
  )
}

function savePosition() {
  window.localStorage.setItem(
    positionStorageKey.value,
    JSON.stringify(floatingPosition.value)
  )
}

function handleDragMove(event: PointerEvent) {
  if (!dragStart) return
  const deltaX = event.clientX - dragStart.x
  const deltaY = event.clientY - dragStart.y
  if (!dragged && Math.hypot(deltaX, deltaY) < 4) return
  dragged = true
  event.preventDefault()
  floatingPosition.value = clampPosition(
    dragStart.left + deltaX,
    dragStart.top + deltaY
  )
}

function stopDragging() {
  if (dragged) savePosition()
  if (
    dragHandle &&
    dragPointerId !== null &&
    dragHandle.hasPointerCapture(dragPointerId)
  ) {
    dragHandle.releasePointerCapture(dragPointerId)
  }
  dragStart = null
  dragHandle = null
  dragPointerId = null
  window.removeEventListener('pointermove', handleDragMove)
  window.removeEventListener('pointerup', stopDragging)
  window.removeEventListener('pointercancel', stopDragging)
}

function startDragging(event: PointerEvent) {
  if (event.button !== 0) return
  dragHandle = event.currentTarget as HTMLElement
  dragPointerId = event.pointerId
  dragHandle.setPointerCapture(event.pointerId)
  dragStart = {
    x: event.clientX,
    y: event.clientY,
    left: floatingPosition.value.left,
    top: floatingPosition.value.top
  }
  dragged = false
  window.addEventListener('pointermove', handleDragMove, { passive: false })
  window.addEventListener('pointerup', stopDragging)
  window.addEventListener('pointercancel', stopDragging)
}

function handleRootClick(event: MouseEvent) {
  if (!dragged) return
  event.preventDefault()
  event.stopPropagation()
  dragged = false
}

function initials(note: QuotationNote): string {
  const value = note.authorName || note.authorEmail
  return value
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const dateLocale = locale.value.startsWith('en') ? 'en-US' : 'zh-CN'
  return new Intl.DateTimeFormat(dateLocale, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

function isEdited(note: QuotationNote): boolean {
  const createdAt = new Date(note.createdAt).getTime()
  const updatedAt = new Date(note.updatedAt).getTime()
  return updatedAt - createdAt > 1000
}

async function loadNotes() {
  const quotationId = props.quotation?.id
  const currentRequest = ++requestId
  notes.value = []
  if (!quotationId) {
    return
  }
  loading.value = true
  error.value = ''
  try {
    const result = await listQuotationNotes(quotationId)
    if (currentRequest === requestId) notes.value = result
  } catch (err) {
    if (currentRequest === requestId) {
      error.value =
        err instanceof Error
          ? err.message
          : t('quotation.pages.create.notesLoadFailed')
    }
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}

function toggle() {
  if (dragged) {
    dragged = false
    return
  }
  dismissTriggerGuide()
  open.value = !open.value
}

function close() {
  if (panelMode.value) {
    panelVisible.value = false
    return
  }
  open.value = false
  editingId.value = null
}

function dismissTriggerGuide() {
  if (!triggerGuideVisible.value) return
  triggerGuideVisible.value = false
  try {
    window.localStorage.setItem(triggerGuideStorageKey.value, 'seen')
  } catch {
    // Ignore storage failures; the guide may show again on the next visit.
  }
}

async function submitNote() {
  const quotationId = props.quotation?.id
  const content = draft.value.trim()
  if (!quotationId || !content || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const note = await createQuotationNote(quotationId, content)
    notes.value.unshift(note)
    draft.value = ''
  } catch (err) {
    error.value =
      err instanceof Error
        ? err.message
        : t('quotation.pages.create.notesSaveFailed')
  } finally {
    saving.value = false
  }
}

function startEdit(note: QuotationNote) {
  editingId.value = note.id
  editingContent.value = note.content
}

async function saveEdit(note: QuotationNote) {
  const quotationId = props.quotation?.id
  const content = editingContent.value.trim()
  if (!quotationId || !content || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const updated = await updateQuotationNote(quotationId, note.id, content)
    notes.value = notes.value.map((item) =>
      item.id === updated.id ? updated : item
    )
    editingId.value = null
  } catch (err) {
    error.value =
      err instanceof Error
        ? err.message
        : t('quotation.pages.create.notesSaveFailed')
  } finally {
    saving.value = false
  }
}

async function removeNote(note: QuotationNote) {
  const quotationId = props.quotation?.id
  if (!quotationId || saving.value) return
  if (!window.confirm(t('quotation.pages.create.notesDeleteConfirm'))) return
  saving.value = true
  error.value = ''
  try {
    await deleteQuotationNote(quotationId, note.id)
    notes.value = notes.value.filter((item) => item.id !== note.id)
  } catch (err) {
    error.value =
      err instanceof Error
        ? err.message
        : t('quotation.pages.create.notesDeleteFailed')
  } finally {
    saving.value = false
  }
}

function handleDocumentClick(event: MouseEvent) {
  if (
    !panelMode.value &&
    open.value &&
    !root.value?.contains(event.target as Node)
  ) {
    close()
  }
}

function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void submitNote()
  }
}

watch(
  () => props.quotation?.id,
  () => {
    requestId += 1
    open.value = false
    panelVisible.value = true
    editingId.value = null
    draft.value = ''
    void loadNotes()
  },
  { immediate: true }
)

onMounted(() => {
  viewport.value = { width: window.innerWidth, height: window.innerHeight }
  const drawerLeft = Math.max(0, window.innerWidth - 1120)
  const defaultLeft = panelMode.value
    ? Math.max(
        VIEWPORT_MARGIN,
        drawerLeft - (root.value?.offsetWidth || 340) - 12
      )
    : window.innerWidth - (root.value?.offsetWidth || 96) - 24
  const defaultTop = panelMode.value ? 76 : 96
  let storedPosition: { left?: number; top?: number } = {}
  try {
    storedPosition = JSON.parse(
      window.localStorage.getItem(positionStorageKey.value) || '{}'
    )
  } catch {
    storedPosition = {}
  }
  floatingPosition.value = clampPosition(
    Number.isFinite(storedPosition.left) ? storedPosition.left! : defaultLeft,
    Number.isFinite(storedPosition.top) ? storedPosition.top! : defaultTop
  )
  if (!panelMode.value) {
    try {
      triggerGuideVisible.value =
        window.localStorage.getItem(triggerGuideStorageKey.value) !== 'seen'
    } catch {
      triggerGuideVisible.value = true
    }
  }
  document.addEventListener('pointerdown', handleDocumentClick)
  window.addEventListener('resize', updateViewport)
})
onBeforeUnmount(() => {
  requestId += 1
  stopDragging()
  document.removeEventListener('pointerdown', handleDocumentClick)
  window.removeEventListener('resize', updateViewport)
})
</script>

<template>
  <div
    ref="root"
    class="fixed inline-flex"
    :class="panelMode ? 'z-[80] w-[min(340px,calc(100vw-2rem))]' : 'z-[60]'"
    :style="floatingStyle"
    @click.capture="handleRootClick"
  >
    <button
      v-if="!panelMode"
      type="button"
      class="inline-flex h-9 touch-none cursor-grab select-none items-center gap-1.5 rounded-lg border bg-white px-3 text-xs font-semibold shadow-xs transition hover:border-blue-300 hover:text-dm-primary active:cursor-grabbing"
      :class="
        triggerGuideVisible
          ? 'border-blue-400 text-dm-primary ring-4 ring-blue-100'
          : 'border-dm-border text-dm-text-secondary'
      "
      :title="
        enabled
          ? t('quotation.pages.create.notesOpen')
          : t('quotation.pages.create.notesSaveFirst')
      "
      :aria-expanded="open"
      @pointerdown="startDragging"
      @click="toggle"
    >
      <MessageSquareText class="h-4 w-4" />
      {{ t('quotation.pages.create.notesButton') }}
      <span
        v-if="enabled"
        class="inline-flex min-w-5 items-center justify-center rounded-full bg-dm-primary px-1.5 py-0.5 text-[10px] leading-none text-white"
      >
        {{ notes.length }}
      </span>
    </button>

    <aside
      v-if="!panelMode && triggerGuideVisible"
      class="absolute right-0 top-[calc(100%+12px)] w-[min(300px,calc(100vw-2rem))] rounded-xl border border-blue-200 bg-white p-3.5 text-left shadow-2xl"
      role="status"
      data-testid="quotation-notes-trigger-guide"
    >
      <span
        class="absolute -top-1.5 right-7 h-3 w-3 rotate-45 border-l border-t border-blue-200 bg-white"
        aria-hidden="true"
      />
      <p class="text-sm font-bold text-dm-text">
        {{ t('quotation.pages.create.notesTriggerGuideTitle') }}
      </p>
      <p class="mt-1.5 text-xs leading-5 text-dm-text-secondary">
        {{
          t(
            enabled
              ? 'quotation.pages.create.notesTriggerGuideDescription'
              : 'quotation.pages.create.notesTriggerGuideSaveFirst'
          )
        }}
      </p>
      <button
        type="button"
        class="mt-3 inline-flex items-center rounded-md bg-dm-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-dm-primary-hover focus:outline-hidden focus:ring-2 focus:ring-blue-300"
        @click.stop="dismissTriggerGuide"
      >
        {{ t('quotation.pages.create.notesGuideDismiss') }}
      </button>
    </aside>

    <section
      v-if="panelMode ? panelVisible : open"
      class="z-50 flex flex-col overflow-hidden rounded-xl border border-dm-border bg-white text-left shadow-2xl"
      :class="
        panelMode
          ? 'relative h-[calc(100vh-88px)] w-full'
          : [
              'absolute max-h-[calc(100vh-8rem)] w-[min(430px,calc(100vw-2rem))]',
              popoverOpensLeft ? 'right-0' : 'left-0',
              popoverOpensUp
                ? 'bottom-[calc(100%+10px)]'
                : 'top-[calc(100%+10px)]'
            ]
      "
      data-testid="quotation-notes-popover"
    >
      <template v-if="quotation">
        <div
          class="flex items-start justify-between gap-3 border-b border-dm-border px-4 py-3.5"
          :class="panelMode ? 'touch-none cursor-grab select-none' : ''"
          @pointerdown="panelMode && startDragging($event)"
        >
          <div class="min-w-0">
            <h3 class="truncate text-sm font-bold text-dm-text">
              {{
                t('quotation.pages.create.notesTitle', {
                  quoteNo: quotation.quoteNo
                })
              }}
            </h3>
            <p class="mt-1 truncate text-xs text-dm-text-secondary">
              {{
                quotation.projectName ||
                t('quotation.pages.create.notesNoProject')
              }}
            </p>
            <p class="truncate text-[11px] text-dm-text-tertiary">
              {{
                quotation.clientCompany ||
                t('quotation.pages.create.notesNoCustomer')
              }}
            </p>
          </div>
          <button
            type="button"
            class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-dm-text-tertiary hover:bg-slate-100 hover:text-dm-text"
            :aria-label="t('quotation.pages.create.notesClose')"
            @pointerdown.stop
            @click.stop="close"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <div
          class="border-b border-dm-border bg-blue-50/70 px-4 py-2 text-[11px] text-blue-700"
        >
          {{ t('quotation.pages.create.notesVisibility') }}
        </div>

        <div class="min-h-32 flex-1 overflow-y-auto px-4">
          <div
            v-if="loading"
            class="flex min-h-32 items-center justify-center gap-2 text-xs text-dm-text-tertiary"
          >
            <LoaderCircle class="h-4 w-4 animate-spin" />
            {{ t('quotation.pages.create.notesLoading') }}
          </div>
          <div
            v-else-if="!notes.length"
            class="flex min-h-32 flex-col items-center justify-center text-center"
          >
            <MessageSquareText class="mb-2 h-6 w-6 text-slate-300" />
            <p class="text-xs font-medium text-dm-text-secondary">
              {{ t('quotation.pages.create.notesEmpty') }}
            </p>
            <p class="mt-1 text-[11px] text-dm-text-tertiary">
              {{ t('quotation.pages.create.notesEmptyHint') }}
            </p>
          </div>
          <article
            v-for="note in notes"
            v-else
            :key="note.id"
            class="flex gap-2.5 border-b border-slate-100 py-3 last:border-0"
          >
            <span
              class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-dm-primary text-[10px] font-bold text-white"
            >
              {{ initials(note) }}
            </span>
            <div class="min-w-0 flex-1">
              <div
                class="flex flex-wrap items-center gap-x-2 text-[11px] text-dm-text-tertiary"
              >
                <strong class="text-xs text-dm-text-secondary">
                  {{ note.authorName }}
                </strong>
                <span>{{ formatTime(note.createdAt) }}</span>
                <span v-if="isEdited(note)">
                  {{ t('quotation.pages.create.notesEdited') }}
                </span>
              </div>
              <template v-if="editingId === note.id">
                <textarea
                  v-model="editingContent"
                  maxlength="4000"
                  class="mt-2 h-20 w-full resize-none rounded-lg border border-dm-border px-2.5 py-2 text-xs text-dm-text focus:border-blue-400 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
                />
                <div class="mt-2 flex justify-end gap-2">
                  <button
                    type="button"
                    class="rounded-md px-2.5 py-1.5 text-[11px] text-dm-text-secondary hover:bg-slate-100"
                    @click="editingId = null"
                  >
                    {{ t('quotation.pages.create.notesCancel') }}
                  </button>
                  <button
                    type="button"
                    class="rounded-md bg-dm-primary px-2.5 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50"
                    :disabled="!editingContent.trim() || saving"
                    @click="saveEdit(note)"
                  >
                    {{ t('quotation.pages.create.notesSave') }}
                  </button>
                </div>
              </template>
              <template v-else>
                <p
                  class="mt-1 whitespace-pre-wrap break-words text-xs leading-5 text-dm-text-secondary"
                >
                  {{ note.content }}
                </p>
                <div v-if="note.canEdit" class="mt-1.5 flex gap-1">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-dm-text-tertiary hover:bg-slate-100 hover:text-dm-text"
                    @click="startEdit(note)"
                  >
                    <Pencil class="h-3 w-3" />
                    {{ t('quotation.pages.create.notesEdit') }}
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-dm-text-tertiary hover:bg-rose-50 hover:text-rose-600"
                    @click="removeNote(note)"
                  >
                    <Trash2 class="h-3 w-3" />
                    {{ t('quotation.pages.create.notesDelete') }}
                  </button>
                </div>
              </template>
            </div>
          </article>
        </div>

        <p
          v-if="error"
          class="border-t border-rose-100 bg-rose-50 px-4 py-2 text-[11px] text-rose-700"
        >
          {{ error }}
        </p>
        <div class="border-t border-dm-border bg-slate-50 px-4 py-3">
          <textarea
            v-model="draft"
            maxlength="4000"
            class="h-16 w-full resize-none rounded-lg border border-dm-border bg-white px-3 py-2 text-xs text-dm-text placeholder:text-dm-text-tertiary focus:border-blue-400 focus:outline-hidden focus:ring-2 focus:ring-blue-100"
            :placeholder="t('quotation.pages.create.notesPlaceholder')"
            @keydown="handleComposerKeydown"
          />
          <div class="mt-2 flex items-center justify-between gap-3">
            <span class="text-[10px] text-dm-text-tertiary">
              {{ t('quotation.pages.create.notesExportHint') }}
            </span>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg bg-dm-primary px-3 py-2 text-xs font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!draft.trim() || saving"
              @click="submitNote"
            >
              <LoaderCircle v-if="saving" class="h-3.5 w-3.5 animate-spin" />
              <Send v-else class="h-3.5 w-3.5" />
              {{ t('quotation.pages.create.notesSubmit') }}
            </button>
          </div>
        </div>
      </template>

      <div
        v-else
        class="flex min-h-40 flex-col items-center justify-center px-6 py-8 text-center"
      >
        <MessageSquareText class="mb-3 h-8 w-8 text-slate-300" />
        <h3 class="text-sm font-semibold text-dm-text">
          {{ t('quotation.pages.create.notesUnsavedTitle') }}
        </h3>
        <p class="mt-1.5 text-xs leading-5 text-dm-text-secondary">
          {{ t('quotation.pages.create.notesUnsavedHint') }}
        </p>
      </div>
    </section>
  </div>
</template>
