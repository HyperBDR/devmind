<template>
  <AdminLayout>
    <div class="w-full max-w-full p-6">
      <div
        class="max-w-2xl mx-auto bg-white rounded-lg border border-gray-200 shadow-sm p-8"
      >
        <h1 class="text-lg font-semibold text-gray-900 mb-2">
          正在打开外部站点
        </h1>
        <p class="text-sm text-gray-500 mb-6">
          系统正在校验配置并准备跳转，请稍候。
        </p>

        <BaseLoading v-if="loading" />

        <div v-if="error" class="space-y-4">
          <p class="text-sm text-red-600">{{ error }}</p>
          <div class="flex items-center gap-3">
            <BaseButton variant="outline" @click="retry">重试</BaseButton>
            <BaseButton variant="primary" @click="goBack">返回列表</BaseButton>
          </div>
        </div>

        <div v-if="launchUrl && !loading" class="space-y-4">
          <p class="text-sm text-green-600">
            已获取访问地址，若未自动跳转，请点击下方按钮。
          </p>
          <div
            class="rounded-md bg-gray-50 border border-gray-200 px-3 py-2 font-mono text-sm text-gray-700 break-all"
          >
            {{ launchUrl }}
          </div>
          <div class="flex items-center gap-3">
            <BaseButton variant="primary" @click="openNow">立即打开</BaseButton>
            <BaseButton variant="outline" @click="copyLink"
              >复制链接</BaseButton
            >
          </div>
        </div>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { externalProxyAdminApi } from '@/admin/api'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'

const route = useRoute()
const router = useRouter()
const { showError, showSuccess } = useToast()

const loading = ref(true)
const error = ref('')
const launchUrl = ref('')

async function loadLaunchUrl() {
  loading.value = true
  error.value = ''
  try {
    const data = await externalProxyAdminApi.launchSite(route.params.id)
    launchUrl.value = data?.launch_url || ''
    if (!launchUrl.value) {
      throw new Error('未获取到可访问链接')
    }
    window.location.href = launchUrl.value
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '打开失败'
    showError(error.value)
  } finally {
    loading.value = false
  }
}

function retry() {
  loadLaunchUrl()
}

function goBack() {
  router.push('/management/external-sites')
}

function openNow() {
  if (launchUrl.value) {
    window.location.href = launchUrl.value
  }
}

async function copyLink() {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(launchUrl.value)
    } else {
      const ta = document.createElement('textarea')
      ta.value = launchUrl.value
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    showSuccess('链接已复制')
  } catch (e) {
    showError(e?.message || '复制失败')
  }
}

onMounted(() => {
  loadLaunchUrl()
})
</script>
