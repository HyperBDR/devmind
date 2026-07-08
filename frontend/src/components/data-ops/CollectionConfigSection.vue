<template>
  <section class="space-y-5">
    <Panel title="飞书多维表格采集配置">
      <div class="overflow-x-auto">
        <table class="min-w-[1280px] divide-y divide-slate-200 text-xs">
          <thead class="bg-slate-50 text-left text-slate-500">
            <tr>
              <th class="px-3 py-3">启用</th>
              <th class="px-3 py-3">数据源</th>
              <th class="px-3 py-3">表</th>
              <th class="px-3 py-3">App Token</th>
              <th class="px-3 py-3">Table ID</th>
              <th class="px-3 py-3">频率</th>
              <th class="px-3 py-3">最低记录</th>
              <th class="px-3 py-3">权限</th>
              <th class="px-3 py-3">状态</th>
              <th class="px-3 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 bg-white">
            <tr v-for="config in configs" :key="config.id">
              <td class="px-3 py-3">
                <input
                  :checked="config.is_enabled"
                  type="checkbox"
                  @change="
                    $emit(
                      'update-config-field',
                      config,
                      'is_enabled',
                      $event.target.checked
                    )
                  "
                />
              </td>
              <td class="px-3 py-3">
                <p class="font-semibold">{{ config.source_key }}</p>
                <p class="mt-1 text-slate-500">{{ config.source_name }}</p>
              </td>
              <td class="px-3 py-3">
                <input
                  :value="config.table_name"
                  class="field-sm w-52"
                  @input="
                    $emit(
                      'update-config-field',
                      config,
                      'table_name',
                      $event.target.value
                    )
                  "
                />
                <p class="mt-1 text-slate-500">{{ config.table_key }}</p>
              </td>
              <td class="px-3 py-3">
                <input
                  :value="config.app_token"
                  class="field-sm w-56 font-mono"
                  @input="
                    $emit(
                      'update-config-field',
                      config,
                      'app_token',
                      $event.target.value
                    )
                  "
                />
              </td>
              <td class="px-3 py-3">
                <input
                  :value="config.table_id"
                  class="field-sm w-48 font-mono"
                  @input="
                    $emit(
                      'update-config-field',
                      config,
                      'table_id',
                      $event.target.value
                    )
                  "
                />
              </td>
              <td class="px-3 py-3">
                <select
                  :value="config.sync_frequency"
                  class="field-sm w-28"
                  @change="
                    $emit(
                      'update-config-field',
                      config,
                      'sync_frequency',
                      $event.target.value
                    )
                  "
                >
                  <option
                    v-for="option in frequencyOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </td>
              <td class="px-3 py-3">
                <input
                  :value="config.expected_min_records"
                  class="field-sm w-24"
                  min="0"
                  type="number"
                  @input="
                    $emit(
                      'update-config-field',
                      config,
                      'expected_min_records',
                      Number($event.target.value || 0)
                    )
                  "
                />
              </td>
              <td class="px-3 py-3">
                <textarea
                  :value="permissionsText(config)"
                  class="field-sm h-20 w-48 font-mono"
                  @input="$emit('update-permissions', config, $event)"
                />
              </td>
              <td class="px-3 py-3">
                <span
                  class="status-pill"
                  :class="statusPillClass(config.sync_status)"
                >
                  {{ config.sync_status || 'pending' }}
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
                    class="btn-secondary h-8 text-xs"
                    type="button"
                    @click="$emit('preflight', config)"
                  >
                    检查
                  </button>
                  <button
                    class="btn-secondary h-8 text-xs"
                    type="button"
                    @click="$emit('trigger', config)"
                  >
                    同步
                  </button>
                  <button
                    class="btn-primary h-8 text-xs"
                    type="button"
                    @click="$emit('save', config)"
                  >
                    保存
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!configs.length">
              <td class="px-4 py-10 text-center text-slate-500" colspan="10">
                暂无采集配置
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  </section>
</template>

<script setup>
import { statusPillClass } from '@/composables/useDataOpsConsole'

import { Panel } from './DataOpsPrimitives'

defineProps({
  configs: { type: Array, default: () => [] },
  frequencyOptions: { type: Array, required: true },
  permissionsText: { type: Function, required: true },
})

defineEmits([
  'preflight',
  'save',
  'trigger',
  'update-config-field',
  'update-permissions',
])
</script>
