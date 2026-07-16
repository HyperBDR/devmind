<script setup lang="ts">
import { ref } from 'vue'
import { Lock, Mail } from 'lucide-vue-next'
import { login as loginApi } from '../api/auth'

const emit = defineEmits<{
  loginSuccess: []
}>()

const email = ref('alice.chen@oneprocloud.com')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await loginApi(email.value.trim(), password.value)
    emit('loginSuccess')
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : '登录失败，请检查邮箱或密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-dm-page px-4">
    <div class="w-full max-w-[420px]">
      <div class="mb-8 text-center">
        <div
          class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-dm-lg bg-dm-primary text-sm font-semibold tracking-wide text-white"
        >
          OP
        </div>
        <h1 class="text-[22px] font-semibold tracking-tight text-dm-text">报价管理平台</h1>
        <p class="mt-2 text-sm text-dm-text-tertiary">使用企业账号登录后继续业务操作</p>
      </div>

      <form
        class="dm-card-lg p-7"
        @submit.prevent="handleSubmit"
      >
        <div class="space-y-4">
          <div>
            <label class="mb-1.5 block text-sm text-dm-text-secondary">邮箱</label>
            <div class="relative">
              <Mail
                class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary"
              />
              <input
                v-model="email"
                type="email"
                autocomplete="username"
                required
                class="w-full rounded-dm border border-dm-border bg-white py-2.5 pl-10 pr-3 text-sm text-dm-text outline-none transition focus:border-dm-primary focus:shadow-[0_0_0_2px_rgba(22,119,255,0.1)]"
                placeholder="name@company.com"
              />
            </div>
          </div>

          <div>
            <label class="mb-1.5 block text-sm text-dm-text-secondary">密码</label>
            <div class="relative">
              <Lock
                class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dm-text-tertiary"
              />
              <input
                v-model="password"
                type="password"
                autocomplete="current-password"
                required
                class="w-full rounded-dm border border-dm-border bg-white py-2.5 pl-10 pr-3 text-sm text-dm-text outline-none transition focus:border-dm-primary focus:shadow-[0_0_0_2px_rgba(22,119,255,0.1)]"
                placeholder="请输入密码"
              />
            </div>
          </div>
        </div>

        <p
          v-if="error"
          class="mt-4 rounded-dm border border-[#ffccc7] bg-dm-error-bg px-3 py-2 text-xs text-dm-error"
        >
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="loading"
          class="dm-btn-primary mt-6 w-full py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
        >
          {{ loading ? '登录中…' : '登录' }}
        </button>

        <div class="mt-5 rounded-dm border border-dm-border-light bg-[#fafafa] px-3 py-3 text-xs leading-relaxed text-dm-text-tertiary">
          <p class="font-medium text-dm-text-secondary">演示账号</p>
          <p class="mt-1">alice.chen@oneprocloud.com</p>
          <p>默认密码：请通过环境变量配置</p>
        </div>
      </form>
    </div>
  </div>
</template>
