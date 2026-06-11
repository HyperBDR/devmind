<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl"
      @submit.prevent="save"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Channel
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ form.id ? '编辑转发渠道' : '新增转发渠道' }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              渠道用于配置可采购/转发模型的供应入口和默认结算规则。
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
      </div>
      <div class="max-h-[calc(100vh-12rem)] space-y-5 overflow-y-auto px-5 py-5">
        <section class="form-section">
          <div class="section-heading">
            <h4>基础信息</h4>
            <p>用于识别渠道，以及记录后续对接接口的入口。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">渠道显示名称</span>
              <input
                v-model="form.name"
                class="field"
                placeholder="例如：真实资源平台"
                required
              />
              <span class="field-help">
                展示在渠道列表、模型转发关系和价格对比中的名称。
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">渠道标识</span>
              <input
                v-model="form.code"
                class="field"
                placeholder="例如：real-resource-platform"
                required
              />
              <span class="field-help">
                系统唯一标识，建议使用小写英文、数字和短横线。
              </span>
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">转发 API Base URL</span>
              <input
                v-model="form.api_endpoint"
                class="field"
                placeholder="例如：https://llm.example.com/v1"
              />
              <span class="field-help">
                渠道提供的模型转发接口地址；暂无接口时可先留空。
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>结算规则</h4>
            <p>作为该渠道模型的默认采购价规则，单个模型仍可覆盖。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">默认结算币种</span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
              <span class="field-help">
                渠道默认采购币种；单个模型可在模型管理中覆盖。
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">默认采购折扣比例</span>
              <div class="relative">
                <input
                  v-model="form.settlement_ratio"
                  class="field pr-16"
                  min="0.0001"
                  step="0.0001"
                  type="number"
                  placeholder="例如：0.85"
                />
                <span class="field-suffix">倍</span>
              </div>
              <span class="field-help">
                采购价 = 价格源价格 × 折扣比例；1 为原价。
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>补充信息</h4>
            <p>记录合同、账期或模型覆盖限制。</p>
          </div>
          <label class="field-group">
            <span class="field-label">运营备注</span>
            <textarea
              v-model="form.notes"
              class="field min-h-20 resize-none"
              placeholder="例如：合同折扣、结算周期、特殊限制"
            />
            <span class="field-help">
              可记录账期、限流、合同折扣、模型覆盖范围等信息。
            </span>
          </label>
        </section>
      </div>
      <div
        class="flex flex-col gap-3 border-t border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between"
      >
        <label class="status-inline" :class="{ active: form.is_active }">
          <input
            v-model="form.is_active"
            type="checkbox"
            class="sr-only"
          />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{ form.is_active ? '渠道已启用' : '渠道已停用' }}
          </span>
        </label>
        <div class="flex justify-end gap-2">
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
            {{ saving ? '保存中' : form.id ? '保存修改' : '创建渠道' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  channel: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const form = ref(defaults())
const saving = ref(false)
const currencyOptions = [
  { label: 'CNY - 人民币', value: 'CNY' },
  { label: 'USD - 美元', value: 'USD' }
]

watch(
  () => [props.open, props.channel],
  () => {
    form.value = props.channel ? { ...props.channel } : defaults()
  },
  { immediate: true }
)

function defaults() {
  return {
    id: null,
    name: '',
    code: '',
    api_endpoint: '',
    currency: 'CNY',
    settlement_ratio: '1',
    notes: '',
    is_active: true
  }
}

function normalizePayload(payload) {
  const clean = { ...payload }
  clean.currency = String(clean.currency || 'CNY').trim().toUpperCase()
  delete clean.id
  return clean
}

function close() {
  form.value = defaults()
  emit('close')
}

async function save() {
  if (saving.value) {
    return
  }
  saving.value = true
  const payload = normalizePayload(form.value)
  try {
    if (form.value.id) {
      await llmOpsApi.updateChannel(form.value.id, payload)
    } else {
      await llmOpsApi.createChannel(payload)
    }
    form.value = defaults()
    emit('saved')
  } finally {
    saving.value = false
  }
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

.field-suffix {
  @apply pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-slate-400;
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

.status-inline {
  @apply inline-flex w-fit cursor-pointer items-center gap-2 rounded-lg px-1 py-1;
}

.status-switch {
  @apply relative h-6 w-10 shrink-0 rounded-full bg-slate-300 transition;
}

.status-inline.active .status-switch {
  @apply bg-indigo-600;
}

.status-switch-dot {
  @apply absolute left-1 top-1 h-4 w-4 rounded-full bg-white shadow transition;
}

.status-inline.active .status-switch-dot {
  @apply translate-x-4;
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
