<template>
  <Panel :title="t('dataOps.config.globalTitle')">
    <div class="grid gap-4 lg:grid-cols-4">
      <label class="space-y-1">
        <span class="text-xs font-semibold text-slate-500">App ID</span>
        <input
          :value="config.feishu_app_id"
          class="field-sm w-full font-mono"
          @input="$emit('update-field', 'feishu_app_id', $event.target.value)"
        />
      </label>

      <label class="space-y-1">
        <span class="text-xs font-semibold text-slate-500">
          App Secret
          <span
            v-if="config.has_feishu_app_secret"
            class="ml-1 text-emerald-600"
          >
            {{ t('dataOps.config.configured') }}
          </span>
        </span>
        <input
          :value="config.feishu_app_secret"
          autocomplete="new-password"
          class="field-sm w-full font-mono"
          :placeholder="t('dataOps.config.secretPlaceholder')"
          type="password"
          @input="
            $emit('update-field', 'feishu_app_secret', $event.target.value)
          "
        />
      </label>

      <label class="space-y-1">
        <span class="text-xs font-semibold text-slate-500">
          {{ t('dataOps.config.timezone') }}
        </span>
        <input
          :value="config.feishu_date_timezone"
          class="field-sm w-full font-mono"
          @input="
            $emit('update-field', 'feishu_date_timezone', $event.target.value)
          "
        />
      </label>

      <label class="space-y-1">
        <span class="text-xs font-semibold text-slate-500">
          {{ t('dataOps.config.timeout') }}
        </span>
        <input
          :value="config.active_sync_job_timeout_hours"
          class="field-sm w-full"
          min="1"
          type="number"
          @input="
            $emit(
              'update-field',
              'active_sync_job_timeout_hours',
              Number($event.target.value || 3)
            )
          "
        />
      </label>
    </div>

    <div class="mt-4 flex justify-end">
      <button
        class="btn-primary min-h-11 text-sm"
        type="button"
        @click="$emit('save')"
      >
        {{ t('dataOps.config.save') }}
      </button>
    </div>
  </Panel>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { Panel } from './DataOpsPrimitives'

const { t } = useI18n()

defineProps({
  config: { type: Object, required: true }
})

defineEmits(['save', 'update-field'])
</script>
