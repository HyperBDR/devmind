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
          <div class="min-w-0">
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Provider
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ form.id ? '编辑模型厂商' : '新建模型厂商' }}
            </h3>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              模型厂商由系统适配，页面只维护展示名称、价格采集地址和运营备注。
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
            <h4>基础信息</h4>
            <p>用于在模型定价、渠道发布和 Agione 挂售中识别厂商。</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">厂商显示名称</span>
              <input
                v-model="form.name"
                class="field"
                placeholder="例如：OpenAI"
                required
              />
              <span class="field-help">
                展示在厂商列表、模型详情和运营总览中的名称。
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">厂商标识 Code</span>
              <input
                v-model="form.code"
                class="field font-mono disabled:bg-slate-50 disabled:text-slate-400"
                :disabled="Boolean(form.id)"
                placeholder="例如：openai"
                required
              />
              <span class="field-help">
                系统适配标识，已创建厂商不建议修改。
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>价格采集地址</h4>
            <p>只影响该厂商绑定的模型价格源，不修改厂商官网或 API 接入地址。</p>
          </div>
          <label class="field-group">
            <span class="field-label">价格源地址</span>
            <input
              v-model="form.price_source_endpoint_url"
              class="field"
              placeholder="例如：https://models.dev/api.json"
              type="url"
              :disabled="!form.primary_source_id"
            />
            <span class="field-help">
              可填写厂商官方价格页，或使用 https://models.dev/api.json
              作为聚合价格数据源；停用状态请在模型价格源列表中维护。
            </span>
          </label>
          <a
            v-if="form.price_source_endpoint_url"
            class="source-preview"
            :href="form.price_source_endpoint_url"
            rel="noopener noreferrer"
            target="_blank"
            :title="form.price_source_endpoint_url"
          >
            <span class="icon-mark" />
            <span class="truncate">{{ form.price_source_endpoint_url }}</span>
          </a>
          <p
            v-if="form.website"
            class="mt-2 truncate text-xs text-slate-400"
            :title="form.website"
          >
            厂商官网 / 接入地址：{{ form.website }}
          </p>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>运营备注</h4>
            <p>记录价格口径、采集限制或厂商适配说明。</p>
          </div>
          <label class="field-group">
            <span class="field-label">备注</span>
            <textarea
              v-model="form.notes"
              class="field min-h-24 resize-none"
              placeholder="例如：价格页更新频率、特殊模型口径、待补充采集适配"
            />
          </label>
        </section>
      </div>

      <div class="modal-footer">
        <div class="modal-footer-status min-w-0 space-y-2">
          <label class="status-inline" :class="{ active: form.is_active }">
            <input v-model="form.is_active" type="checkbox" class="sr-only" />
            <span class="status-switch" aria-hidden="true">
              <span class="status-switch-dot" />
            </span>
            <span class="text-sm text-slate-700">
              {{ form.is_active ? '厂商已启用' : '厂商已停用' }}
            </span>
          </label>
          <p
            v-if="saveError"
            class="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700"
          >
            {{ saveError }}
          </p>
        </div>
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
            {{ form.id ? '保存修改' : '创建厂商' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  provider: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const form = ref(defaults())
const saving = ref(false)
const saveError = ref('')

watch(
  () => [props.open, props.provider],
  () => {
    form.value = props.provider ? providerToForm(props.provider) : defaults()
  },
  { immediate: true }
)

function defaults() {
  return {
    id: null,
    name: '',
    code: '',
    website: '',
    primary_source_id: null,
    price_source_endpoint_url: '',
    original_price_source_endpoint_url: '',
    notes: '',
    is_active: true
  }
}

function providerToForm(provider) {
  const endpoint =
    provider.primary_source_url || provider.price_source_url || ''
  return {
    id: provider.id,
    name: provider.name || '',
    code: provider.code || '',
    website: provider.website || '',
    primary_source_id: provider.primary_source_id || null,
    price_source_endpoint_url: endpoint,
    original_price_source_endpoint_url: endpoint,
    notes: provider.notes || '',
    is_active: provider.is_active !== false
  }
}

function normalizePayload(payload) {
  const clean = {
    name: payload.name,
    code: payload.code,
    notes: payload.notes,
    is_active: payload.is_active
  }
  clean.code = String(clean.code || '')
    .trim()
    .toLowerCase()
  return clean
}

function close() {
  form.value = defaults()
  saveError.value = ''
  emit('close')
}

async function save() {
  saving.value = true
  saveError.value = ''
  let providerSaved = false
  try {
    const payload = normalizePayload(form.value)
    if (form.value.id) {
      await llmOpsApi.updateProvider(form.value.id, payload)
    } else {
      await llmOpsApi.createProvider(payload)
    }
    providerSaved = true
    await savePriceSourceEndpoint()
    form.value = defaults()
    emit('saved')
  } catch (error) {
    saveError.value = providerSaved
      ? errorMessage(error, '厂商已保存，但价格源地址保存失败，请重试。')
      : errorMessage(error, '模型厂商保存失败，请稍后重试。')
  } finally {
    saving.value = false
  }
}

async function savePriceSourceEndpoint() {
  if (!form.value.primary_source_id) return
  const nextEndpoint = String(form.value.price_source_endpoint_url || '').trim()
  const previousEndpoint = String(
    form.value.original_price_source_endpoint_url || ''
  ).trim()
  if (nextEndpoint === previousEndpoint) return
  await llmOpsApi.updateCollectionSource(form.value.primary_source_id, {
    endpoint_url: nextEndpoint
  })
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

.source-preview {
  @apply flex min-w-0 items-center gap-2 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-100;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.status-inline {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.status-switch {
  @apply relative inline-flex h-5 w-9 shrink-0 rounded-full bg-slate-300 transition;
}

.status-switch-dot {
  @apply absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition;
}

.status-inline.active {
  @apply border-emerald-100 bg-emerald-50;
}

.status-inline.active .status-switch {
  @apply bg-emerald-500;
}

.status-inline.active .status-switch-dot {
  transform: translateX(1rem);
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}
</style>
