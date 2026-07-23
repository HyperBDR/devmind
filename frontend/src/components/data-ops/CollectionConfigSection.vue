<template>
  <section class="space-y-5">
    <Panel :title="t('dataOps.config.collectionTitle')">
      <div class="mb-4 flex justify-end">
        <button
          class="btn-secondary min-h-11 text-xs"
          type="button"
          :aria-expanded="showTechnicalIdentifiers"
          @click="showTechnicalIdentifiers = !showTechnicalIdentifiers"
        >
          {{
            showTechnicalIdentifiers
              ? t('dataOps.config.hideTechnicalIds')
              : t('dataOps.config.showTechnicalIds')
          }}
        </button>
      </div>

      <div class="space-y-3 md:hidden">
        <article
          v-for="config in configs"
          :key="config.id"
          class="rounded-lg border border-slate-200 p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="font-semibold text-slate-900">
                {{ config.source_name || config.source_key }}
              </p>
              <a
                v-if="config.table_url"
                :href="config.table_url"
                class="mt-1 block truncate text-sm font-semibold text-indigo-700"
                rel="noopener noreferrer"
                target="_blank"
              >
                {{ config.table_name }}
              </a>
              <p v-else class="mt-1 text-sm text-slate-600">
                {{ config.table_name }}
              </p>
            </div>
            <span
              class="status-pill shrink-0"
              :class="
                config.is_enabled
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-slate-100 text-slate-500'
              "
            >
              {{
                config.is_enabled
                  ? t('dataOps.common.enabled')
                  : t('dataOps.common.disabled')
              }}
            </span>
          </div>
          <dl class="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt class="text-slate-500">
                {{ t('dataOps.config.frequency') }}
              </dt>
              <dd class="mt-1 font-semibold text-slate-800">
                {{ frequencyLabel(config.sync_frequency) }}
              </dd>
            </div>
            <div>
              <dt class="text-slate-500">{{ t('dataOps.config.status') }}</dt>
              <dd class="mt-1 font-semibold text-slate-800">
                {{ syncStatusLabel(config.sync_status) }}
              </dd>
            </div>
          </dl>
          <dl
            v-if="showTechnicalIdentifiers"
            class="mt-3 space-y-2 rounded-lg bg-slate-50 p-3 text-xs"
          >
            <div>
              <dt class="text-slate-500">App Token</dt>
              <dd class="mt-1 break-all font-mono text-slate-700">
                {{ config.app_token || '—' }}
              </dd>
            </div>
            <div>
              <dt class="text-slate-500">Table ID</dt>
              <dd class="mt-1 break-all font-mono text-slate-700">
                {{ config.table_id || '—' }}
              </dd>
            </div>
          </dl>
          <p v-if="config.message" class="mt-3 text-xs text-rose-700">
            {{ config.message }}
          </p>
          <div class="mt-4 grid grid-cols-2 gap-2">
            <button
              class="btn-secondary min-h-11 text-xs"
              type="button"
              @click="$emit('preflight', config)"
            >
              {{ t('dataOps.config.check') }}
            </button>
            <button
              class="btn-secondary min-h-11 text-xs"
              type="button"
              @click="$emit('trigger', config)"
            >
              {{ t('dataOps.config.sync') }}
            </button>
          </div>
        </article>
        <p
          v-if="!configs.length"
          class="rounded-lg border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500"
        >
          {{ t('dataOps.config.empty') }}
        </p>
      </div>

      <div class="hidden overflow-x-auto md:block">
        <table class="w-full min-w-[820px] divide-y divide-slate-200 text-xs">
          <thead class="bg-slate-50 text-left text-slate-500">
            <tr>
              <th class="px-3 py-3">{{ t('dataOps.config.enabled') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.config.source') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.config.table') }}</th>
              <th v-if="showTechnicalIdentifiers" class="px-3 py-3">
                App Token
              </th>
              <th v-if="showTechnicalIdentifiers" class="px-3 py-3">
                Table ID
              </th>
              <th class="px-3 py-3">{{ t('dataOps.config.frequency') }}</th>
              <th class="px-3 py-3">{{ t('dataOps.config.status') }}</th>
              <th class="px-3 py-3 text-right">
                {{ t('dataOps.config.actions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 bg-white">
            <tr v-for="config in configs" :key="config.id">
              <td class="px-3 py-3">
                <span
                  class="status-pill"
                  :class="
                    config.is_enabled
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-slate-100 text-slate-500'
                  "
                >
                  {{
                    config.is_enabled
                      ? t('dataOps.common.enabled')
                      : t('dataOps.common.disabled')
                  }}
                </span>
              </td>
              <td class="px-3 py-3">
                <p class="font-semibold">{{ config.source_key }}</p>
                <p class="mt-1 text-slate-500">{{ config.source_name }}</p>
              </td>
              <td class="max-w-56 px-3 py-3">
                <a
                  v-if="config.table_url"
                  :href="config.table_url"
                  class="font-semibold text-indigo-700 hover:underline"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {{ config.table_name }}
                </a>
                <p v-else class="font-semibold">{{ config.table_name }}</p>
                <p class="mt-1 text-slate-500">{{ config.table_key }}</p>
              </td>
              <td v-if="showTechnicalIdentifiers" class="px-3 py-3">
                <code class="break-all text-[11px] text-slate-600">
                  {{ config.app_token }}
                </code>
              </td>
              <td v-if="showTechnicalIdentifiers" class="px-3 py-3">
                <code class="text-[11px] text-slate-600">
                  {{ config.table_id }}
                </code>
              </td>
              <td class="px-3 py-3">
                <p class="whitespace-nowrap text-slate-700">
                  {{ frequencyLabel(config.sync_frequency) }}
                </p>
              </td>
              <td class="px-3 py-3">
                <span
                  class="status-pill"
                  :class="statusPillClass(config.sync_status)"
                >
                  {{ syncStatusLabel(config.sync_status) }}
                </span>
                <p v-if="config.message" class="mt-2 max-w-56 text-rose-700">
                  {{ config.message }}
                </p>
                <p
                  v-if="config.resolution_hint"
                  class="mt-1 max-w-56 text-slate-500"
                >
                  {{ config.resolution_hint }}
                </p>
              </td>
              <td class="px-3 py-3 text-right">
                <div class="flex justify-end gap-2">
                  <button
                    class="btn-secondary min-h-11 text-xs"
                    type="button"
                    @click="$emit('preflight', config)"
                  >
                    {{ t('dataOps.config.check') }}
                  </button>
                  <button
                    class="btn-secondary min-h-11 text-xs"
                    type="button"
                    @click="$emit('trigger', config)"
                  >
                    {{ t('dataOps.config.sync') }}
                  </button>
                  <a
                    v-if="config.table_url"
                    :aria-label="
                      t('dataOps.config.openTableLabel', {
                        name: config.table_name
                      })
                    "
                    :href="config.table_url"
                    class="btn-secondary min-h-11 whitespace-nowrap text-xs"
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {{ t('dataOps.config.openTable') }}
                  </a>
                </div>
              </td>
            </tr>
            <tr v-if="!configs.length">
              <td
                class="px-4 py-10 text-center text-slate-500"
                :colspan="showTechnicalIdentifiers ? 8 : 6"
              >
                {{ t('dataOps.config.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { statusPillClass } from '@/composables/useDataOpsConsole'

import { Panel } from './DataOpsPrimitives'

const { t } = useI18n()
const showTechnicalIdentifiers = ref(false)

const props = defineProps({
  configs: { type: Array, default: () => [] },
  frequencyOptions: { type: Array, required: true }
})

defineEmits(['preflight', 'trigger'])

function frequencyLabel(value) {
  return (
    props.frequencyOptions.find((option) => option.value === value)?.label ||
    value ||
    t('dataOps.common.notSet')
  )
}

function syncStatusLabel(value) {
  const status = value || 'pending'
  const key = ['ok', 'warning', 'failed', 'pending', 'running'].includes(status)
    ? status
    : 'unknown'
  return t(`dataOps.config.syncStatuses.${key}`)
}
</script>
