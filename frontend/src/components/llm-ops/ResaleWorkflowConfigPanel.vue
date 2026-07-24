<template>
  <section class="workflow-panel">
    <div class="workflow-toolbar">
      <div class="workflow-toolbar-actions">
        <CompactSelect
          v-model="localPlatformId"
          :options="platformOptions"
          class-name="w-44"
          size="sm"
          :disabled="loading"
        />
        <button
          type="button"
          class="btn-secondary btn-action-refresh"
          :disabled="loading || !localPlatformId"
          @click="loadConfig"
        >
          {{ t('llmOps.workflowConfig.actions.reload') }}
        </button>
        <button
          type="button"
          class="btn-secondary btn-action-cancel"
          :disabled="saving || loading || !workflow"
          @click="resetConfig"
        >
          {{ t('llmOps.workflowConfig.actions.reset') }}
        </button>
        <button
          type="button"
          class="btn-primary btn-action-save"
          :disabled="saving || loading || !workflow"
          @click="saveConfig"
        >
          {{ t('llmOps.workflowConfig.actions.save') }}
        </button>
      </div>
    </div>

    <BaseLoading v-if="loading" />

    <div v-else-if="!localPlatformId" class="workflow-empty">
      {{ t('llmOps.workflowConfig.empty.noPlatform') }}
    </div>

    <div v-else-if="workflow" class="workflow-blueprint-layout">
      <div class="workflow-blueprint-main">
        <section
          class="workflow-flowchart"
          :aria-label="t('llmOps.workflowConfig.flowchart.title')"
        >
          <header class="workflow-flowchart-header">
            <div>
              <h4>{{ t('llmOps.workflowConfig.flowchart.title') }}</h4>
              <p>{{ t('llmOps.workflowConfig.flowchart.description') }}</p>
            </div>
            <span>{{ t('llmOps.workflowConfig.flowchart.badge') }}</span>
          </header>

          <div class="workflow-flowchart-body">
            <div class="workflow-flow-row">
              <article class="workflow-flow-node is-fixed">
                <small>01</small>
                <strong>{{
                  t('llmOps.workflowConfig.nodes.selectModel.title')
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.nodes.selectModel.subtitle')
                }}</span>
              </article>
              <span class="workflow-flow-arrow">→</span>
              <article class="workflow-flow-node is-fixed">
                <small>02</small>
                <strong>{{
                  t('llmOps.workflowConfig.nodes.selectChannel.title')
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.nodes.selectChannel.subtitle')
                }}</span>
              </article>
              <span class="workflow-flow-arrow">→</span>
              <article class="workflow-flow-node is-fixed">
                <small>03</small>
                <strong>{{
                  t('llmOps.workflowConfig.nodes.setMargin.title')
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.nodes.setMargin.subtitle')
                }}</span>
              </article>
            </div>

            <div class="workflow-flow-elbow" aria-hidden="true">
              <span></span>
            </div>

            <div class="workflow-flow-split is-submit">
              <article class="workflow-flow-node is-fixed">
                <small>04</small>
                <strong>{{
                  t('llmOps.workflowConfig.nodes.submit.title')
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.nodes.submit.subtitle')
                }}</span>
              </article>
            </div>

            <div class="workflow-flow-branches">
              <article
                class="workflow-flow-node is-policy"
                :class="{ 'is-disabled': !policies.auto_approve_enabled }"
              >
                <div class="workflow-node-top">
                  <small>{{
                    t('llmOps.workflowConfig.policy.autoPath')
                  }}</small>
                  <label class="workflow-node-toggle">
                    <input
                      id="workflow-auto-approve-enabled"
                      v-model="editableConfig.policies.auto_approve_enabled"
                      name="workflow_auto_approve_enabled"
                      type="checkbox"
                      @change="onAutoApproveToggle"
                    />
                    <span>{{
                      policies.auto_approve_enabled
                        ? t('llmOps.workflowConfig.status.enabled')
                        : t('llmOps.workflowConfig.status.disabled')
                    }}</span>
                  </label>
                </div>
                <strong>{{
                  t('llmOps.workflowConfig.policy.autoApproveThreshold', {
                    rate: autoApproveRateLabel
                  })
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.policy.autoApproveHint')
                }}</span>
              </article>
              <article
                class="workflow-flow-node is-policy"
                :class="{ 'is-disabled': !approvalFlowEnabled }"
              >
                <div class="workflow-node-top">
                  <small>{{
                    t('llmOps.workflowConfig.policy.approvalPath')
                  }}</small>
                  <select
                    id="workflow-approval-mode"
                    class="workflow-node-select"
                    name="workflow_approval_mode"
                    :value="approvalMode"
                    :aria-label="t('llmOps.workflowConfig.policy.approvalPath')"
                    @change="setApprovalMode($event.target.value)"
                  >
                    <option value="internal">
                      {{ t('llmOps.workflowConfig.approvalModes.internal') }}
                    </option>
                    <option v-if="feishuApprovalAvailable" value="external">
                      {{ t('llmOps.workflowConfig.approvalModes.external') }}
                    </option>
                    <option v-if="feishuApprovalAvailable" value="both">
                      {{ t('llmOps.workflowConfig.approvalModes.both') }}
                    </option>
                    <option
                      value="disabled"
                      :disabled="!policies.auto_approve_enabled"
                    >
                      {{ t('llmOps.workflowConfig.approvalModes.disabled') }}
                    </option>
                  </select>
                </div>
                <strong>{{ approvalFlowLabel }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.policy.reviewFallback')
                }}</span>
                <span
                  v-if="!feishuApprovalAvailable"
                  class="workflow-node-hint"
                >
                  {{ t('llmOps.workflowConfig.policy.feishuDisabledHint') }}
                </span>
              </article>
            </div>

            <div class="workflow-flow-join" aria-hidden="true">
              <span class="workflow-flow-join-horizontal"></span>
              <span class="workflow-flow-join-trunk"></span>
            </div>

            <div class="workflow-flow-split is-post-approval">
              <article class="workflow-flow-node is-publish">
                <div class="workflow-node-top">
                  <small>05</small>
                  <select
                    id="workflow-publish-mode"
                    class="workflow-node-select"
                    name="workflow_publish_mode"
                    :value="publishMode"
                    :aria-label="
                      t('llmOps.workflowConfig.policy.postApprovalAction')
                    "
                    @change="setPublishMode($event.target.value)"
                  >
                    <option value="auto">
                      {{ t('llmOps.workflowConfig.publishModes.auto') }}
                    </option>
                    <option value="manual">
                      {{ t('llmOps.workflowConfig.publishModes.manual') }}
                    </option>
                  </select>
                </div>
                <strong>{{
                  t('llmOps.workflowConfig.policy.postApprovalAction')
                }}</strong>
                <span class="workflow-flow-outcome">
                  {{ publishFlowLabel }}
                </span>
                <span>{{ publishFlowDescription }}</span>
              </article>
            </div>

            <div class="workflow-flow-split is-terminal">
              <article class="workflow-flow-node is-fixed">
                <small>06</small>
                <strong>{{
                  t('llmOps.workflowConfig.nodes.terminal.title')
                }}</strong>
                <span>{{
                  t('llmOps.workflowConfig.nodes.terminal.subtitle')
                }}</span>
              </article>
            </div>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import '@/components/llm-ops/resaleWorkflowConfigPanel.css'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseLoading from '@/components/ui/BaseLoading.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { llmOpsApi } from '@/api/llmOps'
import { DEFAULT_WORKFLOW_POLICIES } from '@/constants/llmOpsWorkflow'
import { useToast } from '@/composables/useToast'
import { userFacingApiError } from '@/utils/llmOpsErrors'

const props = defineProps({
  platforms: {
    type: Array,
    default: () => []
  },
  platformId: {
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits(['update:platformId', 'saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const workflow = ref(null)
const localPlatformId = ref(props.platformId || '')
const feishuApprovalAvailable = ref(false)

const platformOptions = computed(() =>
  props.platforms.map((platform) => ({
    label: platform.name,
    value: String(platform.id)
  }))
)

const editableConfig = computed(() => workflow.value?.config || {})
const policies = computed(() => editableConfig.value.policies || {})
const runtime = computed(() => editableConfig.value.runtime || {})
const autoApproveRateLabel = computed(
  () => `${runtime.value.auto_approve_max_margin_rate ?? '-'}%`
)
const approvalFlowEnabled = computed(() =>
  Boolean(
    policies.value.manual_confirm_required ||
      policies.value.feishu_approval_enabled
  )
)
const approvalFlowLabel = computed(() => {
  if (
    policies.value.manual_confirm_required &&
    policies.value.feishu_approval_enabled
  ) {
    return t('llmOps.workflowConfig.approvalModes.both')
  }
  if (policies.value.feishu_approval_enabled) {
    return t('llmOps.workflowConfig.approvalModes.external')
  }
  if (policies.value.manual_confirm_required) {
    return t('llmOps.workflowConfig.approvalModes.internal')
  }
  return t('llmOps.workflowConfig.approvalModes.disabledState')
})
const approvalMode = computed(() => {
  if (
    policies.value.manual_confirm_required &&
    policies.value.feishu_approval_enabled
  ) {
    return 'both'
  }
  if (policies.value.feishu_approval_enabled) return 'external'
  if (policies.value.manual_confirm_required) return 'internal'
  return 'disabled'
})
const publishFlowLabel = computed(() => {
  if (policies.value.auto_apply_after_approval) {
    return t('llmOps.workflowConfig.publishModes.auto')
  }
  return t('llmOps.workflowConfig.publishModes.manual')
})
const publishMode = computed(() => {
  if (policies.value.auto_apply_after_approval) return 'auto'
  return 'manual'
})
const publishFlowDescription = computed(() => {
  if (policies.value.auto_apply_after_approval) {
    return t('llmOps.workflowConfig.publishDescriptions.auto')
  }
  return t('llmOps.workflowConfig.publishDescriptions.manual')
})

watch(
  () => props.platformId,
  (next) => {
    if (String(next || '') !== String(localPlatformId.value || '')) {
      localPlatformId.value = next || ''
    }
  }
)

watch(
  localPlatformId,
  (next) => {
    emit('update:platformId', next)
    if (next) {
      loadConfig()
    } else {
      workflow.value = null
    }
  },
  { immediate: true }
)

async function loadConfig() {
  if (!localPlatformId.value) return
  loading.value = true
  try {
    const [response, globalResponse] = await Promise.all([
      llmOpsApi.getResaleWorkflowConfig(localPlatformId.value),
      llmOpsApi.getGlobalConfig()
    ])
    feishuApprovalAvailable.value = Boolean(
      normalizeGlobalConfigPayload(globalResponse.data).feishu_approval_enabled
    )
    workflow.value = normalizeWorkflowPayload(response.data)
    enforceFeishuApprovalAvailability()
    syncPolicyEdges()
  } catch (error) {
    showError(
      errorMessage(error) || t('llmOps.workflowConfig.errors.loadFailed')
    )
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!workflow.value || !localPlatformId.value) return
  if (!hasPublishPath(editableConfig.value.policies)) {
    showError(t('llmOps.workflowConfig.errors.noPublishPath'))
    return
  }
  saving.value = true
  try {
    enforceFeishuApprovalAvailability()
    syncPolicyEdges()
    const response = await llmOpsApi.updateResaleWorkflowConfig(
      localPlatformId.value,
      {
        config: editableConfig.value,
        is_active: workflow.value.is_active !== false,
        notes: workflow.value.notes || ''
      }
    )
    workflow.value = normalizeWorkflowPayload(response.data)
    enforceFeishuApprovalAvailability()
    syncPolicyEdges()
    showSuccess(t('llmOps.workflowConfig.messages.saved'))
    emit('saved', workflow.value)
  } catch (error) {
    showError(
      errorMessage(error) || t('llmOps.workflowConfig.errors.saveFailed')
    )
  } finally {
    saving.value = false
  }
}

async function resetConfig() {
  if (!localPlatformId.value) return
  if (!confirm(t('llmOps.workflowConfig.confirm.reset'))) return
  saving.value = true
  try {
    const response = await llmOpsApi.resetResaleWorkflowConfig(
      localPlatformId.value
    )
    workflow.value = normalizeWorkflowPayload(response.data)
    enforceFeishuApprovalAvailability()
    syncPolicyEdges()
    showSuccess(t('llmOps.workflowConfig.messages.reset'))
    emit('saved', workflow.value)
  } catch (error) {
    showError(
      errorMessage(error) || t('llmOps.workflowConfig.errors.resetFailed')
    )
  } finally {
    saving.value = false
  }
}

function syncPolicyEdges() {
  const config = editableConfig.value
  if (!config?.edges || !config?.nodes || !config?.policies) return
  enforceFeishuApprovalAvailability()
  setNodeEnabled('auto_confirm', config.policies.auto_approve_enabled)
  setNodeEnabled('manual_review', config.policies.manual_confirm_required)
  setNodeEnabled('feishu_approval', config.policies.feishu_approval_enabled)
  setEdgeEnabled('gate_to_auto', config.policies.auto_approve_enabled)
  setEdgeEnabled('auto_to_online', config.policies.auto_approve_enabled)
  setEdgeEnabled('gate_to_manual', config.policies.manual_confirm_required)
  setEdgeEnabled('manual_to_online', config.policies.manual_confirm_required)
  setEdgeEnabled('gate_to_feishu', config.policies.feishu_approval_enabled)
  setEdgeEnabled('feishu_to_online', config.policies.feishu_approval_enabled)
}

function onAutoApproveToggle() {
  const config = editableConfig.value
  if (!config?.policies) return
  if (!config.policies.auto_approve_enabled && !approvalFlowEnabled.value) {
    config.policies.manual_confirm_required = true
  }
  syncPolicyEdges()
}

function setApprovalMode(mode) {
  const config = editableConfig.value
  if (!config?.policies) return
  if (!feishuApprovalAvailable.value && ['external', 'both'].includes(mode)) {
    mode = 'internal'
  }
  if (mode === 'disabled' && !config.policies.auto_approve_enabled) {
    config.policies.manual_confirm_required = true
    config.policies.feishu_approval_enabled = false
    syncPolicyEdges()
    return
  }
  config.policies.manual_confirm_required = ['internal', 'both'].includes(mode)
  config.policies.feishu_approval_enabled = ['external', 'both'].includes(mode)
  syncPolicyEdges()
}

function setPublishMode(mode) {
  const config = editableConfig.value
  if (!config?.policies) return
  config.policies.auto_apply_after_approval = mode === 'auto'
  syncPolicyEdges()
}

function setNodeEnabled(id, enabled) {
  const node = editableConfig.value.nodes.find((item) => item.id === id)
  if (node) node.enabled = Boolean(enabled)
}

function setEdgeEnabled(id, enabled) {
  const edge = editableConfig.value.edges.find((item) => item.id === id)
  if (edge) edge.enabled = Boolean(enabled)
}

function hasPublishPath(policyState = {}) {
  return Boolean(
    policyState.auto_approve_enabled ||
      policyState.manual_confirm_required ||
      (feishuApprovalAvailable.value && policyState.feishu_approval_enabled)
  )
}

function enforceFeishuApprovalAvailability() {
  const config = editableConfig.value
  if (!config?.policies || feishuApprovalAvailable.value) return
  config.policies.feishu_approval_enabled = false
}

function normalizeWorkflowPayload(payload) {
  const source = isPlainObject(payload?.data) ? payload.data : payload
  const next = clone(isPlainObject(source) ? source : {})
  const config = isPlainObject(next.config) ? next.config : {}
  next.config = {
    ...config,
    policies: {
      ...DEFAULT_WORKFLOW_POLICIES,
      ...(isPlainObject(config.policies) ? config.policies : {})
    },
    nodes: Array.isArray(config.nodes) ? config.nodes : [],
    edges: Array.isArray(config.edges) ? config.edges : [],
    runtime: isPlainObject(config.runtime) ? config.runtime : {}
  }
  return next
}

function normalizeGlobalConfigPayload(payload) {
  const source = isPlainObject(payload?.data) ? payload.data : payload
  return isPlainObject(source) ? source : {}
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function errorMessage(error) {
  return userFacingApiError(error, '')
}
</script>
