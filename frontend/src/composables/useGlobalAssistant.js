import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { assistantApi } from '@/api/assistant'
import {
  appendAiContent,
  resolveFinalAiContent,
  sanitizeAiContent
} from '@/utils/dataOpsAiStream'
import {
  indexAssistantCapabilities,
  resolveAssistantCapability
} from '@/utils/assistantCapability'

export function useGlobalAssistant() {
  const { t } = useI18n()
  const capabilities = ref(new Map())
  const currentCapability = ref(null)
  const activeAppKey = ref('')
  const activeHistoryId = ref('')
  const history = ref([])
  const input = ref('')
  const loading = ref(false)
  const messages = ref([])
  const streamController = ref(null)
  let capabilitiesLoaded = false
  let activationVersion = 0

  const context = computed(() => ({
    assistant: currentCapability.value?.profile || {}
  }))

  async function loadCapabilities(force = false) {
    if (capabilitiesLoaded && !force) return capabilities.value
    const response = await assistantApi.capabilities()
    capabilities.value = indexAssistantCapabilities(response?.data?.data || [])
    capabilitiesLoaded = true
    return capabilities.value
  }

  async function activateApp(appKey) {
    const version = ++activationVersion
    stopStream()
    activeAppKey.value = appKey || ''
    activeHistoryId.value = ''
    history.value = []
    messages.value = []
    input.value = ''
    currentCapability.value = null
    if (!appKey) return

    try {
      const loaded = await loadCapabilities()
      if (version !== activationVersion) return
      const capability = resolveAssistantCapability(loaded, appKey)
      if (!capability) return
      currentCapability.value = capability
      await loadHistory(version)
    } catch (_) {
      if (version === activationVersion) {
        currentCapability.value = null
      }
    }
  }

  async function loadHistory(version = activationVersion) {
    if (!activeAppKey.value || !currentCapability.value) return
    const response = await assistantApi.conversations(activeAppKey.value)
    if (version !== activationVersion) return
    history.value = (response?.data?.data || []).map(normalizeHistory)
  }

  async function ensureConversation() {
    if (activeHistoryId.value) return activeHistoryId.value
    const response = await assistantApi.createConversation(activeAppKey.value)
    const item = normalizeHistory(response?.data?.data || {})
    activeHistoryId.value = item.id
    history.value = [item, ...history.value]
    return item.id
  }

  async function sendMessage() {
    const message = input.value.trim()
    if (!message || loading.value || !currentCapability.value) return
    const conversationId = await ensureConversation()
    messages.value.push({ role: 'user', content: message })
    input.value = ''
    loading.value = true
    const startedAt = Date.now()
    const assistantMessage = {
      content: '',
      elapsedMs: 0,
      progressEvents: [],
      role: 'assistant',
      startedAt,
      status: 'thinking'
    }
    messages.value.push(assistantMessage)
    const assistantIndex = messages.value.length - 1
    const timerId = setInterval(() => {
      const current = messages.value[assistantIndex]
      if (current) current.elapsedMs = Date.now() - startedAt
    }, 200)
    streamController.value = new AbortController()

    try {
      await assistantApi.streamMessage(
        conversationId,
        {
          message,
          page_context: { app_key: activeAppKey.value }
        },
        {
          onProgress(event) {
            const current = messages.value[assistantIndex]
            if (!current) return
            current.progressEvents = [...(current.progressEvents || []), event]
          },
          onChunk(content) {
            const current = messages.value[assistantIndex]
            if (!current) return
            current.content = appendAiContent(current.content, content)
            current.status = 'streaming'
          },
          onDone(payload) {
            const current = messages.value[assistantIndex]
            if (!current) return
            current.content = resolveFinalAiContent(
              current.content,
              payload?.reply || '',
              t('dataOps.feedback.analysisEmpty')
            )
            current.llm = payload?.llm || null
            current.status = 'done'
            current.usage = payload?.usage || null
          },
          onError(detail) {
            const current = messages.value[assistantIndex]
            if (!current) return
            current.status = 'error'
            if (!sanitizeAiContent(current.content)) {
              current.content = detail || t('dataOps.feedback.streamFailed')
            }
          }
        },
        streamController.value.signal
      )
    } catch (error) {
      const current = messages.value[assistantIndex]
      if (current) {
        current.status = error?.name === 'AbortError' ? 'stopped' : 'error'
        if (!sanitizeAiContent(current.content)) {
          current.content =
            error?.name === 'AbortError'
              ? t('dataOps.feedback.stopped')
              : error?.message || t('dataOps.feedback.requestFailed')
        }
      }
    } finally {
      clearInterval(timerId)
      const current = messages.value[assistantIndex]
      if (current) current.elapsedMs = Date.now() - startedAt
      streamController.value = null
      loading.value = false
      await loadHistory()
    }
  }

  function askQuestion(question) {
    input.value = question
    return sendMessage()
  }

  function stopStream() {
    if (streamController.value) {
      streamController.value.abort()
      streamController.value = null
    }
    loading.value = false
  }

  function startNewConversation() {
    if (loading.value) return
    activeHistoryId.value = ''
    input.value = ''
    messages.value = []
  }

  async function selectHistory(id) {
    if (loading.value) return
    const response = await assistantApi.messages(id)
    activeHistoryId.value = id
    input.value = ''
    messages.value = (response?.data?.data || []).map(normalizeMessage)
  }

  async function deleteHistory(id) {
    if (loading.value) return
    await assistantApi.deleteConversation(id)
    history.value = history.value.filter((item) => item.id !== id)
    if (activeHistoryId.value === id) startNewConversation()
  }

  onBeforeUnmount(stopStream)

  return {
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
  }
}

function normalizeHistory(item) {
  return {
    id: item.uuid || '',
    messageCount: item.messageCount ?? item.message_count ?? 0,
    title: item.title || 'New conversation',
    updatedAt: item.updatedAt || item.updated_at || new Date().toISOString()
  }
}

function normalizeMessage(item) {
  return {
    content: item.content || '',
    ...(item.metadata || {}),
    role: item.role || 'assistant',
    status: 'done'
  }
}
