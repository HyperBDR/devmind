<template>
  <section class="audit-log-panel">
    <div class="panel audit-filter-panel">
      <div class="audit-filter-grid">
        <label class="form-field audit-filter-field">
          <span class="field-label">大类</span>
          <CompactSelect
            v-model="filters.target_type"
            :options="businessCategoryOptions"
            class-name="audit-filter-select w-full"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">操作动作</span>
          <CompactSelect
            v-model="filters.action"
            :options="actionOptions"
            class-name="audit-filter-select w-full"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">实例名称</span>
          <input
            id="audit-target"
            v-model.trim="filters.target"
            class="audit-filter-input"
            name="target"
            placeholder="如 DeepSeek R1"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">操作人</span>
          <input
            id="audit-actor"
            v-model.trim="filters.actor"
            class="audit-filter-input"
            name="actor"
            placeholder="如 ops"
          />
        </label>
      </div>

      <div class="audit-filter-actions">
        <button
          type="button"
          class="btn-primary btn-action-search"
          :disabled="loading"
          @click="applyFilters"
        >
          查询
        </button>
        <button
          type="button"
          class="btn-secondary btn-action-reset"
          :disabled="loading"
          @click="resetFilters"
        >
          重置
        </button>
        <span class="audit-count"> {{ totalCount }} 条记录 </span>
      </div>
    </div>

    <div class="panel audit-table-panel">
      <div v-if="errorMessage" class="audit-error">
        {{ errorMessage }}
      </div>

      <div class="audit-table-scroll">
        <table class="data-table audit-table">
          <colgroup>
            <col class="audit-col-category" />
            <col class="audit-col-platform" />
            <col class="audit-col-instance" />
            <col class="audit-col-actor" />
            <col class="audit-col-time" />
            <col class="audit-col-change" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-head">大类</th>
              <th class="table-head">平台</th>
              <th class="table-head">实例</th>
              <th class="table-head">操作人</th>
              <th class="table-head">操作时间</th>
              <th class="table-head">变更内容</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="row.id">
              <tr class="audit-row" @click="toggleExpanded(row.id)">
                <td class="table-cell">
                  <div class="audit-kind-stack">
                    <span
                      :class="[
                        'audit-pill',
                        auditBusinessCategoryTone(row.target_type)
                      ]"
                    >
                      {{ auditBusinessCategoryLabel(row.target_type) }}
                    </span>
                  </div>
                </td>
                <td class="table-cell">
                  <span class="audit-platform-label">
                    {{ platformLabel(row) }}
                  </span>
                </td>
                <td class="table-cell">
                  <p class="font-medium text-slate-900">
                    {{ instanceLabel(row) }}
                  </p>
                  <p
                    v-if="channelModelLabel(row)"
                    class="audit-instance-channel"
                  >
                    {{ channelModelLabel(row) }}
                  </p>
                </td>
                <td class="table-cell">
                  <p class="font-medium text-slate-900">
                    {{ actorLabel(row) }}
                  </p>
                </td>
                <td class="table-cell audit-time">
                  {{ formatDateTime(row.created_at) }}
                </td>
                <td class="table-cell audit-change-cell">
                  <div
                    v-if="changeSummaryItems(row).length"
                    class="audit-inline-changes"
                  >
                    <div
                      v-for="item in changeSummaryPreviewItems(row)"
                      :key="item.key"
                      class="audit-inline-change"
                    >
                      <span class="audit-inline-label">{{ item.label }}</span>
                      <span
                        :class="
                          item.isStatus
                            ? statusValueClass(item.before)
                            : 'audit-inline-value'
                        "
                      >
                        {{ item.before }}
                      </span>
                      <span class="audit-inline-arrow">→</span>
                      <strong
                        :class="
                          item.isStatus
                            ? statusValueClass(item.after)
                            : 'audit-inline-value is-after'
                        "
                      >
                        {{ item.after }}
                      </strong>
                    </div>
                    <span
                      v-if="extraChangeCount(row)"
                      class="audit-more-change"
                    >
                      +{{ extraChangeCount(row) }} 项
                    </span>
                  </div>
                  <span v-else class="audit-muted">
                    {{ row.summary || '未记录字段变更' }}
                  </span>
                </td>
              </tr>
              <tr v-if="expandedId === row.id">
                <td class="detail-cell" colspan="6">
                  <div class="audit-detail-grid">
                    <div class="audit-detail-block">
                      <h4>状态变更</h4>
                      <div
                        v-if="statusChangeItems(row).length"
                        class="audit-change-list"
                      >
                        <div
                          v-for="item in statusChangeItems(row)"
                          :key="item.key"
                          class="audit-change-row"
                        >
                          <span class="audit-change-key">{{ item.label }}</span>
                          <span :class="statusValueClass(item.before)">
                            {{ item.before }}
                          </span>
                          <span class="audit-change-arrow">→</span>
                          <strong :class="statusValueClass(item.after)">
                            {{ item.after }}
                          </strong>
                        </div>
                      </div>
                      <p v-else class="audit-muted">未记录状态变更。</p>
                    </div>
                    <div class="audit-detail-block">
                      <h4>内容变更</h4>
                      <div
                        v-if="contentChangeItems(row).length"
                        class="audit-change-list"
                      >
                        <div
                          v-for="item in contentChangeItems(row)"
                          :key="item.key"
                          class="audit-change-row"
                        >
                          <span class="audit-change-key">{{ item.label }}</span>
                          <span>{{ item.before }}</span>
                          <span class="audit-change-arrow">→</span>
                          <strong>{{ item.after }}</strong>
                        </div>
                      </div>
                      <p v-else class="audit-muted">未记录内容字段差异。</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && !rows.length">
              <td class="table-cell" colspan="6">
                <div class="empty-state">
                  <p class="font-medium text-slate-700">暂无操作记录</p>
                  <p class="mt-1 text-sm text-slate-500">
                    调整筛选条件，或完成一次渠道、价格、上架、审批操作后再查询。
                  </p>
                </div>
              </td>
            </tr>
            <tr v-if="loading">
              <td class="table-cell" colspan="6">正在加载操作记录...</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="audit-table-footer">
        <div class="audit-footer-summary">
          <span class="audit-count">{{ pageRangeLabel }}</span>
        </div>
        <div class="audit-footer-controls">
          <label class="audit-footer-page-size">
            <span>每页</span>
            <CompactSelect
              v-model="filters.page_size"
              :options="pageSizeOptions"
              class-name="audit-page-size-select"
            />
          </label>
          <div class="audit-pagination">
            <button
              type="button"
              class="btn-secondary audit-page-button"
              :disabled="loading || page <= 1"
              @click="goToPage(page - 1)"
            >
              上一页
            </button>
            <span class="audit-page-label">{{ page }} / {{ totalPages }}</span>
            <button
              type="button"
              class="btn-secondary audit-page-button"
              :disabled="loading || page >= totalPages"
              @click="goToPage(page + 1)"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  channels: {
    type: Array,
    default: () => []
  }
})

const actionOptions = [
  { label: '全部动作', value: '' },
  { label: '创建', value: 'create' },
  { label: '更新', value: 'update' },
  { label: '删除', value: 'delete' },
  { label: '采集', value: 'collect' },
  { label: '导入', value: 'import' },
  { label: '批量提交', value: 'bulk_upsert' },
  { label: '保存草稿', value: 'bulk_draft' },
  { label: '批量替换', value: 'bulk_replace' },
  { label: '审批流转', value: 'transition' },
  { label: '下架', value: 'offline' },
  { label: '恢复', value: 'restore' },
  { label: '同步', value: 'sync' }
]

const businessCategoryOptions = [
  { label: '全部大类', value: '' },
  {
    label: '模型挂售',
    value: [
      'llm_ops.ResaleListing',
      'llm_ops.ResaleListingExclusion',
      'llm_ops.ResalePlatform'
    ].join(',')
  },
  {
    label: '渠道配置',
    value: [
      'llm_ops.ProcurementChannel',
      'llm_ops.ChannelModelPrice',
      'llm_ops.ChannelPriceItem'
    ].join(',')
  },
  {
    label: '元模型',
    value: [
      'llm_ops.LLMProvider',
      'llm_ops.LLMModel',
      'llm_ops.MetaModel'
    ].join(',')
  },
  { label: '模型价格', value: 'llm_ops.ModelPriceItem' },
  { label: '价格源配置', value: 'llm_ops.PriceCollectionSource' },
  { label: '用量对账', value: 'llm_ops.UsageReconciliationRecord' }
]

const pageSizeOptions = [
  { label: '20 条/页', value: '20' },
  { label: '50 条/页', value: '50' },
  { label: '100 条/页', value: '100' }
]

const statusFieldKeys = new Set([
  'comparison_status',
  'is_active',
  'is_current',
  'is_enabled',
  'is_listed',
  'publish_status',
  'status',
  'updates_model_prices',
  'workflow_status'
])

const auditBusinessCategoryLabels = {
  'llm_ops.ChannelModelPrice': '渠道配置',
  'llm_ops.ChannelPriceItem': '渠道配置',
  'llm_ops.LLMModel': '元模型',
  'llm_ops.LLMProvider': '元模型',
  'llm_ops.MetaModel': '元模型',
  'llm_ops.ModelPriceItem': '模型价格',
  'llm_ops.PriceCollectionSource': '价格源配置',
  'llm_ops.ProcurementChannel': '渠道配置',
  'llm_ops.ResaleListing': '模型挂售',
  'llm_ops.ResaleListingExclusion': '模型挂售',
  'llm_ops.ResalePlatform': '模型挂售',
  'llm_ops.UsageReconciliationRecord': '用量对账'
}

const targetTypeLabels = {
  'llm_ops.ChannelModelPrice': '渠道模型配置',
  'llm_ops.ChannelPriceItem': '渠道价格项',
  'llm_ops.LLMModel': '模型',
  'llm_ops.LLMProvider': '元模型厂商',
  'llm_ops.MetaModel': '元模型',
  'llm_ops.ModelPriceItem': '模型价格',
  'llm_ops.PriceCollectionSource': '价格源',
  'llm_ops.ProcurementChannel': '渠道',
  'llm_ops.ResaleListing': '模型挂售',
  'llm_ops.ResaleListingExclusion': '挂售排除',
  'llm_ops.ResalePlatform': '挂售平台',
  'llm_ops.UsageReconciliationRecord': '对账记录'
}

const auditBusinessCategoryTones = {
  'llm_ops.ChannelModelPrice': 'tone-info',
  'llm_ops.ChannelPriceItem': 'tone-info',
  'llm_ops.LLMModel': 'tone-primary',
  'llm_ops.LLMProvider': 'tone-primary',
  'llm_ops.MetaModel': 'tone-primary',
  'llm_ops.ModelPriceItem': 'tone-success',
  'llm_ops.PriceCollectionSource': 'tone-muted',
  'llm_ops.ProcurementChannel': 'tone-info',
  'llm_ops.ResaleListing': 'tone-warn',
  'llm_ops.ResaleListingExclusion': 'tone-warn',
  'llm_ops.ResalePlatform': 'tone-warn',
  'llm_ops.UsageReconciliationRecord': 'tone-danger'
}

const fieldLabels = {
  aliases: '别名',
  api_endpoint: 'API Endpoint',
  base_price_item_id: '基准价格项',
  billing_unit: '计费单位',
  capabilities: '能力',
  channel_id: '渠道',
  code: '编码',
  comparison_status: '价格对比状态',
  context_window: '上下文窗口',
  currency: '币种',
  custom_audio_input_price_per_second: '自定义音频输入价',
  custom_audio_output_price_per_second: '自定义音频输出价',
  custom_input_price_per_million: '自定义输入价',
  custom_output_price_per_million: '自定义输出价',
  custom_video_input_price_per_second: '自定义视频输入价',
  custom_video_output_price_per_second: '自定义视频输出价',
  custom_video_resolution_prices: '自定义视频分辨率价格',
  delta_amount: '价差金额',
  delta_percent: '价差比例',
  dimension: '计费维度',
  endpoint_url: '端点 URL',
  family: '模型族',
  fee_rate: '费率',
  is_active: '启用状态',
  is_current: '当前版本',
  is_enabled: '采集状态',
  is_listed: '渠道上架状态',
  latency_ms: '延迟',
  max_output_tokens: '最大输出 Token',
  meta_model_id: '元模型',
  metadata: '扩展信息',
  modality: '模态',
  model_id: '模型',
  name: '名称',
  notes: '备注',
  platform_id: '平台',
  point_name: '点数名称',
  point_rounding_mode: '点数取整',
  points_per_currency_unit: '点数换算',
  price_fingerprint: '价格指纹',
  price_source_id: '价格来源',
  price_source_type: '价格来源类型',
  provider_id: '厂商',
  publish_status: '发布状态',
  reason: '原因',
  retail_audio_input_price_per_second: '零售音频输入价',
  retail_audio_output_price_per_second: '零售音频输出价',
  retail_cache_input_price_per_million: '零售缓存输入价',
  retail_image_output_price_per_image: '零售图片输出价',
  retail_input_price_per_million: '零售输入价',
  retail_output_price_per_million: '零售输出价',
  retail_video_input_price_per_second: '零售视频输入价',
  retail_video_output_price_per_second: '零售视频输出价',
  retail_video_resolution_prices: '零售视频分辨率价格',
  rpm_limit: 'RPM 限制',
  service_fee_rate: '服务费率',
  settlement_ratio: '结算比例',
  source_category: '价格源分类',
  source_id: '价格源',
  source_type: '价格源类型',
  source_url: '来源 URL',
  spec: '规格',
  status: '状态',
  tier_end: '阶梯结束',
  tier_start: '阶梯起始',
  tier_type: '阶梯类型',
  tpm_limit: 'TPM 限制',
  unit_price: '单价',
  updates_model_prices: '更新模型价格',
  website: '官网',
  workflow_status: '流程状态'
}

const valueLabelsByField = {
  comparison_status: {
    above_official: '高于上游价',
    below_official: '低于上游价',
    same_as_official: '等于上游价',
    unknown: '待判断'
  },
  publish_status: {
    deleted: '已删除',
    none: '未发布',
    offline: '已下架',
    online: '已发布'
  },
  status: {
    active: '启用',
    draft: '草稿',
    failed: '失败',
    inactive: '停用',
    matched: '已匹配',
    mismatch: '不一致',
    pending: '待处理',
    retired: '停用',
    unmatched: '未匹配'
  },
  workflow_status: {
    deleted: '已失效',
    draft: '草稿',
    offline: '已下架',
    offline_exception: '下架异常',
    online: '已上架',
    pending_offline: '待下架',
    pending_publish: '待发布',
    pending_update: '待更新',
    update_draft: '更新草稿'
  }
}

const filters = reactive({
  action: '',
  target_type: '',
  target: '',
  actor: '',
  page_size: '20'
})

const rows = ref([])
const page = ref(1)
const totalCount = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const expandedId = ref(null)

const pageSizeNumber = computed(() => Number(filters.page_size || 20))

const totalPages = computed(() =>
  Math.max(Math.ceil(totalCount.value / pageSizeNumber.value), 1)
)

const pageRangeLabel = computed(() => {
  if (!totalCount.value) return '0 条记录'
  const start = (page.value - 1) * pageSizeNumber.value + 1
  const end = Math.min(page.value * pageSizeNumber.value, totalCount.value)
  return `${start}-${end} / ${totalCount.value} 条记录`
})

watch(
  () => filters.page_size,
  () => {
    page.value = 1
    loadAuditLogs()
  }
)

onMounted(() => {
  loadAuditLogs()
})

function applyFilters() {
  page.value = 1
  loadAuditLogs()
}

function resetFilters() {
  filters.action = ''
  filters.target_type = ''
  filters.target = ''
  filters.actor = ''
  filters.page_size = '20'
  page.value = 1
  loadAuditLogs()
}

function goToPage(nextPage) {
  page.value = Math.min(Math.max(Number(nextPage) || 1, 1), totalPages.value)
  loadAuditLogs()
}

async function loadAuditLogs() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await llmOpsApi.listAuditLogs(queryParams())
    const payload = response?.data?.data || response?.data || {}
    rows.value = Array.isArray(payload.results)
      ? payload.results
      : Array.isArray(payload)
        ? payload
        : []
    totalCount.value = Number(payload.count ?? rows.value.length)
  } catch (error) {
    rows.value = []
    totalCount.value = 0
    errorMessage.value =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '操作记录加载失败'
  } finally {
    loading.value = false
  }
}

function queryParams() {
  const params = {
    page: page.value,
    page_size: filters.page_size
  }
  Object.entries(filters).forEach(([key, value]) => {
    if (key === 'page_size') return
    const normalized = String(value || '').trim()
    if (normalized) params[key] = normalized
  })
  return params
}

function toggleExpanded(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function actorLabel(row) {
  return row.actor_username || row.actor_identifier || 'anonymous'
}

function targetTypeLabel(value) {
  return targetTypeLabels[value] || value || '-'
}

function platformLabel(row) {
  if (row.target_type !== 'llm_ops.ResaleListing') return '-'
  return splitTargetRepr(row.target_repr).platform || '-'
}

function instanceLabel(row) {
  const parsed = splitTargetRepr(row.target_repr)
  return parsed.instance || row.target_id || '-'
}

function channelModelLabel(row) {
  const channel = channelName(row)
  if (!channel || channel === '-') return ''
  return `渠道：${channel}`
}

function channelName(row) {
  const channelId = snapshotValue(row, 'channel_id')
  if (!channelId) return '-'
  return (
    props.channels.find((channel) => String(channel.id) === String(channelId))
      ?.name || `渠道 #${channelId}`
  )
}

function snapshotValue(row, key) {
  return (
    row?.after?.[key] ??
    row?.before?.[key] ??
    row?.changes?.[key]?.after ??
    row?.changes?.[key]?.before ??
    null
  )
}

function splitTargetRepr(value) {
  const text = String(value || '').trim()
  if (!text) {
    return {
      instance: '',
      platform: ''
    }
  }
  const parts = text.split(/\s+\/\s+/)
  if (parts.length < 2) {
    return {
      instance: text,
      platform: ''
    }
  }
  return {
    instance: parts.slice(1).join(' / '),
    platform: parts[0]
  }
}

function auditBusinessCategoryLabel(targetType) {
  return (
    auditBusinessCategoryLabels[targetType] ||
    targetTypeLabel(targetType) ||
    '-'
  )
}

function auditBusinessCategoryTone(targetType) {
  return auditBusinessCategoryTones[targetType] || 'tone-muted'
}

function changeKeys(row) {
  return Object.keys(row?.changes || {})
}

function changeSummaryItems(row) {
  return changeItems(row)
}

function changeSummaryPreviewItems(row) {
  return changeSummaryItems(row).slice(0, 4)
}

function extraChangeCount(row) {
  return Math.max(changeSummaryItems(row).length - 4, 0)
}

function statusChangeItems(row) {
  return changeItems(row).filter((item) => statusFieldKeys.has(item.key))
}

function contentChangeItems(row) {
  return changeItems(row).filter((item) => !statusFieldKeys.has(item.key))
}

function changeItems(row) {
  return changeKeys(row).map((key) => {
    const change = row.changes[key] || {}
    return {
      after: formatChangeValue(key, change.after),
      before: formatChangeValue(key, change.before),
      isStatus: statusFieldKeys.has(key),
      key,
      label: fieldLabel(key)
    }
  })
}

function fieldLabel(key) {
  return fieldLabels[key] || key
}

function formatChangeValue(key, value) {
  if (Object.prototype.hasOwnProperty.call(valueLabelsByField, key)) {
    const normalized = compactValue(value)
    return valueLabelsByField[key][normalized] || normalized
  }
  return compactValue(value)
}

function compactValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function statusValueClass(value) {
  if (['停用', '已删除', '已失效', '已下架', '否'].includes(value)) {
    return 'audit-status-value tone-muted'
  }
  if (['失败', '不一致', '下架异常'].includes(value)) {
    return 'audit-status-value tone-danger'
  }
  if (
    ['待发布', '待更新', '待下架', '待处理', '草稿', '更新草稿'].includes(value)
  ) {
    return 'audit-status-value tone-warn'
  }
  if (['启用', '已上架', '已发布', '已匹配', '是'].includes(value)) {
    return 'audit-status-value tone-success'
  }
  return 'audit-status-value tone-info'
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>

<style scoped>
.audit-log-panel {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 1.25rem;
  min-height: 0;
}

.audit-filter-panel {
  flex: 0 0 auto;
}

.audit-filter-grid {
  align-items: end;
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(1, minmax(0, 1fr));
}

.audit-filter-field {
  display: grid;
  gap: 0.375rem;
  min-width: 0;
}

.audit-filter-field .field-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 1rem;
}

.audit-filter-input {
  border: 1px solid #dbe4f0;
  border-radius: 0.5rem;
  background: #ffffff;
  box-sizing: border-box;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  height: 36px;
  line-height: 1.25rem;
  min-width: 0;
  outline: none;
  padding: 0 0.75rem;
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease,
    color 150ms ease;
  width: 100%;
}

.audit-filter-input::placeholder {
  color: #94a3b8;
  font-weight: 500;
}

.audit-filter-input:hover {
  border-color: #cbd5e1;
}

.audit-filter-input:focus {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
}

:deep(.audit-filter-select.compact-select) {
  width: 100%;
}

:deep(.audit-filter-select .compact-select-trigger) {
  border-color: #dbe4f0;
  border-radius: 0.5rem;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  height: 36px;
  line-height: 1.25rem;
  min-height: 36px;
  padding: 0 0.75rem;
}

:deep(.audit-filter-select .compact-select-trigger:hover:not(:disabled)) {
  border-color: #cbd5e1;
  background: #ffffff;
}

:deep(.audit-filter-select .compact-select-trigger:focus) {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
}

:deep(.audit-filter-select .compact-select-caret) {
  color: #64748b;
}

:deep(.audit-filter-select .compact-select-menu) {
  border-color: #dbe4f0;
  border-radius: 0.625rem;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
}

.audit-filter-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.audit-filter-actions .btn-primary,
.audit-filter-actions .btn-secondary {
  min-height: 36px;
  padding: 0.5rem 0.875rem;
}

.audit-count {
  color: #64748b;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
}

.audit-pagination {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}

.audit-page-button {
  min-height: 32px;
  padding: 0 0.75rem;
}

.audit-page-label {
  color: #475569;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
}

.audit-table-footer {
  align-items: center;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  flex: 0 0 auto;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.75rem 1rem;
}

.audit-footer-summary,
.audit-footer-controls,
.audit-footer-page-size {
  align-items: center;
  display: flex;
  min-width: 0;
}

.audit-footer-controls {
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: flex-end;
}

.audit-footer-page-size {
  color: #64748b;
  gap: 0.5rem;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

:deep(.audit-page-size-select.compact-select) {
  width: 7.5rem;
}

:deep(.audit-page-size-select .compact-select-trigger) {
  border-color: #dbe4f0;
  border-radius: 0.5rem;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  height: 32px;
  min-height: 32px;
  padding: 0 0.625rem;
}

.audit-error {
  border-bottom: 1px solid #fecdd3;
  background: #fff1f2;
  color: #be123c;
  font-size: 13px;
  padding: 0.75rem 1rem;
}

.audit-table-panel {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.audit-table-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}

.audit-table {
  min-width: 1100px;
}

.audit-table thead th {
  position: sticky;
  text-align: center;
  top: 0;
  z-index: 2;
}

.audit-table th,
.audit-table td {
  vertical-align: middle;
}

.audit-table td:not(.audit-change-cell) {
  text-align: center;
}

.audit-col-category {
  width: 130px;
}

.audit-col-platform {
  width: 130px;
}

.audit-col-instance {
  width: 180px;
}

.audit-col-actor {
  width: 150px;
}

.audit-col-time {
  width: 170px;
}

.audit-col-change {
  width: auto;
}

.audit-row {
  cursor: pointer;
}

.audit-time {
  white-space: nowrap;
}

.audit-kind-stack {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.audit-platform-label,
.audit-instance-channel,
.audit-instance-repr {
  color: #64748b;
  font-size: 12px;
  line-height: 1.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-platform-label {
  color: #0f172a;
  display: block;
  font-weight: 700;
  margin: 0 auto;
  max-width: 8rem;
}

.audit-instance-channel {
  margin-left: auto;
  margin-right: auto;
  margin-top: 0.25rem;
  max-width: 13rem;
}

.audit-instance-repr {
  margin-top: 0.25rem;
  max-width: 18rem;
}

.audit-pill,
.audit-action {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  justify-content: center;
  line-height: 1;
  min-height: 24px;
  padding: 0 0.625rem;
  white-space: nowrap;
}

.audit-change-cell {
  min-width: 0;
}

.audit-inline-changes {
  display: grid;
  gap: 0.375rem;
  min-width: 0;
}

.audit-inline-change {
  align-items: center;
  display: grid;
  gap: 0.375rem;
  grid-template-columns: minmax(86px, 0.45fr) minmax(0, 1fr) auto minmax(0, 1fr);
  min-width: 0;
  text-align: left;
}

.audit-inline-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-inline-value {
  color: #475569;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-inline-value.is-after {
  color: #0f172a;
  font-weight: 700;
}

.audit-inline-arrow {
  color: #94a3b8;
  font-size: 12px;
}

.audit-more-change {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.tone-info {
  background: #eff6ff;
  color: #1d4ed8;
}

.tone-success {
  background: #ecfdf5;
  color: #047857;
}

.tone-primary {
  background: #eef2ff;
  color: #4f46e5;
}

.tone-warn {
  background: #fffbeb;
  color: #b45309;
}

.tone-danger {
  background: #fff1f2;
  color: #be123c;
}

.tone-muted {
  background: #f1f5f9;
  color: #475569;
}

.audit-change-count {
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  display: inline-flex;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  font-weight: 700;
  justify-content: center;
  min-width: 28px;
  padding: 0.25rem 0.5rem;
}

.audit-detail-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: minmax(0, 1fr);
  text-align: left;
}

.audit-detail-block {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.875rem;
}

.audit-detail-block h4 {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  margin: 0 0 0.75rem;
}

.audit-change-list {
  display: grid;
  gap: 0.5rem;
}

.audit-change-row {
  align-items: center;
  display: grid;
  gap: 0.5rem;
  grid-template-columns: minmax(120px, 0.6fr) minmax(0, 1fr) auto minmax(0, 1fr);
  min-width: 0;
}

.audit-change-row span,
.audit-change-row strong {
  color: #475569;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-change-row strong {
  color: #0f172a;
}

.audit-status-value {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-family: inherit;
  font-weight: 700;
  justify-content: center;
  justify-self: start;
  line-height: 1;
  max-width: 100%;
  min-height: 24px;
  padding: 0 0.625rem;
}

.audit-status-value.tone-info {
  color: #1d4ed8;
}

.audit-status-value.tone-success {
  color: #047857;
}

.audit-status-value.tone-warn {
  color: #b45309;
}

.audit-status-value.tone-danger {
  color: #be123c;
}

.audit-status-value.tone-muted {
  color: #475569;
}

.audit-change-key {
  color: #64748b;
  font-weight: 700;
}

.audit-change-arrow {
  color: #94a3b8;
}

.audit-muted {
  color: #94a3b8;
  font-size: 13px;
}

@media (min-width: 768px) {
  .audit-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .audit-detail-grid {
    grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
  }
}

@media (min-width: 1280px) {
  .audit-filter-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .audit-pagination {
    justify-content: flex-start;
  }

  .audit-table-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .audit-footer-controls {
    align-items: stretch;
    justify-content: flex-start;
  }

  .audit-change-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .audit-inline-change {
    grid-template-columns: minmax(0, 1fr);
  }

  .audit-change-arrow,
  .audit-inline-arrow {
    display: none;
  }
}
</style>
