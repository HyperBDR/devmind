<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionChild,
  TransitionRoot
} from '@headlessui/vue'
import { LoaderCircle, RefreshCw, X } from 'lucide-vue-next'
import { getQuotation } from '../api/quotations'
import type { Quotation } from '../types'
import type { PreviewUser } from '../utils/quotationPreviewModel'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import QuotationDetails from './QuotationDetails.vue'
import QuotationNotesPopover from './QuotationNotesPopover.vue'

const props = defineProps<{
  quoteId: string | null
  currentUser?: PreviewUser
}>()

const emit = defineEmits<{
  close: []
  editQuote: [id: string]
  updateQuoteStatus: [
    id: string,
    updatedFields: Partial<Quotation>,
    notes?: string
  ]
}>()

const { t } = useQuotationI18n()
const quote = ref<Quotation | null>(null)
const loading = ref(false)
const error = ref('')
const closeButton = ref<HTMLButtonElement | null>(null)
let detailRequestId = 0
let returnFocusElement: HTMLElement | null = null
let returnFocusTimer: number | undefined

const open = computed(() => Boolean(props.quoteId))
const drawerSubtitle = computed(() => {
  if (!quote.value) {
    return t('quotation.pages.list.drawerLoading')
  }
  return t(
    quote.value.sourceType === 'document_import'
      ? 'quotation.pages.list.drawerSubtitleImported'
      : 'quotation.pages.list.drawerSubtitleLocal'
  )
})

async function loadQuote() {
  const quoteId = props.quoteId
  if (!quoteId) return

  const requestId = ++detailRequestId
  loading.value = true
  error.value = ''
  quote.value = null
  try {
    const result = await getQuotation(quoteId)
    if (requestId === detailRequestId) {
      quote.value = result
    }
  } catch (err: unknown) {
    if (requestId === detailRequestId) {
      error.value =
        err instanceof Error
          ? err.message
          : t('quotation.pages.list.drawerLoadFailed')
    }
  } finally {
    if (requestId === detailRequestId) {
      loading.value = false
    }
  }
}

function close() {
  detailRequestId += 1
  emit('close')
}

function handleEditQuote(id: string) {
  emit('editQuote', id)
  close()
}

function handleUpdateQuoteStatus(
  id: string,
  updatedFields: Partial<Quotation>,
  notes?: string
) {
  if (quote.value?.id === id) {
    quote.value = { ...quote.value, ...updatedFields }
  }
  emit('updateQuoteStatus', id, updatedFields, notes)
}

watch(
  () => props.quoteId,
  (quoteId, previousQuoteId) => {
    if (quoteId) {
      window.clearTimeout(returnFocusTimer)
      if (!previousQuoteId && document.activeElement instanceof HTMLElement) {
        returnFocusElement = document.activeElement
      }
      void loadQuote()
      return
    }
    detailRequestId += 1
    quote.value = null
    error.value = ''
    loading.value = false
    if (previousQuoteId) {
      returnFocusTimer = window.setTimeout(() => {
        if (returnFocusElement?.isConnected) {
          returnFocusElement.focus({ preventScroll: true })
        }
        returnFocusElement = null
      }, 200)
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  window.clearTimeout(returnFocusTimer)
})
</script>

<template>
  <TransitionRoot as="template" :show="open">
    <Dialog
      as="div"
      class="relative z-[70]"
      :initial-focus="closeButton"
      @close="close"
    >
      <TransitionChild
        as="template"
        enter="ease-out duration-200"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-150"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-slate-950/35" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-hidden">
        <div class="absolute inset-0 overflow-hidden">
          <div
            class="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-2 sm:pl-8"
          >
            <TransitionChild
              as="template"
              enter="transform transition ease-out duration-200"
              enter-from="translate-x-full"
              enter-to="translate-x-0"
              leave="transform transition ease-in duration-150"
              leave-from="translate-x-0"
              leave-to="translate-x-full"
            >
              <DialogPanel
                class="pointer-events-auto flex h-full w-screen max-w-[1120px] flex-col bg-slate-50 shadow-2xl"
                data-quotation-detail-drawer
              >
                <QuotationNotesPopover
                  v-if="quote"
                  :quotation="quote"
                  display-mode="panel"
                />

                <header
                  class="flex shrink-0 items-center justify-between gap-4 border-b border-dm-border bg-white px-4 py-3 sm:px-5"
                >
                  <div class="min-w-0">
                    <DialogTitle
                      class="truncate text-base font-semibold text-dm-text"
                    >
                      {{
                        quote?.quoteNo || t('quotation.pages.list.drawerTitle')
                      }}
                    </DialogTitle>
                    <p class="mt-0.5 text-xs text-dm-text-tertiary">
                      {{ drawerSubtitle }}
                    </p>
                  </div>
                  <button
                    ref="closeButton"
                    type="button"
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-dm-text-tertiary transition hover:bg-slate-100 hover:text-dm-text focus:outline-hidden focus:ring-2 focus:ring-blue-200"
                    :aria-label="t('quotation.pages.list.drawerClose')"
                    @click="close"
                  >
                    <X class="h-5 w-5" />
                  </button>
                </header>

                <div
                  class="quotation-drawer-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 sm:p-5"
                  data-quotation-drawer-scroll
                >
                  <div
                    v-if="loading"
                    class="flex min-h-64 items-center justify-center gap-2 rounded-xl border border-dm-border bg-white text-sm text-dm-text-tertiary"
                    role="status"
                  >
                    <LoaderCircle class="h-5 w-5 animate-spin" />
                    {{ t('quotation.pages.list.drawerLoading') }}
                  </div>

                  <div
                    v-else-if="error"
                    class="flex min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-white px-5 text-center"
                    role="alert"
                  >
                    <p class="max-w-lg text-sm font-medium text-rose-700">
                      {{ error }}
                    </p>
                    <button
                      type="button"
                      class="inline-flex items-center gap-1.5 rounded-lg border border-dm-border bg-white px-3 py-2 text-sm font-semibold text-dm-text transition hover:bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-blue-200"
                      @click="loadQuote"
                    >
                      <RefreshCw class="h-4 w-4" />
                      {{ t('quotation.pages.list.drawerRetry') }}
                    </button>
                  </div>

                  <QuotationDetails
                    v-else-if="quote"
                    embedded
                    :quote="quote"
                    :current-user="currentUser"
                    @back="close"
                    @edit-quote="handleEditQuote"
                    @update-quote-status="handleUpdateQuoteStatus"
                  />
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<style scoped>
.quotation-drawer-scroll {
  scrollbar-width: none;
}

.quotation-drawer-scroll::-webkit-scrollbar {
  display: none;
}
</style>
