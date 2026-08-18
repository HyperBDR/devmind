<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Eye } from 'lucide-vue-next'

import type {
  GrantViewPermissionPayload,
  ViewPermissionContext,
  ViewPermissionDocument,
  ViewPermissionFolder
} from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import FormSelect, { type FormSelectOption } from './FormSelect.vue'

const props = defineProps<{
  context: ViewPermissionContext
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  grant: [payload: GrantViewPermissionPayload]
  invalid: []
}>()

const { t } = useQuotationI18n()
const selectedUserId = ref('')
const targetType = ref<'folder' | 'document'>('folder')
const targetId = ref('')
const expiresAt = ref('')

const userOptions = computed<FormSelectOption[]>(() =>
  props.context.users.map((user) => ({
    value: String(user.id),
    label: `${user.name} (${user.username})`
  }))
)
const targetTypeOptions = computed<FormSelectOption[]>(() => [
  { value: 'folder', label: t('quotation.pages.permissions.folder') },
  { value: 'document', label: t('quotation.pages.permissions.document') }
])
const targetOptions = computed<FormSelectOption[]>(() => {
  const targets =
    targetType.value === 'folder'
      ? props.context.folders
      : props.context.documents
  return targets.map((target) => ({
    value: 'file_name' in target ? target.id : target.token,
    label: targetLabel(target)
  }))
})
const minimumExpiry = computed(() => toLocalInput(new Date().toISOString()))

watch(targetType, () => {
  targetId.value = ''
})

function targetLabel(target: ViewPermissionFolder | ViewPermissionDocument) {
  return 'file_name' in target ? target.file_name : target.name
}

function toLocalInput(value: string) {
  const date = new Date(value)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function grant() {
  if (!selectedUserId.value || !targetId.value) {
    emit('invalid')
    return
  }
  const expiry = expiresAt.value
    ? new Date(expiresAt.value).toISOString()
    : null
  emit('grant', {
    user_id: Number(selectedUserId.value),
    target_type: targetType.value,
    target_id: targetId.value,
    expires_at: expiry
  })
}
</script>

<template>
  <div class="dm-card p-4">
    <div class="flex items-center gap-2">
      <Eye class="h-4 w-4 text-dm-primary" />
      <h3 id="view-grants-title" class="font-semibold">
        {{ t('quotation.pages.permissions.addTitle') }}
      </h3>
    </div>
    <div class="mt-4 grid gap-4 lg:grid-cols-5 lg:items-end">
      <label class="text-sm">
        <span class="mb-1.5 block text-dm-text-secondary">
          {{ t('quotation.pages.permissions.userLabel') }}
        </span>
        <FormSelect
          v-model="selectedUserId"
          :options="userOptions"
          :placeholder="t('quotation.pages.permissions.selectUser')"
        />
      </label>
      <label class="text-sm">
        <span class="mb-1.5 block text-dm-text-secondary">
          {{ t('quotation.pages.permissions.scopeLabel') }}
        </span>
        <FormSelect v-model="targetType" :options="targetTypeOptions" />
      </label>
      <label class="text-sm">
        <span class="mb-1.5 block text-dm-text-secondary">
          {{ t('quotation.pages.permissions.targetLabel') }}
        </span>
        <FormSelect
          v-model="targetId"
          :options="targetOptions"
          :placeholder="t('quotation.pages.permissions.selectTarget')"
        />
      </label>
      <label class="text-sm">
        <span class="mb-1.5 block text-dm-text-secondary">
          {{ t('quotation.pages.permissions.expiryLabel') }}
        </span>
        <input
          v-model="expiresAt"
          type="datetime-local"
          :min="minimumExpiry"
          class="dm-input h-10 w-full"
        />
      </label>
      <button
        type="button"
        class="dm-btn-primary h-10 px-4 text-sm"
        :disabled="saving || loading"
        @click="grant"
      >
        <Eye class="h-4 w-4" />
        {{ t('quotation.pages.permissions.grant') }}
      </button>
    </div>
  </div>
</template>
