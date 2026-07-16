<template>
  <AiAssistantSection
    v-if="currentCapability"
    v-model:input="input"
    :active-history-id="activeHistoryId"
    :context="context"
    :drawer-label="assistantCopy.drawerLabel"
    :history="history"
    :loading="loading"
    :messages="messages"
    :open-label="assistantCopy.openLabel"
    :subtitle="assistantCopy.description"
    :title="assistantCopy.title"
    @ask="askQuestion"
    @delete-history="deleteHistory"
    @new-chat="startNewConversation"
    @select-history="selectHistory"
    @send="sendMessage"
    @stop="stopStream"
  />
</template>

<script setup>
import { computed, defineAsyncComponent, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { useGlobalAssistant } from '@/composables/useGlobalAssistant'
import { useUserStore } from '@/store/user'
import { localizeAssistantCapability } from '@/utils/assistantCapability'

const AiAssistantSection = defineAsyncComponent(
  () => import('@/components/data-ops/AiAssistantSection.vue')
)
const route = useRoute()
const { t, te } = useI18n()
const userStore = useUserStore()
const routeAppKey = computed(() => String(route.meta.appKey || ''))
const isAuthenticated = computed(() => userStore.isAuthenticated)
const userKey = computed(() => String(userStore.userInfo?.id || ''))
const {
  activateApp,
  activeHistoryId,
  askQuestion,
  context,
  currentCapability,
  deleteHistory,
  history,
  input,
  loading,
  messages,
  selectHistory,
  sendMessage,
  startNewConversation,
  stopStream
} = useGlobalAssistant()
const assistantCopy = computed(() =>
  localizeAssistantCapability(currentCapability.value, t, te)
)

watch(
  [routeAppKey, isAuthenticated, userKey],
  ([appKey, authenticated, currentUserKey]) =>
    activateApp(authenticated ? appKey : '', currentUserKey),
  { immediate: true }
)
</script>
