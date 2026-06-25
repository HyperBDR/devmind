<template>
  <section class="space-y-5">
    <form class="panel space-y-4" @submit.prevent="saveReconciliation">
      <div class="flex flex-col gap-1">
        <p
          class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
        >
          Reconciliation
        </p>
        <h3 class="panel-title">生产使用对账审计</h3>
        <p class="text-sm text-slate-500">
          录入生产侧实际用量和渠道账单金额，用于核对系统按渠道采购价计算出的应付金额。
        </p>
      </div>

      <div class="grid gap-3 lg:grid-cols-3">
        <label class="form-field">
          <span class="field-label">对账日期</span>
          <input v-model="form.date" class="field" type="date" required />
        </label>
        <label class="form-field">
          <span class="field-label">转发渠道</span>
          <CompactSelect
            v-model="form.channel"
            :options="channelOptions"
            placeholder="选择账单归属渠道"
            searchable
            search-placeholder="搜索渠道名称 / code / 接入地址"
          />
        </label>
        <label class="form-field">
          <span class="field-label">调用模型</span>
          <CompactSelect
            v-model="form.model"
            :options="modelOptions"
            placeholder="选择本次用量对应模型"
            searchable
            search-placeholder="搜索模型名称 / code / 服务商"
          />
        </label>
      </div>

      <div class="usage-grid">
        <div v-if="!selectedModel" class="usage-helper lg:col-span-2">
          选择调用模型后，只显示该模型相关的用量维度。
        </div>
        <template v-if="showTextUsage">
          <label class="form-field">
            <span class="field-label">文本输入 Tokens</span>
            <input
              v-model="form.input_tokens"
              class="field"
              type="number"
              placeholder="0"
            />
          </label>
          <label class="form-field">
            <span class="field-label">文本输出 Tokens</span>
            <input
              v-model="form.output_tokens"
              class="field"
              type="number"
              placeholder="0"
            />
          </label>
        </template>
        <label class="form-field">
          <span class="field-label">渠道账单金额</span>
          <input
            v-model="form.charged_amount"
            class="field"
            type="number"
            step="0.000001"
            placeholder="0.000000"
            required
          />
        </label>
        <template v-if="showAudioUsage">
          <label class="form-field">
            <span class="field-label">音频输入秒数</span>
            <input
              v-model="form.audio_input_seconds"
              class="field"
              type="number"
              step="0.001"
              placeholder="0"
            />
          </label>
          <label class="form-field">
            <span class="field-label">音频输出秒数</span>
            <input
              v-model="form.audio_output_seconds"
              class="field"
              type="number"
              step="0.001"
              placeholder="0"
            />
          </label>
        </template>
        <template v-if="showVideoUsage">
          <label class="form-field">
            <span class="field-label">视频输入秒数</span>
            <input
              v-model="form.video_input_seconds"
              class="field"
              type="number"
              step="0.001"
              placeholder="0"
            />
          </label>
          <label class="form-field">
            <span class="field-label">视频输出秒数</span>
            <input
              v-model="form.video_output_seconds"
              class="field"
              type="number"
              step="0.001"
              placeholder="0"
            />
          </label>
          <label class="form-field lg:col-span-2">
            <span class="field-label">视频规格</span>
            <input
              v-model="form.video_resolution"
              class="field"
              placeholder="如 720p / 1080p，可选"
            />
          </label>
        </template>
      </div>

      <div class="flex gap-2">
        <button
          class="btn-primary btn-action-create"
          type="submit"
          :disabled="!canCreateRecord"
          :title="createDisabledReason"
        >
          <span class="icon-mark" />
          新建对账记录
        </button>
      </div>
      <p v-if="createDisabledReason" class="form-warning">
        {{ createDisabledReason }}
      </p>
    </form>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <h3 class="panel-title">对账记录</h3>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">日期</th>
              <th class="table-head">渠道</th>
              <th class="table-head">模型</th>
              <th class="table-head text-right">账单</th>
              <th class="table-head text-right">应付</th>
              <th class="table-head text-right">差异</th>
              <th class="table-head">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.id">
              <td class="table-cell">{{ record.date }}</td>
              <td class="table-cell">{{ record.channel_name }}</td>
              <td class="table-cell font-medium text-slate-900">
                {{ record.model_name }}
              </td>
              <td class="table-cell text-right">
                {{ money(record.charged_amount) }}
              </td>
              <td class="table-cell text-right">
                {{ money(record.expected_amount) }}
              </td>
              <td class="table-cell text-right">
                {{ money(record.discrepancy) }}
              </td>
              <td class="table-cell">{{ statusLabel(record.status) }}</td>
            </tr>
            <tr v-if="!records.length">
              <td class="table-cell" colspan="7">
                <div class="empty-state">
                  <p class="font-medium text-slate-700">暂无对账记录</p>
                  <p class="mt-1 text-sm text-slate-500">
                    先选择转发渠道和调用模型，录入渠道账单金额与实际用量；
                    系统会按当前渠道采购价计算应付金额并标记差异。
                  </p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  channels: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  records: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['refresh'])

const form = ref(defaults())

const selectedModel = computed(() =>
  props.models.find((model) => String(model.id) === String(form.value.model))
)

const createDisabledReason = computed(() => {
  if (!form.value.channel) return '请选择账单归属的转发渠道。'
  if (!form.value.model) return '请选择本次用量对应的调用模型。'
  if (Number(form.value.charged_amount || 0) <= 0) {
    return '请输入渠道账单金额。'
  }
  return ''
})

const canCreateRecord = computed(() => !createDisabledReason.value)

const showTextUsage = computed(() => {
  const model = selectedModel.value
  if (!model) return false
  return (
    ['text', 'multimodal'].includes(model.modality) ||
    Number(model.input_price_per_million || 0) > 0 ||
    Number(model.output_price_per_million || 0) > 0
  )
})

const showAudioUsage = computed(() => {
  const model = selectedModel.value
  if (!model) return false
  return (
    model.modality === 'audio' ||
    Number(model.audio_input_price_per_second || 0) > 0 ||
    Number(model.audio_output_price_per_second || 0) > 0
  )
})

const showVideoUsage = computed(() => {
  const model = selectedModel.value
  if (!model) return false
  return (
    model.modality === 'video' ||
    Number(model.video_input_price_per_second || 0) > 0 ||
    Number(model.video_output_price_per_second || 0) > 0
  )
})

const channelOptions = computed(() =>
  props.channels.map((channel) => ({
    label: channel.name,
    value: channel.id,
    description: [
      channel.code,
      channel.endpoint_url,
      channel.currency ? `默认币种 ${channel.currency}` : ''
    ]
      .filter(Boolean)
      .join(' · '),
    badge: channel.is_active ? '启用' : '停用',
    searchText: [
      channel.name,
      channel.code,
      channel.endpoint_url,
      channel.currency
    ]
      .filter(Boolean)
      .join(' ')
  }))
)

const modelOptions = computed(() =>
  props.models.map((model) => ({
    label: model.name,
    value: model.id,
    description: [
      model.code,
      model.provider_name,
      modalityLabel(model.modality)
    ]
      .filter(Boolean)
      .join(' · '),
    badge: model.currency || '',
    searchText: [
      model.name,
      model.code,
      model.provider_name,
      model.provider_code,
      model.modality
    ]
      .filter(Boolean)
      .join(' ')
  }))
)

function defaults() {
  return {
    date: new Date().toISOString().slice(0, 10),
    channel: '',
    model: '',
    input_tokens: '0',
    output_tokens: '0',
    audio_input_seconds: '0',
    audio_output_seconds: '0',
    video_input_seconds: '0',
    video_output_seconds: '0',
    video_resolution: '',
    charged_amount: '0'
  }
}

function normalizePayload(payload) {
  const clean = { ...payload }
  delete clean.id
  return clean
}

async function saveReconciliation() {
  await llmOpsApi.createReconciliationRecord(normalizePayload(form.value))
  form.value = defaults()
  emit('refresh')
}

watch(
  () => form.value.model,
  () => {
    if (!showTextUsage.value) {
      form.value.input_tokens = '0'
      form.value.output_tokens = '0'
    }
    if (!showAudioUsage.value) {
      form.value.audio_input_seconds = '0'
      form.value.audio_output_seconds = '0'
    }
    if (!showVideoUsage.value) {
      form.value.video_input_seconds = '0'
      form.value.video_output_seconds = '0'
      form.value.video_resolution = ''
    }
  }
)

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `$${Number(value).toFixed(4)}`
}

function statusLabel(status) {
  const labels = {
    perfect: '正常',
    overcharged: '超收',
    undercharged: '少收'
  }
  return labels[status] || status || '-'
}

function modalityLabel(modality) {
  const labels = {
    text: '文本',
    audio: '音频',
    video: '视频',
    multimodal: '多模态'
  }
  return labels[modality] || modality || ''
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.form-field {
  @apply flex min-w-0 flex-col gap-1.5;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.usage-grid {
  @apply grid gap-3 md:grid-cols-2 lg:grid-cols-3;
}

.usage-helper {
  @apply rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500;
}

.form-warning {
  @apply rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-700;
}

.empty-state {
  @apply whitespace-normal rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-center;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.data-table {
  @apply min-w-full divide-y divide-slate-200;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply whitespace-nowrap px-4 py-3 text-sm text-slate-600;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}
</style>
