<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Eye, FolderOpen, FileText, RefreshCw, Trash2 } from 'lucide-vue-next'
import {
  grantViewPermission,
  revokeViewPermission,
  type ViewPermissionDocument,
  type ViewPermissionFolder,
  type ViewPermissionContext,
} from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import {
  useQuotationViewPermissionAccess,
} from '../composables/useQuotationViewPermissionAccess'
import FormSelect, { type FormSelectOption } from './FormSelect.vue'

const { t } = useQuotationI18n()

const context = ref<ViewPermissionContext>({
  users: [],
  folders: [],
  documents: [],
  permissions: [],
})
const viewPermissionAccess = useQuotationViewPermissionAccess()
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const selectedUserId = ref('')
const targetType = ref<'folder' | 'document'>('folder')
const targetId = ref('')

const userOptions = computed<FormSelectOption[]>(() =>
  context.value.users.map((user) => ({
    value: String(user.id),
    label: `${user.name} (${user.username})`,
  })),
)
const targetTypeOptions = computed<FormSelectOption[]>(() => [
  { value: 'folder', label: t('quotation.pages.permissions.folder') },
  { value: 'document', label: t('quotation.pages.permissions.document') },
])
const targetOptions = computed<FormSelectOption[]>(() => {
  if (targetType.value === 'folder') {
    return context.value.folders.map((target) => ({
      value: target.token,
      label: targetLabel(target),
    }))
  }
  return context.value.documents.map((target) => ({
    value: target.id,
    label: targetLabel(target),
  }))
})

function syncSharedContext() {
  if (viewPermissionAccess.context.value) {
    context.value = viewPermissionAccess.context.value
  }
}

async function load(force = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const allowed = await viewPermissionAccess.ensure(force)
    if (!allowed) {
      throw new Error(t('quotation.pages.permissions.loadFailed'))
    }
    syncSharedContext()
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t('quotation.pages.permissions.loadFailed')
  } finally {
    loading.value = false
  }
}

async function grant() {
  if (!selectedUserId.value || !targetId.value) {
    error.value = t('quotation.pages.permissions.selectRequired')
    return
  }
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await grantViewPermission({
      user_id: Number(selectedUserId.value),
      target_type: targetType.value,
      target_id: targetId.value,
    })
    message.value = t('quotation.pages.permissions.grantSuccess')
    targetId.value = ''
    await load(true)
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t('quotation.pages.permissions.grantFailed')
  } finally {
    saving.value = false
  }
}

async function revoke(id: number) {
  if (!window.confirm(t('quotation.pages.permissions.revokeConfirm'))) return
  error.value = ''
  try {
    await revokeViewPermission(id)
    message.value = t('quotation.pages.permissions.revokeSuccess')
    await load(true)
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t('quotation.pages.permissions.revokeFailed')
  }
}

function targetLabel(
  target: ViewPermissionFolder | ViewPermissionDocument,
) {
  return 'file_name' in target ? target.file_name : target.name
}

onMounted(() => {
  syncSharedContext()
  if (!viewPermissionAccess.context.value) {
    void load()
  }
})
</script>

<template>
  <section class="min-w-0 max-w-full space-y-4 text-dm-text">
    <div>
      <div class="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div class="flex items-center gap-2">
            <Eye class="h-5 w-5 text-dm-primary" />
            <h2 class="text-xl font-semibold text-dm-text">{{ t('quotation.pages.permissions.title') }}</h2>
          </div>
          <p class="mt-1 text-sm text-dm-text-secondary">
            {{ t('quotation.pages.permissions.subtitle') }}
          </p>
        </div>
        <button
          type="button"
          class="dm-btn-default px-3 py-2 text-sm"
          :disabled="loading"
          :aria-busy="loading"
          @click="load(true)"
        >
          <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
          {{ loading ? t('quotation.common.refreshing') : t('quotation.common.refresh') }}
        </button>
      </div>

      <p v-if="error" class="mt-4 rounded-dm bg-red-50 px-4 py-3 text-sm text-red-700">
        {{ error }}
      </p>
      <p v-if="message" class="mt-4 rounded-dm bg-green-50 px-4 py-3 text-sm text-green-700">
        {{ message }}
      </p>

      <div class="dm-card p-4">
        <h3 class="font-semibold">{{ t('quotation.pages.permissions.addTitle') }}</h3>
        <div class="mt-4 grid gap-4 md:grid-cols-[1.2fr_0.8fr_1.4fr_auto] md:items-end">
          <label class="text-sm">
            <span class="mb-1.5 block text-dm-text-secondary">{{ t('quotation.pages.permissions.userLabel') }}</span>
            <FormSelect
              v-model="selectedUserId"
              :options="userOptions"
              :placeholder="t('quotation.pages.permissions.selectUser')"
            />
          </label>
          <label class="text-sm">
            <span class="mb-1.5 block text-dm-text-secondary">{{ t('quotation.pages.permissions.scopeLabel') }}</span>
            <FormSelect v-model="targetType" :options="targetTypeOptions" />
          </label>
          <label class="text-sm">
            <span class="mb-1.5 block text-dm-text-secondary">{{ t('quotation.pages.permissions.targetLabel') }}</span>
            <FormSelect
              v-model="targetId"
              :options="targetOptions"
              :placeholder="t('quotation.pages.permissions.selectTarget')"
            />
          </label>
          <button
            type="button"
            class="dm-btn-primary h-10 px-4 text-sm disabled:opacity-50"
            :disabled="saving || loading"
            @click="grant"
          >
            <Eye class="h-4 w-4" />
            {{ t('quotation.pages.permissions.grant') }}
          </button>
        </div>
      </div>

      <div class="dm-card mt-6 overflow-hidden">
        <div class="border-b border-dm-border-light bg-[#fafafa] px-4 py-3 font-semibold">{{ t('quotation.pages.permissions.currentTitle') }}</div>
        <div v-if="loading" class="px-4 py-8 text-center text-sm text-dm-text-secondary">{{ t('quotation.common.loading') }}</div>
        <div v-else-if="context.permissions.length === 0" class="px-4 py-8 text-center text-sm text-dm-text-secondary">
          {{ t('quotation.pages.permissions.empty') }}
        </div>
        <table v-else class="dm-table">
          <thead class="bg-dm-surface text-dm-text-secondary">
            <tr>
              <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.scopeColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.targetColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.grantedByColumn') }}</th>
              <th class="text-right">{{ t('quotation.pages.permissions.actionsColumn') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="permission in context.permissions" :key="permission.id">
              <td>{{ permission.user_name }}</td>
              <td>
                <span class="inline-flex items-center gap-1">
                  <FolderOpen v-if="permission.target_type === 'folder'" class="h-4 w-4" />
                  <FileText v-else class="h-4 w-4" />
                  {{ permission.target_type === 'folder' ? t('quotation.pages.permissions.folder') : t('quotation.pages.permissions.document') }}
                </span>
              </td>
              <td>{{ permission.target_name || permission.target_id }}</td>
              <td class="text-dm-text-secondary">{{ permission.granted_by }}</td>
              <td class="text-right">
                <button type="button" class="inline-flex items-center gap-1 text-red-600 hover:text-red-800" @click="revoke(permission.id)">
                  <Trash2 class="h-4 w-4" />
                  {{ t('quotation.pages.permissions.revoke') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
