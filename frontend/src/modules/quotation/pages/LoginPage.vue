<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('alice.chen@oneprocloud.com')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login()
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败，请检查邮箱或密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-[#f4f6f8] px-4">
    <div class="w-full max-w-[420px]">
      <div class="mb-8 text-center">
        <div
          class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold tracking-wide text-white"
        >
          OP
        </div>
        <h1 class="text-[22px] font-semibold tracking-tight text-slate-900">报价管理平台</h1>
        <p class="mt-2 text-sm text-slate-500">使用企业账号登录后继续业务操作</p>
      </div>

      <form
        class="rounded-2xl border border-slate-200/80 bg-white p-7 shadow-[0_10px_30px_rgba(15,23,42,0.06)]"
        @submit.prevent="handleSubmit"
      >
        <div class="space-y-4">
          <div>
            <label class="mb-1.5 block text-sm font-semibold text-slate-600">邮箱</label>
            <input
              v-model="email"
              type="email"
              autocomplete="username"
              required
              class="w-full rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
              placeholder="name@company.com"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-sm font-semibold text-slate-600">密码</label>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
              class="w-full rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-slate-400 focus:bg-white"
              placeholder="请输入密码"
            />
          </div>
        </div>

        <p
          v-if="error"
          class="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-600"
        >
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="loading"
          class="mt-6 w-full rounded-xl bg-slate-900 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {{ loading ? '登录中…' : '登录' }}
        </button>

        <div class="mt-5 rounded-xl bg-slate-50 px-3 py-3 text-xs leading-relaxed text-slate-500">
          <p class="font-semibold text-slate-600">演示账号</p>
          <p class="mt-1">alice.chen@oneprocloud.com</p>
          <p>默认密码：请通过环境变量配置</p>
        </div>
      </form>
    </div>
  </div>
</template>
