<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-3rem)] w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="save"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Meta Model
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ form.id ? '编辑元模型' : '新建元模型' }}
            </h3>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              元模型用于把不同价格源中的同一模型身份归一到厂商、能力和版本。
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel shrink-0"
            :disabled="saving"
            @click="close"
          >
            关闭
          </button>
        </div>
      </div>

      <div
        class="max-h-[calc(100vh-15rem)] space-y-5 overflow-y-auto px-5 py-5"
      >
        <section class="form-section">
          <div class="section-heading">
            <h4>模型身份</h4>
            <p>用于跨官方、供应商和人工价格源归并模型。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">显示名称</span>
              <input
                v-model="form.name"
                class="field"
                placeholder="例如：GPT-4o mini"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">模型标识 Code</span>
              <input
                v-model="form.code"
                class="field font-mono disabled:bg-slate-50 disabled:text-slate-400"
                :disabled="Boolean(form.id)"
                placeholder="例如：gpt-4o-mini"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">模型归属方</span>
              <CompactSelect
                v-model="form.owner_code"
                :options="ownerOptions"
                class-name="meta-select w-full"
              />
            </label>
            <label class="field-group">
              <span class="field-label">状态</span>
              <CompactSelect
                v-model="form.status"
                :options="statusOptions"
                class-name="meta-select w-full"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>分类与能力</h4>
            <p>用于运营筛选、渠道规划和模型可用性展示。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">模型家族</span>
              <input
                v-model="form.family"
                class="field"
                placeholder="例如：GPT-4o"
              />
            </label>
            <label class="field-group">
              <span class="field-label">模态</span>
              <CompactSelect
                v-model="form.modality"
                :options="modalityOptions"
                class-name="meta-select w-full"
              />
            </label>
            <label class="field-group">
              <span class="field-label">能力标签</span>
              <input
                v-model="form.feature_text"
                class="field"
                placeholder="chat, vision, tool_calling"
              />
              <span class="field-help">英文逗号分隔。</span>
            </label>
            <label class="field-group">
              <span class="field-label">上下文窗口</span>
              <input
                v-model.number="form.context_window"
                class="field"
                min="0"
                type="number"
              />
            </label>
            <label class="field-group">
              <span class="field-label">最大输出 Token</span>
              <input
                v-model.number="form.max_output_tokens"
                class="field"
                min="0"
                type="number"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>别名</h4>
            <p>别名用于从采集结果中匹配同一元模型身份。</p>
          </div>
          <div class="grid gap-4">
            <label class="field-group">
              <span class="field-label">别名</span>
              <textarea
                v-model="form.alias_text"
                class="field min-h-24 resize-none font-mono"
                placeholder="每行一个别名，例如 GPT-4o mini"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>元数据</h4>
            <p>可记录采集来源、官方页面标识或运营备注，必须是 JSON 对象。</p>
          </div>
          <textarea
            v-model="form.metadata_text"
            class="field min-h-28 resize-none font-mono"
            placeholder='{"source": "models.dev"}'
          />
        </section>
      </div>

      <div class="modal-footer">
        <p
          v-if="saveError"
          class="modal-footer-status rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700"
        >
          {{ saveError }}
        </p>
        <span v-else class="modal-footer-status modal-footer-note">
          {{
            form.id
              ? '保存后会影响关联模型的展示身份。'
              : '创建后可绑定到模型 SKU。'
          }}
        </span>
        <div class="modal-footer-actions">
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            :disabled="saving"
            @click="close"
          >
            取消
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="icon-mark" :class="saving ? 'animate-spin' : ''" />
            {{ form.id ? '保存修改' : '创建元模型' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  metaModel: {
    type: Object,
    default: null
  },
  providers: {
    type: Array,
    default: () => []
  },
  metaModels: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'saved'])

const form = ref(defaults())
const saving = ref(false)
const saveError = ref('')

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'deprecated', label: 'Deprecated' },
  { value: 'unknown', label: 'Unknown' }
]

const modalityOptions = [
  { value: 'text', label: 'Text' },
  { value: 'multimodal', label: 'Multimodal' },
  { value: 'audio', label: 'Audio' },
  { value: 'video', label: 'Video' }
]

const ownerOptions = computed(() => {
  const options = [{ value: '', label: '未绑定' }]
  const seen = new Set([''])
  props.metaModels.forEach((model) => {
    pushOwnerOption(options, seen, model.owner_code, model.owner_name)
  })
  pushOwnerOption(
    options,
    seen,
    form.value.owner_code || props.metaModel?.owner_code,
    form.value.owner_name || props.metaModel?.owner_name
  )
  return options
})

function pushOwnerOption(options, seen, code, name) {
  const value = String(code || '').trim()
  if (!value || seen.has(value)) return
  seen.add(value)
  options.push({
    value,
    label: String(name || value).trim()
  })
}

watch(
  () => [props.open, props.metaModel],
  () => {
    form.value = props.metaModel ? metaModelToForm(props.metaModel) : defaults()
    saveError.value = ''
  },
  { immediate: true }
)

function defaults() {
  return {
    id: null,
    name: '',
    code: '',
    owner_code: '',
    owner_name: '',
    owner_website: '',
    family: '',
    modality: 'text',
    status: 'active',
    context_window: 0,
    max_output_tokens: 0,
    original_capabilities: {},
    feature_text: '',
    alias_text: '',
    metadata_text: '{}'
  }
}

function metaModelToForm(item) {
  const features = item.capabilities?.features || []
  return {
    id: item.id,
    name: item.name || '',
    code: item.code || '',
    owner_code: item.owner_code || '',
    owner_name: item.owner_name || '',
    owner_website: item.owner_website || '',
    family: item.family || '',
    modality: item.modality || 'text',
    status: item.status || 'active',
    context_window: item.context_window || 0,
    max_output_tokens: item.max_output_tokens || 0,
    original_capabilities: item.capabilities || {},
    feature_text: Array.isArray(features) ? features.join(', ') : '',
    alias_text: Array.isArray(item.aliases) ? item.aliases.join('\n') : '',
    metadata_text: JSON.stringify(item.metadata || {}, null, 2)
  }
}

function close() {
  form.value = defaults()
  saveError.value = ''
  emit('close')
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    const payload = normalizePayload(form.value)
    if (form.value.id) {
      await llmOpsApi.updateMetaModel(form.value.id, payload)
    } else {
      await llmOpsApi.createMetaModel(payload)
    }
    form.value = defaults()
    emit('saved')
  } catch (error) {
    saveError.value = errorMessage(error, '元模型保存失败，请稍后重试。')
  } finally {
    saving.value = false
  }
}

function normalizePayload(payload) {
  let metadata = {}
  try {
    metadata = payload.metadata_text ? JSON.parse(payload.metadata_text) : {}
  } catch (_error) {
    throw new Error('元数据必须是合法 JSON 对象。')
  }
  if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object') {
    throw new Error('元数据必须是 JSON 对象。')
  }

  const aliases = String(payload.alias_text || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
  const features = String(payload.feature_text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const owner = props.providers.find(
    (provider) => String(provider.code) === String(payload.owner_code)
  )

  return {
    name: String(payload.name || '').trim(),
    code: String(payload.code || '').trim(),
    owner_code: payload.owner_code || '',
    owner_name: owner?.name || payload.owner_name || '',
    owner_website: owner?.website || payload.owner_website || '',
    family: String(payload.family || '').trim(),
    modality: payload.modality || 'text',
    status: payload.status || 'active',
    aliases,
    capabilities: {
      ...(payload.original_capabilities || {}),
      features
    },
    context_window: Number(payload.context_window || 0),
    max_output_tokens: Number(payload.max_output_tokens || 0),
    metadata
  }
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
.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.field-group {
  @apply block space-y-1.5;
}

.field-label {
  @apply block text-sm font-medium text-slate-800;
}

.field-help {
  @apply block text-xs leading-5 text-slate-500;
}

.form-section {
  @apply space-y-3;
}

.section-heading h4 {
  @apply text-sm font-semibold text-slate-900;
}

.section-heading p {
  @apply mt-0.5 text-xs leading-5 text-slate-500;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}
</style>
