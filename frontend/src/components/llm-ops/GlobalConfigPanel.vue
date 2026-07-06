<template>
  <section class="global-config-panel">
    <div class="global-config-toolbar">
      <div>
        <p class="global-config-eyebrow">Global Config</p>
        <h3>{{ t('llmOps.globalConfigPanel.title') }}</h3>
        <p>{{ t('llmOps.globalConfigPanel.description') }}</p>
      </div>
      <div class="global-config-actions">
        <button
          type="button"
          class="btn-secondary btn-action-refresh"
          :disabled="loading || saving"
          @click="loadConfig"
        >
          {{ t('llmOps.globalConfigPanel.actions.reload') }}
        </button>
        <button
          type="button"
          class="btn-secondary btn-action-cancel"
          :disabled="loading || saving"
          @click="resetConfig"
        >
          {{ t('llmOps.globalConfigPanel.actions.reset') }}
        </button>
        <button
          type="button"
          class="btn-primary btn-action-save"
          :disabled="loading || saving"
          @click="saveConfig"
        >
          {{
            saving
              ? t('llmOps.globalConfigPanel.actions.saving')
              : t('llmOps.globalConfigPanel.actions.save')
          }}
        </button>
      </div>
    </div>

    <BaseLoading v-if="loading" />

    <form v-else class="global-config-grid" @submit.prevent="saveConfig">
      <div class="global-config-main">
        <section class="config-section">
          <div class="config-section-header">
            <div>
              <h4>{{ t('llmOps.globalConfigPanel.metaSync.title') }}</h4>
              <p>{{ t('llmOps.globalConfigPanel.metaSync.description') }}</p>
            </div>
            <label class="config-switch">
              <span>{{
                form.meta_model_sync_enabled
                  ? t('llmOps.globalConfigPanel.status.enabled')
                  : t('llmOps.globalConfigPanel.status.disabled')
              }}</span>
              <input v-model="form.meta_model_sync_enabled" type="checkbox" />
            </label>
          </div>

          <label class="config-field">
            <span>{{ t('llmOps.globalConfigPanel.fields.sourceUrl') }}</span>
            <input
              v-model.trim="form.meta_model_sync_source_url"
              type="url"
              required
              placeholder="https://models.dev/api.json"
            />
          </label>
          <label class="config-field">
            <span>{{ t('llmOps.globalConfigPanel.fields.cron') }}</span>
            <input
              v-model.trim="form.meta_model_sync_cron"
              type="text"
              required
              placeholder="35 2 * * *"
            />
          </label>
        </section>

        <section class="config-section">
          <div class="config-section-header">
            <div>
              <h4>{{ t('llmOps.globalConfigPanel.priceCollection.title') }}</h4>
              <p>
                {{ t('llmOps.globalConfigPanel.priceCollection.description') }}
              </p>
            </div>
            <label class="config-switch">
              <span>{{
                form.price_collection_enabled
                  ? t('llmOps.globalConfigPanel.status.enabled')
                  : t('llmOps.globalConfigPanel.status.disabled')
              }}</span>
              <input v-model="form.price_collection_enabled" type="checkbox" />
            </label>
          </div>

          <label class="config-field">
            <span>{{ t('llmOps.globalConfigPanel.fields.cron') }}</span>
            <input
              v-model.trim="form.price_collection_cron"
              type="text"
              required
              placeholder="15 1,7,13,19 * * *"
            />
          </label>
          <label class="config-field">
            <span>{{ t('llmOps.globalConfigPanel.fields.llmConfig') }}</span>
            <select
              v-model="form.price_sync_llm_config_uuid"
              :disabled="llmConfigLoading"
            >
              <option value="">
                {{ t('llmOps.globalConfigPanel.llmConfig.default') }}
              </option>
              <option
                v-for="option in llmConfigOptions"
                :key="option.uuid"
                :value="option.uuid"
              >
                {{ option.label }}
              </option>
            </select>
            <small>
              {{ t('llmOps.globalConfigPanel.llmConfig.description') }}
            </small>
          </label>

          <div class="source-mode-group" role="radiogroup">
            <label
              v-for="mode in sourceModes"
              :key="mode.value"
              class="source-mode"
              :class="{ active: sourceMode === mode.value }"
            >
              <input
                v-model="sourceMode"
                type="radio"
                name="price_source_mode"
                :value="mode.value"
              />
              <span>{{ mode.label }}</span>
            </label>
          </div>

          <div v-if="sourceMode === 'selected'" class="source-list">
            <label
              v-for="source in priceSourceOptions"
              :key="source.id"
              class="source-row"
            >
              <input
                v-model="form.price_collection_source_ids"
                type="checkbox"
                :value="source.id"
              />
              <span>
                <strong>{{ source.name }}</strong>
                <small>{{ sourceMeta(source) }}</small>
              </span>
            </label>
            <div v-if="!priceSourceOptions.length" class="empty-source">
              {{ t('llmOps.globalConfigPanel.empty.noPriceSources') }}
            </div>
          </div>
        </section>
      </div>

      <aside class="global-config-side">
        <section class="config-section">
          <div class="config-section-header">
            <div>
              <h4>{{ t('llmOps.globalConfigPanel.feishu.title') }}</h4>
              <p>{{ t('llmOps.globalConfigPanel.feishu.description') }}</p>
            </div>
            <span
              class="secret-status"
              :class="{ active: config?.feishu_app_secret_configured }"
            >
              {{
                config?.feishu_app_secret_configured
                  ? t('llmOps.globalConfigPanel.feishu.secretConfigured')
                  : t('llmOps.globalConfigPanel.feishu.secretMissing')
              }}
            </span>
          </div>

          <label class="config-field">
            <span>App ID</span>
            <input
              v-model.trim="form.feishu_app_id"
              type="text"
              autocomplete="off"
            />
          </label>
          <label class="config-field">
            <span>App Secret</span>
            <input
              v-model.trim="form.feishu_app_secret"
              type="password"
              autocomplete="new-password"
              :placeholder="
                config?.feishu_app_secret_configured
                  ? t('llmOps.globalConfigPanel.feishu.secretPlaceholder')
                  : ''
              "
            />
          </label>
          <label class="config-field">
            <span>{{ t('llmOps.globalConfigPanel.fields.approvalCode') }}</span>
            <input
              v-model.trim="form.feishu_approval_code"
              type="text"
              autocomplete="off"
            />
          </label>
          <label class="config-field">
            <span>Tenant Key</span>
            <input
              v-model.trim="form.feishu_tenant_key"
              type="text"
              autocomplete="off"
            />
          </label>
        </section>

        <section class="config-section">
          <div class="config-section-header">
            <div>
              <h4>{{ t('llmOps.globalConfigPanel.notes.title') }}</h4>
              <p>{{ t('llmOps.globalConfigPanel.notes.description') }}</p>
            </div>
          </div>
          <textarea v-model.trim="form.notes" rows="5" />
          <div class="config-runtime">
            <span>{{ t('llmOps.globalConfigPanel.fields.updatedAt') }}</span>
            <strong>{{ formatDateTime(config?.updated_at) }}</strong>
          </div>
        </section>
      </aside>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseLoading from '@/components/ui/BaseLoading.vue'
import { llmAdminApi } from '@/admin/api'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import { priceSourceCollectionMethod } from '@/utils/llmOpsPriceSources'

const props = defineProps({
  sources: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const config = ref(null)
const llmConfigLoading = ref(false)
const llmConfigs = ref([])
const sourceMode = ref('all')

const form = reactive({
  meta_model_sync_enabled: true,
  meta_model_sync_source_url: 'https://models.dev/api.json',
  meta_model_sync_cron: '35 2 * * *',
  price_collection_enabled: true,
  price_collection_source_ids: [],
  price_collection_cron: '15 1,7,13,19 * * *',
  price_sync_llm_config_uuid: '',
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_approval_code: '',
  feishu_tenant_key: '',
  notes: ''
})

const sourceModes = computed(() => [
  {
    label: t('llmOps.globalConfigPanel.sourceModes.all'),
    value: 'all'
  },
  {
    label: t('llmOps.globalConfigPanel.sourceModes.selected'),
    value: 'selected'
  }
])

const priceSourceOptions = computed(() =>
  props.sources.filter((source) => sourceSupportsRuntimePriceSync(source))
)

const llmConfigOptions = computed(() => {
  const options = new Map()
  for (const row of llmConfigs.value) {
    const option = normalizeLLMConfigOption(row)
    if (option.uuid) options.set(option.uuid, option)
  }
  const selected = config.value?.price_sync_llm_config
  if (selected?.uuid && !options.has(selected.uuid)) {
    options.set(selected.uuid, selected)
  }
  return Array.from(options.values())
})

onMounted(() => {
  loadConfig()
  loadLLMConfigs()
})

async function loadConfig() {
  loading.value = true
  try {
    const response = await llmOpsApi.getGlobalConfig()
    applyConfig(extract(response))
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.globalConfigPanel.errors.loadFailed'))
    )
  } finally {
    loading.value = false
  }
}

async function loadLLMConfigs() {
  llmConfigLoading.value = true
  try {
    const response = await llmAdminApi.getLLMConfig()
    const payload = extract(response)
    llmConfigs.value = Array.isArray(payload) ? payload : []
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.globalConfigPanel.errors.llmConfigLoad'))
    )
  } finally {
    llmConfigLoading.value = false
  }
}

async function saveConfig() {
  const missingSelectedSource =
    sourceMode.value === 'selected' && !form.price_collection_source_ids.length
  if (missingSelectedSource) {
    showError(t('llmOps.globalConfigPanel.errors.sourceRequired'))
    return
  }
  saving.value = true
  try {
    const payload = {
      meta_model_sync_enabled: form.meta_model_sync_enabled,
      meta_model_sync_source_url: form.meta_model_sync_source_url,
      meta_model_sync_cron: form.meta_model_sync_cron,
      price_collection_enabled: form.price_collection_enabled,
      price_collection_source_ids:
        sourceMode.value === 'all' ? [] : form.price_collection_source_ids,
      price_collection_cron: form.price_collection_cron,
      price_sync_llm_config_uuid: form.price_sync_llm_config_uuid || null,
      feishu_app_id: form.feishu_app_id,
      feishu_approval_code: form.feishu_approval_code,
      feishu_tenant_key: form.feishu_tenant_key,
      notes: form.notes
    }
    if (form.feishu_app_secret) {
      payload.feishu_app_secret = form.feishu_app_secret
    }
    const response = await llmOpsApi.updateGlobalConfig(payload)
    applyConfig(extract(response))
    showSuccess(t('llmOps.globalConfigPanel.messages.saved'))
    emit('saved')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.globalConfigPanel.errors.saveFailed'))
    )
  } finally {
    saving.value = false
  }
}

async function resetConfig() {
  if (!window.confirm(t('llmOps.globalConfigPanel.confirm.reset'))) return
  saving.value = true
  try {
    const response = await llmOpsApi.resetGlobalConfig()
    applyConfig(extract(response))
    showSuccess(t('llmOps.globalConfigPanel.messages.reset'))
    emit('saved')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.globalConfigPanel.errors.resetFailed'))
    )
  } finally {
    saving.value = false
  }
}

function applyConfig(nextConfig) {
  config.value = nextConfig
  form.meta_model_sync_enabled = nextConfig.meta_model_sync_enabled
  form.meta_model_sync_source_url = nextConfig.meta_model_sync_source_url
  form.meta_model_sync_cron = nextConfig.meta_model_sync_cron
  form.price_collection_enabled = nextConfig.price_collection_enabled
  form.price_collection_source_ids = [
    ...(nextConfig.price_collection_source_ids || [])
  ]
  form.price_collection_cron = nextConfig.price_collection_cron
  form.price_sync_llm_config_uuid =
    nextConfig.price_sync_llm_config?.uuid ||
    nextConfig.price_sync_llm_config_uuid ||
    ''
  form.feishu_app_id = nextConfig.feishu_app_id || ''
  form.feishu_app_secret = ''
  form.feishu_approval_code = nextConfig.feishu_approval_code || ''
  form.feishu_tenant_key = nextConfig.feishu_tenant_key || ''
  form.notes = nextConfig.notes || ''
  sourceMode.value = form.price_collection_source_ids.length
    ? 'selected'
    : 'all'
}

function sourceSupportsRuntimePriceSync(source) {
  return (
    source.updates_model_prices &&
    source.can_collect_prices &&
    sourceCollectionMethod(source) === 'auto_collect'
  )
}

function sourceCollectionMethod(source) {
  return priceSourceCollectionMethod(source)
}

function normalizeLLMConfigOption(row) {
  const configPayload = row.config || {}
  const uuid = row.uuid || row.id || ''
  const model = configPayload.model || row.model || ''
  const provider = row.provider || ''
  const label = row.label || [model, provider].filter(Boolean).join(' · ')
  return {
    uuid: String(uuid),
    label: label || String(uuid)
  }
}

function sourceMeta(source) {
  return [
    source.is_enabled === false
      ? t('llmOps.globalConfigPanel.status.disabled')
      : t('llmOps.globalConfigPanel.status.enabled'),
    source.provider_name,
    source.channel_name,
    source.currency,
    source.endpoint_url
  ]
    .filter(Boolean)
    .join(' · ')
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function extract(response) {
  const payload = response?.data?.data ?? response?.data ?? response
  return payload?.results ?? payload
}

function errorMessage(error, fallback) {
  const data = error?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string') return data
  return error?.message || fallback
}
</script>

<style scoped>
.global-config-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.global-config-toolbar {
  align-items: flex-start;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 1rem;
}

.global-config-eyebrow {
  color: #059669;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.global-config-toolbar h3,
.config-section h4 {
  color: #0f172a;
  font-weight: 700;
  margin: 0;
}

.global-config-toolbar h3 {
  font-size: 1.125rem;
  margin-top: 0.25rem;
}

.global-config-toolbar p,
.config-section-header p {
  color: #64748b;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.global-config-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
}

.global-config-grid {
  align-items: start;
  display: grid;
  gap: 1rem;
  grid-template-columns: minmax(0, 1.45fr) minmax(20rem, 0.8fr);
}

.global-config-main,
.global-config-side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.config-section {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.config-section-header {
  align-items: flex-start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.config-switch {
  align-items: center;
  color: #334155;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.875rem;
  font-weight: 700;
  gap: 0.5rem;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.config-field span {
  color: #334155;
  font-size: 0.8125rem;
  font-weight: 700;
}

.config-field input,
.config-field select,
.config-section textarea {
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  color: #0f172a;
  font-size: 0.875rem;
  line-height: 1.5;
  outline: none;
  padding: 0.625rem 0.75rem;
  width: 100%;
}

.config-field input:focus,
.config-field select:focus,
.config-section textarea:focus {
  border-color: #059669;
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12);
}

.config-field small {
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.5;
}

.source-mode-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.source-mode {
  align-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  color: #475569;
  display: inline-flex;
  font-size: 0.875rem;
  font-weight: 700;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
}

.source-mode.active {
  background: #ecfdf5;
  border-color: #10b981;
  color: #047857;
}

.source-list {
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  display: grid;
  gap: 0;
  overflow: hidden;
}

.source-row {
  align-items: flex-start;
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
}

.source-row + .source-row {
  border-top: 1px solid #e2e8f0;
}

.source-row strong,
.source-row small {
  display: block;
}

.source-row strong {
  color: #0f172a;
  font-size: 0.875rem;
}

.source-row small {
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.5;
  margin-top: 0.2rem;
}

.empty-source {
  color: #64748b;
  font-size: 0.875rem;
  padding: 0.9rem;
}

.secret-status {
  background: #f1f5f9;
  border-radius: 999px;
  color: #64748b;
  flex: 0 0 auto;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.65rem;
}

.secret-status.active {
  background: #dcfce7;
  color: #15803d;
}

.config-runtime {
  align-items: center;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  display: flex;
  font-size: 0.8125rem;
  justify-content: space-between;
  padding-top: 0.75rem;
}

.config-runtime strong {
  color: #0f172a;
  font-weight: 700;
}

@media (max-width: 1024px) {
  .global-config-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .global-config-toolbar,
  .config-section-header {
    flex-direction: column;
  }

  .global-config-actions {
    justify-content: flex-start;
    width: 100%;
  }
}
</style>
