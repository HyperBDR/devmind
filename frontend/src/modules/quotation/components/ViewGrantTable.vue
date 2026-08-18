<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { FileText, FolderOpen, Save, Trash2 } from 'lucide-vue-next'

import type { ViewPermissionRecord } from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const props = defineProps<{
  permissions: ViewPermissionRecord[]
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  updateExpiry: [permissionId: number, expiresAt: string | null]
  revoke: [permissionId: number]
}>()

const { t } = useQuotationI18n()
const expiryDrafts = reactive<Record<number, string>>({})
const minimumExpiry = computed(() => toLocalInput(new Date().toISOString()))

watch(
  () => props.permissions,
  (permissions) => {
    for (const permission of permissions) {
      expiryDrafts[permission.id] = toLocalInput(permission.expires_at)
    }
  },
  { immediate: true }
)

function toLocalInput(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function saveExpiry(permissionId: number) {
  const value = expiryDrafts[permissionId]
  emit(
    'updateExpiry',
    permissionId,
    value ? new Date(value).toISOString() : null
  )
}

function revoke(permissionId: number) {
  if (!window.confirm(t('quotation.pages.permissions.revokeConfirm'))) return
  emit('revoke', permissionId)
}

function formatExpiry(value: string | null) {
  if (!value) return t('quotation.pages.permissions.neverExpires')
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value))
}
</script>

<template>
  <div class="dm-card overflow-hidden">
    <div
      :class="[
        'border-b border-dm-border-light bg-dm-surface',
        'px-4 py-3 font-semibold'
      ]"
    >
      {{ t('quotation.pages.permissions.currentTitle') }}
    </div>
    <div
      v-if="loading"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.common.loading') }}
    </div>
    <div
      v-else-if="permissions.length === 0"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.pages.permissions.empty') }}
    </div>
    <div v-else class="overflow-x-auto">
      <table class="dm-table min-w-[980px]">
        <thead class="bg-dm-surface text-dm-text-secondary">
          <tr>
            <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.scopeColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.targetColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.expiryLabel') }}</th>
            <th>{{ t('quotation.pages.permissions.grantedByColumn') }}</th>
            <th class="text-right">
              {{ t('quotation.pages.permissions.actionsColumn') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="permission in permissions" :key="permission.id">
            <td>{{ permission.user_name }}</td>
            <td>
              <span class="inline-flex items-center gap-1">
                <FolderOpen
                  v-if="permission.target_type === 'folder'"
                  class="h-4 w-4"
                />
                <FileText v-else class="h-4 w-4" />
                {{
                  permission.target_type === 'folder'
                    ? t('quotation.pages.permissions.folder')
                    : t('quotation.pages.permissions.document')
                }}
              </span>
            </td>
            <td>{{ permission.target_name || permission.target_id }}</td>
            <td>
              <div class="flex min-w-64 items-center gap-2">
                <input
                  v-model="expiryDrafts[permission.id]"
                  type="datetime-local"
                  :min="minimumExpiry"
                  class="dm-input h-9 min-w-48"
                />
                <button
                  type="button"
                  class="dm-btn-default h-9 px-2"
                  :aria-label="t('quotation.pages.permissions.saveExpiry')"
                  :disabled="saving"
                  @click="saveExpiry(permission.id)"
                >
                  <Save class="h-4 w-4" />
                </button>
              </div>
              <div class="mt-1 flex items-center gap-2 text-xs">
                <span
                  :class="
                    permission.status === 'expired'
                      ? 'text-red-700'
                      : 'text-dm-text-secondary'
                  "
                >
                  {{
                    permission.status === 'expired'
                      ? t('quotation.pages.permissions.expired')
                      : formatExpiry(permission.expires_at)
                  }}
                </span>
              </div>
            </td>
            <td class="text-dm-text-secondary">
              {{ permission.granted_by }}
            </td>
            <td class="text-right">
              <button
                type="button"
                :class="[
                  'inline-flex items-center gap-1 text-red-600',
                  'hover:text-red-800'
                ]"
                @click="revoke(permission.id)"
              >
                <Trash2 class="h-4 w-4" />
                {{ t('quotation.pages.permissions.revoke') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
