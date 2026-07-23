<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listQuotations, updateQuotation, deleteQuotation } from '../api/quotations'
import ImportedDocumentsPage from '../components/ImportedDocumentsPage.vue'
import QuotationList from '../components/QuotationList.vue'
import { isFeishuLinkOnlyUpdate, reconcileFeishuQuotationLinks } from '../utils/feishuLinkState'
import { useAuthStore } from '../stores/auth'
import type { Quotation } from '../types'

const router = useRouter()
const auth = useAuthStore()

const quotations = ref<Quotation[]>([])
const loading = ref(false)
const toast = ref<{ message: string; type: string } | null>(null)
let toastTimer: number | undefined

const currentUser = computed(() => {
  if (!auth.user) return undefined
  return {
    name: auth.user.name,
    title: auth.user.title || '',
    email: auth.user.email,
    role: auth.user.role,
  }
})

function showToast(message: string, type: 'success' | 'info' | 'error' = 'info') {
  toast.value = { message, type }
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
  }, 4000)
}

async function load() {
  loading.value = true
  try {
    quotations.value = await listQuotations()
    const staleLinks = await reconcileFeishuQuotationLinks(quotations.value)
    if (staleLinks) {
      quotations.value = await listQuotations()
    }
  } catch (err: unknown) {
    showToast(err instanceof Error ? err.message : '加载报价单失败', 'error')
    quotations.value = []
  } finally {
    loading.value = false
  }
}

async function handleFeishuUploadDone(_id: string) {
  await load()
}

onMounted(() => {
  void load()

  const params = new URLSearchParams(window.location.search)
  if (params.get('feishu') === 'connected') {
    showToast('飞书账号已连接，可在报价查询中心使用云盘功能', 'success')
    params.delete('feishu')
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}${window.location.hash}`
    window.history.replaceState({}, '', next)
  }
})

function handleViewQuote(id: string) {
  void router.push(`/quotations/${id}`)
}

function handleEditQuote(id: string) {
  void router.push({ path: '/quotations/new', query: { edit: id } })
}

async function handleDeleteQuote(id: string) {
  const previous = quotations.value
  quotations.value = quotations.value.filter((q) => q.id !== id)
  try {
    await deleteQuotation(id)
    showToast('报价单已安全从系统抹除！', 'info')
  } catch (err: unknown) {
    quotations.value = previous
    showToast(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

async function handleReconcileFeishuLinks() {
  const staleLinks = await reconcileFeishuQuotationLinks(quotations.value)
  if (staleLinks) {
    quotations.value = await listQuotations()
  }
}

function handleUpdateQuoteStatus(
  id: string,
  updatedFields: Partial<Quotation>,
  notes?: string,
) {
  const previous = quotations.value.find((q) => q.id === id)
  if (!previous) return

  const nextQuote = { ...previous, ...updatedFields }
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

  quotations.value = quotations.value.map((q) =>
    q.id === id ? nextQuote : q,
  )

  if (isFeishuLinkOnlyUpdate(updatedFields)) {
    return
  }

  void updateQuotation(nextQuote, { notes: computedNotes || undefined })
    .then((saved) => {
      quotations.value = quotations.value.map((q) =>
        q.id === id ? saved : q,
      )
    })
    .catch(() => {
      quotations.value = quotations.value.map((q) =>
        q.id === id ? previous : q,
      )
    })

  if (updatedFields.status) {
    switch (updatedFields.status) {
      case 'Sent':
        showToast('报价单已成功标记为「已发送客户」！', 'success')
        break
      case 'Accepted':
        showToast('🎉 恭喜！该报价方案已确定成交，已更新统计绩效！', 'success')
        break
      case 'Rejected':
        showToast('该报价方案已标记为「已拒绝/失败」。销售团队将总结经验！', 'info')
        break
      case 'Expired':
        showToast('该报价方案已标记为「已过期」。', 'info')
        break
      case 'Cancelled':
        showToast(
          notes ? `该报价方案已作废！原因：${notes}` : '该报价方案已标记为「已作废/废弃」。',
          'info',
        )
        break
      default:
        break
    }
  }
}
</script>

<template>
  <div>
    <div
      v-if="toast"
      class="fixed right-6 top-6 z-50 rounded-lg px-4 py-2 text-sm font-medium shadow-lg"
      :class="{
        'bg-emerald-600 text-white': toast.type === 'success',
        'bg-slate-800 text-white': toast.type === 'info',
        'bg-red-600 text-white': toast.type === 'error',
      }"
    >
      {{ toast.message }}
    </div>

    <div class="space-y-5">
      <div v-if="loading && !quotations.length" class="py-16 text-center text-sm text-slate-400">
        正在加载报价单…
      </div>

      <QuotationList
        v-else
        :quotations="quotations"
        :current-user="currentUser"
        @view-quote="handleViewQuote"
        @delete-quote="handleDeleteQuote"
        @update-quote-status="handleUpdateQuoteStatus"
        @feishu-upload-done="handleFeishuUploadDone"
        @reconcile-feishu-links="handleReconcileFeishuLinks"
        @edit-quote="handleEditQuote"
        @toast="showToast"
      />

      <ImportedDocumentsPage
        embedded
        @toast="showToast"
      />
    </div>
  </div>
</template>
