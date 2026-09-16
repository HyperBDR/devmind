<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import {
  ShieldCheck,
  UserCog
} from 'lucide-vue-next'

import type {
  InvoiceAccessContext,
  InvoiceAccessRecord,
  InvoiceAccessRole
} from '../api/invoicePermissions'
import type {
  QuotationMembershipContext,
  QuotationMembershipRecord,
  QuotationMembershipRole
} from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const props = defineProps<{
  context: QuotationMembershipContext
  invoiceContext: InvoiceAccessContext
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  save: [payload: {
    userId: number
    membershipId: number | null
    currentRole: QuotationMembershipRole | null
    role: QuotationMembershipRole | null
    invoiceEnabled: boolean
    invoicePermissionId: number | null
    invoicePermissionStatus: 'active' | 'expired' | null
    invoiceRole: InvoiceAccessRole
    currentInvoiceRole: InvoiceAccessRole | null
    invoiceExpiresAt: string
    currentInvoiceExpiresAt: string | null
  }]
}>()

const { t } = useQuotationI18n()
const roleDrafts = reactive<Record<number, QuotationMembershipRole | ''>>({})
const invoiceRoleDrafts = reactive<Record<number, InvoiceAccessRole | ''>>({})
const invoiceExpiryDrafts = reactive<Record<number, string>>({})

const roleOptions = computed(() => [
  {
    value: 'quotation_user',
    label: t('quotation.pages.permissions.quotationUser')
  },
  {
    value: 'quotation_admin',
    label: t('quotation.pages.permissions.quotationAdmin')
  }
])

const invoiceRoleOptions = computed(() => [
  {
    value: 'invoice_user' as InvoiceAccessRole,
    label: t('quotation.pages.permissions.invoiceRoleUser')
  },
  {
    value: 'invoice_admin' as InvoiceAccessRole,
    label: t('quotation.pages.permissions.invoiceRoleAdmin')
  }
])

const invoicePermissions = computed(
  () => new Map(
    props.invoiceContext.permissions.map((permission) => [
      permission.user_id,
      permission
    ])
  )
)

function toLocalDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

watch(
  () => props.context.members,
  (members) => {
    for (const member of members) {
      roleDrafts[member.user_id] = member.role || ''
    }
  },
  { immediate: true }
)

watch(
  () => props.invoiceContext.permissions,
  (permissions) => {
    for (const member of props.context.members) {
      invoiceRoleDrafts[member.user_id] = ''
      invoiceExpiryDrafts[member.user_id] = ''
    }
    for (const permission of permissions) {
      invoiceRoleDrafts[permission.user_id] = permission.status === 'active'
        ? permission.role
        : ''
      invoiceExpiryDrafts[permission.user_id] = toLocalDateTime(
        permission.expires_at
      )
    }
  },
  { immediate: true }
)

function selectedRole(member: QuotationMembershipRecord) {
  return roleDrafts[member.user_id] || null
}

function roleChanged(member: QuotationMembershipRecord) {
  return member.role !== selectedRole(member)
}

function invoicePermission(
  member: QuotationMembershipRecord
): InvoiceAccessRecord | undefined {
  return invoicePermissions.value.get(member.user_id)
}

function invoiceEnabled(member: QuotationMembershipRecord) {
  return selectedInvoiceRole(member) !== ''
}

function selectedInvoiceRole(
  member: QuotationMembershipRecord
): InvoiceAccessRole | '' {
  return invoiceRoleDrafts[member.user_id] || ''
}

function roleDotClass(role: string | null | undefined): string {
  if (role === 'quotation_admin' || role === 'invoice_admin') {
    return 'bg-indigo-700'
  }
  if (role === 'quotation_user' || role === 'invoice_user') {
    return 'bg-sky-400'
  }
  return 'bg-slate-400'
}

function invoiceExpiryChanged(member: QuotationMembershipRecord) {
  const permission = invoicePermission(member)
  if (!permission || !invoiceEnabled(member)) return false
  return (invoiceExpiryDrafts[member.user_id] || '') !== (
    toLocalDateTime(permission.expires_at)
  )
}

function invoiceAccessChanged(member: QuotationMembershipRecord) {
  const currentlyEnabled = invoicePermission(member)?.status === 'active'
  return currentlyEnabled !== invoiceEnabled(member)
}

function invoiceRoleChanged(member: QuotationMembershipRecord) {
  const currentRole = invoicePermission(member)?.status === 'active'
    ? invoicePermission(member)?.role || null
    : null
  return currentRole !== (selectedInvoiceRole(member) || null)
}

function hasChanges(member: QuotationMembershipRecord) {
  return roleChanged(member)
    || invoiceAccessChanged(member)
    || invoiceRoleChanged(member)
    || invoiceExpiryChanged(member)
}

function saveChanges(member: QuotationMembershipRecord) {
  const permission = invoicePermission(member)
  emit('save', {
    userId: member.user_id,
    membershipId: member.id,
    currentRole: member.role,
    role: selectedRole(member),
    invoiceEnabled: invoiceEnabled(member),
    invoicePermissionId: permission?.id || null,
    invoicePermissionStatus: permission?.status || null,
    invoiceRole: selectedInvoiceRole(member) || 'invoice_user',
    currentInvoiceRole: permission?.role || null,
    invoiceExpiresAt: invoiceExpiryDrafts[member.user_id] || '',
    currentInvoiceExpiresAt: permission?.expires_at || null
  })
}
</script>

<template>
  <section
    class="dm-card overflow-hidden"
    aria-labelledby="workspace-access-title"
  >
    <div class="border-b border-dm-border-light bg-dm-surface px-4 py-3">
      <div class="flex items-center gap-2">
        <UserCog class="h-4 w-4 text-dm-primary" />
        <h3 id="workspace-access-title" class="font-semibold">
          {{ t('quotation.pages.permissions.userPermissionsTitle') }}
        </h3>
      </div>
      <p class="mt-1 text-sm text-dm-text-secondary">
        {{ t('quotation.pages.permissions.userPermissionsSubtitle') }}
      </p>
      <p class="mt-2 text-xs text-dm-text-tertiary">
        {{ t('quotation.pages.permissions.platformAccessHint') }}
      </p>
      <div class="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
        <span class="text-dm-text-secondary">
          <strong class="font-semibold text-dm-text">
            {{ t('quotation.pages.permissions.invoiceRoleUser') }}
          </strong>
          · {{ t('quotation.pages.permissions.invoiceRoleUserHint') }}
        </span>
        <span class="text-dm-text-secondary">
          <strong class="font-semibold text-dm-text">
            {{ t('quotation.pages.permissions.invoiceRoleAdmin') }}
          </strong>
          · {{ t('quotation.pages.permissions.invoiceRoleAdminHint') }}
        </span>
      </div>
    </div>

    <div
      v-if="loading"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.common.loading') }}
    </div>
    <div
      v-else-if="context.members.length === 0"
      class="px-4 py-8 text-center text-sm text-dm-text-secondary"
    >
      {{ t('quotation.pages.permissions.noManagedUsers') }}
    </div>
    <div v-else class="overflow-hidden">
      <table class="dm-table workspace-access-table table-fixed">
        <colgroup>
          <col class="w-[22%]">
          <col class="w-[22%]">
          <col class="w-[22%]">
          <col class="w-[18%]">
          <col class="w-[16%]">
        </colgroup>
        <thead class="bg-dm-surface text-dm-text-secondary">
          <tr>
            <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.platformColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.invoiceColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.expiryLabel') }}</th>
            <th class="text-right">
              {{ t('quotation.pages.permissions.actionsColumn') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="member in context.members" :key="member.user_id">
            <td>
              <div class="font-medium">{{ member.name }}</div>
              <div class="text-xs text-dm-text-secondary">
                {{ member.email || member.username }}
              </div>
            </td>
            <td>
              <div class="relative">
                <span
                  class="pointer-events-none absolute left-3 top-1/2 z-10 h-2.5 w-2.5 -translate-y-1/2 rounded-full"
                  :class="roleDotClass(selectedRole(member))"
                >
                </span>
                <select
                  v-model="roleDrafts[member.user_id]"
                  class="dm-input cursor-pointer pl-8"
                  :aria-label="t('quotation.pages.permissions.roleColumn')"
                >
                  <option value="">
                    {{ t('quotation.pages.permissions.platformOff') }}
                  </option>
                  <option
                    v-for="option in roleOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </td>
            <td>
              <div class="relative">
                <span
                  class="pointer-events-none absolute left-3 top-1/2 z-10 h-2.5 w-2.5 -translate-y-1/2 rounded-full"
                  :class="roleDotClass(selectedInvoiceRole(member))"
                >
                </span>
                <select
                  v-model="invoiceRoleDrafts[member.user_id]"
                  class="dm-input cursor-pointer pl-8"
                  :disabled="saving"
                  :aria-label="t('quotation.pages.permissions.invoiceColumn')"
                >
                  <option value="">
                    {{ t('quotation.pages.permissions.platformOff') }}
                  </option>
                  <option
                    v-for="option in invoiceRoleOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </td>
            <td>
              <input
                v-model="invoiceExpiryDrafts[member.user_id]"
                type="datetime-local"
                class="dm-input text-xs"
                :disabled="!invoiceEnabled(member)"
                :aria-label="t('quotation.pages.permissions.expiryLabel')"
              >
            </td>
            <td class="text-right">
              <div class="flex justify-end">
                <button
                  type="button"
                  class="dm-btn-primary whitespace-nowrap px-2.5 py-2 text-sm"
                  :disabled="saving || !hasChanges(member)"
                  @click="saveChanges(member)"
                >
                  <ShieldCheck class="h-4 w-4" />
                  {{ t('quotation.pages.permissions.saveWorkspaceAccess') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.workspace-access-table th,
.workspace-access-table td {
  min-width: 0;
  padding: 10px;
  vertical-align: middle;
}

.workspace-access-table .dm-input {
  min-width: 0;
}

.workspace-access-table select.dm-input {
  padding-left: 2rem !important;
}

.workspace-access-table tbody tr:last-child td {
  border-bottom: 0;
}
</style>
