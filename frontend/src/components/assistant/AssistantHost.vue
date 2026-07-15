<template>
  <AiAssistantSection
    v-if="currentCapability"
    v-model:input="input"
    :active-history-id="activeHistoryId"
    :context="context"
    :drawer-label="currentCapability.displayName"
    :history="history"
    :loading="loading"
    :messages="messages"
    :open-label="currentCapability.displayName"
    :subtitle="currentCapability.description"
    :title="currentCapability.displayName"
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
import { useRoute } from 'vue-router'

import { useGlobalAssistant } from '@/composables/useGlobalAssistant'
import { useUserStore } from '@/store/user'

const AiAssistantSection = defineAsyncComponent(
  () => import('@/components/data-ops/AiAssistantSection.vue')
)
const route = useRoute()
const userStore = useUserStore()
const routeAppKey = computed(() => String(route.meta.appKey || ''))
const isAuthenticated = computed(() => userStore.isAuthenticated)
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

watch(
  [routeAppKey, isAuthenticated],
  ([appKey, authenticated]) => activateApp(authenticated ? appKey : ''),
  { immediate: true }
)
</script>
