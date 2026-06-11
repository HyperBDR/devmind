<template>
  <div
    v-if="source"
    class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
    @click.self="$emit('close')"
  >
    <aside class="h-full w-full max-w-5xl overflow-y-auto bg-white shadow-xl">
      <div
        class="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Price Source
            </p>
            <h3 class="mt-2 truncate text-xl font-semibold text-slate-900">
              {{ source.name }}
            </h3>
            <p class="mt-1 truncate font-mono text-xs text-slate-500">
              {{ source.slug }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="btn-danger"
              :disabled="deleting"
              @click="$emit('delete', source)"
            >
              {{ deleting ? '删除中' : '删除' }}
            </button>
            <button type="button" class="btn-secondary" @click="$emit('close')">
              关闭
            </button>
          </div>
        </div>
      </div>

      <div class="space-y-5 px-5 py-5">
        <div class="grid gap-3 md:grid-cols-4">
          <div class="summary-card">
            <p>价格项</p>
            <strong>{{ sourceRows.length }}</strong>
          </div>
          <div class="summary-card">
            <p>覆盖模型</p>
            <strong>{{ coveredModelCount }}</strong>
          </div>
          <div class="summary-card">
            <p>币种</p>
            <strong>{{ source.currency || '-' }}</strong>
          </div>
          <div class="summary-card">
            <p>状态</p>
            <strong>{{ source.is_enabled ? '启用' : '停用' }}</strong>
          </div>
        </div>

        <div class="source-info-grid">
          <div>
            <span>来源类型</span>
            <strong>{{ sourceCategoryLabel(source.source_category) }}</strong>
          </div>
          <div>
            <span>关联对象</span>
            <strong>{{ relationName }}</strong>
          </div>
          <div>
            <span>价格地址</span>
            <a
              v-if="source.endpoint_url"
              class="source-link"
              :href="source.endpoint_url"
              rel="noopener noreferrer"
              target="_blank"
              :title="source.endpoint_url"
            >
              {{ source.endpoint_url }}
            </a>
            <strong v-else class="text-slate-400">-</strong>
          </div>
        </div>

        <div class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <div>
              <h3 class="panel-title">当前价格源模型价格</h3>
              <p class="mt-1 text-xs text-slate-500">
                仅展示该价格源写入的当前有效价格项。
              </p>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">计价维度</th>
                  <th class="table-head text-right">价格</th>
                  <th class="table-head">原始币种</th>
                  <th class="table-head">更新时间</th>
                  <th class="table-head text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in sourceRows" :key="row.key">
                  <td class="table-cell">
                    <p class="truncate font-medium text-slate-900">
                      {{ row.model_name }}
                    </p>
                    <p class="mt-1 truncate font-mono text-xs text-slate-400">
                      {{ row.model_code }} · {{ row.provider_name }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <p class="font-medium text-slate-800">
                      {{ row.dimension_label }}
                    </p>
                    <p
                      v-if="row.spec_label || row.tier_label"
                      class="mt-1 text-xs text-slate-400"
                    >
                      {{ [row.spec_label, row.tier_label].filter(Boolean).join(' · ') }}
                    </p>
                  </td>
                  <td
                    class="table-cell text-right font-mono font-semibold text-slate-800"
                  >
                    {{ row.price }}
                  </td>
                  <td class="table-cell font-mono">
                    {{ row.currency || '-' }}
                  </td>
                  <td class="table-cell">
                    {{ formatDateTime(row.updated_at) }}
                  </td>
                  <td class="table-cell">
                    <div class="flex justify-end gap-2">
                      <button
                        type="button"
                        class="btn-ghost"
                        @click="openEdit(row)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="btn-text-danger"
                        :disabled="deletingItemId === row.id"
                        @click="deletePriceItem(row)"
                      >
                        {{ deletingItemId === row.id ? '删除中' : '删除' }}
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!sourceRows.length">
                  <td class="table-cell text-slate-500" colspan="6">
                    当前价格源还没有模型价格记录。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </aside>

    <div
      v-if="editingRow"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/35 px-4"
      @click.self="closeEdit"
    >
      <form class="price-modal" @submit.prevent="savePriceItem">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Edit Price Item
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              编辑模型价格
            </h3>
            <p class="mt-1 text-xs text-slate-500">
              {{ editingRow.model_name }} · {{ editingRow.dimension_label }}
            </p>
          </div>
          <button type="button" class="btn-secondary" @click="closeEdit">
            关闭
          </button>
        </div>

        <div class="mt-5 grid gap-4 sm:grid-cols-2">
          <label class="field-block">
            <span>计价维度</span>
            <select v-model="editForm.dimension" class="field-input">
              <option
                v-for="option in dimensionOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>
          <label class="field-block">
            <span>计价单位</span>
            <select v-model="editForm.billing_unit" class="field-input">
              <option
                v-for="option in billingUnitOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>
          <label class="field-block">
            <span>单价</span>
            <input
              v-model="editForm.unit_price"
              class="field-input font-mono"
              min="0"
              step="0.000001"
              type="number"
              required
            />
          </label>
          <label class="field-block">
            <span>币种</span>
            <select v-model="editForm.currency" class="field-input">
              <option value="CNY">CNY 人民币</option>
              <option value="USD">USD 美元</option>
            </select>
          </label>
          <label class="field-block">
            <span>阶梯类型</span>
            <select v-model="editForm.tier_type" class="field-input">
              <option value="flat">固定价</option>
              <option value="usage_range">用量区间</option>
              <option value="volume">阶梯用量</option>
            </select>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field-block">
              <span>起始用量</span>
              <input
                v-model="editForm.tier_start"
                class="field-input font-mono"
                min="0"
                step="0.000001"
                type="number"
              />
            </label>
            <label class="field-block">
              <span>结束用量</span>
              <input
                v-model="editForm.tier_end"
                class="field-input font-mono"
                min="0"
                step="0.000001"
                type="number"
              />
            </label>
          </div>
          <label class="field-block sm:col-span-2">
            <span>规格 JSON</span>
            <textarea
              v-model="editForm.spec"
              class="field-input min-h-[92px] font-mono"
              placeholder='例如 {"resolution":"1080P","audio":"included"}'
            />
          </label>
        </div>

        <p v-if="formError" class="mt-3 text-sm text-rose-600">
          {{ formError }}
        </p>
        <div class="mt-5 flex justify-end gap-2">
          <button type="button" class="btn-secondary" @click="closeEdit">
            取消
          </button>
          <button type="submit" class="btn-primary" :disabled="saving">
            {{ saving ? '保存中' : '保存价格' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'

const emit = defineEmits(['close', 'delete', 'refresh'])
const { showSuccess, showError } = useToast()

const props = defineProps({
  source: {
    type: Object,
    default: null
  },
  models: {
    type: Array,
    default: () => []
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  displayCurrency: {
    type: String,
    default: 'CNY'
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  },
  deleting: {
    type: Boolean,
    default: false
  }
})

const editingRow = ref(null)
const saving = ref(false)
const deletingItemId = ref(null)
const formError = ref('')
const editForm = reactive({
  dimension: 'text_input',
  billing_unit: 'per_1m_tokens',
  unit_price: '',
  currency: 'CNY',
  tier_type: 'flat',
  tier_start: '',
  tier_end: '',
  spec: '{}'
})

const dimensionOptions = [
  { value: 'text_input', label: '文本输入' },
  { value: 'text_output', label: '文本输出' },
  { value: 'cache_input', label: '缓存输入' },
  { value: 'image_input', label: '图片输入' },
  { value: 'image_output', label: '图片输出' },
  { value: 'audio_input', label: '音频输入' },
  { value: 'audio_output', label: '音频输出' },
  { value: 'video_input', label: '视频输入' },
  { value: 'video_output', label: '视频输出' }
]

const billingUnitOptions = [
  { value: 'per_1m_tokens', label: '每百万 tokens' },
  { value: 'per_image', label: '每张图片' },
  { value: 'per_second', label: '每秒' },
  { value: 'per_generation', label: '每次生成' }
]

const modelMap = computed(() => {
  const entries = props.models.map((model) => [String(model.id), model])
  return new Map(entries)
})

const sourceRows = computed(() =>
  props.priceItems
    .filter(
      (item) =>
        String(item.source) === String(props.source?.id) &&
        item.is_current !== false
    )
    .slice()
    .sort((left, right) => {
      const leftModel = modelName(left).localeCompare(modelName(right))
      if (leftModel !== 0) return leftModel
      const leftKey = `${left.dimension}-${left.tier_start || ''}`
      const rightKey = `${right.dimension}-${right.tier_start || ''}`
      return leftKey.localeCompare(rightKey)
    })
    .map((item) => {
      const model = modelMap.value.get(String(item.model)) || {}
      return {
        key: `source-price-${item.id}`,
        id: item.id,
        raw: item,
        model_name: item.model_name || model.name || '未知模型',
        model_code: item.model_code || model.code || '-',
        provider_name: item.provider_name || model.provider_name || '-',
        dimension_label: `${dimensionLabel(item.dimension)} ${billingUnitLabel(item.billing_unit)}`,
        spec_label: specLabel(item.spec || {}),
        tier_label: tierLabel(item),
        price: money(item.unit_price, item.currency),
        unit_price: item.unit_price,
        currency: item.currency,
        dimension: item.dimension,
        billing_unit: item.billing_unit,
        tier_type: item.tier_type,
        tier_start: item.tier_start,
        tier_end: item.tier_end,
        spec: item.spec || {},
        updated_at: item.updated_at || item.effective_from
      }
    })
)

const coveredModelCount = computed(() => {
  const ids = new Set(sourceRows.value.map((row) => row.model_code))
  return ids.size
})

const relationName = computed(() => {
  if (props.source?.provider_name) return props.source.provider_name
  if (props.source?.channel_name) return props.source.channel_name
  return '未绑定'
})

function modelName(item) {
  const model = modelMap.value.get(String(item.model)) || {}
  return item.model_name || model.name || ''
}

function convertCurrencyAmount(value, sourceCurrency = 'USD') {
  if (value === null || value === undefined || value === '') return null
  const source = String(sourceCurrency || '').toUpperCase()
  const target = String(props.displayCurrency || 'CNY').toUpperCase()
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  if (source === target) return amount
  if (source === 'USD' && target === 'CNY') {
    return amount * Number(props.exchangeRate || 7.15)
  }
  if (source === 'CNY' && target === 'USD') {
    return amount / Number(props.exchangeRate || 7.15)
  }
  return null
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  const displayValue = convertCurrencyAmount(value, currency)
  if (displayValue === null) {
    return `${currency || 'USD'} ${Number(value).toFixed(4)}`
  }
  return `${props.displayCurrency || 'CNY'} ${displayValue.toFixed(4)}`
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: '文本输入',
    text_output: '文本输出',
    cache_input: '缓存输入',
    image_input: '图片输入',
    image_output: '图片输出',
    audio_input: '音频输入',
    audio_output: '音频输出',
    video_input: '视频输入',
    video_output: '视频输出'
  }
  return labels[dimension] || dimension || '-'
}

function billingUnitLabel(unit) {
  const labels = {
    per_1m_tokens: '/ 百万 tokens',
    per_image: '/ 张',
    per_second: '/ 秒',
    per_generation: '/ 次'
  }
  return labels[unit] || ''
}

function specLabel(spec) {
  const parts = [
    spec.resolution,
    spec.quality,
    spec.audio,
    spec.mode
  ].filter(Boolean)
  return parts.join(' / ')
}

function tierLabel(item) {
  if (item.tier_type === 'flat') return ''
  const start = item.tier_start || 0
  const end = item.tier_end || '∞'
  return `${start} - ${end}`
}

function openEdit(row) {
  editingRow.value = row
  formError.value = ''
  editForm.dimension = row.dimension || 'text_input'
  editForm.billing_unit = row.billing_unit || 'per_1m_tokens'
  editForm.unit_price = row.unit_price ?? ''
  editForm.currency = row.currency || props.source?.currency || 'CNY'
  editForm.tier_type = row.tier_type || 'flat'
  editForm.tier_start = row.tier_start ?? ''
  editForm.tier_end = row.tier_end ?? ''
  editForm.spec = JSON.stringify(row.spec || {}, null, 2)
}

function closeEdit() {
  editingRow.value = null
  formError.value = ''
}

async function savePriceItem() {
  if (!editingRow.value?.id) return
  const spec = parseSpec()
  if (spec === null) return
  saving.value = true
  try {
    await llmOpsApi.updateModelPriceItem(editingRow.value.id, {
      dimension: editForm.dimension,
      billing_unit: editForm.billing_unit,
      unit_price: editForm.unit_price,
      currency: editForm.currency,
      tier_type: editForm.tier_type,
      tier_start: emptyToNull(editForm.tier_start),
      tier_end: emptyToNull(editForm.tier_end),
      spec
    })
    showSuccess('模型价格已更新')
    closeEdit()
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '保存模型价格失败'))
  } finally {
    saving.value = false
  }
}

async function deletePriceItem(row) {
  if (!row?.id) return
  const confirmed = window.confirm(
    `确认删除「${row.model_name} / ${row.dimension_label}」这条价格吗？`
  )
  if (!confirmed) return
  deletingItemId.value = row.id
  try {
    await llmOpsApi.deleteModelPriceItem(row.id)
    showSuccess('模型价格已删除')
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '删除模型价格失败'))
  } finally {
    deletingItemId.value = null
  }
}

function parseSpec() {
  try {
    const value = editForm.spec.trim() ? JSON.parse(editForm.spec) : {}
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      formError.value = '规格 JSON 必须是对象。'
      return null
    }
    formError.value = ''
    return value
  } catch {
    formError.value = '规格 JSON 格式不正确。'
    return null
  }
}

function emptyToNull(value) {
  return value === '' || value === undefined ? null : value
}

function errorMessage(error, fallback) {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const firstKey = Object.keys(data)[0]
  const firstValue = firstKey ? data[firstKey] : null
  if (Array.isArray(firstValue)) return firstValue.join('、')
  return fallback
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: '原厂价格',
    supplier: '供货商价格',
    manual: '人工录入',
    unknown: '其他'
  }
  return labels[category] || labels.unknown
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.summary-card {
  @apply rounded-lg bg-slate-50 px-3 py-2;
}

.summary-card p {
  @apply text-xs text-slate-500;
}

.summary-card strong {
  @apply mt-1 block font-mono text-sm text-slate-800;
}

.source-info-grid {
  @apply grid gap-3 md:grid-cols-3;
}

.source-info-grid div {
  @apply min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.source-info-grid span {
  @apply block text-xs text-slate-500;
}

.source-info-grid strong,
.source-info-grid a {
  @apply mt-1 block truncate text-sm font-medium text-slate-800;
}

.source-link {
  @apply text-indigo-600 hover:text-indigo-700 hover:underline;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.data-table {
  @apply min-w-full table-fixed divide-y divide-slate-200;
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
  @apply min-w-0 px-4 py-3 text-sm text-slate-600;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-danger {
  @apply inline-flex items-center gap-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-200 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-ghost {
  @apply rounded-lg px-2.5 py-1.5 text-xs font-medium text-indigo-600 transition hover:bg-indigo-50 hover:text-indigo-700;
}

.btn-text-danger {
  @apply rounded-lg px-2.5 py-1.5 text-xs font-medium text-rose-600 transition hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.price-modal {
  @apply w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-xl;
}

.field-block {
  @apply block;
}

.field-block span {
  @apply mb-1.5 block text-xs font-medium text-slate-500;
}

.field-input {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}
</style>
