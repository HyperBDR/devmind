<template>
  <section class="collection-run-log-panel">
    <div class="collection-log-summary-grid">
      <div
        v-for="metric in summaryMetrics"
        :key="metric.key"
        class="collection-log-metric"
        :class="metric.tone"
      >
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
      </div>
    </div>

    <div class="panel collection-log-table-panel">
      <div class="collection-log-toolbar">
        <div>
          <h3 class="panel-title">{{ t('llmOps.taskLogs.title') }}</h3>
          <p>{{ t('llmOps.taskLogs.description') }}</p>
        </div>
        <button
          type="button"
          class="btn-secondary collection-log-refresh btn-action-refresh"
          @click="emit('refresh')"
        >
          <svg
            aria-hidden="true"
            class="collection-log-action-icon"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
            <path d="M3 16v5h5" />
            <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
            <path d="M21 3v5h-5" />
          </svg>
          {{ t('llmOps.taskLogs.actions.refresh') }}
        </button>
      </div>

      <div class="collection-log-filters">
        <label class="collection-log-filter is-wide">
          <span>{{ t('llmOps.taskLogs.filters.keyword') }}</span>
          <input
            v-model.trim="searchKeyword"
            class="collection-log-input"
            :placeholder="t('llmOps.taskLogs.filters.keywordPlaceholder')"
          />
        </label>
        <label class="collection-log-filter">
          <span>{{ t('llmOps.taskLogs.filters.status') }}</span>
          <CompactSelect
            v-model="statusFilter"
            :options="statusOptions"
            class-name="collection-log-select w-full"
          />
        </label>
        <label class="collection-log-filter">
          <span>{{ t('llmOps.taskLogs.filters.category') }}</span>
          <CompactSelect
            v-model="categoryFilter"
            :options="categoryOptions"
            class-name="collection-log-select w-full"
          />
        </label>
      </div>

      <div class="collection-log-table-scroll">
        <table class="data-table collection-log-table">
          <colgroup>
            <col class="status-col" />
            <col class="source-col" />
            <col class="category-col" />
            <col class="time-col" />
            <col class="duration-col" />
            <col class="result-col" />
            <col class="detail-col" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-head">{{ t('llmOps.taskLogs.table.status') }}</th>
              <th class="table-head">{{ t('llmOps.taskLogs.table.source') }}</th>
              <th class="table-head">{{ t('llmOps.taskLogs.table.category') }}</th>
              <th class="table-head">
                {{ t('llmOps.taskLogs.table.startedAt') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.taskLogs.table.duration') }}
              </th>
              <th class="table-head">{{ t('llmOps.taskLogs.table.result') }}</th>
              <th class="table-head">{{ t('llmOps.taskLogs.table.detail') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in pagedRows" :key="row.id">
              <tr>
                <td class="table-cell">
                  <span :class="['run-status-pill', row.statusTone]">
                    {{ row.statusLabel }}
                  </span>
                </td>
                <td class="table-cell">
                  <p class="font-medium text-slate-900">
                    {{ row.sourceLabel }}
                  </p>
                  <p v-if="row.providerLabel" class="source-subtitle">
                    {{ row.providerLabel }}
                  </p>
                </td>
                <td class="table-cell">
                  <span :class="['source-category-pill', row.categoryTone]">
                    {{ row.categoryLabel }}
                  </span>
                </td>
                <td class="table-cell run-time">
                  {{ formatDateTime(row.started_at) }}
                </td>
                <td class="table-cell run-duration">
                  {{ formatDuration(row) }}
                </td>
                <td class="table-cell">
                  <div class="run-result-grid">
                    <span>
                      {{ t('llmOps.taskLogs.counts.collected') }}
                      <strong>{{ row.collected_count || 0 }}</strong>
                    </span>
                    <span>
                      {{ t('llmOps.taskLogs.counts.created') }}
                      <strong>{{ row.created_count || 0 }}</strong>
                    </span>
                    <span>
                      {{ t('llmOps.taskLogs.counts.updated') }}
                      <strong>{{ row.updated_count || 0 }}</strong>
                    </span>
                    <span>
                      {{ t('llmOps.taskLogs.counts.skipped') }}
                      <strong>{{ row.skipped_count || 0 }}</strong>
                    </span>
                  </div>
                </td>
                <td class="table-cell">
                  <button
                    type="button"
                    class="collection-log-detail-button"
                    :disabled="!row.hasDetails"
                    :aria-expanded="expandedId === row.id"
                    :aria-controls="`collection-run-detail-${row.id}`"
                    @click="toggleExpanded(row.id)"
                  >
                    {{
                      expandedId === row.id
                        ? t('llmOps.taskLogs.actions.hideDetails')
                        : detailButtonLabel(row)
                    }}
                  </button>
                </td>
              </tr>
              <tr v-if="expandedId === row.id">
                <td
                  :id="`collection-run-detail-${row.id}`"
                  class="detail-cell"
                  colspan="7"
                >
                  <div class="collection-log-detail-grid">
                    <section v-if="row.error_message" class="detail-block">
                      <h4>{{ t('llmOps.taskLogs.detail.error') }}</h4>
                      <p class="detail-error">{{ row.error_message }}</p>
                    </section>
                    <section
                      v-if="metadataEntries(row).length"
                      class="detail-block"
                    >
                      <h4>{{ t('llmOps.taskLogs.detail.metadata') }}</h4>
                      <dl class="metadata-list">
                        <template
                          v-for="item in metadataEntries(row)"
                          :key="item.key"
                        >
                          <dt>{{ item.label }}</dt>
                          <dd>{{ item.value }}</dd>
                        </template>
                      </dl>
                    </section>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!pagedRows.length">
              <td class="table-cell" colspan="7">
                <div class="empty-state">
                  <p class="font-medium text-slate-700">
                    {{ t('llmOps.taskLogs.empty.title') }}
                  </p>
                  <p class="mt-1 text-sm text-slate-500">
                    {{ t('llmOps.taskLogs.empty.description') }}
                  </p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="collection-log-footer">
        <span>{{ pageRangeLabel }}</span>
        <div class="collection-log-pagination">
          <label>
            <span>{{ t('llmOps.taskLogs.pagination.pageSize') }}</span>
            <CompactSelect
              v-model="pageSize"
              :options="pageSizeOptions"
              class-name="collection-log-page-size"
            />
          </label>
          <button
            type="button"
            class="btn-secondary collection-log-page-button"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          >
            {{ t('llmOps.taskLogs.pagination.previous') }}
          </button>
          <span class="collection-log-page-label">
            {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            type="button"
            class="btn-secondary collection-log-page-button"
            :disabled="currentPage >= totalPages"
            @click="currentPage += 1"
          >
            {{ t('llmOps.taskLogs.pagination.next') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  runs: {
    type: Array,
    default: () => []
  },
  sources: {
    type: Array,
    default: () => []
  }
})
const emit = defineEmits(['refresh'])
const { t } = useI18n()

const searchKeyword = ref('')
const statusFilter = ref('')
const categoryFilter = ref('')
const pageSize = ref('50')
const currentPage = ref(1)
const expandedId = ref(null)

const statusOptions = computed(() => [
  { label: t('llmOps.taskLogs.status.all'), value: '' },
  { label: t('llmOps.taskLogs.status.succeeded'), value: 'succeeded' },
  { label: t('llmOps.taskLogs.status.failed'), value: 'failed' },
  { label: t('llmOps.taskLogs.status.running'), value: 'running' }
])

const categoryOptions = computed(() => [
  { label: t('llmOps.taskLogs.categories.all'), value: '' },
  {
    label: t('llmOps.taskLogs.categories.officialProvider'),
    value: 'official_provider'
  },
  {
    label: t('llmOps.taskLogs.categories.cloudHosted'),
    value: 'cloud_hosted'
  },
  { label: t('llmOps.taskLogs.categories.supplier'), value: 'supplier' },
  { label: t('llmOps.taskLogs.categories.manual'), value: 'manual' },
  { label: t('llmOps.taskLogs.categories.unknown'), value: 'unknown' }
])

const pageSizeOptions = computed(() =>
  ['20', '50', '100'].map((size) => ({
    label: t('llmOps.taskLogs.pagination.pageSizeOption', { size }),
    value: size
  }))
)

const sourcesById = computed(() => {
  return new Map(props.sources.map((source) => [String(source.id), source]))
})

const enrichedRows = computed(() =>
  props.runs.map((run) => {
    const source = sourceForRun(run)
    const category = sourceCategory(run, source)
    return {
      ...run,
      category,
      categoryLabel: categoryLabel(category),
      categoryTone: categoryTone(category),
      hasDetails:
        Boolean(run.error_message) || metadataEntries(run).length > 0,
      providerLabel: providerLabel(run, source),
      sourceLabel: sourceLabel(run, source),
      statusLabel: statusLabel(run.status),
      statusTone: statusTone(run.status)
    }
  })
)

const filteredRows = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return enrichedRows.value.filter((row) => {
    if (statusFilter.value && row.status !== statusFilter.value) return false
    if (categoryFilter.value && row.category !== categoryFilter.value) {
      return false
    }
    if (!keyword) return true
    return [
      row.sourceLabel,
      row.providerLabel,
      row.statusLabel,
      row.error_message
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword))
  })
})

const pageSizeNumber = computed(() => Number(pageSize.value || 50))

const totalPages = computed(() =>
  Math.max(Math.ceil(filteredRows.value.length / pageSizeNumber.value), 1)
)

const pagedRows = computed(() => {
  const page = Math.min(currentPage.value, totalPages.value)
  const start = (page - 1) * pageSizeNumber.value
  return filteredRows.value.slice(start, start + pageSizeNumber.value)
})

const pageRangeLabel = computed(() => {
  if (!filteredRows.value.length) {
    return t('llmOps.taskLogs.pagination.emptyRange')
  }
  const start = (currentPage.value - 1) * pageSizeNumber.value + 1
  const end = Math.min(
    currentPage.value * pageSizeNumber.value,
    filteredRows.value.length
  )
  return t('llmOps.taskLogs.pagination.range', {
    count: filteredRows.value.length,
    end,
    start
  })
})

const summaryMetrics = computed(() => {
  const total = props.runs.length
  const running = props.runs.filter((run) => run.status === 'running').length
  const failed = props.runs.filter((run) => run.status === 'failed').length
  const succeeded = props.runs.filter(
    (run) => run.status === 'succeeded'
  ).length
  return [
    {
      key: 'total',
      label: t('llmOps.taskLogs.metrics.total'),
      value: total,
      tone: 'tone-neutral'
    },
    {
      key: 'running',
      label: t('llmOps.taskLogs.metrics.running'),
      value: running,
      tone: running ? 'tone-info' : 'tone-neutral'
    },
    {
      key: 'succeeded',
      label: t('llmOps.taskLogs.metrics.succeeded'),
      value: succeeded,
      tone: 'tone-success'
    },
    {
      key: 'failed',
      label: t('llmOps.taskLogs.metrics.failed'),
      value: failed,
      tone: failed ? 'tone-danger' : 'tone-neutral'
    }
  ]
})

watch(
  [searchKeyword, statusFilter, categoryFilter, pageSize],
  () => {
    currentPage.value = 1
    expandedId.value = null
  }
)

watch(totalPages, (value) => {
  if (currentPage.value > value) currentPage.value = value
})

function sourceForRun(run) {
  if (!run?.source) return null
  return sourcesById.value.get(String(run.source)) || null
}

function sourceCategory(run, source) {
  const rawCategory =
    source?.business_source_category ||
    source?.source_category ||
    run?.source_category ||
    'unknown'
  return normalizeSourceCategory(rawCategory, source)
}

function normalizeSourceCategory(category, source = null) {
  const normalized = String(category || '').trim().toLowerCase()
  if (normalized === 'official_provider') {
    return normalizeOfficialSourceCategory(source)
  }
  if (normalized === 'model_provider_official') return 'official_provider'
  if (normalized === 'cloud_provider_official') return 'cloud_hosted'
  if (normalized === 'internal') return 'manual'
  if (normalized === 'manual_entry') return 'manual'
  if (normalized === 'manual_import') return 'manual'
  if (normalized === 'api_sync') return 'supplier'
  if (['cloud_hosted', 'supplier', 'manual'].includes(normalized)) {
    return normalized
  }
  return 'unknown'
}

function normalizeOfficialSourceCategory(source) {
  const ownerType = String(source?.source_owner_type || '').toLowerCase()
  if (ownerType === 'cloud_provider_official') return 'cloud_hosted'
  return 'official_provider'
}

function sourceLabel(run, source) {
  return (
    run?.source_name ||
    source?.name ||
    t('llmOps.taskLogs.deletedSource')
  )
}

function providerLabel(run, source) {
  return run?.source_provider_name || source?.provider_name || ''
}

function statusLabel(status) {
  const labels = {
    failed: t('llmOps.taskLogs.status.failed'),
    running: t('llmOps.taskLogs.status.running'),
    succeeded: t('llmOps.taskLogs.status.succeeded')
  }
  return labels[status] || status || t('llmOps.taskLogs.status.unknown')
}

function statusTone(status) {
  if (status === 'succeeded') return 'tone-success'
  if (status === 'failed') return 'tone-danger'
  if (status === 'running') return 'tone-info'
  return 'tone-neutral'
}

function categoryLabel(category) {
  const labels = {
    cloud_hosted: t('llmOps.taskLogs.categories.cloudHosted'),
    manual: t('llmOps.taskLogs.categories.manual'),
    official_provider: t('llmOps.taskLogs.categories.officialProvider'),
    supplier: t('llmOps.taskLogs.categories.supplier'),
    unknown: t('llmOps.taskLogs.categories.unknown')
  }
  return labels[category] || labels.unknown
}

function categoryTone(category) {
  if (category === 'official_provider') return 'tone-primary'
  if (category === 'cloud_hosted') return 'tone-success'
  if (category === 'supplier') return 'tone-info'
  if (category === 'manual') return 'tone-warn'
  return 'tone-neutral'
}

function toggleExpanded(id) {
  const row = enrichedRows.value.find((item) => item.id === id)
  if (!row?.hasDetails) return
  expandedId.value = expandedId.value === id ? null : id
}

function detailButtonLabel(row) {
  if (!row.hasDetails) return t('llmOps.taskLogs.actions.noDetails')
  return t('llmOps.taskLogs.actions.showDetails')
}

function metadataEntries(row) {
  const metadata = row?.metadata
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    return []
  }
  return Object.entries(metadata)
    .filter(([, value]) => hasMetadataValue(value))
    .map(([key, value]) => ({
      key,
      label: metadataLabel(key),
      value: formatMetadataValue(value)
    }))
}

function hasMetadataValue(value) {
  if (value === null || value === undefined || value === '') return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

function metadataLabel(key) {
  const labelKeys = {
    changed_count: 'changedCount',
    collected_model_codes: 'collectedModelCodes',
    currency: 'currency',
    fallback_model_ids: 'fallbackModelIds',
    missing_model_ids: 'missingModelIds',
    skipped_model_codes: 'skippedModelCodes',
    source_parse_fallback_model_ids: 'sourceParseFallbackModelIds',
    source_parse_missing_model_ids: 'sourceParseMissingModelIds',
    source_url: 'sourceUrl',
    unchanged_count: 'unchangedCount'
  }
  const labelKey = labelKeys[key]
  return labelKey ? t(`llmOps.taskLogs.metadata.${labelKey}`) : key
}

function formatMetadataValue(value) {
  if (Array.isArray(value)) {
    const preview = value.slice(0, 8).join(', ')
    return value.length > 8 ? `${preview} +${value.length - 8}` : preview
  }
  if (typeof value === 'boolean') {
    return value ? t('common.yes') : t('common.no')
  }
  if (value && typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatDuration(row) {
  const start = new Date(row.started_at || 0).getTime()
  const end = row.finished_at
    ? new Date(row.finished_at).getTime()
    : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(end) || !start) return '-'
  const seconds = Math.max(Math.round((end - start) / 1000), 0)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const restSeconds = seconds % 60
  if (minutes < 60) return `${minutes}m ${restSeconds}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}
</script>

<style scoped>
.collection-run-log-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.collection-log-summary-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (min-width: 1024px) {
  .collection-log-summary-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.collection-log-metric {
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background: #ffffff;
  padding: 1rem;
}

.collection-log-metric span {
  color: #64748b;
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
}

.collection-log-metric strong {
  color: #0f172a;
  display: block;
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.1;
  margin-top: 0.35rem;
}

.collection-log-metric.tone-success {
  border-color: #bbf7d0;
}

.collection-log-metric.tone-danger {
  border-color: #fecdd3;
}

.collection-log-metric.tone-info {
  border-color: #bae6fd;
}

.panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
}

.panel-title {
  color: #0f172a;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.4;
}

.collection-log-table-panel {
  overflow: hidden;
}

.collection-log-toolbar,
.collection-log-filters,
.collection-log-footer {
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 1rem;
}

.collection-log-toolbar p {
  color: #64748b;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.collection-log-refresh {
  align-items: center;
  display: inline-flex;
  gap: 0.4rem;
  white-space: nowrap;
}

.collection-log-action-icon {
  height: 1rem;
  width: 1rem;
}

.collection-log-filters {
  align-items: end;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}

@media (min-width: 768px) {
  .collection-log-filters {
    grid-template-columns: minmax(0, 1fr) 12rem 12rem;
  }
}

.collection-log-filter {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}

.collection-log-filter span {
  color: #475569;
  font-size: 0.75rem;
  font-weight: 700;
}

.collection-log-input {
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  color: #0f172a;
  font-size: 0.875rem;
  height: 2.5rem;
  outline: none;
  padding: 0 0.75rem;
}

.collection-log-input:focus {
  border-color: #6a5ac7;
  box-shadow: 0 0 0 3px rgb(106 90 199 / 0.12);
}

.collection-log-table-scroll {
  overflow-x: auto;
}

.collection-log-table {
  min-width: 960px;
}

.status-col {
  width: 8rem;
}

.source-col {
  width: 17rem;
}

.category-col {
  width: 8rem;
}

.time-col {
  width: 13rem;
}

.duration-col {
  width: 7rem;
}

.detail-col {
  width: 7rem;
}

.run-status-pill,
.source-category-pill {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-size: 0.75rem;
  font-weight: 700;
  justify-content: center;
  min-height: 1.5rem;
  padding: 0.2rem 0.6rem;
  white-space: nowrap;
}

.run-status-pill.tone-success,
.source-category-pill.tone-success {
  background: #ecfdf5;
  color: #047857;
}

.run-status-pill.tone-danger,
.source-category-pill.tone-danger {
  background: #fff1f2;
  color: #be123c;
}

.run-status-pill.tone-info,
.source-category-pill.tone-info {
  background: #eff6ff;
  color: #1d4ed8;
}

.source-category-pill.tone-primary {
  background: #eef2ff;
  color: #4f46e5;
}

.source-category-pill.tone-warn {
  background: #fffbeb;
  color: #b45309;
}

.run-status-pill.tone-neutral,
.source-category-pill.tone-neutral {
  background: #f1f5f9;
  color: #475569;
}

.source-subtitle {
  color: #64748b;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.run-time,
.run-duration {
  color: #64748b;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.75rem;
}

.run-result-grid {
  display: grid;
  gap: 0.25rem 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.run-result-grid span {
  color: #64748b;
  font-size: 0.75rem;
  white-space: nowrap;
}

.run-result-grid strong {
  color: #0f172a;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.75rem;
  margin-left: 0.25rem;
}

.collection-log-detail-button {
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  color: #334155;
  font-size: 0.75rem;
  font-weight: 700;
  min-height: 2rem;
  padding: 0 0.65rem;
}

.collection-log-detail-button:not(:disabled):hover {
  border-color: #6a5ac7;
  color: #4a3eb0;
}

.collection-log-detail-button:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.collection-log-detail-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: minmax(0, 1fr);
}

@media (min-width: 900px) {
  .collection-log-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.detail-block {
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background: #ffffff;
  padding: 0.875rem;
  text-align: left;
}

.detail-block h4 {
  color: #0f172a;
  font-size: 0.8rem;
  font-weight: 700;
  margin: 0 0 0.6rem;
}

.detail-error {
  color: #be123c;
  font-size: 0.8rem;
  line-height: 1.6;
  margin: 0;
  overflow-wrap: anywhere;
}

.metadata-list {
  display: grid;
  gap: 0.4rem 0.75rem;
  grid-template-columns: max-content minmax(0, 1fr);
  margin: 0;
}

.metadata-list dt {
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
}

.metadata-list dd {
  color: #0f172a;
  font-size: 0.75rem;
  margin: 0;
  overflow-wrap: anywhere;
}

.collection-log-footer {
  border-bottom: 0;
  border-top: 1px solid #f1f5f9;
  color: #64748b;
  font-size: 0.75rem;
}

.collection-log-pagination,
.collection-log-pagination label {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}

.collection-log-page-label {
  color: #334155;
  font-weight: 700;
  min-width: 4rem;
  text-align: center;
}

.collection-log-page-button {
  min-height: 2rem;
  padding: 0 0.75rem;
}

@media (max-width: 767px) {
  .collection-log-toolbar,
  .collection-log-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .collection-log-pagination {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}
</style>
