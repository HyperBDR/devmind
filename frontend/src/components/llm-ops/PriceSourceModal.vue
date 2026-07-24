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
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.slug') }}
              </span>
              <input
                v-model="form.slug"
                class="field font-mono"
                :disabled="!canEditSlug"
                maxlength="100"
                :placeholder="sourceSlugLabel"
                @blur="normalizeSlugField"
              />
              <span class="field-help">
                {{ slugHelpText }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.syncMode') }}
              </span>
              <CompactSelect v-model="syncMode" :options="syncModeOptions" />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.autoSyncSource') }}
              </span>
              <CompactSelect
                v-model="selectedAutoSyncSourceCode"
                :disabled="
                  !shouldCreateAutoSyncPreset ||
                  loadingAutoSyncSourceOptions ||
                  saving
                "
                :options="autoSyncSourceSelectOptions"
                class-name="w-full"
                :menu-min-width="360"
                :placeholder="
                  t('llmOps.priceSourceModal.autoSyncPreset.selectSource')
                "
              />
              <span class="field-help">
                {{ autoSyncSourceHelpText }}
              </span>
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
            :disabled="saving || saveDisabled"
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
import { userFacingApiError } from '@/utils/llmOpsErrors'

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
const autoSyncSourceOptions = ref([])
const selectedAutoSyncSourceCode = ref('')
const loadingAutoSyncSourceOptions = ref(false)
const isEditing = computed(() => Boolean(props.source?.id))
const isAutoSyncMode = computed(() => syncMode.value === 'auto')
const shouldCreateAutoSyncPreset = computed(
  () => !isEditing.value && isAutoSyncMode.value
)
const canEditSlug = computed(
  () => !shouldCreateAutoSyncPreset.value && !isStableOfficialSource.value
)
const isStableOfficialSource = computed(() => {
  if (!isEditing.value) return false
  const source = props.source || {}
  const providerCode = String(source.provider_code || '').trim()
  if (!providerCode) return false
  const ownerType =
    source.source_owner_type ||
    sourceOwnerTypeFromLegacyCategory(source.source_category)
  return (
    ['model_provider_official', 'cloud_provider_official'].includes(
      ownerType
    ) && String(source.slug || '') === `${providerCode}-official`
  )
})
const slugHelpText = computed(() => {
  if (shouldCreateAutoSyncPreset.value && !selectedAutoSyncSourceOption.value) {
    return t('llmOps.priceSourceModal.help.autoSyncSlugPreset')
  }
  if (isStableOfficialSource.value) {
    return t('llmOps.priceSourceModal.help.autoSyncSlugLocked')
  }
  if (shouldCreateAutoSyncPreset.value) {
    return t('llmOps.priceSourceModal.help.autoSyncSlugLocked')
  }
  if (isEditing.value) {
    return t('llmOps.priceSourceModal.help.slug')
  }
  return t('llmOps.priceSourceModal.help.autoSlug', {
    slug: sourceSlugLabel.value
  })
})
const sourceSlugLabel = computed(() => {
  if (shouldCreateAutoSyncPreset.value && selectedAutoSyncSourceOption.value) {
    return selectedAutoSyncSourceOption.value.source_slug || '-'
  }
  return autoSlug(form.value.name || '')
})
const syncModeOptions = computed(() => [
  {
    label: t('llmOps.priceSourceModal.syncModes.auto'),
    value: 'auto'
  },
  {
    label: t('llmOps.priceSourceModal.syncModes.manual'),
    value: 'manual'
  }
])

const syncMode = computed({
  get() {
    if (
      ['manual_entry', 'manual_import'].includes(form.value.collection_method)
    ) {
      return 'manual'
    }
    return form.value.source_owner_type === 'internal' ? 'manual' : 'auto'
  },
  set(value) {
    if (value === 'manual') {
      selectedAutoSyncSourceCode.value = ''
      form.value = {
        ...form.value,
        source_owner_type: 'internal',
        source_category: 'manual',
        collection_method: 'manual_entry',
        updates_model_prices: false
      }
      return
    }
    selectedAutoSyncSourceCode.value = ''
    form.value = {
      ...form.value,
      source_owner_type: 'supplier',
      source_category: 'supplier',
      collection_method: 'auto_collect',
      updates_model_prices: true
    }
    if (!autoSyncSourceOptions.value.length) {
      loadAutoSyncSourceOptions()
    }
  }
})

const currencyOptions = computed(() => [
  { label: t('llmOps.priceSourceModal.currencies.cny'), value: 'CNY' },
  { label: t('llmOps.priceSourceModal.currencies.usd'), value: 'USD' }
])

const autoSyncSourceSelectOptions = computed(() =>
  autoSyncSourceOptions.value.map((option) => ({
    value: sourceOptionKey(option),
    label: option.provider_name,
    description: option.source_name,
    badge: option.source_exists
      ? t('llmOps.priceSourceModal.autoSyncPreset.existsBadge')
      : option.currency
  }))
)

const selectedAutoSyncSourceOption = computed(() =>
  autoSyncSourceOptions.value.find(
    (option) => sourceOptionKey(option) === selectedAutoSyncSourceCode.value
  )
)

const autoSyncSourceStatus = computed(() => {
  if (loadingAutoSyncSourceOptions.value) {
    return t('llmOps.priceSourceModal.autoSyncPreset.loading')
  }
  const option = selectedAutoSyncSourceOption.value
  if (!option && autoSyncSourceOptions.value.length) {
    return t('llmOps.priceSourceModal.autoSyncPreset.selectSource')
  }
  if (!option) return t('llmOps.priceSourceModal.autoSyncPreset.empty')
  if (option.source_exists) {
    return t('llmOps.priceSourceModal.autoSyncPreset.exists')
  }
  return t('llmOps.priceSourceModal.autoSyncPreset.ready')
})

const autoSyncSourceHelpText = computed(() => {
  if (!shouldCreateAutoSyncPreset.value) {
    return t('llmOps.priceSourceModal.autoSyncPreset.manualMode')
  }
  return autoSyncSourceStatus.value
})

const saveDisabled = computed(
  () => shouldCreateAutoSyncPreset.value && !selectedAutoSyncSourceOption.value
)

watch(
  () => props.source,
  (source) => {
    form.value = source ? normalizeSource(source) : defaults()
  },
  { immediate: true }
)

watch(
  () => props.open,
  (open) => {
    if (open && shouldCreateAutoSyncPreset.value) {
      loadAutoSyncSourceOptions()
    }
  }
)

watch(
  () => form.value.source_owner_type,
  () => {
    if (
      props.open &&
      shouldCreateAutoSyncPreset.value &&
      !autoSyncSourceOptions.value.length
    ) {
      loadAutoSyncSourceOptions()
    }
  }
)

watch(selectedAutoSyncSourceOption, (option) => {
  if (!shouldCreateAutoSyncPreset.value || !option) return
  applyAutoSyncSourceOption(option)
})

function defaults() {
  return {
    name: '',
    slug: '',
    source_owner_type: 'model_provider_official',
    collection_method: 'auto_collect',
    endpoint_url: '',
    currency: 'CNY',
    is_enabled: true,
    updates_model_prices: true,
    notes: ''
  }
}

function normalizeSource(source) {
  return {
    name: source.name || '',
    slug: source.slug || '',
    source_owner_type:
      source.source_owner_type ||
      sourceOwnerTypeFromLegacyCategory(source.source_category),
    collection_method: source.collection_method || 'unknown',
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
    if (shouldCreateAutoSyncPreset.value) {
      await saveAutoSyncSource()
      return
    }
    const submittedSlug = canEditSlug.value
      ? normalizeSlug(form.value.slug) || autoSlug(form.value.name)
      : props.source?.slug || form.value.slug || autoSlug(form.value.name)
    const payload = {
      ...form.value,
      slug: submittedSlug,
      source_type: props.source?.source_type || 'custom'
    }
    if (!isAutoSyncMode.value) {
      payload.source_category = 'manual'
      payload.source_owner_type = 'internal'
      payload.collection_method = 'manual_entry'
      payload.updates_model_prices = false
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

async function saveAutoSyncSource() {
  const option = selectedAutoSyncSourceOption.value
  if (!option) return

  let sourceName = option.source_name
  if (isStableOfficialOption(option)) {
    const response = await llmOpsApi.ensureOfficialProviderSource(
      option.provider_code
    )
    const payload = response?.data?.data || response?.data || {}
    sourceName = payload.source?.name || sourceName
  } else if (!option.source_exists) {
    await llmOpsApi.createCollectionSource(autoSyncSourcePayload(option))
  }
  showSuccess(
    t(
      option.source_exists
        ? 'llmOps.priceSourceModal.messages.autoSyncExists'
        : 'llmOps.priceSourceModal.messages.autoSyncCreated',
      {
        name: sourceName
      }
    )
  )
  emit('saved')
}

async function loadAutoSyncSourceOptions() {
  if (loadingAutoSyncSourceOptions.value) return
  loadingAutoSyncSourceOptions.value = true
  try {
    const response = await llmOpsApi.listAutoSyncSourceOptions()
    const payload = response?.data?.data || response?.data || {}
    const options = Array.isArray(payload.results) ? payload.results : []
    autoSyncSourceOptions.value = options
    const current = options.find(
      (option) => sourceOptionKey(option) === selectedAutoSyncSourceCode.value
    )
    selectedAutoSyncSourceCode.value = current ? sourceOptionKey(current) : ''
    if (current) applyAutoSyncSourceOption(current)
  } catch (error) {
    showError(
      errorMessage(
        error,
        t('llmOps.priceSourceModal.errors.loadAutoSyncSources')
      )
    )
  } finally {
    loadingAutoSyncSourceOptions.value = false
  }
}

function applyAutoSyncSourceOption(option) {
  form.value = {
    ...form.value,
    source_category: option.source_category || 'supplier',
    source_owner_type: option.source_owner_type || 'supplier',
    collection_method: option.collection_method || 'unknown',
    name: option.source_name || option.provider_name || form.value.name,
    slug: option.source_slug || form.value.slug,
    currency: option.currency || form.value.currency,
    endpoint_url: option.source_url || form.value.endpoint_url,
    updates_model_prices: true
  }
}

function autoSyncSourcePayload(option) {
  return {
    name: option.source_name,
    slug: option.source_slug,
    source_type: 'custom',
    source_category: option.source_category,
    source_owner_type: option.source_owner_type,
    collection_method: option.collection_method || 'unknown',
    endpoint_url: option.source_url || '',
    currency: option.currency || 'CNY',
    is_enabled: true,
    updates_model_prices: true,
    notes: form.value.notes || ''
  }
}

function sourceOptionKey(option) {
  return String(
    option?.source_slug ||
      option?.option_code ||
      option?.provider_code ||
      option?.source_name ||
      ''
  )
}

function isStableOfficialOption(option) {
  const ownerType =
    option?.source_owner_type ||
    sourceOwnerTypeFromLegacyCategory(option?.source_category)
  if (
    !['model_provider_official', 'cloud_provider_official'].includes(ownerType)
  ) {
    return false
  }
  const providerCode = String(option.provider_code || '').trim()
  return Boolean(
    providerCode &&
      String(option.source_slug || '') === `${providerCode}-official`
  )
}

function sourceOwnerTypeFromLegacyCategory(value) {
  if (value === 'official_provider') return 'model_provider_official'
  if (value === 'supplier') return 'supplier'
  if (value === 'manual') return 'internal'
  return 'unknown'
}

function errorMessage(error, fallback) {
  return userFacingApiError(error, fallback)
}

function normalizeSlugField() {
  if (!canEditSlug.value) return
  form.value.slug = normalizeSlug(form.value.slug)
}

function autoSlug(value) {
  return normalizeSlug(value) || 'price-source'
}

function normalizeSlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
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
  @apply h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500;
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
