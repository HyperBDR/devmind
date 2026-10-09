<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  ShieldCheck,
  UserCog,
  X,
} from 'lucide-vue-next'

import type {
  CreatedMcpRobotCredential,
  McpRobotScope,
} from '../api/mcpRobots'
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
  generatingUserId: number | null
  generatedToken: CreatedMcpRobotCredential | null
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
  'generate-token': [userId: number]
  'close-token': []
}>()

const { t } = useQuotationI18n()
const roleDrafts = reactive<Record<number, QuotationMembershipRole | ''>>({})
const invoiceRoleDrafts = reactive<Record<number, InvoiceAccessRole | ''>>({})
const invoiceExpiryDrafts = reactive<Record<number, string>>({})
const copiedToken = ref(false)
const copyFailed = ref(false)

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

watch(
  () => props.generatedToken?.id,
  () => {
    copiedToken.value = false
    copyFailed.value = false
  },
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

function memberScopes(member: QuotationMembershipRecord): McpRobotScope[] {
  const scopes: McpRobotScope[] = []
  if (member.role) scopes.push('quotation:read')
  if (invoicePermission(member)?.status === 'active') {
    scopes.push('invoice:read')
  }
  return scopes
}

function scopeLabel(scope: McpRobotScope): string {
  return scope === 'quotation:read'
    ? t('quotation.pages.permissions.mcpQuotationRead')
    : t('quotation.pages.permissions.mcpInvoiceRead')
}

function formatExpiry(value: string | null) {
  if (!value) return t('quotation.pages.permissions.noExpiry')
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(value))
}

async function copyToken() {
  if (!props.generatedToken) return
  try {
    await navigator.clipboard.writeText(props.generatedToken.token)
    copiedToken.value = true
    copyFailed.value = false
  } catch {
    copiedToken.value = false
    copyFailed.value = true
  }
}

function selectToken(event: FocusEvent) {
  if (event.target instanceof HTMLInputElement) event.target.select()
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
      <p class="mt-2 text-xs text-dm-text-tertiary">
        {{ t('quotation.pages.permissions.mcpTokenHint') }}
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
    <div v-else class="overflow-x-auto">
      <table class="dm-table workspace-access-table min-w-[1100px] table-fixed">
        <colgroup>
          <col>
          <col>
          <col>
          <col>
          <col class="w-[256px]">
        </colgroup>
        <thead class="bg-dm-surface text-dm-text-secondary">
          <tr>
            <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.platformColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.invoiceColumn') }}</th>
            <th>{{ t('quotation.pages.permissions.expiryLabel') }}</th>
            <th>
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
            <td>
              <div class="flex flex-nowrap items-center gap-2">
                <button
                  type="button"
                  class="dm-btn-primary shrink-0 whitespace-nowrap px-2.5 py-2 text-sm"
                  :disabled="saving || !hasChanges(member)"
                  @click="saveChanges(member)"
                >
                  <ShieldCheck class="h-4 w-4" />
                  {{ t('quotation.pages.permissions.saveWorkspaceAccess') }}
                </button>
                <button
                  type="button"
                  class="dm-btn-default shrink-0 whitespace-nowrap px-2.5 py-2 text-sm disabled:opacity-50"
                  :disabled="saving || generatingUserId !== null || memberScopes(member).length === 0 || hasChanges(member)"
                  @click="emit('generate-token', member.user_id)"
                >
                  <span
                    v-if="generatingUserId === member.user_id"
                    class="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
                  />
                  <ShieldCheck v-else class="h-4 w-4" />
                  {{ t('quotation.pages.permissions.generateMcpToken') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <Teleport to="body">
    <div
      v-if="generatedToken"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-[2px]"
      role="presentation"
      @click.self="emit('close-token')"
    >
      <div
        class="w-full max-w-xl rounded-xl border border-dm-border-light bg-white p-5 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mcp-token-title"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <h2 id="mcp-token-title" class="text-lg font-bold text-dm-text">
              {{ t('quotation.pages.permissions.mcpTokenGenerated') }}
            </h2>
            <p class="mt-1 text-sm text-dm-text-secondary">
              {{ t('quotation.pages.permissions.mcpTokenOneTime') }}
            </p>
          </div>
          <button
            type="button"
            class="rounded-md p-1.5 text-dm-text-tertiary hover:bg-slate-100"
            :aria-label="t('quotation.common.close')"
            @click="emit('close-token')"
          >
            <X class="h-5 w-5" />
          </button>
        </div>
        <div class="mt-4 flex flex-wrap gap-2">
          <span
            v-for="scope in generatedToken.scopes"
            :key="scope"
            class="rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-800"
          >
            {{ scopeLabel(scope) }}
          </span>
        </div>
        <p class="mt-3 text-sm text-dm-text-secondary">
          {{ t('quotation.pages.permissions.mcpTokenExpiryLabel') }}
          {{ formatExpiry(generatedToken.expires_at) }}
        </p>
        <label class="mt-4 block text-sm font-medium text-dm-text">
          {{ t('quotation.pages.permissions.mcpTokenLabel') }}
          <input
            :value="generatedToken.token"
            readonly
            class="dm-input mt-1 font-mono text-sm"
            @focus="selectToken"
          >
        </label>
        <div class="mt-4 flex justify-end gap-2">
          <button
            type="button"
            class="dm-btn-default px-4 py-2 text-sm"
            @click="emit('close-token')"
          >
            {{ t('quotation.common.close') }}
          </button>
          <button
            type="button"
            class="dm-btn-primary px-4 py-2 text-sm"
            @click="copyToken"
          >
            {{ copiedToken
              ? t('quotation.pages.permissions.mcpTokenCopied')
              : t('quotation.pages.permissions.copyMcpToken') }}
          </button>
        </div>
        <p
          v-if="copyFailed"
          class="mt-3 text-sm text-red-700"
          role="alert"
        >
          {{ t('quotation.pages.permissions.mcpTokenCopyFailed') }}
        </p>
      </div>
    </div>
  </Teleport>
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
