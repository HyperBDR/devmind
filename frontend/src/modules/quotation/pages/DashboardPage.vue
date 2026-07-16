<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listQuotations } from '../api/quotations'
import { listImportedFeishuDocuments } from '../api/documents'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const quoteCount = ref(0)
const importCount = ref(0)
const loading = ref(true)

onMounted(async () => {
  loading.value = true
  try {
    const [quotes, docs] = await Promise.all([
      listQuotations(),
      listImportedFeishuDocuments().catch(() => []),
    ])
    quoteCount.value = quotes.length
    importCount.value = docs.length
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-slate-900">工作台</h1>
      <p class="mt-1 text-sm text-slate-500">
        欢迎，{{ auth.displayName || '用户' }}。从下方入口快速进入常用功能。
      </p>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">报价单</div>
        <div class="mt-2 text-3xl font-semibold text-slate-900">
          {{ loading ? '…' : quoteCount }}
        </div>
        <RouterLink
          to="/quotations"
          class="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          查看全部 →
        </RouterLink>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">导入资料</div>
        <div class="mt-2 text-3xl font-semibold text-slate-900">
          {{ loading ? '…' : importCount }}
        </div>
        <RouterLink
          to="/imports"
          class="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          管理导入 →
        </RouterLink>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">快捷操作</div>
        <RouterLink
          to="/quotations/new"
          class="mt-4 inline-flex rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          创建报价
        </RouterLink>
      </div>
    </div>
  </div>
</template>
