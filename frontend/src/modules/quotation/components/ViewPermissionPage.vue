<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  CheckCircle2,
  Clock3,
  FolderUp,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
  XCircle,
} from 'lucide-vue-next'

import {
  decideAccessRequest,
  getAccessRequestContext,
  type AccessRequestContext,
  type AccessRequestRecord,
  type AccessRequestType,
} from '../api/accessRequests'
import {
  getUploadPermissionContext,
  grantUploadPermission,
  revokeUploadPermission,
  updateUploadPermission,
  type UploadPermissionContext,
} from '../api/uploadPermissions'
import {
  assignMembership,
  getMembershipContext,
  getViewPermissionContext,
  grantViewPermission,
  revokeViewPermission,
  updateMembershipRole,
  updateViewPermissionExpiry,
  type QuotationMembershipContext,
  type QuotationMembershipRole,
  type ViewPermissionContext,
} from '../api/viewPermissions'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import FormSelect, { type FormSelectOption } from './FormSelect.vue'
import UserPermissionSection from './UserPermissionSection.vue'
import ViewGrantSection from './ViewGrantSection.vue'

type GrantPayload = Parameters<typeof grantViewPermission>[0]

const { t } = useQuotationI18n()

const emptyAccessContext = (): AccessRequestContext => ({
  is_admin: false,
  folders: [],
  documents: [],
  requests: [],
})
const emptyViewContext = (): ViewPermissionContext => ({
  users: [],
  folders: [],
  documents: [],
  permissions: [],
})
const emptyUploadContext = (): UploadPermissionContext => ({
  users: [],
  folders: [],
  permissions: [],
})

const accessContext = ref(emptyAccessContext())
const viewContext = ref(emptyViewContext())
const uploadContext = ref(emptyUploadContext())
const membershipContext = ref<QuotationMembershipContext>({
  members: [],
  role_options: [],
})
const loading = ref(false)
const saving = ref(false)
const decidingId = ref<number | null>(null)
const error = ref('')
const message = ref('')

const uploadUserId = ref('')
const uploadFolderToken = ref('')
const uploadExpiresAt = ref('')
const uploadExpiryDrafts = ref<Record<number, string>>({})
const decisionExpiryDrafts = ref<Record<number, string>>({})
const reviewNotes = ref<Record<number, string>>({})

const isAdmin = computed(() => accessContext.value.is_admin)

const adminUserOptions = computed<FormSelectOption[]>(() =>
  viewContext.value.users.map((user) => ({
    value: String(user.id),
    label: `${user.name} (${user.username})`,
  })),
)

const uploadFolderOptions = computed<FormSelectOption[]>(() =>
  uploadContext.value.folders.map((folder) => ({
    value: folder.token,
    label: folder.name,
  })),
)

function toLocalDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function toApiDateTime(value: string): string | null {
  return value ? new Date(value).toISOString() : null
}

function formatDateTime(value: string | null): string {
  if (!value) return t('quotation.pages.permissions.noExpiry')
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function resetFeedback() {
  error.value = ''
  message.value = ''
}

function populateDrafts() {
  uploadExpiryDrafts.value = Object.fromEntries(
    uploadContext.value.permissions.map((permission) => [
      permission.id,
      toLocalDateTime(permission.expires_at),
    ]),
  )
  decisionExpiryDrafts.value = Object.fromEntries(
    accessContext.value.requests.map((request) => [
      request.id,
      toLocalDateTime(request.expires_at),
    ]),
  )
}

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    accessContext.value = await getAccessRequestContext()
    if (accessContext.value.is_admin) {
      const [viewPermissions, uploadPermissions, memberships] =
        await Promise.all([
          getViewPermissionContext(),
          getUploadPermissionContext(),
          getMembershipContext(),
        ])
      viewContext.value = viewPermissions
      uploadContext.value = uploadPermissions
      membershipContext.value = memberships
    } else {
      viewContext.value = emptyViewContext()
      uploadContext.value = emptyUploadContext()
      membershipContext.value = { members: [], role_options: [] }
    }
    populateDrafts()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t('quotation.pages.permissions.loadFailed')
  } finally {
    loading.value = false
  }
}

async function mutate(
  action: () => Promise<unknown>,
  successKey: string,
  failureKey: string,
) {
  saving.value = true
  resetFeedback()
  try {
    await action()
    message.value = t(successKey)
    await load()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t(failureKey)
  } finally {
    saving.value = false
  }
}

function assignRole(userId: number, role: QuotationMembershipRole) {
  void mutate(
    () => assignMembership({ user_id: userId, role }),
    'quotation.pages.permissions.roleSuccess',
    'quotation.pages.permissions.roleFailed',
  )
}

function changeRole(id: number, role: QuotationMembershipRole) {
  void mutate(
    () => updateMembershipRole(id, role),
    'quotation.pages.permissions.roleSuccess',
    'quotation.pages.permissions.roleFailed',
  )
}

function grantView(payload: GrantPayload) {
  void mutate(
    () => grantViewPermission(payload),
    'quotation.pages.permissions.grantSuccess',
    'quotation.pages.permissions.grantFailed',
  )
}

function saveViewExpiry(id: number, expiresAt: string | null) {
  void mutate(
    () => updateViewPermissionExpiry(id, expiresAt),
    'quotation.pages.permissions.editSuccess',
    'quotation.pages.permissions.editFailed',
  )
}

function revokeView(id: number) {
  if (!window.confirm(t('quotation.pages.permissions.revokeConfirm'))) return
  void mutate(
    () => revokeViewPermission(id),
    'quotation.pages.permissions.revokeSuccess',
    'quotation.pages.permissions.revokeFailed',
  )
}

function showSelectionError() {
  error.value = t('quotation.pages.permissions.selectRequired')
}

async function grantUpload() {
  if (!uploadUserId.value || !uploadFolderToken.value) {
    error.value = t('quotation.pages.permissions.uploadSelectRequired')
    return
  }
  saving.value = true
  resetFeedback()
  try {
    await grantUploadPermission({
      user_id: Number(uploadUserId.value),
      folder_token: uploadFolderToken.value,
      expires_at: toApiDateTime(uploadExpiresAt.value),
    })
    uploadFolderToken.value = ''
    message.value = t('quotation.pages.permissions.uploadGrantSuccess')
    await load()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t('quotation.pages.permissions.uploadGrantFailed')
  } finally {
    saving.value = false
  }
}

async function saveUploadExpiry(id: number) {
  resetFeedback()
  try {
    await updateUploadPermission(
      id,
      toApiDateTime(uploadExpiryDrafts.value[id] || ''),
    )
    message.value = t('quotation.pages.permissions.uploadUpdateSuccess')
    await load()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t('quotation.pages.permissions.uploadUpdateFailed')
  }
}

async function revokeUpload(id: number) {
  if (!window.confirm(
    t('quotation.pages.permissions.uploadRevokeConfirm'),
  )) return
  resetFeedback()
  try {
    await revokeUploadPermission(id)
    message.value = t('quotation.pages.permissions.uploadRevokeSuccess')
    await load()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t('quotation.pages.permissions.uploadRevokeFailed')
  }
}

async function decide(
  accessRequest: AccessRequestRecord,
  action: 'approve' | 'reject' | 'revoke' | 'expire',
) {
  if (
    action !== 'approve'
    && !window.confirm(t('quotation.pages.permissions.decisionConfirm'))
  ) return
  decidingId.value = accessRequest.id
  resetFeedback()
  try {
    await decideAccessRequest(accessRequest.id, {
      action,
      review_note: reviewNotes.value[accessRequest.id] || '',
      expires_at: action === 'approve'
        ? toApiDateTime(
          decisionExpiryDrafts.value[accessRequest.id] || '',
        )
        : undefined,
    })
    message.value = t('quotation.pages.permissions.decisionSuccess')
    await load()
  } catch (err: unknown) {
    error.value = err instanceof Error
      ? err.message
      : t('quotation.pages.permissions.decisionFailed')
  } finally {
    decidingId.value = null
  }
}

function requestTypeLabel(type: AccessRequestType): string {
  return t(`quotation.pages.permissions.requestTypes.${type}`)
}

function statusClass(status: AccessRequestRecord['status']): string {
  return {
    pending: 'bg-amber-50 text-amber-700 ring-amber-200',
    approved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    rejected: 'bg-red-50 text-red-700 ring-red-200',
    revoked: 'bg-slate-100 text-slate-700 ring-slate-200',
    expired: 'bg-slate-100 text-slate-700 ring-slate-200',
  }[status]
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="min-w-0 max-w-full space-y-5 text-dm-text">
    <div class="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div>
        <div class="flex items-center gap-2">
          <ShieldCheck class="h-5 w-5 text-dm-primary" />
          <h2 class="text-xl font-semibold">
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
        :disabled="loading"
        :aria-busy="loading"
        @click="load"
      >
        <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" />
        {{ loading ? t('quotation.common.refreshing') : t('quotation.common.refresh') }}
      </button>
    </div>

    <p v-if="error" class="rounded-dm bg-red-50 px-4 py-3 text-sm text-red-700">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-dm bg-green-50 px-4 py-3 text-sm text-green-700">
      {{ message }}
    </p>

    <div class="dm-card overflow-hidden">
      <div class="border-b border-dm-border-light bg-[#fafafa] px-4 py-3">
        <h3 class="font-semibold">
          {{ isAdmin
            ? t('quotation.pages.permissions.reviewTitle')
            : t('quotation.pages.permissions.myRequestsTitle') }}
        </h3>
      </div>
      <div v-if="loading" class="px-4 py-8 text-center text-sm text-dm-text-secondary">
        {{ t('quotation.common.loading') }}
      </div>
      <div
        v-else-if="accessContext.requests.length === 0"
        class="px-4 py-8 text-center text-sm text-dm-text-secondary"
      >
        {{ t('quotation.pages.permissions.requestsEmpty') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="dm-table min-w-[920px]">
          <thead class="bg-dm-surface text-dm-text-secondary">
            <tr>
              <th v-if="isAdmin">{{ t('quotation.pages.permissions.applicantColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.requestColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.targetColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.reasonColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.statusColumn') }}</th>
              <th>{{ t('quotation.pages.permissions.resultColumn') }}</th>
              <th v-if="isAdmin" class="min-w-[260px]">
                {{ t('quotation.pages.permissions.actionsColumn') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in accessContext.requests" :key="item.id">
              <td v-if="isAdmin">{{ item.applicant }}</td>
              <td>{{ requestTypeLabel(item.request_type) }}</td>
              <td>{{ item.target_name }}</td>
              <td class="max-w-[260px] whitespace-normal">{{ item.reason }}</td>
              <td>
                <span
                  class="inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset"
                  :class="statusClass(item.status)"
                >
                  {{ t(`quotation.pages.permissions.statuses.${item.status}`) }}
                </span>
              </td>
              <td class="whitespace-normal text-dm-text-secondary">
                <div v-if="item.reviewer" class="font-medium text-dm-text">
                  {{ item.reviewer }}
                </div>
                <div v-if="item.review_note">{{ item.review_note }}</div>
                <div v-if="item.status === 'approved'" class="text-xs">
                  {{ formatDateTime(item.expires_at) }}
                </div>
                <span v-if="!item.reviewer && !item.review_note">—</span>
              </td>
              <td v-if="isAdmin">
                <div v-if="item.status === 'pending'" class="space-y-2">
                  <div class="grid grid-cols-2 gap-2">
                    <input
                      v-model="decisionExpiryDrafts[item.id]"
                      type="datetime-local"
                      class="dm-input text-xs"
                      :aria-label="t('quotation.pages.permissions.expiryLabel')"
                    >
                    <input
                      v-model="reviewNotes[item.id]"
                      type="text"
                      maxlength="2000"
                      class="dm-input text-xs"
                      :placeholder="t('quotation.pages.permissions.reviewNotePlaceholder')"
                    >
                  </div>
                  <div class="flex gap-2">
                    <button
                      type="button"
                      class="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700"
                      :disabled="decidingId === item.id"
                      @click="decide(item, 'approve')"
                    >
                      <CheckCircle2 class="h-3.5 w-3.5" />
                      {{ t('quotation.pages.permissions.approve') }}
                    </button>
                    <button
                      type="button"
                      class="inline-flex items-center gap-1 text-xs font-semibold text-red-700"
                      :disabled="decidingId === item.id"
                      @click="decide(item, 'reject')"
                    >
                      <XCircle class="h-3.5 w-3.5" />
                      {{ t('quotation.pages.permissions.reject') }}
                    </button>
                  </div>
                </div>
                <div v-else-if="item.status === 'approved'" class="flex gap-3">
                  <button
                    type="button"
                    class="text-xs font-semibold text-red-700"
                    :disabled="decidingId === item.id"
                    @click="decide(item, 'revoke')"
                  >
                    {{ t('quotation.pages.permissions.revoke') }}
                  </button>
                  <button
                    type="button"
                    class="text-xs font-semibold text-slate-700"
                    :disabled="decidingId === item.id"
                    @click="decide(item, 'expire')"
                  >
                    {{ t('quotation.pages.permissions.expire') }}
                  </button>
                </div>
                <span v-else class="text-dm-text-tertiary">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template v-if="isAdmin">
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
        @grant="grantView"
        @update-expiry="saveViewExpiry"
        @revoke="revokeView"
        @invalid="showSelectionError"
      />

      <div class="grid gap-5 xl:grid-cols-2">
        <div class="dm-card p-4">
          <div class="flex items-center gap-2">
            <FolderUp class="h-5 w-5 text-dm-primary" />
            <h3 class="font-semibold">
              {{ t('quotation.pages.permissions.uploadGrantTitle') }}
            </h3>
          </div>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <FormSelect
              v-model="uploadUserId"
              :options="adminUserOptions"
              :placeholder="t('quotation.pages.permissions.selectUser')"
            />
            <FormSelect
              v-model="uploadFolderToken"
              :options="uploadFolderOptions"
              :placeholder="t('quotation.pages.permissions.selectDirectory')"
            />
            <input
              v-model="uploadExpiresAt"
              type="datetime-local"
              class="dm-input sm:col-span-2"
              :aria-label="t('quotation.pages.permissions.expiryLabel')"
            >
          </div>
          <button
            type="button"
            class="dm-btn-primary mt-4 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="saving || loading"
            @click="grantUpload"
          >
            <FolderUp class="h-4 w-4" />
            {{ t('quotation.pages.permissions.grantUpload') }}
          </button>
        </div>

        <div class="dm-card overflow-hidden">
          <div class="border-b border-dm-border-light bg-[#fafafa] px-4 py-3 font-semibold">
            {{ t('quotation.pages.permissions.currentUploadTitle') }}
          </div>
          <div v-if="uploadContext.permissions.length === 0" class="px-4 py-8 text-center text-sm text-dm-text-secondary">
            {{ t('quotation.pages.permissions.uploadEmpty') }}
          </div>
          <div v-else class="overflow-x-auto">
            <table class="dm-table min-w-[700px]">
              <thead><tr>
                <th>{{ t('quotation.pages.permissions.userColumn') }}</th>
                <th>{{ t('quotation.pages.permissions.targetColumn') }}</th>
                <th>{{ t('quotation.pages.permissions.expiryLabel') }}</th>
                <th class="text-right">{{ t('quotation.pages.permissions.actionsColumn') }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="permission in uploadContext.permissions" :key="permission.id">
                  <td>{{ permission.user_name }}</td>
                  <td>{{ permission.folder_name }}</td>
                  <td>
                    <input
                      v-model="uploadExpiryDrafts[permission.id]"
                      type="datetime-local"
                      class="dm-input text-xs"
                    >
                  </td>
                  <td class="text-right">
                    <div class="inline-flex gap-3">
                      <button type="button" class="inline-flex items-center gap-1 text-blue-700" @click="saveUploadExpiry(permission.id)">
                        <Save class="h-4 w-4" />
                        {{ t('quotation.pages.permissions.save') }}
                      </button>
                      <button type="button" class="inline-flex items-center gap-1 text-red-600" @click="revokeUpload(permission.id)">
                        <Trash2 class="h-4 w-4" />
                        {{ t('quotation.pages.permissions.revoke') }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <div v-if="loading && !accessContext.requests.length" class="sr-only" aria-live="polite">
      <Clock3 class="h-4 w-4" />
      {{ t('quotation.common.loading') }}
    </div>
  </section>
</template>
