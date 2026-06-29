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
          重新加载
        </button>
        <button
          type="button"
          class="btn-secondary btn-action-cancel"
          :disabled="saving || loading || !workflow"
          @click="resetConfig"
        >
          恢复默认
        </button>
        <button
          type="button"
          class="btn-primary btn-action-save"
          :disabled="saving || loading || !workflow"
          @click="saveConfig"
        >
          保存并生效
        </button>
      </div>
    </div>

    <BaseLoading v-if="loading" />

    <div v-else-if="!localPlatformId" class="workflow-empty">
      请先创建或选择一个上架平台。
    </div>

    <div v-else-if="workflow" class="workflow-blueprint-layout">
      <div class="workflow-blueprint-main">
        <section class="workflow-flowchart" aria-label="上架流程图">
          <header class="workflow-flowchart-header">
            <div>
              <h4>上架流程图</h4>
              <p>主干流程固定只读，仅策略分支可配置。</p>
            </div>
            <span>只读主干</span>
          </header>

          <div class="workflow-flowchart-body">
            <div class="workflow-flow-row">
              <article class="workflow-flow-node is-fixed">
                <small>01</small>
                <strong>选择元模型</strong>
                <span>模型与版本</span>
              </article>
              <span class="workflow-flow-arrow">→</span>
              <article class="workflow-flow-node is-fixed">
                <small>02</small>
                <strong>选择采购渠道</strong>
                <span>渠道与成本</span>
              </article>
              <span class="workflow-flow-arrow">→</span>
              <article class="workflow-flow-node is-fixed">
                <small>03</small>
                <strong>设置利润率</strong>
                <span>生成上架价格</span>
              </article>
            </div>

            <div class="workflow-flow-elbow" aria-hidden="true">
              <span></span>
            </div>

            <div class="workflow-flow-split is-submit">
              <article class="workflow-flow-node is-fixed">
                <small>04</small>
                <strong>提交上架</strong>
                <span>进入判断</span>
              </article>
            </div>

            <div class="workflow-flow-branches">
              <article
                class="workflow-flow-node is-policy"
                :class="{ 'is-disabled': !policies.auto_approve_enabled }"
              >
                <div class="workflow-node-top">
                  <small>免审路径</small>
                  <label class="workflow-node-toggle">
                    <input
                      id="workflow-auto-approve-enabled"
                      v-model="editableConfig.policies.auto_approve_enabled"
                      name="workflow_auto_approve_enabled"
                      type="checkbox"
                      @change="onAutoApproveToggle"
                    />
                    <span>{{
                      policies.auto_approve_enabled ? '启用' : '停用'
                    }}</span>
                  </label>
                </div>
                <strong>利润率 ≤ {{ autoApproveRateLabel }}</strong>
                <span>直接确认</span>
              </article>
              <article
                class="workflow-flow-node is-policy"
                :class="{ 'is-disabled': !approvalFlowEnabled }"
              >
                <div class="workflow-node-top">
                  <small>审核路径</small>
                  <select
                    id="workflow-approval-mode"
                    class="workflow-node-select"
                    name="workflow_approval_mode"
                    :value="approvalMode"
                    aria-label="审核路径"
                    @change="setApprovalMode($event.target.value)"
                  >
                    <option value="internal">内部人工确认</option>
                    <option value="external">外部飞书审核</option>
                    <option value="both">内部 + 外部审核</option>
                    <option
                      value="disabled"
                      :disabled="!policies.auto_approve_enabled"
                    >
                      仅保留免审路径
                    </option>
                  </select>
                </div>
                <strong>{{ approvalFlowLabel }}</strong>
                <span>超阈值复核</span>
              </article>
            </div>

            <div class="workflow-flow-join" aria-hidden="true">
              <span></span>
            </div>

            <div class="workflow-flow-split">
              <article class="workflow-flow-node is-policy">
                <div class="workflow-node-top">
                  <small>发布策略</small>
                  <select
                    id="workflow-publish-mode"
                    class="workflow-node-select"
                    name="workflow_publish_mode"
                    :value="publishMode"
                    aria-label="发布策略"
                    @change="setPublishMode($event.target.value)"
                  >
                    <option value="auto">免审后自动上线</option>
                    <option value="manual">提交后待确认</option>
                  </select>
                </div>
                <strong>{{ publishFlowLabel }}</strong>
                <span>{{ publishFlowDescription }}</span>
              </article>
            </div>

            <div class="workflow-flow-split is-terminal">
              <article class="workflow-flow-node is-fixed">
                <small>06</small>
                <strong>下架/异常处理</strong>
                <span>确认 / 驳回 / 异常</span>
              </article>
            </div>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import BaseLoading from '@/components/ui/BaseLoading.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { llmOpsApi } from '@/api/llmOps'
import { DEFAULT_WORKFLOW_POLICIES } from '@/constants/llmOpsWorkflow'
import { useToast } from '@/composables/useToast'

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

const loading = ref(false)
const saving = ref(false)
const workflow = ref(null)
const localPlatformId = ref(props.platformId || '')

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
    return '内部 + 外部审核'
  }
  if (policies.value.feishu_approval_enabled) return '外部飞书审核'
  if (policies.value.manual_confirm_required) return '内部人工确认'
  return '审核路径停用'
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
  if (policies.value.auto_apply_after_approval) return '免审后自动上线'
  return '提交后待确认'
})
const publishMode = computed(() => {
  if (policies.value.auto_apply_after_approval) return 'auto'
  return 'manual'
})
const publishFlowDescription = computed(() => {
  if (policies.value.auto_apply_after_approval) {
    return '免审命中后确认发布'
  }
  return '保留人工确认'
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
    const response = await llmOpsApi.getResaleWorkflowConfig(
      localPlatformId.value
    )
    workflow.value = normalizeWorkflowPayload(response.data)
    syncPolicyEdges()
  } catch (error) {
    showError(errorMessage(error) || '加载上架流程配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!workflow.value || !localPlatformId.value) return
  if (!hasPublishPath(editableConfig.value.policies)) {
    showError('至少需要保留免审、内部确认或外部审核中的一种上架路径')
    return
  }
  saving.value = true
  try {
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
    syncPolicyEdges()
    showSuccess('上架流程配置已生效')
    emit('saved', workflow.value)
  } catch (error) {
    showError(errorMessage(error) || '保存上架流程配置失败')
  } finally {
    saving.value = false
  }
}

async function resetConfig() {
  if (!localPlatformId.value) return
  if (!confirm('恢复默认流程配置？当前平台的自定义配置会被删除。')) return
  saving.value = true
  try {
    const response = await llmOpsApi.resetResaleWorkflowConfig(
      localPlatformId.value
    )
    workflow.value = normalizeWorkflowPayload(response.data)
    syncPolicyEdges()
    showSuccess('已恢复默认上架流程')
    emit('saved', workflow.value)
  } catch (error) {
    showError(errorMessage(error) || '恢复默认流程失败')
  } finally {
    saving.value = false
  }
}

function syncPolicyEdges() {
  const config = editableConfig.value
  if (!config?.edges || !config?.nodes || !config?.policies) return
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
      policyState.feishu_approval_enabled
  )
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

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function errorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    ''
  )
}
</script>

<style scoped>
.workflow-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.workflow-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.workflow-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

.workflow-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
  padding: 2rem;
  text-align: center;
}

.workflow-blueprint-layout {
  display: block;
}

.workflow-blueprint-main {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  min-width: 0;
  padding: 1rem;
}

.workflow-flowchart {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  overflow: hidden;
}

.workflow-flowchart-header {
  align-items: flex-start;
  border-bottom: 1px solid #dbeafe;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem;
}

.workflow-flowchart-header h4,
.workflow-flowchart-header p {
  margin: 0;
}

.workflow-flowchart-header h4 {
  color: #0f172a;
  font-size: 0.9375rem;
  font-weight: 800;
}

.workflow-flowchart-header p {
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.45;
  margin-top: 0.25rem;
}

.workflow-flowchart-header > span {
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  flex: 0 0 auto;
  font-size: 0.75rem;
  font-weight: 800;
  padding: 0.25rem 0.55rem;
}

.workflow-flowchart-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 1.25rem 1.25rem;
}

.workflow-flow-row {
  align-items: stretch;
  display: grid;
  grid-template-columns:
    minmax(8rem, 9rem) auto minmax(8rem, 9rem) auto
    minmax(8rem, 9rem);
  gap: 0.75rem;
  justify-content: center;
}

.workflow-flow-row.is-two {
  grid-template-columns: minmax(9.75rem, 11.75rem) auto minmax(
      9.75rem,
      11.75rem
    );
}

.workflow-flow-split {
  display: flex;
  justify-content: center;
  position: relative;
}

.workflow-flow-split::before,
.workflow-flow-split::after {
  background: #bfdbfe;
  content: '';
  height: 1rem;
  left: 50%;
  position: absolute;
  transform: translateX(-50%);
  width: 2px;
}

.workflow-flow-split::before {
  top: -1rem;
}

.workflow-flow-split::after {
  bottom: -1rem;
}

.workflow-flow-split.is-terminal::after {
  display: none;
}

.workflow-flow-split .workflow-flow-node {
  max-width: 11.75rem;
  width: 100%;
}

.workflow-flow-split.is-submit::before {
  display: none;
}

.workflow-flow-elbow {
  --workflow-elbow-offset: 16rem;
  height: 2rem;
  margin: -1rem auto;
  max-width: 41rem;
  position: relative;
  width: 100%;
}

.workflow-flow-elbow::before,
.workflow-flow-elbow::after,
.workflow-flow-elbow span {
  background: #bfdbfe;
  content: '';
  position: absolute;
}

.workflow-flow-elbow::before {
  bottom: 50%;
  left: calc(50% + var(--workflow-elbow-offset));
  top: 0;
  transform: translateX(-50%);
  width: 2px;
}

.workflow-flow-elbow::after {
  height: 2px;
  left: 50%;
  top: 50%;
  width: var(--workflow-elbow-offset);
}

.workflow-flow-elbow span {
  bottom: 0;
  left: 50%;
  top: 50%;
  transform: translateX(-50%);
  width: 2px;
}

.workflow-flow-branches {
  display: grid;
  gap: 4.5rem;
  grid-template-columns: repeat(2, minmax(10.25rem, 11.75rem));
  justify-content: center;
  position: relative;
}

.workflow-flow-branches::before {
  background: #bfdbfe;
  content: '';
  height: 2px;
  left: 22%;
  position: absolute;
  right: 22%;
  top: -0.5rem;
}

.workflow-flow-join {
  --workflow-join-offset: 11.25rem;
  height: 2rem;
  margin: -1rem auto;
  max-width: 32rem;
  position: relative;
  width: 100%;
}

.workflow-flow-join::before,
.workflow-flow-join::after,
.workflow-flow-join span,
.workflow-flow-join span::before {
  background: #bfdbfe;
  content: '';
  position: absolute;
}

.workflow-flow-join::before {
  height: 2px;
  left: calc(50% - var(--workflow-join-offset));
  right: calc(50% - var(--workflow-join-offset));
  top: 0;
}

.workflow-flow-join::after {
  bottom: 0;
  left: 50%;
  top: 0;
  transform: translateX(-50%);
  width: 2px;
}

.workflow-flow-join span,
.workflow-flow-join span::before {
  height: 0.75rem;
  top: 0;
  width: 2px;
}

.workflow-flow-join span {
  left: calc(50% - var(--workflow-join-offset));
}

.workflow-flow-join span::before {
  left: calc(var(--workflow-join-offset) + var(--workflow-join-offset));
}

.workflow-flow-node {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  min-width: 0;
  padding: 0.45rem 0.55rem;
}

.workflow-flow-node small,
.workflow-flow-node strong,
.workflow-flow-node span {
  display: block;
}

.workflow-flow-node small {
  color: #64748b;
  font-size: 0.625rem;
  font-weight: 800;
  line-height: 1.2;
  text-transform: uppercase;
}

.workflow-flow-node strong {
  color: #0f172a;
  font-size: 0.8125rem;
  line-height: 1.3;
  margin-top: 0.2rem;
}

.workflow-flow-node span {
  color: #64748b;
  font-size: 0.6875rem;
  line-height: 1.35;
  margin-top: 0.2rem;
}

.workflow-node-top {
  align-items: flex-start;
  display: flex;
  gap: 0.4rem;
  justify-content: space-between;
}

.workflow-node-select {
  appearance: none;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  cursor: pointer;
  flex: 0 0 auto;
  font-size: 0.75rem;
  font-weight: 800;
  line-height: 1.2;
  max-width: 6.9rem;
  padding: 0.22rem 1.15rem 0.22rem 0.45rem;
}

.workflow-node-toggle {
  align-items: center;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  gap: 0.35rem;
  min-height: 1.4rem;
  padding: 0.16rem 0.42rem;
}

.workflow-node-toggle input {
  width: 0.8rem;
  height: 0.8rem;
  flex: 0 0 auto;
}

.workflow-node-toggle span {
  color: inherit;
  font-size: 0.6875rem;
  font-weight: 800;
  line-height: 1;
  margin: 0;
}

.workflow-flow-node.is-fixed {
  background: #ffffff;
  border-color: #cbd5e1;
  box-shadow: inset 0 3px 0 #64748b;
}

.workflow-flow-node.is-fixed small {
  color: #475569;
}

.workflow-flow-node.is-policy {
  background: #fffbeb;
  border-color: #fde68a;
  box-shadow: inset 0 3px 0 #f59e0b;
}

.workflow-flow-node.is-policy small {
  color: #b45309;
}

.workflow-flow-node.is-disabled {
  background: #f8fafc;
  border-color: #e2e8f0;
  box-shadow: inset 0 3px 0 #cbd5e1;
  opacity: 0.62;
}

.workflow-flow-arrow {
  align-items: center;
  color: #2563eb;
  display: flex;
  font-size: 0;
  font-weight: 900;
  justify-content: center;
  min-width: 5.5rem;
  position: relative;
}

.workflow-flow-arrow::before {
  background: #60a5fa;
  content: '';
  height: 2px;
  width: 100%;
}

.workflow-flow-arrow::after {
  border-bottom: 4px solid transparent;
  border-left: 6px solid #2563eb;
  border-top: 4px solid transparent;
  content: '';
  position: absolute;
  right: 0;
}

@media (max-width: 1180px) {
  .workflow-flowchart-body {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .workflow-flow-elbow {
    --workflow-elbow-offset: 15rem;
    max-width: 39.5rem;
  }

  .workflow-flow-row {
    grid-template-columns:
      minmax(8rem, 9rem) auto minmax(8rem, 9rem) auto
      minmax(8rem, 9rem);
  }

  .workflow-flow-row.is-two {
    grid-template-columns: minmax(9.75rem, 11.75rem) auto minmax(
        9.75rem,
        11.75rem
      );
  }

  .workflow-flow-branches {
    grid-template-columns: repeat(2, minmax(10.25rem, 11.75rem));
  }

  .workflow-flow-arrow {
    min-width: 4.75rem;
  }

  .workflow-toolbar {
    flex-direction: column;
  }

  .workflow-toolbar-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .workflow-flow-branches {
    grid-template-columns: 1fr;
  }

  .workflow-flow-branches {
    justify-items: center;
  }

  .workflow-flow-row {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .workflow-flow-row.is-two {
    grid-template-columns: 1fr;
  }

  .workflow-flow-arrow {
    min-height: 0.5rem;
    min-width: 3rem;
    transform: rotate(90deg);
  }

  .workflow-flow-arrow::before {
    width: 3rem;
  }

  .workflow-flow-split::before,
  .workflow-flow-split::after,
  .workflow-flow-branches::before,
  .workflow-flow-elbow,
  .workflow-flow-join {
    display: none;
  }

  .workflow-flow-split .workflow-flow-node {
    max-width: 14rem;
  }

  .workflow-flow-node {
    width: min(100%, 14rem);
  }

  .workflow-node-top {
    align-items: stretch;
    flex-direction: column;
  }

  .workflow-node-select,
  .workflow-node-toggle {
    width: 100%;
  }
}
</style>
