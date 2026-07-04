<template>
  <section class="audit-log-panel">
    <div class="panel audit-filter-panel">
      <div class="audit-filter-grid">
        <label class="form-field audit-filter-field">
          <span class="field-label">
            {{ t('llmOps.auditLog.filters.category') }}
          </span>
          <CompactSelect
            v-model="filters.target_type"
            :options="businessCategoryOptions"
            class-name="audit-filter-select w-full"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">
            {{ t('llmOps.auditLog.filters.action') }}
          </span>
          <CompactSelect
            v-model="filters.action"
            :options="actionOptions"
            class-name="audit-filter-select w-full"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">
            {{ t('llmOps.auditLog.filters.target') }}
          </span>
          <input
            id="audit-target"
            v-model.trim="filters.target"
            class="audit-filter-input"
            name="target"
            :placeholder="t('llmOps.auditLog.filters.targetPlaceholder')"
          />
        </label>
        <label class="form-field audit-filter-field">
          <span class="field-label">
            {{ t('llmOps.auditLog.filters.actor') }}
          </span>
          <input
            id="audit-actor"
            v-model.trim="filters.actor"
            class="audit-filter-input"
            name="actor"
            :placeholder="t('llmOps.auditLog.filters.actorPlaceholder')"
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
          {{ t('llmOps.auditLog.actions.search') }}
        </button>
        <button
          type="button"
          class="btn-secondary btn-action-reset"
          :disabled="loading"
          @click="resetFilters"
        >
          {{ t('llmOps.auditLog.actions.reset') }}
        </button>
        <span class="audit-count">
          {{ t('llmOps.auditLog.recordCount', { count: totalCount }) }}
        </span>
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
              <th class="table-head">
                {{ t('llmOps.auditLog.table.category') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.auditLog.table.platform') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.auditLog.table.instance') }}
              </th>
              <th class="table-head">{{ t('llmOps.auditLog.table.actor') }}</th>
              <th class="table-head">{{ t('llmOps.auditLog.table.time') }}</th>
              <th class="table-head">
                {{ t('llmOps.auditLog.table.changes') }}
              </th>
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
                      {{
                        t('llmOps.auditLog.moreChanges', {
                          count: extraChangeCount(row)
                        })
                      }}
                    </span>
                  </div>
                  <span v-else class="audit-muted">
                    {{
                      row.summary || t('llmOps.auditLog.empty.noFieldChanges')
                    }}
                  </span>
                </td>
              </tr>
              <tr v-if="expandedId === row.id">
                <td class="detail-cell" colspan="6">
                  <div class="audit-detail-grid">
                    <div class="audit-detail-block">
                      <h4>{{ t('llmOps.auditLog.detail.statusChanges') }}</h4>
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
                      <p v-else class="audit-muted">
                        {{ t('llmOps.auditLog.empty.noStatusChanges') }}
                      </p>
                    </div>
                    <div class="audit-detail-block">
                      <h4>{{ t('llmOps.auditLog.detail.contentChanges') }}</h4>
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
                      <p v-else class="audit-muted">
                        {{ t('llmOps.auditLog.empty.noContentChanges') }}
                      </p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && !rows.length">
              <td class="table-cell" colspan="6">
                <div class="empty-state">
                  <p class="font-medium text-slate-700">
                    {{ t('llmOps.auditLog.empty.title') }}
                  </p>
                  <p class="mt-1 text-sm text-slate-500">
                    {{ t('llmOps.auditLog.empty.description') }}
                  </p>
                </div>
              </td>
            </tr>
            <tr v-if="loading">
              <td class="table-cell" colspan="6">
                {{ t('llmOps.auditLog.loading') }}
              </td>
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
            <span>{{ t('llmOps.auditLog.pagination.pageSize') }}</span>
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
              {{ t('llmOps.auditLog.pagination.previous') }}
            </button>
            <span class="audit-page-label">{{ page }} / {{ totalPages }}</span>
            <button
              type="button"
              class="btn-secondary audit-page-button"
              :disabled="loading || page >= totalPages"
              @click="goToPage(page + 1)"
            >
              {{ t('llmOps.auditLog.pagination.next') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import '@/components/llm-ops/auditLogPanel.css'

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  channels: {
    type: Array,
    default: () => []
  }
})
const { t } = useI18n()

const actionOptions = computed(() => [
  { label: t('llmOps.auditLog.actionOptions.all'), value: '' },
  { label: t('llmOps.auditLog.actionOptions.create'), value: 'create' },
  { label: t('llmOps.auditLog.actionOptions.update'), value: 'update' },
  { label: t('llmOps.auditLog.actionOptions.delete'), value: 'delete' },
  { label: t('llmOps.auditLog.actionOptions.collect'), value: 'collect' },
  { label: t('llmOps.auditLog.actionOptions.import'), value: 'import' },
  {
    label: t('llmOps.auditLog.actionOptions.bulkUpsert'),
    value: 'bulk_upsert'
  },
  {
    label: t('llmOps.auditLog.actionOptions.bulkDraft'),
    value: 'bulk_draft'
  },
  {
    label: t('llmOps.auditLog.actionOptions.bulkReplace'),
    value: 'bulk_replace'
  },
  {
    label: t('llmOps.auditLog.actionOptions.transition'),
    value: 'transition'
  },
  { label: t('llmOps.auditLog.actionOptions.offline'), value: 'offline' },
  { label: t('llmOps.auditLog.actionOptions.restore'), value: 'restore' },
  { label: t('llmOps.auditLog.actionOptions.sync'), value: 'sync' }
])

const businessCategoryOptions = computed(() => [
  { label: t('llmOps.auditLog.businessCategories.all'), value: '' },
  {
    label: t('llmOps.auditLog.businessCategories.listing'),
    value: [
      'llm_ops.ResaleListing',
      'llm_ops.ResaleListingExclusion',
      'llm_ops.ResalePlatform'
    ].join(',')
  },
  {
    label: t('llmOps.auditLog.businessCategories.channelConfig'),
    value: [
      'llm_ops.ProcurementChannel',
      'llm_ops.ChannelModelPrice',
      'llm_ops.ChannelPriceItem'
    ].join(',')
  },
  {
    label: t('llmOps.auditLog.businessCategories.metaModel'),
    value: [
      'llm_ops.LLMProvider',
      'llm_ops.LLMModel',
      'llm_ops.MetaModel'
    ].join(',')
  },
  {
    label: t('llmOps.auditLog.businessCategories.modelPrice'),
    value: 'llm_ops.ModelPriceItem'
  },
  {
    label: t('llmOps.auditLog.businessCategories.priceSource'),
    value: 'llm_ops.PriceCollectionSource'
  },
  {
    label: t('llmOps.auditLog.businessCategories.reconciliation'),
    value: 'llm_ops.UsageReconciliationRecord'
  }
])

const pageSizeOptions = computed(() =>
  ['20', '50', '100'].map((size) => ({
    label: t('llmOps.auditLog.pagination.pageSizeOption', { size }),
    value: size
  }))
)

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

const auditBusinessCategoryKeys = {
  'llm_ops.ChannelModelPrice': 'channelConfig',
  'llm_ops.ChannelPriceItem': 'channelConfig',
  'llm_ops.LLMModel': 'metaModel',
  'llm_ops.LLMProvider': 'metaModel',
  'llm_ops.MetaModel': 'metaModel',
  'llm_ops.ModelPriceItem': 'modelPrice',
  'llm_ops.PriceCollectionSource': 'priceSource',
  'llm_ops.ProcurementChannel': 'channelConfig',
  'llm_ops.ResaleListing': 'listing',
  'llm_ops.ResaleListingExclusion': 'listing',
  'llm_ops.ResalePlatform': 'listing',
  'llm_ops.UsageReconciliationRecord': 'reconciliation'
}

const targetTypeKeys = {
  'llm_ops.ChannelModelPrice': 'channelModelPrice',
  'llm_ops.ChannelPriceItem': 'channelPriceItem',
  'llm_ops.LLMModel': 'model',
  'llm_ops.LLMProvider': 'provider',
  'llm_ops.MetaModel': 'metaModel',
  'llm_ops.ModelPriceItem': 'modelPrice',
  'llm_ops.PriceCollectionSource': 'priceSource',
  'llm_ops.ProcurementChannel': 'channel',
  'llm_ops.ResaleListing': 'listing',
  'llm_ops.ResaleListingExclusion': 'listingExclusion',
  'llm_ops.ResalePlatform': 'resalePlatform',
  'llm_ops.UsageReconciliationRecord': 'reconciliationRecord'
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

const fieldLabelKeys = {
  aliases: 'aliases',
  api_endpoint: 'apiEndpoint',
  base_price_item_id: 'basePriceItem',
  billing_unit: 'billingUnit',
  capabilities: 'capabilities',
  channel_id: 'channel',
  code: 'code',
  comparison_status: 'comparisonStatus',
  context_window: 'contextWindow',
  currency: 'currency',
  custom_audio_input_price_per_second: 'customAudioInput',
  custom_audio_output_price_per_second: 'customAudioOutput',
  custom_input_price_per_million: 'customInput',
  custom_output_price_per_million: 'customOutput',
  custom_video_input_price_per_second: 'customVideoInput',
  custom_video_output_price_per_second: 'customVideoOutput',
  custom_video_resolution_prices: 'customVideoResolution',
  delta_amount: 'deltaAmount',
  delta_percent: 'deltaPercent',
  dimension: 'dimension',
  endpoint_url: 'endpointUrl',
  family: 'family',
  fee_rate: 'feeRate',
  is_active: 'isActive',
  is_current: 'isCurrent',
  is_enabled: 'isEnabled',
  is_listed: 'isListed',
  latency_ms: 'latency',
  max_output_tokens: 'maxOutputTokens',
  meta_model_id: 'metaModel',
  metadata: 'metadata',
  modality: 'modality',
  model_id: 'model',
  name: 'name',
  notes: 'notes',
  platform_id: 'platform',
  point_name: 'pointName',
  point_rounding_mode: 'pointRoundingMode',
  points_per_currency_unit: 'pointsPerCurrencyUnit',
  price_fingerprint: 'priceFingerprint',
  price_source_id: 'priceSource',
  price_source_type: 'priceSourceType',
  provider_id: 'provider',
  publish_status: 'publishStatus',
  reason: 'reason',
  retail_audio_input_price_per_second: 'retailAudioInput',
  retail_audio_output_price_per_second: 'retailAudioOutput',
  retail_cache_input_price_per_million: 'retailCacheInput',
  retail_image_output_price_per_image: 'retailImageOutput',
  retail_input_price_per_million: 'retailInput',
  retail_output_price_per_million: 'retailOutput',
  retail_video_input_price_per_second: 'retailVideoInput',
  retail_video_output_price_per_second: 'retailVideoOutput',
  retail_video_resolution_prices: 'retailVideoResolution',
  rpm_limit: 'rpmLimit',
  service_fee_rate: 'serviceFeeRate',
  settlement_ratio: 'settlementRatio',
  source_category: 'sourceCategory',
  source_id: 'priceSource',
  source_type: 'sourceType',
  source_url: 'sourceUrl',
  spec: 'spec',
  status: 'status',
  tier_end: 'tierEnd',
  tier_start: 'tierStart',
  tier_type: 'tierType',
  tpm_limit: 'tpmLimit',
  unit_price: 'unitPrice',
  updates_model_prices: 'updatesModelPrices',
  website: 'website',
  workflow_status: 'workflowStatus'
}

const valueLabelKeysByField = {
  comparison_status: {
    above_official: 'aboveOfficial',
    below_official: 'belowOfficial',
    same_as_official: 'sameAsOfficial',
    unknown: 'unknown'
  },
  publish_status: {
    deleted: 'deleted',
    none: 'none',
    offline: 'offline',
    online: 'online'
  },
  status: {
    active: 'active',
    draft: 'draft',
    failed: 'failed',
    inactive: 'inactive',
    matched: 'matched',
    mismatch: 'mismatch',
    pending: 'pending',
    retired: 'retired',
    unmatched: 'unmatched'
  },
  workflow_status: {
    deleted: 'deleted',
    draft: 'draft',
    offline: 'offline',
    offline_exception: 'offlineException',
    online: 'online',
    pending_offline: 'pendingOffline',
    pending_publish: 'pendingPublish',
    pending_update: 'pendingUpdate',
    update_draft: 'updateDraft'
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
  if (!totalCount.value) return t('llmOps.auditLog.pagination.emptyRange')
  const start = (page.value - 1) * pageSizeNumber.value + 1
  const end = Math.min(page.value * pageSizeNumber.value, totalCount.value)
  return t('llmOps.auditLog.pagination.range', {
    count: totalCount.value,
    end,
    start
  })
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
      t('llmOps.auditLog.errors.loadFailed')
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
  const key = targetTypeKeys[value]
  return key ? t(`llmOps.auditLog.targetTypes.${key}`) : value || '-'
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
  return t('llmOps.auditLog.channelPrefix', { name: channel })
}

function channelName(row) {
  const channelId = snapshotValue(row, 'channel_id')
  if (!channelId) return '-'
  return (
    props.channels.find((channel) => String(channel.id) === String(channelId))
      ?.name || t('llmOps.auditLog.channelFallback', { id: channelId })
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
  const key = auditBusinessCategoryKeys[targetType]
  return key
    ? t(`llmOps.auditLog.businessCategories.${key}`)
    : targetTypeLabel(targetType) || '-'
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
  const labelKey = fieldLabelKeys[key]
  return labelKey ? t(`llmOps.auditLog.fields.${labelKey}`) : key
}

function formatChangeValue(key, value) {
  if (Object.prototype.hasOwnProperty.call(valueLabelKeysByField, key)) {
    const normalized = compactValue(value)
    const labelKey = valueLabelKeysByField[key][normalized]
    return labelKey
      ? t(`llmOps.auditLog.values.${key}.${labelKey}`)
      : normalized
  }
  return compactValue(value)
}

function compactValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') {
    return value
      ? t('llmOps.auditLog.values.boolean.yes')
      : t('llmOps.auditLog.values.boolean.no')
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function statusValueClass(value) {
  const mutedValues = [
    t('llmOps.auditLog.values.boolean.no'),
    t('llmOps.auditLog.values.publish_status.deleted'),
    t('llmOps.auditLog.values.publish_status.offline'),
    t('llmOps.auditLog.values.status.inactive'),
    t('llmOps.auditLog.values.status.retired'),
    t('llmOps.auditLog.values.workflow_status.deleted'),
    t('llmOps.auditLog.values.workflow_status.offline')
  ]
  const dangerValues = [
    t('llmOps.auditLog.values.status.failed'),
    t('llmOps.auditLog.values.status.mismatch'),
    t('llmOps.auditLog.values.workflow_status.offlineException')
  ]
  const warnValues = [
    t('llmOps.auditLog.values.status.draft'),
    t('llmOps.auditLog.values.status.pending'),
    t('llmOps.auditLog.values.workflow_status.draft'),
    t('llmOps.auditLog.values.workflow_status.pendingOffline'),
    t('llmOps.auditLog.values.workflow_status.pendingPublish'),
    t('llmOps.auditLog.values.workflow_status.pendingUpdate'),
    t('llmOps.auditLog.values.workflow_status.updateDraft')
  ]
  const successValues = [
    t('llmOps.auditLog.values.boolean.yes'),
    t('llmOps.auditLog.values.publish_status.online'),
    t('llmOps.auditLog.values.status.active'),
    t('llmOps.auditLog.values.status.matched'),
    t('llmOps.auditLog.values.workflow_status.online')
  ]
  if (mutedValues.includes(value)) {
    return 'audit-status-value tone-muted'
  }
  if (dangerValues.includes(value)) {
    return 'audit-status-value tone-danger'
  }
  if (warnValues.includes(value)) {
    return 'audit-status-value tone-warn'
  }
  if (successValues.includes(value)) {
    return 'audit-status-value tone-success'
  }
  return 'audit-status-value tone-info'
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
