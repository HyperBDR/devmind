<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-4">
      <!-- Page Header -->
      <div class="mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('settings.title') }}
        </h2>
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <!-- Content (hidden until loading completes) -->
      <template v-else>
        <!-- User Profile Section -->
        <UserProfileSection />

        <!-- Basic Information Card -->
        <BasicInfoCard />

        <!-- Google News Configuration Card -->
        <GoogleNewsConfigCard />

        <!-- GitHub Configuration Card -->
        <GithubConfigCard />

        <!-- Social OSS Configuration Card -->
        <SocialOssConfigCard
          :modelValue="socialOssConfig"
          @update:modelValue="handleSocialOssConfigUpdate"
        />

        <!-- Publish OSS Configuration Card -->
        <PublishOssConfigCard
          :modelValue="publishOssConfig"
          @update:modelValue="handlePublishOssConfigUpdate"
        />

        <!-- Notification channels: configured in Admin > Notifications > Channels -->
        <div
          v-if="isAdmin"
          class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
        >
          <h3 class="text-sm font-semibold text-gray-900 mb-1">
            {{ t('settings.notificationChannels') }}
          </h3>
          <p class="text-sm text-gray-600 mb-3">
            {{ t('settings.notificationChannelsDesc') }}
          </p>
          <router-link
            to="/management/notifier/channels"
            class="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            {{ t('settings.goToChannels') }} →
          </router-link>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { settingsApi } from '@/api/settings'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import UserProfileSection from '@/components/settings/UserProfileSection.vue'
import BasicInfoCard from '@/components/settings/BasicInfoCard.vue'
import GoogleNewsConfigCard from '@/components/settings/GoogleNewsConfigCard.vue'
import GithubConfigCard from '@/components/settings/GithubConfigCard.vue'
import SocialOssConfigCard from '@/components/settings/SocialOssConfigCard.vue'
import PublishOssConfigCard from '@/components/settings/PublishOssConfigCard.vue'

const { t } = useI18n()
const userStore = useUserStore()
const loading = ref(true)

const isAdmin = computed(() => {
  return userStore.userInfo?.is_staff === true
})

const socialOssConfig = reactive({
  enable: false,
  access_key_id: '',
  access_key_secret: '',
  bucket_name: '',
  endpoint: '',
  region: '',
  use_virtual_style: false
})

const publishOssConfig = reactive({
  use_same_as_storage: true,
  access_key_id: '',
  access_key_secret: '',
  bucket_name: '',
  endpoint: '',
  region: '',
  use_virtual_style: false
})

const handleSocialOssConfigUpdate = (newValue) => {
  Object.assign(socialOssConfig, newValue)
}

const handlePublishOssConfigUpdate = (newValue) => {
  Object.assign(publishOssConfig, newValue)
}

const loadAllConfigs = async () => {
  loading.value = true
  try {
    // Ensure user data is loaded first
    if (!userStore.user) {
      await userStore.checkAuthStatus()
    }

    // Load all configurations in parallel
    // Note: GoogleNewsConfigCard loads its own data independently
    const [socialOssData, publishOssData] = await Promise.allSettled([
      settingsApi.getSocialOssConfig().catch(() => null),
      settingsApi.getPublishOssConfig().catch(() => null)
    ])

    // Update social OSS config
    // Mark as loaded by ensuring all fields are set (even if empty)
    if (socialOssData.status === 'fulfilled' && socialOssData.value !== null) {
      Object.assign(socialOssConfig, {
        enable: socialOssData.value.enable ?? false,
        access_key_id: socialOssData.value.access_key_id || '',
        access_key_secret: socialOssData.value.access_key_secret || '',
        bucket_name: socialOssData.value.bucket_name || '',
        endpoint: socialOssData.value.endpoint || '',
        region: socialOssData.value.region || '',
        use_virtual_style: socialOssData.value.use_virtual_style || false,
        _loaded: true // Mark as loaded
      })
    }

    // Update publish OSS config
    if (
      publishOssData.status === 'fulfilled' &&
      publishOssData.value !== null
    ) {
      Object.assign(publishOssConfig, {
        use_same_as_storage: publishOssData.value.use_same_as_storage ?? true,
        access_key_id: publishOssData.value.access_key_id || '',
        access_key_secret: publishOssData.value.access_key_secret || '',
        bucket_name: publishOssData.value.bucket_name || '',
        endpoint: publishOssData.value.endpoint || '',
        region: publishOssData.value.region || '',
        use_virtual_style: publishOssData.value.use_virtual_style || false,
        _loaded: true // Mark as loaded
      })
    }
  } catch (error) {
    console.error('Failed to load settings:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadAllConfigs()
})
</script>
