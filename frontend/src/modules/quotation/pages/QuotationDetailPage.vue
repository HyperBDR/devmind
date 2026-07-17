<script setup lang="ts">
/**
 * Thin router wrapper around QuotationDetails.
 * Prefer App.vue tab wiring for full feature parity.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuotationDetails from '../components/QuotationDetails.vue'
import { listQuotations, updateQuotation } from '../api/quotations'
import { isFeishuLinkOnlyUpdate } from '../utils/feishuLinkState'
import { useAuthStore } from '../stores/auth'
import type { Quotation } from '../types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const quote = ref<Quotation | null>(null)
const loading = ref(true)
const error = ref('')

const currentUser = computed(() => auth.currentUser || undefined)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const all = await listQuotations()
    quote.value = all.find((item) => item.id === String(route.params.id)) || null
    if (!quote.value) error.value = '未找到该报价单'
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    quote.value = null
  } finally {
    loading.value = false
  }
}

async function handleUpdateQuoteStatus(
  id: string,
  updatedFields: Partial<Quotation>,
  notes?: string,
) {
  if (!quote.value || quote.value.id !== id) return
  const previous = quote.value
  const next = { ...previous, ...updatedFields }
  const statusChanged = Boolean(
    updatedFields.status && updatedFields.status !== previous.status,
  )
  const isExcelGenerated =
    updatedFields.status === 'Generated' && previous.status === 'Draft'

  let computedNotes = notes || ''
  if (!computedNotes) {
    if (isExcelGenerated) {
      computedNotes = 'Generated Excel quotation'
    } else if (statusChanged && updatedFields.status) {
      computedNotes = `Updated status to ${updatedFields.status}`
    }
  }

  quote.value = next

  if (isFeishuLinkOnlyUpdate(updatedFields)) {
    return
  }

  try {
    quote.value = await updateQuotation(next, {
      notes: computedNotes || undefined,
    })
  } catch {
    quote.value = previous
  }
}

function handleBack() {
  void router.push('/quotations')
}

function handleEditQuote(id: string) {
  void router.push({ path: '/quotations/new', query: { edit: id } })
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div>
    <p v-if="error" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{{ error }}</p>
    <div
      v-if="loading"
      class="rounded-xl border border-slate-200 bg-white px-4 py-12 text-center text-slate-400"
    >
      加载中…
    </div>
    <QuotationDetails
      v-else-if="quote"
      :quote="quote"
      :current-user="currentUser"
      @back="handleBack"
      @update-quote-status="handleUpdateQuoteStatus"
      @edit-quote="handleEditQuote"
    />
  </div>
</template>
