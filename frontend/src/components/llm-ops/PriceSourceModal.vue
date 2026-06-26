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
              Price Source
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{
                isEditing
                  ? t('llmOps.priceSourceModal.title.edit')
                  : t('llmOps.priceSourceModal.title.create')
              }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{
                isEditing
                  ? t('llmOps.priceSourceModal.description.edit')
                  : t('llmOps.priceSourceModal.description.create')
              }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            :disabled="saving"
            @click="close"
          >
            {{ t('llmOps.priceSourceModal.actions.close') }}
          </button>
        </div>
      </div>

      <div
        class="max-h-[calc(100vh-15rem)] space-y-5 overflow-y-auto px-5 py-5"
      >
        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.priceSourceModal.sections.basic') }}</h4>
            <p>{{ t('llmOps.priceSourceModal.sections.basicHint') }}</p>
          </div>
          <div class="source-meta-strip">
            <div class="source-meta-item">
              <span>{{ t('llmOps.priceSourceModal.fields.slug') }}</span>
              <strong>{{ internalSlugLabel }}</strong>
            </div>
            <div class="source-meta-item">
              <span>{{ t('llmOps.priceSourceModal.fields.sourceType') }}</span>
              <strong>{{ sourceTypeLabel }}</strong>
            </div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.name') }}
              </span>
              <input
                v-model="form.name"
                class="field"
                :placeholder="t('llmOps.priceSourceModal.placeholders.name')"
                required
              />
              <span v-if="!isEditing" class="field-help">
                {{
                  t('llmOps.priceSourceModal.help.autoSlug', {
                    slug: internalSlugLabel
                  })
                }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.category') }}
              </span>
              <CompactSelect
                v-model="form.source_category"
                :options="sourceCategoryOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.currency') }}
              </span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.endpointUrl') }}
              </span>
              <input
                v-model="form.endpoint_url"
                class="field"
                placeholder="https://example.com/pricing"
                type="url"
              />
              <span class="field-help">
                {{ t('llmOps.priceSourceModal.help.endpointUrl') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.priceSourceModal.sections.notes') }}</h4>
            <p>{{ t('llmOps.priceSourceModal.sections.notesHint') }}</p>
          </div>
          <textarea
            v-model="form.notes"
            class="field min-h-20 resize-none"
            :placeholder="t('llmOps.priceSourceModal.placeholders.notes')"
          />
        </section>
      </div>

      <div class="modal-footer">
        <label
          class="modal-footer-status status-inline"
          :class="{ active: form.is_enabled }"
        >
          <input v-model="form.is_enabled" type="checkbox" class="sr-only" />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{
              form.is_enabled
                ? t('llmOps.priceSourceModal.status.enabled')
                : t('llmOps.priceSourceModal.status.disabled')
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
            {{ t('llmOps.priceSourceModal.actions.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="icon-mark" />
            {{
              saving
                ? t('llmOps.priceSourceModal.actions.saving')
                : isEditing
                  ? t('llmOps.priceSourceModal.actions.saveChanges')
                  : t('llmOps.priceSourceModal.actions.create')
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
  }
})

const emit = defineEmits(['close', 'saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

const saving = ref(false)
const form = ref(defaults())
const isEditing = computed(() => Boolean(props.source?.id))
const internalSlugLabel = computed(() =>
  isEditing.value ? form.value.slug || '-' : autoSlug(form.value.name || '')
)
const sourceTypeLabel = computed(() => {
  const type = props.source?.source_type || 'custom'
  const labels = {
    agione: 'Agione',
    yunce: 'Yunce',
    custom: t('llmOps.priceSourceModal.sourceTypes.custom')
  }
  return labels[type] || type || '-'
})

const sourceCategoryOptions = computed(() => [
  {
    label: t('llmOps.priceSourceModal.categories.officialProvider'),
    value: 'official_provider'
  },
  {
    label: t('llmOps.priceSourceModal.categories.supplier'),
    value: 'supplier'
  },
  {
    label: t('llmOps.priceSourceModal.categories.manual'),
    value: 'manual'
  },
  {
    label: t('llmOps.priceSourceModal.categories.unknown'),
    value: 'unknown'
  }
])

const currencyOptions = computed(() => [
  { label: t('llmOps.priceSourceModal.currencies.cny'), value: 'CNY' },
  { label: t('llmOps.priceSourceModal.currencies.usd'), value: 'USD' }
])

watch(
  () => props.source,
  (source) => {
    form.value = source ? normalizeSource(source) : defaults()
  },
  { immediate: true }
)

function defaults() {
  return {
    name: '',
    slug: '',
    source_category: 'supplier',
    endpoint_url: '',
    currency: 'CNY',
    is_enabled: true,
    updates_model_prices: false,
    notes: ''
  }
}

function normalizeSource(source) {
  return {
    name: source.name || '',
    slug: source.slug || '',
    source_category: source.source_category || 'unknown',
    endpoint_url: source.endpoint_url || '',
    currency: source.currency || 'CNY',
    is_enabled: source.is_enabled !== false,
    updates_model_prices: Boolean(source.updates_model_prices),
    notes: source.notes || ''
  }
}

function close() {
  if (saving.value) return
  emit('close')
}

async function save() {
  saving.value = true
  try {
    const payload = {
      ...form.value,
      slug: isEditing.value
        ? props.source?.slug || form.value.slug || autoSlug(form.value.name)
        : form.value.slug || autoSlug(form.value.name),
      source_type: props.source?.source_type || 'custom'
    }
    if (isEditing.value) {
      await llmOpsApi.updateCollectionSource(props.source.id, payload)
      showSuccess(t('llmOps.priceSourceModal.messages.updated'))
    } else {
      await llmOpsApi.createCollectionSource(payload)
      showSuccess(t('llmOps.priceSourceModal.messages.created'))
    }
    emit('saved')
  } catch (error) {
    showError(errorMessage(error, t('llmOps.priceSourceModal.errors.save')))
  } finally {
    saving.value = false
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

function autoSlug(value) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || 'price-source'
}
</script>

<style scoped>
.form-section {
  @apply rounded-lg border border-slate-200 bg-slate-50 p-4;
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

.field-group {
  @apply flex min-w-0 flex-col gap-1.5;
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

.source-meta-strip {
  @apply mb-4 grid gap-3 sm:grid-cols-2;
}

.source-meta-item {
  @apply rounded-lg border border-slate-200 bg-white px-3 py-2;
}

.source-meta-item span {
  @apply block text-xs text-slate-500;
}

.source-meta-item strong {
  @apply mt-1 block truncate font-mono text-sm text-slate-800;
}

.status-inline {
  @apply inline-flex items-center gap-2;
}

.status-switch {
  @apply flex h-5 w-9 items-center rounded-full bg-slate-300 p-0.5 transition;
}

.status-inline.active .status-switch {
  @apply bg-emerald-500;
}

.status-switch-dot {
  @apply h-4 w-4 rounded-full bg-white shadow transition;
}

.status-inline.active .status-switch-dot {
  @apply translate-x-4;
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
</style>
