<template>
  <main class="flex min-h-screen items-center justify-center bg-slate-50 p-6">
    <section class="w-full max-w-lg rounded-xl border bg-white p-8 shadow-sm">
      <h1 class="text-xl font-semibold">DevMind MCP 授权</h1>
      <p v-if="request" class="mt-4 text-slate-700">
        {{ request.client_name }} 请求访问 DevMind 数据。
      </p>
      <p v-if="request" class="mt-2 text-slate-700">
        本次授权的 DevMind 账号：
        {{ request.devmind_user.username }}
        <span v-if="request.devmind_user.email" class="text-slate-500">
          （{{ request.devmind_user.email }}）
        </span>
      </p>
      <ul v-if="request" class="mt-4 list-inside list-disc text-slate-600">
        <li v-for="scope in request.scopes" :key="scope">
          {{ scope === 'mcp:read' ? '只读查询报价单、票据及授权文档' : scope }}
        </li>
      </ul>
      <p v-if="error" class="mt-4 text-red-700">{{ error }}</p>
      <div v-if="request" class="mt-8 flex justify-end gap-3">
        <button
          class="rounded-lg border px-4 py-2"
          :disabled="busy"
          @click="finish(false)"
        >
          拒绝
        </button>
        <button
          class="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
          :disabled="busy"
          @click="finish(true)"
        >
          {{ busy ? '处理中…' : '允许只读访问' }}
        </button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import {
  finishMcpOAuthAuthorization,
  getMcpOAuthAuthorization,
} from '@/api/mcpOAuth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const request = ref(null)
const error = ref('')
const busy = ref(false)
const transactionId = String(route.query.transaction || '')

onMounted(async () => {
  if (!/^[0-9a-f-]{36}$/i.test(transactionId)) {
    error.value = '授权请求无效或已过期。'
    return
  }
  if (!(await userStore.checkAuth())) {
    sessionStorage.setItem('mcp_oauth_return', route.fullPath)
    await router.replace('/login')
    return
  }
  try {
    request.value = await getMcpOAuthAuthorization(transactionId)
  } catch {
    error.value = '无法读取授权请求，请重新从 MCP 客户端连接。'
  }
})

async function finish(approved) {
  busy.value = true
  error.value = ''
  try {
    const response = await finishMcpOAuthAuthorization(
      transactionId,
      approved,
    )
    window.location.assign(response.redirect_url)
  } catch {
    error.value = '授权处理失败，请重新从 MCP 客户端连接。'
    busy.value = false
  }
}
</script>
