<template>
  <section class="workflow-panel">
    <div class="workflow-toolbar">
      <div>
        <p class="workflow-eyebrow">Workflow</p>
        <h3>上架流程配置</h3>
        <p>配置按平台生效，保存后上架工作台会按这里的免审和审批策略加载。</p>
      </div>
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

    <div v-else-if="workflow" class="workflow-grid">
      <div class="workflow-map">
        <div class="workflow-runtime">
          <span>当前平台：{{ workflow.platform_name }}</span>
          <span>
            免审利润率：
            {{ runtime.auto_approve_max_margin_rate ?? '-' }}%
          </span>
          <span>
            飞书审批：
            {{ policies.feishu_approval_enabled ? '启用' : '未启用' }}
          </span>
        </div>

        <div class="workflow-lanes">
          <div v-for="lane in lanes" :key="lane.key" class="workflow-lane">
            <div class="workflow-lane-title">
              <span>{{ lane.label }}</span>
              <small>{{ nodesByLane(lane.key).length }} 个节点</small>
            </div>
            <div class="workflow-node-list">
              <article
                v-for="node in nodesByLane(lane.key)"
                :key="node.id"
                class="workflow-node"
                :class="[
                  node.enabled === false ? 'is-disabled' : '',
                  `status-${node.status || 'implemented'}`
                ]"
              >
                <div class="workflow-node-header">
                  <span class="workflow-node-dot"></span>
                  <strong>{{ node.label }}</strong>
                </div>
                <p>{{ node.description || node.id }}</p>
                <div class="workflow-node-meta">
                  <span>{{ nodeStatusLabel(node.status) }}</span>
                  <span>{{
                    node.enabled === false ? '已停用' : '已启用'
                  }}</span>
                </div>
              </article>
            </div>
          </div>
        </div>

        <div class="workflow-edge-band">
          <div class="workflow-edge-title">条件连线</div>
          <div class="workflow-edge-list">
            <span
              v-for="edge in editableConfig.edges"
              :key="edge.id"
              class="workflow-edge"
              :class="{ 'is-disabled': edge.enabled === false }"
            >
              {{ nodeLabel(edge.from) }} → {{ nodeLabel(edge.to) }}
              <em>{{ edge.label }}</em>
            </span>
          </div>
        </div>
      </div>

      <aside class="workflow-editor">
        <section class="workflow-editor-section">
          <h4>策略开关</h4>
          <label
            v-for="policy in policyOptions"
            :key="policy.key"
            class="workflow-switch-row"
          >
            <span>
              <strong>{{ policy.label }}</strong>
              <small>{{ policy.description }}</small>
            </span>
            <input
              v-model="editableConfig.policies[policy.key]"
              type="checkbox"
            />
          </label>
        </section>

        <section class="workflow-editor-section">
          <h4>节点控制</h4>
          <label
            v-for="node in editableConfig.nodes"
            :key="node.id"
            class="workflow-switch-row compact"
          >
            <span>
              <strong>{{ node.label }}</strong>
              <small>{{ node.id }}</small>
            </span>
            <input v-model="node.enabled" type="checkbox" />
          </label>
        </section>

        <section class="workflow-editor-section">
          <h4>生效说明</h4>
          <ul class="workflow-impact-list">
            <li>免审开关关闭后，上架工作台不再显示“免审通过”状态。</li>
            <li>
              飞书审批开启后，流程图展示审批路径；审批提交接口仍需后续接入。
            </li>
            <li>下架审批开关用于预留下架审批路径，不改变现有下架状态机。</li>
          </ul>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import BaseLoading from '@/components/ui/BaseLoading.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { llmOpsApi } from '@/api/llmOps'
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

const lanes = [
  { key: 'pricing', label: '价格准备' },
  { key: 'approval', label: '审批判断' },
  { key: 'publishing', label: '发布/下架' }
]

const policyOptions = [
  {
    key: 'auto_approve_enabled',
    label: '启用免审路径',
    description: '低于平台免审利润率时展示免审确认路径'
  },
  {
    key: 'manual_confirm_required',
    label: '保留人工确认',
    description: '保留现有 confirm_publish / confirm_update 操作'
  },
  {
    key: 'feishu_approval_enabled',
    label: '启用飞书审批路径',
    description: '高于免审阈值时展示飞书审批路径'
  },
  {
    key: 'auto_apply_after_approval',
    label: '审批通过后自动发布',
    description: '审批通过后可自动执行确认发布动作'
  },
  {
    key: 'offline_approval_enabled',
    label: '启用下架审批',
    description: '下架操作进入审批路径后再确认下架'
  }
]

const platformOptions = computed(() =>
  props.platforms.map((platform) => ({
    label: platform.name,
    value: String(platform.id)
  }))
)

const editableConfig = computed(() => workflow.value?.config || {})
const policies = computed(() => editableConfig.value.policies || {})
const runtime = computed(() => editableConfig.value.runtime || {})

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
    workflow.value = clone(response.data)
    syncPolicyEdges()
  } catch (error) {
    showError(errorMessage(error) || '加载上架流程配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!workflow.value || !localPlatformId.value) return
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
    workflow.value = clone(response.data)
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
    workflow.value = clone(response.data)
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
  setNodeEnabled('feishu_approval', config.policies.feishu_approval_enabled)
  setEdgeEnabled('gate_to_auto', config.policies.auto_approve_enabled)
  setEdgeEnabled('auto_to_online', config.policies.auto_approve_enabled)
  setEdgeEnabled('gate_to_manual', config.policies.manual_confirm_required)
  setEdgeEnabled('manual_to_online', config.policies.manual_confirm_required)
  setEdgeEnabled('gate_to_feishu', config.policies.feishu_approval_enabled)
  setEdgeEnabled('feishu_to_online', config.policies.feishu_approval_enabled)
}

function setNodeEnabled(id, enabled) {
  const node = editableConfig.value.nodes.find((item) => item.id === id)
  if (node) node.enabled = Boolean(enabled)
}

function setEdgeEnabled(id, enabled) {
  const edge = editableConfig.value.edges.find((item) => item.id === id)
  if (edge) edge.enabled = Boolean(enabled)
}

function nodesByLane(lane) {
  return (editableConfig.value.nodes || []).filter(
    (node) => (node.lane || 'pricing') === lane
  )
}

function nodeLabel(id) {
  const node = (editableConfig.value.nodes || []).find((item) => item.id === id)
  return node?.label || id
}

function nodeStatusLabel(status) {
  const labels = {
    configurable: '可配置',
    implemented: '已实现',
    planned: '规划中'
  }
  return labels[status] || '已实现'
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

.workflow-toolbar h3 {
  margin: 0.25rem 0 0;
  color: #0f172a;
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: 0;
}

.workflow-toolbar p {
  margin: 0.35rem 0 0;
  max-width: 48rem;
  color: #64748b;
  font-size: 0.875rem;
  line-height: 1.5;
}

.workflow-eyebrow {
  margin: 0;
  color: #2563eb;
  font-size: 0.6875rem;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
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

.workflow-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
}

.workflow-map,
.workflow-editor {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.workflow-map {
  min-width: 0;
  padding: 1rem;
}

.workflow-runtime {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.workflow-runtime span,
.workflow-edge {
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.65rem;
}

.workflow-lanes {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.workflow-lane {
  min-width: 0;
}

.workflow-lane-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #334155;
  font-size: 0.8125rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
}

.workflow-lane-title small {
  color: #94a3b8;
  font-size: 0.6875rem;
  font-weight: 700;
}

.workflow-node-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.workflow-node {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #f8fafc;
  padding: 0.75rem;
}

.workflow-node.is-disabled,
.workflow-edge.is-disabled {
  opacity: 0.45;
}

.workflow-node.status-planned {
  border-color: #fed7aa;
  background: #fff7ed;
}

.workflow-node.status-configurable {
  border-color: #bae6fd;
  background: #f0f9ff;
}

.workflow-node-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.workflow-node-header strong {
  min-width: 0;
  color: #0f172a;
  font-size: 0.875rem;
  line-height: 1.35;
}

.workflow-node-dot {
  width: 0.5rem;
  height: 0.5rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #2563eb;
}

.workflow-node p {
  margin: 0.5rem 0 0;
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.45;
}

.workflow-node-meta {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.65rem;
}

.workflow-node-meta span {
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 0.6875rem;
  font-weight: 800;
  padding: 0.2rem 0.45rem;
}

.workflow-edge-band {
  border-top: 1px solid #e2e8f0;
  margin-top: 1rem;
  padding-top: 1rem;
}

.workflow-edge-title {
  color: #334155;
  font-size: 0.8125rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
}

.workflow-edge-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.workflow-edge em {
  color: #64748b;
  font-style: normal;
  font-weight: 600;
  margin-left: 0.4rem;
}

.workflow-editor {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.workflow-editor-section h4 {
  margin: 0 0 0.65rem;
  color: #0f172a;
  font-size: 0.875rem;
  font-weight: 800;
}

.workflow-switch-row {
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
  padding: 0.7rem;
}

.workflow-switch-row + .workflow-switch-row {
  margin-top: 0.5rem;
}

.workflow-switch-row strong,
.workflow-switch-row small {
  display: block;
}

.workflow-switch-row strong {
  color: #0f172a;
  font-size: 0.8125rem;
}

.workflow-switch-row small {
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.4;
  margin-top: 0.2rem;
}

.workflow-switch-row input {
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
}

.workflow-switch-row.compact {
  padding: 0.55rem 0.65rem;
}

.workflow-impact-list {
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.55;
  margin: 0;
  padding-left: 1rem;
}

@media (max-width: 1180px) {
  .workflow-grid,
  .workflow-lanes {
    grid-template-columns: 1fr;
  }

  .workflow-toolbar {
    flex-direction: column;
  }

  .workflow-toolbar-actions {
    justify-content: flex-start;
  }
}
</style>
