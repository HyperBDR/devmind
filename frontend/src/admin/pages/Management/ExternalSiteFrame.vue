<template>
  <AdminLayout>
    <div class="w-full h-[calc(100vh-4rem)] p-4">
      <div v-if="loading" class="h-full flex items-center justify-center">
        <BaseLoading />
      </div>

      <div
        v-else-if="error"
        class="max-w-2xl mx-auto bg-white rounded-lg border border-gray-200 shadow-sm p-8"
      >
        <h1 class="text-lg font-semibold text-gray-900 mb-2">
          外部视图加载失败
        </h1>
        <p class="text-sm text-red-600 mb-4">{{ error }}</p>
        <div class="flex items-center gap-3">
          <BaseButton variant="outline" @click="loadFrame">重试</BaseButton>
          <BaseButton variant="primary" @click="goBack">返回列表</BaseButton>
        </div>
      </div>

      <div
        v-else
        class="h-full bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden"
      >
        <div
          class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50"
        >
          <div>
            <h1 class="text-base font-semibold text-gray-900">{{ title }}</h1>
            <p class="text-xs text-gray-500">{{ frameUrl }}</p>
          </div>
          <div class="flex items-center gap-2">
            <BaseButton variant="outline" size="sm" @click="reloadFrame"
              >刷新</BaseButton
            >
            <BaseButton variant="outline" size="sm" @click="openNewTab"
              >新窗口打开</BaseButton
            >
          </div>
        </div>
        <iframe
          :key="frameKey"
          :src="frameUrl"
          class="w-full h-[calc(100%-57px)] border-0"
          referrerpolicy="strict-origin-when-cross-origin"
        />
      </div>
    </div>
  </AdminLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { externalProxyAdminApi } from '@/admin/api'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { showError } = useToast()

const loading = ref(true)
const error = ref('')
const title = ref(t('management.externalSiteProxy'))
const frameUrl = ref('')
const frameKey = ref(0)

async function loadFrame() {
  loading.value = true
  error.value = ''
  try {
    const data = await externalProxyAdminApi.launchSite(route.params.id)
    if (data?.access_mode !== 'iframe') {
      throw new Error('该视图不是 iframe 模式')
    }
    title.value = data?.name || t('management.externalSiteProxy')
    frameUrl.value = data?.launch_url || ''
    if (!frameUrl.value) {
      throw new Error('未获取到 iframe 地址')
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
    showError(error.value)
  } finally {
    loading.value = false
  }
}

function reloadFrame() {
  frameKey.value += 1
}

function openNewTab() {
  if (frameUrl.value) {
    window.open(frameUrl.value, '_blank', 'noopener')
  }
}

function goBack() {
  router.push('/management/external-sites')
}

onMounted(() => {
  loadFrame()
})
</script>
