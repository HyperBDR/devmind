<template>
  <Panel title="全局飞书配置">
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
            已配置
          </span>
        </span>
        <input
          :value="config.feishu_app_secret"
          autocomplete="new-password"
          class="field-sm w-full font-mono"
          placeholder="留空保持不变"
          type="password"
          @input="
            $emit('update-field', 'feishu_app_secret', $event.target.value)
          "
        />
      </label>

      <label class="space-y-1">
        <span class="text-xs font-semibold text-slate-500">日期时区</span>
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
          任务超时(小时)
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
      <button class="btn-primary h-9 text-sm" type="button" @click="$emit('save')">
        保存全局配置
      </button>
    </div>
  </Panel>
</template>

<script setup>
import { Panel } from './DataOpsPrimitives'

defineProps({
  config: { type: Object, required: true },
})

defineEmits(['save', 'update-field'])
</script>
