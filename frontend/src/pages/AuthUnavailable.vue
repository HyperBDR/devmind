<template>
  <main class="auth-unavailable-page">
    <section class="auth-unavailable-panel">
      <p class="auth-unavailable-eyebrow">Authentication service</p>
      <h1>认证服务暂时不可用</h1>
      <p>当前无法确认账号状态，本地登录信息已保留。服务恢复后可继续访问。</p>
      <button type="button" :disabled="retrying" @click="retry">
        {{ retrying ? '重试中...' : '重试' }}
      </button>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const retrying = ref(false)

async function retry() {
  if (retrying.value) return
  retrying.value = true
  try {
    const authenticated = await userStore.checkAuth()
    if (authenticated) {
      await router.replace(String(route.query.redirect || '/dashboard'))
    } else if (!userStore.authCheckUnavailable) {
      await router.replace('/login')
    }
  } finally {
    retrying.value = false
  }
}
</script>

<style scoped>
.auth-unavailable-page {
  align-items: center;
  background: #f8fafc;
  display: flex;
  min-height: 100vh;
  padding: 1.5rem;
}

.auth-unavailable-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  box-shadow: 0 20px 45px rgb(15 23 42 / 8%);
  margin: 0 auto;
  max-width: 28rem;
  padding: 2rem;
  width: 100%;
}

.auth-unavailable-eyebrow {
  color: #0f766e;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 0 0 0.75rem;
  text-transform: uppercase;
}

h1 {
  color: #0f172a;
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1.25;
  margin: 0;
}

p {
  color: #475569;
  line-height: 1.7;
  margin: 1rem 0 0;
}

button {
  background: #0f172a;
  border: 0;
  border-radius: 0.375rem;
  color: #ffffff;
  cursor: pointer;
  font-weight: 700;
  margin-top: 1.5rem;
  padding: 0.75rem 1rem;
  width: 100%;
}

button:disabled {
  cursor: wait;
  opacity: 0.7;
}
</style>
