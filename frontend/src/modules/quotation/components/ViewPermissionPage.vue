<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { KeyRound, RefreshCw } from 'lucide-vue-next'

import {
  assignMembership,
  getMembershipContext,
  grantViewPermission,
  revokeViewPermission,
  updateMembershipRole,
  updateViewPermissionExpiry,
  type QuotationMembershipContext,
  type QuotationMembershipRole,
  type ViewPermissionContext
} from '../api/viewPermissions'
import { useQuotationViewPermissionAccess } from '../composables/useQuotationViewPermissionAccess'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import UserPermissionSection from './UserPermissionSection.vue'
import ViewGrantSection from './ViewGrantSection.vue'

type GrantPayload = Parameters<typeof grantViewPermission>[0]

const { t } = useQuotationI18n()
const viewPermissionAccess = useQuotationViewPermissionAccess()
const viewContext = ref<ViewPermissionContext>({
  users: [],
  folders: [],
  documents: [],
  permissions: []
})
const membershipContext = ref<QuotationMembershipContext>({
  members: [],
  role_options: []
})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')

function syncViewContext() {
  if (viewPermissionAccess.context.value) {
    viewContext.value = viewPermissionAccess.context.value
  }
}

async function load(force = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const [allowed, memberships] = await Promise.all([
      viewPermissionAccess.ensure(force),
      getMembershipContext()
    ])
    if (!allowed) {
      throw new Error(t('quotation.pages.permissions.loadFailed'))
    }
    syncViewContext()
    membershipContext.value = memberships
  } catch (loadError: unknown) {
    error.value =
      loadError instanceof Error
        ? loadError.message
        : t('quotation.pages.permissions.loadFailed')
  } finally {
    loading.value = false
  }
}

async function mutate(
  action: () => Promise<unknown>,
  successKey: string,
  failureKey: string
) {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await action()
    message.value = t(successKey)
    await load(true)
  } catch (mutationError: unknown) {
    error.value =
      mutationError instanceof Error ? mutationError.message : t(failureKey)
  } finally {
    saving.value = false
  }
}

function assignRole(userId: number, role: QuotationMembershipRole) {
  void mutate(
    () => assignMembership({ user_id: userId, role }),
    'quotation.pages.permissions.roleSuccess',
    'quotation.pages.permissions.roleFailed'
  )
}

function changeRole(id: number, role: QuotationMembershipRole) {
  void mutate(
    () => updateMembershipRole(id, role),
    'quotation.pages.permissions.roleSuccess',
    'quotation.pages.permissions.roleFailed'
  )
}

function grant(payload: GrantPayload) {
  void mutate(
    () => grantViewPermission(payload),
    'quotation.pages.permissions.grantSuccess',
    'quotation.pages.permissions.grantFailed'
  )
}

function saveExpiry(id: number, expiresAt: string | null) {
  void mutate(
    () => updateViewPermissionExpiry(id, expiresAt),
    'quotation.pages.permissions.editSuccess',
    'quotation.pages.permissions.editFailed'
  )
}

function revoke(id: number) {
  void mutate(
    () => revokeViewPermission(id),
    'quotation.pages.permissions.revokeSuccess',
    'quotation.pages.permissions.revokeFailed'
  )
}

function showSelectionError() {
  error.value = t('quotation.pages.permissions.selectRequired')
}

onMounted(() => {
  syncViewContext()
  void load()
})
</script>

<template>
  <section class="min-w-0 max-w-full space-y-4 text-dm-text">
    <div
      class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between"
    >
      <div>
        <div class="flex items-center gap-2">
          <KeyRound class="h-5 w-5 text-dm-primary" />
          <h2 class="text-xl font-semibold text-dm-text">
            {{ t('quotation.pages.permissions.title') }}
          </h2>
        </div>
        <p class="mt-1 text-sm text-dm-text-secondary">
          {{ t('quotation.pages.permissions.subtitle') }}
        </p>
      </div>
      <button
        type="button"
        class="dm-btn-default px-3 py-2 text-sm"
        :disabled="loading || saving"
        :aria-busy="loading"
        @click="load(true)"
      >
        <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
        {{
          loading
            ? t('quotation.common.refreshing')
            : t('quotation.common.refresh')
        }}
      </button>
    </div>

    <p
      v-if="error"
      role="alert"
      class="rounded-dm bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {{ error }}
    </p>
    <p
      v-if="message"
      role="status"
      class="rounded-dm bg-green-50 px-4 py-3 text-sm text-green-700"
    >
      {{ message }}
    </p>

    <UserPermissionSection
      :context="membershipContext"
      :loading="loading"
      :saving="saving"
      @assign="assignRole"
      @change="changeRole"
    />
    <ViewGrantSection
      :context="viewContext"
      :loading="loading"
      :saving="saving"
      @grant="grant"
      @update-expiry="saveExpiry"
      @revoke="revoke"
      @invalid="showSelectionError"
    />
  </section>
</template>
