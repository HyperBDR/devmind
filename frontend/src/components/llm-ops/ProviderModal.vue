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
              {{
                form.id
                  ? t('llmOps.providerModal.editTitle')
                  : t('llmOps.providerModal.createTitle')
              }}
            </h3>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              {{ t('llmOps.providerModal.description') }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel shrink-0"
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
            <h4>{{ t('llmOps.providerModal.basicTitle') }}</h4>
            <p>{{ t('llmOps.providerModal.basicHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.providerModal.fields.name') }}
              </span>
              <input
                v-model="form.name"
                class="field"
                :placeholder="t('llmOps.providerModal.placeholders.name')"
                required
              />
              <span class="field-help">
                {{ t('llmOps.providerModal.help.name') }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.providerModal.fields.code') }}
              </span>
              <input
                v-model="form.code"
                class="field font-mono disabled:bg-slate-50 disabled:text-slate-400"
                :disabled="Boolean(form.id)"
                :placeholder="t('llmOps.providerModal.placeholders.code')"
                required
              />
              <span class="field-help">
                {{ t('llmOps.providerModal.help.code') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.providerModal.priceSourceTitle') }}</h4>
            <p>{{ t('llmOps.providerModal.priceSourceHint') }}</p>
          </div>
          <label class="field-group">
            <span class="field-label">
              {{ t('llmOps.providerModal.fields.priceSourceEndpoint') }}
            </span>
            <input
              v-model="form.price_source_endpoint_url"
              class="field"
              :placeholder="
                t('llmOps.providerModal.placeholders.priceSourceEndpoint')
              "
              type="url"
              :disabled="!form.primary_source_id"
            />
            <span class="field-help">
              {{ t('llmOps.providerModal.help.priceSourceEndpoint') }}
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
            {{
              t('llmOps.providerModal.websitePrefix', {
                website: form.website
              })
            }}
          </p>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.providerModal.notesTitle') }}</h4>
            <p>{{ t('llmOps.providerModal.notesHint') }}</p>
          </div>
          <label class="field-group">
            <span class="field-label">
              {{ t('llmOps.providerModal.fields.notes') }}
            </span>
            <textarea
              v-model="form.notes"
              class="field min-h-24 resize-none"
              :placeholder="t('llmOps.providerModal.placeholders.notes')"
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
              {{
                form.is_active
                  ? t('llmOps.providerModal.enabled')
                  : t('llmOps.providerModal.disabled')
              }}
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
            {{ t('common.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="icon-mark" :class="saving ? 'animate-spin' : ''" />
            {{
              form.id
                ? t('llmOps.providerModal.saveChanges')
                : t('llmOps.providerModal.createProvider')
            }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

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
const { t } = useI18n()

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
      ? errorMessage(error, t('llmOps.providerModal.errors.sourceSaveFailed'))
      : errorMessage(error, t('llmOps.providerModal.errors.saveFailed'))
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
