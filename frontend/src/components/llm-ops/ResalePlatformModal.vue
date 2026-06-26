<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-3rem)] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="save"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Resale Platform
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ form.id ? '编辑挂售平台' : '新建挂售平台' }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              配置 Agione 实例、抽佣、服务费率、免审利润率和积分规则。
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
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
            <h4>平台信息</h4>
            <p>用于区分多个 Agione 实例和后续接口适配。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">平台名称</span>
              <input
                v-model="form.name"
                class="field"
                placeholder="例如：Agione 主平台"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">平台标识</span>
              <input
                v-model="form.code"
                class="field"
                placeholder="例如：agione-main"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">官网地址</span>
              <input
                v-model="form.website"
                class="field"
                placeholder="https://www.agione.com"
                type="url"
              />
            </label>
            <label class="field-group">
              <span class="field-label">API 接入地址</span>
              <input
                v-model="form.api_endpoint"
                class="field"
                placeholder="https://api.example.com"
                type="url"
              />
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">平台 API Key</span>
              <input
                v-model="form.api_key"
                class="field font-mono"
                autocomplete="off"
                placeholder="用于挂售接口鉴权"
                type="password"
              />
              <span class="field-help">
                用于调用挂售平台接口执行上架、改价和下架操作。
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>结算与积分</h4>
            <p>用于挂售页将平台上架价换算为积分。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">平台货币</span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">平台抽佣比例（%）</span>
              <input
                v-model="form.fee_rate"
                class="field"
                min="0"
                max="99.99"
                step="0.01"
                type="number"
                placeholder="例如：3"
              />
            </label>
            <label class="field-group">
              <span class="field-label">服务费率（%）</span>
              <input
                v-model="form.service_fee_rate"
                class="field"
                min="0"
                max="99.99"
                step="0.01"
                type="number"
                placeholder="例如：10"
              />
            </label>
            <label class="field-group">
              <span class="field-label">免审最高利润率（%）</span>
              <input
                v-model="form.auto_approve_max_margin_rate"
                class="field"
                min="0"
                step="0.01"
                type="number"
                placeholder="例如：20"
              />
            </label>
            <label class="field-group">
              <span class="field-label">积分名称</span>
              <input
                v-model="form.point_name"
                class="field"
                placeholder="积分"
              />
            </label>
            <label class="field-group">
              <span class="field-label">积分兑换比例（每 1 平台货币）</span>
              <input
                v-model="form.points_per_currency_unit"
                class="field"
                min="0.000001"
                step="0.000001"
                type="number"
                placeholder="例如：100"
              />
            </label>
            <label class="field-group">
              <span class="field-label">积分取整方式</span>
              <CompactSelect
                v-model="form.point_rounding_mode"
                :options="roundingModeOptions"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>备注</h4>
            <p>记录平台差异、合同口径或接口限制。</p>
          </div>
          <textarea
            v-model="form.notes"
            class="field min-h-20 resize-none"
            placeholder="例如：积分倍率来源、结算周期、接口适配状态"
          />
        </section>
      </div>

      <div class="modal-footer">
        <label class="status-inline" :class="{ active: form.is_active }">
          <input v-model="form.is_active" type="checkbox" class="sr-only" />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{ form.is_active ? '平台已启用' : '平台已停用' }}
          </span>
        </label>
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
            {{ saving ? '保存中' : form.id ? '保存修改' : '创建平台' }}
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
  platform: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const form = ref(defaults())
const saving = ref(false)
const currencyOptions = [
  { label: 'CNY', value: 'CNY' },
  { label: 'USD', value: 'USD' }
]
const roundingModeOptions = [
  { label: '四舍五入', value: 'half_up' },
  { label: '向上取整', value: 'up' },
  { label: '向下取整', value: 'down' }
]

watch(
  () => [props.open, props.platform],
  () => {
    form.value = props.platform ? platformToForm(props.platform) : defaults()
  },
  { immediate: true }
)

function defaults() {
  return {
    id: null,
    name: '',
    code: '',
    website: '',
    api_endpoint: '',
    api_key: '',
    currency: 'CNY',
    fee_rate: '3',
    service_fee_rate: '0',
    auto_approve_max_margin_rate: '100',
    point_name: '积分',
    points_per_currency_unit: '100',
    point_rounding_mode: 'half_up',
    notes: '',
    is_active: true
  }
}

function platformToForm(platform) {
  return {
    ...platform,
    fee_rate: percentFromRatio(platform.fee_rate),
    service_fee_rate: percentFromRatio(platform.service_fee_rate)
  }
}

function percentFromRatio(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return ''
  return (numberValue * 100).toFixed(2).replace(/\.?0+$/, '')
}

function ratioFromPercent(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return 0
  return Number((numberValue / 100).toFixed(6))
}

function normalizePayload(payload) {
  const clean = { ...payload }
  clean.code = String(clean.code || '')
    .trim()
    .toLowerCase()
  clean.currency = String(clean.currency || 'CNY')
    .trim()
    .toUpperCase()
  clean.fee_rate = ratioFromPercent(clean.fee_rate)
  clean.service_fee_rate = ratioFromPercent(clean.service_fee_rate)
  delete clean.id
  delete clean.listing_count
  return clean
}

function close() {
  form.value = defaults()
  emit('close')
}

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = normalizePayload(form.value)
    if (form.value.id) {
      await llmOpsApi.updateResalePlatform(form.value.id, payload)
    } else {
      await llmOpsApi.createResalePlatform(payload)
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

.status-inline {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.status-inline.active {
  @apply border-emerald-100 bg-emerald-50;
}

.status-switch {
  @apply inline-flex h-5 w-9 items-center rounded-full bg-slate-300 p-0.5 transition;
}

.status-inline.active .status-switch {
  @apply bg-emerald-500;
}

.status-switch-dot {
  @apply h-4 w-4 rounded-full bg-white shadow transition;
}

.status-inline.active .status-switch-dot {
  transform: translateX(1rem);
}
</style>
