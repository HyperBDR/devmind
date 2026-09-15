<script setup lang="ts">
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionChild,
  TransitionRoot,
} from '@headlessui/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'

import InvoiceDetail from './InvoiceDetail.vue'

const props = defineProps<{
  invoiceId: string | null
}>()
const emit = defineEmits<{
  close: []
}>()
const { t } = useI18n()
const closeButton = ref<HTMLButtonElement | null>(null)
const open = computed(() => Boolean(props.invoiceId))
let returnFocusElement: HTMLElement | null = null
let returnFocusTimer: number | undefined

function close() {
  emit('close')
}

watch(
  () => props.invoiceId,
  (invoiceId, previousInvoiceId) => {
    if (invoiceId) {
      window.clearTimeout(returnFocusTimer)
      if (!previousInvoiceId && document.activeElement instanceof HTMLElement) {
        returnFocusElement = document.activeElement
      }
      return
    }
    if (previousInvoiceId) {
      returnFocusTimer = window.setTimeout(() => {
        if (returnFocusElement?.isConnected) {
          returnFocusElement.focus({ preventScroll: true })
        }
        returnFocusElement = null
      }, 200)
    }
  },
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
                data-invoice-detail-drawer
              >
                <header
                  class="flex shrink-0 items-center justify-between gap-4 border-b border-dm-border bg-white px-4 py-3 sm:px-5"
                >
                  <div class="min-w-0">
                    <DialogTitle class="text-base font-semibold text-dm-text">
                      {{ t('quotation.sales.detail.drawerTitle') }}
                    </DialogTitle>
                    <p class="mt-0.5 text-xs text-dm-text-tertiary">
                      {{ t('quotation.sales.detail.drawerSubtitle') }}
                    </p>
                  </div>
                  <button
                    ref="closeButton"
                    type="button"
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-dm-text-tertiary transition hover:bg-slate-100 hover:text-dm-text focus:outline-hidden focus:ring-2 focus:ring-blue-200"
                    :aria-label="t('quotation.sales.detail.drawerClose')"
                    @click="close"
                  >
                    <X class="h-5 w-5" />
                  </button>
                </header>

                <div
                  class="invoice-drawer-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 sm:p-5"
                >
                  <InvoiceDetail
                    v-if="invoiceId"
                    :invoice-id="invoiceId"
                    embedded
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
.invoice-drawer-scroll {
  scrollbar-width: none;
}

.invoice-drawer-scroll::-webkit-scrollbar {
  display: none;
}
</style>
