<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-3rem)] w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="submit"
    >
      <div class="modal-header">
        <div class="min-w-0">
          <p class="eyebrow">Manual Price Entry</p>
          <h3 class="mt-2 text-lg font-semibold text-slate-900">
            录入模型价格
          </h3>
          <p class="mt-1 text-sm text-slate-500">
            为当前价格源维护一条模型价格。优先选择已有原厂模型，确实不存在时可新增自定义模型。
          </p>
        </div>
        <button
          type="button"
          class="btn-secondary"
          :disabled="saving"
          @click="close"
        >
          关闭
        </button>
      </div>

      <div class="modal-body space-y-5">
        <section class="source-context">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-900">
              {{ source?.name || '-' }}
            </p>
            <p class="mt-1 truncate text-xs text-slate-500">
              {{ sourceRelationLabel }} · 默认币种 {{ form.currency }}
            </p>
          </div>
          <span :class="['source-badge', sourceCategoryTone]">
            {{ sourceCategoryLabel }}
          </span>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>选择模型</h4>
            <p>渠道和挂售后续会基于这个模型和价格源计算成本。</p>
          </div>

          <div class="mode-tabs">
            <button
              class="mode-tab"
              :class="{ active: modelMode === 'existing' }"
              type="button"
              @click="modelMode = 'existing'"
            >
              选择已有模型
            </button>
            <button
              class="mode-tab"
              :class="{ active: modelMode === 'custom' }"
              type="button"
              @click="modelMode = 'custom'"
            >
              新建自定义模型
            </button>
          </div>

          <div v-if="modelMode === 'existing'" class="grid gap-4 md:grid-cols-2">
            <label class="field-group md:col-span-2">
              <span class="field-label">模型</span>
              <CompactSelect
                v-model="form.model_id"
                :options="modelOptions"
                searchable
                search-placeholder="搜索模型名称、编码或厂商"
              />
              <span class="field-help">
                只从当前系统已有模型中选择，选择后会自动带入模型厂商和类型。
              </span>
            </label>
            <div class="readonly-field">
              <span>模型厂商</span>
              <strong>{{ selectedModel?.provider_name || '-' }}</strong>
            </div>
            <div class="readonly-field">
              <span>模型类型</span>
              <strong>{{ modalityLabel(selectedModel?.modality) }}</strong>
            </div>
          </div>

          <div v-else class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">模型名称</span>
              <input
                v-model="form.custom_model_name"
                class="field"
                placeholder="例如 DeepSeek V3"
              />
            </label>
            <label class="field-group">
              <span class="field-label">模型编码</span>
              <input
                v-model="form.custom_model_code"
                class="field"
                placeholder="例如 deepseek-v3"
              />
            </label>
            <label class="field-group">
              <span class="field-label">模型厂商</span>
              <CompactSelect
                v-model="form.provider"
                :options="providerOptions"
                searchable
                search-placeholder="搜索模型厂商"
              />
            </label>
            <label class="field-group">
              <span class="field-label">模型类型</span>
              <CompactSelect
                v-model="form.modality"
                :options="modalityOptions"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>价格明细</h4>
            <p>按模型支持的计费维度填写；未填写的维度不会生成价格项。</p>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group compact-field">
              <span class="field-label">币种</span>
              <CompactSelect v-model="form.currency" :options="currencyOptions" />
            </label>
            <label class="field-group">
              <span class="field-label">来源地址</span>
              <input
                v-model="form.source_url"
                class="field"
                placeholder="可选，价格页或报价单链接"
                type="url"
              />
            </label>
          </div>

          <div class="price-grid">
            <label
              v-for="field in priceFields"
              :key="field.key"
              class="field-group"
            >
              <span class="field-label">{{ field.label }}</span>
              <input
                v-model="form[field.key]"
                class="field font-mono"
                inputmode="decimal"
                min="0"
                placeholder="-"
                step="0.000001"
                type="number"
              />
              <span class="field-help">{{ field.help }}</span>
            </label>
          </div>
        </section>

        <p v-if="validationMessage" class="error-line">
          {{ validationMessage }}
        </p>
      </div>

      <div class="modal-footer">
        <div class="modal-footer-actions">
          <button
            class="btn-secondary"
            type="button"
            :disabled="saving"
            @click="close"
          >
            取消
          </button>
          <button class="btn-primary" type="submit" :disabled="saving">
            <span class="icon-mark" />
            {{ saving ? '保存中' : '保存价格' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  source: {
    type: Object,
    default: null
  },
  providers: {
    type: Array,
    default: () => []
  },
  models: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'saved'])
const { showSuccess, showError } = useToast()

const saving = ref(false)
const modelMode = ref('existing')
const form = ref(defaults())

const priceFields = [
  {
    key: 'input_price_per_million',
    label: '文本输入 / 百万 token',
    help: 'Prompt 或输入 token 单价'
  },
  {
    key: 'output_price_per_million',
    label: '文本输出 / 百万 token',
    help: 'Completion 或输出 token 单价'
  },
  {
    key: 'cache_input_price_per_million',
    label: '缓存输入 / 百万 token',
    help: '可选，命中缓存后的输入价格'
  },
  {
    key: 'image_output_price_per_image',
    label: '图片输出 / 张',
    help: '图片生成模型按张计价'
  },
  {
    key: 'audio_input_price_per_second',
    label: '音频输入 / 秒',
    help: '语音识别或音频理解输入'
  },
  {
    key: 'audio_output_price_per_second',
    label: '音频输出 / 秒',
    help: '语音合成或音频生成输出'
  },
  {
    key: 'video_input_price_per_second',
    label: '视频输入 / 秒',
    help: '视频理解输入'
  },
  {
    key: 'video_output_price_per_second',
    label: '视频输出 / 秒',
    help: '视频生成输出'
  }
]

const modalityOptions = [
  { label: '文本', value: 'text' },
  { label: '多模态', value: 'multimodal' },
  { label: '音频', value: 'audio' },
  { label: '视频', value: 'video' }
]

const currencyOptions = [
  { label: '人民币 CNY', value: 'CNY' },
  { label: '美元 USD', value: 'USD' }
]

const providerOptions = computed(() => [
  { label: '选择模型厂商', value: '' },
  ...props.providers
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((provider) => ({
      label: provider.name,
      value: provider.id,
      description: provider.code
    }))
])

const modelOptions = computed(() =>
  buildModelOptions()
)

const selectedModel = computed(() =>
  props.models.find(
    (model) => String(model.id) === String(form.value.model_id)
  )
)

const selectedProvider = computed(() =>
  props.providers.find(
    (provider) => String(provider.id) === String(form.value.provider)
  )
)

const sourceCategoryLabel = computed(() => {
  const labels = {
    official_provider: '原厂',
    supplier: '供货商',
    manual: '人工',
    unknown: '其他'
  }
  const category =
    props.source?.business_source_category ||
    props.source?.source_category ||
    'unknown'
  return labels[category] || '其他'
})

const sourceCategoryTone = computed(() => {
  const tones = {
    official_provider: 'official',
    supplier: 'supplier',
    manual: 'manual'
  }
  const category =
    props.source?.business_source_category ||
    props.source?.source_category ||
    'unknown'
  return tones[category] || 'unknown'
})

const sourceRelationLabel = computed(() => {
  if (props.source?.provider_name) return `模型厂商 ${props.source.provider_name}`
  if (props.source?.channel_name) return `转发渠道 ${props.source.channel_name}`
  return '未绑定模型厂商'
})

const validationMessage = computed(() => {
  if (!props.source?.id) return '缺少价格源。'
  if (modelMode.value === 'existing' && !selectedModel.value) {
    return '请选择一个已有模型。'
  }
  if (modelMode.value === 'custom') {
    if (!form.value.custom_model_name.trim()) return '请填写自定义模型名称。'
    if (!form.value.custom_model_code.trim()) return '请填写自定义模型编码。'
    if (!selectedProvider.value) return '请选择自定义模型的模型厂商。'
  }
  if (!hasAnyPrice()) return '至少填写一个价格维度。'
  return ''
})

watch(
  () => props.open,
  (open) => {
    if (open) {
      modelMode.value = 'existing'
      form.value = defaults()
      if (!form.value.model_id && props.models.length) {
        const matched = props.models.find(
          (model) => String(model.provider) === String(props.source?.provider)
        )
        form.value.model_id = matched?.id || ''
      }
    }
  }
)

function defaults() {
  return {
    model_id: '',
    provider: props.source?.provider || '',
    custom_model_name: '',
    custom_model_code: '',
    modality: 'text',
    currency: props.source?.currency || 'CNY',
    source_url: props.source?.endpoint_url || '',
    input_price_per_million: '',
    output_price_per_million: '',
    cache_input_price_per_million: '',
    image_output_price_per_image: '',
    audio_input_price_per_second: '',
    audio_output_price_per_second: '',
    video_input_price_per_second: '',
    video_output_price_per_second: ''
  }
}

function close() {
  if (saving.value) return
  emit('close')
}

async function submit() {
  if (validationMessage.value) {
    showError(validationMessage.value)
    return
  }

  saving.value = true
  try {
    const model = await resolveModel()
    const providerId = model.provider
    const row = buildImportRow(model)
    await llmOpsApi.importManualPrices({
      source: props.source.id,
      provider: providerId,
      source_name: props.source.name,
      source_slug: props.source.slug,
      source_url: form.value.source_url || props.source.endpoint_url || '',
      currency: form.value.currency,
      updates_model_prices: Boolean(props.source.updates_model_prices),
      rows: [row]
    })
    showSuccess('模型价格已保存')
    emit('saved')
  } catch (error) {
    showError(errorMessage(error, '保存模型价格失败'))
  } finally {
    saving.value = false
  }
}

async function resolveModel() {
  if (modelMode.value === 'existing') {
    return selectedModel.value
  }
  const response = await llmOpsApi.createModel({
    provider: selectedProvider.value.id,
    name: form.value.custom_model_name.trim(),
    code: form.value.custom_model_code.trim(),
    modality: form.value.modality,
    currency: form.value.currency,
    source: props.source.id,
    source_url: form.value.source_url || props.source.endpoint_url || '',
    is_active: true
  })
  return response.data
}

function buildImportRow(model) {
  const row = {
    model_code: model.code,
    model_name: model.name || model.code,
    modality: model.modality || form.value.modality,
    currency: form.value.currency,
    source_url: form.value.source_url || props.source.endpoint_url || ''
  }
  priceFields.forEach((field) => {
    const value = normalizePrice(form.value[field.key])
    if (value !== null) row[field.key] = value
  })
  return row
}

function hasAnyPrice() {
  return priceFields.some((field) => normalizePrice(form.value[field.key]) !== null)
}

function buildModelOptions() {
  const sourceProvider = props.source?.provider
  const sortedModels = props.models.slice().sort((left, right) => {
    const providerCompare = String(left.provider_name || '').localeCompare(
      String(right.provider_name || '')
    )
    if (providerCompare !== 0) return providerCompare
    return String(left.name || '').localeCompare(String(right.name || ''))
  })
  const preferred = sortedModels.filter(
    (model) => String(model.provider) === String(sourceProvider)
  )
  const others = sortedModels.filter(
    (model) => String(model.provider) !== String(sourceProvider)
  )
  if (!sourceProvider || !preferred.length) {
    return sortedModels.map(modelOption)
  }
  return [
    { label: '当前价格源关联厂商', value: '__group_preferred', type: 'group' },
    ...preferred.map(modelOption),
    { label: '其他模型', value: '__group_others', type: 'group' },
    ...others.map(modelOption)
  ]
}

function modelOption(model) {
  return {
    label: model.name || model.code,
    value: model.id,
    description: `${model.provider_name || '未知厂商'} · ${model.code}`,
    badge: modalityLabel(model.modality),
    searchText: [model.name, model.code, model.provider_name].join(' ')
  }
}

function normalizePrice(value) {
  if (value === '' || value === null || value === undefined) return null
  const number = Number(value)
  if (!Number.isFinite(number) || number < 0) return null
  return String(number)
}

function modalityLabel(value) {
  const labels = {
    text: '文本',
    multimodal: '多模态',
    audio: '音频',
    video: '视频'
  }
  return labels[value] || value || '文本'
}

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}
</script>

<style scoped>
.modal-header {
  @apply flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-start sm:justify-between;
}

.modal-body {
  @apply max-h-[calc(100vh-13rem)] overflow-y-auto px-5 py-5;
}

.modal-footer {
  @apply flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4;
}

.eyebrow {
  @apply text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600;
}

.source-context {
  @apply flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3;
}

.form-section {
  @apply rounded-lg border border-slate-200 bg-white p-4;
}

.section-heading {
  @apply mb-4;
}

.section-heading h4 {
  @apply text-sm font-semibold text-slate-900;
}

.section-heading p {
  @apply mt-1 text-xs leading-5 text-slate-500;
}

.mode-tabs {
  @apply mb-4 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1;
}

.mode-tab {
  @apply rounded-md px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-800;
}

.mode-tab.active {
  @apply bg-white text-indigo-700 shadow-sm;
}

.field-group {
  @apply flex min-w-0 flex-col gap-1.5;
}

.compact-field {
  @apply md:max-w-44;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.field-help {
  @apply text-xs leading-5 text-slate-400;
}

.field {
  @apply h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100;
}

.readonly-field {
  @apply rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.readonly-field span {
  @apply block text-xs font-medium text-slate-500;
}

.readonly-field strong {
  @apply mt-1 block truncate text-sm font-semibold text-slate-900;
}

.price-grid {
  @apply mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4;
}

.error-line {
  @apply rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-700;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.source-badge {
  @apply shrink-0 rounded-full border px-2 py-1 text-xs font-medium;
}

.source-badge.official {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.manual {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}
</style>
