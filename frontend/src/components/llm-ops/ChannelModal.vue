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
              Channel
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{
                form.id
                  ? t('llmOps.channelModal.editTitle')
                  : t('llmOps.channelModal.createTitle')
              }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('llmOps.channelModal.description') }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            :disabled="saving"
            @click="close"
          >
            {{ t('common.close') }}
          </button>
        </div>
      </div>
      <div
        class="max-h-[calc(100vh-15rem)] space-y-5 overflow-y-auto px-5 py-5"
      >
        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.channelModal.basicTitle') }}</h4>
            <p>{{ t('llmOps.channelModal.basicHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.channelModal.fields.name') }}
              </span>
              <input
                v-model="form.name"
                class="field"
                :placeholder="t('llmOps.channelModal.placeholders.name')"
                required
              />
              <span class="field-help">
                {{ t('llmOps.channelModal.help.name') }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.channelModal.fields.code') }}
              </span>
              <input
                v-model="form.code"
                class="field"
                :placeholder="t('llmOps.channelModal.placeholders.code')"
                required
              />
              <span class="field-help">
                {{ t('llmOps.channelModal.help.code') }}
              </span>
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.channelModal.fields.apiEndpoint') }}
              </span>
              <input
                v-model="form.api_endpoint"
                class="field"
                :placeholder="t('llmOps.channelModal.placeholders.apiEndpoint')"
              />
              <span class="field-help">
                {{ t('llmOps.channelModal.help.apiEndpoint') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.channelModal.settlementTitle') }}</h4>
            <p>{{ t('llmOps.channelModal.settlementHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.channelModal.fields.currency') }}
              </span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
              <span class="field-help">
                {{ t('llmOps.channelModal.help.currency') }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.channelModal.fields.settlementRatio') }}
              </span>
              <div class="relative">
                <input
                  v-model="settlementRatioPercent"
                  class="field pr-16"
                  min="0.01"
                  step="0.01"
                  type="number"
                  :placeholder="
                    t('llmOps.channelModal.placeholders.settlementRatio')
                  "
                />
                <span class="field-suffix">%</span>
              </div>
              <span class="field-help">
                {{ t('llmOps.channelModal.help.settlementRatio') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.channelModal.notesTitle') }}</h4>
            <p>{{ t('llmOps.channelModal.notesHint') }}</p>
          </div>
          <label class="field-group">
            <span class="field-label">
              {{ t('llmOps.channelModal.fields.notes') }}
            </span>
            <textarea
              v-model="form.notes"
              class="field min-h-20 resize-none"
              :placeholder="t('llmOps.channelModal.placeholders.notes')"
            />
            <span class="field-help">
              {{ t('llmOps.channelModal.help.notes') }}
            </span>
          </label>
        </section>
      </div>
      <div class="modal-footer">
        <label
          class="modal-footer-status status-inline"
          :class="{ active: form.is_active }"
        >
          <input v-model="form.is_active" type="checkbox" class="sr-only" />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{
              form.is_active
                ? t('llmOps.channelModal.enabled')
                : t('llmOps.channelModal.disabled')
            }}
          </span>
        </label>
        <div class="modal-footer-actions">
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            :disabled="saving"
            @click="close"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="icon-mark" />
            {{
              saving
                ? t('common.saving')
                : form.id
                  ? t('llmOps.channelModal.saveChanges')
                  : t('llmOps.channelModal.createChannel')
            }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

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
const { t } = useI18n()

const form = ref(defaults())
const saving = ref(false)
const currencyOptions = [
  { label: 'CNY', value: 'CNY' },
  { label: 'USD', value: 'USD' }
]

const settlementRatioPercent = computed({
  get() {
    const ratio = Number(form.value.settlement_ratio)
    if (!Number.isFinite(ratio)) return ''
    return Number((ratio * 100).toFixed(4))
  },
  set(value) {
    if (value === '' || value === null || value === undefined) {
      form.value.settlement_ratio = ''
      return
    }
    const percent = Number(value)
    form.value.settlement_ratio = Number.isFinite(percent)
      ? String(percent / 100)
      : ''
  }
})

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
  clean.currency = String(clean.currency || 'CNY')
    .trim()
    .toUpperCase()
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
